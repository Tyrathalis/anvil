"""Offline tests for the Pauper pool pipeline: parsing, shape gates, .dck
emission, banlist section parsing. No network. Shared pieces (forge_db name
resolution, CURRENT-pin mechanics) are covered by test_pool.py."""

import pytest

from anvil.pool.pauper.decklist import ShapeError, deck_from_export, parse_mtgo, to_dck
from anvil.pool.pauper.fetch import parse_banlist

EXPORT = "4 Counterspell\n4 Ephemerate\n56 Island" + "\n"


def test_parse_mtgo_no_sideboard():
    main, side = parse_mtgo(EXPORT)
    assert sum(c for c, _ in main) == 64
    assert side == []


def test_parse_mtgo_with_real_sideboard():
    text = EXPORT + "Sideboard\n3 Hydroblast\n2 Dust to Dust\n"
    _main, side = parse_mtgo(text)
    assert side == [(3, "Hydroblast"), (2, "Dust to Dust")]


def test_deck_shape_ok():
    text = "4 Counterspell\n56 Island" + "\n"
    deck = deck_from_export(1, text, {})
    assert deck.main_size == 60
    assert deck.sideboard_size == 0


def test_deck_shape_with_sideboard_ok():
    text = "4 Counterspell\n56 Island\n\nSideboard\n3 Hydroblast" + "\n"
    deck = deck_from_export(1, text, {})
    assert deck.sideboard_size == 3


def test_main_deck_size_violation():
    text = "4 Counterspell\n50 Island" + "\n"
    with pytest.raises(ShapeError, match="60"):
        deck_from_export(1, text, {})


def test_sideboard_too_large():
    side = "\n".join(f"1 Card{i}" for i in range(16))
    text = f"4 Counterspell\n56 Island\n\nSideboard\n{side}" + "\n"
    with pytest.raises(ShapeError, match="15"):
        deck_from_export(1, text, {})


def test_four_of_limit():
    text = "5 Counterspell\n55 Island" + "\n"
    with pytest.raises(ShapeError, match="4x"):
        deck_from_export(1, text, {})


def test_basics_exempt_from_four_of_limit():
    text = "4 Counterspell\n56 Island" + "\n"
    deck_from_export(1, text, {})  # 56 Island passes


def test_to_dck_format():
    dck = to_dck("pau-1", [(4, "Counterspell"), (56, "Island")], [(3, "Hydroblast")])
    assert dck.splitlines()[:3] == ["[metadata]", "Name=pau-1", "[Main]"]
    assert "56 Island" in dck
    assert "[Sideboard]" in dck
    assert "3 Hydroblast" in dck


def test_to_dck_no_sideboard_section_when_empty():
    dck = to_dck("pau-1", [(60, "Island")], [])
    assert "[Sideboard]" not in dck


def test_banlist_section_parsing():
    html = """
    <section id="Pauper-banned"><h3>Pauper Banned Cards</h3>
    <p>The following cards are banned in this format:</p>
    <ul>
    <li>All cards that bring a sticker or an Attraction into the game are banned. For a full list of cards, click <a href="x">here</a>.</li>
    <li>Cranial Plating</li>
    <li>Grapeshot</li>
    </ul>
    </section>
    """
    cards = parse_banlist(html)
    names = [c["name"] for c in cards]
    assert "Cranial Plating" in names
    assert "Grapeshot" in names
    assert not any("sticker" in n.lower() for n in names)
