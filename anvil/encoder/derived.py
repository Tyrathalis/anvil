"""Derived-state features (M6 D2-B lever B-1, ADR-0042).

State-level arithmetic the frozen trunk provably lacks (ADR-0041: ranking
plateau 0.43-0.46 vs 0.94-0.97 achievable; ADR-0036: the residual is
winnable-labeled-dead, global). Five families per ADR-0042 decision 1:
race/lethality margins, turns-to-death clock, castability-vs-mana,
material/card-advantage differentials, commander-zone/tax state.

Transform-side by construction (observation-schema-v1 decision 2: full-state
records, feature iteration never regenerates the corpus): computed from one
logged `dec` record at read time, and from the identical live obs bytes at
serve time — no dataset boundary, no fork delta. The loader-parity test
extends to these features when they enter the model feed (ADR-0042
decision 4).

Info-set discipline matches anvil.encoder.transform: card identity
contributes only where `visible_to(ent, perspective)` grants it — a hidden
entity is a count, never a name. The leak invariant (output invariant under
identity-substitution of invisible entities) is tested in
tests/test_derived.py.

Card statics (cmc / is-land / has-X) come from the pinned fork's cardsfolder
via anvil.encoder.cardtext — the same source of truth the games were played
with. Lookup misses (tokens, emblems) degrade gracefully: an unknown name is
excluded from castability and land counts (creatures never need statics —
`pt` presence is the currently-a-creature signal, animated manlands and
tokens included).

Known proxies, recorded deliberately (probe first, refine only if the family
carries signal): mana available = untapped battlefield lands + floating
pool (ignores rocks/dorks/Treasure — statics misses undercount); castability
is cmc-vs-mana only (no color-pip feasibility — land-produced colors are
oracle-text knowledge); per-turn damage = total board power (no evasion,
no blockers).
"""

from __future__ import annotations

from typing import Any, Mapping, NamedTuple

import numpy as np

from anvil.encoder.transform import visible_to

DERIVED_VERSION = 1

TTD_CAP = 20.0  # turns-to-death clip; also the "no clock on board" value
# Conditioning clips (the transform v2/v3 lesson, seen again at the probe:
# infinite-combo boards log six-digit power and drain kills six-digit-negative
# life; unclipped they own the feature std and standardization crushes the
# normal-game range to ~0). Lethality semantics saturate far below the caps.
PT_CAP = 50.0  # per-entity power/toughness contribution, [0, cap]
LIFE_LO, LIFE_HI = -10.0, 150.0


class CardStatic(NamedTuple):
    cmc: float
    is_land: bool
    has_x: bool


# fixed feature order; family tags drive the probe's per-family attribution
FEATURE_NAMES = [
    # race/lethality: on-board damage vs life
    "race_power_ready_self",
    "race_power_ready_opp",
    "race_power_total_self",
    "race_power_total_opp",
    "race_lethal_margin_vs_self",
    "race_lethal_margin_vs_opp",
    "race_lethal_now_vs_self",
    "race_lethal_now_vs_opp",
    "race_life_diff",
    # turns-to-death clock
    "clock_ttd_self",
    "clock_ttd_opp",
    "clock_diff",
    "clock_ahead",
    # castability vs mana development
    "cast_mana_avail_self",
    "cast_mana_avail_opp",
    "cast_now",
    "cast_next",
    "cast_hand_lands",
    "cast_hand_nonland",
    "cast_hand_min_cmc",
    "cast_hand_mean_cmc",
    "cast_curve_gap",
    # material / card advantage differentials (self minus opponent)
    "mat_creatures_diff",
    "mat_permanents_diff",
    "mat_lands_diff",
    "mat_hand_diff",
    "mat_grave_diff",
    "mat_lib_diff",
    "mat_toughness_diff",
    "mat_card_adv",
    # commander zone / tax
    "cmd_tax_self",
    "cmd_tax_opp",
    "cmd_zone_self",
    "cmd_zone_opp",
    "cmd_bf_self",
    "cmd_bf_opp",
    "cmd_cast_gap",
    "cmd_castable",
]

