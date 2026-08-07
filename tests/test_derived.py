"""Derived-state features (anvil/encoder/derived.py, M6 D2-B B-1).

Value assertions on a hand-built observation, plus the info-set leak
invariant inherited from the transform: features for perspective P must be
invariant under identity-substitution of entities P cannot see.
"""

import numpy as np
import pytest

from anvil.encoder.derived import (FAMILIES, FAMILY_OF, FEATURE_NAMES,
                                   CardStatic, collect_names,
                                   derived_features)

STATICS = {
    "Forest": CardStatic(cmc=0.0, is_land=True, has_x=False),
    "Lightning Bolt": CardStatic(cmc=1.0, is_land=False, has_x=False),
    "Big Guy": CardStatic(cmc=6.0, is_land=False, has_x=False),
    "Cmdr A": CardStatic(cmc=3.0, is_land=False, has_x=False),
    "Cmdr B": CardStatic(cmc=5.0, is_land=False, has_x=False),
    "Grizzly Bears": CardStatic(cmc=2.0, is_land=False, has_x=False),
}

HEADER = {"sv": 1, "players": [{"name": "A", "cmd": ["Cmdr A"]},
                               {"name": "B", "cmd": ["Cmdr B"]}]}


def _dec(ents, players=None, s=1):
    return {"k": "dec", "s": s, "p": 0, "obs": {
        "glob": {"turn": 5, "ph": "MAIN1", "ap": 0},
        "players": players or [
            {"life": 10, "hand": 2, "lib": 50, "mana": {"C": 1},
             "cmdcast": [1]},
            {"life": 7, "hand": 4, "lib": 60, "cmdcast": [0]},
        ],
        "ents": ents}}


ENTS = [
    # self: two forests (one tapped), a ready 3/3, commander in the zone
    {"e": 1, "n": "Forest", "z": "battlefield", "c": 0, "o": 0},
    {"e": 2, "n": "Forest", "z": "battlefield", "c": 0, "o": 0, "tap": 1},
    {"e": 3, "n": "Grizzly Bears", "z": "battlefield", "c": 0, "o": 0,
     "pt": [3, 3]},
    {"e": 4, "n": "Cmdr A", "z": "command", "c": 0, "o": 0},
    # self hand: a castable bolt and an uncastable 6-drop
    {"e": 5, "n": "Lightning Bolt", "z": "hand", "c": 0, "o": 0},
    {"e": 6, "n": "Big Guy", "z": "hand", "c": 0, "o": 0},
    # opponent: a ready 8/8, a summoning-sick 2/2, a tapped land,
    # a hidden hand card, a graveyard card
    {"e": 7, "n": "Big Guy", "z": "battlefield", "c": 1, "o": 1,
     "pt": [8, 8]},
    {"e": 8, "n": "Grizzly Bears", "z": "battlefield", "c": 1, "o": 1,
     "pt": [2, 2], "sick": 1},
    {"e": 9, "n": "Forest", "z": "battlefield", "c": 1, "o": 1, "tap": 1},
    {"e": 10, "n": "Lightning Bolt", "z": "hand", "c": 1, "o": 1},
    {"e": 11, "n": "Big Guy", "z": "graveyard", "c": 1, "o": 1},
]


def _feat(vec, name):
    return float(vec[FEATURE_NAMES.index(name)])


@pytest.fixture
def vec():
    return derived_features(_dec(ENTS), HEADER, 0, STATICS)


def test_shape_and_families(vec):
    assert vec.shape == (len(FEATURE_NAMES),)
    assert vec.dtype == np.float32
    assert set(FAMILY_OF.values()) == set(FAMILIES)


def test_race(vec):
    assert _feat(vec, "race_power_ready_self") == 3.0
    assert _feat(vec, "race_power_ready_opp") == 8.0     # sick 2/2 not ready
    assert _feat(vec, "race_power_total_opp") == 10.0
    assert _feat(vec, "race_lethal_margin_vs_self") == 8.0 - 10.0
    assert _feat(vec, "race_lethal_margin_vs_opp") == 3.0 - 7.0
    assert _feat(vec, "race_lethal_now_vs_self") == 0.0
    assert _feat(vec, "race_lethal_now_vs_opp") == 0.0
    assert _feat(vec, "race_life_diff") == 3.0


def test_clock(vec):
    assert _feat(vec, "clock_ttd_self") == 1.0           # 10 life / 10 power
    assert _feat(vec, "clock_ttd_opp") == pytest.approx(7 / 3)
    assert _feat(vec, "clock_diff") == pytest.approx(1.0 - 7 / 3)
    assert _feat(vec, "clock_ahead") == 0.0


def test_clock_caps_without_board():
    ents = [e for e in ENTS if "pt" not in e]
    v = derived_features(_dec(ents), HEADER, 0, STATICS)
    assert _feat(v, "clock_ttd_self") == 20.0
    assert _feat(v, "clock_ttd_opp") == 20.0


def test_castability(vec):
    # 1 untapped land + 1 floating = 2 mana: bolt (1) yes, Big Guy (6) no
    assert _feat(vec, "cast_mana_avail_self") == 2.0
    assert _feat(vec, "cast_mana_avail_opp") == 0.0
    assert _feat(vec, "cast_now") == 1.0
    assert _feat(vec, "cast_next") == 1.0
    assert _feat(vec, "cast_hand_lands") == 0.0
    assert _feat(vec, "cast_hand_nonland") == 2.0
    assert _feat(vec, "cast_hand_min_cmc") == 1.0
    assert _feat(vec, "cast_hand_mean_cmc") == 3.5
    assert _feat(vec, "cast_curve_gap") == 1.5


