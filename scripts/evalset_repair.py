#!/usr/bin/env python3
"""M10 R5: the payment-evalset repair (ADR-0069's owed item, ADR-0073's
empirical inputs, executed at ADR-0082).

Two defects, both settled against the banked certification data — no new
rollouts:

1. **Exact-index scoring was unfair on multi-arm outcome classes.** The
   certify read picks `best = max(cleared_pos)` — and tuple comparison
   tiebreaks EQUAL margins by highest arm index, an arbitrary choice no
   model can infer. Measured on the v1 positives: 11/17 wide_choice, 9/26
   color_hold, 3/13 blocker_pressure windows carry ≥2 INDEPENDENTLY
   certified positive arms (many margin-identical). The repair: every
   positive gains `cls` = the full cleared-positive arm list (the read's
   own predicate re-applied per arm) — the outcome-equivalence class the
   ADR-0066 rule says consumers must consume.
2. **phyrexian positives are value-free at game end** (ADR-0073: Δ=0.0pp
   at both horizons) — the 13 rows RETIRE with reason; the shape's
   auto-correct rows stand (their claim is class-free).

Outputs (new version dirs — evalset versions are era-scoped assets):
  data/runs/payment-evalset-v2/   repaired training evalset (v1 lineage)
  data/runs/payment-holdout-v1/   the ratesweep-certified set, same class
                                  treatment — the PRE-REGISTERED
                                  conditional holdout (uniform-drawn;
                                  m10-build-spec §5 family 5). Never
                                  ingested; the per-iteration holdout
                                  score is the generalization read.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from payment_certify import CONSISTENT, MARGIN, _axes, _payer_seat, _score  # noqa: E402

EVALSET_V1 = Path("data/runs/payment-evalset-v1")
OUT_V2 = Path("data/runs/payment-evalset-v2")
OUT_HOLDOUT = Path("data/runs/payment-holdout-v1")
BATCHES = {
    "b1": ("data/census/run-20260820-paygoals3/certify.out.jsonl",
           "data/census/run-20260820-paygoals3/certify-jobs.jsonl"),
    "b2": ("data/census/run-20260820-paygoals3/certify2.out.jsonl",
           "data/census/run-20260820-paygoals3/certify2-jobs.jsonl"),
    "b3": ("data/census/run-20260820-paygoals3/certify3.out.jsonl",
           "data/census/run-20260820-paygoals3/certify3-jobs.jsonl"),
    "b4": ("data/census/run-20260821-handbuilt/certify4.out.jsonl",
           "data/census/run-20260821-handbuilt/certify4-jobs.jsonl"),
}
SWEEP = ("data/census/run-20260824-ratesweep/sweep.out.jsonl",
         "data/census/run-20260824-ratesweep/sweep-jobs.jsonl")


def load_batch(certout: str, jobsfile: str):
    rows: dict[tuple, list] = defaultdict(list)
    for line in open(certout):
        r = json.loads(line)
        if r.get("ev") == "certify":
            rows[(r["job"], r["arm"])].append(r)
    jobs = {j["job"]: j for j in map(json.loads, open(jobsfile))}
    return rows, jobs


def cleared_class(rows, jobs, jid: int, shape: str) -> list[int]:
    """The read's certification predicate re-applied per arm — the full
    cleared-positive class."""
    base = sorted(rows[(jid, 0)], key=lambda x: x["roll"])
    if not base:
        return []
    seat = _payer_seat(base[0], jobs[jid])
    out = []
    for a in sorted(a for (j, a) in rows if j == jid and a > 0):
        paired = [
            _score(shape, _axes(r, seat), _axes(b, seat))
            for r, b in zip(sorted(rows[(jid, a)], key=lambda x: x["roll"]), base)
            if r["fired"] and r.get("exec") == "directed_ok"
        ]
        if not paired:
            continue
        mean = sum(paired) / len(paired)
        agree = sum(1 for s in paired if (s > 0) == (mean > 0)) / len(paired)
        if mean > 0 and abs(mean) >= MARGIN.get(shape, 2.0) and agree >= CONSISTENT:
            out.append(a)
    return out


def repair_evalset() -> dict:
    loaded = {b: load_batch(co, jf) for b, (co, jf) in BATCHES.items()}
    OUT_V2.mkdir(parents=True, exist_ok=True)
    kept, retired, stats = [], [], defaultdict(int)
    for line in open(EVALSET_V1 / "positive-drills.jsonl"):
        d = json.loads(line)
        if d["shape"] == "phyrexian":
            retired.append({**d, "retired_why": (
                "ADR-0082 (from ADR-0073 decision 5): phyrexian converts "
                "+0.0pp at game end — value-free at both horizons; the 13 "
                "positives do not survive repair")})
            stats["retired_phyrexian"] += 1
            continue
        rows, jobs = loaded[d["batch"]]
        cls = cleared_class(rows, jobs, d["job"], d["shape"])
        if d["best"] not in cls:
            raise SystemExit(f"repair invariant broken: best {d['best']} not in "
                             f"recomputed class {cls} ({d['batch']} job {d['job']})")
        kept.append({**d, "cls": cls})
        stats["kept"] += 1
        stats["multi_arm"] += int(len(cls) >= 2)
    with open(OUT_V2 / "positive-drills.jsonl", "w") as f:
        for d in kept:
            f.write(json.dumps(d) + "\n")
    (OUT_V2 / "autocorrect-drills.jsonl").write_bytes(
        (EVALSET_V1 / "autocorrect-drills.jsonl").read_bytes()
    )
    with open(OUT_V2 / "retired-drills.jsonl", "w") as f:
        for d in retired:
            f.write(json.dumps(d) + "\n")
    v1_meta = json.loads((EVALSET_V1 / "meta.json").read_text())
    meta = {
        "version": "payment-evalset-v2",
        "created": "2026-08-27",
        "lineage": "payment-evalset-v1 (ADR-0082 repair: cls outcome-classes "
                   "on positives; phyrexian positives retired)",
        "thresholds": v1_meta["thresholds"],
        "batches": v1_meta["batches"],
        "counts": {
            "positive": stats["kept"],
            "positive_multi_arm": stats["multi_arm"],
            "autocorrect": sum(1 for _ in open(OUT_V2 / "autocorrect-drills.jsonl")),
            "retired": stats["retired_phyrexian"],
        },
    }
    (OUT_V2 / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return dict(stats)


def build_holdout() -> dict:
    rows, jobs = load_batch(*SWEEP)
    OUT_HOLDOUT.mkdir(parents=True, exist_ok=True)
    stats = defaultdict(int)
    src = Path("data/census/run-20260824-ratesweep")
    kept = []
    for line in open(src / "sweep-certified.jsonl"):
        d = json.loads(line)
        cls = cleared_class(rows, jobs, d["job"], d["shape"])
        if d["best"] not in cls:
            raise SystemExit(f"holdout invariant broken: job {d['job']}")
        kept.append({**d, "batch": "sweep", "cls": cls})
        stats["positive"] += 1
        stats["multi_arm"] += int(len(cls) >= 2)
    with open(OUT_HOLDOUT / "positive-drills.jsonl", "w") as f:
        for d in kept:
            f.write(json.dumps(d) + "\n")
    with open(OUT_HOLDOUT / "autocorrect-drills.jsonl", "w") as f:
        for line in open(src / "autocorrect-drills.jsonl"):
            d = json.loads(line)
            f.write(json.dumps({**d, "batch": "sweep"}) + "\n")
            stats["autocorrect"] += 1
    meta = {
        "version": "payment-holdout-v1",
        "created": "2026-08-27",
        "lineage": "run-20260824-ratesweep certified set (uniform-drawn, "
                   "ADR-0075) + ADR-0082 cls treatment — the pre-registered "
                   "conditional HOLDOUT (m10-build-spec §5 family 5). "
                   "NEVER ingested for training.",
        "counts": dict(stats),
    }
    (OUT_HOLDOUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return dict(stats)


if __name__ == "__main__":
    s1 = repair_evalset()
    print(f"evalset v2: {s1}")
    s2 = build_holdout()
    print(f"holdout v1: {s2}")
