"""Oracle-tag functional features (M6 exploratory probe, 2026-08-08).

Motivated by an outside-builder observation (talor, Discord): embedding
card text alone under-clusters FUNCTION — Basalt Monolith files under
"untap" until curated oracle tags pull it to "artifact ramp/combo". Our
card encoder (ADR-0007) embeds oracle text; if function is what the
representation is missing, positions' functional composition (outs in
hand, deployed interaction) may carry live-vs-dead signal the trunk
cannot see. B-1's negative does not predict this probe: B-1 features were
arithmetic derivable from state the trunk observes; oracle tags inject
EXTERNAL curated knowledge. The reconstruction-R² read distinguishes
"[STATE] already encodes function" from "function is genuinely new".

Same discipline as anvil.encoder.derived: transform-side from the logged
obs, info-set-respecting via `visible_to` (a hidden card contributes no
tags), per-count conditioning clip at birth (standing rule, ADR-0043).

Tag source: Scryfall oracle-tag search (scripts/otag_probe.py fetch —
official API, per-tag `otag:` queries intersected with the pool). GROUPS
maps candidate tag names to ~10 functional groups; the fetch records
which tags resolve, and group membership is the union of its resolved
tags' card lists.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from anvil.encoder.transform import visible_to

OTAG_VERSION = 1
COUNT_CAP = 20.0  # conditioning clip (counts are zone-bounded, belt anyway)

# functional group -> candidate Scryfall oracle tags (fetch validates;
# unknown tags are recorded and skipped, membership = union of survivors)
GROUPS: dict[str, list[str]] = {
    "removal": ["removal", "creature-removal", "spot-removal"],
    "wipe": ["boardwipe", "sweeper", "mass-removal"],
    "counter": ["counterspell", "counter"],
    "ramp": ["ramp", "mana-rock", "mana-dork", "ritual"],
    "tutor": ["tutor", "search"],
    "draw": ["draw", "card-draw", "cantrip", "card-advantage"],
    "recursion": ["recursion", "reanimate", "reanimation", "regrowth"],
    "protection": ["protection", "counterspell-protection", "hexproof"],
    "combo": ["combo-piece", "infinite-combo", "untapper", "cost-reducer", "storm"],
    "wincon": ["win-condition", "extra-turn", "extra-combat", "burn", "lifedrain"],
}

_ZONES = ("hand_self", "bf_self", "bf_opp")
FEATURE_NAMES = [f"otag_{z}_{g}" for z in _ZONES for g in GROUPS]
# per-family attribution: the self-hand block (outs) vs own board vs
# opponent board — three distinct hypotheses about where function matters
FAMILY_OF = {
    f"otag_{z}_{g}": {"hand_self": "ohand", "bf_self": "obfself", "bf_opp": "obfopp"}[z]
    for z in _ZONES
    for g in GROUPS
}
FAMILIES = ["ohand", "obfself", "obfopp"]


def otag_features(
    dec: dict[str, Any],
    header: dict[str, Any],
    perspective: int,
    groups_of: Mapping[str, frozenset[str]],
) -> np.ndarray:
    """One decision record -> (len(FEATURE_NAMES),) float32.
    groups_of: card name -> set of group keys (from the fetched tag table);
    a name absent from the mapping contributes nothing."""
    obs = dec.get("obs")
    if obs is None:
        raise ValueError(f"decision s={dec.get('s')} has no observation")
    players = obs["players"]
    n = len(header["players"])
    opps = {i for i in range(n) if i != perspective and not players[i].get("lost")}
    if not opps:
        opps = {i for i in range(n) if i != perspective}

    counts = {(z, g): 0.0 for z in _ZONES for g in GROUPS}
    for ent in obs.get("ents", []):
        if ent.get("phz"):
            continue
        if not visible_to(ent, perspective):
            continue
        gs = groups_of.get(ent["n"])
        if not gs:
            continue
        z, c = ent["z"], ent["c"]
        if z == "hand" and c == perspective:
            zone = "hand_self"
        elif z == "battlefield" and c == perspective:
            zone = "bf_self"
        elif z == "battlefield" and c in opps:
            zone = "bf_opp"
        else:
            continue
        for g in gs:
            counts[(zone, g)] += 1.0

    return np.array(
        [min(counts[(z, g)], COUNT_CAP) for z in _ZONES for g in GROUPS], dtype=np.float32
    )
