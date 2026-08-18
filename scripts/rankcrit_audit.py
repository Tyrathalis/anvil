"""M8 D2′ entry-gate audit of rank-critic-c2v3 ordering (m8-plan D2′).

Gate PINNED 2026-08-17 at the design session, before any generation;
threshold AMENDED same session 0.45 -> 0.35 (m8-plan D2' amendment,
user-approved, before any audit labels existed): the smoke's validation
read measured the in-era, same-population benchmark at 0.377 — the gate
now asks whether ordering survives the ERA TRANSFER, not whether it
matches the training-holdout 0.4833 measured on a different population
type. Spearman >= 0.35 between the critic's calibrated score and K=8
rollout `sel_wr` on N=500 uniformly-random anchor points from the fresh
candidate pool. Pass => critic-ordered curation (scripts/critic_select.py);
fail => corrected-map fallback composition from these same labels.

Two verbs:

  sample  trace/curation dir -> audit-selection.jsonl: N anchor points
          drawn uniformly (seeded) over the pool's (game x anchor-turn)
          set — the same anchor turns cycle-3 labeled (crash+{0,-2,-4},
          peak) — NOT band-filtered (banding on labels-under-test would
          condition on the answer). Consumed directly by
          `grindstone plan --anchor selected --k 8`.
  read    audit label dirs + traces -> audit-report.json:
          1. THE GATE: Spearman(calibrated critic, sel_wr), verdict vs
             the pinned threshold.
          2. The pinned pool-scale rule: selectivity curve — points
             ordered by band-centrality of the calibrated value (the
             critic_select ordering), sliced at effective pool scales
             {1,2,4,8}x (selection fractions 320/(422*s)); primary
             metric = true-in-band precision; final scale = largest
             within 5pp of the 1x read, CAP 4x. Rollout-labeled
             quantities only — no self-grading.
          3. Descriptive (never gating): per-truth-bin ordering quality
             (the ADR-0036 winnable-blindness check), top-quartile
             enrichment, calibration level check.

Usage:
  uv run python scripts/rankcrit_audit.py sample \
      --trace-dir data/runs/early-doom-m8-rankcrit --n 500 \
      --seed 20260818 --out data/runs/m8-audit
  uv run python scripts/rankcrit_audit.py read \
      --audit-labels data/runs/drillm8audit-... \
      --trace-dir data/runs/early-doom-m8-rankcrit \
      --isotonic data/runs/isotonic-maps/isotonic-maps-rank-critic-v1.json \
      --isotonic-key c2/v_rank --out data/runs/m8-audit
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from critic_select import anchor_candidates, load_calibrated_traces

# PINNED (m8-plan D2', 2026-08-17; amended 0.45 -> 0.35 same session,
# before any audit labels — the in-era benchmark re-reference) — do not tune
THRESHOLD = 0.35
CURVE_SCALES = (1, 2, 4, 8)
CURVE_BASE_FRAC = 320 / 422  # cycle-3's realized selectivity = the 1x point
CURVE_MARGIN = 0.05
CURVE_CAP = 4


def bin_of(wr: float) -> str:
    # grindstone _bin_of, on a winrate
    return "lost" if wr <= 0.2 else "long_shot" if wr <= 0.45 else "coin" if wr <= 0.7 else "winnable"


def sample(a: argparse.Namespace) -> None:
    trace_dir = Path(a.trace_dir)
    turns_of: dict[tuple[str, int], set[int]] = {}
    for line in (trace_dir / "traces.jsonl").read_text().splitlines():
        r = json.loads(line)
        turns_of[(r["store"], r["g"])] = {t for t, _ in r["vals"]}
    cur = [json.loads(x) for x in (trace_dir / "curation.jsonl").read_text().splitlines()]

    points = []
    for row in cur:
        tv = dict.fromkeys(turns_of[(row["store"], row["g"])], 0.0)
        for t in anchor_candidates(row, tv):
            points.append((row, t))

    rng = np.random.default_rng(a.seed)
    idx = rng.permutation(len(points))[: a.n]
    picked = [points[i] for i in sorted(idx)]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "audit-selection.jsonl").open("w") as f:
        for row, t in picked:
            f.write(json.dumps(dict(row, drill_turn=t, sel_rule="audit-uniform")) + "\n")
    meta = {
        "trace_dir": str(trace_dir),
        "pool_games": len(cur),
        "pool_points": len(points),
        "n": len(picked),
        "seed": a.seed,
        "games_in_sample": len({(r["store"], r["g"]) for r, _ in picked}),
        "offset_mix": dict(
            Counter(
                "peak" if t == r["peak_turn"] and t != r["crash_from_turn"]
                else str(min(t - r["crash_from_turn"], 0))
                for r, t in picked
            )
        ),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps(meta, indent=1))
    print(f"[audit-sample] {len(picked)} points -> {out / 'audit-selection.jsonl'}")


def read(a: argparse.Namespace) -> None:
    from scipy.stats import spearmanr

    lo, hi = (float(x) for x in a.band.split(":"))
    traces = load_calibrated_traces(Path(a.trace_dir), a.isotonic, a.isotonic_key)

    # later label sources supersede earlier at the same point (D2.4 lesson)
    labels: dict[tuple[str, int, int], tuple[int, int]] = {}
    for src in a.audit_labels.split(","):
        for line in (Path(src) / "drills.jsonl").open():
            r = json.loads(line)
            if r["n"] > 0:
                labels[(r["store"], r["g"], r["fired_t"])] = (r["model_wins"], r["n"])

    joined = []
    misses = 0
    for (store, g, t), (w, n) in sorted(labels.items()):
        tv = traces.get((store, g), {})
        if t not in tv:
            misses += 1
            continue
        v = tv[t]
        joined.append(
            {
                "store": store,
                "g": g,
                "t": t,
                "v_cal": v,
                "wr": w / n,
                "n": n,
                "centrality": round(min(v - lo, hi - v), 4),
            }
        )
    if not joined:
        raise SystemExit("FATAL: zero joined points")

    v = np.array([p["v_cal"] for p in joined])
    wr = np.array([p["wr"] for p in joined])

    # ---- 1. THE GATE ----
    rho, _ = spearmanr(v, wr)
    rho = float(rho)
    se_z = 1.0 / np.sqrt(len(joined) - 3)
    verdict = "PASS" if rho >= a.threshold else "FAIL"

    # ---- 2. the pinned pool-scale rule (selectivity curve) ----
    order = sorted(joined, key=lambda p: (-p["centrality"], p["store"], p["g"], p["t"]))
    curve = {}
    for s in CURVE_SCALES:
        k = max(1, round(CURVE_BASE_FRAC / s * len(order)))
        top = order[:k]
        curve[f"{s}x"] = {
            "frac": round(CURVE_BASE_FRAC / s, 4),
            "n": k,
            "in_band_precision": round(
                sum(1 for p in top if lo <= p["wr"] <= hi) / k, 4
            ),
        }
    p1 = curve["1x"]["in_band_precision"]
    eligible = [
        s
        for s in CURVE_SCALES
        if s <= CURVE_CAP and curve[f"{s}x"]["in_band_precision"] >= p1 - CURVE_MARGIN
    ]
    final_scale = max(eligible) if eligible else 1

    # ---- 3. descriptive (never gating) ----
    by_bin: dict[str, list[dict]] = {}
    for p in joined:
        by_bin.setdefault(bin_of(p["wr"]), []).append(p)
    per_bin = {}
    for b, rows in sorted(by_bin.items()):
        entry = {"n": len(rows), "mean_v_cal": round(float(np.mean([p["v_cal"] for p in rows])), 4)}
        if len(rows) >= 10:
            r_b, _ = spearmanr([p["v_cal"] for p in rows], [p["wr"] for p in rows])
            entry["spearman"] = round(float(r_b), 4)
        per_bin[b] = entry
    q = max(1, len(order) // 4)
    enrich = sum(1 for p in order[:q] if lo <= p["wr"] <= hi) / q
    base = sum(1 for p in joined if lo <= p["wr"] <= hi) / len(joined)

    report = {
        "gate": {
            "threshold_pinned": a.threshold,
            "spearman": round(rho, 4),
            "n_points": len(joined),
            "se_fisher_z": round(float(se_z), 4),
            "verdict": verdict,
            "reference": {
                "in_era_population_benchmark": 0.3772,
                "home_holdout": 0.4833,
                "blind_floor": 0.27,
                "k8_repeat_ceiling": 0.94,
            },
        },
        "pool_scale_rule": {
            "curve": curve,
            "margin": CURVE_MARGIN,
            "cap": CURVE_CAP,
            "final_scale": final_scale,
        },
        "descriptive": {
            "per_truth_bin": per_bin,
            "top_quartile_in_band": round(enrich, 4),
            "pool_in_band": round(base, 4),
            "mean_v_cal": round(float(v.mean()), 4),
            "mean_wr": round(float(wr.mean()), 4),
            "label_trace_misses": misses,
        },
        "inputs": {
            "audit_labels": a.audit_labels.split(","),
            "trace_dir": a.trace_dir,
            "isotonic": {"maps": a.isotonic, "key": a.isotonic_key},
            "band": [lo, hi],
        },
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit-report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    print(
        f"[audit-read] GATE {verdict}: spearman {rho:.4f} vs pinned "
        f"{a.threshold} (n={len(joined)}, se_z {se_z:.3f}); pool scale "
        f"{final_scale}x -> {out / 'audit-report.json'}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="verb", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--trace-dir", required=True)
    s.add_argument("--n", type=int, default=500)
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=sample)
    r = sub.add_parser("read")
    r.add_argument("--audit-labels", required=True, help="comma-separated drills.jsonl dirs")
    r.add_argument("--trace-dir", required=True)
    r.add_argument("--isotonic", required=True)
    r.add_argument("--isotonic-key", required=True)
    r.add_argument("--band", default="0.25:0.85")
    r.add_argument("--threshold", type=float, default=THRESHOLD)
    r.add_argument("--out", required=True)
    r.set_defaults(fn=read)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
