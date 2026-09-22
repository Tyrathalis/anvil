"""ADR-0116 (09-21, Kryptic's finding): the player-position convention is one helper,
self first then turn order after self, used by the dataset labels, the featurizer's
seat list and the server's decode. The old label copied the registered seat into a
self-first row: from seat 1 the model's "opponent" decoded as itself (46% self-targets
served on b4post; the heuristic's legitimate share 11%)."""

from __future__ import annotations

import pytest

from anvil.bridge.server import check_player_target_convention, decode_player_ref
from anvil.encoder.transform import (
    PLAYER_TARGET_CONVENTION,
    player_seats,
    player_target_position,
)


def test_two_players_self_first_from_both_seats():
    assert player_seats(0, 2) == [0, 1]
    assert player_seats(1, 2) == [1, 0]
    # the opponent is position 1 from EITHER seat; self is 0
    assert player_target_position(1, 0, 2) == 1
    assert player_target_position(0, 1, 2) == 1
    assert player_target_position(0, 0, 2) == 0
    assert player_target_position(1, 1, 2) == 0


def test_two_players_equals_the_legacy_self_then_registered_form():
    for p in (0, 1):
        assert player_seats(p, 2) == [p] + [q for q in range(2) if q != p]


def test_n_players_turn_order_after_self_is_seat_permutation_invariant():
    # four seats: from seat 2 the next to act (3) is position 1, then 0, then 1
    assert player_seats(2, 4) == [2, 3, 0, 1]
    for p in range(4):
        seats = player_seats(p, 4)
        assert seats[0] == p and sorted(seats) == [0, 1, 2, 3]
        for pos, pi in enumerate(seats):
            assert player_target_position(pi, p, 4) == pos
    # the same relative situation from any seat gives the same position:
    # "the player after me" is position 1 everywhere
    assert {player_target_position((p + 1) % 4, p, 4) for p in range(4)} == {1}


def test_label_and_decode_round_trip_from_every_seat():
    """The whole path: registered ref -> label position -> the model's pick ->
    decode -> the same registered player the ref named."""
    for n in (2, 3, 4):
        for p in range(n):
            seats = player_seats(p, n)
            for pi in range(n):
                pos = player_target_position(pi, p, n)
                assert decode_player_ref(pos, seats) == pi


def test_the_old_decode_was_wrong_from_seat_one():
    """Documents the bug: from seat 1 the opponent (registered 0) labels position
    1; the old decode `pick - n_ent` handed the engine registered 1 = self."""
    p, n = 1, 2
    pos = player_target_position(0, p, n)  # the opponent's position
    assert pos == 1
    assert pos != 0  # the old decode's answer (registered index 1 -> self)
    assert decode_player_ref(pos, player_seats(p, n)) == 0  # the corrected one


def test_decode_rejects_an_out_of_range_position():
    with pytest.raises(ValueError):
        decode_player_ref(2, [1, 0])
    with pytest.raises(ValueError):
        decode_player_ref(-1, [0, 1])


def test_checkpoint_convention_check(capsys):
    assert check_player_target_convention({}, "legacy.pt") == "legacy"
    assert "legacy" in capsys.readouterr().out
    assert check_player_target_convention({"player_target_convention": PLAYER_TARGET_CONVENTION}, "x") \
        == PLAYER_TARGET_CONVENTION
    with pytest.raises(RuntimeError):
        check_player_target_convention({"player_target_convention": "registered_v0"}, "old.pt")
