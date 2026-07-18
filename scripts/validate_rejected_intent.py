"""§6c gate: reconcile reader-derived rejected-intent events against census.

The rejected-intent penalty (d6-vtrace-loop §6c) derives its per-timestep
flags from the store (rejected_events in anvil/training/rl.py). Before any
penalty run trains, this script certifies the derivation against the
generation run's census — the serve-time ground truth the realizer logged:

  priority : derived veto events  vs  census veto lines (bridged, priority)
  attack   : derived dropped attackers  vs  census "dropped" on attack recs
  block    : derived |dropped|+|forced| vs census dropped+forced on block recs

Usage:
  uv run python scripts/validate_rejected_intent.py \
      --store data/trajectories/<store> --run data/runs/<run_dir> [--strict]

--strict exits nonzero on any mismatch (the gate mode); default prints the
reconciliation table for diagnosis.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def derived_counts(store_path: str, stem: str) -> dict:
    from anvil.bridge.featurize import Featurizer, store_wire_hist
    from anvil.store.trajectories import open_store
    from anvil.training.dataset import default_methods
    from anvil.training.rl import rejected_events

    store = open_store(store_path)
    feat = Featurizer(stem, default_methods())
    out = {"priority": 0, "attack": 0, "block": 0, "games": 0, "skipped": 0}
    for g in store.game_indices():
        mu = store.mu_for_game(g)
        if not mu:
            out["skipped"] += 1
            continue
        try:
            traj = store.game(g)
        except Exception as e:  # undecodable frame: census still counted it
            out["skipped"] += 1
            out.setdefault("undecodable", []).append((g, str(e)[:60]))
            continue
        out["games"] += 1
        prior = []
        for dec in traj.decisions:
            rec = mu.get(dec["s"])
            if rec is not None and dec.get("obs") is not None:
                wire = dict(dec)
                wire["hist"] = store_wire_hist(prior, dec["_pos"])
                _ex, aux = feat.example(wire, traj.header, rec["task"])
                n = rejected_events(traj.decisions, len(prior), dec, rec, aux)
                if n and rec["task"] in out:
                    out[rec["task"]] += n
            prior.append(dec)
    return out


def census_counts(run_dir: str) -> dict:
    out = {"priority": 0, "attack": 0, "block": 0}
    for f in glob.glob(f"{run_dir}/workers/inv-*/census.jsonl"):
        for line in open(f):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("by") != "bridge":
                continue
            m = r.get("m")
            if m == "chooseSpellAbilityToPlay" and r.get("veto"):
                out["priority"] += 1
            elif m == "declareAttackers":
                out["attack"] += r.get("dropped", 0)
            elif m == "declareBlockers":
                out["block"] += r.get("dropped", 0) + r.get("forced", 0)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--strict", action="store_true",
                    help="exit nonzero on any mismatch (gate mode)")
    ap.add_argument("--stem", default="data/embeddings/cf2ca6ba-qwen3")
    args = ap.parse_args()

    d = derived_counts(args.store, args.stem)
    c = census_counts(args.run)
    print(f"store: {args.store} ({d['games']} mu-covered games, "
          f"{d['skipped']} skipped)")
    ok = True
    for k in ("priority", "attack", "block"):
        match = d[k] == c[k]
        ok = ok and match
        print(f"  {k:9} derived {d[k]:7}  census {c[k]:7}  "
              f"{'OK' if match else 'MISMATCH'}")
    if args.strict and not ok:
        raise SystemExit(1)
    report = {"store": args.store, "run": args.run,
              "derived": d, "census": c, "match": ok}
    out = Path(args.store) / "rejected_intent_validation.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"report: {out}")


if __name__ == "__main__":
    main()
