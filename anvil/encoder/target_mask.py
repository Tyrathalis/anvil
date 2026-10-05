"""The union target mask (ADR-0122): the fork lists each priority option's
legal targets ("tg" on the option entry — the union over the ability's
targeting nodes: {"e":id} cards, {"pi":seat} players, {"e":hostId,"stk":1}
stack entries; "tg":null = the fork declined to enumerate that option; no
"tg" key = a pre-ADR-0122 record), and the decoder masks its target pointer
to the chosen candidate's set. This module is the one builder both the serve
featurizer and the training loader call, so serve and loader see one mask.

Key space per candidate = [entity rows 0..n) ++ [player positions n..n+P)
++ STOP — the decoder's, in the ITEM's row count (collate re-bases the
player block and STOP onto the padded width). Conventions:

- PASS (candidate 0) and any candidate one of whose collapsed options is
  unmasked (null / absent "tg") allow every key: the mask only ever narrows
  where the fork spoke for every option behind the candidate.
- A candidate collapses several wire options (identical host row + SA text):
  its set is the UNION of theirs — the realizer tries the option the server
  names, and a target legal for any of them is a legal pick.
- A ref whose id is not a row (hidden by the information set, dropped by the
  transform, a hidden-zone candidate) is dropped: the model cannot point at
  what it cannot see. Players map through the ADR-0116 position convention.
- STOP is always open (the realizer's `added < min` veto stays the backstop
  for a required target the model declines to name). An option whose
  required node has no candidate carries "tz":1 — `unfit` — and the serve
  rule may prune it from the candidate set (the loader re-applies from the
  mu row's flag; see apply_target_mask).

Game-agnostic by construction: refs are opaque ids and seats; nothing here
names a zone or a card type.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from anvil.encoder.transform import player_target_position

MASK_FLAG = 1  # mu "tm" bit: the target pointer was masked when sampled
PRUNE_FLAG = 2  # mu "tm" bit: unfit candidates were pruned from the choice


def has_target_union(opts: list[dict[str, Any]]) -> bool:
    """True when any option entry carries the ADR-0122 field (null counts)."""
    return any(isinstance(o, dict) and "tg" in o for o in opts)


def target_allow(
    opts: list[dict[str, Any]],
    cand_opts: list[list[int]],
    row_of: dict[int, int],
    perspective: int,
    n_players: int,
    n_rows: int,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Per-candidate key mask + unfit flags, or None when the record carries
    no union at all (older stores: no narrowing).

    cand_opts[c] = the wire option indices collapsed into candidate c
    (cand 0 = PASS = []). Returns (allow (C, n_rows + n_players + 1) bool,
    unfit (C,) bool)."""
    if not has_target_union(opts):
        return None
    width = n_rows + n_players + 1
    stop = width - 1
    C = len(cand_opts)
    allow = np.zeros((C, width), dtype=bool)
    unfit = np.zeros(C, dtype=bool)
    allow[0, :] = True  # PASS: nothing to point at; the decoder's query is zeroed anyway
    for c in range(1, C):
        members = cand_opts[c]
        if not members:
            allow[c, :] = True
            continue
        open_all = False
        keys: set[int] = set()
        all_unfit = True
        for i in members:
            o = opts[i] if 0 <= i < len(opts) else None
            tg = o.get("tg") if isinstance(o, dict) else None
            if not isinstance(o, dict) or "tg" not in o or tg is None:
                open_all = True  # the fork did not speak for this option
                break
            if not o.get("tz"):
                all_unfit = False
            for ref in tg:
                if not isinstance(ref, dict):
                    continue
                if "e" in ref:
                    r = row_of.get(ref["e"])
                    if r is not None and 0 <= r < n_rows:
                        keys.add(int(r))
                elif "pi" in ref:
                    pi = int(ref["pi"])
                    if 0 <= pi < n_players:
                        keys.add(n_rows + player_target_position(pi, perspective, n_players))
        if open_all:
            allow[c, :] = True
            continue
        for k in keys:
            allow[c, k] = True
        allow[c, stop] = True
        unfit[c] = all_unfit
    return allow, unfit


def union_stats(opts: list[dict[str, Any]]) -> dict[str, int]:
    """Per-window counts for the census / battery: masked, unmasked (by
    reason), legacy (no field), unfit."""
    out: dict[str, int] = {"masked": 0, "unmasked": 0, "legacy": 0, "unfit": 0}
    for o in opts:
        if not isinstance(o, dict) or "tg" not in o:
            out["legacy"] += 1
        elif o["tg"] is None:
            out["unmasked"] += 1
            key = "unmasked_" + str(o.get("tu", "?"))
            out[key] = out.get(key, 0) + 1
        else:
            out["masked"] += 1
            if o.get("tz"):
                out["unfit"] += 1
    return out


def apply_target_mask(ex: dict, aux: dict | None, *, mask: bool, prune: bool) -> int:
    """The consumer's rule over the featurizer's two optional fields.

    The featurizer attaches `tgt_allow` and `cand_unfit` whenever the record
    carries the union; the SERVER applies its flags here and records the
    result as the mu row's "tm" (returned; also set on aux when given), and
    the RL LOADER calls this with the flags read back from "tm" — one rule,
    both sides. `cand_unfit` never reaches the batch."""
    import torch

    flags = 0
    unfit = ex.pop("cand_unfit", None)
    if "tgt_allow" in ex:
        if mask:
            flags |= MASK_FLAG
        else:
            ex.pop("tgt_allow")
    if prune and unfit is not None and bool(unfit.any()):
        base = ex.get("cand_allow")
        if base is None:
            base = torch.ones(unfit.shape[0], dtype=torch.bool)
        ex["cand_allow"] = base & ~unfit
        flags |= PRUNE_FLAG
    if aux is not None:
        aux["tm"] = flags
    return flags
