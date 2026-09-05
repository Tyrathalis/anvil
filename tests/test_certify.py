"""M10 reset Fork 3: the inline certifier's Python side — the deterministic
rate gate, the sweep-identical eligibility + arm enumeration on a peek
record, the label -> option-index mapping, and the server's answer shape."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from veto_knowability import CardInfo, ProdUnit, parse_mana_cost  # noqa: E402

from anvil.bridge.certify import CERTIFY_TAG, Certifier, accept, window_cands  # noqa: E402
from anvil.bridge.pb import anvil_bridge_pb2 as pb  # noqa: E402
from anvil.bridge.server import DecisionServicer  # noqa: E402

ANY = frozenset("WUBRGC")


def fs(*colors):
    return frozenset(colors)


def _land(name, color):
    return CardInfo(name, parse_mana_cost("no cost"), "Land",
                    [ProdUnit(fs(color), 1, False, True, False, "battlefield")])


TABLE = {
    "Forest": _land("Forest", "G"),
    "Mountain": _land("Mountain", "R"),
    "Bear": CardInfo("Bear", parse_mana_cost("1 G"), "Creature Bear"),
    "Bolt": CardInfo("Bolt", parse_mana_cost("R"), "Instant"),
    "Rock": CardInfo("Rock", parse_mana_cost("2"), "Artifact",
                     [ProdUnit(ANY, 1, False, True, False, "battlefield")]),
    "Titan": CardInfo("Titan", parse_mana_cost("4 G G"), "Creature Giant"),
}


def _peek(turn=5, seat=0):
    ents = [
        {"e": 1, "n": "Forest", "z": "battlefield", "c": seat},
        {"e": 2, "n": "Forest", "z": "battlefield", "c": seat},
        {"e": 3, "n": "Mountain", "z": "battlefield", "c": seat},
        {"e": 10, "n": "Bear", "z": "hand", "c": seat},
        {"e": 11, "n": "Bolt", "z": "hand", "c": seat},
        {"e": 12, "n": "Rock", "z": "hand", "c": seat},
        {"e": 13, "n": "Titan", "z": "hand", "c": seat},
    ]
    opts = [
        {"e": 10, "sa": "Bear - Creature 2 / 2", "kind": "spell"},
        {"e": 11, "sa": "Bolt - deal 3 damage", "kind": "spell"},
        {"e": 12, "sa": "Rock - Artifact", "kind": "spell"},
        {"e": 13, "sa": "Titan - Creature 6 / 6", "kind": "spell"},  # unaffordable on 3 lands
        {"e": 1, "sa": "{T}: Add {G}.", "kind": "ability"},          # mana ability: not a cand
    ]
    return {"k": "peek", "t": turn, "ph": "MAIN1", "p": seat,
            "obs": {"glob": {"ph": "MAIN1", "ap": seat}, "ents": ents,
                    "players": [{"cmdcast": [0]}, {"cmdcast": [0]}]},
            "opts": opts}


def test_accept_is_deterministic_and_rate_bounded():
    assert not accept(0.0, 1, 5, 0) and accept(1.0, 1, 5, 0)
    a = [accept(0.3, seed, 5, 0) for seed in range(2000)]
    assert a == [accept(0.3, seed, 5, 0) for seed in range(2000)]  # replays
    assert 0.25 < sum(a) / len(a) < 0.35
    assert [accept(0.3, 7, t, 0) for t in range(50)] != [accept(0.3, 7, t, 1) for t in range(50)]


def test_window_cands_mirror_eligible_turns():
    cands = window_cands(_peek(), 0, TABLE)
    by = {c["label"]: c for c in cands}
    assert set(by) == {"Bear - Creature 2 / 2", "Bolt - deal 3 damage", "Rock - Artifact",
                       "Titan - Creature 6 / 6"}
    assert by["Bear - Creature 2 / 2"]["afford"] and by["Bolt - deal 3 damage"]["afford"]
    assert by["Rock - Artifact"]["afford"] and by["Rock - Artifact"]["mana_producer"]
    assert not by["Titan - Creature 6 / 6"]["afford"]
    assert by["Bolt - deal 3 damage"]["instant_speed"] and not by["Bear - Creature 2 / 2"]["instant_speed"]
    assert by["Rock - Artifact"]["idx"] == 2


def test_arms_are_index_lists_over_affordable_cands():
    c = Certifier(rate=1.0, table=TABLE)
    labels = [o["sa"][:60] for o in _peek()["opts"]]
    arms = c.arms(_peek(), labels, game_seed=42)
    assert arms and all(isinstance(a, list) for a in arms)
    flat = {i for a in arms for i in a}
    assert flat <= {0, 1, 2}  # Titan (3) unaffordable, the mana ability (4) never a cand
    assert [] in arms  # the hold-all arm
    assert len(arms) <= c.arm_cap and c.counts["certified_points"] == 1
    # n <= 3 affordable cands: every ordered subset (permutations of 0..3 elements)
    assert len(arms) == 1 + 3 + 6 + 6
    # deterministic per window
    assert arms == Certifier(rate=1.0, table=TABLE).arms(_peek(), labels, game_seed=42)


def test_arms_gate_and_eligibility():
    c = Certifier(rate=0.0, table=TABLE)
    assert c.arms(_peek(), [], game_seed=1) == [] and c.counts["declined_rate"] == 1
    # one affordable cast only: nothing to schedule
    peek = _peek()
    peek["opts"] = peek["opts"][:1]
    c2 = Certifier(rate=1.0, table=TABLE)
    assert c2.arms(peek, ["Bear - Creature 2 / 2"], game_seed=1) == [] and c2.counts["ineligible"] == 1


def test_server_certify_answer_shape():
    class Stub:
        counts = {}

        def arms(self, peek, labels, game_seed):
            return [[2, 0], []]

    sv = DecisionServicer("model", ["mtg.priority", CERTIFY_TAG], certifier=Stub())
    req = pb.DecisionRequest(decision_seq=9, decision_tag=CERTIFY_TAG, shape=pb.SELECT_K,
                             observation=b'{"t": 3, "p": 0, "obs": {}, "opts": []}')
    req.options.add(id=0, label="a")
    resp = sv._certify_answer(req, game_seed=5)
    assert resp.decision_seq == 9 and [list(x.indices) for x in resp.index_lists] == [[2, 0], []]
    # no certifier / no observation -> empty answer, counted as a fallback
    sv0 = DecisionServicer("model", ["mtg.priority"])
    assert len(sv0._certify_answer(req, 5).index_lists) == 0 and sv0.fallbacks[CERTIFY_TAG] == 1
