"""DC card pool / decklist pipeline (docs/design/dc-pool-pipeline.md).

Two layers: acquisition (network, incremental, append-only under
data/pool/raw/) and derivation (offline, deterministic: raw -> pool manifest
+ .dck files + report). The manifest content hash is the pool version.
"""

from __future__ import annotations

import os
from pathlib import Path

FORGE_DIR = Path(os.environ.get("FORGE_DIR", Path.home() / "Everything/Projects/forge"))
CARDSFOLDER = FORGE_DIR / "forge-gui/res/cardsfolder"
FORGE_USER_DECKS = Path(os.environ.get("FORGE_USER_DIR", Path.home() / ".forge")) / "decks/commander"

POOL_DIR = Path(os.environ.get("ANVIL_POOL_DIR", Path(__file__).parents[2] / "data/pool"))
RAW_DIR = POOL_DIR / "raw"
RAW_DECKS_DIR = RAW_DIR / "decks"
CACHE_DIR = POOL_DIR / "cache"
DECKS_OUT_DIR = POOL_DIR / "decks"
FLEX_FILE = POOL_DIR / "flex.txt"
OVERRIDES_FILE = POOL_DIR / "overrides.json"


def current_manifest_path() -> Path:
    """The ACTIVE pool manifest, resolved through the data/pool/CURRENT pin
    (one line: the pool version; written by `anvil.pool build`).

    Selection was newest-mtime until 2026-08-03 (the M3 standing hazard): a
    checkout, backup restore, or stray touch could silently repoint game
    generation at a stale pool and stamp its version into run provenance —
    final_read included. A dangling or missing pin fails loudly instead.
    """
    import sys
    current = POOL_DIR / "CURRENT"
    if not current.exists():
        sys.exit(f"{current} missing — pin the active pool with "
                 f"`python -m anvil.pool build`, or write its version "
                 f"(e.g. cf2ca6ba) there by hand")
    version = current.read_text().strip()
    manifest = POOL_DIR / f"pool-{version}.json"
    if not manifest.exists():
        sys.exit(f"{current} pins {version!r} but {manifest.name} does not "
                 f"exist under {POOL_DIR}")
    return manifest


def current_manifest() -> dict:
    import json
    return json.loads(current_manifest_path().read_text())


def verify_installed_decks(deck_files, decks_out_dir=None, installed_dir=None):
    """Hash-compare installed pool decks against their built sources.

    The playable build's GUI shares the Forge user deck store the research
    worker resolves decks from by name, so a GUI edit/rename would silently
    change future game generation; the pool_version pin covers the manifest,
    not the installed file contents. Returns a list of problem strings
    (empty = clean).
    """
    import hashlib

    decks_out_dir = Path(decks_out_dir) if decks_out_dir else DECKS_OUT_DIR
    installed_dir = Path(installed_dir) if installed_dir else FORGE_USER_DECKS
    problems = []
    for name in deck_files:
        src = decks_out_dir / name
        installed = installed_dir / name
        if not src.exists():
            problems.append(f"{name}: missing from {decks_out_dir}")
        elif not installed.exists():
            problems.append(f"{name}: not installed in {installed_dir}")
        elif (hashlib.sha256(installed.read_bytes()).hexdigest()
                != hashlib.sha256(src.read_bytes()).hexdigest()):
            problems.append(f"{name}: installed copy differs from pool source")
    return problems
