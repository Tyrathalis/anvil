"""CLI: uv run python -m anvil.store ingest|status ...

  ingest <run-dir> [--dest DIR] [--pool-version V] [--verify]
  status <store-dir>
"""

from __future__ import annotations

import argparse

from anvil.store.trajectories import ingest, status


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

    a = ap.parse_args()
    if a.verb == "ingest":
        ingest(a.run_dir, a.dest, a.pool_version, a.verify)
    else:
        status(a.store_dir)


if __name__ == "__main__":
    main()
