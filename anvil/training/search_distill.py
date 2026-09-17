"""M12 Build 4 (ADR-0111): the re-warm as OFFLINE DISTILLATION TOWARD THE SEARCH
(the user's option 4, 09-16). The representation completions are additive and
zero-init, so nothing needs recovering; the re-warm's one job is to give the
new paths (the stack-entry projections, the ability-text descriptor) a gradient
that carries information the old inputs lacked — and the only banked signal
that does without pulling the RL policy back toward the heuristic is the
search's own: the per-option leaf values the search directive recorded on
every searched priority window (`labels.jsonl` `ev: search`, rate 1) in the
Build 2 arms and the Build 3 / 4 pools (≈ 600K windows).

Loss per searched window, over the model's candidates: KL(softmax(v / T) ||
policy) — the policy toward the search's leaf-value softmax (the acting rule's
distribution, ADR-0104) — plus BCE(value_logit, Σ p v) — the value head toward
the search's estimate of the state. Options without a leaf value (void / skip
rolls) leave the target; the pass option is candidate 0; wire options that the
loader collapses onto one candidate average their values.

Join: a search row (game seed, t, ph, seat, option labels, `sw` ordinal) to
its `chooseSpellAbilityToPlay` dec record in the run's obs frames, walked in
order per game; featurized on the WIRE path (Featurizer.example, the serve
featurizer — the same tensors the server builds, incl. the Build 4 fields).

Reads (held-out games by hash, before and after): mean KL, top-1 agreement
with the search's argmax, the value head's Spearman vs the windows' values.

  uv run python -m anvil.training.search_distill --runs 'data/runs/b4-tgtlab-*' \\
      --init data/training/m12-build4-e1/last.pt --out data/runs/build4-rewarm \\
      --ckpt-out data/training/m12-build4-rw --steps 8000
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, IterableDataset

from anvil.store.trajectories import decode_frame

REPO = Path(__file__).resolve().parents[2]
ABIL = "data/embeddings/abil-cf2ca6ba-b4s-qwen3"
NEW_PATHS = ("assemble.stack_", "cand_abil_proj")  # Build 4's zero-init representation paths
POLICY_PATHS = ("ptr_query", "ptr_key", "sa_proj", "value_head")
PRIORITY = "chooseSpellAbilityToPlay"
VALID_KINDS = {"leaf", "end", "eot", "h2", "next"}


def fold_of(name: str, g: int, folds: int) -> int:
    h = hashlib.sha1(f"{name}:{g}".encode()).digest()
    return int.from_bytes(h[:4], "little") % folds


# ---------------------------------------------------------------- the join

def run_games(run: Path) -> Iterator[tuple[Path, dict]]:
    """(worker dir, idx entry) for every game of a harness run."""
    for w in sorted(run.glob("workers/inv-*")):
        idx = w / "obs.idx.jsonl"
        if not idx.exists():
            continue
        for line in idx.open():
            if line.strip():
                yield w, json.loads(line)


def rows_by_seed(w: Path) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = defaultdict(list)
    lab = w / "labels.jsonl"
    if not lab.exists():
        return out
    for line in lab.open():
        if '"ev":"search"' not in line:
            continue
        r = json.loads(line)
        if r.get("ev") == "search" and r.get("opts"):
            out[int(r["seed"])].append(r)
    for v in out.values():
        v.sort(key=lambda r: r.get("sw", 0))
    return out


def align(labels: list[str], opts: list[dict]) -> list[int] | None:
    """The row's non-pass options (the SEARCHED list: contiguous, the mana
    abilities the search skips removed) aligned in order against the dec's
    option list (the mask: mana abilities included) by render prefix; None
    when a label finds no later option."""
    out: list[int] = []
    j = 0
    for lab in labels:
        found = -1
        while j < len(opts):
            sa = opts[j].get("sa") or ""
            j += 1
            n = min(len(str(lab)), len(sa))  # the row truncates labels (~25 chars), the dec renders up to 120
            if n > 0 and str(lab)[:n] == sa[:n]:
                found = j - 1
                break
        if found < 0:
            return None
        out.append(found)
    return out


def match(decs: list[dict], rows: list[dict], counts: Counter) -> list[tuple[dict, int, dict]]:
    """(row, dec index, row option index -> dec option index): rows in sw
    order, decs in seq order, one pointer per seat; a row takes the first
    later priority dec of its seat at its (t, ph) whose option list aligns
    with the row's labels (a label-less row = the first such dec)."""
    out = []
    ptr: dict[int, int] = defaultdict(int)
    for r in rows:
        seat = int(r["seat"])
        row_opts = [o for o in r["opts"] if o.get("o", 0) != 0]
        labels = [o["label"] for o in row_opts]
        j = ptr[seat]
        found = -1
        o_to_dec: dict[int, int] = {}
        while j < len(decs):
            d = decs[j]
            j += 1
            if d.get("m") != PRIORITY or d.get("p") != seat:
                continue
            if d.get("t", 0) > r["t"]:
                break
            if d.get("t") != r["t"] or d.get("ph") != r["ph"]:
                continue
            al = align(labels, d.get("opts") or [])
            if al is None:
                continue
            found = j - 1
            o_to_dec = {int(o["o"]): di for o, di in zip(row_opts, al)}
            break
        if found < 0:
            counts["row_unmatched"] += 1
            continue
        ptr[seat] = found + 1
        out.append((r, found, o_to_dec))
    return out


