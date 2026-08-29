#!/usr/bin/env python3
"""M10 probe pre-flight: derive the invalid-schedule penalty magnitude
(m10-plan "Build-era operational pins": ADR-0053-calibrated — the penalty
must never exceed the measured cost of the deterred behavior; the banked
sweep degraded-arm composite deltas are the pinned measurement source).

Read logic written before any output is looked at (house discipline).

Population: the h2 sweep lanes (lanes-h2/lane-*.out.jsonl), joint arms
(1..100) paired to the natural arm-0 roll by roll index (paired
rollSeeds). Composite = sched_pins.composite (the standing certify
blend), payer perspective from the schedfile seat.

Contrasts (all reported, none blended):
  within-arm   arms carrying BOTH >=1 degraded and >=1 clean roll:
               mean(clean composite) - mean(degraded composite) per arm,
               aggregated. Same emitted schedule on both sides — the
               cleanest "cost of the slot failing" number.
  pooled       all degraded rolls vs all clean rolls across arms
               (selection-confounded: ambitious schedules degrade more;
               context only).
  void         void rolls vs clean rolls (the arm never executed — the
               fully-invalid class), same two cuts.

The derived bound: the ADR-0053 rule caps the penalty at the measured
composite cost |within-arm delta|; the loss-scale mapping is proposed at
the numerics session, this script's job is the composite-scale number.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sched_pins as pins  # noqa: E402
from schedule_read import load_rows, read_sched  # noqa: E402


def paired_composite(row: dict, nat_rows: dict, seat: int) -> float | None:
    nat = nat_rows.get(row["roll"])
    if nat is None or nat.get("crash") or row.get("crash"):
        return None
    return pins.composite(pins.axes(row, seat), pins.axes(nat, seat))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="data/runs/sched-sweep-m10")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    plan = Path(args.plan)

    turns = load_rows([str(plan / "lanes-h2/lane-*.out.jsonl")])
    sched = read_sched(str(plan / "sched-h2.tsv"))

    clean_all, degr_all, void_all = [], [], []
    within_arm = []          # per-arm mean(clean) - mean(degraded)
    n_arms = n_mixed = 0
    for key, plandef in sorted(sched.items()):
        entry = turns.get(key)
        if entry is None:
            continue
        seat = plandef["seat"]
        for arm_id, rows in entry["arms"].items():
            if arm_id > 100:
                continue  # auto twins: separate stratum, not this read
            n_arms += 1
            cs, ds, vs = [], [], []
            for r in rows.values():
                comp = paired_composite(r, entry["nat"], seat)
                if comp is None:
                    continue
                if r.get("void"):
                    vs.append(comp)
                elif r.get("degraded_at", -1) >= 0:
                    ds.append(comp)
                else:
                    cs.append(comp)
            clean_all += cs
            degr_all += ds
            void_all += vs
            if cs and ds:
                n_mixed += 1
                within_arm.append(statistics.mean(cs) - statistics.mean(ds))

    def summ(xs: list[float]) -> dict:
        if not xs:
            return {"n": 0}
        return {"n": len(xs), "mean": round(statistics.mean(xs), 3),
                "median": round(statistics.median(xs), 3),
                "stdev": round(statistics.stdev(xs), 3) if len(xs) > 1 else None}

    out = {
        "plan": str(plan),
        "arms_read": n_arms,
        "arms_mixed_clean_and_degraded": n_mixed,
        "within_arm_clean_minus_degraded": summ(within_arm),
        "pooled": {
            "clean": summ(clean_all),
            "degraded": summ(degr_all),
            "void": summ(void_all),
            "clean_minus_degraded_mean": (
                round(statistics.mean(clean_all) - statistics.mean(degr_all), 3)
                if clean_all and degr_all else None),
            "clean_minus_void_mean": (
                round(statistics.mean(clean_all) - statistics.mean(void_all), 3)
                if clean_all and void_all else None),
        },
    }
    print(json.dumps(out, indent=2))
    if args.out:
        json.dump(out, open(args.out, "w"), indent=2)


if __name__ == "__main__":
    main()
