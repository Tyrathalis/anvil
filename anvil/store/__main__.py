"""CLI: uv run python -m anvil.store ingest|status|validate ...

  ingest <run-dir> [--dest DIR] [--pool-version V] [--verify]
  status <store-dir>
  validate <store-dir> [--limit N]   # CastPlan label sanity gate (M1 D2)
"""

from __future__ import annotations

import argparse
import sys

from anvil.store.trajectories import TrajectoryStore, ingest, status


def main() -> None:
    ap = argparse.ArgumentParser(prog="anvil.store")
    sub = ap.add_subparsers(dest="verb", required=True)

    p_ingest = sub.add_parser("ingest", help="consolidate a harness run into the store")
    p_ingest.add_argument("run_dir")
    p_ingest.add_argument("--dest", default=None)
    p_ingest.add_argument("--pool-version", default=None)
    p_ingest.add_argument("--verify", action="store_true",
                          help="decode every frame after ingest")

    p_status = sub.add_parser("status", help="summarize a store directory")
    p_status.add_argument("store_dir")

    p_val = sub.add_parser("validate", help="validate CastPlan labels against observations")
    p_val.add_argument("store_dir")
    p_val.add_argument("--limit", type=int, default=None, help="only the first N games")

    a = ap.parse_args()
    if a.verb == "ingest":
        ingest(a.run_dir, a.dest, a.pool_version, a.verify)
    elif a.verb == "validate":
        from anvil.store.castplan import validate
        report = validate(TrajectoryStore(a.store_dir), limit=a.limit)
        print(report.summary())
        sys.exit(0 if report.ok else 1)
    else:
        status(a.store_dir)


if __name__ == "__main__":
    main()
