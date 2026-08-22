"""V-trace self-play learner machinery (M2 D6, docs/design/d6-vtrace-loop.md).

Core contract: the composite action logp is a pure sum over LABELED factors —
the inclusion rules (which factors are part of the action) live in the RL
loader's label construction and in the server's mu record, which must stay in
lockstep (see server._write_mu):
  priority: choice, + tgt slots/x iff choice > 0
  one-field: the single bool/num factor
  attack: every real row's yes/no, + cnt (group>1) / target for yes rows
  block: every real row's slot pick, + cnt for blocking group>1 rows

composite_logp(fwd, batch) therefore serves three jobs with one body:
  - recompute mu under the generating checkpoint (the standing drift
    tripwire: |recomputed - recorded| beyond tolerance = serve/loader skew)
  - compute pi under the training checkpoint (the V-trace ratios)
  - the policy-gradient term (differentiable when fwd came from grad mode)
"""

from __future__ import annotations

import torch
import torch.nn.functional as F

from anvil.training.dataset import TASKS, collate, default_methods


def _gather_lp(
    logits: torch.Tensor, labels: torch.Tensor, temperature: float = 1.0
) -> torch.Tensor:
    """log_softmax over the last dim gathered at labels; -1 labels -> 0."""
    ok = labels >= 0
    lp = torch.log_softmax(logits.float() / temperature, dim=-1)
    out = lp.gather(-1, labels.clamp(min=0).unsqueeze(-1)).squeeze(-1)
    return out * ok.float()


def composite_logp(fwd: dict, batch: dict, temperature: float = 1.0) -> dict:
    """Per-window composite action log-prob from forward() outputs.

    Every factor with a set label (>= 0 / != -1) contributes; the loader
    encodes the inclusion rules by which labels it sets. Returns per-head
    terms plus the total — the per-head split is what the mu tripwire
    compares record-by-record.
    """
    # pointer-choice tasks: priority + pay_class (M9 rung 3) — both label the
    # policy_logits choice; pay_class never sets tgt/x labels
    is_pointer = (batch["task"] == TASKS["priority"]) | (batch["task"] == TASKS["pay_class"])
    label = torch.where(is_pointer, batch["label"], torch.full_like(batch["label"], -1))
    lp_choice = _gather_lp(fwd["policy_logits"], label, temperature)

    # target slots: teacher-forced logits at labeled slots, cast windows only
    lp_tgt = _gather_lp(fwd["tgt_logits"], batch["tgt_labels"], temperature).sum(-1)
    lp_x = _gather_lp(fwd["x_logits"], batch["x_val"], temperature)

    b = fwd["bool_logit"].float() / temperature
    b_ok = batch["bool_label"] >= 0
    b_sign = torch.where(batch["bool_label"].clamp(min=0) > 0, b, -b)
    lp_bool = F.logsigmoid(b_sign) * b_ok.float()
    lp_num = _gather_lp(fwd["num_logits"], batch["num_label"], temperature)

    a = fwd["atk_logits"].float() / temperature
    a_ok = batch["atk_label"] >= 0
    a_sign = torch.where(batch["atk_label"].clamp(min=0) > 0, a, -a)
    lp_atk = (F.logsigmoid(a_sign) * a_ok.float()).sum(-1)
    lp_cnt = _gather_lp(fwd["cmb_count_logits"], batch["cmb_count_label"], temperature).sum(-1)
    lp_atgt = _gather_lp(fwd["atk_tgt_logits"], batch["atk_tgt_labels"], temperature).sum(-1)
    lp_blk = _gather_lp(fwd["blk_logits"], batch["blk_label"], temperature).sum(-1)

    total = lp_choice + lp_tgt + lp_x + lp_bool + lp_num + lp_atk + lp_cnt + lp_atgt + lp_blk
    return {
        "logp": total,
        "choice": lp_choice,
        "tgt": lp_tgt,
        "x": lp_x,
        "bool": lp_bool,
        "num": lp_num,
        "atk": lp_atk,
        "cnt": lp_cnt,
        "atgt": lp_atgt,
        "blk": lp_blk,
    }


def apply_mu_labels(ex: dict, rec: dict) -> dict:
    """Write the sampled action from a mu record into an example's label
    fields — the inclusion rules in label form (an unlabeled factor is -1 and
    contributes nothing to composite_logp). Inverse of sampling.mu_record;
    the two must stay in lockstep."""
    from anvil.training.dataset import T_MAX

    n_i = ex["entities"].shape[0]
    task = rec["task"]
    if task == "pay_class":
        # choice-only (M9 rung 3): the goal pick IS the whole answer
        ex["label"] = torch.tensor(rec["c"], dtype=torch.int64)
        return ex
    if task == "priority":
        c = rec["c"]
        ex["label"] = torch.tensor(c, dtype=torch.int64)
        if c > 0:
            tk = torch.full((T_MAX + 1,), -1, dtype=torch.int64)
            ti = torch.full((T_MAX + 1,), -1, dtype=torch.int64)
            for j, t in enumerate(rec.get("tgt", [])):
                tk[j], ti[j] = (0, t) if t < n_i else (1, t - n_i)
            j = len(rec.get("tgt", []))
            if j <= T_MAX:  # all-slots-filled samples carry no STOP factor
                tk[j], ti[j] = 2, 0
            ex["tgt_kind"], ex["tgt_idx"] = tk, ti
            ex["x_val"] = torch.tensor(rec["x"], dtype=torch.int64)
    elif task in ("mull_keep", "trigger", "binary"):
        ex["bool_label"] = torch.tensor(rec["b"], dtype=torch.int64)
    elif task == "number":
        ex["num_label"] = torch.tensor(rec["n"], dtype=torch.int64)
    elif task == "attack":
        a_i = ex["cmb_rows"].shape[0]
        ex["atk_label"] = torch.tensor(rec["atk"], dtype=torch.int64)
        cnt = torch.full((a_i,), -1, dtype=torch.int64)
        tk = torch.full((a_i,), -1, dtype=torch.int64)
        ti = torch.full((a_i,), -1, dtype=torch.int64)
        for i in range(a_i):
            if rec["atk"][i]:
                t = rec["atgt"][i]
                tk[i], ti[i] = (0, t) if t < n_i else (1, t - n_i)
                if int(ex["cmb_count"][i]) > 1:
                    cnt[i] = rec["cnt"][i] - 1
        ex["cmb_count_label"] = cnt
        ex["atk_tgt_kind"], ex["atk_tgt_idx"] = tk, ti
    elif task == "block":
        a_i = ex["cmb_rows"].shape[0]
        m_i = ex["blk_atk_rows"].shape[0]
        ex["blk_label"] = torch.tensor(rec["blk"], dtype=torch.int64)
        cnt = torch.full((a_i,), -1, dtype=torch.int64)
        for i in range(a_i):
            if rec["blk"][i] < m_i and int(ex["cmb_count"][i]) > 1:
                cnt[i] = rec["cnt"][i] - 1
        ex["cmb_count_label"] = cnt
    return ex


