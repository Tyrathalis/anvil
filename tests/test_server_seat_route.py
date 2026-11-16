"""The head-to-head read's seat routing (`server --seat-ckpt`) and its
report (`scripts/h2h_read.py`).

An ask is answered by the checkpoint that sits at the asking seat, read
from the observation's `p`. An answer from the wrong checkpoint would be
silent, so an ask whose seat cannot be read is declined and counted, and
the driver refuses an arm that was not routed on both seats.
"""

import json
import sys
from pathlib import Path

import pytest

from anvil.bridge import server as srv
from anvil.bridge.server import DecisionServicer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import h2h_read  # noqa: E402


class _Backend:
    """Answers every ask with its own index, so the reply names the backend."""

    def __init__(self, index: int):
        self.index = index
        self.asked: list[int] = []
        self.counts: dict = {}

    def answer(self, req, header, game_seed=None, greedy=False, clock=None):
        self.asked.append(req.decision_seq)
        return srv.pb.DecisionResponse(decision_seq=req.decision_seq, index=self.index)

    def value(self, req, header):
        return srv.pb.DecisionResponse(decision_seq=req.decision_seq, value=self.index)


def _req(seq: int, obs: dict | None, tag: str = "mtg.priority"):
    return srv.pb.WorkerMsg(
        request=srv.pb.DecisionRequest(
            game_id="g1", decision_seq=seq, decision_tag=tag,
            observation=json.dumps(obs).encode() if obs is not None else b"",
        )
    )


def _session(sv: DecisionServicer, msgs: list) -> list:
    start = srv.pb.WorkerMsg(game_start=srv.pb.GameStart(game_id="g1", seed=7, header=b'{"g": 1}'))
    return [m.response for m in sv.Session(iter([start, *msgs]), None) if m.WhichOneof("msg") == "response"]


def test_each_seat_is_answered_by_its_own_checkpoint():
    main, other = _Backend(10), _Backend(11)
    sv = DecisionServicer("model", ["mtg.priority"], backend=main, seat_backends={1: other}, slow_ask_s=0)
    out = _session(sv, [_req(1, {"p": 0}), _req(2, {"p": 1}), _req(3, {"p": 1}), _req(4, {"p": 0})])
    assert [r.index for r in out] == [10, 11, 11, 10]
    assert main.asked == [1, 4] and other.asked == [2, 3]
    assert sv.seat_requests == {0: 2, 1: 2} and sv.seat_unrouted == 0


def test_swapping_the_seat_swaps_the_answers():
    main, other = _Backend(10), _Backend(11)
    sv = DecisionServicer("model", ["mtg.priority"], backend=main, seat_backends={0: other}, slow_ask_s=0)
    out = _session(sv, [_req(1, {"p": 0}), _req(2, {"p": 1})])
    assert [r.index for r in out] == [11, 10]


def test_an_ask_without_a_seat_is_declined_and_counted(capsys):
    main, other = _Backend(10), _Backend(11)
    sv = DecisionServicer("model", ["mtg.priority"], backend=main, seat_backends={1: other}, slow_ask_s=0)
    out = _session(sv, [_req(1, {"t": 3}), _req(2, {"p": "x"})])
    assert all(r.fallback for r in out)
    assert sv.seat_unrouted == 2 and main.asked == [] and other.asked == []
    assert "SEAT UNROUTED" in capsys.readouterr().out


def test_the_search_leaf_value_follows_the_seat():
    main, other = _Backend(10), _Backend(11)
    sv = DecisionServicer("model", [srv.VALUE_TAG], backend=main, seat_backends={1: other}, slow_ask_s=0)
    out = _session(sv, [_req(1, {"p": 1}, srv.VALUE_TAG), _req(2, {"p": 0}, srv.VALUE_TAG)])
    assert [r.value for r in out] == [11, 10]


def test_without_seat_checkpoints_the_observation_is_not_read():
    main = _Backend(10)
    sv = DecisionServicer("model", ["mtg.priority"], backend=main, slow_ask_s=0)
    out = _session(sv, [_req(1, {"t": 3}), _req(2, None)])
    assert [r.index for r in out] == [10, 10]
    assert not sv.seat_requests and sv.seat_unrouted == 0


def _game(i: int, winner_seat: int | None, status: str = "won") -> dict:
    winner = f"Anvil({winner_seat + 1})-dc-1" if winner_seat is not None else None
    return {"i": i, "status": status, "winner": winner}


def test_game_score_reads_the_seat_from_the_winner():
    assert h2h_read.game_score(_game(0, 0), a_seat=0) == 1.0
    assert h2h_read.game_score(_game(0, 0), a_seat=1) == 0.0
    assert h2h_read.game_score(_game(0, 1), a_seat=1) == 1.0
    assert h2h_read.game_score(_game(0, None, "draw"), a_seat=0) == 0.5
    assert h2h_read.game_score(_game(0, None, "crash:npe"), a_seat=0) is None
    with pytest.raises(ValueError):
        h2h_read.game_score({"i": 0, "status": "won", "winner": "Heur-x"}, a_seat=0)


def test_score_pairs_the_two_seatings_of_one_seeded_game():
    # A wins every game from seat 0 and loses every game from seat 1: the
    # seat decides, the checkpoints are level, and the paired SE is zero
    arms = {0: [_game(i, 0) for i in range(4)], 1: [_game(i, 0) for i in range(4)]}
    rep = h2h_read.score(arms)
    assert rep["a_score"] == 0.5 and rep["se"] == 0.0
    assert rep["a_wins"] == 4 and rep["b_wins"] == 4 and rep["seat0_winrate_decisive"] == 1.0
    assert rep["a_score_by_a_seat"][0]["a_score"] == 1.0 and rep["a_score_by_a_seat"][1]["a_score"] == 0.0


def test_score_counts_a_win_for_a_from_either_seat_and_drops_crashes():
    arms = {
        0: [_game(0, 0), _game(1, 0), _game(2, None, "crash:npe")],
        1: [_game(0, 1), _game(1, 0), _game(2, 1)],
    }
    rep = h2h_read.score(arms)
    assert rep["a_wins"] == 4 and rep["b_wins"] == 1 and rep["crashes"] == 1
    assert rep["indices"] == 3 and rep["games_scored"] == 5
    assert rep["a_score"] == pytest.approx((1.0 + 0.5 + 1.0) / 3)


def test_check_routing_refuses_an_arm_that_was_not_routed():
    good = {"seat_requests": {"0": 5, "1": 6}, "seat_unrouted": 0, "seat1_greedy": 6}
    h2h_read.check_routing(good, seat_b=1)
    with pytest.raises(RuntimeError, match="both seats"):
        h2h_read.check_routing({**good, "seat_requests": {"0": 5}}, seat_b=1)
    with pytest.raises(RuntimeError, match="no readable seat"):
        h2h_read.check_routing({**good, "seat_unrouted": 2}, seat_b=1)
    with pytest.raises(RuntimeError, match="answered nothing"):
        h2h_read.check_routing({"seat_requests": {"0": 5, "1": 6}, "seat_unrouted": 0}, seat_b=1)
