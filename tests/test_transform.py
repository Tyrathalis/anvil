"""Tensor-assembly transform v0: determinism, dedup, and THE LEAK TEST.

The leak test is load-bearing (observation-schema-v1 decision 2): records
carry full hidden state for M2 belief labels; the transform is the only gate
between that and the policy input. Its output for perspective P must be
invariant under any change to what P cannot see — identity substitution and
reordering of hidden entities.
"""

import numpy as np
import pytest

from anvil.encoder.transform import VocabError, assemble, visible_to


def _header():
    return {"k": "game", "sv": 1, "g": 0, "seed": 1, "fmt": "Commander",
            "players": [{"name": "P0", "deck": "D0"}, {"name": "P1", "deck": "D1"}]}


def _dec(ents, stack=None, p=0):
    return {"k": "dec", "s": 0, "t": 3, "ph": "MAIN1", "p": p, "m": "chooseSpellAbilityToPlay",
            "obs": {"glob": {"turn": 3, "ph": "MAIN1", "ap": 0},
                    "players": [{"life": 38, "hand": 5, "lib": 90},
                                {"life": 40, "hand": 4, "lib": 88}],
                    "ents": ents, **({"stack": stack} if stack else {})}}


def test_leak_invariance():
    """Perspective-0 output must not change when hidden identities change."""
    opp_hand_a = [{"e": 10, "n": "Lightning Bolt", "z": "hand", "c": 1},
                  {"e": 11, "n": "Counterspell", "z": "hand", "c": 1},
                  {"e": 12, "n": "Swords to Plowshares", "z": "hand", "c": 1}]
    opp_hand_b = [{"e": 12, "n": "Black Lotus", "z": "hand", "c": 1},
                  {"e": 10, "n": "Ancestral Recall", "z": "hand", "c": 1},
                  {"e": 11, "n": "Time Walk", "z": "hand", "c": 1}]
    own = [{"e": 1, "n": "Sol Ring", "z": "battlefield", "c": 0, "tap": 1},
           {"e": 2, "n": "Brainstorm", "z": "hand", "c": 0}]

    out_a = assemble(_dec(own + opp_hand_a), _header())
    out_b = assemble(_dec(opp_hand_b + own), _header())  # reordered AND renamed

    np.testing.assert_array_equal(out_a["entities"], out_b["entities"])
    assert out_a["entity_names"] == out_b["entity_names"]
    np.testing.assert_array_equal(out_a["entity_counts"], out_b["entity_counts"])
    # and the hidden cards never leak a name
    hidden_rows = [n for n, row in zip(out_a["entity_names"], out_a["entities"])
                   if row[-1] == 1.0]
    assert hidden_rows == [None]


def test_facedown_battlefield_hidden_from_opponent():
    ents = [{"e": 5, "n": "Hypnotic Specter", "z": "battlefield", "c": 1, "fd": 1,
             "pt": [2, 2], "vis": "c"}]
    mine = assemble(_dec(ents, p=0), _header())          # I am player 0: hidden
    theirs = assemble(_dec(ents, p=1), _header(), perspective=1)  # controller: visible
    assert mine["entity_names"] == [None]
    assert theirs["entity_names"] == ["Hypnotic Specter"]
    # public aspects of the face-down permanent still present for both
    assert mine["entities"][0][8:10].tolist() == [2.0, 2.0]


def test_revealed_hand_visible():
    ents = [{"e": 7, "n": "Gilded Drake", "z": "hand", "c": 1, "vis": "all"}]
    out = assemble(_dec(ents), _header())
    assert out["entity_names"] == ["Gilded Drake"]


def test_multiset_dedup():
    ents = [{"e": i, "n": "Rat Colony", "z": "battlefield", "c": 0, "pt": [1, 1]}
            for i in range(30, 36)]
    out = assemble(_dec(ents), _header())
    assert out["entities"].shape[0] == 1
    assert out["entity_counts"].tolist() == [6]


def test_visible_to_zone_defaults():
    assert visible_to({"e": 1, "n": "X", "z": "battlefield", "c": 1}, 0)
    assert not visible_to({"e": 1, "n": "X", "z": "hand", "c": 1}, 0)
    assert visible_to({"e": 1, "n": "X", "z": "hand", "c": 1}, 1)
    assert not visible_to({"e": 1, "n": "X", "z": "exile", "c": 1, "fd": 1, "vis": "none"}, 1)


def test_unknown_vocab_is_loud():
    ents = [{"e": 1, "n": "X", "z": "subterranean_lair", "c": 0}]
    with pytest.raises(VocabError):
        assemble(_dec(ents), _header())


def test_globals_and_players_perspective():
    out0 = assemble(_dec([]), _header())
    assert out0["globals"][2] == 1.0          # active player is self
    assert out0["players"][0][0] == 38.0      # self first
    out1 = assemble(_dec([], p=1), _header())
    assert out1["globals"][2] == 0.0
    assert out1["players"][0][0] == 40.0


def test_library_top_visibility():
    """Schema v1 amendment (M1 D3): library-top rows carry explicit vis;
    'c' stays controller-only, 'all' is public, missing vis = hidden."""
    forge = [{"e": 20, "n": "Mystic Forge Top", "z": "library", "c": 1, "vis": "c"}]
    courser = [{"e": 21, "n": "Courser Top", "z": "library", "c": 1, "vis": "all"}]
    bare = [{"e": 22, "n": "Never Serialized Like This", "z": "library", "c": 1}]

    assert assemble(_dec(forge, p=0), _header())["entity_names"] == [None]
    assert assemble(_dec(forge, p=1), _header(), perspective=1)["entity_names"] == [
        "Mystic Forge Top"]
    assert assemble(_dec(courser, p=0), _header())["entity_names"] == ["Courser Top"]
    assert not visible_to(bare[0], 0) and not visible_to(bare[0], 1)


def test_library_top_leak_invariance():
    """Opponent's controller-only library top must not leak identity."""
    a = [{"e": 20, "n": "Bolas Citadel Pick A", "z": "library", "c": 1, "vis": "c"}]
    b = [{"e": 20, "n": "Something Else Entirely", "z": "library", "c": 1, "vis": "c"}]
    out_a = assemble(_dec(a, p=0), _header())
    out_b = assemble(_dec(b, p=0), _header())
    np.testing.assert_array_equal(out_a["entities"], out_b["entities"])
    assert out_a["entity_names"] == out_b["entity_names"] == [None]
