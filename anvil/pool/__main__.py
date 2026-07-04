"""CLI (docs/design/dc-pool-pipeline.md):

  python -m anvil.pool fetch [--since YYYY-MM] [--limit-decks N]
  python -m anvil.pool banlist
  python -m anvil.pool build
  python -m anvil.pool install
  python -m anvil.pool status
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys

from anvil.pool import DECKS_OUT_DIR, FORGE_USER_DECKS, POOL_DIR, RAW_DECKS_DIR


def main() -> None:
    p = argparse.ArgumentParser(prog="anvil.pool")
    sub = p.add_subparsers(dest="verb", required=True)
    f = sub.add_parser("fetch", help="fetch new DC decklists from mtgtop8")
    f.add_argument("--since", help="skip events before YYYY-MM(-DD)")
    f.add_argument("--limit-decks", type=int, help="stop after N new decks")
    sub.add_parser("banlist", help="snapshot the current DC banlist")
    sub.add_parser("build", help="derive pool manifest + .dck files from raw")
    sub.add_parser("install", help="copy built .dck files into the Forge profile")
    sub.add_parser("status", help="raw/built state summary")
    a = p.parse_args()

    if a.verb == "fetch":
        from anvil.pool.fetch import fetch_decks
        print(json.dumps(fetch_decks(since=a.since, limit_decks=a.limit_decks), indent=2))
    elif a.verb == "banlist":
        from anvil.pool.fetch import fetch_banlist
        print(json.dumps(fetch_banlist(), indent=2))
    elif a.verb == "build":
        from anvil.pool.build import build
        print(json.dumps(build(), indent=2))
    elif a.verb == "install":
        dcks = sorted(DECKS_OUT_DIR.glob("*.dck"))
        if not dcks:
            sys.exit("nothing built — run `python -m anvil.pool build` first")
        FORGE_USER_DECKS.mkdir(parents=True, exist_ok=True)
        for d in dcks:
            shutil.copy2(d, FORGE_USER_DECKS / d.name)
        print(f"installed {len(dcks)} decks -> {FORGE_USER_DECKS}")
    elif a.verb == "status":
        raws = len(list(RAW_DECKS_DIR.glob("*.txt"))) if RAW_DECKS_DIR.exists() else 0
        manifests = sorted(POOL_DIR.glob("pool-*.json"))
        print(f"raw decks: {raws}")
        print(f"banlist snapshots: {len(list(POOL_DIR.glob('raw/banlist-*.json')))}")
        if manifests:
            m = json.loads(manifests[-1].read_text())
            print(f"latest manifest: {manifests[-1].name} — {m['counts']}")
        else:
            print("no manifest built yet")


if __name__ == "__main__":
    main()
