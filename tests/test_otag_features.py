"""Oracle-tag functional features (anvil/encoder/otag_features.py)."""

import numpy as np

from anvil.encoder.otag_features import FAMILY_OF, FEATURE_NAMES, otag_features

GROUPS_OF = {
    "Swords to Plowshares": frozenset({"removal"}),
    "Sol Ring": frozenset({"ramp"}),
    "Demonic Tutor": frozenset({"tutor"}),
    "Basalt Monolith": frozenset({"ramp", "combo"}),
}

HEADER = {"sv": 2, "players": [{"name": "A", "cmd": []}, {"name": "B", "cmd": []}]}


def _dec(ents):
    return {
        "k": "dec",
        "s": 1,
        "p": 0,
        "obs": {
            "glob": {"turn": 4, "ph": "MAIN1", "ap": 0},
            "players": [{"life": 30, "hand": 2, "lib": 80}, {"life": 30, "hand": 2, "lib": 80}],
            "ents": ents,
        },
    }


ENTS = [
    {"e": 1, "n": "Swords to Plowshares", "z": "hand", "c": 0, "o": 0},
    {"e": 2, "n": "Basalt Monolith", "z": "battlefield", "c": 0, "o": 0},
    {"e": 3, "n": "Sol Ring", "z": "battlefield", "c": 1, "o": 1},
    # opponent hand tutor: hidden — must contribute nothing
    {"e": 4, "n": "Demonic Tutor", "z": "hand", "c": 1, "o": 1},
    # untagged card: contributes nothing anywhere
    {"e": 5, "n": "Island", "z": "battlefield", "c": 0, "o": 0},
]


def _feat(v, name):
    return float(v[FEATURE_NAMES.index(name)])


def test_counts_and_families():
    v = otag_features(_dec(ENTS), HEADER, 0, GROUPS_OF)
    assert v.shape == (len(FEATURE_NAMES),)
    assert _feat(v, "otag_hand_self_removal") == 1.0
    assert _feat(v, "otag_bf_self_ramp") == 1.0  # Basalt: ramp...
    assert _feat(v, "otag_bf_self_combo") == 1.0  # ...and combo
    assert _feat(v, "otag_bf_opp_ramp") == 1.0  # opp Sol Ring (public)
    assert _feat(v, "otag_hand_self_tutor") == 0.0  # opp tutor is hidden
    assert set(FAMILY_OF.values()) == {"ohand", "obfself", "obfopp"}


def test_leak_invariance_hidden_hand():
    swapped = [dict(e) for e in ENTS]
    for e in swapped:
        if e["e"] == 4:
            e["n"] = "Swords to Plowshares"
    a = otag_features(_dec(ENTS), HEADER, 0, GROUPS_OF)
    b = otag_features(_dec(swapped), HEADER, 0, GROUPS_OF)
    assert np.array_equal(a, b)


def test_own_hand_visible_and_capped():
    ents = [dict(ENTS[0])]
    for i in range(30):  # 30 copies of a removal spell in hand
        ents.append({"e": 100 + i, "n": "Swords to Plowshares", "z": "hand", "c": 0, "o": 0})
    v = otag_features(_dec(ents), HEADER, 0, GROUPS_OF)
    assert _feat(v, "otag_hand_self_removal") == 20.0  # COUNT_CAP


def test_phased_and_lost_excluded():
    ents = [dict(e) for e in ENTS]
    for e in ents:
        if e["e"] == 3:
            e["phz"] = 1
    v = otag_features(_dec(ents), HEADER, 0, GROUPS_OF)
    assert _feat(v, "otag_bf_opp_ramp") == 0.0
