# pyright: basic
from __future__ import annotations

from typing import Any, NotRequired, TypedDict

import torch


class Example(TypedDict, total=True):
    """One model example before batching (serve or training)."""

    entities: torch.Tensor
    ent_emb: torch.Tensor
    globals: torch.Tensor
    players: torch.Tensor
    history: torch.Tensor
    cand_rows: torch.Tensor
    cand_sa: torch.Tensor
    cand_kind: torch.Tensor
    label: torch.Tensor
    label_row: torch.Tensor
    tgt_kind: NotRequired[torch.Tensor]
    tgt_idx: NotRequired[torch.Tensor]
    x_val: torch.Tensor
    task: torch.Tensor
    bool_label: torch.Tensor
    num_label: torch.Tensor
    num_lo: torch.Tensor
    num_hi: torch.Tensor
    ctx_row: torch.Tensor
    forced: torch.Tensor
    has_outcome: torch.Tensor
    won: torch.Tensor
    cmb_rows: torch.Tensor
    cmb_count: torch.Tensor
    cmb_count_label: torch.Tensor
    blk_atk_rows: torch.Tensor
    atk_label: torch.Tensor
    atk_tgt_kind: torch.Tensor
    atk_tgt_idx: torch.Tensor
    blk_label: torch.Tensor


class Batch(TypedDict, total=True):
    """Padded batch produced by dataset.collate()."""

    entities: torch.Tensor
    ent_emb: torch.Tensor
    ent_mask: torch.Tensor
    cand_rows: torch.Tensor
    cand_sa: torch.Tensor
    cand_kind: torch.Tensor
    cand_mask: torch.Tensor
    globals: torch.Tensor
    players: torch.Tensor
    history: torch.Tensor
    label: torch.Tensor
    label_row: torch.Tensor
    tgt_labels: torch.Tensor
    x_val: torch.Tensor
    task: torch.Tensor
    bool_label: torch.Tensor
    num_label: torch.Tensor
    num_lo: torch.Tensor
    num_hi: torch.Tensor
    ctx_row: torch.Tensor
    forced: torch.Tensor
    has_outcome: torch.Tensor
    won: torch.Tensor
    cmb_rows: torch.Tensor
    cmb_mask: torch.Tensor
    cmb_count: torch.Tensor
    cmb_count_label: torch.Tensor
    blk_atk_rows: torch.Tensor
    blk_atk_mask: torch.Tensor
    atk_label: torch.Tensor
    atk_tgt_labels: torch.Tensor
    blk_label: torch.Tensor


class Slot(TypedDict, total=True):
    ex: Example
    pd: float
    nz: dict[str, torch.Tensor] | None
    ev: Any
    out: dict[str, torch.Tensor]
    err: Exception