def composite_entropy(fwd: dict, batch: dict) -> torch.Tensor:
    """Per-window summed entropy over the LABELED factor heads (the sampled
    action's factors) — the exploration-collapse monitor and bonus term.
    Masked logits carry -1e9, so exp() underflows to exact 0 there."""

    def cat_ent(logits, ok):
        lp = torch.log_softmax(logits.float(), dim=-1)
        return (-(lp.exp() * lp).sum(-1)) * ok.float()

    is_pointer = (batch["task"] == TASKS["priority"]) | (batch["task"] == TASKS["pay_class"])
    ent = cat_ent(fwd["policy_logits"], is_pointer & (batch["label"] >= 0))
    ent = ent + cat_ent(fwd["tgt_logits"], batch["tgt_labels"] >= 0).sum(-1)
    ent = ent + cat_ent(fwd["x_logits"], batch["x_val"] >= 0)

    b = fwd["bool_logit"].float()
    p = torch.sigmoid(b)
    bent = -(p * F.logsigmoid(b) + (1 - p) * F.logsigmoid(-b))
    ent = ent + bent * (batch["bool_label"] >= 0).float()
    ent = ent + cat_ent(fwd["num_logits"], batch["num_label"] >= 0)

    a = fwd["atk_logits"].float()
    pa = torch.sigmoid(a)
    aent = -(pa * F.logsigmoid(a) + (1 - pa) * F.logsigmoid(-a))
    ent = ent + (aent * (batch["atk_label"] >= 0).float()).sum(-1)
    ent = ent + cat_ent(fwd["cmb_count_logits"], batch["cmb_count_label"] >= 0).sum(-1)
    ent = ent + cat_ent(fwd["atk_tgt_logits"], batch["atk_tgt_labels"] >= 0).sum(-1)
    ent = ent + cat_ent(fwd["blk_logits"], batch["blk_label"] >= 0).sum(-1)
    return ent


