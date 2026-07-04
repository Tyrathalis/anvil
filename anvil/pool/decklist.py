"""MTGO-export decklist parsing and Forge .dck emission.

DC convention on mtgtop8: the export's Sideboard section is the command zone
(the format has no sideboard) — one commander, or two for partner pairs.
Anything else fails shape validation. Partner-pairing legality is not checked
here: the engine adjudicates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
          "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
          "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes"}


class ShapeError(ValueError):
    pass


@dataclass
class Deck:
    deck_id: int
    commanders: list[str]  # 1, or 2 for partners; names as printed in the source
    main: list[tuple[int, str]]  # (count, name)
    meta: dict = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.commanders) + sum(c for c, _ in self.main)


def parse_mtgo(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    main: list[tuple[int, str]] = []
    side: list[tuple[int, str]] = []
    target = main
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower() == "sideboard":
            target = side
            continue
        count, _, name = line.partition(" ")
        if not count.isdigit() or not name:
            raise ShapeError(f"unparseable line: {line!r}")
        target.append((int(count), name.strip()))
    return main, side


def deck_from_export(deck_id: int, text: str, meta: dict) -> Deck:
    main, side = parse_mtgo(text)
    if not 1 <= len(side) <= 2 or any(c != 1 for c, _ in side):
        raise ShapeError(f"sideboard is not a command zone (1 commander or partner pair): {side}")
    deck = Deck(deck_id=deck_id, commanders=[n for _, n in side], main=main, meta=meta)
    if deck.size != 100:
        raise ShapeError(f"deck is {deck.size} cards, want 100")
    for count, name in main:
        if count > 1 and name not in BASICS:
            raise ShapeError(f"singleton violation: {count}x {name}")
    return deck


def to_dck(name: str, commanders: list[str], main: list[tuple[int, str]]) -> str:
    """Forge .dck: names only, no set pins — Forge picks printings."""
    lines = ["[metadata]", f"Name={name}", "[Commander]"]
    lines += [f"1 {c}" for c in commanders]
    lines += ["[Main]"]
    lines += [f"{count} {card}" for count, card in main]
    return "\n".join(lines) + "\n"
