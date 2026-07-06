"""Card text for the embedding cache (M1 D4, m1-bc-plan decision 5).

Extracts name / mana cost / type line / P-T / loyalty / oracle text for every
pool card from the fork's cardsfolder (the pinned engine state — same source
of truth the games were played with), and renders the instruction-formatted
text the embedding model sees. Multi-face scripts (ALTERNATE sections: MDFC,
split, adventure, flip) contribute every face to one text — the pool indexes
cards by canonical/face name, the embedding sees the whole object.

Pure extraction, no torch: the embed CLI (anvil/encoder/__main__.py) imports
this and does the GPU pass.
"""

from __future__ import annotations

import json

from anvil.pool import CACHE_DIR, CARDSFOLDER
from anvil.pool.forge_db import fork_commit, normalize


def parse_faces(script: str) -> list[dict]:
    """Card-script text -> one dict per face (ALTERNATE-separated)."""
    faces = []
    for chunk in script.replace("\r\n", "\n").split("\nALTERNATE\n"):
        face: dict = {}
        for line in chunk.splitlines():
            for key, field in (("Name:", "name"), ("ManaCost:", "cost"),
                               ("Types:", "types"), ("PT:", "pt"),
                               ("Loyalty:", "loyalty"), ("Oracle:", "oracle")):
                if line.startswith(key):
                    face[field] = line[len(key):].strip()
        if face.get("name"):
            faces.append(face)
    return faces


def _brace_cost(cost: str) -> str:
    """Forge 'ManaCost:1 B' -> '{1}{B}'; 'no cost' stays as written."""
    if not cost or cost == "no cost":
        return "no cost"
    return "".join(f"{{{tok}}}" for tok in cost.split())


def render(faces: list[dict]) -> str:
    """The exact text the embedding model sees for one card."""
    parts = []
    for f in faces:
        lines = [f"Name: {f['name']}"]
        if f.get("cost"):
            lines.append(f"Cost: {_brace_cost(f['cost'])}")
        if f.get("types"):
            lines.append(f"Type: {f['types']}")
        if f.get("pt"):
            lines.append(f"Power/Toughness: {f['pt']}")
        if f.get("loyalty"):
            lines.append(f"Loyalty: {f['loyalty']}")
        oracle = f.get("oracle", "").replace("\\n", "\n")
        if oracle:
            lines.append(f"Text: {oracle}")
        parts.append("\n".join(lines))
    return "\n--- other face ---\n".join(parts)


def _scan_files() -> dict[str, str]:
    """normalized face/primary name -> script path (str), cached per commit."""
    commit = fork_commit()
    cache = CACHE_DIR / f"forge-files-v1-{commit[:12]}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    index: dict[str, str] = {}
    for path in CARDSFOLDER.rglob("*.txt"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for face in parse_faces(text):
            index.setdefault(normalize(face["name"]), str(path))
    if len(index) < 10000:
        raise RuntimeError(f"cardsfolder scan found only {len(index)} faces — wrong FORGE_DIR?")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(index))
    return index


def pool_texts(manifest: dict) -> dict[str, str]:
    """pool manifest -> {canonical pool name: embedding text}, loud on gaps."""
    files = _scan_files()
    out: dict[str, str] = {}
    missing = []
    for name in sorted(manifest["pool"]):
        path = files.get(normalize(name))
        if path is None:
            missing.append(name)
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            out[name] = render(parse_faces(f.read()))
    if missing:
        raise RuntimeError(f"{len(missing)} pool cards have no cardsfolder script "
                           f"(pool/fork mismatch?): {missing[:5]}")
    return out
