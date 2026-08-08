"""Pauper pool pipeline — sibling of anvil.pool.dc.

mtgtop8 f=PAU decklists + the Wizards official Pauper banlist -> pool
manifest + Forge .dck files. Unlike DC, Pauper decklist exports carry a real
sideboard (no command-zone hijack) and decks are 60+15 with a 4-of limit
instead of Commander's 100-card singleton. Pool boundary matches the DC
pipeline's pattern: meta-decklist union + flex, not an independent
rarity/common-only filter — legality is implicit in the fetched decklists
already being tournament-legal.
"""

from __future__ import annotations
