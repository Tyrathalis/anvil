"""Forge card-name universe: every Name: line in the fork's cardsfolder,
plus Variant FlavorNames mapped to their canonical name.

Split/DFC/adventure card scripts carry one Name: per face; collecting all of
them means face names resolve directly, which is also how Forge's own CardDb
looks cards up. Universes Within twins (182 cards, e.g. "Greymond, Avacyn's
Stalwart" = "Rick, Steadfast Leader") appear as `Variant:...:FlavorName:` and
resolve to the file's primary Name — decklists cite whichever name was
printed, .dck output always gets the canonical one. Cached per fork commit
(the cardsfolder is part of the pinned engine state).
"""

from __future__ import annotations

import json
import subprocess
import unicodedata

from anvil.pool import CACHE_DIR, CARDSFOLDER, FORGE_DIR


def normalize(name: str) -> str:
    """Match key: casefolded, diacritics stripped, whitespace collapsed."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split()).casefold()


def fork_commit() -> str:
    return subprocess.run(["git", "-C", str(FORGE_DIR), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def parse_card_names(script: str) -> dict[str, str]:
    """card-script text -> {referencable name: canonical name}. Face Name:
    lines map to themselves; FlavorName variants map to the primary Name."""
    names: dict[str, str] = {}
    primary = None
    for line in script.splitlines():
        if line.startswith("Name:"):
            face = line[5:].strip()
            names[face] = face
            if primary is None:
                primary = face
        elif line.startswith("Variant:") and "FlavorName:" in line and primary:
            flavor = line.split("FlavorName:", 1)[1].strip()
            names[flavor] = primary
    return names


def _scan_cardsfolder() -> dict[str, str]:
    names: dict[str, str] = {}
    for path in CARDSFOLDER.rglob("*.txt"):
        names.update(parse_card_names(path.read_text(encoding="utf-8", errors="replace")))
    return names


def load_names() -> dict[str, str]:
    """normalized name -> canonical Forge name, cached per fork commit."""
    commit = fork_commit()
    cache = CACHE_DIR / f"forge-names-v2-{commit[:12]}.json"  # v2: +FlavorName mapping
    if cache.exists():
        names = json.loads(cache.read_text())
    else:
        names = _scan_cardsfolder()
        if len(names) < 10000:
            raise RuntimeError(f"cardsfolder scan found only {len(names)} names at {CARDSFOLDER} — wrong FORGE_DIR?")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(names))
    return {normalize(n): canonical for n, canonical in names.items()}


def resolve(raw: str, universe: dict[str, str], overrides: dict[str, str]) -> str | None:
    """Resolution ladder: override -> exact-normalized -> front face of a
    split/DFC written as 'A // B' or 'A / B'. None = unresolved."""
    if raw in overrides:
        return overrides[raw]
    hit = universe.get(normalize(raw))
    if hit:
        return hit
    for sep in (" // ", " / ", "/"):
        if sep in raw:
            return universe.get(normalize(raw.split(sep)[0]))
    return None
