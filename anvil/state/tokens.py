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
    def __init__(
        self,
        d_model: int,
        d_card: int,
        n_entity_features: int,
        n_global: int,
        n_players: int,
        n_player_features: int,
        n_methods: int,
        history_k: int,
        n_sa: int = 0,
    ):
        super().__init__()
        self.ent_proj = nn.Linear(d_card + n_entity_features, d_model)
        self.state_proj = nn.Linear(n_global + n_players * n_player_features, d_model)
        # input-layout split for load_compat: global-feature growth (fmt
        # one-hot, M9 boundary) inserts columns at the END of the globals
        # segment, mid-input for state_proj — the pad must insert, not append
        self.n_global = n_global
        self.plan_tok = nn.Parameter(torch.zeros(1, d_model))  # [PLAN] latent (§3)
        # D6 (m9-d6-plan-latent-spec §2): carried plan vector enters through a
        # ZERO-init projection gated by has_plan — day-zero outputs are
        # bit-identical to the static token until the emission loss trains it
        self.plan_proj = nn.Linear(d_model, d_model)
        nn.init.zeros_(self.plan_proj.weight)
        nn.init.zeros_(self.plan_proj.bias)
        self.method_emb = nn.Embedding(n_methods + 2, d_model // 2)  # +OOV +pad(-1)
        self.self_emb = nn.Embedding(2, d_model // 2)
        self.hist_proj = nn.Linear(d_model, d_model)
        self.hist_pos = nn.Parameter(torch.zeros(history_k, d_model))
        # M10 v2 schedule slot tokens (m10-build-spec §2): the discrete carry
        # enters as ≤SCHED_CAP attention-visible tokens appended after
        # history. sched_proj is ZERO-init (weight and bias) — day-zero slot
        # tokens are the zero vector regardless of content (schedule-content
        # invariance, the v2 identity contract case 3); presence itself is
        # measured + banked at the graft smoke, not assumed invisible.
        if n_sa:
            from anvil.training.dataset import SCHED_CAP, SCHED_PAY_CLASSES

            self.sched_sa_emb = nn.Embedding(n_sa + 1, 48)  # +1 = OOV, shared vocab
            self.sched_status_emb = nn.Embedding(4, 16)  # pending/next/done/failed
            self.sched_pos_emb = nn.Embedding(SCHED_CAP, 16)
            self.sched_pay_emb = nn.Embedding(SCHED_PAY_CLASSES, 16)
            self.sched_null_ent = nn.Parameter(torch.randn(d_model) * 0.02)
            self.sched_proj = nn.Linear(d_model + 48 + 16 + 16 + 16 + 1, d_model)
            nn.init.zeros_(self.sched_proj.weight)
            nn.init.zeros_(self.sched_proj.bias)

    def forward(self, card_vecs: torch.Tensor, batch: dict) -> tuple[torch.Tensor, torch.Tensor]:
        """-> (tokens (B, 1+N+K, d), key_padding_mask (B, 1+N+K) True=PAD)."""
        b = card_vecs.shape[0]
        ent = self.ent_proj(torch.cat([card_vecs, batch["entities"]], dim=-1))
        state = self.state_proj(
            torch.cat([batch["globals"], batch["players"].flatten(1)], dim=-1)
        ).unsqueeze(1)

        hist = batch["history"]  # (B, K, 3): method, self, host-row(-1 ok, unused v0)
        method = self.method_emb(
            hist[..., 0].clamp(min=0) + (hist[..., 0] < 0).long() * 0
        )  # pad -> id 0, masked below
        selfsame = self.self_emb(hist[..., 1].clamp(min=0))
        htok = self.hist_proj(torch.cat([method, selfsame], dim=-1)) + self.hist_pos

        plan = self.plan_tok.expand(b, 1, -1)
        pv = batch.get("plan_vec")
        if pv is not None and pv.numel():
            plan = plan + (self.plan_proj(pv) * batch["has_plan"].unsqueeze(-1)).unsqueeze(1)
        seqs = [state, plan, ent, htok]
        pads = [
            torch.zeros(b, 2, dtype=torch.bool, device=ent.device),  # [STATE],[PLAN]
            ~batch["ent_mask"],
            hist[..., 0] < 0,  # unused history slots
        ]
        smask = batch.get("sched_mask")
        if smask is not None:
            # M10 v2 slot tokens: ent token at the slot's current row (the
            # pointer-grounding argument — shared entity representation),
            # sched_null_ent when the entity left the visible zones (row -1).
            # Padding-masked slots (mask False) are invisible to every other
            # token — the mask-closed identity case.
            rows = batch["sched_rows"]  # (B, S), -1 = entity absent
            d = ent.shape[-1]
            ent_vec = ent.gather(1, rows.clamp(min=0).unsqueeze(-1).expand(-1, -1, d))
            ent_vec = torch.where(
                (rows >= 0).unsqueeze(-1), ent_vec, self.sched_null_ent.expand_as(ent_vec)
            )
            s = rows.shape[1]
            pos = torch.arange(s, device=ent.device).unsqueeze(0).expand(b, -1)
            stok = self.sched_proj(
                torch.cat(
                    [
                        ent_vec,
                        self.sched_sa_emb(batch["sched_sa"].clamp(min=0)),
                        self.sched_status_emb(batch["sched_status"].clamp(min=0)),
                        self.sched_pos_emb(pos),
                        self.sched_pay_emb(batch["sched_pay"].clamp(min=0)),
                        batch["sched_afford"].unsqueeze(-1),
                    ],
                    dim=-1,
                )
            )
            seqs.append(stok)
            pads.append(~smask)
        return torch.cat(seqs, dim=1), torch.cat(pads, dim=1)
