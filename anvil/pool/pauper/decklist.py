"""MTGO-export decklist parsing and Forge .dck emission for Pauper.

Unlike DC, the export's Sideboard section IS a real sideboard (no command
zone hijack): 60-card main deck (4-of limit, basics exempt), up to 15-card
sideboard. Rarity/common-only legality is NOT re-checked here — the pool
boundary matches anvil.pool.dc's meta-decklist-union pattern (legality is
implicit in the fetched decklists already being tournament-legal), and
color-identity-style checks the engine adjudicates at game setup.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BASICS = {
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    "Wastes",
    "Snow-Covered Plains",
    "Snow-Covered Island",
    "Snow-Covered Swamp",
    "Snow-Covered Mountain",
    "Snow-Covered Forest",
    "Snow-Covered Wastes",
}

MAIN_SIZE = 60
MAX_COPIES = 4
MAX_SIDEBOARD = 15


class ShapeError(ValueError):
    pass


@dataclass
class Deck:
    deck_id: int
    main: list[tuple[int, str]]  # (count, name)
    sideboard: list[tuple[int, str]]  # (count, name)
    meta: dict = field(default_factory=dict)

    @property
    def main_size(self) -> int:
        return sum(c for c, _ in self.main)

    @property
    def sideboard_size(self) -> int:
        return sum(c for c, _ in self.sideboard)


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
    deck = Deck(deck_id=deck_id, main=main, sideboard=side, meta=meta)
    if deck.main_size != MAIN_SIZE:
        raise ShapeError(f"main deck is {deck.main_size} cards, want {MAIN_SIZE}")
    if deck.sideboard_size > MAX_SIDEBOARD:
        raise ShapeError(f"sideboard is {deck.sideboard_size} cards, want <= {MAX_SIDEBOARD}")
    for count, name in main + side:
        if count > MAX_COPIES and name not in BASICS:
            raise ShapeError(f"more than {MAX_COPIES}x non-basic: {count}x {name}")
    return deck


def to_dck(name: str, main: list[tuple[int, str]], sideboard: list[tuple[int, str]]) -> str:
    """Forge .dck: names only, no set pins — Forge picks printings."""
    lines = ["[metadata]", f"Name={name}", "[Main]"]
    lines += [f"{count} {card}" for count, card in main]
    if sideboard:
        lines += ["[Sideboard]"]
        lines += [f"{count} {card}" for count, card in sideboard]
    return "\n".join(lines) + "\n"