def option_values(r: dict) -> dict[int, float]:
    """row option index -> mean leaf value over valid rolls (absent = no value)."""
    out: dict[int, float] = {}
    for o in r["opts"]:
        vs = [float(v) for v, k in zip(o.get("v") or [], o.get("kind") or []) if v is not None and k in VALID_KINDS]
        if vs:
            out[int(o["o"])] = sum(vs) / len(vs)
    return out


def option_voids(r: dict) -> set[int]:
    """row option indices whose every roll voided (the copy could not realize
    the option: the heuristic would not / could not play it here) — the
    playability negatives (09-17: the distilled policy over-generalized the
    acted windows' casts into unplayable ones; these teach it not to)."""
    out: set[int] = set()
    for o in r["opts"]:
        ks = o.get("kind") or []
        if ks and all(k in ("void", "skip") for k in ks):
            out.add(int(o["o"]))
    return out


# ---------------------------------------------------------------- the dataset

class SearchWindows(IterableDataset):
    def __init__(self, runs: list[Path], embed: str, abilities: str | None, folds: int, fold: int | None,
                 split: str, seed: int = 0, max_games: int | None = None, shuffle: bool = True):
        self.runs = runs
        self.embed = embed
        self.abilities = abilities
        self.folds, self.fold, self.split = folds, fold, split
        self.seed, self.max_games, self.shuffle = seed, max_games, shuffle
        self.counts: Counter = Counter()

    def _keep(self, run: Path, g: int) -> bool:
        if self.fold is None:
            return True
        f = fold_of(run.name, g, self.folds)
        return (f == self.fold) if self.split == "test" else (f != self.fold)

    def _games(self) -> list[tuple[Path, Path, dict]]:
        items = []
        for run in self.runs:
            for w, e in run_games(run):
                if self._keep(run, int(e["g"])):
                    items.append((run, w, e))
        if self.max_games:
            rng = random.Random(self.seed)
            rng.shuffle(items)
            items = items[: self.max_games]
        return items

    def __iter__(self):
        from anvil.bridge.featurize import Featurizer, store_wire_hist
        from anvil.training.dataset import default_methods

        feat = Featurizer(self.embed, default_methods(), abilities=self.abilities)
        wi = torch.utils.data.get_worker_info()
        items = self._games()
        if self.shuffle:
            random.Random(self.seed + (wi.id if wi else 0) * 7919).shuffle(items)
        if wi is not None:
            items = items[wi.id :: wi.num_workers]
        rows_cache: dict[Path, dict[int, list[dict]]] = {}
        data_cache: dict[Path, bytes] = {}
        for run, w, e in items:
            if w not in rows_cache:
                rows_cache[w] = rows_by_seed(w)
                data_cache[w] = (w / "obs.zst").read_bytes()
            rows = rows_cache[w].get(int(e["seed"]))
            if not rows:
                continue
            try:
                hdr, decs, _end, _marks = decode_frame(data_cache[w][e["off"] : e["off"] + e["clen"]], 3)
            except Exception as ex:  # noqa: BLE001
                self.counts[f"undecodable_{type(ex).__name__}"] += 1
                continue
            for r, di, o_to_dec in match(decs, rows, self.counts):
                d = decs[di]
                if d.get("obs") is None:
                    self.counts["no_obs"] += 1
                    continue
                vals = option_values(r)
                voids = option_voids(r)
                if len(vals) < 2:
                    self.counts["lt2_values"] += 1
                    continue
                wire = dict(d)
                wire["hist"] = store_wire_hist(decs[:di], d.get("_pos", di))
                try:
                    ex, aux = feat.example(wire, hdr, "priority")
                except Exception as ex_:  # noqa: BLE001
                    self.counts[f"featurize_{type(ex_).__name__}"] += 1
                    continue
                first = aux["cand_first_opt"]
                # candidate j <- wire option index; the row's o = wire index + 1 (pass = 0)
                cand_v: list[list[float]] = [[] for _ in first]
                cand_void = [False] * len(first)
                opts = d.get("opts") or []
                key_of = {}
                for j, fo in enumerate(first):
                    if fo >= 0:
                        key_of[fo] = j
                # every wire option that collapsed onto a candidate: same (row, normalized sa) key
                from anvil.training.dataset import norm_sa

                cand_key = {j: (aux.get("cand_rows_list") or [None] * len(first))[j] for j in range(len(first))}
                for o_idx, v in vals.items():
                    if o_idx == 0:
                        cand_v[0].append(v)
                        continue
                    wo = o_to_dec.get(o_idx, -1)  # the row's contiguous index -> the dec's option index
                    j = key_of.get(wo)
                    if j is None and 0 <= wo < len(opts):
                        # a collapsed duplicate: find the candidate with the same normalized render + host
                        want = (opts[wo].get("e"), norm_sa(opts[wo].get("sa", "")))
                        for jj, fo in enumerate(first):
                            if fo >= 0 and (opts[fo].get("e"), norm_sa(opts[fo].get("sa", ""))) == want:
                                j = jj
                                break
                    if j is None:
                        self.counts["opt_unmapped"] += 1
                        continue
                    cand_v[j].append(v)
                for o_idx in voids:
                    wo = o_to_dec.get(o_idx, -1)
                    j = key_of.get(wo)
                    if j is not None and not cand_v[j]:
                        cand_void[j] = True
                sd_v = torch.tensor([sum(x) / len(x) if x else 0.0 for x in cand_v], dtype=torch.float32)
                sd_has = torch.tensor([bool(x) for x in cand_v], dtype=torch.bool)
                if int(sd_has.sum()) < 2:
                    self.counts["lt2_mapped"] += 1
                    continue
                ex["sd_v"] = sd_v
                ex["sd_has"] = sd_has
                ex["sd_void"] = torch.tensor(cand_void, dtype=torch.bool)
                ex["sd_nat"] = torch.tensor(float(vals.get(0, float("nan"))))
                ex["sd_margin"] = torch.tensor(float(r.get("margin", float("nan"))))
                self.counts["windows"] += 1
                yield ex


