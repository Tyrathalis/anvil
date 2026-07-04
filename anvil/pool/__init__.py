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
