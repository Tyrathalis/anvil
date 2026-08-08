"""CLI (docs/design/dc-pool-pipeline.md):

  python -m anvil.pool [--format dc|pauper] fetch [--since YYYY-MM] [--limit-decks N]
  python -m anvil.pool [--format dc|pauper] banlist
  python -m anvil.pool [--format dc|pauper] build
  python -m anvil.pool [--format dc|pauper] install
  python -m anvil.pool [--format dc|pauper] status

--format defaults to dc (the original, un-migrated pool at data/pool/). Both
formats have independent CURRENT pins and Forge deck-store subdirs (DC ->
decks/commander/, Pauper -> decks/constructed/), so they can be fetched,
built, and installed side by side without conflicting.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys

from anvil.pool import forge_user_decks, pool_dir


def main() -> None:
    p = argparse.ArgumentParser(prog="anvil.pool")
    p.add_argument("--format", choices=["dc", "pauper"], default="dc")
    sub = p.add_subparsers(dest="verb", required=True)
    f = sub.add_parser("fetch", help="fetch new decklists from mtgtop8")
    f.add_argument("--since", help="skip events before YYYY-MM(-DD)")
    f.add_argument("--limit-decks", type=int, help="stop after N new decks")
    sub.add_parser("banlist", help="snapshot the current banlist")
    sub.add_parser("build", help="derive pool manifest + .dck files from raw")
    sub.add_parser("install", help="copy built .dck files into the Forge profile")
    sub.add_parser("status", help="raw/built state summary")
    a = p.parse_args()

    pool_pkg = f"anvil.pool.{a.format}"
    POOL_DIR = pool_dir(a.format)
    DECKS_OUT_DIR = POOL_DIR / "decks"
    FORGE_USER_DECKS = forge_user_decks(a.format)
    RAW_DECKS_DIR = POOL_DIR / "raw" / "decks"

    if a.verb == "fetch":
        import importlib

        fetch_decks = importlib.import_module(f"{pool_pkg}.fetch").fetch_decks
        print(json.dumps(fetch_decks(since=a.since, limit_decks=a.limit_decks), indent=2))
    elif a.verb == "banlist":
        import importlib

        fetch_banlist = importlib.import_module(f"{pool_pkg}.fetch").fetch_banlist
        print(json.dumps(fetch_banlist(), indent=2))
    elif a.verb == "build":
        import importlib

        build = importlib.import_module(f"{pool_pkg}.build").build
        print(json.dumps(build(), indent=2))
    elif a.verb == "install":
        dcks = sorted(DECKS_OUT_DIR.glob("*.dck"))
        if not dcks:
            sys.exit(f"nothing built — run `python -m anvil.pool --format {a.format} build` first")
        FORGE_USER_DECKS.mkdir(parents=True, exist_ok=True)
        for d in dcks:
            shutil.copy2(d, FORGE_USER_DECKS / d.name)
        print(f"installed {len(dcks)} decks -> {FORGE_USER_DECKS}")
    elif a.verb == "status":
        raws = len(list(RAW_DECKS_DIR.glob("*.txt"))) if RAW_DECKS_DIR.exists() else 0
        manifests = sorted(POOL_DIR.glob("pool-*.json"))
        print(f"format: {a.format}")
        print(f"raw decks: {raws}")
        print(f"banlist snapshots: {len(list((POOL_DIR / 'raw').glob('banlist-*.json')))}")
        print(f"manifests built: {len(manifests)}")
        current = POOL_DIR / "CURRENT"
        if current.exists():
            from anvil.pool import current_manifest

            m = current_manifest(a.format)
            print(f"ACTIVE ({current}): pool-{m['pool_version']} — {m['counts']}")
        else:
            print(
                f"no CURRENT pin — run `python -m anvil.pool --format {a.format} build` or "
                f"write a version to {current}"
            )


if __name__ == "__main__":
    main()
