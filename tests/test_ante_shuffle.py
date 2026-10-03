"""ADR-0121: the shuffle mark cleanses the Ante ledger's library knowledge.

Synthetic two-player trajectories through `ledger.extract`: a scry poisons
the seat's draws until its next shuffle mark; the cleanse lands after the
mark's own record (events inside one gap have no order); a looked-at
library card is a uniform draw again once shuffled; a store without marks
reads as before.
"""

from collections import Counter

from anvil.ante import ledger
from anvil.store.trajectories import GameTrajectory

DECK = Counter({"Forest": 30, "Bear": 10})
LIB0 = 33  # 40 - 7


def ent(e, name, zone, c):
    return {"e": e, "n": name, "z": zone, "c": c}


def dec(pos, m, p, turn, ents, libs):
    return {
        "_pos": pos,
        "s": pos,
        "m": m,
        "p": p,
        "obs": {
            "glob": {"turn": turn, "ap": 0},
            "ents": ents,
            "players": [{"lib": libs[0]}, {"lib": libs[1]}],
        },
    }


def mark(pos, p):
    return {"_pos": pos, "k": "mark", "m": "shuffle", "p": p, "t": 1}


def traj(decisions, marks=()):
    header = {"players": [{"deck": "A"}, {"deck": "B"}], "seed": 1, "g": 0}
    return GameTrajectory(header, decisions, None, {}, list(marks))


def hand(p, ids):
    return [ent(e, "Forest", "hand", p) for e in ids]


def run(decisions, marks=(), deck0=DECK):
    nodes, _on_play, skips = ledger.extract(traj(decisions, marks), {0: deck0, 1: DECK})
    return [(n.cls, n.p, sorted(n.drawn)) for n in nodes], skips


def base_stream():
    """Seat 0: opening hand 1..7 (turn 1), scry at record 2 (poison), then a
    draw at turn 2 (id 8), a draw at turn 3 (id 9)."""
    h0 = hand(0, range(1, 8))
    h1 = hand(1, range(101, 108))
    return [
        dec(0, "chooseSpellAbilityToPlay", 0, 1, h0 + h1, [LIB0, LIB0]),
        dec(1, "arrangeForScry", 0, 1, h0 + h1, [LIB0, LIB0]),
        dec(2, "chooseSpellAbilityToPlay", 0, 2, h0 + hand(0, [8]) + h1, [LIB0 - 1, LIB0]),
        dec(3, "chooseSpellAbilityToPlay", 0, 3, h0 + hand(0, [8, 9]) + h1, [LIB0 - 2, LIB0]),
    ]


def test_poison_holds_without_a_mark():
    nodes, skips = run(base_stream())
    assert nodes == []
    assert skips["draw_poisoned"] == 2
    assert "shuffle_cleanse" not in skips


def test_shuffle_mark_cleanses_after_its_own_record():
    # the shuffle lands between records 1 and 2: record 2's draw (id 8) is
    # still judged poisoned (same-gap conservatism), record 3's draw is corrected
    nodes, skips = run(base_stream(), [mark(1.5, 0)])
    assert nodes == [("draw", 0, [9])]
    assert skips["draw_poisoned"] == 1
    assert skips["shuffle_cleanse"] == 1


def test_shuffle_of_the_other_seat_does_not_cleanse():
    nodes, skips = run(base_stream(), [mark(1.5, 1)])
    assert nodes == []
    assert skips["draw_poisoned"] == 2
    assert skips["shuffle_cleanse"] == 1


def test_looked_at_library_card_is_uniform_again_after_a_shuffle():
    # seat 0 sees library card 50 (a library row at record 1), no order
    # method; without a shuffle its draw is not a chance node (a seen card
    # entering the hand is passed over), with one it is a draw node
    h0 = hand(0, range(1, 8))
    h1 = hand(1, range(101, 108))
    seen_top = [ent(50, "Bear", "library", 0)]
    stream = [
        dec(0, "chooseSpellAbilityToPlay", 0, 1, h0 + h1, [LIB0, LIB0]),
        dec(1, "chooseSpellAbilityToPlay", 0, 1, h0 + seen_top + h1, [LIB0, LIB0]),
        dec(2, "chooseSpellAbilityToPlay", 0, 2, h0 + h1, [LIB0, LIB0]),
        dec(3, "chooseSpellAbilityToPlay", 0, 3, h0 + hand(0, [50]) + h1, [LIB0 - 1, LIB0]),
    ]
    nodes, skips = run(stream)
    assert nodes == []
    assert not any(k.startswith("draw_") for k in skips)
    nodes, skips = run(stream, [mark(1.5, 0)])  # the gap before record 2
    assert nodes == [("draw", 0, [50])]
    assert nodes and skips["shuffle_cleanse"] == 1


def test_cards_outside_the_library_stay_seen_through_a_shuffle():
    # a card seen in hand (id 3) that later leaves and re-enters the hand
    # is never a draw, shuffle or not
    h0 = hand(0, range(1, 8))
    h1 = hand(1, range(101, 108))
    h0_minus3 = hand(0, [1, 2, 4, 5, 6, 7])
    stream = [
        dec(0, "chooseSpellAbilityToPlay", 0, 1, h0 + h1, [LIB0, LIB0]),
        dec(
            1,
            "chooseSpellAbilityToPlay",
            0,
            2,
            h0_minus3 + [ent(3, "Forest", "graveyard", 0)] + h1,
            [LIB0, LIB0],
        ),
        dec(2, "chooseSpellAbilityToPlay", 0, 3, h0 + h1, [LIB0, LIB0]),
    ]
    nodes, skips = run(stream, [mark(1.5, 0)])
    assert nodes == []
    assert not any(k.startswith("draw_") for k in skips)


def test_tuck_list_is_cleared_by_a_shuffle():
    # a London put-back (known bottom) is forgotten by a shuffle; the draw
    # after the shuffle at a small library is corrected instead of hitting
    # the bottom margin
    deck = Counter({"Forest": 20, "Bear": 6})  # 26 cards; 6 in hand -> lib 20
    h0 = hand(0, range(1, 7))
    h1 = hand(1, range(101, 108))
    tuck_ents = hand(0, range(1, 8))
    stream = [
        dec(0, "tuckCardsViaMulligan", 0, 0, tuck_ents + h1, [19, LIB0]),
        dec(1, "chooseSpellAbilityToPlay", 0, 1, h0 + h1, [20, LIB0]),
        dec(2, "chooseSpellAbilityToPlay", 0, 2, h0 + hand(0, [8]) + h1, [19, LIB0]),
    ]
    stream[0]["ret"] = [{"e": 7}]
    nodes, skips = run(stream, deck0=deck)
    assert nodes == []
    assert skips["draw_bottom_margin"] == 1
    nodes, skips = run(stream, [mark(0.5, 0)], deck0=deck)  # the gap before record 1
    assert nodes == [("draw", 0, [8])]
