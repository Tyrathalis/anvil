"""State token assembly (design §2, M1 D4): batch -> trunk input sequence.

Sequence layout: [STATE] global token, [PLAN] latent token, then N entity
tokens, then K history tokens. [STATE] is the pooled read-out for the value
head and the pointer query; [PLAN] is the turn-plan latent (§3) — reserved
in the base architecture now (near-zero cost, m1-bc-plan D4), unsupervised
until M2 attaches plan-consistency losses. Entity tokens fuse the card
vector with the dynamic per-entity features (zone/tapped/counters/count/...);
history tokens are method-id + actor-flag embeddings (host linkage arrives
with the target pointer work).
"""

from __future__ import annotations

import torch
from torch import nn


class StateAssembler(nn.Module):
    def __init__(self, d_model: int, d_card: int, n_entity_features: int,
                 n_global: int, n_players: int, n_player_features: int,
                 n_methods: int, history_k: int):
        super().__init__()
        self.ent_proj = nn.Linear(d_card + n_entity_features, d_model)
        self.state_proj = nn.Linear(n_global + n_players * n_player_features, d_model)
        self.plan_tok = nn.Parameter(torch.zeros(1, d_model))  # [PLAN] latent (§3)
        self.method_emb = nn.Embedding(n_methods + 2, d_model // 2)  # +OOV +pad(-1)
        self.self_emb = nn.Embedding(2, d_model // 2)
        self.hist_proj = nn.Linear(d_model, d_model)
        self.hist_pos = nn.Parameter(torch.zeros(history_k, d_model))

    def forward(self, card_vecs: torch.Tensor, batch: dict) -> tuple[torch.Tensor, torch.Tensor]:
        """-> (tokens (B, 1+N+K, d), key_padding_mask (B, 1+N+K) True=PAD)."""
        b = card_vecs.shape[0]
        ent = self.ent_proj(torch.cat([card_vecs, batch["entities"]], dim=-1))
        state = self.state_proj(
            torch.cat([batch["globals"], batch["players"].flatten(1)], dim=-1)).unsqueeze(1)

        hist = batch["history"]  # (B, K, 3): method, self, host-row(-1 ok, unused v0)
        method = self.method_emb(hist[..., 0].clamp(min=0)
                                 + (hist[..., 0] < 0).long() * 0)  # pad -> id 0, masked below
        selfsame = self.self_emb(hist[..., 1].clamp(min=0))
        htok = self.hist_proj(torch.cat([method, selfsame], dim=-1)) + self.hist_pos

        plan = self.plan_tok.expand(b, 1, -1)
        tokens = torch.cat([state, plan, ent, htok], dim=1)
        pad = torch.cat([
            torch.zeros(b, 2, dtype=torch.bool, device=ent.device),   # [STATE],[PLAN]
            ~batch["ent_mask"],
            hist[..., 0] < 0,                                          # unused history slots
        ], dim=1)
        return tokens, pad