def vtrace_targets(
    values: torch.Tensor,
    logp_pi: torch.Tensor,
    logp_mu: torch.Tensor,
    reward: float,
    gamma: float = 1.0,
    rho_bar: float = 1.0,
    c_bar: float = 1.0,
    step_r: "torch.Tensor | None" = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """V-trace value targets + policy-gradient advantages for ONE trajectory
    (one seat's decision sequence in one game, time-ordered).

    values: (T,) V(x_t) under the current net (probabilities, [0,1]).
    reward: terminal only — 1 win, 0 otherwise (loss/draw/cap: the §3d
    cap-aware rule; a stalling leader forfeits the +1). The terminal state
    itself has value 0 (nothing follows); the reward rides the LAST
    transition — putting it in both places double-counts.
    step_r: (T,) optional per-step shaping rewards (§6c rejected-intent
    penalty); the terminal reward ADDS to step_r[-1].

    Returns (vs, pg_adv, rho): vs (T,) the value regression targets,
    pg_adv (T,) = rho_s (r_s + gamma vs_{s+1} - V(x_s)), rho (T,) clipped.
    """
    t_len = values.shape[0]
    rho = torch.exp(logp_pi - logp_mu)
    c = rho.clamp(max=c_bar)
    rho = rho.clamp(max=rho_bar)
    r = torch.zeros(t_len) if step_r is None else step_r.clone().float()
    r[-1] += reward
    v_next = torch.cat([values[1:], torch.zeros(1)])  # V(terminal) = 0
    delta = rho * (r + gamma * v_next - values)
    vs = torch.zeros(t_len)
    acc = torch.zeros(())
    for t in range(t_len - 1, -1, -1):
        acc = delta[t] + gamma * c[t] * acc
        vs[t] = values[t] + acc
    vs_next = torch.cat([vs[1:], torch.zeros(1)])
    pg_adv = rho * (r + gamma * vs_next - values)
    return vs, pg_adv, rho


def mu_matches(ex: dict, rec: dict) -> bool:
    """Structural bounds check of a mu record against its rebuilt window —
    the backstop for chimeric (g, s) joins (diverged re-issued games; the
    ingest-side conflict drop is the primary guard). An out-of-bounds label
    would crash the gather kernels mid-training; a mismatch means the record
    does not belong to this window, so the caller drops the whole game."""
    from anvil.training.dataset import COMBAT_COUNT_MAX, T_MAX, X_CLASSES

    n_i = ex["entities"].shape[0]
    p = ex["players"].shape[0]
    task = rec["task"]
    if task == "pay_class":
        return 0 <= rec["c"] < ex["cand_rows"].shape[0]
    if task == "priority":
        if not (0 <= rec["c"] < ex["cand_rows"].shape[0]):
            return False
        if rec["c"] > 0:
            tgt = rec.get("tgt", [])
            if len(tgt) > T_MAX + 1 or not all(0 <= t < n_i + p for t in tgt):
                return False
            if not (0 <= rec["x"] < X_CLASSES):
                return False
    elif task == "number":
        if not (0 <= rec["n"] < X_CLASSES):
            return False
    elif task in ("attack", "block"):
        a_i = ex["cmb_rows"].shape[0]
        if len(rec["cnt"]) != a_i or not all(1 <= k <= COMBAT_COUNT_MAX for k in rec["cnt"]):
            return False
        if task == "attack":
            if len(rec["atk"]) != a_i or len(rec["atgt"]) != a_i:
                return False
            if not all(0 <= t < n_i + p for y, t in zip(rec["atk"], rec["atgt"]) if y):
                return False
        else:
            m_i = ex["blk_atk_rows"].shape[0]
            if len(rec["blk"]) != a_i or not all(0 <= b <= m_i for b in rec["blk"]):
                return False
    return True


def rejected_events(
    decs: list,
    i: int,
    dec: dict,
    rec: dict,
    aux: dict,
    mu: dict | None = None,
    grouping: str = "event",
) -> int:
    """Engine-rejected intent count for one mu-covered window (§6c pin;
    pricing superseded by ADR-0054 — see `grouping`).

    priority: 1 iff the mu pick was a cast (c > 0) and no SA realized
    (ret null) — the vetoed-attempt signature. grouping="event" counts
    every vetoed attempt (re-ask chains: each dec counts once — the
    original §6c pricing; scripts/validate_rejected_intent.py reconciles
    THIS basis against census). grouping="first" (ADR-0054 C3): one count
    per veto WINDOW — a chain continuation (the immediately preceding dec
    is a vetoed attempt by the same seat in the same turn; §6b re-asks
    adjacently, nothing intervenes — the scripts/rejected_chain_read.py
    inference) counts zero, because chain length is realizer walk-down
    machinery, not graded intent. Requires `mu` to classify the neighbor.
    attack: declared-but-not-realized attacker entities (per candidate row,
    intended count minus realized count), via the D5 bounded obs join.
    block: |declared - realized| blocker entities per row — dropped AND
    forced-add repairs both count (the engine modified the declaration).

    Combat bases come from the featurizer's aux (cmb_rows/cmb_members —
    the same rows mu was recorded against, skew-free by construction).
    Reader-side only; scripts/validate_rejected_intent.py reconciles these
    against census veto/drop counts per run — the gate before any penalty
    run trains (d6-vtrace-loop §6c)."""
    task = rec["task"]
    if task == "priority":
        if not (rec["c"] > 0 and dec.get("ret") is None):
            return 0
        if grouping == "first" and mu is not None and i > 0:
            prev = decs[i - 1]
            pr = mu.get(prev["s"])
            if (
                pr is not None
                and pr.get("task") == "priority"
                and pr.get("c", 0) > 0
                and prev.get("ret") is None
                and prev.get("p") == dec.get("p")
                and (prev.get("obs") or {}).get("glob", {}).get("turn")
                == (dec.get("obs") or {}).get("glob", {}).get("turn")
            ):
                return 0  # chain continuation: the window already paid
        return 1
    if task not in ("attack", "block"):
        return 0
    from anvil.training.dataset import _combat_label_window

    obs = dec["obs"]
    p = dec["p"]
    rows = aux.get("cmb_rows") or []
    members = aux.get("cmb_members") or {}
    if not rows:
        return 0
    turn = obs["glob"].get("turn")
    lw = _combat_label_window(decs, i, turn, "atk" if task == "attack" else "blk")
    flag = "atk" if task == "attack" else "blk"
    realized = (
        set() if lw is None else {e["e"] for e in lw["ents"] if flag in e and e.get("c") == p}
    )
    if task == "attack":
        n = 0
        for j, r in enumerate(rows):
            ids = members[r]
            want = min(rec["cnt"][j], len(ids)) if rec["atk"][j] else 0
            got = sum(1 for eid in ids if eid in realized)
            n += max(0, want - got)
        return n
    none_class = len(aux.get("blk_atk_rows") or [])
    n = 0
    for j, r in enumerate(rows):
        ids = members[r]
        want = min(rec["cnt"][j], len(ids)) if rec["blk"][j] != none_class else 0
        got = sum(1 for eid in ids if eid in realized)
        n += abs(want - got)
    return n


def game_trajectories(store, feat, g: int, full_vis: bool = False, penalty_grouping: str = "first"):
    """Per-seat mu-covered trajectories of one stored game, serve-identical
    windows via the featurizer path (store_wire_hist -> Featurizer.example ->
    apply_mu_labels).

    Returns (trajs, skip_reason): trajs = [(seat, [(ex, rec), ...], reward,
    rej, exs_fv)]; reward per §3d — win 1, loss/draw/cap 0 (a stalling leader
    forfeits the +1); skip_reason set (and trajs empty) for crash/no-outcome
    games, whose returns are engine artifacts, and for games without mu
    records. full_vis (§6f): exs_fv = the asymmetric critic's windows (same
    decisions, info-set gate bypassed) — consumed ONLY by the frozen critic's
    value forward in pass A, never by the policy passes; [] when off."""
    from anvil.bridge.featurize import store_wire_hist

    mu = store.mu_for_game(g)
    if not mu:
        return [], "no_mu"
    outcome = store.outcomes.get(g) if hasattr(store, "outcomes") else None
    if outcome is None and hasattr(store, "_store_of"):  # MultiStore
        outcome = store._store_of[g].outcomes.get(g)
    status = (outcome or {}).get("status")
    if status not in ("won", "draw"):
        return [], f"status:{status}"
    winner = store.winner_seat(g)
    traj = store.game(g)
    by_seat: dict[int, list] = {}
    prior = []
    for dec in traj.decisions:
        rec = mu.get(dec["s"])
        if rec is not None and dec.get("obs") is not None:
            wire = dict(dec)
            if "hist" not in dec:
                wire["hist"] = store_wire_hist(prior, dec["_pos"])
            # else: fork frames (M4 D3) store the serve-time wire hist
            # verbatim — the first windows' history includes parent-game
            # entries a reconstruction from this frame could never see
            ex, aux = feat.example(wire, traj.header, rec["task"])
            if not mu_matches(ex, rec):
                return [], "mu_mismatch"
            rej = rejected_events(
                traj.decisions, len(prior), dec, rec, aux, mu=mu, grouping=penalty_grouping
            )
            apply_mu_labels(ex, rec)
            ex_fv = (
                feat.example(wire, traj.header, rec["task"], full_vis=True)[0] if full_vis else None
            )
            by_seat.setdefault(dec["p"], []).append((ex, rec, rej, ex_fv))
        prior.append(dec)
    return [
        (
            p,
            [(e, r) for e, r, _, _ in items],
            1.0 if winner == p else 0.0,
            [rj for _, _, rj, _ in items],
            [fv for _, _, _, fv in items] if full_vis else [],
        )
        for p, items in sorted(by_seat.items())
    ], None


def seq_pass(
    net,
    seq_segs: list,
    forward_segments,
    w_seq: float,
    aux_w: float,
    grad: bool = True,
    margin: float = 0.0,
) -> tuple[float, float]:
    """One pass over the C-seq batch (ADR-0054): the sequence-contrastive
    term L_seq = −Â·[logp(cast*) − logp(pass)] (logp(cast*) = logsumexp over
    the candidates matching the act arm's modal first cast; the tmask is the
    all-nonpass mass fallback where agreement was low) + the C2a masked-head
    aux BCE toward wr_nat. margin > 0 hinges the contrast at ±margin: a
    window where the preferred action already wins by the margin contributes
    zero gradient, so L_seq is bounded (|L_seq| ≤ clip·margin) — the raw
    log-prob contrast is unbounded and ran away in d6-run14 (seq_raw −0.22 →
    −8.5 across three iterations under a frozen w_seq; the M6 rule is clips
    at birth). Means are over the whole seq batch. grad=True backwards the
    weighted total into the current accumulation window; grad=False
    (calibration) just measures. Returns (raw L_seq, raw aux)."""
    n_total = sum(next(iter(s.values())).shape[0] for s in seq_segs)
    tot_l = tot_aux = 0.0
    for seg, fwd in forward_segments(net, seq_segs, grad=grad):
        lp = fwd["policy_logits"].float().log_softmax(1)
        contrast = lp.masked_fill(~seg["seq_tmask"], -1e9).logsumexp(1) - lp[:, 0]
        if margin > 0:
            contrast = contrast.clamp(-margin, margin)
        l_seq = -(seg["seq_adv"] * contrast).sum() / n_total
        aux = (
            F.binary_cross_entropy_with_logits(
                fwd["value_logit"].float(), seg["seq_wr"].clamp(0.0, 1.0), reduction="sum"
            )
            / n_total
        )
        if grad:
            (w_seq * l_seq + aux_w * aux).backward()
        tot_l += float(l_seq.detach())
        tot_aux += float(aux.detach())
    return tot_l, tot_aux


def entropy_hinge(ent: "torch.Tensor", floor: float, b: int, t_len: int):
    """ADR-0017 hinge floor: a penalty (ADDED to the loss) only when the
    segment's mean composite entropy sinks below `floor`; identically zero —
    zero gradient — above it. Replaces the always-on bonus, which was the
    sole persistent gradient under mirror-self-play ~zero advantages and ran
    away with lr (run-2). Weighted by the segment's share of the trajectory
    so multi-segment trajectories aggregate to a trajectory-level hinge."""
    return torch.relu(torch.as_tensor(floor, device=ent.device, dtype=ent.dtype) - ent.mean()) * (
        b / t_len
    )


def _identity(x):
    """DataLoader collate for trajectory items (module-level: py3.14
    forkserver workers must pickle it; a lambda can't)."""
    return x


class RlTrajectories(torch.utils.data.IterableDataset):
    """Streams (seat, windows, reward) trajectories from sampled-actor stores.

    stores/weights: replay mixing by expected pass count — the integer part
    repeats every game, the fractional part subsamples (weight 0.33 ≈ a third
    of the store's games per epoch, seeded-deterministic). Fresh 1.0 beside
    three old stores at 0.33 ≈ one extra store-scan, 50% fresh samples.
    Worker-sharded by game; schedule reshuffled per epoch from the seed."""

    def __init__(
        self,
        stores: list[str],
        weights: list[float],
        stem: str,
        methods: list[str],
        seed: int = 0,
        epochs: int = 1,
        full_vis: bool = False,
        seg: int = 256,
        penalty_grouping: str = "first",
    ):
        self.stores = stores
        self.weights = weights
        self.stem = stem
        self.methods = methods
        self.seed = seed
        self.epochs = epochs
        self.full_vis = full_vis
        self.penalty_grouping = penalty_grouping
        # Collate WORKER-SIDE at exactly the learner's seg size (2026-07-26).
        # Yielding per-window example dicts shipped ~20 tensors x hundreds of
        # windows x2 (masked + fv) through the DataLoader's shm+pickle path for
        # the single main process to deserialize and collate: measured 87% of
        # the train phase in loader handoff, main process at 83% CPU while six
        # workers idled at 25% and the GPU sat ~10% busy. Chunking here at the
        # same boundaries the main process used keeps segmentation and padding
        # IDENTICAL, so the change is verifiable byte-for-byte rather than
        # to a tolerance.
        self.seg = seg

    def __iter__(self):
        import random as _random

        from anvil.bridge.featurize import Featurizer
        from anvil.store.trajectories import open_store

        info = torch.utils.data.get_worker_info()
        wid, nw = (info.id, info.num_workers) if info else (0, 1)
        feat = Featurizer(self.stem, self.methods)
        opened = [open_store(s) for s in self.stores]
        for epoch in range(self.epochs):
            rng = _random.Random(self.seed + epoch)
            schedule = []
            for si, (st, w) in enumerate(zip(opened, self.weights)):
                for g in st.game_indices():
                    reps = int(w) + (1 if rng.random() < w - int(w) else 0)
                    schedule += [(si, g)] * reps
            rng.shuffle(schedule)
            for si, g in schedule:
                if (g * 2654435761 + si) % nw != wid:
                    continue
                trajs, skip = game_trajectories(
                    opened[si],
                    feat,
                    g,
                    full_vis=self.full_vis,
                    penalty_grouping=self.penalty_grouping,
                )
                if skip is not None:
                    yield {"skip": skip, "g": g}
                    continue
                st = opened[si]
                if hasattr(st, "_store_of"):
                    st = st._store_of[g]
                mu_step = (st.mu_meta or {}).get("step")
                # mu_tau: the GENERATION temperature — recorded mu logps are
                # tempered (act() reports the sampled distribution), so the
                # tripwire recompute must use it; per-store because replay
                # mixtures may span runs at different temperatures
                mu_tau = (st.mu_meta or {}).get("temperature", 1.0)
                for seat, exs, reward, rej, exs_fv in trajs:
                    plain = [e for e, _ in exs]
                    n = max(1, self.seg)
                    yield {
                        "g": g,
                        "seat": seat,
                        "reward": reward,
                        "t_len": len(plain),
                        "segs": [collate(plain[i : i + n]) for i in range(0, len(plain), n)],
                        "segs_fv": [collate(exs_fv[i : i + n]) for i in range(0, len(exs_fv), n)],
                        # mu_step: which checkpoint generated these mu
                        # records — the recompute tripwire only applies
                        # when it matches the ref net (replay stores were
                        # sampled under older checkpoints)
                        "mu_step": mu_step,
                        "mu_tau": mu_tau,
                        "rej": torch.tensor(rej, dtype=torch.float32),
                        "mu_logp": torch.tensor([r["logp"] for _, r in exs], dtype=torch.float32),
                    }


def make_forward_segments(dev: str, seg: int):
    """Segmented GPU forward passes over a trajectory's examples.

    VRAM elasticity (task #12): seg is pure micro-batching — activation
    peak scales with it, semantics don't — so cotenant memory pressure (a
    resident ComfyUI job, run-3's OOM class) is absorbed by halving it
    and retrying instead of crashing the iteration. Extended 2026-08-18
    (user directive, the run17 iter-8 incident): at the halving floor the
    learner PARKS for the cotenant instead of raising (scale-to-zero),
    and after a quiet stretch a free-VRAM tier probe restores seg toward
    the launch size (replacing the original sticks-for-the-run policy)."""
    from anvil.training.vram import free_mb, park_for_cotenant, seg_tier

    seg_size = {"n": seg, "target": seg, "ok": 0}
    RESTORE_AFTER = 256  # clean segments before probing back up

    def forward_segments(model, segs, grad: bool):
        # GENERATOR, deliberately: with grad on, each yielded fwd holds a
        # ~GB-scale autograd graph — the caller must backward/drop it before
        # the next segment runs. Materializing the list OOM'd on the first
        # real store (grindy games reach 2K+ decisions/seat = 8+ segments).
        #
        # Segments arrive PRE-COLLATED from the loader worker at the same seg
        # size, so the common path is one forward per segment and the tensors
        # are already batch-first. OOM elasticity still works: halving splits
        # a collated segment by SLICING dim 0, which inherits the parent's
        # padding — marginally wasteful, but numerically identical to the
        # unsplit pass (padding is masked), where re-collating a sub-range
        # would change the padded width.
        for s in segs:
            # every collate() output is batch-first with the same leading dim,
            # so any entry answers "how many windows" and slicing dim 0 is
            # valid across all of them
            b = next(iter(s.values())).shape[0]
            i = 0
            while i < b:
                n = min(seg_size["n"], b - i)
                try:
                    seg = {k: (v if n == b else v[i : i + n]).to(dev) for k, v in s.items()}
                    ctx = torch.enable_grad() if grad else torch.no_grad()
                    with ctx, torch.autocast(dev, dtype=torch.bfloat16):
                        fwd = model(seg)
                except torch.cuda.OutOfMemoryError:
                    seg_size["ok"] = 0
                    torch.cuda.empty_cache()
                    if seg_size["n"] <= 8:
                        # scale-to-zero: below this the fixed footprint
                        # dominates. Park ONLY for genuine scarcity and
                        # retry; a floor OOM with VRAM free re-raises
                        # (fragmentation/bug — not parkable)
                        if park_for_cotenant("rl learner"):
                            continue
                        raise
                    seg_size["n"] //= 2
                    print(f"[rl] OOM at seg {n} -> retrying at {seg_size['n']}")
                    continue
                yield seg, fwd
                i += n
                # scale-back-up: after a quiet stretch, restore toward the
                # launch seg if the free-VRAM tier allows (no trial OOM —
                # the probe reads mem_get_info against the autotune tiers)
                seg_size["ok"] += 1
                if seg_size["n"] < seg_size["target"] and seg_size["ok"] >= RESTORE_AFTER:
                    seg_size["ok"] = 0
                    t = min(seg_size["target"], seg_tier(free_mb()))
                    if t > seg_size["n"]:
                        print(f"[rl] VRAM recovered -> seg {t}")
                        seg_size["n"] = t

    return forward_segments


def main() -> None:
    import argparse
    import json
    import time
    from pathlib import Path

    from anvil.training.train import build_net

    ap = argparse.ArgumentParser(description="V-trace self-play learner (M2 D6)")
    ap.add_argument("--store", required=True, help="csv of iteration store dirs")
    ap.add_argument(
        "--weights",
        default=None,
        help="csv of expected passes per store (replay mixing; fractions subsample); default all 1",
    )
    ap.add_argument("--ckpt", required=True, help="init/pi checkpoint (last.pt)")
    ap.add_argument(
        "--ref-ckpt", default=None, help="mu-recompute tripwire checkpoint (default: --ckpt)"
    )
    ap.add_argument(
        "--critic-ckpt",
        default=None,
        help="full-vis critic checkpoint (d6-vtrace-loop §6f): "
        "pass-A values (baseline + bootstrap) come from this "
        "frozen net on full-vis windows; the policy's own "
        "masked value head keeps training on the same vs "
        "targets. Off = v0 behavior (masked head values).",
    )
    ap.add_argument("--out", required=True)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument(
        "--pay-lr",
        type=float,
        default=None,
        help="separate lr for the M9 §3c payment params (pay_ prefix). "
        "The loop takes one optimizer step per --traj-per-step "
        "trajectories (~417/iteration at run17 volumes), so at the "
        "trunk lr a fresh head displaces <=0.03 across a whole probe "
        "run: pay_bias would sit at its +2.0 init and pay_kind_emb "
        "would never reach the ~0.1 per-element scale its neighbours "
        "carry. m9-plan D4 recipe pin 2. None = one group (v0).",
    )
    ap.add_argument("--wd", type=float, default=0.0)
    ap.add_argument("--traj-per-step", type=int, default=4)
    ap.add_argument("--seg", type=int, default=256, help="windows per GPU pass")
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--rho-bar", type=float, default=1.0)
    ap.add_argument("--c-bar", type=float, default=1.0)
    ap.add_argument("--value-weight", type=float, default=0.5)
    ap.add_argument(
        "--ent-weight",
        type=float,
        default=3e-3,
        help="weight on the hinge entropy-floor penalty (ADR-0017: "
        "the always-on bonus had no equilibrium and ran away)",
    )
    ap.add_argument(
        "--ent-floor",
        type=float,
        default=0.08,
        help="hinge target: penalize segments whose MEAN composite "
        "entropy falls below this; zero gradient above. Default "
        "~half the BC-init mean (~0.15) — a collapse guard, not "
        "a pin (pinning at init would forbid legitimate "
        "sharpening)",
    )
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument(
        "--tripwire-every", type=int, default=25, help="mu-recompute check every Nth trajectory"
    )
    ap.add_argument(
        "--penalty",
        type=float,
        default=0.0,
        help="rejected-intent penalty lambda (d6-vtrace-loop §6c): "
        "negative reward on vetoed cast attempts and dropped/"
        "repaired combat declarations; 0 = off. ADR-0054 pricing "
        "= 0.01 with --penalty-grouping first (per-window "
        "exposure strictly below one held turn's measured cost). "
        "A reward change is an RL-chain boundary — never mix "
        "replay stores across different lambda values.",
    )
    ap.add_argument(
        "--penalty-grouping",
        choices=["first", "event"],
        default="first",
        help="§6c pricing basis (ADR-0054): first = one penalty per "
        "veto WINDOW (re-ask chain continuations free — chain "
        "length is realizer walk-down, not graded intent); "
        "event = the superseded per-attempt pricing (run5-run13 "
        "era reproduction only).",
    )
    # ---- C-seq + C2a policy-side aux (ADR-0054) ----
    ap.add_argument(
        "--seq-labels",
        default=None,
        help="csv of forced-seq labels.jsonl paths or campaign run dirs "
        "(ADR-0054 C-seq). With --seq-stores, enables the sequence-"
        "contrastive term L_seq = -A*[logp(cast*) - logp(pass)] and "
        "the C2a masked-head aux at the same fork windows. Labels "
        "are policy-conditional: pass only THIS iteration's fresh "
        "campaign output.",
    )
    ap.add_argument(
        "--seq-stores",
        default=None,
        help="csv of drill fork stores carrying the fork windows the "
        "seq labels join to (keyed header.fork.pg/fp = labels i/fp)",
    )
    ap.add_argument(
        "--seq-frac",
        type=float,
        default=0.1,
        help="target share of policy-gradient loss magnitude the seq "
        "term carries (w_seq calibrated over --seq-calib-steps, "
        "then frozen and logged)",
    )
    ap.add_argument("--seq-calib-steps", type=int, default=50)
    ap.add_argument(
        "--seq-w",
        type=float,
        default=0.0,
        help="explicit w_seq (skips calibration). ADR-0054 calibrates at "
        "RUN start, not per invocation: the driver calibrates in "
        "iteration 0 and carries the value forward via loop_state — "
        "otherwise every iteration's first --seq-calib-steps "
        "optimizer steps (~28%% of an iteration) run with the seq "
        "term silently off.",
    )
    ap.add_argument(
        "--seq-agree-min",
        type=float,
        default=0.5,
        help="act_first_agree threshold below which a point falls back "
        "to the cast-mass-vs-pass contrast (ADR-0054 pin 1)",
    )
    ap.add_argument("--seq-clip", type=float, default=0.25, help="advantage clip (at birth)")
    ap.add_argument(
        "--seq-margin",
        type=float,
        default=6.0,
        help="hinge on the L_seq contrast at ±margin (log-prob units): a "
        "window already preferring its target by e^margin odds gives "
        "zero gradient, bounding |L_seq| ≤ seq_clip*margin. 0 = raw "
        "unbounded contrast — the d6-run14 divergence; keep > 0.",
    )
    ap.add_argument(
        "--kl-abort",
        type=float,
        default=0.0,
        help="end the phase early if a log-window's mean kl_mu exceeds "
        "this (0 = off). A runaway diverges exponentially within one "
        "phase (d6-run14 iter 2: 0.05 -> 20 in ~300 steps); the driver "
        "guard still rejects the ckpt — this just stops wasting steps "
        "and leaves a cleaner state.",
    )
    ap.add_argument(
        "--seq-aux-weight",
        type=float,
        default=0.5,
        help="weight on the C2a masked-head aux BCE toward wr_nat at "
        "fork windows (mirrors --value-weight's scale)",
    )
    ap.add_argument(
        "--tripwire-tol",
        type=float,
        default=0.2,
        help="per-decision |recomputed - recorded| logp tolerance. "
        "bf16 serve-vs-recompute noise reaches ~0.075 on "
        "soft heads (measured, d6 smoke); real skew shows "
        "pick mismatches or O(1)+ deviations",
    )
    ap.add_argument(
        "--max-traj",
        type=int,
        default=0,
        help="stop after N trajectories (0 = whole store). "
        "Profiling/smoke only — a capped run's checkpoint is "
        "trained on a store prefix, never promote one",
    )
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--log-every", type=int, default=20)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    stores = args.store.split(",")
    weights = [float(w) for w in args.weights.split(",")] if args.weights else [1.0] * len(stores)
    assert len(weights) == len(stores)

    dev = args.device
    ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    methods = default_methods()
    n_sa = cfg.get("sa_vocab_size", 0)
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(methods), n_sa=n_sa).to(dev)
    net.load_compat(ckpt["model"])
    net.train()
    ref = build_net(cfg["embed"], cfg["pool_manifest"], len(methods), n_sa=n_sa).to(dev)
    ref_ckpt = (
        torch.load(args.ref_ckpt, map_location="cpu", weights_only=False) if args.ref_ckpt else ckpt
    )
    ref.load_compat(ref_ckpt["model"])
    ref.eval()
    critic = None
    if args.critic_ckpt:
        critic_ck = torch.load(args.critic_ckpt, map_location="cpu", weights_only=False)
        critic = build_net(cfg["embed"], cfg["pool_manifest"], len(methods), n_sa=n_sa).to(dev)
        critic.load_compat(critic_ck["model"])
        critic.eval()
        critic.requires_grad_(False)

    if args.pay_lr is None:
        opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=args.wd)
    else:
        # M9 D4 recipe pin 2: the fresh §3c payment params need their own
        # step size; the trunk keeps the pinned 1e-5 so policy drift is
        # unchanged. Split by name so the grouping is auditable.
        pay = [p_ for n_, p_ in net.named_parameters() if n_.startswith("pay_")]
        rest = [p_ for n_, p_ in net.named_parameters() if not n_.startswith("pay_")]
        if not pay:
            raise ValueError("--pay-lr set but the net carries no pay_ params")
        opt = torch.optim.AdamW(
            [{"params": rest, "lr": args.lr}, {"params": pay, "lr": args.pay_lr}],
            lr=args.lr,
            weight_decay=args.wd,
        )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rl_cfg = {
        **cfg,
        "rl": {
            k: getattr(args, k.replace("-", "_"))
            for k in (
                "store",
                "weights",
                "ckpt",
                "critic_ckpt",
                "lr",
                "pay_lr",
                "traj_per_step",
                "gamma",
                "rho_bar",
                "c_bar",
                "value_weight",
                "ent_weight",
                "ent_floor",
                "epochs",
                "seed",
                "tripwire_tol",
                "penalty",
                "penalty_grouping",
                "seq_labels",
                "seq_stores",
                "seq_frac",
                "seq_calib_steps",
                "seq_agree_min",
                "seq_clip",
                "seq_margin",
                "seq_aux_weight",
                "kl_abort",
            )
        },
        "init_step": ckpt.get("step"),
    }
    (out_dir / "config.json").write_text(json.dumps(rl_cfg, indent=2, default=str))
    metrics = open(out_dir / "metrics.jsonl", "a", buffering=1)

    ds = RlTrajectories(
        stores,
        weights,
        cfg["embed"],
        methods,
        seed=args.seed,
        epochs=args.epochs,
        full_vis=critic is not None,
        seg=args.seg,
        penalty_grouping=args.penalty_grouping,
    )
    loader = torch.utils.data.DataLoader(
        ds,
        batch_size=None,
        num_workers=args.workers,
        collate_fn=_identity,
        persistent_workers=False,
    )

    forward_segments = make_forward_segments(dev, args.seg)

    # ---- C-seq batch (ADR-0054): built once per invocation — the campaign
    # regenerates labels fresh each iteration, so one rl.py run sees one
    # policy-conditional label generation ----
    if bool(args.seq_labels) != bool(args.seq_stores):
        raise SystemExit("--seq-labels and --seq-stores go together")
    seq = None
    w_seq: float | None = args.seq_w if args.seq_w > 0 else None
    if args.seq_labels:
        from anvil.training.seqlabels import build_seq_batch

        seq = build_seq_batch(
            args.seq_labels.split(","),
            args.seq_stores.split(","),
            cfg["embed"],
            methods,
            seg=args.seg,
            agree_min=args.seq_agree_min,
            clip=args.seq_clip,
        )
        if seq is None:
            print("[rl] WARNING: seq labels joined ZERO fork windows — seq term OFF this run")
        else:
            print(
                f"[rl] seq batch: {seq['n']} fork windows / {seq['n_labels']} labels "
                f"({seq['n_cast_target']} specific-cast, {seq['n_mass']} mass-fallback; "
                f"mean |adv| {seq['mean_abs_adv']:.4f})"
            )
    calib_pg = 0.0
    calib_traj = 0
    calib_steps = 0
    share_pg = share_seq = 0.0
    share_traj = share_steps = 0
    kl_aborted = False

    # step continues from the init checkpoint: monotonic across the whole
    # BC->RL chain, so mu meta "step" uniquely names the generating ckpt
    # (per-iteration counters would collide in the tripwire's mu_step gate)
    step = ckpt.get("step") or 0
    n_traj = 0
    last_flush_traj = 0
    skips: dict[str, int] = {}
    tripwire_viol = 0
    acc: dict[str, float] = {}
    t0 = time.monotonic()
    win_count = 0

    def save(tag="last"):
        torch.save(
            {"step": step, "model": net.state_dict(), "config": rl_cfg}, out_dir / f"{tag}.pt"
        )

    # Per-phase wall clock (bench 2026-07-25: the GPU sits ~90% idle through
    # the train phase and throughput is flat in both --seg and --workers, so
    # the bottleneck is neither device capacity nor worker count — this says
    # which phase actually holds the clock). `load` is isolated by timing the
    # loader handoff itself, so `continue` paths can't misattribute it.
    tprof: dict[str, float] = {}

    def timed_loader(src):
        it = iter(src)
        while True:
            t0 = time.monotonic()
            try:
                item = next(it)
            except StopIteration:
                return
            tprof["load"] = tprof.get("load", 0.0) + (time.monotonic() - t0)
            yield item

    def tick(key: str, t: float) -> float:
        now = time.monotonic()
        tprof[key] = tprof.get(key, 0.0) + (now - t)
        return now

    opt.zero_grad(set_to_none=True)
    for item in timed_loader(loader):
        if "skip" in item:
            skips[item["skip"]] = skips.get(item["skip"], 0) + 1
            continue
        segs, mu_logp, reward = item["segs"], item["mu_logp"], item["reward"]
        t_len = item["t_len"]
        if t_len == 0:
            continue
        if args.max_traj and n_traj >= args.max_traj:
            print(f"[rl] --max-traj {args.max_traj} reached; stopping early")
            break
        n_traj += 1
        win_count += t_len
        tphase = time.monotonic()

        # ---- pass A (no grad): values + logp_pi for targets/ratios ----
        # §6f: with a critic, values come from the frozen full-vis net on the
        # fv windows (baseline AND bootstrap — asymmetric V-trace); the policy
        # forward still supplies logp_pi, and its masked head's first-window
        # read is logged as v0_masked (the live masked-vs-full-vis A/B).
        values, logp_pi = [], []
        v0_masked = None
        for seg, fwd in forward_segments(net, segs, grad=False):
            logp_pi.append(composite_logp(fwd, seg)["logp"].cpu())
            if critic is None:
                values.append(torch.sigmoid(fwd["value_logit"].float()).cpu())
            elif v0_masked is None:
                v0_masked = float(torch.sigmoid(fwd["value_logit"].float())[0])
        if critic is not None:
            for seg, fwd in forward_segments(critic, item["segs_fv"], grad=False):
                values.append(torch.sigmoid(fwd["value_logit"].float()).cpu())
        tphase = tick("fwd_nograd", tphase)
        values = torch.cat(values)
        logp_pi = torch.cat(logp_pi)
        if len(values) != len(logp_pi):
            raise RuntimeError(
                f"game {item['g']} seat {item['seat']}: fv window count "
                f"{len(values)} != masked {len(logp_pi)} — loader misalignment"
            )

        # ---- mu recompute tripwire (sampled): serve/loader drift detector ----
        if n_traj % args.tripwire_every == 1 and item.get("mu_step") == ref_ckpt.get("step"):
            head = segs[:1]  # the first pre-collated segment
            n_head = head[0]["label"].shape[0]
            ((seg, fwd),) = forward_segments(ref, head, grad=False)
            lp_ref = composite_logp(fwd, seg, temperature=float(item.get("mu_tau", 1.0)))[
                "logp"
            ].cpu()
            bad = (lp_ref - mu_logp[:n_head]).abs() > args.tripwire_tol
            if bad.any():
                tripwire_viol += int(bad.sum())
                print(
                    f"[rl] TRIPWIRE: game {item['g']} seat {item['seat']}: "
                    f"{int(bad.sum())}/{n_head} decisions off by "
                    f"{float((lp_ref - mu_logp[:n_head]).abs().max()):.4f} "
                    "— trajectory dropped"
                )
                continue

        tphase = tick("tripwire", tphase)
        step_r = (-args.penalty) * item["rej"] if args.penalty else None
        vs, pg_adv, rho = vtrace_targets(
            values,
            logp_pi,
            mu_logp,
            reward,
            gamma=args.gamma,
            rho_bar=args.rho_bar,
            c_bar=args.c_bar,
            step_r=step_r,
        )

        # ---- pass B (grad): policy gradient + value + entropy ----
        off = 0
        traj_pg = 0.0
        for seg, fwd in forward_segments(net, segs, grad=True):
            b = seg["label"].shape[0]
            adv = pg_adv[off : off + b].to(dev)
            tgt = vs[off : off + b].clamp(0.0, 1.0).to(dev)
            lp = composite_logp(fwd, seg)["logp"]
            ent = composite_entropy(fwd, seg)
            pg_loss = -(adv * lp).sum() / t_len
            v_loss = (
                F.binary_cross_entropy_with_logits(fwd["value_logit"].float(), tgt, reduction="sum")
                / t_len
            )
            ent_mean = ent.sum() / t_len  # also the monitor's ent metric
            ent_pen = entropy_hinge(ent, args.ent_floor, b, t_len)
            loss = (
                pg_loss + args.value_weight * v_loss + args.ent_weight * ent_pen
            ) / args.traj_per_step
            loss.backward()
            acc["pg"] = acc.get("pg", 0.0) + float(pg_loss)
            traj_pg += float(pg_loss)
            acc["v"] = acc.get("v", 0.0) + float(v_loss)
            acc["ent"] = acc.get("ent", 0.0) + float(ent_mean)
            acc["ent_pen"] = acc.get("ent_pen", 0.0) + float(ent_pen)
            off += b
        tphase = tick("fwd_bwd", tphase)
        acc["rho_mean"] = acc.get("rho_mean", 0.0) + float(rho.mean())
        acc["rho_clip"] = acc.get("rho_clip", 0.0) + float((rho >= args.rho_bar).float().mean())
        acc["kl_mu"] = acc.get("kl_mu", 0.0) + float((mu_logp - logp_pi).mean())
        acc["reward"] = acc.get("reward", 0.0) + reward
        acc["v0"] = acc.get("v0", 0.0) + float(values[0])
        if v0_masked is not None:
            acc["v0_masked"] = acc.get("v0_masked", 0.0) + v0_masked
        acc["rej"] = acc.get("rej", 0.0) + float(item["rej"].sum())
        if seq is not None and w_seq is None:
            calib_pg += abs(traj_pg)
            calib_traj += 1
        if seq is not None and w_seq is not None:
            # seq-share window accumulators (d6-run14): the calibration
            # identity w_seq*|L_seq| ≈ seq_frac*mean|PG per traj| is the
            # design's load-bearing invariant — measure it continuously,
            # the driver guards on the iteration mean
            share_pg += abs(traj_pg)
            share_traj += 1

        if n_traj % args.traj_per_step == 0:
            # ---- C-seq step (ADR-0054): calibrate w_seq over the first
            # --seq-calib-steps optimizer steps (loss-magnitude proxy for
            # gradient mass: w_seq * |L_seq| ≈ seq_frac * mean |PG per
            # trajectory|), then apply the seq batch every step ----
            if seq is not None:
                if w_seq is None:
                    calib_steps += 1
                    if calib_steps >= args.seq_calib_steps:
                        raw, aux_raw = seq_pass(
                            net,
                            seq["segs"],
                            forward_segments,
                            0.0,
                            0.0,
                            grad=False,
                            margin=args.seq_margin,
                        )
                        mean_pg = calib_pg / max(calib_traj, 1)
                        w_seq = args.seq_frac * mean_pg / max(abs(raw), 1e-4)
                        cal = {
                            "w_seq": w_seq,
                            "seq_frac": args.seq_frac,
                            "mean_abs_pg_per_traj": mean_pg,
                            "l_seq_raw_at_calib": raw,
                            "seq_aux_raw_at_calib": aux_raw,
                            "calib_steps": calib_steps,
                            "calib_traj": calib_traj,
                            "n_windows": seq["n"],
                        }
                        (out_dir / "seq_calibration.json").write_text(
                            json.dumps(cal, indent=1) + "\n"
                        )
                        print(f"[rl] w_seq calibrated: {cal}")
                else:
                    raw, aux_raw = seq_pass(
                        net,
                        seq["segs"],
                        forward_segments,
                        w_seq,
                        args.seq_aux_weight,
                        grad=True,
                        margin=args.seq_margin,
                    )
                    acc["seq_raw"] = acc.get("seq_raw", 0.0) + raw
                    acc["seq_aux"] = acc.get("seq_aux", 0.0) + aux_raw
                    share_seq += raw
                    share_steps += 1
            torch.nn.utils.clip_grad_norm_(net.parameters(), args.clip)
            opt.step()
            opt.zero_grad(set_to_none=True)
            step += 1
            if step % args.log_every == 0:
                # actual trajectories since the last flush — the modulo is on
                # the ABSOLUTE step (monotonic across the BC->RL chain), so
                # the first window after a non-aligned init step is short;
                # dividing by the nominal window diluted first-row metrics
                # (run-1 iter rows; rediscovered on the re-ask smoke)
                n = max(n_traj - last_flush_traj, 1)
                last_flush_traj = n_traj
                wall = time.monotonic() - t0
                # seq_share = w_seq*|mean L_seq per step| / mean|PG per traj|
                # — the calibration identity, measured live; at calibration
                # it equals seq_frac by construction
                seq_share = None
                if share_steps and share_traj and share_pg > 0 and w_seq:
                    seq_share = round(
                        w_seq * abs(share_seq / share_steps) / (share_pg / share_traj), 5
                    )
                share_pg = share_seq = 0.0
                share_traj = share_steps = 0
                row = {
                    "step": step,
                    "traj": n_traj,
                    **{k: round(v / n, 5) for k, v in acc.items()},
                    # seq_raw/seq_aux above are per-TRAJECTORY means of a
                    # once-per-optimizer-step term (trend metric, not a
                    # loss share); w_seq is the frozen calibration
                    **({"w_seq": round(w_seq, 6)} if w_seq is not None else {}),
                    **({"seq_share": seq_share} if seq_share is not None else {}),
                    "skips": dict(skips),
                    "tripwire_viol": tripwire_viol,
                    "win_per_s": round(win_count / wall, 1),
                    # cumulative share of wall clock per phase; `load` is
                    # loader-handoff wait, so a high share means the
                    # learner is data-starved, not compute-bound
                    "phase": {k: round(v / wall, 3) for k, v in sorted(tprof.items())},
                }
                metrics.write(json.dumps(row) + "\n")
                print(f"[rl] {row}")
                if args.kl_abort > 0 and row.get("kl_mu", 0.0) > args.kl_abort:
                    kl_aborted = True
                    print(
                        f"[rl] KL ABORT: window kl_mu {row['kl_mu']} > "
                        f"{args.kl_abort} — ending the phase early (the "
                        f"driver guard rejects the ckpt on the iteration mean)"
                    )
                acc = {}
            if step % 200 == 0:
                save()
        if kl_aborted:
            break

    save()
    (out_dir / "DONE").touch()  # completion marker: the loop driver skips
    # the train phase on resume iff this exists (last.pt alone is ambiguous
    # — periodic saves leave one behind mid-run)
    wall = time.monotonic() - t0
    print(
        f"[rl] done: {step} steps, {n_traj} trajectories, skips={skips}, "
        f"tripwire_viol={tripwire_viol}"
    )
    print(
        f"[rl] wall {wall:.0f}s; phase shares "
        + ", ".join(f"{k} {v / wall:.1%}" for k, v in sorted(tprof.items()))
    )


if __name__ == "__main__":
    main()
