"""Duel Commander pool pipeline (docs/design/dc-pool-pipeline.md).

mtgtop8 f=EDH decklists + duelcommander.com banlist -> pool manifest +
Forge .dck files. This is the original v0 pool pipeline; format="dc" is
the default everywhere in anvil.pool for backward compatibility.
"""

from __future__ import annotations
