"""Offline tests for the DC pool pipeline: parsing, shape gates, name
resolution, .dck emission, banlist section mapping. No network."""

import pytest

from anvil.pool import decklist, forge_db
from anvil.pool.decklist import ShapeError, deck_from_export, parse_mtgo, to_dck
from anvil.pool.fetch import parse_banlist

EXPORT = "\n".join(
    ["1 Command Tower", "96 Forest", "1 Fire / Ice", "1 Lim-Dul's Vault",
     "", "Sideboard", "1 Tasigur, the Golden Fang"]) + "\n"


def test_parse_mtgo_sections():
    main, side = parse_mtgo(EXPORT)
    assert sum(c for c, _ in main) == 99
    assert side == [(1, "Tasigur, the Golden Fang")]


def test_deck_shape_ok():
    deck = deck_from_export(1, EXPORT, {})
    assert deck.commanders == ["Tasigur, the Golden Fang"]
    assert deck.size == 100


def test_partner_pair_ok():
    text = EXPORT.replace("96 Forest", "95 Forest").replace(
        "Sideboard\n1 Tasigur, the Golden Fang",
        "Sideboard\n1 Tana, the Bloodsower\n1 Yoshimaru, Ever Faithful")
    deck = deck_from_export(1, text, {})
    assert deck.commanders == ["Tana, the Bloodsower", "Yoshimaru, Ever Faithful"]
    assert deck.size == 100


@pytest.mark.parametrize("mutation, match", [
    (EXPORT.replace("Sideboard\n1 Tasigur, the Golden Fang", "Sideboard\n1 A\n1 B\n1 C"), "command zone"),
    (EXPORT.replace("Sideboard\n1 Tasigur, the Golden Fang", "Sideboard\n2 A"), "command zone"),
    (EXPORT.replace("96 Forest", "95 Forest"), "100"),
    (EXPORT.replace("1 Command Tower", "2 Command Tower").replace("96 Forest", "95 Forest"), "singleton"),
])
def test_deck_shape_violations(mutation, match):
    with pytest.raises(ShapeError, match=match):
        deck_from_export(1, mutation, {})


def test_basics_exempt_from_singleton():
    deck_from_export(1, EXPORT, {})  # 96 Forest passes


def test_parse_card_names_flavorname_maps_to_primary():
    script = (
        "Name:Rick, Steadfast Leader\n"
        "Variant:UniversesWithin:FlavorName:Greymond, Avacyn's Stalwart\n"
        "ManaCost:2 W W\n")
    names = forge_db.parse_card_names(script)
    assert names["Rick, Steadfast Leader"] == "Rick, Steadfast Leader"
    assert names["Greymond, Avacyn's Stalwart"] == "Rick, Steadfast Leader"


def test_parse_card_names_faces_map_to_themselves():
    script = "Name:Fire\nManaCost:1 R\nAlternateMode:Split\nALTERNATE\nName:Ice\n"
    names = forge_db.parse_card_names(script)
    assert names == {"Fire": "Fire", "Ice": "Ice"}


def test_normalize_diacritics_and_case():
    assert forge_db.normalize("Lim-Dûl's  Vault") == forge_db.normalize("lim-dul's vault")


def test_resolve_ladder():
    universe = {forge_db.normalize(n): n for n in ["Fire", "Ice", "Command Tower", "Lim-Dul's Vault"]}
    assert forge_db.resolve("command tower", universe, {}) == "Command Tower"
    assert forge_db.resolve("Fire / Ice", universe, {}) == "Fire"    # front face
    assert forge_db.resolve("Fire // Ice", universe, {}) == "Fire"
    assert forge_db.resolve("Fire/Ice", universe, {}) == "Fire"     # mtgtop8 spells splits bare
    assert forge_db.resolve("Nonexistent Card", universe, {}) is None
    assert forge_db.resolve("Nonexistent Card", universe, {"Nonexistent Card": "Fire"}) == "Fire"


def test_to_dck_format():
    dck = to_dck("dc-1", ["Tasigur, the Golden Fang"], [(1, "Command Tower"), (96, "Forest")])
    assert dck.splitlines()[:5] == [
        "[metadata]", "Name=dc-1", "[Commander]", "1 Tasigur, the Golden Fang", "[Main]"]
    assert "96 Forest" in dck
    partner = to_dck("dc-2", ["Tana, the Bloodsower", "Yoshimaru, Ever Faithful"], [(98, "Forest")])
    assert partner.splitlines()[2:6] == [
        "[Commander]", "1 Tana, the Bloodsower", "1 Yoshimaru, Ever Faithful", "[Main]"]


def test_banlist_section_attribution():
    html = """
    <h2>🚫 Banned in Deck</h2>
    <div data-card-name="Ancestral Recall"></div>
    <h2>⛔ Banned as Commander only</h2>
    <div data-card-name="Edgar Markov"></div>
    <h2>✅ Recently Unbanned</h2>
    <div data-card-name="Tasigur, the Golden Fang"></div>
    <h3>Something</h3><div data-card-name="${data.card_name}"></div>
    """
    cards = parse_banlist(html)
    assert {"name": "Ancestral Recall", "kind": "banned", "section": "Banned in Deck"} in cards
    assert {"name": "Edgar Markov", "kind": "banned_commander", "section": "Banned as Commander only"} in cards
    names = [c["name"] for c in cards]
    assert "Tasigur, the Golden Fang" not in names  # unbanned section is informational
    assert "${data.card_name}" not in names