def collate_sd(batch: list[dict]) -> dict:
    from anvil.training.dataset import collate

    sd_v = [x.pop("sd_v") for x in batch]
    sd_has = [x.pop("sd_has") for x in batch]
    sd_void = [x.pop("sd_void") for x in batch]
    nat = [x.pop("sd_nat") for x in batch]
    mg = [x.pop("sd_margin") for x in batch]
    out = collate(batch)
    c = out["cand_rows"].shape[1]
    out["sd_v"] = torch.zeros(len(batch), c)
    out["sd_has"] = torch.zeros(len(batch), c, dtype=torch.bool)
    out["sd_void"] = torch.zeros(len(batch), c, dtype=torch.bool)
    for i, (v, h, vd) in enumerate(zip(sd_v, sd_has, sd_void)):
        out["sd_v"][i, : v.shape[0]] = v
        out["sd_has"][i, : h.shape[0]] = h
        out["sd_void"][i, : vd.shape[0]] = vd
    out["sd_nat"] = torch.stack(nat)
    out["sd_margin"] = torch.stack(mg)
    return out


# ---------------------------------------------------------------- the model side

def load_net(init: str, device: str, abilities: str | None):
    from anvil.policy.surfaces import AbilityCache
    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net

    ck = torch.load(REPO / init, map_location=device, weights_only=False)
    cfg = ck["config"]
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(default_methods()), n_sa=cfg.get("sa_vocab_size", 0)).to(device)
    net.load_compat(ck["model"])
    stem = abilities or cfg.get("abilities")
    if stem:
        net.set_ability_table(AbilityCache(REPO / stem).vectors)
    return net, ck


