"""M9 D2a probe: the pure-python pieces — AUC, holdout convention, cost
features, and the leakage guard (obs-arithmetic arm never sees the engine
verdict). GPU feature capture is validated live by the run itself."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from affordability_probe import (  # noqa: E402
    _feats,
    auc,
    held_out,
    match_opt,
)
from veto_knowability import CardInfo, ProdUnit, parse_mana_cost  # noqa: E402


def test_auc_perfect_and_random():
    y = np.array([0, 0, 1, 1])
    assert auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == 0.0
    assert auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == 0.5  # all-tied -> 0.5


def test_auc_ties_averaged():
    y = np.array([0, 1, 0, 1])
    s = np.array([0.3, 0.3, 0.1, 0.9])
    # pos ranks: 0.3 ties rank (2+3)/2=2.5, 0.9 rank 4 -> (6.5 - 3)/4
    assert abs(auc(y, s) - 0.875) < 1e-9


def test_held_out_deterministic_and_game_grouped():
    assert held_out("runA", 7) == held_out("runA", 7)
    frac = np.mean([held_out("runA", g) for g in range(2000)])
    assert 0.15 < frac < 0.25  # ~1/5


def test_match_opt_prefix_both_ways():
    dec = {"opts": [{"sa": "Grim Initiate - Creature 1 / 1", "e": 4}]}
    assert match_opt(dec, "Grim Initiate - Creature 1 / 1")["e"] == 4
    assert match_opt(dec, "Grim Initiate - Crea")["e"] == 4
    assert match_opt(dec, "Nope") is None


def _table():
    return {
        "Dork": CardInfo("Dork", parse_mana_cost("G"), "Creature Elf",
                         [ProdUnit(frozenset("G"), 1, False, True, False,
                                   "battlefield")]),
        "Ox": CardInfo("Ox", parse_mana_cost("2 G"), "Creature Ox"),
    }


def _dec(sick=0):
    return {
        "p": 0, "m": "chooseSpellAbilityToPlay",
        "obs": {"glob": {"ph": "MAIN1", "ap": 0},
                "players": [{"cmdcast": [0]}, {"cmdcast": [0]}],
                "ents": [{"e": 1, "n": "Ox", "z": "hand", "c": 0},
                         {"e": 2, "n": "Dork", "z": "battlefield", "c": 0,
                          **({"sick": 1} if sick else {})}]},
        "opts": [{"sa": "Ox - Creature 4 / 4", "e": 1, "kind": "spell"}],
    }


def test_feats_cost_vector():
    fc, fa = _feats(_dec(), {"sa": "Ox - Creature 4 / 4", "e": 1,
                             "kind": "spell"}, _table())
    # [generic, W,U,B,R,G,C, twobrid, phyx, x, snow, total, cmd_extra, unresolved]
    assert fc[0] == 2 and fc[5] == 1 and fc[11] == 3 and fc[13] == 0.0
    assert len(fa) > len(fc)


def test_feats_sick_changes_arith_not_cost():
    """The leakage guard's positive twin: arithmetic features respond to the
    obs (sick flag), never to any engine verdict field."""
    opt = {"sa": "Ox - Creature 4 / 4", "e": 1, "kind": "spell"}
    t = _table()
    _, fa_ok = _feats(_dec(sick=0), opt, t)
    _, fa_sick = _feats(_dec(sick=1), opt, t)
    assert not np.array_equal(fa_ok, fa_sick)  # n_now / can_pay views moved


def test_feats_ignores_engine_verdict_fields():
    """Adding veto/reask fields to the dec record must not change features —
    corroborated=False everywhere (the leakage guard itself)."""
    opt = {"sa": "Ox - Creature 4 / 4", "e": 1, "kind": "spell"}
    d1, d2 = _dec(), _dec()
    d2["veto"] = "unpayable"
    d2["reask"] = True
    t = _table()
    fc1, fa1 = _feats(d1, opt, t)
    fc2, fa2 = _feats(d2, opt, t)
    assert np.array_equal(fc1, fc2) and np.array_equal(fa1, fa2)