def test_material(vec):
    assert _feat(vec, "mat_creatures_diff") == 1.0 - 2.0
    assert _feat(vec, "mat_permanents_diff") == 3.0 - 3.0
    assert _feat(vec, "mat_lands_diff") == 2.0 - 1.0
    assert _feat(vec, "mat_hand_diff") == 2.0 - 4.0     # player counts, not ents
    assert _feat(vec, "mat_grave_diff") == -1.0
    assert _feat(vec, "mat_toughness_diff") == 3.0 - 10.0
    assert _feat(vec, "mat_card_adv") == (2 + 3) - (4 + 3)


def test_commander(vec):
    # cmdcast [1] => tax 2; Cmdr A cmc 3 + tax 2 = 5 > 2 avail
    assert _feat(vec, "cmd_tax_self") == 2.0
    assert _feat(vec, "cmd_tax_opp") == 0.0
    assert _feat(vec, "cmd_zone_self") == 1.0
    assert _feat(vec, "cmd_zone_opp") == 0.0
    assert _feat(vec, "cmd_bf_self") == 0.0
    assert _feat(vec, "cmd_cast_gap") == 3.0
    assert _feat(vec, "cmd_castable") == 0.0


def test_commander_on_battlefield():
    ents = [dict(e) for e in ENTS if e["e"] != 4]
    ents.append({"e": 4, "n": "Cmdr A", "z": "battlefield", "c": 0, "o": 0,
                 "pt": [2, 4]})
    v = derived_features(_dec(ents), HEADER, 0, STATICS)
    assert _feat(v, "cmd_zone_self") == 0.0
    assert _feat(v, "cmd_bf_self") == 1.0
    assert _feat(v, "cmd_cast_gap") == 0.0
    # its body joins the race math
    assert _feat(v, "race_power_ready_self") == 5.0


def test_leak_invariance_hidden_hand():
    """Opponent hand identity must not move any feature (visible_to gates
    it): substituting the hidden card's name is a no-op."""
    swapped = [dict(e) for e in ENTS]
    for e in swapped:
        if e["e"] == 10:
            e["n"] = "Big Guy"  # was Lightning Bolt; hidden either way
    a = derived_features(_dec(ENTS), HEADER, 0, STATICS)
    b = derived_features(_dec(swapped), HEADER, 0, STATICS)
    assert np.array_equal(a, b)


def test_own_hand_is_visible():
    swapped = [dict(e) for e in ENTS]
    for e in swapped:
        if e["e"] == 5:
            e["n"] = "Big Guy"  # own bolt becomes a 6-drop: castable drops
    v = derived_features(_dec(swapped), HEADER, 0, STATICS)
    assert _feat(v, "cast_now") == 0.0


def test_statics_miss_degrades_gracefully():
    """A token/emblem name with no statics entry: never a land, never
    castability-counted, but its body still races."""
    ents = ENTS + [{"e": 20, "n": "Spirit Token", "z": "battlefield",
                    "c": 0, "o": 0, "tok": 1, "pt": [1, 1]}]
    v = derived_features(_dec(ents), HEADER, 0, STATICS)
    assert _feat(v, "race_power_ready_self") == 4.0
    assert _feat(v, "cast_mana_avail_self") == 2.0


def test_conditioning_clips():
    """Combo-scale power and drain-scale life must not own the feature
    range: per-entity P/T clips at PT_CAP, life at [LIFE_LO, LIFE_HI]."""
    ents = [dict(e) for e in ENTS]
    for e in ents:
        if e["e"] == 7:
            e["pt"] = [999999, 999999]  # the opp 8/8 goes infinite
    players = [
        {"life": 10, "hand": 2, "lib": 50, "mana": {"C": 1}, "cmdcast": [1]},
        {"life": -80000, "hand": 4, "lib": 60, "cmdcast": [0]},
    ]
    v = derived_features(_dec(ents, players=players), HEADER, 0, STATICS)
    assert _feat(v, "race_power_ready_opp") == 50.0
    assert _feat(v, "race_power_total_opp") == 52.0
    assert _feat(v, "mat_toughness_diff") == 3.0 - 52.0
    assert _feat(v, "race_life_diff") == 10.0 - (-10.0)
    assert _feat(v, "race_lethal_margin_vs_opp") == 3.0 - (-10.0)
    # negative power contributes zero, never heals
    ents2 = [dict(e) for e in ENTS]
    for e in ents2:
        if e["e"] == 8:
            e["pt"] = [-3, 2]
    v2 = derived_features(_dec(ents2), HEADER, 0, STATICS)
    assert _feat(v2, "race_power_total_opp") == 8.0


def test_eliminated_opponent_excluded():
    players = [
        {"life": 10, "hand": 2, "lib": 50, "mana": {"C": 1}, "cmdcast": [1]},
        {"life": 7, "hand": 4, "lib": 60, "cmdcast": [0]},
        {"life": 0, "hand": 0, "lib": 0, "lost": 1, "cmdcast": [3]},
    ]
    header = {"sv": 1, "players": HEADER["players"] + [{"name": "C",
                                                        "cmd": ["Cmdr B"]}]}
    v = derived_features(_dec(ENTS, players=players), header, 0, STATICS)
    assert _feat(v, "race_life_diff") == 3.0     # vs the living opponent
    assert _feat(v, "cmd_tax_opp") == 0.0        # lost seat's casts ignored


def test_collect_names_respects_visibility():
    names = collect_names(_dec(ENTS), HEADER, 0)
    assert "Cmdr A" in names and "Cmdr B" in names
    assert "Forest" in names
    # e10 is the opponent's hand card: identity must not even be requested
    ents = [dict(e) for e in ENTS]
    for e in ents:
        if e["e"] == 10:
            e["n"] = "Totally Unique Name"
    assert "Totally Unique Name" not in collect_names(_dec(ents), HEADER, 0)