FAMILIES = ["race", "clock", "cast", "mat", "cmd"]
FAMILY_OF = {n: n.split("_", 1)[0] for n in FEATURE_NAMES}
assert set(FAMILY_OF.values()) == set(FAMILIES)


def collect_names(dec: dict[str, Any], header: dict[str, Any], perspective: int) -> set[str]:
    """Every card name derived_features would look up in statics for this
    record — visible entity names + header commander names. For prefetch."""
    obs = dec["obs"]
    names = {ent["n"] for ent in obs.get("ents", []) if visible_to(ent, perspective)}
    for p in header["players"]:
        names.update(p.get("cmd") or [])
    return names


def load_statics(names: set[str]) -> dict[str, CardStatic]:
    """name -> CardStatic from the pinned fork's cardsfolder; silent on
    misses (tokens/emblems have no script) — callers diff against `names`
    for diagnostics."""
    from anvil.encoder.cardtext import CARD_FEATURES, _scan_files, face_features, parse_faces
    from anvil.pool.forge_db import normalize

    files = _scan_files()
    i_cmc = CARD_FEATURES.index("cmc")
    i_land = CARD_FEATURES.index("type_land")
    i_x = CARD_FEATURES.index("has_x")
    out: dict[str, CardStatic] = {}
    for name in names:
        path = files.get(normalize(name))
        if path is None:
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            feats = face_features(parse_faces(f.read()))
        out[name] = CardStatic(
            cmc=feats[i_cmc], is_land=bool(feats[i_land]), has_x=bool(feats[i_x])
        )
    return out


