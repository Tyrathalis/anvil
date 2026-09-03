#!/usr/bin/env python3
"""ADR-0092 Fork 2: full-support emitter labels — schedule EVERY turn.

The mint's stage-1 read certifies ~19% of witnessed turns (an arm beat
natural by θ). The other ~81% are not "no schedule": natural play DID
cast, in an order, and nothing enumerated beat it. The honest emission
label there is the natural line's realized casts on that witnessed turn,
read from the FROZEN mint store (the retired ADR-0086 own-emission
target as a fixed era asset — non-self-referential, so the ADR-0085
empty fixed point cannot form). Hold only where natural cast nothing.

Per store: labels-full.jsonl = the certified rows of labels.jsonl
(verbatim, src="certified") + one natural row per witnessed-valid READ
turn that was NOT certified (src="natural"; seq = own chosen casts at
priority windows from the emission window onward this turn, as
(entity, sa[:60]) pairs — the seed-label identity the loader rejoins on;
lands included, as in the certified arms and sched_annotate). Rows whose
emission window has no obs are counted and dropped.

Usage:
  uv run python scripts/mint_full_support.py --plan data/runs/sched-mint-20260830
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
    ap.add_argument("--plan", required=True)
    args = ap.parse_args()

    from v2_target_probe import _main1_window  # noqa: E402

    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import SCHED_CAP

    plan = Path(args.plan).resolve()
    manifest = json.loads((plan / "mint-manifest.json").read_text())
    out_pairs = []
    grand = Counter()
    for name, s in manifest["stores"].items():
        sdir = plan / f"store-{name}"
        valid = {(r["g"], r["t"]) for r in map(json.loads, open(sdir / "valid-turns.jsonl"))}
        read_uncert = {
            (r["g"], r["t"])
            for r in map(json.loads, open(sdir / "stage1-perturn.jsonl"))
            if r.get("read") and not r.get("certified")
        } & valid
        cert_rows = []
        meta = None
        for ln in open(sdir / "labels.jsonl"):
            r = json.loads(ln)
            if r.get("k") == "meta":
                meta = r
                continue
            r["src"] = "certified"
            cert_rows.append(r)
        cert_keys = {(r["g"], r["t"]) for r in cert_rows}
        wants: dict[int, set] = {}
        for g, t in read_uncert - cert_keys:
            wants.setdefault(g, set()).add(t)

        ts = TrajectoryStore(Path(s["store"]))
        nat_rows = []
        c = Counter()
        for traj in ts.games(skip_undecodable=True):
            g = traj.header["g"]
            turns = wants.get(g)
            if not turns:
                continue
            players = traj.header.get("players") or []
            seat = next((i for i, pl in enumerate(players)
                         if str(pl.get("name", "")).startswith("Anvil")), 0)
            by_turn: dict[int, list[tuple[int, dict]]] = {}
            for idx, dec in enumerate(traj.decisions):
                if (dec.get("m") == "chooseSpellAbilityToPlay"
                        and dec.get("p") == seat and dec.get("t", 0) >= 1):
                    by_turn.setdefault(dec["t"], []).append((idx, dec))
            for t in sorted(turns):
                wins = by_turn.get(t) or []
                emis = _main1_window([d for _, d in wins], seat)
                if emis is None:
                    c["no_window"] += 1
                    continue
                emis_idx = next(i for i, d in wins if d is emis)
                seq = []
                for idx, dec in wins:
                    if idx < emis_idx:
                        continue
                    oi = dec.get("oi")
                    if not oi or oi <= 0:
                        continue  # PASS / no exact option logged
                    opts = dec.get("opts") or []
                    if oi >= len(opts):
                        c["oi_out_of_range"] += 1
                        continue
                    opt = opts[oi]
                    seq.append([opt.get("e"), str(opt.get("sa") or "")[:60]])
                seq = seq[:SCHED_CAP]
                nat_rows.append({
                    "store": name, "g": g, "t": t, "seat": seat, "arm": -1,
                    "score_mean": None, "seq": seq, "s": emis.get("s"),
                    "src": "natural" if seq else "natural_hold",
                })
                c["natural"] += 1
                c["natural_hold"] += int(not seq)
                c["natural_slots"] += len(seq)
        rows = cert_rows + nat_rows
        out = sdir / "labels-full.jsonl"
        with open(out, "w") as f:
            fm = dict(meta or {})
            fm.update({"k": "meta", "full_support": True,
                       "certified": len(cert_rows), "natural": len(nat_rows),
                       "frame": dict(c)})
            f.write(json.dumps(fm) + "\n")
            for r in rows:
                f.write(json.dumps(r) + "\n")
        lens = Counter(len(r["seq"]) for r in rows)
        n = len(rows)
        print(f"{name}: certified {len(cert_rows)} + natural {len(nat_rows)} "
              f"(holds {c['natural_hold']}, no_window {c['no_window']}) = {n} "
              f"labels; pure_hold {lens[0] / max(n, 1):.1%}, mean len "
              f"{sum(k * v for k, v in lens.items()) / max(n, 1):.2f} -> {out}")
        out_pairs.append({"labels": str(out), "store": s["store"]})
        grand.update({"certified": len(cert_rows), "natural": len(nat_rows)})
    manifest["loader_full"] = {
        "seed_labels": ",".join(p["labels"] for p in out_pairs),
        "seed_store": ",".join(p["store"] for p in out_pairs),
        "total": dict(grand),
    }
    json.dump(manifest, open(plan / "mint-manifest.json", "w"), indent=2)
    print(f"full-support total: {dict(grand)}\n  --seed-labels "
          f"{manifest['loader_full']['seed_labels']}\n  --seed-store "
          f"{manifest['loader_full']['seed_store']}")


if __name__ == "__main__":
    main()
