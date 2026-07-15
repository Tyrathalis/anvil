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

from anvil.training.dataset import TASKS


def _gather_lp(logits: torch.Tensor, labels: torch.Tensor,
               temperature: float = 1.0) -> torch.Tensor:
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
    is_priority = batch["task"] == TASKS["priority"]
    label = torch.where(is_priority, batch["label"], torch.full_like(batch["label"], -1))
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
    lp_cnt = _gather_lp(fwd["cmb_count_logits"], batch["cmb_count_label"],
                        temperature).sum(-1)
    lp_atgt = _gather_lp(fwd["atk_tgt_logits"], batch["atk_tgt_labels"],
                         temperature).sum(-1)
    lp_blk = _gather_lp(fwd["blk_logits"], batch["blk_label"], temperature).sum(-1)

    total = lp_choice + lp_tgt + lp_x + lp_bool + lp_num + lp_atk + lp_cnt \
        + lp_atgt + lp_blk
    return {"logp": total, "choice": lp_choice, "tgt": lp_tgt, "x": lp_x,
            "bool": lp_bool, "num": lp_num, "atk": lp_atk, "cnt": lp_cnt,
            "atgt": lp_atgt, "blk": lp_blk}


def apply_mu_labels(ex: dict, rec: dict) -> dict:
    """Write the sampled action from a mu record into an example's label
    fields — the inclusion rules in label form (an unlabeled factor is -1 and
    contributes nothing to composite_logp). Inverse of sampling.mu_record;
    the two must stay in lockstep."""
    from anvil.training.dataset import T_MAX
    n_i = ex["entities"].shape[0]
    task = rec["task"]
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

    is_priority = batch["task"] == TASKS["priority"]
    ent = cat_ent(fwd["policy_logits"], is_priority & (batch["label"] >= 0))
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


