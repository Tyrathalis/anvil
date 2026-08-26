#!/usr/bin/env python3
"""M10 planning-ceiling stage-1 read (m10-ceiling-spec; every threshold and
rule imported from scripts/sched_pins.py — PRE-REGISTERED: this script is
written before any sweep data exists, the launch-commit discipline).

  stage1  lane out.jsonl rows -> per-turn certification:
          - pair (arm row, natural row) by (g, t, roll); validity = both
            non-crash; arm candidacy = non-void, >= MIN_VALID_ROLLS valid
            pairs in EACH half (select/score).
          - selection: argmax over candidate arms of mean composite on
            SELECT_ROLLS (ties -> lower armId).
          - positivity: the SELECTED arm's SCORE_ROLLS mean >= THETA and
            sign-consistency >= CONSISTENT.
          - rate: certified / read turns, Wilson 95% CI.
          - divergence/void/skip accounting (first-class, fork 5).
          Emits positives.jsonl (the stage-2 job input: g, t, seat,
          selected armId + its schedule row echo) + stage1-read.json.
  h4flag  the 1b evaluation on the shared side-sample turns: h2 vs h4
          certification counts, the pinned H4_RATIO/H4_MIN_NET flag,
          split by arm shape (hold-bearing = selected arm shorter than
          the affordable set, incl. hold-all).
  stage2plan  positives.jsonl -> sched-end.tsv (horizon 0 = natural end,
          selected arm ONLY + natural, same seeds by construction — the
          rollSeed identity is in-jar, keyed on target turn).

Usage:
  uv run python scripts/schedule_read.py stage1 \
      --labels data/runs/sched-sweep-m10/lanes-h2/lane-*.out.jsonl \
      --sched data/runs/sched-sweep-m10/sched-h2.tsv \
      --out data/runs/sched-sweep-m10
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sched_pins as pins  # noqa: E402


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def load_rows(patterns: list[str]) -> dict:
    """-> {(g, t): {"nat": {roll: row}, "arms": {armId: {roll: row}},
    "skips": [reason]}}"""
    turns: dict = defaultdict(lambda: {"nat": {}, "arms": defaultdict(dict),
                                       "skips": []})
    for pat in patterns:
        for path in sorted(glob.glob(pat)):
            for line in open(path):
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("ev") != "sched":
                    continue
                if "skip" in r:
                    turns[(r["i"], r["tt"])]["skips"].append(r["skip"])
                    continue
                key = (r["i"], r["t"])
                if r["arm"] == 0:
                    turns[key]["nat"][r["roll"]] = r
                else:
                    turns[key]["arms"][r["arm"]][r["roll"]] = r
    return turns


def read_sched(path: str) -> dict:
    """schedfile -> {(g, t): {"seat": s, "arms": {armId: (paymode, labels)}}}"""
    out: dict = defaultdict(lambda: {"arms": {}})
    for ln in Path(path).read_text().splitlines():
        if not ln or ln.startswith("#"):
            continue
        f = ln.split("\t")
        g, t, _h, seat, arm, mode = (int(f[0]), int(f[1]), int(f[2]),
                                     int(f[3]), int(f[4]), f[5])
        out[(g, t)]["seat"] = seat
        out[(g, t)]["arms"][arm] = (mode, f[6:])
    return out


def arm_scores(arm_rows: dict, nat_rows: dict, seat: int,
               rolls: tuple) -> list[float]:
    """Paired composites over the given roll half; only pairs with both
    rows present and non-crash count (pins validity)."""
    out = []
    for roll in rolls:
        a, b = arm_rows.get(roll), nat_rows.get(roll)
        if a is None or b is None or a.get("crash") or b.get("crash"):
            continue
        if "snap" not in a or "snap" not in b:
            continue
        out.append(pins.composite(pins.axes(a, seat), pins.axes(b, seat)))
    return out


def certify_turn(entry: dict, seat: int, joint_only: bool = True) -> dict:
    """One turn's selection + positivity per the pinned rules. Returns the
    per-turn record (certified flag, selected arm, margins, accounting)."""
    nat = entry["nat"]
    cands = []
    for arm_id, rows in sorted(entry["arms"].items()):
        if joint_only and arm_id > 100:
            continue  # auto-stratum arms never certify (marginal read only)
        any_row = next(iter(rows.values()), None)
        if any_row is None:
            continue
        if any_row.get("void") or any(r.get("void") for r in rows.values()):
            continue
        sel = arm_scores(rows, nat, seat, pins.SELECT_ROLLS)
        sco = arm_scores(rows, nat, seat, pins.SCORE_ROLLS)
        if len(sel) < pins.MIN_VALID_ROLLS or len(sco) < pins.MIN_VALID_ROLLS:
            continue
        cands.append((sum(sel) / len(sel), -arm_id, arm_id, sco))
    if not cands:
        return {"read": False, "why": "no_candidate_arm"}
    cands.sort(reverse=True)  # max select-mean; tie -> LOWER armId wins
    sel_mean, _, arm_id, sco = cands[0]
    mean = sum(sco) / len(sco)
    agree = sum(1 for s in sco if (s > 0) == (mean > 0)) / len(sco)
    certified = mean >= pins.THETA and agree >= pins.CONSISTENT
    return {"read": True, "arm": arm_id, "select_mean": round(sel_mean, 3),
            "score_mean": round(mean, 3), "agree": round(agree, 3),
            "score_n": len(sco), "certified": certified}


def stage1(args) -> None:
    turns = load_rows(args.labels)
    sched = read_sched(args.sched)
    out = Path(args.out)
    stats = Counter()
    positives = []
    per_turn = []
    for key, plan in sorted(sched.items()):
        entry = turns.get(key)
        if entry is None or (not entry["nat"] and not entry["arms"]):
            stats["missing"] += 1
            continue
        if entry["skips"]:
            stats["skip_" + entry["skips"][0]] += 1
            continue
        rec = certify_turn(entry, plan["seat"])
        rec.update({"g": key[0], "t": key[1]})
        per_turn.append(rec)
        if not rec["read"]:
            stats[rec["why"]] += 1
            continue
        stats["read"] += 1
        # divergence accounting on the selected arm (fork 5, first-class)
        sel_rows = entry["arms"][rec["arm"]]
        stats["sel_degraded_rolls"] += sum(
            1 for r in sel_rows.values() if r.get("degraded_at", -1) >= 0)
        stats["sel_rolls"] += len(sel_rows)
        if rec["certified"]:
            stats["certified"] += 1
            mode, labels = plan["arms"][rec["arm"]]
            positives.append({"g": key[0], "t": key[1], "seat": plan["seat"],
                              "arm": rec["arm"], "paymode": mode,
                              "labels": labels,
                              "score_mean": rec["score_mean"]})
    n, k = stats["read"], stats["certified"]
    p, lo, hi = wilson(k, n)
    report = {
        "turns_planned": len(sched), "read": n, "certified": k,
        "rate": round(p, 4), "rate_ci": [round(lo, 4), round(hi, 4)],
        "theta": pins.THETA, "consistent": pins.CONSISTENT,
        "stats": dict(stats),
    }
    with open(out / "positives.jsonl", "w") as f:
        for r in positives:
            f.write(json.dumps(r) + "\n")
    with open(out / "stage1-perturn.jsonl", "w") as f:
        for r in per_turn:
            f.write(json.dumps(r) + "\n")
    json.dump(report, open(out / "stage1-read.json", "w"), indent=2)
    print(json.dumps(report, indent=2))


def h4flag(args) -> None:
    """1b: compare certification on the shared side-sample turns."""
    h2 = {(r["g"], r["t"]): r for r in map(
        json.loads, open(Path(args.out) / "stage1-perturn.jsonl"))}
    turns4 = load_rows(args.labels_h4)
    sched4 = read_sched(args.sched_h4)
    c2 = c4 = n = 0
    hold_c2 = hold_c4 = 0
    for key, plan in sorted(sched4.items()):
        r2 = h2.get(key)
        e4 = turns4.get(key)
        if r2 is None or not r2.get("read") or e4 is None or e4["skips"]:
            continue
        r4 = certify_turn(e4, plan["seat"])
        if not r4["read"]:
            continue
        n += 1
        hold2 = r2.get("certified") and len(
            plan["arms"].get(r2.get("arm"), ("", []))[1]) == 0
        hold4 = r4["certified"] and len(
            plan["arms"].get(r4.get("arm"), ("", []))[1]) == 0
        c2 += bool(r2.get("certified"))
        c4 += bool(r4["certified"])
        hold_c2 += bool(hold2)
        hold_c4 += bool(hold4)
    fires = c2 > 0 and c4 >= pins.H4_RATIO * c2 and (c4 - c2) >= pins.H4_MIN_NET
    report = {"shared_read": n, "h2_certified": c2, "h4_certified": c4,
              "hold_shaped_h2": hold_c2, "hold_shaped_h4": hold_c4,
              "ratio": round(c4 / c2, 3) if c2 else None,
              "flag_fires": bool(fires),
              "pins": {"ratio": pins.H4_RATIO, "min_net": pins.H4_MIN_NET}}
    json.dump(report, open(Path(args.out) / "h4flag.json", "w"), indent=2)
    print(json.dumps(report, indent=2))


def stage2plan(args) -> None:
    """positives -> sched-end.tsv: horizon 0, selected arm only (the
    natural arm always runs implicitly). rollSeed identity is in-jar."""
    out = Path(args.out)
    lines = 0
    with open(out / "sched-end.tsv", "w") as f:
        f.write("# M10 ceiling stage 2 (game-end conversion on stage-1 "
                "positives; schedule_read.py stage2plan)\n")
        for r in map(json.loads, open(out / "positives.jsonl")):
            tail = ("\t" + "\t".join(r["labels"])) if r["labels"] else ""
            f.write(f"{r['g']}\t{r['t']}\t0\t{r['seat']}\t{r['arm']}"
                    f"\t{r['paymode']}{tail}\n")
            lines += 1
    print(f"{lines} stage-2 points -> {out / 'sched-end.tsv'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    s1 = sub.add_parser("stage1")
    s1.add_argument("--labels", nargs="+", required=True)
    s1.add_argument("--sched", required=True)
    s1.add_argument("--out", required=True)
    s1.set_defaults(fn=stage1)
    hf = sub.add_parser("h4flag")
    hf.add_argument("--labels-h4", nargs="+", required=True)
    hf.add_argument("--sched-h4", required=True)
    hf.add_argument("--out", required=True)
    hf.set_defaults(fn=h4flag)
    s2 = sub.add_parser("stage2plan")
    s2.add_argument("--out", required=True)
    s2.set_defaults(fn=stage2plan)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
