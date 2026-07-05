"""Tensor assembly v0: observation record -> dense arrays (M1 D1).

The deterministic Python half of ADR-0004's featurization line: Java logs
versioned entity-level records at generation time; this transform turns one
decision record into model-ready arrays. Feature iteration happens HERE (free,
no regeneration); only state-extraction changes touch the Java side. At
inference (D8) the decision server runs this same transform on the
`observation: bytes` payload before the GPU pass.

Information-set enforcement lives here and only here: the record carries full
state (belief-head ground truth, M2); the transform is the gate that keeps
hidden identities away from the policy input. `tests/test_transform.py` holds
the leak test — output for perspective P must be invariant under permutation
and identity-substitution of entities P cannot see.

v0 is the boundary contract, not the full §1/§2 encoder: card identity leaves
as a name list (embedding lookup + fusion is D4); features are the schema's
dynamic fields; multiset dedup (§2) collapses identical entities into one row
plus a count.

Everything Magic-specific keys off vocab_mtg.json (mtg.* namespace); the
envelope handling above it is game-agnostic (§1 hygiene).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

TRANSFORM_VERSION = 0

_VOCAB_PATH = Path(__file__).parent / "vocab_mtg.json"

# entity feature columns (float32), fixed order; see ENTITY_FEATURES
ENTITY_FEATURES = [
    "zone", "controller_is_self", "owner_is_self", "tapped", "sick", "phased",
    "facedown", "damage", "power", "toughness", "has_pt", "token", "attached",
    "attacking", "blocking", "count", "hidden",
]
GLOBAL_FEATURES = [
    "turn", "phase", "active_is_self", "monarch_is_self", "initiative_is_self",
    "day", "night", "stack_size",
]
# per player, self first then opponents in seat order
PLAYER_FEATURES = ["life", "hand_count", "library_count", "lands_played", "mana_total", "lost"]


class VocabError(KeyError):
    """Unknown vocabulary entry — extend vocab_mtg.json, never guess."""


class Vocab:
    def __init__(self, path: Path = _VOCAB_PATH):
        raw = json.loads(path.read_text())
        self.zones: dict[str, int] = {z: i for i, z in enumerate(raw["zones"])}
        self.phases: dict[str, int] = {p: i for i, p in enumerate(raw["phases"])}
        self.mana: list[str] = raw["mana"]

    def zone(self, z: str) -> int:
        try:
            return self.zones[z]
        except KeyError:
            raise VocabError(f"unknown zone {z!r}") from None

    def phase(self, ph: str | None) -> int:
        if ph is None:
            return -1
        try:
            return self.phases[ph]
        except KeyError:
            raise VocabError(f"unknown phase {ph!r}") from None


_DEFAULT_VOCAB: Vocab | None = None


def _vocab() -> Vocab:
    global _DEFAULT_VOCAB
    if _DEFAULT_VOCAB is None:
        _DEFAULT_VOCAB = Vocab()
    return _DEFAULT_VOCAB


def visible_to(ent: dict[str, Any], perspective: int) -> bool:
    """Effective identity visibility: zone default, overridden by 'vis'."""
    vis = ent.get("vis")
    if vis == "all":
        return True
    if vis == "none":
        return False
    if vis == "c":
        return ent["c"] == perspective
    if ent["z"] == "hand":
        return ent["c"] == perspective
    if ent["z"] == "library":
        # Library rows exist only under engine look permission (schema v1
        # amendment, M1 D3) and always carry vis; hidden if one ever doesn't.
        return False
    return not ent.get("fd")


def _dedup_key(ent: dict[str, Any], name: str | None) -> str:
    """Multiset dedup (§2): identical entities -> one token + count.
    Identity-bearing fields only when visible; entity id never participates."""
    keyed = {k: v for k, v in sorted(ent.items()) if k not in ("e", "n", "att", "blk", "atk")}
    keyed["n"] = name
    # attachment/combat references collapse to presence flags for the key
    # (per-target distinctions return with pointer heads, D4+)
    keyed["_att"] = "att" in ent or "attp" in ent
    keyed["_atk"] = "atk" in ent
    keyed["_blk"] = "blk" in ent
    return json.dumps(keyed, sort_keys=True)


def assemble(dec: dict[str, Any], header: dict[str, Any],
             perspective: int | None = None, vocab: Vocab | None = None) -> dict[str, Any]:
    """One decision record -> arrays. perspective defaults to the deciding player."""
    v = vocab or _vocab()
    obs = dec.get("obs")
    if obs is None:
        raise ValueError(f"decision s={dec.get('s')} has no observation (obs:null error record?)")
    if perspective is None:
        perspective = dec["p"]
    if perspective < 0:
        raise ValueError("no perspective: decision record has no deciding player")

    n_players = len(header["players"])
    glob = obs["glob"]

    # --- entities: dedup into (key -> [name, features, count]) ---
    # Rows leave in sorted-key order, NOT record order: record order can encode
    # hidden information (e.g. opponent draw order), and the leak test enforces
    # invariance to it. Order is non-semantic by schema; sets are what §2 wants.
    groups: dict[str, list] = {}
    for ent in obs.get("ents", []):
        vis = visible_to(ent, perspective)
        name = ent["n"] if vis else None
        key = _dedup_key(ent, name)
        if key in groups:
            groups[key][2] += 1
            continue
        pt = ent.get("pt")
        feats = [
            float(v.zone(ent["z"])),
            1.0 if ent["c"] == perspective else 0.0,
            1.0 if ent.get("o", ent["c"]) == perspective else 0.0,
            float(ent.get("tap", 0)),
            float(ent.get("sick", 0)),
            float(ent.get("phz", 0)),
            float(ent.get("fd", 0)),
            float(ent.get("dmg", 0)),
            float(pt[0]) if pt else 0.0,
            float(pt[1]) if pt else 0.0,
            1.0 if pt else 0.0,
            float(ent.get("tok", 0)),
            1.0 if ("att" in ent or "attp" in ent) else 0.0,
            1.0 if "atk" in ent else 0.0,
            1.0 if "blk" in ent else 0.0,
            1.0,  # count, filled below
            0.0 if vis else 1.0,
        ]
        groups[key] = [name, feats, 1]

    names: list[str | None] = []
    rows: list[list[float]] = []
    counts: list[int] = []
    for key in sorted(groups):
        name, feats, count = groups[key]
        feats[ENTITY_FEATURES.index("count")] = float(count)
        names.append(name)
        rows.append(feats)
        counts.append(count)

    entities = (np.array(rows, dtype=np.float32) if rows
                else np.zeros((0, len(ENTITY_FEATURES)), dtype=np.float32))

    # --- globals ---
    globals_vec = np.array([
        float(glob["turn"]),
        float(v.phase(glob.get("ph"))),
        1.0 if glob.get("ap") == perspective else 0.0,
        1.0 if glob.get("mono") == perspective else 0.0,
        1.0 if glob.get("init") == perspective else 0.0,
        1.0 if glob.get("day") == "day" else 0.0,
        1.0 if glob.get("day") == "night" else 0.0,
        float(len(obs.get("stack", []))),
    ], dtype=np.float32)

    # --- players, self first then seat order ---
    seats = [perspective] + [i for i in range(n_players) if i != perspective]
    prows = []
    for i in seats:
        p = obs["players"][i]
        prows.append([
            float(p["life"]),
            float(p["hand"]),
            float(p["lib"]),
            float(p.get("lands", 0)),
            float(sum((p.get("mana") or {}).values())),
            float(p.get("lost", 0)),
        ])
    players = np.array(prows, dtype=np.float32)

    return {
        "transform_version": TRANSFORM_VERSION,
        "schema_version": header["sv"],
        "perspective": perspective,
        "entities": entities,          # (N, len(ENTITY_FEATURES)) float32
        "entity_names": names,         # len N; None = hidden from perspective
        "entity_counts": np.array(counts, dtype=np.int32),
        "globals": globals_vec,
        "players": players,            # (n_players, len(PLAYER_FEATURES)), self first
    }
