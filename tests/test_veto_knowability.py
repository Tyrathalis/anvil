"""M9 D1 veto-knowability instrument: the pure arithmetic — Forge ManaCost
parsing, the backtracking payment matcher, cost-modifying static filters, and
card-script face parsing. The obs-join and population sweeps are validated
live by the accepted-cast validity bar (>= 0.95, pinned in m9-plan D1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from veto_knowability import (  # noqa: E402
    CardInfo,
    Cost,
    ProdUnit,
    _parse_script,
    _static_applies,
    can_pay,
    classify_window,
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
    allcolors = frozenset().union(*(u.colors for u in prod))
    units = max(u.amount for u in prod)
    assert allcolors == fs("R", "W") and units == 1  # ...one unit at classify


def test_parse_amount_two():
    faces = _parse_script(
        "Name:Tomb\nManaCost:no cost\nTypes:Land\n"
        "A:AB$ Mana | Cost$ T | Produced$ C | Amount$ 2 | SpellDescription$ Add {C}{C}.\n")
    u, = faces[0].prod
    assert u.colors == fs("C") and u.amount == 2 and not u.variable
    assert u.needs_tap and not u.conditional and u.zone == "battlefield"


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


def test_parse_restricted_production_is_conditional():
    # Delighted Halfling shape: unconditional {C} + RestrictValid any-color
    faces = _parse_script(
        "Name:Halfling2\nManaCost:G\nTypes:Creature Halfling\n"
        "A:AB$ Mana | Cost$ T | Produced$ C | SpellDescription$ Add {C}.\n"
        "A:AB$ Mana | Cost$ T | Produced$ Any | RestrictValid$ Spell.Legendary"
        " | SpellDescription$ Add one mana of any color.\n")
    uncond, cond = faces[0].prod
    assert not uncond.conditional and uncond.colors == fs("C")
    assert cond.conditional and cond.colors == ANY


def test_parse_tapxtype_cost_is_conditional_not_tap():
    # Urza shape: taps OTHER permanents — board-dependent, not sickness-gated
    faces = _parse_script(
        "Name:Urza2\nManaCost:2 U U\nTypes:Legendary Creature Human\n"
        "A:AB$ Mana | Cost$ tapXType<1/Artifact> | Produced$ U"
        " | SpellDescription$ Add {U}.\n")
    u, = faces[0].prod
    assert u.conditional and not u.needs_tap


def test_parse_activation_zone_scoping():
    # Simian shape: hand-activated -> zone "hand"; graveyard-activated -> out
    faces = _parse_script(
        "Name:Ape2\nManaCost:2 R\nTypes:Creature Ape\n"
        "A:AB$ Mana | Cost$ ExileFromHand<1/CARDNAME> | Produced$ R"
        " | ActivationZone$ Hand | SpellDescription$ Add {R}.\n")
    u, = faces[0].prod
    assert u.zone == "hand" and not u.needs_tap
    faces = _parse_script(
        "Name:Gy\nManaCost:B\nTypes:Creature Spirit\n"
        "A:AB$ Mana | Cost$ ExileFromGrave<1/CARDNAME> | Produced$ B"
        " | ActivationZone$ Graveyard | SpellDescription$ Add {B}.\n")
    assert not faces[0].prod


def test_parse_basic_land_intrinsic_needs_tap():
    faces = _parse_script("Name:F1\nManaCost:no cost\nTypes:Basic Land Forest\n")
    u, = faces[0].prod
    assert u.needs_tap and not u.conditional and u.colors == fs("G")


def test_parse_multiface_both_faces():
    faces = _parse_script(
        "Name:Front\nManaCost:1 U\nTypes:Instant\n"
        "ALTERNATE\n"
        "Name:Back Mire\nManaCost:no cost\nTypes:Land Swamp\n")
    assert [f.name for f in faces] == ["Front", "Back Mire"]
    assert all(f.multiface for f in faces)
    assert faces[1].prod  # back-face land resolves as a source


# ------------------------------------------------------- classify (sick-aware)


def _dork(name="Dork", colors=("G",)):
    return CardInfo(name, parse_mana_cost("G"), "Creature Elf",
                    [ProdUnit(fs(*colors), 1, False, True, False, "battlefield")])


def _window(table, ents, pick_sa, pick_e, reason="unpayable", kind="spell"):
    cen = {"veto": reason, "pick": pick_sa}
    dec = {"p": 0, "obs": {"glob": {"ph": "MAIN1", "ap": 0}, "ents": ents,
                           "players": [{"cmdcast": [0]}, {"cmdcast": [0]}]},
           "opts": [{"sa": pick_sa, "e": 1, "kind": kind}]}
    return classify_window(cen, dec, table)


def test_classify_sick_source_is_knowable():
    # cast needs G; only source is a summoning-sick dork -> knowable via flag
    table = {"Dork": _dork(), "Bear": CardInfo("Bear", parse_mana_cost("G"),
                                               "Creature Bear")}
    ents = [{"e": 1, "n": "Bear", "z": "hand", "c": 0},
            {"e": 2, "n": "Dork", "z": "battlefield", "c": 0, "sick": 1}]
    res = _window(table, ents, "Bear - Creature 2 / 2", 1)
    assert (res["verdict"], res["why"]) == ("knowable", "sickness_short")


def test_classify_nonsick_source_is_payable_artifact():
    # same board, dork NOT sick -> arithmetic says payable -> auto-payer artifact
    table = {"Dork": _dork(), "Bear": CardInfo("Bear", parse_mana_cost("G"),
                                               "Creature Bear")}
    ents = [{"e": 1, "n": "Bear", "z": "hand", "c": 0},
            {"e": 2, "n": "Dork", "z": "battlefield", "c": 0}]
    res = _window(table, ents, "Bear - Creature 2 / 2", 1)
    assert (res["verdict"], res["why"]) == ("not_knowable", "obs_says_payable")


def test_classify_conditional_production_is_uncertain():
    # payable only through RestrictValid production -> uncertain, either way
    table = {"Halfling": CardInfo(
        "Halfling", parse_mana_cost("G"), "Creature Halfling",
        [ProdUnit(ANY, 1, False, True, True, "battlefield")]),
        "Bear": CardInfo("Bear", parse_mana_cost("G"), "Creature Bear")}
    ents = [{"e": 1, "n": "Bear", "z": "hand", "c": 0},
            {"e": 2, "n": "Halfling", "z": "battlefield", "c": 0}]
    res = _window(table, ents, "Bear - Creature 2 / 2", 1)
    assert (res["verdict"], res["why"]) == ("uncertain", "conditional_production")


def test_classify_sick_tap_ability_is_knowable():
    # {T} ability picked on a summoning-sick host -> knowable from the flag
    table = {"Mom": CardInfo("Mom", parse_mana_cost("W"), "Creature Human")}
    ents = [{"e": 1, "n": "Mom", "z": "battlefield", "c": 0, "sick": 1}]
    res = _window(table, ents, "Mom - {T}: target creature you control",
                  1, kind="ability")
    assert (res["verdict"], res["why"]) == ("knowable", "ability_sick")


def test_classify_hand_activated_source_counts():
    # Simian-from-hand pays {R} -> obs says payable, not knowable-short
    table = {"Ape": CardInfo("Ape", parse_mana_cost("2 R"), "Creature Ape",
                             [ProdUnit(fs("R"), 1, False, False, False, "hand")]),
             "Bolt": CardInfo("Bolt", parse_mana_cost("R"), "Instant")}
    ents = [{"e": 1, "n": "Bolt", "z": "hand", "c": 0},
            {"e": 2, "n": "Ape", "z": "hand", "c": 0}]
    res = _window(table, ents, "Bolt - deal 3 damage", 1)
    assert (res["verdict"], res["why"]) == ("not_knowable", "obs_says_payable")


def test_classify_tapped_or_sick_variable_source_cannot_rescue():
    # a tapped (or sick) Cradle-class source can't make the cast payable ->
    # the knowable verdict must NOT downgrade to variable_amount_source
    cradle = CardInfo("Cradle", parse_mana_cost("no cost"),
                      "Legendary Land Creature",
                      [ProdUnit(fs("G"), 1, True, True, False, "battlefield")])
    table = {"Cradle": cradle,
             "Bear": CardInfo("Bear", parse_mana_cost("G"), "Creature Bear")}
    # tapped: excluded from every view -> plain knowable, no downgrade
    ents = [{"e": 1, "n": "Bear", "z": "hand", "c": 0},
            {"e": 2, "n": "Cradle", "z": "battlefield", "c": 0, "tap": 1}]
    res = _window(table, ents, "Bear - Creature 2 / 2", 1)
    assert (res["verdict"], res["why"]) == ("knowable", "generic_short"), res
    # sick: unusable this turn regardless of amount -> knowable via the flag
    ents = [{"e": 1, "n": "Bear", "z": "hand", "c": 0},
            {"e": 2, "n": "Cradle", "z": "battlefield", "c": 0, "sick": 1}]
    res = _window(table, ents, "Bear - Creature 2 / 2", 1)
    assert (res["verdict"], res["why"]) == ("knowable", "sickness_short"), res
    # untapped, non-sick, cost above the parsed 1-unit floor: the variable
    # amount genuinely might pay -> uncertain
    table["Ox"] = CardInfo("Ox", parse_mana_cost("2 G"), "Creature Ox")
    ents = [{"e": 1, "n": "Ox", "z": "hand", "c": 0},
            {"e": 2, "n": "Cradle", "z": "battlefield", "c": 0}]
    res = _window(table, ents, "Ox - Creature 4 / 4", 1)
    assert (res["verdict"], res["why"]) == ("uncertain", "variable_amount_source")
