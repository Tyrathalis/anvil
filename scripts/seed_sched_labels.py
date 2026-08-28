#!/usr/bin/env python3
"""M10 R5: mint the best-arm seed-supervision labels (the ceiling spec's
co-design dividend 9 — "best-arm schedules become seed supervision"; the
ceiling-drills.jsonl precedent).

For each certified-positive sweep turn (ADR-0078 stage 1, select/score
split — winner's-curse-priced by construction), reconstruct the emission
window from the ceiling census store and map the selected best arm's
ordered action labels to the window's candidate indices (the decode head's
class space: 0 = STOP, j = candidate j). Rows whose labels fail to match
(enumeration drift, ambiguity) are counted and dropped LOUDLY.

The output is an ERA-ASSET (labels certified under iter-019 rollouts on
the boundary-era jar); the sweep machinery is the re-runnable mint at
boundaries/scale.

Usage:
  uv run python scripts/seed_sched_labels.py \
      --plan data/runs/sched-sweep-m10 \
      --store data/runs/m10-ceiling-census-20260825-212414 \
      --out data/runs/sched-sweep-m10/seed-sched-labels.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="data/runs/sched-sweep-m10")
    ap.add_argument("--store", default="data/trajectories/m10-ceiling-census-20260825-212414")
    ap.add_argument("--out", default="data/runs/sched-sweep-m10/seed-sched-labels.jsonl")
    args = ap.parse_args()

    from v2_target_probe import _main1_window  # noqa: E402

    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import SCHED_CAP

    positives = [json.loads(x) for x in open(Path(args.plan) / "positives.jsonl")]
    by_game: dict[int, list[dict]] = {}
    for p in positives:
        if p.get("paymode") == "joint":
            by_game.setdefault(p["g"], []).append(p)

    ts = TrajectoryStore(Path(args.store))
    frame: Counter = Counter()
    rows = []
    for traj in ts.games(skip_undecodable=True):
        g = traj.header["g"]
        wants = by_game.get(g)
        if not wants:
            continue
        players = traj.header.get("players") or []
        seat = next((i for i, pl in enumerate(players)
                     if str(pl.get("name", "")).startswith("Anvil")), 0)
        by_turn: dict[int, list[dict]] = {}
        for dec in traj.decisions:
            if (dec.get("m") == "chooseSpellAbilityToPlay"
                    and dec.get("p") == seat and dec.get("t", 0) >= 1):
                by_turn.setdefault(dec["t"], []).append(dec)
        for p in wants:
            emis = _main1_window(by_turn.get(p["t"]) or [], seat)
            if emis is None:
                frame["no_window"] += 1
                continue
            # label -> FIRST matching wire-option candidate index (the
            # executor's own label-match convention); candidate j = wire
            # option j is NOT the mapping here — the featurizer collapses,
            # so record (e, sa) pairs and let the loader rebuild indices
            # through its own cand map. We store the matched option's
            # (e, sa60) — loader-independent identity.
            opts = emis.get("opts") or []
            seq = []
            ok = True
            for lab in p["labels"]:
                hit = next(
                    (o for o in opts if str(o.get("sa") or "")[:60] == lab[:60]), None
                )
                if hit is None:
                    frame["label_unmatched"] += 1
                    ok = False
                    break
                seq.append([hit.get("e"), str(hit.get("sa") or "")[:60]])
            if not ok:
                frame["dropped"] += 1
                continue
            if len(seq) > SCHED_CAP:
                frame["truncated"] += 1
                seq = seq[:SCHED_CAP]
            rows.append({
                "store": Path(args.store).name,
                "g": g, "t": p["t"], "seat": seat, "arm": p["arm"],
                "score_mean": p.get("score_mean"),
                "seq": seq,
                "s": emis.get("s"),  # the emission dec id, for exact rejoin
            })
            frame["minted"] += 1
    out = Path(args.out)
    with open(out, "w") as f:
        f.write(json.dumps({"k": "meta", "plan": str(args.plan),
                            "store": str(args.store),
                            "cert_ckpt": "d6-run11/iter-019",
                            "era": "m9-boundary/2f87180cdf",
                            "frame": dict(frame)}) + "\n")
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"minted {frame['minted']}/{len([p for ps in by_game.values() for p in ps])} "
          f"seed labels -> {out}")
    print(f"  frame: {dict(frame)}")


if __name__ == "__main__":
    main()
