"""ADR-0137: the attack-target head scores only legal defenders."""

from anvil.encoder.transform import assemble, attack_target_ok


def _ent(e, n, c, z="battlefield", **kw):
    return {"e": e, "n": n, "z": z, "c": c, **kw}


def test_attack_target_ok_rules():
    walker = _ent(1, "Teferi, Time Raveler", 1, cnt={"LOYALTY": 3})
    assert attack_target_ok(walker, 0)
    assert not attack_target_ok(walker, 1)  # one's own planeswalker
    assert not attack_target_ok(_ent(2, "Plains", 1), 0)
    assert not attack_target_ok(_ent(3, "Grizzly Bears", 1, pt=[2, 2]), 0)
    # a flip-walker's creature face has no loyalty
    assert not attack_target_ok(_ent(4, "Ajani, Nacatl Pariah", 1, pt=[1, 2]), 0)
    assert not attack_target_ok(_ent(5, "Teferi, Time Raveler", 1, z="graveyard", cnt={"LOYALTY": 3}), 0)
    assert attack_target_ok(_ent(6, "Invasion of Zendikar", 0, cnt={"DEFENSE": 3}), 0)
    assert not attack_target_ok(_ent(7, "Walking Ballista", 1, pt=[1, 1], cnt={"P1P1": 1}), 0)


def test_assemble_marks_rows_in_row_order():
    header = {
        "sv": 3,
        "fmt": "Commander",
        "players": [{"name": "a", "cmd": []}, {"name": "b", "cmd": []}],
    }
    dec = {
        "k": "dec",
        "p": "0",
        "m": "declareAttackers",
        "obs": {
            "glob": {"turn": 5, "ph": "COMBAT_DECLARE_ATTACKERS", "ap": 0},
            "players": [
                {"life": 40, "hand": 1, "lib": 80, "cmdcast": []},
                {"life": 40, "hand": 1, "lib": 80, "cmdcast": []},
            ],
            "ents": [
                _ent(10, "Plains", 1),
                _ent(11, "Teferi, Time Raveler", 1, cnt={"LOYALTY": 4}),
                _ent(12, "Grizzly Bears", 0, pt=[2, 2]),
                _ent(13, "Jace, the Mind Sculptor", 0, cnt={"LOYALTY": 3}),
            ],
        },
    }
    out = assemble(dec, header, perspective=0)
    ok = out["atk_tgt_ok"]
    assert ok.shape[0] == out["entities"].shape[0]
    row_of = out["entity_row_of"]
    assert [bool(ok[row_of[e]]) for e in (10, 11, 12, 13)] == [False, True, False, False]
