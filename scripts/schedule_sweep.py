#!/usr/bin/env python3
"""M10 planning-ceiling sweep planner (m10-ceiling-spec.md, launch pins in
scripts/sched_pins.py — imported, never redefined).

  sample  ingested census store(s) -> the pinned uniform sample (600
          eligible turn-groups + 200 marginal subset + 100 h4 side-sample,
          rng + draw order per sched_pins), per-turn arm construction
          (n<=3 full ordered-subset enumeration incl. hold-all; n>=4 the
          six canonical arms + seeded-random fill to the cap), schedfile
          TSV emission (sched-h2.tsv / sched-h4.tsv) + frame.json.
  lanes   split a schedfile across N lane TSVs (round-robin by game) and
          emit lane shell scripts that replay the census configuration
          (same jar flags — obs/census/paytelemetry parity) with
          -forceschedule.

Conventions shared with schedule_census.py / veto_knowability (recorded):
mana-ability options excluded; costs by the classify_window convention
(uncertain counted, never guessed); affordability under the `now` source
view; commander tax optimistic; X=0/phyrexian-free optimism throughout.

Candidate labels are taken from the FORK-CONSISTENT window: the first
MAIN1 own-turn dec with an obs in the turn-group (the RolloutMonitor
forks at the first quiescent MAIN1 own-priority event — the same window
that produces that dec, so its opts are the fork window's options; the
mechanical smoke's degrade:absent lesson). Turn-groups with no MAIN1 dec
are ineligible (rare; counted in the frame).

Arm shapes (spec knob b), n>=4 canonical:
  greedy-max-spend  largest total optimistic cmc, cost-descending order
  ramp-first        mana-producing permanents first (CardInfo.prod
                    non-empty — rocks; ramp sorceries approximate out,
                    recorded), then greedy over the rest
  curve-ascending   cost-ascending
  curve-descending  cost-descending (= greedy-max-spend when all fit;
                    kept distinct because greedy-max-spend SELECTS a
                    max-cmc subset when not all candidates fit a plan
                    cap of 3, while curve-desc takes all in desc order)
  hold-interaction  exclude instant-speed candidates (Instant type or
                    Flash keyword), greedy over the rest
  hold-all          the empty schedule
Dedup by label sequence; seeded-random ordered subsets fill to ARM_CAP.

Usage:
  uv run python scripts/schedule_sweep.py sample \
      --stores data/trajectories/m10-ceiling-census-... --out data/runs/sched-sweep-m10
  uv run python scripts/schedule_sweep.py lanes \
      --plan data/runs/sched-sweep-m10 --which h2 --lanes 8 \
      --jar <instrumented jar> --pairs data/runs/m10-ceiling-census-pairs.tsv
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sched_pins as pins  # noqa: E402
from schedule_census import MANA_ABILITY_SA, cmc, resolve_cost  # noqa: E402
from veto_knowability import build_card_table, can_pay, source_views  # noqa: E402


# ------------------------------------------------------------------ sample

def eligible_turns(stores: list[str], table) -> tuple[list[dict], dict]:
    """Walk the census stores; -> (eligible turn rows sorted (store, g, t),
    frame counters). Each row carries the fork-window candidate list with
    per-candidate (label, cost bucket, optimistic cmc, affordable-now,
    mana_producer, instant_speed)."""
    from anvil.store.trajectories import TrajectoryStore

    rows: list[dict] = []
    frame = Counter()
    for store in stores:
        ts = TrajectoryStore(Path(store))
        sname = Path(store).name
        for traj in ts.games(skip_undecodable=True):
            g = traj.header["g"]
            players = traj.header.get("players") or []
            seat = next((i for i, p in enumerate(players)
                         if str(p.get("name", "")).startswith("Anvil")), 0)
            groups: dict[int, list] = {}
            for dec in traj.decisions:
                if dec.get("m") != "chooseSpellAbilityToPlay":
                    continue
                if dec.get("p") != seat or dec.get("t", 0) < 1:
                    continue
                groups.setdefault(dec["t"], []).append(dec)
            for t, decs in sorted(groups.items()):
                frame["turn_groups"] += 1
                # fork-consistent window: first MAIN1 own-turn dec with obs
                emis = next((d for d in decs if d.get("obs")
                             and d["obs"].get("glob", {}).get("ph") == "MAIN1"
                             and d["obs"].get("glob", {}).get("ap") == seat), None)
                if emis is None:
                    frame["no_main1_window"] += 1
                    continue
                frame["own_turn_groups"] += 1
                obs = emis["obs"]
                ents = {e["e"]: e for e in obs.get("ents", [])}
                try:
                    cmd_extra = 2 * min(obs["players"][seat]["cmdcast"])
                except (KeyError, IndexError, TypeError, ValueError):
                    cmd_extra = 0
                views = source_views(obs, seat, table)
                seen: set[tuple] = set()
                cands = []
                afford_now = 0
                for opt in emis.get("opts", []):
                    key = (opt.get("e"), str(opt.get("sa") or "")[:60])
                    if key in seen:
                        continue
                    seen.add(key)
                    bucket, cost, extra, name = resolve_cost(opt, ents, table)
                    if bucket == "spell" and ents.get(opt.get("e"), {}).get("z") == "command":
                        extra = cmd_extra
                    if bucket not in ("spell", "ability") or cost is None:
                        continue
                    label = str(opt.get("sa") or "")[:60]
                    if "\t" in label or "\n" in label:
                        frame["label_tab_dropped"] += 1
                        continue
                    ok = can_pay(cost, views.now, extra)
                    afford_now += int(ok)
                    card = table.get(name)
                    cands.append({
                        "label": label,
                        "cmc": cmc(cost, extra),
                        "afford": ok,
                        "mana_producer": bool(card and card.prod),
                        "instant_speed": bool(card and (
                            "Instant" in (card.types or "")
                            or "Flash" in (card.keywords or ""))),
                    })
                if afford_now < 2:
                    continue
                rows.append({
                    "store": sname, "g": g, "t": t, "seat": seat,
                    "cands": [c for c in cands if c["afford"]],
                })
    rows.sort(key=lambda r: (r["store"], r["g"], r["t"]))
    return rows, dict(frame)


def _dedup_append(arms: list[tuple[str, ...]], seq: tuple[str, ...]) -> None:
    if seq not in arms:
        arms.append(seq)


def build_arms(row: dict) -> list[tuple[str, ...]]:
    """Ordered label sequences for one turn, per spec knob b. Index in the
    returned list + 1 = armId (stable given the row + pins)."""
    cands = row["cands"]
    n = len(cands)
    if n <= 3:
        arms: list[tuple[str, ...]] = []
        labels = [c["label"] for c in cands]
        for k in range(0, n + 1):
            for sub in itertools.permutations(labels, k):
                _dedup_append(arms, sub)
        return arms[: pins.ARM_CAP]

    by_cost_desc = sorted(cands, key=lambda c: (-c["cmc"], c["label"]))
    by_cost_asc = sorted(cands, key=lambda c: (c["cmc"], c["label"]))
    lab = lambda cs: tuple(c["label"] for c in cs)  # noqa: E731

    arms = []
    _dedup_append(arms, ())                          # hold-all
    _dedup_append(arms, lab(by_cost_desc[:3]))       # greedy-max-spend
    ramp = [c for c in cands if c["mana_producer"]]
    rest = [c for c in by_cost_desc if not c["mana_producer"]]
    _dedup_append(arms, lab((sorted(ramp, key=lambda c: (c["cmc"], c["label"]))
                             + rest)[:3]))           # ramp-first
    _dedup_append(arms, lab(by_cost_asc[:3]))        # curve-ascending
    _dedup_append(arms, lab(by_cost_desc))           # curve-descending (all)
    noint = [c for c in by_cost_desc if not c["instant_speed"]]
    _dedup_append(arms, lab(noint[:3]))              # hold-interaction

    rng = random.Random(pins.arm_fill_seed(row["g"], row["t"]))
    labels = [c["label"] for c in cands]
    tries = 0
    while len(arms) < pins.ARM_CAP and tries < 500:
        tries += 1
        k = rng.randint(1, min(n, 4))
        seq = tuple(rng.sample(labels, k))
        _dedup_append(arms, seq)
    return arms[: pins.ARM_CAP]


def sample(args) -> None:
    table = build_card_table()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, frame = eligible_turns(args.stores, table)
    print(f"eligible universe: {len(rows)} turn-groups "
          f"(of {frame.get('own_turn_groups', 0)} own-turn)")
    if len(rows) < pins.SAMPLE_N:
        sys.exit(f"FATAL: eligible universe {len(rows)} < SAMPLE_N {pins.SAMPLE_N}")

    # the pinned rng + DOCUMENTED DRAW ORDER (sched_pins)
    rng = random.Random(pins.SAMPLE_RNG_SEED)
    sample600 = rng.sample(rows, pins.SAMPLE_N)                # draw 1
    marginal = rng.sample(sample600, pins.MARGINAL_N)          # draw 2
    h4 = rng.sample(sample600, pins.H4_N)                      # draw 3
    marginal_keys = {(r["g"], r["t"]) for r in marginal}
    h4_keys = {(r["g"], r["t"]) for r in h4}

    def write_sched(path: Path, turns: list[dict], horizon: int,
                    with_auto: bool) -> Counter:
        c = Counter()
        with open(path, "w") as f:
            f.write(f"# M10 ceiling sweep schedfile (schedule_sweep.py sample; "
                    f"rng {pins.SAMPLE_RNG_SEED}; horizon {horizon})\n")
            for r in turns:
                arms = build_arms(r)
                base = f"{r['g']}\t{r['t']}\t{horizon}\t{r['seat']}"
                for i, seq in enumerate(arms):
                    tail = ("\t" + "\t".join(seq)) if seq else ""
                    f.write(f"{base}\t{i + 1}\tjoint{tail}\n")
                    c["joint_arms"] += 1
                if with_auto and (r["g"], r["t"]) in marginal_keys:
                    for i, seq in enumerate(arms):
                        tail = ("\t" + "\t".join(seq)) if seq else ""
                        f.write(f"{base}\t{i + 101}\tauto{tail}\n")
                        c["auto_arms"] += 1
                c["turns"] += 1
        return c

    c2 = write_sched(out / "sched-h2.tsv", sample600, pins.HORIZON_H2, True)
    c4 = write_sched(out / "sched-h4.tsv",
                     [r for r in sample600 if (r["g"], r["t"]) in h4_keys],
                     pins.HORIZON_H4, False)
    frame.update({
        "eligible": len(rows),
        "sampled": pins.SAMPLE_N,
        "marginal": pins.MARGINAL_N,
        "h4": pins.H4_N,
        "h2_file": dict(c2), "h4_file": dict(c4),
        "rng_seed": pins.SAMPLE_RNG_SEED,
        "stores": {s: hashlib.sha256(
            (Path(s) / "manifest.json").read_bytes()).hexdigest()[:16]
            for s in args.stores},
        "sample_keys": sorted([r["g"], r["t"]] for r in sample600),
        "marginal_keys": sorted(map(list, marginal_keys)),
        "h4_keys": sorted(map(list, h4_keys)),
    })
    json.dump(frame, open(out / "frame.json", "w"), indent=2)
    print(f"h2: {c2['turns']} turns, {c2['joint_arms']} joint + "
          f"{c2['auto_arms']} auto arms; h4: {c4['turns']} turns, "
          f"{c4['joint_arms']} arms -> {out}")


# ------------------------------------------------------------------- lanes

def lanes(args) -> None:
    plan = Path(args.plan)
    sched = plan / f"sched-{args.which}.tsv"
    lines = [ln for ln in sched.read_text().splitlines()
             if ln and not ln.startswith("#")]
    games = sorted({int(ln.split("\t", 1)[0]) for ln in lines})
    lane_games = {g: i % args.lanes for i, g in enumerate(games)}
    gui = Path(args.jar).resolve().parent.parent.parent / "forge-gui"
    outdir = plan / f"lanes-{args.which}"
    outdir.mkdir(exist_ok=True)
    for i in range(args.lanes):
        tsv = outdir / f"lane-{i}.tsv"
        with open(tsv, "w") as f:
            for ln in lines:
                if lane_games[int(ln.split("\t", 1)[0])] == i:
                    f.write(ln + "\n")
        scratch = outdir / f"lane-{i}.scratch"
        sh = outdir / f"lane-{i}.sh"
        # replay parity: the census configuration's trajectory-perturbing
        # flags (-obs/-census/-paytelemetry) all on, scratch outputs
        sh.write_text(
            "#!/bin/sh\nset -e\n"
            f"cd '{gui}'\n"
            f"nice -n 19 java -Xms2g -Xmx2g -XX:ActiveProcessorCount=2 "
            f"-XX:+ExitOnOutOfMemoryError "
            f"-jar '{Path(args.jar).resolve()}' anvil "
            f"-pairs '{Path(args.pairs).resolve()}' -gpp 5 -f Commander "
            f"-range 0 {pins.CENSUS_GAMES} -seedbase {pins.CENSUS_SEED_BASE} "
            f"-b {args.bridge} "
            f"-obs '{scratch}.obs.zst' -census '{scratch}.census.jsonl' "
            f"-paytelemetry "
            f"-rollout {pins.K_ROLLS} -labels '{outdir}/lane-{i}.out.jsonl' "
            f"-forceschedule '{tsv}'\n")
        sh.chmod(0o755)
    print(f"{args.lanes} lanes -> {outdir} (games {len(games)}, "
          f"rows {len(lines)})")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    sp = sub.add_parser("sample")
    sp.add_argument("--stores", nargs="+", required=True)
    sp.add_argument("--out", required=True)
    sp.set_defaults(fn=sample)
    lp = sub.add_parser("lanes")
    lp.add_argument("--plan", required=True)
    lp.add_argument("--which", choices=["h2", "h4"], required=True)
    lp.add_argument("--lanes", type=int, default=8)
    lp.add_argument("--jar", required=True)
    lp.add_argument("--pairs", required=True)
    lp.add_argument("--bridge", default="grpc:localhost:50065")
    lp.set_defaults(fn=lanes)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
