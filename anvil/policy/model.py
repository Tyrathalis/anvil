"""AnvilNet v0 (M1 D4) + SA-level candidates (M2 D2): encoder + trunk + rung-1 heads.

Trunk: pre-LN transformer encoder, d=512, 8 heads, 10 layers (plan band
8-12). Priority pointer scores PASS + candidate rows; since M2 D2 a
candidate is a (host entity, SA descriptor) pair — the key adds a learned
SA-string-vocab + kind embedding when n_sa > 0 (n_sa=0 reproduces the M1
host-level architecture for old checkpoints). Target/X/one-field heads and
the win-prob value head as at M1. The turn-plan latent (§3) enters as a
second read-out token when the target pointer lands.

Combat heads (M2 D5): factorized per-candidate-row declare-attackers/
blockers — attack yes/no logit + dedup count classes + target pointer per
row; block pointer over attacker rows ∪ a learned none key. Factorized (not
autoregressive) per the D5 design; the AR decoder is the documented D6
exploration-coherence upgrade path. Pre-D5 checkpoints load via load_compat
(task_emb row growth + fresh-init combat params).
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
                 d_model: int = 512, n_heads: int = 8, n_layers: int = 10,
                 n_sa: int = 0):
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
        # SA-level candidates (M2 D2): the pointer key is the host entity's
        # trunk output plus a learned SA-descriptor vector (string-vocab
        # embedding + kind). n_sa=0 reproduces the M1 host-level architecture
        # (old checkpoints load and serve unchanged).
        if n_sa:
            self.sa_emb = nn.Embedding(n_sa + 1, 64)   # +1 = OOV id
            self.kind_emb = nn.Embedding(4, 8)  # dataset.KINDS
            self.sa_proj = nn.Linear(64 + 8, d_model)
        else:
            self.sa_emb = None
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
        # combat heads (M2 D5): factorized per-candidate-row declarations.
        # Row input = candidate entity output ⊕ [STATE]. Param names keep the
        # atk_/blk_/cmb_ prefixes — load_compat lets pre-D5 checkpoints load
        # with these at fresh init.
        from anvil.training.dataset import COMBAT_COUNT_MAX
        self.atk_head = nn.Sequential(nn.Linear(2 * d_model, d_model), nn.GELU(),
                                      nn.Linear(d_model, 1))
        self.cmb_count_head = nn.Sequential(nn.Linear(2 * d_model, d_model), nn.GELU(),
                                            nn.Linear(d_model, COMBAT_COUNT_MAX))
        self.atk_tgt_query = nn.Linear(2 * d_model, d_model)
        self.atk_tgt_key = nn.Linear(d_model, d_model)
        self.atk_player_key = nn.Linear(n_player_features, d_model)
        self.blk_query = nn.Linear(2 * d_model, d_model)
        self.blk_key = nn.Linear(d_model, d_model)
        self.blk_none = nn.Parameter(torch.randn(d_model) / d_model ** 0.5)

    # params new at M2 D5 (combat heads); absent from older checkpoints and
    # allowed missing on load — they keep their fresh init
    _D5_PREFIXES = ("atk_", "blk_", "cmb_")

    def load_compat(self, state: dict) -> None:
        """Load a checkpoint state_dict across the D5 boundary: task_emb grew
        6->8 rows (attack/block) — saved rows load exactly, new rows keep
        their fresh init; combat-head params may be missing entirely. Any
        OTHER mismatch still raises (this is not a blanket strict=False).

        M3 D1 boundary: entity features grew 17->18 (cmd_tax, appended =
        last ent_proj input column). Saved weights get a ZERO-padded new
        column — zero, not fresh init, so pre-D1 checkpoints produce
        byte-identical outputs until the feature is trained."""
        cur = self.task_emb.weight
        saved = state.get("task_emb.weight")
        if saved is not None and saved.shape[0] < cur.shape[0]:
            merged = cur.detach().clone()
            merged[:saved.shape[0]] = saved
            state = {**state, "task_emb.weight": merged}
        cur_ep = self.assemble.ent_proj.weight
        saved_ep = state.get("assemble.ent_proj.weight")
        if saved_ep is not None and saved_ep.shape[1] < cur_ep.shape[1]:
            padded = cur_ep.new_zeros(cur_ep.shape)
            padded[:, :saved_ep.shape[1]] = saved_ep
            state = {**state, "assemble.ent_proj.weight": padded}
        missing, unexpected = self.load_state_dict(state, strict=False)
        bad = [k for k in missing if not k.startswith(self._D5_PREFIXES)]
        if bad or unexpected:
            raise RuntimeError(f"checkpoint mismatch: missing {bad}, "
                               f"unexpected {list(unexpected)}")

    def _pointer_logits(self, state: torch.Tensor, ent_out: torch.Tensor,
                        batch: dict,
                        pass_delta: "float | torch.Tensor" = 0.0) -> torch.Tensor:
        # pass_delta: scalar, or (B,1) tensor for mixed micro-batches (D6
        # server batching: priority items carry the calibration delta,
        # other tasks 0) — broadcasts onto the PASS logit either way.
        """Pointer logits over candidates: index 0 = PASS, rest gather host
        rows; with SA-level candidates (n_sa > 0) the key adds a learned
        SA-descriptor vector. Shared by forward() and act() — the plumbing
        must not fork."""
        q = self.ptr_query(state).unsqueeze(1)                    # (B,1,d)
        k = self.ptr_key(ent_out)                                 # (B,N,d)
        rows = batch["cand_rows"].clamp(min=0)                    # (B,C); 0-safe gather
        k_cand = k.gather(1, rows.unsqueeze(-1).expand(-1, -1, k.shape[-1]))
        if self.sa_emb is not None:
            sa = self.sa_proj(torch.cat([self.sa_emb(batch["cand_sa"].clamp(min=0)),
                                         self.kind_emb(batch["cand_kind"].clamp(min=0))],
                                        dim=-1))
            k_cand = k_cand + sa * (batch["cand_sa"] >= 0).unsqueeze(-1)  # PASS/pad: none
        logits = (q * k_cand).sum(-1) / k.shape[-1] ** 0.5        # (B,C)
        pass_logit = self.pass_head(state) + pass_delta           # (B,1)
        logits = torch.cat([pass_logit, logits[:, 1:]], dim=1)    # slot 0 = PASS
        return logits.masked_fill(~batch["cand_mask"], -1e9)

    def _combat_outputs(self, state: torch.Tensor, ent_out: torch.Tensor,
                        batch: dict) -> dict:
        """Combat-head logits (D5), shared by forward() and act(). Per
        candidate row (cmb_rows): attack yes/no logit; count-class logits
        masked to [1, group size]; attack-target pointer over entities+players
        (a training-time superset of the engine's legal defenders — labels
        only land on legal ones, serve masks exactly via the executor);
        block pointer over attacker slots + the learned none key at index M."""
        d = ent_out.shape[-1]
        rows = batch["cmb_rows"].clamp(min=0)
        row_vec = ent_out.gather(1, rows.unsqueeze(-1).expand(-1, -1, d))
        cin = torch.cat([row_vec, state.unsqueeze(1).expand_as(row_vec)], dim=-1)

        atk_logits = self.atk_head(cin).squeeze(-1)               # (B,A)

        cnt_logits = self.cmb_count_head(cin)                     # (B,A,Kmax)
        rng = torch.arange(cnt_logits.shape[-1], device=cnt_logits.device)
        cnt_logits = cnt_logits.masked_fill(
            rng >= batch["cmb_count"].unsqueeze(-1).clamp(min=1), -1e9)

        q = self.atk_tgt_query(cin)                               # (B,A,d)
        tkeys = torch.cat([self.atk_tgt_key(ent_out),
                           self.atk_player_key(batch["players"])], dim=1)
        tgt_logits = q @ tkeys.transpose(1, 2) / d ** 0.5         # (B,A,N+P)
        pmask = torch.cat([~batch["ent_mask"],
                           torch.zeros(ent_out.shape[0], batch["players"].shape[1],
                                       dtype=torch.bool, device=ent_out.device)], dim=1)
        tgt_logits = tgt_logits.masked_fill(pmask.unsqueeze(1), -1e9)

        arows = batch["blk_atk_rows"].clamp(min=0)
        akeys = self.blk_key(ent_out.gather(1, arows.unsqueeze(-1).expand(-1, -1, d)))
        keys = torch.cat([akeys, self.blk_none.expand(ent_out.shape[0], 1, -1)], dim=1)
        blk_logits = self.blk_query(cin) @ keys.transpose(1, 2) / d ** 0.5  # (B,A,M+1)
        bmask = torch.cat([~batch["blk_atk_mask"],
                           torch.zeros(ent_out.shape[0], 1, dtype=torch.bool,
                                       device=ent_out.device)], dim=1)
        blk_logits = blk_logits.masked_fill(bmask.unsqueeze(1), -1e9)

        return {"atk_logits": atk_logits, "cmb_count_logits": cnt_logits,
                "atk_tgt_logits": tgt_logits, "blk_logits": blk_logits}

    def forward(self, batch: dict) -> dict:
        card_vecs = self.cards(batch["ent_emb"])
        tokens, pad = self.assemble(card_vecs, batch)
        out = self.trunk(tokens, src_key_padding_mask=pad)
        state = out[:, 0]                       # [STATE] read-out
        plan = out[:, 1]                        # [PLAN] latent (unsupervised at M1)
        n_ent = batch["entities"].shape[1]
        ent_out = out[:, 2:2 + n_ent]           # entity token outputs

        logits = self._pointer_logits(state, ent_out, batch)

        # ---- teacher-forced target decoder + X head (cast windows only) ----
        # source vector: entity output at the labeled source row (pass or
        # masked SA label -> zeros; masked windows pad their tgt/x labels too)
        lab = batch["label"].clamp(min=0)
        rows_src = batch["cand_rows"].gather(1, lab.unsqueeze(1)).clamp(min=0)
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
                "value_logit": self.value_head(state).squeeze(-1),
                **self._combat_outputs(state, ent_out, batch)}

    @torch.no_grad()
    def act(self, batch: dict, pass_delta: "float | torch.Tensor" = 0.0,
            noise: "dict | None" = None, temperature: float = 1.0) -> dict:
        """Greedy inference (M1 D8 serve path). Mirrors forward()'s encode and
        pointer plumbing but conditions the target decoder on the MODEL's
        candidate choice and feeds its own picks back (forward teacher-forces
        both). pass_delta is the post-hoc PASS-boundary calibration knob
        (calibrate_pass.py). Any change to forward()'s tensor plumbing must
        land here too.

        noise (M2 D6, sampling.pad_noise output) switches every head from
        argmax to Gumbel-max sampling and adds fp32 per-head logp_*/ent_* of
        the sampled picks under the temperature-scaled distribution — the
        behavior policy mu the V-trace learner corrects against. noise=None
        is byte-identical to the pre-D6 greedy path."""
        card_vecs = self.cards(batch["ent_emb"])
        tokens, pad = self.assemble(card_vecs, batch)
        out = self.trunk(tokens, src_key_padding_mask=pad)
        state = out[:, 0]
        n_ent = batch["entities"].shape[1]
        ent_out = out[:, 2:2 + n_ent]

        mu: dict[str, torch.Tensor] = {}

        def cat_pick(lg: torch.Tensor, nz: "torch.Tensor | None", name: str):
            """Sampled (or greedy) pick over the last dim + logp/ent bookkeeping."""
            if noise is None:
                return lg.argmax(-1)
            lgf = lg.float()
            pick = (lgf + nz).argmax(-1)
            lp = torch.log_softmax(lgf / temperature, dim=-1)
            mu[f"logp_{name}"] = lp.gather(-1, pick.unsqueeze(-1)).squeeze(-1)
            mu[f"ent_{name}"] = -(lp.exp() * lp).sum(-1)
            return pick

        def bern_pick(lg: torch.Tensor, nz: "torch.Tensor | None", name: str):
            if noise is None:
                return lg > 0
            lgf = lg.float()
            pick = (lgf + nz) > 0
            z = lgf / temperature
            mu[f"logp_{name}"] = torch.nn.functional.logsigmoid(
                torch.where(pick, z, -z))
            p = torch.sigmoid(z)
            mu[f"ent_{name}"] = -(p * torch.nn.functional.logsigmoid(z)
                                  + (1 - p) * torch.nn.functional.logsigmoid(-z))
            return pick

        logits = self._pointer_logits(state, ent_out, batch, pass_delta=pass_delta)
        choice = cat_pick(logits, noise and noise["choice"], "choice")

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
        if noise is not None:
            # slot factors accumulate while un-stopped (the STOP pick itself
            # is a factor; post-stop slots are forced and contribute nothing)
            mu["logp_tgt"] = torch.zeros(ent_out.shape[0], device=ent_out.device)
            mu["ent_tgt"] = torch.zeros(ent_out.shape[0], device=ent_out.device)
        for t in range(self.t_max + 1):
            qv = self.tgt_query(torch.cat([state, src_vec, prev], dim=-1)) + self.slot_emb[t]
            lg = (keys @ qv.unsqueeze(-1)).squeeze(-1) / d ** 0.5
            lg = lg.masked_fill(kpad, -1e9)
            if noise is None:
                raw = lg.argmax(-1)
            else:
                lgf = lg.float()
                raw = (lgf + noise["tgt"][:, t]).argmax(-1)
                lp = torch.log_softmax(lgf / temperature, dim=-1)
                active = (~stopped).float()
                pick_ = torch.where(stopped, torch.full_like(raw, stop_idx), raw)
                mu["logp_tgt"] += lp.gather(1, pick_.unsqueeze(1)).squeeze(1) * active
                mu["ent_tgt"] += -(lp.exp() * lp).sum(-1) * active
            pick = torch.where(stopped, torch.full_like(raw, stop_idx), raw)
            picks.append(pick)
            stopped = stopped | (pick == stop_idx)
            picked = vecs.gather(1, pick.unsqueeze(-1).unsqueeze(-1)
                                 .expand(-1, -1, vecs.shape[-1])).squeeze(1)
            prev = prev + picked  # STOP's vec is zeros; post-stop slots add nothing

        x_cls = cat_pick(self.x_head(torch.cat([state, src_vec], dim=-1)),
                         noise and noise["x"], "x")

        ctx = ent_out.gather(1, batch["ctx_row"].clamp(min=0).unsqueeze(-1).unsqueeze(-1)
                             .expand(-1, -1, ent_out.shape[-1])).squeeze(1)
        ctx = ctx * (batch["ctx_row"] >= 0).unsqueeze(-1)
        of_in = torch.cat([state, ctx, self.task_emb(batch["task"])], dim=-1)
        num_logits = self.num_head(of_in)
        rng = torch.arange(num_logits.shape[-1], device=num_logits.device)
        num_logits = num_logits.masked_fill(
            (rng < batch["num_lo"].unsqueeze(-1)) | (rng > batch["num_hi"].unsqueeze(-1)), -1e9)

        cmb = self._combat_outputs(state, ent_out, batch)
        return {"choice": choice, "tgt_picks": torch.stack(picks, dim=1),
                "x_cls": x_cls, "n_ent": n_ent, "stop_idx": stop_idx,
                "bool": bern_pick(self.bool_head(of_in).squeeze(-1),
                                  noise and noise["bool"], "bool"),
                "num": cat_pick(num_logits, noise and noise["num"], "num"),
                "win": torch.sigmoid(self.value_head(state).squeeze(-1)),
                # combat picks (D5): per-row attack yes/no, group count k
                # (count-class argmax + 1), target class over [0,N)∪[N,N+P),
                # block slot over [0,M]∪{M=none}
                # sampled per-row logp_/ent_ stay (B,A) — the server slices
                # real rows and applies the composite inclusion rules
                "atk_yes": bern_pick(cmb["atk_logits"], noise and noise["atk"], "atk"),
                "cmb_count": cat_pick(cmb["cmb_count_logits"],
                                      noise and noise["cnt"], "cnt") + 1,
                "atk_tgt": cat_pick(cmb["atk_tgt_logits"],
                                    noise and noise["atk_tgt"], "atk_tgt"),
                "blk_pick": cat_pick(cmb["blk_logits"], noise and noise["blk"], "blk"),
                **mu}

    def losses(self, batch: dict, pass_weight: float = 1.0, tgt_weight: float = 1.0,
               x_weight: float = 0.5, value_weight: float = 0.5,
               onefield_weight: float = 0.5, combat_weight: float = 1.0) -> dict:
        out = self(batch)
        prio = batch["task"] == 0
        # label -1 = SA-level-ambiguous (masked from the policy loss; the
        # window still trains value and contributes host-level metrics)
        valid = batch["label"] >= 0
        lab = batch["label"].clamp(min=0)
        ce = nn.functional.cross_entropy(out["policy_logits"], lab,
                                         reduction="none")
        w = torch.where(lab == 0, torch.full_like(ce, pass_weight),
                        torch.ones_like(ce)) * (prio & valid).float()
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

        # ---- combat losses (D5): every mask is label-carried, so each term
        # fires only on its own task's rows ----
        zero = torch.zeros((), device=policy.device)
        am = batch["atk_label"] >= 0
        atkL = (nn.functional.binary_cross_entropy_with_logits(
            out["atk_logits"][am], batch["atk_label"][am].float())
            if am.any() else zero)
        cm = batch["cmb_count_label"] >= 0
        cntL = (nn.functional.cross_entropy(
            out["cmb_count_logits"][cm], batch["cmb_count_label"][cm])
            if cm.any() else zero)
        atm = batch["atk_tgt_labels"] >= 0
        atgtL = (nn.functional.cross_entropy(
            out["atk_tgt_logits"][atm], batch["atk_tgt_labels"][atm])
            if atm.any() else zero)
        bm = batch["blk_label"] >= 0
        blkL = (nn.functional.cross_entropy(
            out["blk_logits"][bm], batch["blk_label"][bm])
            if bm.any() else zero)

        with torch.no_grad():
            pred = out["policy_logits"].argmax(1)
            pbasis = prio & valid
            acc = ((pred == lab) & pbasis).sum() / pbasis.sum().clamp(min=1)
            nonpass = (lab > 0) & pbasis
            acc_np = ((pred == lab) & nonpass).sum() / nonpass.sum().clamp(min=1)
            tmask = batch["tgt_labels"] >= 0
            tacc = ((tl.argmax(-1) == batch["tgt_labels"]) & tmask).sum() / tmask.sum().clamp(min=1)
            acc_atk = (((out["atk_logits"] > 0) == (batch["atk_label"] == 1)) & am
                       ).sum() / am.sum().clamp(min=1)
            acc_blk = ((out["blk_logits"].argmax(-1) == batch["blk_label"]) & bm
                       ).sum() / bm.sum().clamp(min=1)
        return {"policy": policy, "target": target, "x": x, "value": value,
                "bool": boolL, "num": num,
                "atk": atkL, "cmb_count": cntL, "atk_tgt": atgtL, "blk": blkL,
                "loss": policy + tgt_weight * target + x_weight * x + value_weight * value
                        + onefield_weight * (boolL + num)
                        + combat_weight * (atkL + cntL + atgtL + blkL),
                "acc": acc, "acc_nonpass": acc_np, "acc_target": tacc,
                "acc_atk": acc_atk, "acc_blk": acc_blk}
