"""M9 D1 veto-knowability instrument: the pure arithmetic — Forge ManaCost
parsing, the backtracking payment matcher, cost-modifying static filters, and
card-script face parsing. The obs-join and population sweeps are validated
live by the accepted-cast validity bar (>= 0.95, pinned in m9-plan D1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from veto_knowability import (  # noqa: E402
    Cost,
    _parse_script,
    _static_applies,
    can_pay,
    cost_from_sa,
    parse_mana_cost,
)

W, U, B, R, G, C = (frozenset(x) for x in "WUBRG C".replace(" ", "C")[:6])
ANY = frozenset("WUBRGC")


def fs(*colors):
    return frozenset(colors)


# ---------------------------------------------------------------- cost parse


def test_parse_simple():
    c = parse_mana_cost("1 B")
    assert c.generic == 1 and c.pips == [fs("B")] and not c.uncertain


def test_parse_no_cost():
    c = parse_mana_cost("no cost")
    assert c.generic == 0 and not c.pips


def test_parse_hybrid_twobrid_phyrexian_x():
    c = parse_mana_cost("2 WU 2R BP X")
    assert c.generic == 2
    assert fs("W", "U") in c.pips
    assert c.twobrid == 1 and c.twobrid_colors == [fs("R")]
    assert c.phyrexian == 1 and c.x == 1 and not c.uncertain


def test_parse_snow_is_uncertain():
    assert parse_mana_cost("2 S").uncertain == "snow"


# ---------------------------------------------------------------- matcher


def test_can_pay_colored_assignment():
    # {W}{W} payable from W + WU, not from W + U
    cost = Cost(pips=[fs("W"), fs("W")])
    assert can_pay(cost, [fs("W"), fs("W", "U")])
    assert not can_pay(cost, [fs("W"), fs("U")])


def test_can_pay_generic_uses_leftovers():
    cost = Cost(generic=2, pips=[fs("B")])
    assert can_pay(cost, [fs("B"), fs("C"), fs("G")])
    assert not can_pay(cost, [fs("B"), fs("C")])


def test_can_pay_constrained_pip_ordering():
    # naive greedy on {W} first would burn the flexible source
    cost = Cost(pips=[fs("W", "U"), fs("W")])
    assert can_pay(cost, [fs("W"), fs("U")])


def test_can_pay_twobrid_branches():
    cost = Cost(twobrid=1, twobrid_colors=[fs("R")])
    assert can_pay(cost, [fs("R")])  # pay with the color
    assert can_pay(cost, [fs("C"), fs("C")])  # or 2 generic
    assert not can_pay(cost, [fs("C")])


def test_can_pay_commander_tax():
    cost = Cost(pips=[fs("U")])
    assert can_pay(cost, [fs("U"), fs("C"), fs("C")], extra_generic=2)
    assert not can_pay(cost, [fs("U"), fs("C")], extra_generic=2)


def test_can_pay_x_and_phyrexian_optimistic():
    # X=0 minimum, phyrexian payable via life — both free
    cost = Cost(x=1, phyrexian=2, pips=[fs("G")])
    assert can_pay(cost, [fs("G")])


# ---------------------------------------------------------------- sa costs


def test_cost_from_sa_stops_at_reminder_text():
    # reminder text repeats the cost — must not double it
    cost, _ = cost_from_sa("Reconfigure {2} ({2}: Attach to target creature)")
    assert cost.generic == 2 and not cost.pips


def test_cost_from_sa_channel():
    cost, free = cost_from_sa(
        "Channel — {3}{R}, Discard Sokenzan: Create two tokens.")
    assert cost.generic == 3 and cost.pips == [fs("R")] and not free


def test_cost_from_sa_tap_only_is_free():
    cost, free = cost_from_sa("{T}: Another target creature gains protection.")
    assert cost.generic == 0 and not cost.pips and "T" in free


# ---------------------------------------------------------------- statics


def test_static_thalia_filter():
    card_noncre = _parse_script("Name:Needle\nManaCost:1\nTypes:Artifact\n")[0]
    card_cre = _parse_script("Name:Bear\nManaCost:1 G\nTypes:Creature Bear\n")[0]
    assert _static_applies("Card.nonCreature", "", 1, 0, card_noncre)
    assert not _static_applies("Card.nonCreature", "", 1, 0, card_cre)


def test_static_activator_you_scoped_to_controller():
    card = _parse_script("Name:X\nManaCost:1\nTypes:Instant\n")[0]
    assert _static_applies("Card", "You", 0, 0, card)
    assert not _static_applies("Card", "You", 1, 0, card)


def test_static_color_filter():
    white = _parse_script("Name:W\nManaCost:1 W\nTypes:Instant\n")[0]
    assert _static_applies("Card.White", "", 1, 0, white)
    assert not _static_applies("Card.Black", "", 1, 0, white)


# ---------------------------------------------------------------- scripts


def test_parse_dual_subtype_land_single_unit():
    # Land Mountain Plains — choose-one, ONE unit of {R,W}, never two sources
    faces = _parse_script("Name:Parlor\nManaCost:no cost\nTypes:Land Mountain Plains\n")
    prod = faces[0].prod
    assert len(prod) == 2  # two subtype alternatives...
    allcolors = frozenset().union(*(c for c, _, _ in prod))
    units = max(a for _, a, _ in prod)
    assert allcolors == fs("R", "W") and units == 1  # ...one unit at classify


def test_parse_amount_two():
    faces = _parse_script(
        "Name:Tomb\nManaCost:no cost\nTypes:Land\n"
        "A:AB$ Mana | Cost$ T | Produced$ C | Amount$ 2 | SpellDescription$ Add {C}{C}.\n")
    (colors, amount, variable), = faces[0].prod
    assert colors == fs("C") and amount == 2 and not variable


def test_parse_chained_mana_ability():
    faces = _parse_script(
        "Name:Filter\nManaCost:no cost\nTypes:Land\n"
        "A:AB$ Mana | Cost$ 1 T | Produced$ Combo B B | SpellDescription$ Add {B}{B}.\n")
    assert faces[0].chained and not faces[0].prod


def test_parse_alternative_cost_flag():
    faces = _parse_script(
        "Name:Daze2\nManaCost:1 U\nTypes:Instant\n"
        "S:Mode$ AlternativeCost | ValidSA$ Spell.Self | Cost$ Return<1/Island>\n")
    assert faces[0].altcost


def test_parse_raise_static():
    faces = _parse_script(
        "Name:Thalia2\nManaCost:1 W\nTypes:Creature Human\n"
        "S:Mode$ RaiseCost | ValidCard$ Card.nonCreature | Type$ Spell | Amount$ 1\n")
    assert faces[0].raises == [(1, "Card.nonCreature", "")]


def test_parse_multiface_both_faces():
    faces = _parse_script(
        "Name:Front\nManaCost:1 U\nTypes:Instant\n"
        "ALTERNATE\n"
        "Name:Back Mire\nManaCost:no cost\nTypes:Land Swamp\n")
    assert [f.name for f in faces] == ["Front", "Back Mire"]
    assert all(f.multiface for f in faces)
    assert faces[1].prod  # back-face land resolves as a source
