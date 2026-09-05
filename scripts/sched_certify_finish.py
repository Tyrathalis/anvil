#!/usr/bin/env python3
"""M10 reset Fork 3 — inline certification, the FINISH step: a generation
run's per-worker labels.jsonl (the `sched` completion rows written by the
-certify rollouts + one `sched_arms` row per certified point) and the run's
INGESTED store -> full-support schedule labels in the seed-label format the
distiller (`sched_distill.py build --certified`) and the learner
(`rl.py --seed-labels`) already consume.

Adjudication = the pinned stage-1 rule verbatim (schedule_read.certify_turn:
SELECT_ROLLS pick the best arm by composite vs the natural line, SCORE_ROLLS
price it — θ, sign consistency; sched_pins). Label rule (draft §D.3): a
window gets a label ONLY if it was rolled out, and the label is the search-
adjudicated best of {the natural line (arm 0), the arms}:
  - certified arm  -> src="certified", arm=id, seq = the arm's labels mapped
                      to the emission window's (entity, sa[:60]) pairs;
  - natural wins   -> src="natural", arm=-1, seq = the seat's realized casts
                      from the emission window on (the mint_full_support
                      rule; "natural_hold" when it cast nothing).
Every rolled-out point also writes its ARM SPREAD (per-arm select/score
means vs natural) to <out>.spread.jsonl — the pivotal-moment head's data,
recorded from the first inline certification (draft §D.3 named extension).

No replay, no parity witness: the labels are adjudicated from the live
game's own forks and rejoin the live game's own store row (`s` = the
emission dec id) — the ADR-0089 defect class has nothing to reproduce.

Usage:
  uv run python scripts/sched_certify_finish.py \
      --run data/runs/<run dir> --store data/trajectories/<store> \
      --out data/trajectories/<store>/sched-labels.jsonl \
      --cert-ckpt <serve ckpt> --era <era tag>
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sched_pins as pins  # noqa: E402
from schedule_read import arm_scores, certify_turn, load_rows  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def load_arms(patterns: list[str]) -> dict:
    """sched_arms rows -> {(g, t): {"seat", "horizon", "arms": {armId: ("joint", labels)}}}
    (the read_sched shape, built from the rows the worker wrote at the window)."""
    out: dict = {}
    for pat in patterns:
        for path in sorted(glob.glob(pat)):
            for line in open(path):
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("ev") != "sched_arms":
                    continue
                key = (r["i"], r["t"])
                ent = out.setdefault(key, {"seat": r["seat"], "horizon": r.get("horizon"), "arms": {}})
                for i, labels in enumerate(r["arms"]):
                    ent["arms"][i + 1] = ("joint", list(labels))
    return out


def spread(entry: dict, seat: int) -> list[dict]:
    """Per-arm select/score means vs natural (the arm spread)."""
    rows = []
    for arm_id, arows in sorted(entry["arms"].items()):
        sel = arm_scores(arows, entry["nat"], seat, pins.SELECT_ROLLS)
        sco = arm_scores(arows, entry["nat"], seat, pins.SCORE_ROLLS)
        rows.append({"arm": arm_id, "n_sel": len(sel), "n_sco": len(sco),
                     "select_mean": round(sum(sel) / len(sel), 3) if sel else None,
                     "score_mean": round(sum(sco) / len(sco), 3) if sco else None})
    return rows


def _emission_window(decs: list[dict], seat: int, turn: int) -> "tuple[int, dict] | None":
    for i, d in enumerate(decs):
        if (d.get("m") == "chooseSpellAbilityToPlay" and d.get("p") == seat and d.get("t") == turn
                and d.get("obs") and d["obs"].get("glob", {}).get("ph") == "MAIN1"
                and d["obs"].get("glob", {}).get("ap") == seat):
            return i, d
    return None


def _chosen(dec: dict) -> "tuple | None":
    """(e, sa60) the seat chose at a priority window; None = pass / unmappable."""
    opts = dec.get("opts") or []
    oi = dec.get("oi")
    if oi is not None and 0 <= oi < len(opts):
        o = opts[oi]
        return o.get("e"), str(o.get("sa") or "")[:60]
    ret = dec.get("ret")
    plan = ret[0] if isinstance(ret, list) and ret else None
    if not plan or plan.get("e") is None:
        return None
    hits = [o for o in opts if o.get("e") == plan.get("e")]
    if len(hits) != 1:
        return None
    return hits[0].get("e"), str(hits[0].get("sa") or "")[:60]


def finish(args) -> dict:
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import SCHED_CAP

    run = Path(args.run)
    pats = [str(run / "workers" / "inv-*" / "labels.jsonl")]
    turns = load_rows(pats)
    arms = load_arms(pats)
    st = TrajectoryStore(Path(args.store))
    stats: Counter = Counter()
    per_turn = []
    labels_out = []
    spread_out = []
    by_game: dict[int, list] = defaultdict(list)
    for key, plan in sorted(arms.items()):
        entry = turns.get(key)
        if entry is None or (not entry["nat"] and not entry["arms"]):
            stats["missing_rows"] += 1
            continue
        if entry["skips"]:
            stats["skip_" + entry["skips"][0]] += 1
            continue
        rec = certify_turn(entry, plan["seat"])
        rec.update({"g": key[0], "t": key[1], "seat": plan["seat"]})
        per_turn.append(rec)
        spread_out.append({"g": key[0], "t": key[1], "seat": plan["seat"],
                           "arms": spread(entry, plan["seat"]),
                           "certified": bool(rec.get("read") and rec.get("certified")),
                           "selected": rec.get("arm")})
        if not rec["read"]:
            stats[rec["why"]] += 1
            continue
        stats["read"] += 1
        by_game[key[0]].append((key[1], plan, rec))
    # rejoin each read turn to its emission window in the store
    for g, items in by_game.items():
        try:
            traj = st.game(g)
        except Exception:  # noqa: BLE001
            stats["undecodable"] += len(items)
            continue
        decs = traj.decisions
        for t, plan, rec in items:
            seat = plan["seat"]
            win = _emission_window(decs, seat, t)
            if win is None:
                stats["no_window"] += 1
                continue
            emis_i, emis = win
            opts = emis.get("opts") or []
            row = {"store": Path(args.store).name, "g": g, "t": t, "seat": seat,
                   "s": emis.get("s"), "score_mean": rec.get("score_mean"),
                   "select_mean": rec.get("select_mean")}
            if rec["certified"]:
                _, labels = plan["arms"][rec["arm"]]
                seq = []
                ok = True
                for lab in labels:
                    hit = next((o for o in opts if str(o.get("sa") or "")[:60] == lab[:60]), None)
                    if hit is None:
                        stats["label_unmatched"] += 1
                        ok = False
                        break
                    seq.append([hit.get("e"), str(hit.get("sa") or "")[:60]])
                if not ok:
                    stats["certified_dropped"] += 1
                    continue
                row.update({"arm": rec["arm"], "seq": seq[:SCHED_CAP], "src": "certified"})
                stats["certified"] += 1
            else:
                # natural wins: the seat's realized casts from the emission window on
                seq = []
                for d in decs[emis_i:]:
                    if d.get("m") != "chooseSpellAbilityToPlay" or d.get("p") != seat or d.get("t") != t:
                        continue
                    ch = _chosen(d)
                    if ch is not None:
                        seq.append([ch[0], ch[1]])
                row.update({"arm": -1, "seq": seq[:SCHED_CAP],
                            "src": "natural" if seq else "natural_hold"})
                stats["natural"] += 1
                stats["natural_hold"] += int(not seq)
            labels_out.append(row)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"k": "meta", "run": str(run), "store": str(args.store), "cert_ckpt": args.cert_ckpt,
            "era": args.era, "mode": "inline", "theta": pins.THETA, "consistent": pins.CONSISTENT,
            "k_rolls": pins.K_ROLLS, "frame": dict(stats), "points": len(arms),
            "labels": len(labels_out)}
    with open(out, "w") as f:
        f.write(json.dumps(meta) + "\n")
        for r in labels_out:
            f.write(json.dumps(r) + "\n")
    with open(out.with_suffix(".spread.jsonl"), "w") as f:
        for r in spread_out:
            f.write(json.dumps(r) + "\n")
    with open(out.with_suffix(".perturn.jsonl"), "w") as f:
        for r in per_turn:
            f.write(json.dumps(r) + "\n")
    print(f"[certify-finish] {len(arms)} certified points -> read {stats['read']}, "
          f"certified {stats['certified']}, natural {stats['natural']} "
          f"(holds {stats['natural_hold']}); frame {dict(stats)} -> {out}")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="the generation run dir (workers/inv-*/labels.jsonl)")
    ap.add_argument("--store", required=True, help="the run's ingested trajectory store")
    ap.add_argument("--out", default=None, help="labels.jsonl (default <store>/sched-labels.jsonl)")
    ap.add_argument("--cert-ckpt", default="UNKNOWN")
    ap.add_argument("--era", default="inline")
    args = ap.parse_args()
    if args.out is None:
        args.out = str(Path(args.store) / "sched-labels.jsonl")
    finish(args)


if __name__ == "__main__":
    main()
