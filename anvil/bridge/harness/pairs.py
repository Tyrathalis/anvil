"""Deterministic deck-pair schedule over the pool (census-driver pattern).

Decks sorted by filename, seeded shuffle passes, consecutive pairing;
repeated passes until the requested pair count is met, so every deck appears
with near-uniform frequency (an odd deck count drops one random deck per
pass — harmless across many passes). The schedule is a pure function of
(deck list, n_pairs, seed): run manifests pin all three, and the worker maps
game index -> pair via (index // games_per_pair) % n_pairs.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from anvil.pool import POOL_DIR


def latest_pool_manifest() -> dict:
    manifests = sorted(POOL_DIR.glob("pool-*.json"), key=lambda p: p.stat().st_mtime)
    if not manifests:
        sys.exit("no pool manifest under data/pool/ — run `python -m anvil.pool build` first")
    return json.loads(manifests[-1].read_text())


def pair_schedule(deck_files: list[str], n_pairs: int, seed: int) -> list[tuple[str, str]]:
    if len(deck_files) < 2:
        sys.exit("need at least 2 decks to schedule pairs")
    pairs: list[tuple[str, str]] = []
    rng = random.Random(seed)
    while len(pairs) < n_pairs:
        order = sorted(deck_files)
        rng.shuffle(order)
        it = iter(order)
        pairs.extend(zip(it, it))
    return pairs[:n_pairs]


def write_pairs_file(path: Path, pairs: list[tuple[str, str]]) -> None:
    # Tab-separated: deck names contain spaces and brackets.
    path.write_text("".join(f"{a}\t{b}\n" for a, b in pairs))
