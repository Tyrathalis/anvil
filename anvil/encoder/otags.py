"""Scryfall Tagger functional-tag support for Anvil embeddings (design §1).

Builds a per-pool card -> functional-tags index by querying Scryfall search with
`otag:<tag>` for a curated functional taxonomy. Tags are frequency-cleared
(drop tags matching too few pool cards) and returned as a multi-hot matrix.

The public Scryfall API has no tag-list endpoint, so we ship a curated candidate
list and discover which tags actually hit the pool. Results are cached under
`data/otags/` keyed by pool version and content hash, so the expensive fetch
only runs once per pool/taxonomy.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).parents[2]
OTAG_DIR = REPO / "data" / "otags"
SCRYFALL_DELAY = 0.12  # Scryfall asks ~100ms between requests

# Curated functional-tag candidate list. These are Scryfall Tagger tags that
# describe *what a card does* in a deck, independent of raw stats. The list is
# intentionally broad; frequency clearing keeps only the informative ones for the
# current pool.
DEFAULT_TAG_CANDIDATES = [
    # mana / ramp
    "ramp", "mana-rock", "mana-dork", "mana-fixing", "ritual",
    # card advantage / selection
    "card-draw", "tutor", "card-selection", "looting", "rummaging", "cantrip",
    # interaction
    "removal", "single-target-removal", "board-wipe", "edict", "bounce",
    "counterspell", "discard", "hate",
    # combat keywords / abilities
    "evasion", "flying", "trample", "menace", "deathtouch", "lifelink",
    "first-strike", "double-strike", "haste", "vigilance", "hexproof",
    "indestructible", "ward", "reach", "shadow",
    # graveyard
    "recursion", "reanimation", "self-mill", "dredge", "flashback",
    # tokens / creatures
    "token", "token-generation", "go-wide", "anthem", "lord",
    # life / damage
    "lifegain", "lifedrain", "burn", "direct-damage", "ping",
    # tempo / protection / utility
    "blink", "flicker", "blink-enabler", "stax", "lock", "prison",
    "tapped-land-matters", "untap", "extra-turn", "copy",
    # combo / archetype
    "combo-piece", "storm", "cascade", "surveil", "investigate", "blood",
    "connive", "cycling", "suspend", "kicker", "convoke", "retrace",
    # role / macro type
    "commander", "commander-tutor", "commander-protection", "hatebear",
    "draw-go", "control", "aggro", "midrange", "ramp-payoff",
]


def _otag_stem(manifest: dict, tags: list[str]) -> str:
    """Deterministic cache name: pool version + hash of tag list."""
    tag_hash = hashlib.sha256(",".join(sorted(tags)).encode()).hexdigest()[:12]
    return f"{manifest['pool_version']}-otags-{tag_hash}"


def _scryfall_search(q: str) -> list[dict[str, Any]]:
    """Paginated Scryfall search, sleeping between requests."""
    cards: list[dict[str, Any]] = []
    page = 1
    while True:
        params = urllib.parse.urlencode({
            "q": q, "format": "json", "unique": "cards", "page": page
        })
        url = f"https://api.scryfall.com/cards/search?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "anvil/0.0.1",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Scryfall query failed ({e.code}): {q}") from e
        cards.extend(data.get("data", []))
        if data.get("has_more") and data.get("next_page"):
            page += 1
            time.sleep(SCRYFALL_DELAY)
        else:
            break
    return cards


def _canonical_pool_names(manifest: dict) -> set[str]:
    return {name for name in manifest["pool"]}


def build_otag_index(
    manifest: dict,
    tags: list[str] | None = None,
    min_cards: int = 5,
    top_k: int | None = 64,
    cache: Path | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Return {names: [...], tag_vocab: [...], card_tags: {name: [tag, ...]}}.

    Frequency clearing:
      - drop tags that hit fewer than `min_cards` pool cards
      - if `top_k` is set, keep only the top-K most frequent tags

    Cached results are loaded when available and when the tag list matches.
    """
    tags = list(tags or DEFAULT_TAG_CANDIDATES)
    cache = cache or OTAG_DIR / f"{_otag_stem(manifest, tags)}.json"
    if cache.exists():
        if verbose:
            print(f"[otags] loading cached index from {cache}")
        return json.loads(cache.read_text())

    pool_names = _canonical_pool_names(manifest)
    pool_lower = {n.lower(): n for n in pool_names}
    tag_hits: dict[str, set[str]] = {}

    if verbose:
        print(f"[otags] querying Scryfall for {len(tags)} tag candidates...")
    for tag in tags:
        try:
            cards = _scryfall_search(f"otag:{tag}")
        except RuntimeError as e:
            if verbose:
                print(f"[otags] warning: tag '{tag}' query failed: {e}")
            continue
        hits: set[str] = set()
        for c in cards:
            for face in c.get("card_faces") or [c]:
                name = face.get("name") or c.get("name")
                if name and name.lower() in pool_lower:
                    hits.add(pool_lower[name.lower()])
        if len(hits) >= min_cards:
            tag_hits[tag] = hits
        if verbose:
            print(f"[otags]   {tag}: {len(hits)} pool cards")

    # frequency-clear to top_k
    if top_k is not None and len(tag_hits) > top_k:
        by_freq = sorted(tag_hits.items(), key=lambda kv: -len(kv[1]))
        tag_hits = dict(by_freq[:top_k])
        if verbose:
            print(f"[otags] frequency-cleared to top {top_k} tags")

    # invert to card -> tags
    card_tags: dict[str, list[str]] = {n: [] for n in pool_names}
    for tag, hits in tag_hits.items():
        for name in hits:
            card_tags[name].append(tag)

    # sort vocab and per-card tags for stable ordering
    vocab = sorted(tag_hits.keys())
    card_tags = {n: sorted(ts) for n, ts in card_tags.items()}

    covered = sum(1 for ts in card_tags.values() if ts)
    if verbose:
        print(f"[otags] {len(vocab)} tags cover {covered}/{len(pool_names)} cards")

    index = {
        "pool_version": manifest["pool_version"],
        "tag_candidates": tags,
        "min_cards": min_cards,
        "top_k": top_k,
        "names": sorted(pool_names),
        "tag_vocab": vocab,
        "card_tags": card_tags,
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(index, indent=1) + "\n")
    if verbose:
        print(f"[otags] cached index -> {cache}")
    return index


