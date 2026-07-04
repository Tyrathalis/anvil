"""Forge card-name universe: every Name: line in the fork's cardsfolder.

Split/DFC/adventure card scripts carry one Name: per face; collecting all of
them means face names resolve directly, which is also how Forge's own CardDb
looks cards up. Cached per fork commit (the cardsfolder is part of the pinned
engine state).
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


def _scan_cardsfolder() -> list[str]:
    names = set()
    for path in CARDSFOLDER.rglob("*.txt"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Name:"):
                names.add(line[5:].strip())
    return sorted(names)


def load_names() -> dict[str, str]:
    """normalized name -> canonical Forge name, cached per fork commit."""
    commit = fork_commit()
    cache = CACHE_DIR / f"forge-names-{commit[:12]}.json"
    if cache.exists():
        names = json.loads(cache.read_text())
    else:
        names = _scan_cardsfolder()
        if len(names) < 10000:
            raise RuntimeError(f"cardsfolder scan found only {len(names)} names at {CARDSFOLDER} — wrong FORGE_DIR?")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(names))
    return {normalize(n): n for n in names}


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