def vtrace_targets(values: torch.Tensor, logp_pi: torch.Tensor,
                   logp_mu: torch.Tensor, reward: float, gamma: float = 1.0,
                   rho_bar: float = 1.0, c_bar: float = 1.0
                   ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """V-trace value targets + policy-gradient advantages for ONE trajectory
    (one seat's decision sequence in one game, time-ordered).

    values: (T,) V(x_t) under the current net (probabilities, [0,1]).
    reward: terminal only — 1 win, 0 otherwise (loss/draw/cap: the §3d
    cap-aware rule; a stalling leader forfeits the +1). The terminal state
    itself has value 0 (nothing follows); the reward rides the LAST
    transition — putting it in both places double-counts.

    Returns (vs, pg_adv, rho): vs (T,) the value regression targets,
    pg_adv (T,) = rho_s (r_s + gamma vs_{s+1} - V(x_s)), rho (T,) clipped.
    """
    t_len = values.shape[0]
    rho = torch.exp(logp_pi - logp_mu)
    c = rho.clamp(max=c_bar)
    rho = rho.clamp(max=rho_bar)
    r = torch.zeros(t_len)
    r[-1] = reward
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
        if len(rec["cnt"]) != a_i or not all(
                1 <= k <= COMBAT_COUNT_MAX for k in rec["cnt"]):
            return False
        if task == "attack":
            if len(rec["atk"]) != a_i or len(rec["atgt"]) != a_i:
                return False
            if not all(0 <= t < n_i + p
                       for y, t in zip(rec["atk"], rec["atgt"]) if y):
                return False
        else:
            m_i = ex["blk_atk_rows"].shape[0]
            if len(rec["blk"]) != a_i or not all(
                    0 <= b <= m_i for b in rec["blk"]):
                return False
    return True


def game_trajectories(store, feat, g: int):
    """Per-seat mu-covered trajectories of one stored game, serve-identical
    windows via the featurizer path (store_wire_hist -> Featurizer.example ->
    apply_mu_labels).

    Returns (trajs, skip_reason): trajs = [(seat, [(ex, rec), ...], reward)],
    reward per §3d — win 1, loss/draw/cap 0 (a stalling leader forfeits the
    +1); skip_reason set (and trajs empty) for crash/no-outcome games, whose
    returns are engine artifacts, and for games without mu records."""
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
            wire["hist"] = store_wire_hist(prior, dec["_pos"])
            ex, _aux = feat.example(wire, traj.header, rec["task"])
            if not mu_matches(ex, rec):
                return [], "mu_mismatch"
            apply_mu_labels(ex, rec)
            by_seat.setdefault(dec["p"], []).append((ex, rec))
        prior.append(dec)
    return [(p, exs, 1.0 if winner == p else 0.0)
            for p, exs in sorted(by_seat.items())], None


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

    def __init__(self, stores: list[str], weights: list[float], stem: str,
                 methods: list[str], seed: int = 0, epochs: int = 1):
        self.stores = stores
        self.weights = weights
        self.stem = stem
        self.methods = methods
        self.seed = seed
        self.epochs = epochs

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
                trajs, skip = game_trajectories(opened[si], feat, g)
                if skip is not None:
                    yield {"skip": skip, "g": g}
                    continue
                st = opened[si]
                if hasattr(st, "_store_of"):
                    st = st._store_of[g]
                mu_step = (st.mu_meta or {}).get("step")
                for seat, exs, reward in trajs:
                    yield {"g": g, "seat": seat, "reward": reward,
                           # mu_step: which checkpoint generated these mu
                           # records — the recompute tripwire only applies
                           # when it matches the ref net (replay stores were
                           # sampled under older checkpoints)
                           "mu_step": mu_step,
                           "exs": [e for e, _ in exs],
                           "mu_logp": torch.tensor([r["logp"] for _, r in exs],
                                                   dtype=torch.float32)}


def main() -> None:
    import argparse
    import json
    import time
    from pathlib import Path

    from anvil.training.dataset import collate, default_methods
    from anvil.training.train import build_net

    ap = argparse.ArgumentParser(description="V-trace self-play learner (M2 D6)")
    ap.add_argument("--store", required=True, help="csv of iteration store dirs")
    ap.add_argument("--weights", default=None,
                    help="csv of expected passes per store (replay mixing; "
                         "fractions subsample); default all 1")
    ap.add_argument("--ckpt", required=True, help="init/pi checkpoint (last.pt)")
    ap.add_argument("--ref-ckpt", default=None,
                    help="mu-recompute tripwire checkpoint (default: --ckpt)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--wd", type=float, default=0.0)
    ap.add_argument("--traj-per-step", type=int, default=4)
    ap.add_argument("--seg", type=int, default=256, help="windows per GPU pass")
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--rho-bar", type=float, default=1.0)
    ap.add_argument("--c-bar", type=float, default=1.0)
    ap.add_argument("--value-weight", type=float, default=0.5)
    ap.add_argument("--ent-weight", type=float, default=3e-3)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tripwire-every", type=int, default=25,
                    help="mu-recompute check every Nth trajectory")
    ap.add_argument("--tripwire-tol", type=float, default=0.2,
                    help="per-decision |recomputed - recorded| logp tolerance. "
                         "bf16 serve-vs-recompute noise reaches ~0.075 on "
                         "soft heads (measured, d6 smoke); real skew shows "
                         "pick mismatches or O(1)+ deviations")
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--log-every", type=int, default=20)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    stores = args.store.split(",")
    weights = ([float(w) for w in args.weights.split(",")] if args.weights
               else [1.0] * len(stores))
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
    ref_ckpt = (torch.load(args.ref_ckpt, map_location="cpu", weights_only=False)
                if args.ref_ckpt else ckpt)
    ref.load_compat(ref_ckpt["model"])
    ref.eval()

    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=args.wd)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rl_cfg = {**cfg, "rl": {k: getattr(args, k.replace("-", "_")) for k in
                            ("store", "weights", "ckpt", "lr", "traj_per_step",
                             "gamma", "rho_bar", "c_bar", "value_weight",
                             "ent_weight", "epochs", "seed",
                             "tripwire_tol")},
              "init_step": ckpt.get("step")}
    (out_dir / "config.json").write_text(json.dumps(rl_cfg, indent=2, default=str))
    metrics = open(out_dir / "metrics.jsonl", "a", buffering=1)

    ds = RlTrajectories(stores, weights, cfg["embed"], methods,
                        seed=args.seed, epochs=args.epochs)
    loader = torch.utils.data.DataLoader(
        ds, batch_size=None, num_workers=args.workers,
        collate_fn=_identity, persistent_workers=False)

    def forward_segments(model, exs, grad: bool):
        # GENERATOR, deliberately: with grad on, each yielded fwd holds a
        # ~GB-scale autograd graph — the caller must backward/drop it before
        # the next segment runs. Materializing the list OOM'd on the first
        # real store (grindy games reach 2K+ decisions/seat = 8+ segments).
        for i in range(0, len(exs), args.seg):
            seg = {k: v.to(dev) for k, v in
                   collate(exs[i:i + args.seg]).items()}
            ctx = torch.enable_grad() if grad else torch.no_grad()
            with ctx, torch.autocast(dev, dtype=torch.bfloat16):
                fwd = model(seg)
            yield seg, fwd

    # step continues from the init checkpoint: monotonic across the whole
    # BC->RL chain, so mu meta "step" uniquely names the generating ckpt
    # (per-iteration counters would collide in the tripwire's mu_step gate)
    step = ckpt.get("step") or 0
    n_traj = 0
    skips: dict[str, int] = {}
    tripwire_viol = 0
    acc: dict[str, float] = {}
    t0 = time.monotonic()
    win_count = 0

    def save(tag="last"):
        torch.save({"step": step, "model": net.state_dict(), "config": rl_cfg},
                   out_dir / f"{tag}.pt")

    opt.zero_grad(set_to_none=True)
    for item in loader:
        if "skip" in item:
            skips[item["skip"]] = skips.get(item["skip"], 0) + 1
            continue
        exs, mu_logp, reward = item["exs"], item["mu_logp"], item["reward"]
        t_len = len(exs)
        if t_len == 0:
            continue
        n_traj += 1
        win_count += t_len

        # ---- pass A (no grad): values + logp_pi for targets/ratios ----
        values, logp_pi = [], []
        for seg, fwd in forward_segments(net, exs, grad=False):
            values.append(torch.sigmoid(fwd["value_logit"].float()).cpu())
            logp_pi.append(composite_logp(fwd, seg)["logp"].cpu())
        values = torch.cat(values)
        logp_pi = torch.cat(logp_pi)

        # ---- mu recompute tripwire (sampled): serve/loader drift detector ----
        if (n_traj % args.tripwire_every == 1
                and item.get("mu_step") == ref_ckpt.get("step")):
            head = exs[:args.seg]
            (seg, fwd), = forward_segments(ref, head, grad=False)
            lp_ref = composite_logp(fwd, seg)["logp"].cpu()
            bad = (lp_ref - mu_logp[:len(head)]).abs() > args.tripwire_tol
            if bad.any():
                tripwire_viol += int(bad.sum())
                print(f"[rl] TRIPWIRE: game {item['g']} seat {item['seat']}: "
                      f"{int(bad.sum())}/{len(head)} decisions off by "
                      f"{float((lp_ref - mu_logp[:len(head)]).abs().max()):.4f} "
                      "— trajectory dropped")
                continue

        vs, pg_adv, rho = vtrace_targets(values, logp_pi, mu_logp, reward,
                                         gamma=args.gamma, rho_bar=args.rho_bar,
                                         c_bar=args.c_bar)

        # ---- pass B (grad): policy gradient + value + entropy ----
        off = 0
        for seg, fwd in forward_segments(net, exs, grad=True):
            b = seg["label"].shape[0]
            adv = pg_adv[off:off + b].to(dev)
            tgt = vs[off:off + b].clamp(0.0, 1.0).to(dev)
            lp = composite_logp(fwd, seg)["logp"]
            ent = composite_entropy(fwd, seg)
            pg_loss = -(adv * lp).sum() / t_len
            v_loss = F.binary_cross_entropy_with_logits(
                fwd["value_logit"].float(), tgt, reduction="sum") / t_len
            ent_bonus = ent.sum() / t_len
            loss = (pg_loss + args.value_weight * v_loss
                    - args.ent_weight * ent_bonus) / args.traj_per_step
            loss.backward()
            acc["pg"] = acc.get("pg", 0.0) + float(pg_loss)
            acc["v"] = acc.get("v", 0.0) + float(v_loss)
            acc["ent"] = acc.get("ent", 0.0) + float(ent_bonus)
            off += b
        acc["rho_mean"] = acc.get("rho_mean", 0.0) + float(rho.mean())
        acc["rho_clip"] = acc.get("rho_clip", 0.0) + float((rho >= args.rho_bar).float().mean())
        acc["kl_mu"] = acc.get("kl_mu", 0.0) + float((mu_logp - logp_pi).mean())
        acc["reward"] = acc.get("reward", 0.0) + reward
        acc["v0"] = acc.get("v0", 0.0) + float(values[0])

        if n_traj % args.traj_per_step == 0:
            torch.nn.utils.clip_grad_norm_(net.parameters(), args.clip)
            opt.step()
            opt.zero_grad(set_to_none=True)
            step += 1
            if step % args.log_every == 0:
                n = args.traj_per_step * args.log_every
                row = {"step": step, "traj": n_traj,
                       **{k: round(v / n, 5) for k, v in acc.items()},
                       "skips": dict(skips), "tripwire_viol": tripwire_viol,
                       "win_per_s": round(win_count / (time.monotonic() - t0), 1)}
                metrics.write(json.dumps(row) + "\n")
                print(f"[rl] {row}")
                acc = {}
            if step % 200 == 0:
                save()

    save()
    print(f"[rl] done: {step} steps, {n_traj} trajectories, skips={skips}, "
          f"tripwire_viol={tripwire_viol}")


if __name__ == "__main__":
    main()
