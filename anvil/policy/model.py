"""AnvilNet v0 (M1 D4): encoder + trunk + rung-1 heads.

Trunk: pre-LN transformer encoder, d=512, 8 heads, 10 layers (plan band
8-12). Heads at v0: priority pointer (PASS + candidate source rows — the
first stage of the rung-1 autoregressive decomposition; targets/X/modes
sub-heads land next) and the win-prob value head. The turn-plan latent
(§3) enters as a second read-out token when the target pointer lands.
"""

from __future__ import annotations

import torch
from torch import nn

from anvil.encoder.cards import CardEncoder
from anvil.state.tokens import StateAssembler


class AnvilNet(nn.Module):
    def __init__(self, card_encoder: CardEncoder, n_entity_features: int,
                 n_global: int, n_players: int, n_player_features: int,
                 n_methods: int, history_k: int,
                 d_model: int = 512, n_heads: int = 8, n_layers: int = 10):
        super().__init__()
        self.cards = card_encoder
        d_card = card_encoder.fuse[-1].out_features
        self.assemble = StateAssembler(d_model, d_card, n_entity_features,
                                       n_global, n_players, n_player_features,
                                       n_methods, history_k)
        layer = nn.TransformerEncoderLayer(
            d_model, n_heads, dim_feedforward=4 * d_model, activation="gelu",
            batch_first=True, norm_first=True, dropout=0.0)
        self.trunk = nn.TransformerEncoder(layer, n_layers)
        self.pass_head = nn.Sequential(nn.Linear(d_model, d_model), nn.GELU(),
                                       nn.Linear(d_model, 1))
        self.ptr_query = nn.Linear(d_model, d_model)
        self.ptr_key = nn.Linear(d_model, d_model)
        self.value_head = nn.Sequential(nn.Linear(d_model, d_model), nn.GELU(),
                                        nn.Linear(d_model, 1))
        # target decoder (rung 1, autoregressive over T_MAX+1 slots incl. STOP)
        from anvil.training.dataset import T_MAX, TASKS, X_CLASSES
        self.t_max = T_MAX
        self.tgt_query = nn.Linear(3 * d_model, d_model)
        self.tgt_key = nn.Linear(d_model, d_model)
        self.player_key = nn.Linear(6, d_model)   # PLAYER_FEATURES -> key/vec
        self.stop_key = nn.Parameter(torch.randn(d_model) / d_model ** 0.5)
        self.slot_emb = nn.Parameter(torch.zeros(T_MAX + 1, d_model))
        self.x_head = nn.Sequential(nn.Linear(2 * d_model, d_model), nn.GELU(),
                                    nn.Linear(d_model, X_CLASSES))
        # one-field heads (rung-1 family: mull_keep/trigger/binary as bools,
        # number as [lo,hi]-masked classes); input = [STATE] ⊕ ctx-entity ⊕ task
        self.task_emb = nn.Embedding(len(TASKS), 64)
        self.bool_head = nn.Sequential(nn.Linear(2 * d_model + 64, d_model),
                                       nn.GELU(), nn.Linear(d_model, 1))
        self.num_head = nn.Sequential(nn.Linear(2 * d_model + 64, d_model),
                                      nn.GELU(), nn.Linear(d_model, X_CLASSES))

    def forward(self, batch: dict) -> dict:
        card_vecs = self.cards(batch["ent_emb"])
        tokens, pad = self.assemble(card_vecs, batch)
        out = self.trunk(tokens, src_key_padding_mask=pad)
        state = out[:, 0]                       # [STATE] read-out
        plan = out[:, 1]                        # [PLAN] latent (unsupervised at M1)
        n_ent = batch["entities"].shape[1]
        ent_out = out[:, 2:2 + n_ent]           # entity token outputs

        # pointer logits over candidates: index 0 = PASS, rest gather rows
        q = self.ptr_query(state).unsqueeze(1)                    # (B,1,d)
        k = self.ptr_key(ent_out)                                 # (B,N,d)
        rows = batch["cand_rows"].clamp(min=0)                    # (B,C); 0-safe gather
        k_cand = k.gather(1, rows.unsqueeze(-1).expand(-1, -1, k.shape[-1]))
        logits = (q * k_cand).sum(-1) / k.shape[-1] ** 0.5        # (B,C)
        pass_logit = self.pass_head(state)                        # (B,1)
        logits = torch.cat([pass_logit, logits[:, 1:]], dim=1)    # slot 0 = PASS
        logits = logits.masked_fill(~batch["cand_mask"], -1e9)

        # ---- teacher-forced target decoder + X head (cast windows only) ----
        # source vector: entity output at the labeled source row (pass -> zeros)
        rows_src = batch["cand_rows"].gather(1, batch["label"].unsqueeze(1)).clamp(min=0)
        src_vec = ent_out.gather(1, rows_src.unsqueeze(-1).expand(-1, -1, ent_out.shape[-1]))
        src_vec = src_vec.squeeze(1) * (batch["label"] > 0).unsqueeze(-1)

        p_keys = self.player_key(batch["players"])                # (B,P,d)
        keys = torch.cat([self.tgt_key(ent_out), p_keys,
                          self.stop_key.expand(ent_out.shape[0], 1, -1)], dim=1)
        vecs = torch.cat([ent_out, p_keys,
                          torch.zeros_like(p_keys[:, :1])], dim=1)  # STOP adds nothing
        pad = torch.cat([~batch["ent_mask"],
                         torch.zeros(ent_out.shape[0], p_keys.shape[1] + 1,
                                     dtype=torch.bool, device=ent_out.device)], dim=1)
        tgt_logits = []
        prev = torch.zeros_like(src_vec)
        d = keys.shape[-1]
        for t in range(self.t_max + 1):
            q = self.tgt_query(torch.cat([state, src_vec, prev], dim=-1)) + self.slot_emb[t]
            lg = (keys @ q.unsqueeze(-1)).squeeze(-1) / d ** 0.5
            lg = lg.masked_fill(pad, -1e9)
            tgt_logits.append(lg)
            if t < self.t_max:  # teacher-force the true pick into prev
                lab = batch["tgt_labels"][:, t].clamp(min=0)
                picked = vecs.gather(1, lab.unsqueeze(-1).unsqueeze(-1)
                                     .expand(-1, -1, vecs.shape[-1])).squeeze(1)
                prev = prev + picked * (batch["tgt_labels"][:, t] >= 0).unsqueeze(-1)
        tgt_logits = torch.stack(tgt_logits, dim=1)               # (B, T+1, N+P+1)

        x_logits = self.x_head(torch.cat([state, src_vec], dim=-1))

        # one-field heads: ctx entity output (zeros when ctx_row = -1) + task emb
        ctx = ent_out.gather(1, batch["ctx_row"].clamp(min=0).unsqueeze(-1).unsqueeze(-1)
                             .expand(-1, -1, ent_out.shape[-1])).squeeze(1)
        ctx = ctx * (batch["ctx_row"] >= 0).unsqueeze(-1)
        of_in = torch.cat([state, ctx, self.task_emb(batch["task"])], dim=-1)
        bool_logit = self.bool_head(of_in).squeeze(-1)
        num_logits = self.num_head(of_in)
        rng = torch.arange(num_logits.shape[-1], device=num_logits.device)
        num_logits = num_logits.masked_fill(
            (rng < batch["num_lo"].unsqueeze(-1)) | (rng > batch["num_hi"].unsqueeze(-1)), -1e9)

        return {"policy_logits": logits, "tgt_logits": tgt_logits, "x_logits": x_logits,
                "bool_logit": bool_logit, "num_logits": num_logits, "plan": plan,
                "value_logit": self.value_head(state).squeeze(-1)}

    @torch.no_grad()
    def act(self, batch: dict, pass_delta: float = 0.0) -> dict:
        """Greedy inference (M1 D8 serve path). Mirrors forward()'s encode and
        pointer plumbing but conditions the target decoder on the MODEL's
        candidate choice and feeds its own picks back (forward teacher-forces
        both). pass_delta is the post-hoc PASS-boundary calibration knob
        (calibrate_pass.py). Any change to forward()'s tensor plumbing must
        land here too."""
        card_vecs = self.cards(batch["ent_emb"])
        tokens, pad = self.assemble(card_vecs, batch)
        out = self.trunk(tokens, src_key_padding_mask=pad)
        state = out[:, 0]
        n_ent = batch["entities"].shape[1]
        ent_out = out[:, 2:2 + n_ent]

        q = self.ptr_query(state).unsqueeze(1)
        k = self.ptr_key(ent_out)
        rows = batch["cand_rows"].clamp(min=0)
        k_cand = k.gather(1, rows.unsqueeze(-1).expand(-1, -1, k.shape[-1]))
        logits = (q * k_cand).sum(-1) / k.shape[-1] ** 0.5
        pass_logit = self.pass_head(state) + pass_delta
        logits = torch.cat([pass_logit, logits[:, 1:]], dim=1)
        logits = logits.masked_fill(~batch["cand_mask"], -1e9)
        choice = logits.argmax(1)

        rows_src = batch["cand_rows"].gather(1, choice.unsqueeze(1)).clamp(min=0)
        src_vec = ent_out.gather(1, rows_src.unsqueeze(-1).expand(-1, -1, ent_out.shape[-1]))
        src_vec = src_vec.squeeze(1) * (choice > 0).unsqueeze(-1)

        p_keys = self.player_key(batch["players"])
        keys = torch.cat([self.tgt_key(ent_out), p_keys,
                          self.stop_key.expand(ent_out.shape[0], 1, -1)], dim=1)
        vecs = torch.cat([ent_out, p_keys, torch.zeros_like(p_keys[:, :1])], dim=1)
        kpad = torch.cat([~batch["ent_mask"],
                          torch.zeros(ent_out.shape[0], p_keys.shape[1] + 1,
                                      dtype=torch.bool, device=ent_out.device)], dim=1)
        d = keys.shape[-1]
        stop_idx = n_ent + p_keys.shape[1]
        prev = torch.zeros_like(src_vec)
        stopped = torch.zeros(ent_out.shape[0], dtype=torch.bool, device=ent_out.device)
        picks = []
        for t in range(self.t_max + 1):
            qv = self.tgt_query(torch.cat([state, src_vec, prev], dim=-1)) + self.slot_emb[t]
            lg = (keys @ qv.unsqueeze(-1)).squeeze(-1) / d ** 0.5
            lg = lg.masked_fill(kpad, -1e9)
            pick = torch.where(stopped, torch.full_like(lg.argmax(-1), stop_idx),
                               lg.argmax(-1))
            picks.append(pick)
            stopped = stopped | (pick == stop_idx)
            picked = vecs.gather(1, pick.unsqueeze(-1).unsqueeze(-1)
                                 .expand(-1, -1, vecs.shape[-1])).squeeze(1)
            prev = prev + picked  # STOP's vec is zeros; post-stop slots add nothing

        x_cls = self.x_head(torch.cat([state, src_vec], dim=-1)).argmax(-1)

        ctx = ent_out.gather(1, batch["ctx_row"].clamp(min=0).unsqueeze(-1).unsqueeze(-1)
                             .expand(-1, -1, ent_out.shape[-1])).squeeze(1)
        ctx = ctx * (batch["ctx_row"] >= 0).unsqueeze(-1)
        of_in = torch.cat([state, ctx, self.task_emb(batch["task"])], dim=-1)
        num_logits = self.num_head(of_in)
        rng = torch.arange(num_logits.shape[-1], device=num_logits.device)
        num_logits = num_logits.masked_fill(
            (rng < batch["num_lo"].unsqueeze(-1)) | (rng > batch["num_hi"].unsqueeze(-1)), -1e9)

        return {"choice": choice, "tgt_picks": torch.stack(picks, dim=1),
                "x_cls": x_cls, "n_ent": n_ent, "stop_idx": stop_idx,
                "bool": self.bool_head(of_in).squeeze(-1) > 0,
                "num": num_logits.argmax(-1),
                "win": torch.sigmoid(self.value_head(state).squeeze(-1))}

    def losses(self, batch: dict, pass_weight: float = 1.0, tgt_weight: float = 1.0,
               x_weight: float = 0.5, value_weight: float = 0.5,
               onefield_weight: float = 0.5) -> dict:
        out = self(batch)
        prio = batch["task"] == 0
        ce = nn.functional.cross_entropy(out["policy_logits"], batch["label"],
                                         reduction="none")
        w = torch.where(batch["label"] == 0, torch.full_like(ce, pass_weight),
                        torch.ones_like(ce)) * prio.float()
        policy = (ce * w).sum() / w.sum().clamp(min=1e-6)

        tl = out["tgt_logits"]
        target = nn.functional.cross_entropy(
            tl.flatten(0, 1), batch["tgt_labels"].flatten(), ignore_index=-1)

        xmask = batch["x_val"] >= 0
        if xmask.any():
            x = nn.functional.cross_entropy(out["x_logits"][xmask], batch["x_val"][xmask])
        else:
            x = torch.zeros((), device=policy.device)

        bmask = batch["bool_label"] >= 0
        if bmask.any():
            boolL = nn.functional.binary_cross_entropy_with_logits(
                out["bool_logit"][bmask], batch["bool_label"][bmask].float())
        else:
            boolL = torch.zeros((), device=policy.device)

        nmask = (batch["num_label"] >= 0) & (batch["forced"] == 0)
        if nmask.any():
            num = nn.functional.cross_entropy(out["num_logits"][nmask],
                                              batch["num_label"][nmask])
        else:
            num = torch.zeros((), device=policy.device)

        vmask = batch["has_outcome"].bool()
        if vmask.any():
            value = nn.functional.binary_cross_entropy_with_logits(
                out["value_logit"][vmask], batch["won"][vmask].float())
        else:
            value = torch.zeros((), device=policy.device)

        with torch.no_grad():
            pred = out["policy_logits"].argmax(1)
            acc = ((pred == batch["label"]) & prio).sum() / prio.sum().clamp(min=1)
            nonpass = (batch["label"] > 0) & prio
            acc_np = ((pred == batch["label"]) & nonpass).sum() / nonpass.sum().clamp(min=1)
            tmask = batch["tgt_labels"] >= 0
            tacc = ((tl.argmax(-1) == batch["tgt_labels"]) & tmask).sum() / tmask.sum().clamp(min=1)
        return {"policy": policy, "target": target, "x": x, "value": value,
                "bool": boolL, "num": num,
                "loss": policy + tgt_weight * target + x_weight * x + value_weight * value
                        + onefield_weight * (boolL + num),
                "acc": acc, "acc_nonpass": acc_np, "acc_target": tacc}
