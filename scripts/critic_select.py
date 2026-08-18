"""Critic-ordered curation selection (M8 D2′ funded method, m8-plan D2′).

The never-run method: `rank-critic-c2v3`'s CALIBRATED score replaces the
K=8 rollout map's `sel_wr` as the ordering/band-membership source.
Addressability screening + anchor placement carry verbatim from cycle-3
(this consumes `early_doom.py` trace/analyze output unchanged); the
selection and composition rules mirror `grindstone select` +
`compose_selection.py` with the critic's calibrated value standing where
those consumed rollout labels:

  per game   anchor candidates = crash+offset (0,-2,-4, clipped >=1) and
             peak — the exact turn set cycle-3 labeled — each with the
             trace's calibrated value at that turn (turns absent from the
             trace are skipped: no value, no candidate). Pick the LATEST
             in-band anchor (else the latest above-band, else exclude) —
             `select`'s rule verbatim.
  across     rank by BAND-CENTRALITY of the picked value,
  games      min(v - lo, hi - v) descending (the operationalization of
             "critic-ordered within bands": most-confidently-in-band
             first; above-band picks have negative centrality and only
             enter when in-band supply runs short — matching select's
             band-then-above preference). Cut to --size.
  compose    ahead-swaps to the peak anchor (calibrated peak value in
             band, peak_turn < crash_from_turn) in deterministic hash
             order until --ahead-share — `compose_selection.py` verbatim.

Emits selection.jsonl in schema parity with `grindstone select` EXCEPT
sel_wr/sel_n are replaced by sel_v (calibrated critic value): loudly
absent, so nothing downstream can silently mistake a critic score for
rollout truth (`plan --anchor selected` reads only drill_turn).

Usage (M8 D2′, after the audit gate funds the method):
  uv run python scripts/critic_select.py \
      --trace-dir data/runs/early-doom-m8-rankcrit \
      --isotonic data/runs/isotonic-maps/isotonic-maps-rank-critic-v1.json \
      --isotonic-key c2/v_rank \
      --out data/runs/drill-selection-m8-critic
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

OFFSETS = (0, -2, -4)  # crash-relative anchors; peak rides separately


def load_calibrated_traces(
    trace_dir: Path, isotonic: str, isotonic_key: str
) -> dict[tuple[str, int], dict[int, float]]:
    """(store, g) -> {turn: calibrated critic value}, remapped in memory
    exactly as early_doom analyze does (traces stay raw on disk)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from critic_calibration import pav_apply
    from isotonic_maps import load_map

    lo, vals = load_map(isotonic, isotonic_key)
    out: dict[tuple[str, int], dict[int, float]] = {}
    for line in (trace_dir / "traces.jsonl").read_text().splitlines():
        r = json.loads(line)
        vv = pav_apply(np.array([v for _, v in r["vals"]]), lo, vals)
        out[(r["store"], r["g"])] = {
            t: round(float(v), 4) for (t, _), v in zip(r["vals"], vv)
        }
    return out


