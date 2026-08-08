"""Card pool / decklist pipelines (docs/design/dc-pool-pipeline.md).

Two layers per format: acquisition (network, incremental, append-only under
data/pool/<fmt>/raw/) and derivation (offline, deterministic: raw -> pool
manifest + .dck files + report). The manifest content hash is the pool
version. Format-specific fetch/decklist/build logic lives in sibling
subpackages (anvil.pool.dc, anvil.pool.pauper); this module holds the
surface shared across formats: Forge paths, name resolution (forge_db), and
the per-format CURRENT-pin/manifest/install-verification helpers everything
else (encoder, harness, visualizer) goes through.

Two formats can be fetched/built/installed independently and coexist: each
gets its own data/pool/<fmt>/ directory, its own CURRENT pin, and its own
Forge user-deck install subdir, so two operators (or one operator on two
tracks) never clobber each other's pool state. format="dc" is the default
everywhere for backward compatibility — the M1-M6 track's pool keeps living
directly under data/pool/ (no migration), unlike pauper and any later format
which nest under data/pool/<fmt>/.
"""

from __future__ import annotations

import os
from pathlib import Path

FORGE_DIR = Path(os.environ.get("FORGE_DIR", Path.home() / "Everything/Projects/forge"))
CARDSFOLDER = FORGE_DIR / "forge-gui/res/cardsfolder"

FORGE_USER_DIR = Path(os.environ.get("FORGE_USER_DIR", Path.home() / ".forge"))

# per-format Forge deck-store subdir: DC decks are Commander-zone decks,
# Pauper decks are ordinary constructed decks with a real sideboard.
FORGE_DECKS_SUBDIR = {"dc": "decks/commander", "pauper": "decks/constructed"}

# data/pool/ itself IS the dc pool dir (pre-existing, un-migrated: M6 is
# live on this pin). Every other format nests under data/pool/<fmt>/.
_POOL_ROOT = Path(os.environ.get("ANVIL_POOL_DIR", Path(__file__).parents[2] / "data/pool"))


def pool_dir(format: str = "dc") -> Path:
    # dc reads the live module global (not a frozen copy) so tests can
    # monkeypatch anvil.pool.POOL_DIR the same way they always have.
    return globals()["POOL_DIR"] if format == "dc" else _POOL_ROOT / format


def forge_user_decks(format: str = "dc") -> Path:
    return FORGE_USER_DIR / FORGE_DECKS_SUBDIR[format]


# --- back-compat bare constants (format="dc"); new code should prefer the
# pool_dir(format)-relative paths above via anvil.pool.dc/pauper.
POOL_DIR = _POOL_ROOT
RAW_DIR = POOL_DIR / "raw"
RAW_DECKS_DIR = RAW_DIR / "decks"
CACHE_DIR = POOL_DIR / "cache"
DECKS_OUT_DIR = POOL_DIR / "decks"
FLEX_FILE = POOL_DIR / "flex.txt"
OVERRIDES_FILE = POOL_DIR / "overrides.json"
FORGE_USER_DECKS = forge_user_decks("dc")


def current_manifest_path(format: str = "dc") -> Path:
    """The ACTIVE pool manifest for `format`, resolved through its
    data/pool/<fmt>/CURRENT pin (one line: the pool version; written by
    `anvil.pool <fmt> build`).

    Selection was newest-mtime until 2026-08-03 (the M3 standing hazard): a
    checkout, backup restore, or stray touch could silently repoint game
    generation at a stale pool and stamp its version into run provenance —
    final_read included. A dangling or missing pin fails loudly instead.
    """
    import sys

    pdir = pool_dir(format)
    current = pdir / "CURRENT"
    if not current.exists():
        sys.exit(
            f"{current} missing — pin the active pool with "
            f"`python -m anvil.pool --format {format} build`, or write "
            f"its version (e.g. cf2ca6ba) there by hand"
        )
    version = current.read_text().strip()
    manifest = pdir / f"pool-{version}.json"
    if not manifest.exists():
        sys.exit(f"{current} pins {version!r} but {manifest.name} does not exist under {pdir}")
    return manifest


def current_manifest(format: str = "dc") -> dict:
    import json

    return json.loads(current_manifest_path(format).read_text())


def verify_installed_decks(deck_files, decks_out_dir=None, installed_dir=None, format: str = "dc"):
    """Hash-compare installed pool decks against their built sources.

    The playable build's GUI shares the Forge user deck store the research
    worker resolves decks from by name, so a GUI edit/rename would silently
    change future game generation; the pool_version pin covers the manifest,
    not the installed file contents. Returns a list of problem strings
    (empty = clean).
    """
    import hashlib

    decks_out_dir = Path(decks_out_dir) if decks_out_dir else pool_dir(format) / "decks"
    installed_dir = Path(installed_dir) if installed_dir else forge_user_decks(format)
    problems = []
    for name in deck_files:
        src = decks_out_dir / name
        installed = installed_dir / name
        if not src.exists():
            problems.append(f"{name}: missing from {decks_out_dir}")
        elif not installed.exists():
            problems.append(f"{name}: not installed in {installed_dir}")
        elif (
            hashlib.sha256(installed.read_bytes()).hexdigest()
            != hashlib.sha256(src.read_bytes()).hexdigest()
        ):
            problems.append(f"{name}: installed copy differs from pool source")
    return problems