def tag_text_for_card(card_tags: list[str]) -> str:
    """Appendable text fragment for embedding input."""
    if not card_tags:
        return ""
    return "\nFunctional tags: " + ", ".join(card_tags)


def multi_hot_matrix(names: list[str], index: dict[str, Any]) -> "numpy.ndarray":
    """Return (len(names), len(vocab)) float32 multi-hot matrix aligned to names."""
    import numpy as np

    vocab = {t: i for i, t in enumerate(index["tag_vocab"])}
    mat = np.zeros((len(names), len(vocab)), dtype="float32")
    card_tags = index["card_tags"]
    for r, name in enumerate(names):
        for t in card_tags.get(name, []):
            if t in vocab:
                mat[r, vocab[t]] = 1.0
    return mat


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--min-cards", type=int, default=5)
    ap.add_argument("--top-k", type=int, default=64)
    a = ap.parse_args()

    manifest = json.loads(a.manifest.read_text())
    idx = build_otag_index(manifest, min_cards=a.min_cards, top_k=a.top_k)
    print(json.dumps({
        "vocab_size": len(idx["tag_vocab"]),
        "covered": sum(1 for ts in idx["card_tags"].values() if ts),
        "total": len(idx["names"]),
        "top_tags": sorted(idx["tag_vocab"])[:20],
    }, indent=1))
