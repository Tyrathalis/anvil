"""Card-text extraction for the embedding cache (D4)."""

from anvil.encoder.cardtext import _brace_cost, parse_faces, render

MDFC = """Name:Valki, God of Lies
ManaCost:1 B
Types:Legendary Creature God
PT:2/1
T:Mode$ ChangesZone | Origin$ Any | TriggerDescription$ irrelevant engine line
Oracle:When Valki enters, each opponent reveals their hand.\\n{X}: Choose.

ALTERNATE

Name:Tibalt, Cosmic Impostor
ManaCost:5 B R
Types:Legendary Planeswalker Tibalt
Loyalty:5
Oracle:As Tibalt enters, you get an emblem.
"""


def test_parse_faces_mdfc():
    faces = parse_faces(MDFC)
    assert [f["name"] for f in faces] == ["Valki, God of Lies", "Tibalt, Cosmic Impostor"]
    assert faces[0]["pt"] == "2/1"
    assert faces[1]["loyalty"] == "5"


def test_render_both_faces_one_text():
    text = render(parse_faces(MDFC))
    assert "Name: Valki, God of Lies" in text
    assert "Name: Tibalt, Cosmic Impostor" in text
    assert "--- other face ---" in text
    assert "Cost: {1}{B}" in text and "Cost: {5}{B}{R}" in text
    # oracle \n unescaped, engine script lines never leak into the text
    assert "{X}: Choose." in text
    assert "TriggerDescription" not in text


def test_brace_cost():
    assert _brace_cost("4") == "{4}"
    assert _brace_cost("1 B") == "{1}{B}"
    assert _brace_cost("no cost") == "no cost"
    assert _brace_cost("2/W 2/W") == "{2/W}{2/W}"