def anchor_candidates(row: dict, tv: dict[int, float]) -> dict[int, float]:
    """The cycle-3 anchor turn set, restricted to turns the trace valued."""
    turns = {max(1, row["crash_from_turn"] + o) for o in OFFSETS}
    turns.add(row["peak_turn"])
    return {t: tv[t] for t in sorted(turns) if t in tv}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--trace-dir",
        required=True,
        help="early_doom out dir(s), comma-separated — the 4x pool is "
        "base stock + top-up stock (ADR-0061)",
    )
    ap.add_argument("--isotonic", required=True)
    ap.add_argument("--isotonic-key", required=True)
    ap.add_argument("--band", default="0.25:0.85")
    ap.add_argument("--size", type=int, default=320)
    ap.add_argument("--ahead-share", type=float, default=0.188)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.band.split(":"))

    traces: dict = {}
    cur: list[dict] = []
    for d in a.trace_dir.split(","):
        trace_dir = Path(d)
        traces.update(load_calibrated_traces(trace_dir, a.isotonic, a.isotonic_key))
        cur += [json.loads(x) for x in (trace_dir / "curation.jsonl").read_text().splitlines()]

    picked, stats = [], Counter()
    for row in cur:
        key = (row["store"], row["g"])
        cands = anchor_candidates(row, traces[key])
        in_band = [t for t, v in cands.items() if lo <= v <= hi]
        above = [t for t, v in cands.items() if v > hi]
        if in_band:
            t, rule = max(in_band), "critic-band"
        elif above:
            t, rule = max(above), "critic-above"
        else:
            stats["excluded"] += 1
            continue
        stats[rule] += 1
        v = cands[t]
        picked.append(
            dict(
                row,
                drill_turn=t,
                sel_rule=rule,
                sel_v=v,
                centrality=round(min(v - lo, hi - v), 4),
            )
        )

    # Fork-store index namespace (run17 iter-2 crash, 2026-08-18): encoded
    # fork indices carry source_g only (FORK_G_BASE + g*10000 + k), so the
    # same g drilled in two source stores collides in the training mixture
    # (MultiStore FATAL). Until the next-era store-format namespace fix,
    # selections must be cross-store g-unique: keep the higher-centrality
    # entry per g; the size cut below refills from the pool.
    best_by_g: dict[int, dict] = {}
    for r in picked:
        b = best_by_g.get(r["g"])
        if b is None or (r["centrality"], r["store"]) > (b["centrality"], b["store"]):
            best_by_g[r["g"]] = r
    stats["cross_store_g_dups_dropped"] = len(picked) - len(best_by_g)
    picked = list(best_by_g.values())

    # critic order: most-confidently-in-band first; deterministic tiebreak
    picked.sort(key=lambda r: (-r["centrality"], r["store"], r["g"]))
    pool_n = len(picked)
    picked = picked[: a.size]
    stats["cut"] = pool_n - len(picked)

    # composition: ahead-swaps, compose_selection.py mirrored on calibrated
    # peak values (peak label in band -> peak calibrated value in band)
    def is_ahead(r: dict) -> bool:
        return r["drill_turn"] == r["peak_turn"] and r["peak_turn"] < r["crash_from_turn"]

    n = len(picked)
    target = round(a.ahead_share * n)
    have = sum(1 for r in picked if is_ahead(r))
    cands = [
        r
        for r in picked
        if not is_ahead(r)
        and r["drill_turn"] == r["crash_from_turn"]
        and r["peak_turn"] < r["crash_from_turn"]
        and r["peak_turn"] in traces[(r["store"], r["g"])]
        and lo <= traces[(r["store"], r["g"])][r["peak_turn"]] <= hi
    ]
    cands.sort(key=lambda r: hashlib.sha256(f"compose:{r['store']}:{r['g']}".encode()).hexdigest())
    swapped = 0
    for r in cands:
        if have + swapped >= target:
            break
        pv = traces[(r["store"], r["g"])][r["peak_turn"]]
        r["drill_turn"] = r["peak_turn"]
        r["sel_v"] = pv
        r["centrality"] = round(min(pv - lo, hi - pv), 4)
        r["sel_rule"] = "critic-band-peak-compose"
        swapped += 1

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "selection.jsonl").open("w") as f:
        for r in picked:
            f.write(json.dumps(r) + "\n")

    final_ahead = sum(1 for r in picked if is_ahead(r))
    offsets = Counter(min(r["drill_turn"] - r["crash_from_turn"], 0) for r in picked)
    meta = {
        "method": "critic-ordered (m8-plan D2' funded branch)",
        "trace_dir": a.trace_dir.split(","),
        "isotonic": {"maps": a.isotonic, "key": a.isotonic_key},
        "band": [lo, hi],
        "size": a.size,
        "ordering": "band-centrality of calibrated critic value, descending",
        "pool_candidates": len(cur),
        "pool_selected": pool_n,
        "selected": len(picked),
        "stats": dict(stats),
        "mean_sel_v": round(sum(r["sel_v"] for r in picked) / n, 4) if picked else None,
        "compose": {
            "ahead_target": a.ahead_share,
            "swapped": swapped,
            "ahead_share": round(final_ahead / n, 4) if n else None,
        },
        "offset_vs_crash": {str(k): v for k, v in sorted(offsets.items())},
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps(meta, indent=1))
    print(f"[critic-select] {len(picked)} drill points -> {out / 'selection.jsonl'}")


if __name__ == "__main__":
    main()
