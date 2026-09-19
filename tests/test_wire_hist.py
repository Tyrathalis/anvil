"""The loader's wire-history reconstruction mirrors Obs.retHostId (09-18, the
loop-wiring smoke's tripwire): a single-entity answer is a bare dict."""

from anvil.bridge.featurize import store_wire_hist


def test_single_entity_answer_backfills_the_host():
    prior = [
        {"m": "chooseSingleCardForZoneChange", "p": 0, "ret": {"e": 41}, "_retpos": 5},
        {"m": "orderMoveToZoneList", "p": 1, "ret": [{"e": 197}, {"e": 124}], "_retpos": 6},
        {"m": "assignCombatDamage", "p": 0, "ret": {"map": [[{"e": 67}, 2]]}, "_retpos": 7},
        {"m": "chooseNumber", "p": 0, "ret": 3, "_retpos": 8},
        {"m": "chooseSpellAbilityToPlay", "p": 1, "ret": [{"e": 9, "sa": "x"}], "_retpos": 20},  # lands later
    ]
    h = store_wire_hist(prior, now_pos=10)
    assert [x["e"] for x in h] == [41, 197, -1, -1, -1]