def set_trainable(net, unfreeze: int) -> int:
    n_layers = len(net.trunk.layers)
    top = set(range(n_layers - unfreeze, n_layers)) if unfreeze > 0 else set()
    for name, p in net.named_parameters():
        p.requires_grad = (
            name.startswith(NEW_PATHS) or name.startswith(POLICY_PATHS)
            or any(name.startswith(f"trunk.layers.{i}.") for i in top)
        )
    return sum(p.numel() for p in net.parameters() if p.requires_grad)


def losses(net, batch: dict, temp: float, bar: float = 0.0, teacher=None) -> tuple[torch.Tensor, torch.Tensor, dict]:
    """Per window: the policy KL toward the search's softmax (the acting rule's
    distribution, ADR-0104) — applied where the search's recorded margin clears
    the bar (below it the search played the policy's own line: no information
    that it should change) — and the value head toward Σ p v on every window."""
    out = net(batch)
    logits = out["policy_logits"].float()
    mask = batch["cand_mask"] & batch["sd_has"]
    v = batch["sd_v"]
    neg = torch.finfo(logits.dtype).min
    cm = batch["cand_mask"]
    p_t = torch.softmax((v / temp).masked_fill(~mask, neg), dim=-1)
    # the student normalized over EVERY legal option (09-17): mass the policy puts on options the
    # search never valued (the voids among them) is a cost here, not invisible
    lp_s = torch.log_softmax(logits.masked_fill(~cm, neg), dim=-1)
    kl = (p_t * (torch.log(p_t.clamp_min(1e-12)) - lp_s)).masked_fill(~mask, 0).sum(-1)
    # the playability term: the policy's mass on the void options -> 0, on every window
    p_s = lp_s.exp()
    void_mass = (p_s * batch["sd_void"].float()).sum(-1)
    void_loss = -torch.log((1.0 - void_mass).clamp_min(1e-6))
    v_t = (p_t * v).sum(-1)
    vb = F.binary_cross_entropy_with_logits(out["value_logit"].float().squeeze(-1), v_t, reduction="none")
    acted = (batch["sd_margin"] >= bar) & torch.isfinite(batch["sd_margin"])
    kl = kl * acted.float()
    # the anchor (09-16 22:45, after the first re-warm collapsed to a pass-happy policy: −46.7 pp,
    # pass mass 0.09 → 0.55): below the bar the acting rule plays the CURRENT policy's line, so the
    # target there is the frozen teacher's distribution — KL(teacher || student) over the legal
    # candidates on every un-acted window; without it the shared layers generalized the acted
    # windows' "pass" onto the 93% the policy term never touched
    anchor = torch.zeros_like(kl)
    if teacher is not None:
        with torch.no_grad():
            tl = teacher(batch)["policy_logits"].float()
        lp_t = torch.log_softmax(tl.masked_fill(~cm, neg), dim=-1)
        anchor = (lp_t.exp() * (lp_t - lp_s)).masked_fill(~cm, 0).sum(-1) * (~acted).float()
    p_full = p_s
    stats = {
        "void_loss": void_loss,
        "void_mass": void_mass,
        "has_void": batch["sd_void"].any(-1).float(),
        "pass_mass": p_full[:, 0],
        "entropy": -(p_full * torch.log(p_full.clamp_min(1e-12))).sum(-1),
        "anchor": anchor,
        "acted": acted.float(),
        "top1": (lp_s.argmax(-1) == (v.masked_fill(~mask, -1.0)).argmax(-1)).float(),
        "v_pred": torch.sigmoid(out["value_logit"].float().squeeze(-1)),
        "v_t": v_t,
    }
    return kl, vb, stats


