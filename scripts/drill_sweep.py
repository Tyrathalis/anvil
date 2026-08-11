"""Turn-offset/peak-turn drill sweep (M4 D3, experiment 1).

The 584-drill map's headline — rollout winrate 23.7% vs mean v_before
0.584, lost-at-crash 58% — says most value-crash windows sit AFTER the
real decision error. This driver re-drills a chosen ground-truth bin at
earlier fork anchors and measures where the positions become winnable:
the per-game recovery profile is the curation refinement D3's training
drills select on.

Each arm (tag:anchor:offset) is a full plan -> generate -> report cycle
under its own run-dir tag (report aggregation is per-tag; untagged arms
would supersede each other's labels per game). The FIRST arm is the
paired baseline — run o0 (anchor=crash, offset 0) first: bins were
selected on their own noisy K=8 labels, so only a same-conditions
re-measure is a fair baseline (the D2.4 regression-to-the-mean lesson).

Resume is per-arm: an arm whose report.json exists is skipped, so a
killed sweep rerun redoes at most one arm (~1.1 h at w=8).

Usage:
  uv run python scripts/drill_sweep.py \
      --map data/runs/drill-map-r9i9-k8 \
      --bins lost \
      --arms o0:crash:0,o2:crash:-2,o4:crash:-4,peak:peak:0 \
      --out data/runs/drill-sweep-lost-20260729
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import threading
import time
from collections import Counter
from pathlib import Path

from anvil.grindstone import __main__ as gs
from anvil.training.notify import notify


def _parse_arms(spec: str) -> list[dict]:
    arms = []
    for part in spec.split(","):
        tag, anchor, off = part.split(":")
        if anchor not in gs.ANCHOR_FIELD:
            raise SystemExit(f"FATAL: unknown anchor {anchor!r} in {part!r}")
        arms.append({"tag": tag, "anchor": anchor, "turn_offset": int(off)})
    if len({a["tag"] for a in arms}) != len(arms):
        raise SystemExit("FATAL: duplicate arm tags")
    return arms


def _subset_curation(
    map_dir: Path, bins: set[str], out: Path, filter_holdout: bool = False
) -> Path:
    """Filter the map's source curation to the games whose K-rollout
    ground truth fell in the requested bins. filter_holdout (M6 tranche,
    label_merge freeze protocol): additionally drop games hashing into
    the frozen benchmark holdout BEFORE any rollout is spent — new labels
    are train-side only."""
    manifest = json.loads((map_dir / "manifest.json").read_text())
    keep = set()
    for line in (map_dir / "drills.jsonl").open():
        r = json.loads(line)
        if r["n"] > 0 and gs._bin_of(r["model_wins"], r["n"]) in bins:
            keep.add((r["store"], r["g"]))
    dropped_ho = 0
    if filter_holdout:
        from label_merge import held_out

        ho = {k for k in keep if held_out(*k)}
        dropped_ho = len(ho)
        keep -= ho
    subset = out / "subset-curation.jsonl"
    n = 0
    with subset.open("w") as f, Path(manifest["curation"]).open() as src:
        for line in src:
            c = json.loads(line)
            if (c["store"], c["g"]) in keep:
                f.write(line)
                n += 1
    if n != len(keep):
        raise SystemExit(
            f"FATAL: {len(keep)} mapped games but {n} curation rows — map/curation mismatch"
        )
    print(
        f"[sweep] subset: {n} games in bins {sorted(bins)}"
        + (f" (holdout-hash pre-filter dropped {dropped_ho})" if filter_holdout else "")
    )
    return subset


def _watchdog(out: Path, tags: list[str], stall_min: int, state: dict) -> None:
    """Notify once per stall if no arm has written a label recently while
    the sweep is still running. Progress clock resets at each arm start
    (state['phase_start']) — server boot + pre-fork mainline replay write
    no labels."""
    quiet = False
    while not state["done"]:
        time.sleep(300)
        newest = state["phase_start"]
        for tag in tags:
            for lf in glob.glob(
                str(gs.RUNS_DIR / f"drill{tag}-*" / "workers" / "*" / "labels.jsonl")
            ):
                newest = max(newest, os.path.getmtime(lf))
        stalled = time.time() - newest > stall_min * 60
        if stalled and not quiet:
            notify("anvil drill sweep STALLED", f"no labels written in {stall_min} min ({out})")
            quiet = True
        elif not stalled:
            quiet = False


def _arm_rows(arm_dir: Path) -> dict[tuple, dict]:
    return {(r["store"], r["g"]): r for r in map(json.loads, (arm_dir / "drills.jsonl").open())}


def _summarize(out: Path, arms: list[dict]) -> dict:
    per_arm = {}
    for a in arms:
        rows = _arm_rows(out / f"arm-{a['tag']}")
        rep = json.loads((out / f"arm-{a['tag']}" / "report.json").read_text())
        per_arm[a["tag"]] = {
            **a,
            "labeled": rep["drills_labeled"],
            "replay_missed": rep["replay_missed"],
            "all_completions_crashed": rep["all_completions_crashed"],
            "rollout_winrate": rep["rollout_winrate"],
            "bins": rep["bins"],
            "mean_fired_t": round(sum(r["fired_t"] for r in rows.values()) / len(rows), 2)
            if rows
            else None,
            "_rows": rows,
        }

    base_tag = arms[0]["tag"]
    base = per_arm[base_tag]["_rows"]
    paired = {}
    for a in arms[1:]:
        rows = per_arm[a["tag"]]["_rows"]
        common = [
            (base[k], rows[k])
            for k in base.keys() & rows.keys()
            if base[k]["n"] > 0 and rows[k]["n"] > 0
        ]
        deltas = [r["model_wins"] / r["n"] - b["model_wins"] / b["n"] for b, r in common]
        trans = Counter(
            f"{gs._bin_of(b['model_wins'], b['n'])}->{gs._bin_of(r['model_wins'], r['n'])}"
            for b, r in common
        )
        paired[a["tag"]] = {
            "n_pairs": len(common),
            "mean_wr_delta": round(sum(deltas) / len(deltas), 4) if deltas else None,
            "transitions": dict(trans.most_common()),
        }

    summary = {
        "arms": {t: {k: v for k, v in d.items() if k != "_rows"} for t, d in per_arm.items()},
        "paired_vs_" + base_tag: paired,
    }
    return summary


def main() -> None:
    import sys

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--map", type=Path, required=True, help="mapped manifest dir (plan+generate+report done)"
    )
    ap.add_argument("--bins", default="lost", help="comma-joined ground-truth bins to re-drill")
    ap.add_argument(
        "--arms",
        default="o0:crash:0,o2:crash:-2,o4:crash:-4,peak:peak:0",
        help="comma-joined tag:anchor:turn_offset specs; the first arm is the paired baseline",
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--k", type=int, default=None, help="completions per drill (default: the map's K)"
    )
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--port", type=int, default=50067)
    ap.add_argument("--limit", type=int, default=0, help="first N subset rows only (smokes)")
    ap.add_argument("--stall-min", type=int, default=75)
    ap.add_argument(
        "--filter-holdout",
        action="store_true",
        help="drop games hashing into the frozen benchmark "
        "holdout pre-spend (label_merge freeze protocol)",
    )
    a = ap.parse_args()

    arms = _parse_arms(a.arms)
    map_manifest = json.loads((a.map / "manifest.json").read_text())
    k = a.k or map_manifest["k"]
    a.out.mkdir(parents=True, exist_ok=True)
    subset = _subset_curation(a.map, set(a.bins.split(",")), a.out, filter_holdout=a.filter_holdout)

    (a.out / "meta.json").write_text(
        json.dumps(
            {
                "map": str(a.map),
                "bins": sorted(a.bins.split(",")),
                "arms": arms,
                "k": k,
                "ckpt": map_manifest["ckpt"],
                "limit": a.limit or None,
                "note": "measurement sweep — evalset holdout is NOT subtracted "
                "here; D3 training plans must subtract it themselves",
            },
            indent=2,
        )
        + "\n"
    )

    state = {"done": False, "phase_start": time.time()}
    wd = threading.Thread(
        target=_watchdog, daemon=True, args=(a.out, [x["tag"] for x in arms], a.stall_min, state)
    )
    wd.start()

    try:
        for arm in arms:
            arm_dir = a.out / f"arm-{arm['tag']}"
            if (arm_dir / "report.json").exists():
                print(f"[sweep] arm {arm['tag']}: report exists, skipping")
                continue
            state["phase_start"] = time.time()
            print(f"[sweep] arm {arm['tag']}: anchor={arm['anchor']} offset={arm['turn_offset']}")
            gs.plan(
                argparse.Namespace(
                    curation=subset,
                    out=str(arm_dir),
                    ckpt=map_manifest["ckpt"],
                    k=k,
                    anchor=arm["anchor"],
                    turn_offset=arm["turn_offset"],
                    tag=arm["tag"],
                    limit=a.limit,
                )
            )
            gs.generate(
                argparse.Namespace(
                    manifest=str(arm_dir),
                    ckpt=None,
                    k=None,
                    port=a.port,
                    workers=a.workers,
                    chunk=a.chunk,
                    drill_stop=True,
                    fork_obs=False,
                    drill_ckpt=None,
                    sample_forks=False,
                )
            )
            gs.report(argparse.Namespace(manifest=str(arm_dir)))

        summary = _summarize(a.out, arms)
        (a.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        wr = {t: d["rollout_winrate"] for t, d in summary["arms"].items()}
        notify("anvil drill sweep done", f"winrates {wr} ({a.out})")
    except BaseException as e:
        notify("anvil drill sweep FAILED", f"{type(e).__name__}: {e}")
        raise
    finally:
        state["done"] = True


if __name__ == "__main__":
    main()
