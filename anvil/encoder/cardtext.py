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


# ---- structured card features (§1: pips, types, P/T — static per card) ----

FEATURE_TYPES = ["Land", "Creature", "Artifact", "Enchantment", "Instant",
                 "Sorcery", "Planeswalker", "Battle", "Legendary", "Snow"]
CARD_FEATURES = (["pip_w", "pip_u", "pip_b", "pip_r", "pip_g", "pip_c",
                  "generic", "has_x", "cmc"]
                 + [f"type_{t.lower()}" for t in FEATURE_TYPES]
                 + ["power", "toughness", "has_pt", "loyalty", "has_loyalty", "n_faces"])


def face_features(faces: list[dict]) -> list[float]:
    """First-face cost/types/PT (the castable identity), n_faces for the rest;
    the text embedding carries full multi-face semantics."""
    f = faces[0]
    pips = {c: 0.0 for c in "WUBRGC"}
    generic = 0.0
    has_x = 0.0
    for tok in (f.get("cost") or "").split():
        if tok == "no" or tok == "cost":
            continue
        if tok.isdigit():
            generic += int(tok)
        elif tok == "X":
            has_x = 1.0
        else:
            for ch in tok:
                if ch in pips:
                    pips[ch] += 1.0
    cmc = generic + sum(pips.values())
    types = f.get("types", "")
    pt = (f.get("pt") or "").split("/")
    power, tough, has_pt = 0.0, 0.0, 0.0
    if len(pt) == 2:
        has_pt = 1.0
        power = float(pt[0]) if pt[0].lstrip("+-").isdigit() else 0.0
        tough = float(pt[1]) if pt[1].lstrip("+-").isdigit() else 0.0
    loyalty = f.get("loyalty", "")
    return ([pips[c] for c in "WUBRGC"] + [generic, has_x, cmc]
            + [1.0 if t in types else 0.0 for t in FEATURE_TYPES]
            + [power, tough, has_pt,
               float(loyalty) if loyalty.isdigit() else 0.0,
               1.0 if loyalty else 0.0, float(len(faces))])


def pool_features(manifest: dict, names: list[str]):
    """Feature matrix aligned to the embedding-cache name order."""
    import numpy as np
    files = _scan_files()
    rows = []
    for name in names:
        with open(files[normalize(name)], encoding="utf-8", errors="replace") as f:
            rows.append(face_features(parse_faces(f.read())))
    return np.asarray(rows, dtype="float32")