def _to(b: dict, device: str) -> dict:
    return {k: (t.to(device, non_blocking=True) if torch.is_tensor(t) else t) for k, t in b.items()}


@torch.no_grad()
def evaluate(net, loader, device: str, temp: float, bar: float, max_batches: int | None) -> dict:
    net.eval()
    kls, top1, vp, vt, acted, pm, en, vm = [], [], [], [], [], [], [], []
    for i, b in enumerate(loader):
        if max_batches and i >= max_batches:
            break
        b = _to(b, device)
        with torch.autocast(device, dtype=torch.bfloat16, enabled=device == "cuda"):
            kl, vb, st = losses(net, b, temp, bar)
        kls.append(kl.float().cpu()); top1.append(st["top1"].cpu()); vp.append(st["v_pred"].cpu()); vt.append(st["v_t"].cpu()); acted.append(st["acted"].cpu()); pm.append(st["pass_mass"].cpu()); en.append(st["entropy"].cpu()); vm.append(st["void_mass"].cpu())
    if not kls:
        return {"n": 0}
    kl = torch.cat(kls); t1 = torch.cat(top1); vp_ = torch.cat(vp).numpy(); vt_ = torch.cat(vt).numpy(); ac = torch.cat(acted).bool()
    from scipy.stats import spearmanr

    rho = float(spearmanr(vp_, vt_).correlation) if len(vp_) > 3 else float("nan")
    n_ac = int(ac.sum())
    return {"n": int(kl.numel()), "n_acted": n_ac, "acted_frac": float(ac.float().mean()),
            "kl_acted": float(kl[ac].mean()) if n_ac else float("nan"), "top1_acted": float(t1[ac].mean()) if n_ac else float("nan"),
            "top1_all": float(t1.mean()), "pass_mass": float(torch.cat(pm).mean()), "entropy": float(torch.cat(en).mean()), "void_mass": float(torch.cat(vm).mean()), "value_spearman": rho, "value_mae": float(np.abs(vp_ - vt_).mean())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="comma-separated globs of harness run dirs (labels.jsonl + obs)")
    ap.add_argument("--init", required=True, help="the checkpoint to re-warm")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt-out", default=None, help="save the re-warmed checkpoint here (last.pt)")
    ap.add_argument("--abilities", default=ABIL)
    ap.add_argument("--folds", type=int, default=10)
    ap.add_argument("--fold", type=int, default=0, help="the held-out fold (games by hash)")
    ap.add_argument("--steps", type=int, default=8000)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--temp", type=float, default=0.025, help="the distillation temperature over leaf values (the recipe's T)")
    ap.add_argument("--bar", type=float, default=0.10, help="the policy term applies where the row's margin >= bar (the recipe's acting bar)")
    ap.add_argument("--w-kl", type=float, default=1.0)
    ap.add_argument("--w-value", type=float, default=0.5)
    ap.add_argument("--w-anchor", type=float, default=1.0, help="KL(teacher || student) on the un-acted windows (the frozen init)")
    ap.add_argument("--w-void", type=float, default=1.0, help="the playability term: -log(1 - policy mass on the options that voided on the copies), every window")
    ap.add_argument("--unfreeze", type=int, default=2, help="top-N trunk layers (the new paths + the pointer / value heads always)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-games", type=int, default=None)
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--eval-batches", type=int, default=150)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--clip", type=float, default=1.0)
    a = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(a.seed)
    out_dir = REPO / a.out
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = sorted({Path(p) for pat in a.runs.split(",") for p in glob.glob(str(REPO / pat))})
    if not runs:
        raise SystemExit(f"no runs match {a.runs}")
    net, ck = load_net(a.init, device, a.abilities)
    embed = ck["config"]["embed"]
    teacher = None
    if a.w_anchor > 0:
        import copy

        teacher = copy.deepcopy(net).eval()
        for p_ in teacher.parameters():
            p_.requires_grad = False
    n_train = set_trainable(net, a.unfreeze)
    print(f"[search_distill] runs {len(runs)} init {a.init} trainable {n_train:,} temp {a.temp} device {device}", flush=True)

    def loader(split: str, shuffle: bool):
        ds = SearchWindows(runs, embed, a.abilities, a.folds, a.fold, split, seed=a.seed,
                           max_games=a.max_games, shuffle=shuffle)
        return DataLoader(ds, batch_size=a.batch, collate_fn=collate_sd, num_workers=a.workers,
                          persistent_workers=a.workers > 0, prefetch_factor=4 if a.workers > 0 else None)

    te = loader("test", False)
    before = evaluate(net, te, device, a.temp, a.bar, a.eval_batches)
    print(f"[search_distill] before: {before}", flush=True)
    log = {"args": vars(a), "runs": [str(r) for r in runs], "before": before, "evals": [], "train": []}

    opt = torch.optim.AdamW([p for p in net.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / a.warmup) * 0.5 * (1 + math.cos(math.pi * min(s, a.steps) / a.steps)))
    tr = loader("train", True)
    step = 0
    acc: dict[str, list[float]] = defaultdict(list)
    t0 = time.time()
    done = False
    while not done:
        for b in tr:
            net.train()
            b = _to(b, device)
            with torch.autocast(device, dtype=torch.bfloat16, enabled=device == "cuda"):
                kl, vb, st = losses(net, b, a.temp, a.bar, teacher)
            n_ac = st["acted"].sum().clamp_min(1.0)
            n_un = (1 - st["acted"]).sum().clamp_min(1.0)
            loss = a.w_kl * kl.sum() / n_ac + a.w_value * vb.mean() + a.w_anchor * st["anchor"].sum() / n_un + a.w_void * st["void_loss"].mean()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            if a.clip:
                torch.nn.utils.clip_grad_norm_([p for p in net.parameters() if p.requires_grad], a.clip)
            opt.step(); sched.step(); step += 1
            acc["kl_acted"].append(float(kl.sum() / n_ac)); acc["anchor"].append(float(st["anchor"].sum() / n_un)); acc["void_mass"].append(float(st["void_mass"].mean())); acc["acted"].append(float(st["acted"].mean())); acc["value_bce"].append(float(vb.mean())); acc["top1"].append(float(st["top1"].mean()))
            if step % 100 == 0:
                rec = {"step": step, **{k: float(np.mean(v)) for k, v in acc.items()}, "wall_s": round(time.time() - t0)}
                log["train"].append(rec); acc.clear()
                print(f"[search_distill] {rec}", flush=True)
            if step % a.eval_every == 0 or step >= a.steps:
                ev = evaluate(net, te, device, a.temp, a.bar, a.eval_batches)
                ev["step"] = step; log["evals"].append(ev)
                print(f"[search_distill] eval: {ev}", flush=True)
                (out_dir / "log.json").write_text(json.dumps(log, indent=1) + "\n")
            if step >= a.steps:
                done = True
                break
        else:
            if step == 0:
                raise SystemExit("no training windows")
    counts = dict(getattr(tr.dataset, "counts", {}))
    log["counts"] = counts
    if a.ckpt_out:
        cfg = dict(ck["config"])
        cfg["abilities"] = a.abilities
        cfg["search_distill"] = {"init": a.init, "steps": step, "temp": a.temp, "bar": a.bar, "w_kl": a.w_kl, "w_value": a.w_value, "w_anchor": a.w_anchor, "w_void": a.w_void,
                                 "unfreeze": a.unfreeze, "runs": [str(r) for r in runs], "before": before, "after": log["evals"][-1]}
        from anvil.encoder.transform import TRANSFORM_VERSION

        cfg["transform_version"] = TRANSFORM_VERSION
        cd = REPO / a.ckpt_out
        cd.mkdir(parents=True, exist_ok=True)
        torch.save({"step": ck.get("step", 0) + step, "model": net.state_dict(), "config": cfg}, cd / "last.pt")
        log["ckpt"] = str(cd / "last.pt")
        print(f"[search_distill] -> {cd / 'last.pt'}", flush=True)
    (out_dir / "log.json").write_text(json.dumps(log, indent=1) + "\n")


if __name__ == "__main__":
    main()
