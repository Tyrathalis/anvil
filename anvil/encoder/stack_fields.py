"""M12 Build 4 (ADR-0111): the stack-entry fields — the representation's
completion of §J item 10 (a pending trigger's identity and its targets never
reached the model; the encoder fed `stack_size` alone).

Each recorded stack instance (top-first, at most STACK_K) becomes one row:
the host's entity row (-1 = hostless / not in the observation), the ability
key's table row (-1 = outside the table), whether the perspective controls it,
its first card target's entity row and its first player target's seat
position (perspective first). The model adds the entry ADDITIVELY onto the
host's and the targets' tokens through zero-init projections
(anvil.state.tokens.StateAssembler) — no new tokens, day-zero byte-identical.
"""
from __future__ import annotations

import numpy as np

STACK_K = 8  # entries kept, top-first (deeper stacks are rare and the top matters)

STACK_FIELDS = ("stack_rows", "stack_ak", "stack_ctrl", "stack_tgt_rows", "stack_tgt_pi", "stack_mask")


def stack_fields(out: dict, abil, perspective: int) -> dict[str, np.ndarray]:
    """assemble() output (its "stack" + "seats" + "entity_row_of") -> the K-row
    int arrays (+ the bool mask). abil = an AbilityCache or None (-1 keys)."""
    rows = np.full(STACK_K, -1, dtype=np.int64)
    ak = np.full(STACK_K, -1, dtype=np.int64)
    ctrl = np.zeros(STACK_K, dtype=np.int64)
    trows = np.full(STACK_K, -1, dtype=np.int64)
    tpi = np.full(STACK_K, -1, dtype=np.int64)
    mask = np.zeros(STACK_K, dtype=bool)
    row_of = out.get("entity_row_of") or {}
    seats = out.get("seats") or [perspective]
    seat_pos = {s: i for i, s in enumerate(seats)}
    for i, si in enumerate((out.get("stack") or [])[:STACK_K]):
        if not isinstance(si, dict):
            continue
        mask[i] = True
        rows[i] = row_of.get(si.get("e"), -1)
        ak[i] = abil.index(si.get("ak")) if abil is not None else -1
        ctrl[i] = 1 if si.get("c") == perspective else 0
        for t in si.get("tgt") or []:
            if not isinstance(t, dict):
                continue
            if "e" in t and trows[i] < 0:
                trows[i] = row_of.get(t["e"], -1)
            elif "pi" in t and tpi[i] < 0:
                tpi[i] = seat_pos.get(t["pi"], -1)
    return {"stack_rows": rows, "stack_ak": ak, "stack_ctrl": ctrl,
            "stack_tgt_rows": trows, "stack_tgt_pi": tpi, "stack_mask": mask}
