#!/usr/bin/env python3
"""M10 ceiling sweep — the two remaining named exploratory reads, funded
at the build design session 2026-08-26 (m10-ceiling-spec "Secondary /
exploratory reads": inform routing, NEVER gate). Read logic written
before any output is looked at, per the house exploratory discipline.

  marginal  auto-pay marginal attribution on the marginal stratum (the
            200 turns whose schedules ran under BOTH paymodes): joint vs
            auto-only certification (2x2 + Wilson rates), same-schedule
            twin composite deltas on SCORE rolls (payment's contribution
            GIVEN the schedule — the twin shares the schedule, so
            selection bias cancels), and twin degrade/void rates
            (payment's contribution to schedule FEASIBILITY). The
            super-additivity pieces for the design discussion; assembly
            is the discussion's job, not this script's.
  binned    critic-binned gain (the LordOfThePigs instrument prototype):
            pre-turn critic P(win) at the fork window (the emis rule from
            schedule_sweep.eligible_turns), TWO critics per the
            early_doom convention — the era on-policy iter-019 critic and
            the standing d4-critic-fullvis; quintile-binned certification
            rate over the read turns + binned stage-2 dwr over the
            positives. Per-turn values emitted so the session can re-bin.

Usage:
  uv run python scripts/schedule_explore2.py marginal \
      --plan data/runs/sched-sweep-m10
  uv run python scripts/schedule_explore2.py binned \
      --plan data/runs/sched-sweep-m10 \
      --stores data/trajectories/m10-ceiling-census-20260825-212414
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sched_pins as pins  # noqa: E402
from schedule_read import (arm_scores, certify_turn, load_rows,  # noqa: E402
                           read_sched, wilson)

CRITICS = {
    "era_i019": "data/training/d6-run11/iter-019/critic/last.pt",
    "d4_fullvis": "data/training/d4-critic-fullvis/last.pt",
}


# ---------------------------------------------------------------- marginal

def marginal(args) -> None:
    plan = Path(args.plan)
    turns = load_rows([str(plan / "lanes-h2/lane-*.out.jsonl")])
    sched = read_sched(str(plan / "sched-h2.tsv"))
    joint = {(r["g"], r["t"]): r for r in map(
        json.loads, open(plan / "stage1-perturn.jsonl"))}

    stats = Counter()
    table = Counter()          # (joint_cert, auto_cert) 2x2 over both-read
    twin_deltas = []           # joint score mean - auto twin score mean
    twin_cert_survives = 0     # joint-certified whose auto twin also passes
    twin_cert_n = 0
    deg = Counter()            # degrade/void accounting over all twin pairs
    per_turn = []

    for key, plandef in sorted(sched.items()):
        auto_ids = [a for a in plandef["arms"] if a > 100]
        if not auto_ids:
            continue  # not a marginal-stratum turn
        stats["marginal_turns"] += 1
        jrec = joint.get(key)
        entry = turns.get(key)
        if jrec is None or not jrec.get("read") or entry is None:
            stats["joint_not_read"] += 1
            continue
        auto_entry = {"nat": entry["nat"],
                      "arms": {a: r for a, r in entry["arms"].items()
                               if a > 100},
                      "skips": entry["skips"]}
        arec = certify_turn(auto_entry, plandef["seat"], joint_only=False)
        if not arec["read"]:
            stats["auto_not_read"] += 1
            continue
        stats["both_read"] += 1
        jc, ac = bool(jrec["certified"]), bool(arec["certified"])
        table[(jc, ac)] += 1

        # same-schedule twin delta on the JOINT-selected arm (score rolls;
        # the twin shares the schedule so selection bias cancels)
        twin_id = jrec["arm"] + 100
        twin_rows = entry["arms"].get(twin_id, {})
        tw = arm_scores(twin_rows, entry["nat"], plandef["seat"],
                        pins.SCORE_ROLLS)
        rec = {"g": key[0], "t": key[1], "joint_cert": jc, "auto_cert": ac,
               "joint_arm": jrec["arm"], "auto_arm": arec["arm"],
               "joint_score": jrec["score_mean"],
               "auto_best_score": arec["score_mean"]}
        if len(tw) >= pins.MIN_VALID_ROLLS and not any(
                r.get("void") for r in twin_rows.values()):
            tmean = sum(tw) / len(tw)
            rec["twin_score"] = round(tmean, 3)
            twin_deltas.append(jrec["score_mean"] - tmean)
            if jc:
                twin_cert_n += 1
                agree = sum(1 for s in tw if (s > 0) == (tmean > 0)) / len(tw)
                if tmean >= pins.THETA and agree >= pins.CONSISTENT:
                    twin_cert_survives += 1
        per_turn.append(rec)

        # feasibility: degrade/void over ALL twin pairs of this turn
        for a, rows in entry["arms"].items():
            if a > 100 or (a + 100) not in entry["arms"]:
                continue
            for mode, rr in (("joint", rows), ("auto", entry["arms"][a + 100])):
                for r in rr.values():
                    deg[mode + "_rolls"] += 1
                    if r.get("degraded_at", -1) >= 0:
                        deg[mode + "_degraded"] += 1
                    if r.get("void"):
                        deg[mode + "_void"] += 1
                    w = r.get("degrade_why")
                    if w:
                        deg[f"{mode}_why_{w}"] += 1

    n = table[(True, True)] + table[(True, False)] + table[(False, True)] \
        + table[(False, False)]
    jk = table[(True, True)] + table[(True, False)]
    ak = table[(True, True)] + table[(False, True)]
    jp, jlo, jhi = wilson(jk, n)
    ap_, alo, ahi = wilson(ak, n)
    out = {
        "accounting": dict(stats),
        "table_2x2": {"both": table[(True, True)],
                      "joint_only": table[(True, False)],
                      "auto_only": table[(False, True)],
                      "neither": table[(False, False)]},
        "joint_rate": {"k": jk, "n": n, "rate": round(jp, 4),
                       "ci": [round(jlo, 4), round(jhi, 4)]},
        "auto_rate": {"k": ak, "n": n, "rate": round(ap_, 4),
                      "ci": [round(alo, 4), round(ahi, 4)]},
        "twin_delta_score": {
            "n": len(twin_deltas),
            "mean": round(statistics.mean(twin_deltas), 3)
            if twin_deltas else None,
            "median": round(statistics.median(twin_deltas), 3)
            if twin_deltas else None,
            "share_positive": round(sum(1 for d in twin_deltas if d > 0)
                                    / len(twin_deltas), 3)
            if twin_deltas else None,
        },
        "joint_certified_twin_survives_auto": [twin_cert_survives,
                                               twin_cert_n],
        "twin_feasibility": dict(deg),
        "twin_degrade_rate": {
            m: round(deg[m + "_degraded"] / deg[m + "_rolls"], 4)
            for m in ("joint", "auto") if deg[m + "_rolls"]},
    }
    json.dump(out, open(plan / "marginal-read.json", "w"), indent=2)
    with open(plan / "marginal-perturn.jsonl", "w") as f:
        for r in per_turn:
            f.write(json.dumps(r) + "\n")
    print(json.dumps(out, indent=2))


# ------------------------------------------------------------------ binned

def binned(args) -> None:
    from anvil.ante.ledger import ValueEvaluator
    from anvil.store.trajectories import TrajectoryStore

    plan = Path(args.plan)
    stage1 = {(r["g"], r["t"]): r for r in map(
        json.loads, open(plan / "stage1-perturn.jsonl")) if r.get("read")}
    stage2 = {(r["g"], r["t"]): r for r in map(
        json.loads, open(plan / "stage2-perturn.jsonl"))}
    sched = read_sched(str(plan / "sched-h2.tsv"))
    wanted = defaultdict(dict)  # g -> {t: seat}
    for (g, t) in stage1:
        wanted[g][t] = sched[(g, t)]["seat"]

    evs = {name: ValueEvaluator(path) for name, path in CRITICS.items()}
    vals: dict[str, dict] = {name: {} for name in evs}
    stats = Counter()
    for store in args.stores:
        ts = TrajectoryStore(Path(store))
        for traj in ts.games(skip_undecodable=True):
            g = traj.header["g"]
            if g not in wanted:
                continue
            for i, dec in enumerate(traj.decisions):
                t = dec.get("t", 0)
                seat = wanted[g].get(t)
                if seat is None or dec.get("m") != "chooseSpellAbilityToPlay":
                    continue
                if dec.get("p") != seat:
                    continue
                obs = dec.get("obs")
                if not obs or obs.get("glob", {}).get("ph") != "MAIN1" \
                        or obs.get("glob", {}).get("ap") != seat:
                    continue
                key = (g, t)
                if key in vals["era_i019"]:
                    continue  # emis rule: FIRST matching dec only
                for name, ev in evs.items():
                    ex = ev.example(dec, traj.header, seat,
                                    traj.decisions[:i])
                    vals[name][key] = float(ev.win_probs([ex])[0])
                stats["windows"] += 1

    per_turn = []
    for key, rec in sorted(stage1.items()):
        if key not in vals["era_i019"]:
            stats["missing_window"] += 1
            continue
        per_turn.append({
            "g": key[0], "t": key[1],
            "certified": bool(rec["certified"]),
            "score_mean": rec["score_mean"],
            "dwr": stage2.get(key, {}).get("dwr"),
            **{"v_" + name: round(vals[name][key], 4) for name in evs},
        })

    def bin_read(name: str) -> dict:
        vs = sorted(r["v_" + name] for r in per_turn)
        edges = [vs[int(len(vs) * q / 5)] for q in range(1, 5)]
        bins: list[dict] = [{"read": 0, "cert": 0, "dwrs": []}
                            for _ in range(5)]
        for r in per_turn:
            b = sum(r["v_" + name] >= e for e in edges)
            bins[b]["read"] += 1
            bins[b]["cert"] += r["certified"]
            if r["dwr"] is not None:
                bins[b]["dwrs"].append(r["dwr"])
        return {
            "quintile_edges": [round(e, 4) for e in edges],
            "bins": [{
                "read": b["read"], "certified": b["cert"],
                "cert_rate": round(b["cert"] / b["read"], 3)
                if b["read"] else None,
                "n_pos": len(b["dwrs"]),
                "mean_dwr": round(statistics.mean(b["dwrs"]), 4)
                if b["dwrs"] else None,
            } for b in bins],
        }

    out = {"stats": dict(stats),
           "critics": {n: CRITICS[n] for n in evs},
           **{name: bin_read(name) for name in evs}}
    json.dump(out, open(plan / "binned-read.json", "w"), indent=2)
    with open(plan / "binned-perturn.jsonl", "w") as f:
        for r in per_turn:
            f.write(json.dumps(r) + "\n")
    print(json.dumps(out, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    mp = sub.add_parser("marginal")
    mp.add_argument("--plan", default="data/runs/sched-sweep-m10")
    mp.set_defaults(fn=marginal)
    bp = sub.add_parser("binned")
    bp.add_argument("--plan", default="data/runs/sched-sweep-m10")
    bp.add_argument("--stores", nargs="+", required=True)
    bp.set_defaults(fn=binned)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
