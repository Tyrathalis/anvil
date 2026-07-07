"""Card encoder (design §1, M1 D4): frozen text embedding + structured
features + ID embedding -> 2-layer MLP fusion -> d_card.

The text table is a frozen buffer (the embedding model never ships at
inference; ageing is §1's distillation escape hatch). Row -1 = "no card
text" (hidden identity, tokens/emblems): a learned null vector, so hidden
rows are represented without leaking anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn


class CardEncoder(nn.Module):
    def __init__(self, embedding_stem: str | Path, features: torch.Tensor,
                 d_card: int = 256, d_id: int = 48):
        super().__init__()
        from safetensors.torch import load_file
        meta = json.loads(Path(f"{embedding_stem}.json").read_text())
        text = load_file(f"{embedding_stem}.safetensors")["embeddings"].float()
        n, d_text = text.shape
        assert features.shape[0] == n, "feature table must align with the embedding cache"
        self.meta = meta
        self.register_buffer("text", text)              # frozen (n, d_text)
        self.register_buffer("feats", features.float()) # frozen (n, d_feat)
        self.null_text = nn.Parameter(torch.zeros(d_text))
        self.null_feats = nn.Parameter(torch.zeros(features.shape[1]))
        self.id_emb = nn.Embedding(n + 1, d_id)         # +1 = the no-card id
        # start the ID (memorization) channel at text-embedding volume
        # (~1/sqrt(d_text)); default N(0,1) init hands it a ~60x head start
        # over the generalization channel
        nn.init.normal_(self.id_emb.weight, std=0.02)
        d_in = d_text + features.shape[1] + d_id
        self.fuse = nn.Sequential(
            nn.Linear(d_in, 2 * d_card), nn.GELU(), nn.Linear(2 * d_card, d_card))

    def forward(self, rows: torch.Tensor) -> torch.Tensor:
        """rows (..., ) int64, -1 = no card -> (..., d_card)."""
        safe = rows.clamp(min=0)
        known = (rows >= 0).unsqueeze(-1)
        text = torch.where(known, self.text[safe], self.null_text)
        feats = torch.where(known, self.feats[safe], self.null_feats)
        ids = self.id_emb(torch.where(rows >= 0, rows, torch.full_like(rows, self.id_emb.num_embeddings - 1)))
        return self.fuse(torch.cat([text, feats, ids], dim=-1))