def derived_features(
    dec: dict[str, Any], header: dict[str, Any], perspective: int, statics: Mapping[str, CardStatic]
) -> np.ndarray:
    """One decision record -> (len(FEATURE_NAMES),) float32, raw scale
    (the probe standardizes; a model-boundary scale vector comes with the
    graduated build, same pattern as transform.ENTITY_SCALE)."""
    obs = dec.get("obs")
    if obs is None:
        raise ValueError(f"decision s={dec.get('s')} has no observation")
    players = obs["players"]
    n = len(header["players"])
    opps = [i for i in range(n) if i != perspective and not players[i].get("lost")]
    if not opps:  # terminal-ish record: everyone else eliminated
        opps = [i for i in range(n) if i != perspective]

    def side(i: int) -> int:
        return 0 if i == perspective else 1 if i in opps else -1

    # --- entity walks (raw ents; dedup is a transform concern, not ours) ---
    power_ready = [0.0, 0.0]
    power_total = [0.0, 0.0]
    tough_total = [0.0, 0.0]
    creatures = [0, 0]
    lands_bf = [0, 0]
    lands_untapped = [0, 0]
    permanents = [0, 0]
    grave = [0, 0]
    cmd_zone = [0, 0]
    cmd_bf = [0, 0]
    hand_cmcs: list[float] = []  # own non-land hand cards with known cmc
    hand_lands = 0
    hand_nonland = 0
    cmd_zone_names_self: list[str] = []

    hdr_cmd = [hp.get("cmd") or [] for hp in header["players"]]

    for ent in obs.get("ents", []):
        s = side(ent["c"])
        if s < 0 or ent.get("phz"):
            continue
        name = ent["n"] if visible_to(ent, perspective) else None
        st = statics.get(name) if name else None
        z = ent["z"]
        if z == "battlefield":
            permanents[s] += 1
            pt = ent.get("pt")
            if pt:
                creatures[s] += 1
                pw = min(max(float(pt[0]), 0.0), PT_CAP)
                power_total[s] += pw
                tough_total[s] += min(max(float(pt[1]), 0.0), PT_CAP)
                if not ent.get("tap") and not ent.get("sick"):
                    power_ready[s] += pw
            if st is not None and st.is_land:
                lands_bf[s] += 1
                if not ent.get("tap"):
                    lands_untapped[s] += 1
            if name is not None and name in hdr_cmd[ent["c"]]:
                cmd_bf[s] += 1
        elif z == "graveyard":
            grave[s] += 1
        elif z == "command":
            if not ent.get("tok") and name is not None and name in hdr_cmd[ent["c"]]:
                cmd_zone[s] += 1
                if s == 0:
                    cmd_zone_names_self.append(name)
        elif z == "hand" and s == 0 and name is not None:
            if st is not None and st.is_land:
                hand_lands += 1
            else:
                hand_nonland += 1
                if st is not None:
                    hand_cmcs.append(st.cmc)

    # --- player-level aggregates ---
    def _life(i: int) -> float:
        return min(max(float(players[i]["life"]), LIFE_LO), LIFE_HI)

    life_self = _life(perspective)
    life_opp = min(_life(i) for i in opps)
    pool = [
        float(sum((players[perspective].get("mana") or {}).values())),
        float(sum(sum((players[i].get("mana") or {}).values()) for i in opps)),
    ]
    mana_avail = [lands_untapped[0] + pool[0], lands_untapped[1] + pool[1]]
    hand_ct = [float(players[perspective]["hand"]), float(sum(players[i]["hand"] for i in opps))]
    lib_ct = [float(players[perspective]["lib"]), float(sum(players[i]["lib"] for i in opps))]

    # --- race / lethality ---
    lethal_vs_self = power_ready[1] - life_self
    lethal_vs_opp = power_ready[0] - life_opp

    # --- clock ---
    ttd_self = TTD_CAP if power_total[1] <= 0 else min(TTD_CAP, life_self / power_total[1])
    ttd_opp = TTD_CAP if power_total[0] <= 0 else min(TTD_CAP, life_opp / power_total[0])

    # --- castability ---
    cast_now = sum(1 for c in hand_cmcs if c <= mana_avail[0])
    cast_next = sum(1 for c in hand_cmcs if c <= mana_avail[0] + 1)
    hand_min = min(hand_cmcs) if hand_cmcs else 0.0
    hand_mean = float(np.mean(hand_cmcs)) if hand_cmcs else 0.0
    curve_gap = (hand_mean - mana_avail[0]) if hand_cmcs else 0.0

    # --- commander tax / castability ---
    casts = [players[i].get("cmdcast") or [] for i in range(n)]
    tax_self = 2.0 * sum(casts[perspective])
    tax_opp = 2.0 * sum(sum(casts[i]) for i in opps)
    cmd_gap, cmd_castable = 0.0, 0.0
    gaps = []
    for name in cmd_zone_names_self:
        st = statics.get(name)
        if st is None:
            continue
        idx = hdr_cmd[perspective].index(name)
        tax_i = 2.0 * (casts[perspective][idx] if idx < len(casts[perspective]) else 0)
        gaps.append(st.cmc + tax_i - mana_avail[0])
    if gaps:
        cmd_gap = min(gaps)
        cmd_castable = 1.0 if cmd_gap <= 0 else 0.0

    return np.array(
        [
            power_ready[0],
            power_ready[1],
            power_total[0],
            power_total[1],
            lethal_vs_self,
            lethal_vs_opp,
            1.0 if power_ready[1] >= life_self else 0.0,
            1.0 if power_ready[0] >= life_opp else 0.0,
            life_self - life_opp,
            ttd_self,
            ttd_opp,
            ttd_self - ttd_opp,
            1.0 if ttd_self > ttd_opp else 0.0,
            mana_avail[0],
            mana_avail[1],
            float(cast_now),
            float(cast_next),
            float(hand_lands),
            float(hand_nonland),
            hand_min,
            hand_mean,
            curve_gap,
            float(creatures[0] - creatures[1]),
            float(permanents[0] - permanents[1]),
            float(lands_bf[0] - lands_bf[1]),
            hand_ct[0] - hand_ct[1],
            float(grave[0] - grave[1]),
            lib_ct[0] - lib_ct[1],
            tough_total[0] - tough_total[1],
            (hand_ct[0] + permanents[0]) - (hand_ct[1] + permanents[1]),
            tax_self,
            tax_opp,
            float(cmd_zone[0]),
            float(cmd_zone[1]),
            float(cmd_bf[0]),
            float(cmd_bf[1]),
            cmd_gap,
            cmd_castable,
        ],
        dtype=np.float32,
    )
