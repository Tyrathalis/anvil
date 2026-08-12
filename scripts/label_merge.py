"""Benchmark label merge with the holdout-freeze guard (M6 pre-tranche).

The frozen `frozen-probe-ext2-c2` benchmark is the standing gate for every
representation candidate (ADR-0041), and its measured points (ridge plateau
0.4552, unfreeze N=2 0.4769 — ADR-0043/0044) are only comparable while the
holdout stays byte-identical. New tranche labels therefore extend the TRAIN
side only.

Enforcement is two-layer:
  1. At the source (cheap): the campaign's plan step pre-filters candidate
     positions with `held_out(store, g)` — the split hashes (store, g),
     both known BEFORE any rollout is spent, so holdout-hashing games are
     simply never labeled (~20% of candidates skipped pre-spend, zero
     rollout waste). Import `held_out` from here.
  2. At the merge (the belt, this tool): any addition row that hashes into
     the holdout is REFUSED and counted loudly (nonzero = the campaign
     leaked), and the merged file's holdout row set is proven identical to
     the base's before anything is written.

Join + row schema are critic_calibration.build_dataset verbatim (drill
maps/sweep arms x early-doom traces -> wr + v_era/v_d4 columns). Dedup:
within one label source, repeated (store, g, t) rows are crash re-launch
duplicates (the bench_labeler lesson) — first row wins.

Usage:
  uv run python scripts/label_merge.py merge \
      --base data/runs/frozen-probe-ext2-c2/dataset.jsonl \
      --era c2 \
      --labels data/runs/<map-or-arm-dir> [--labels ...] \
      --trace-era data/runs/<early-doom-era-dir> \
      --trace-d4 data/runs/<early-doom-d4-dir> \
      --out data/runs/<new>/dataset.jsonl
  uv run python scripts/label_merge.py check \
      --base data/runs/frozen-probe-ext2-c2/dataset.jsonl \
      --dataset data/runs/<new>/dataset.jsonl
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from pathlib import Path


def held_out(store: str, g: int) -> bool:
    """The deterministic ~20%-by-game holdout split of record
    (critic_calibration._held_out / frozen_probe._held_out)."""
    h = hashlib.sha256(f"{store}:{g}".encode()).digest()
    return h[0] % 5 == 0


def _row_key(r: dict) -> tuple:
    return (r["store"], r["g"], r["t"], r.get("src"))


def _load(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).open()]


def _load_traces(paths: list[str]) -> dict[tuple, dict[int, float]]:
    """Union of trace dirs (a campaign's labels may span several
    early-doom trace runs); duplicate (store, g) keys must agree —
    conflicting traces mean mixed critic eras, refuse."""
    out: dict[tuple, dict[int, float]] = {}
    for path in paths:
        for line in Path(path, "traces.jsonl").open():
            r = json.loads(line)
            key = (r["store"], r["g"])
            vals = {t: v for t, v in r["vals"]}
            if key in out and out[key] != vals:
                raise SystemExit(
                    f"[merge] trace conflict for {key} across "
                    f"trace dirs — mixed critic eras, refusing"
                )
            out[key] = vals
    return out


def build_rows(
    era: str, label_dirs: list[str], trace_era: list[str], trace_d4: list[str]
) -> tuple[list[dict], dict]:
    """critic_calibration.build_dataset's join, plus per-source crash-dupe
    dedup; returns (rows, stats)."""
    tr = {"era": _load_traces(trace_era), "d4": _load_traces(trace_d4)}
    rows, miss, dupes = [], 0, 0
    for src in label_dirs:
        seen: set = set()
        for line in Path(src, "drills.jsonl").open():
            r = json.loads(line)
            if r["n"] <= 0:
                continue
            key = (r["store"], r["g"], r["fired_t"])
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            vals = {k: tr[k].get((r["store"], r["g"]), {}).get(r["fired_t"]) for k in tr}
            if any(v is None for v in vals.values()):
                miss += 1
                continue
            rows.append(
                {
                    "era": era,
                    "src": Path(src).name,
                    "store": r["store"],
                    "g": r["g"],
                    "t": r["fired_t"],
                    "wr": r["model_wins"] / r["n"],
                    "n": r["n"],
                    "v_era": vals["era"],
                    "v_d4": vals["d4"],
                    "deck": r["deck"],
                }
            )
    return rows, {"trace_join_misses": miss, "crash_dupes_dropped": dupes}


def merge(args: argparse.Namespace) -> None:
    base = _load(args.base)
    base_keys = {_row_key(r) for r in base}
    base_holdout = {_row_key(r) for r in base if held_out(r["store"], r["g"])}

    new_rows, stats = build_rows(args.era, args.labels, args.trace_era, args.trace_d4)
    refused = [r for r in new_rows if held_out(r["store"], r["g"])]
    kept = [r for r in new_rows if not held_out(r["store"], r["g"])]
    collide = [r for r in kept if _row_key(r) in base_keys]
    kept = [r for r in kept if _row_key(r) not in base_keys]

    merged = base + kept
    # the freeze proof: identical holdout row set, before anything is written
    merged_holdout = {_row_key(r) for r in merged if held_out(r["store"], r["g"])}
    if merged_holdout != base_holdout:
        raise SystemExit(
            "[merge] FREEZE VIOLATION: merged holdout differs from base holdout — refusing to write"
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in merged:
            f.write(json.dumps(r) + "\n")
    meta = {
        "base": str(args.base),
        "n_base": len(base),
        "labels": args.labels,
        "traces": {"era": args.trace_era, "d4": args.trace_d4},
        "created": _dt.date.today().isoformat(),
        "n_new_built": len(new_rows),
        "n_new_kept": len(kept),
        "n_refused_holdout_hash": len(refused),
        "n_base_key_collisions": len(collide),
        **stats,
        "n_merged": len(merged),
        "holdout_rows_unchanged": len(base_holdout),
        "train_rows": len(merged) - len(base_holdout),
    }
    Path(str(out) + ".merge-meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    if refused:
        print(
            f"[merge] WARNING {len(refused)} rows refused by the freeze "
            "guard — the campaign's plan-time filter leaked; rollouts "
            "were wasted on holdout-hashing games"
        )
    print(
        f"[merge] holdout PROVEN unchanged ({len(base_holdout)} rows); "
        f"train {meta['train_rows']} (+{len(kept)}) -> {out}"
    )


def check(args: argparse.Namespace) -> None:
    base = _load(args.base)
    ds = _load(args.dataset)
    bh = {_row_key(r) for r in base if held_out(r["store"], r["g"])}
    dh = {_row_key(r) for r in ds if held_out(r["store"], r["g"])}
    ok = bh == dh
    print(f"[check] base holdout {len(bh)} rows; dataset holdout {len(dh)} rows; identical: {ok}")
    if not ok:
        extra, missing = dh - bh, bh - dh
        print(
            f"[check] extra {len(extra)} e.g. {sorted(extra)[:3]}; "
            f"missing {len(missing)} e.g. {sorted(missing)[:3]}"
        )
        raise SystemExit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("merge")
    p.add_argument("--base", required=True)
    p.add_argument("--era", required=True)
    p.add_argument("--labels", action="append", required=True)
    p.add_argument("--trace-era", action="append", required=True)
    p.add_argument("--trace-d4", action="append", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=merge)
    p = sub.add_parser("check")
    p.add_argument("--base", required=True)
    p.add_argument("--dataset", required=True)
    p.set_defaults(fn=check)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
