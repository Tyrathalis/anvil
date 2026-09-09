"""M12 Build 3 evening 4 (ADR-0105): the payment sub-row distillation term —
the pay head's first learning signal.

The search's payment slot (-searchpay B, fork e44d83a8327) expands the first
traced payment window on the top-B candidates' paths: one copy per goal
option ({auto} = answer 0 ∪ the M9 goal options), each valued at the
END-OF-TURN leaf (the seat's first quiescent window of a later turn — where
what stayed untapped is visible), the natural answer re-run under the same
leaf, `rolls` determinizations each. The sub row carries the copy's own
payment dec record (`frame`: the wire shape the pay head is served on).

The target is ASYMMETRIC (the evening-4 pin): most consequential payment
windows are ties (ADR-0075: 3% of them certify), and a leaf-value softmax
over a tie is near-uniform — a KL toward it teaches random deviation, the
evening-2 mode failure. So

    margin = max_goal V(goal) − V(auto)
    margin <  bar  →  target = δ(auto)                 (a TIE row)
    margin ≥  bar  →  target = softmax_a V(a) / T       (a POSITIVE row)

over the answers the search valued (V = the mean over ≥ min_rolls rolls),
and the loss is the cross-entropy from the target to the pay head's
softmax over its candidate slots (slot 0 = auto, slot i = wire option i —
the featurizer's pay_class path is positional). Ties and positives are
always read apart (the ADR-0069 discrimination discipline): the tie rows
anchor the auto prior, the positive rows are the capability.

The M9 pin (no BC from the heuristic) is untouched: the heuristic's
answer (auto) is answer 0 by init; nothing here imitates it — the
counterfactual leaf values are the only label.

Reads a harness run directory (workers/inv-*/labels.jsonl + obs.idx.jsonl /
obs.zst for the parent game's header, keyed by seed) or a flat smoke
directory (search.jsonl + obs.idx.jsonl), like surface_distill.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import torch
from torch.utils.data import IterableDataset, get_worker_info

from anvil.training.dataset import collate, default_methods
from anvil.training.surface_distill import HeaderIndex, _label_files

PAY_KIND = "pay"


def pay_groups(run: Path, bar: float, temp: float, min_rolls: int, counts: Counter) -> Iterator[dict]:
    """Yield one group per usable payment sub row: {seed, frame, n, target,
    margin, positive, spread, leaf}."""
    for f in _label_files(run):
        for ln in open(f):
            if not ln.startswith('{"ev":"search"'):
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            for s in r.get("sub") or []:
                if s.get("kind") != PAY_KIND:
                    continue
                counts["sub:pay"] += 1
                if not s.get("frame"):
                    counts["no_frame"] += 1
                    continue
                n = int(s.get("n", 0))
                vals: dict[int, float] = {}
                for ans in s.get("ans") or []:
                    a = list(ans.get("a") or [])
                    if len(a) != 1 or not 0 <= a[0] < n:
                        continue
                    vs = [v for v in ans.get("v") or [] if v is not None]
                    if len(vs) < min_rolls:
                        counts["answer_short_rolls"] += 1
                        continue
                    vals.setdefault(a[0], sum(vs) / len(vs))
                if 0 not in vals:
                    counts["auto_unvalued"] += 1
                    continue
                if len(vals) < 2:
                    counts["one_valued_answer"] += 1
                    continue
                v0 = vals[0]
                best = max(v for a, v in vals.items() if a != 0)
                margin = best - v0
                target = np.zeros(n, dtype=np.float32)
                positive = margin >= bar
                if positive:
                    keys = list(vals)
                    v = np.array([vals[k] for k in keys], dtype=np.float64)
                    z = (v - v.max()) / max(temp, 1e-6)
                    p = np.exp(z)
                    p /= p.sum()
                    for k, pk in zip(keys, p):
                        target[k] = pk
                    counts["positive"] += 1
                else:
                    target[0] = 1.0
                    counts["tie"] += 1
                yield {
                    "seed": int(r["seed"]),
                    "frame": s["frame"],
                    "n": n,
                    "target": target,
                    "margin": float(margin),
                    "positive": bool(positive),
                    "spread": float(max(vals.values()) - min(vals.values())),
                    "leaf": s.get("leaf"),
                    "n_valued": len(vals),
                }


class PaySubRows(IterableDataset):
    """One item = one payment sub row = one pay_class example carrying its
    target over the candidate slots (`_target`), the tie/positive flag and
    the margin."""

    def __init__(
        self,
        run: str | Path,
        embedding_stem: str | Path,
        abilities_stem: str | Path | None,
        bar: float = 0.03,
        temp: float = 0.025,
        min_rolls: int = 1,
        seed: int = 0,
        shuffle: bool = True,
        max_rows: int | None = None,
        seed_filter=None,
    ):
        from anvil.bridge.featurize import Featurizer

        self.run = Path(run)
        self.feat = Featurizer(Path(embedding_stem), default_methods(), abilities=abilities_stem)
        self.bar = bar
        self.temp = temp
        self.min_rolls = min_rolls
        self.seed = seed
        self.shuffle = shuffle
        self.max_rows = max_rows
        self.seed_filter = seed_filter  # game seed -> bool (cross-fit folds)
        self.counts: Counter = Counter()

    def _example(self, grp: dict, header: dict) -> dict[str, Any] | None:
        frame = grp["frame"]
        if frame.get("obs") is None:
            return None
        try:
            ex, _aux = self.feat.example(frame, header, "pay_class")
        except Exception:
            self.counts["featurize_error"] += 1
            return None
        c = int(ex["cand_rows"].shape[0])
        if c != grp["n"]:
            self.counts["cand_mismatch"] += 1
            return None
        ex["_target"] = grp["target"]
        ex["_positive"] = grp["positive"]
        ex["_margin"] = grp["margin"]
        return ex

    def __iter__(self) -> Iterator[dict]:
        headers = HeaderIndex(self.run)
        groups = [
            g for g in pay_groups(self.run, self.bar, self.temp, self.min_rolls, self.counts)
            if self.seed_filter is None or self.seed_filter(g["seed"])
        ]
        wi = get_worker_info()
        if wi is not None:
            groups = groups[wi.id :: wi.num_workers]
        if self.shuffle:
            random.Random(self.seed + (wi.id if wi else 0)).shuffle(groups)
        if self.max_rows is not None:
            groups = groups[: self.max_rows]
        for grp in groups:
            header = headers.get(grp["seed"])
            if header is None:
                self.counts["no_header"] += 1
                continue
            ex = self._example(grp, header)
            if ex is None:
                self.counts["unbuildable"] += 1
                continue
            self.counts["examples"] += 1
            yield ex


def collate_pay(items: list[dict]) -> dict[str, torch.Tensor]:
    targets = [ex.pop("_target") for ex in items]
    positive = torch.tensor([bool(ex.pop("_positive")) for ex in items])
    margin = torch.tensor([float(ex.pop("_margin")) for ex in items], dtype=torch.float32)
    out = collate(items)
    b, cw = out["cand_mask"].shape
    tgt = torch.zeros(b, cw, dtype=torch.float32)
    for i, t in enumerate(targets):
        tgt[i, : len(t)] = torch.from_numpy(np.asarray(t, dtype=np.float32))
    out["pay_target"] = tgt
    out["pay_positive"] = positive
    out["pay_margin"] = margin
    return out


def pay_distill_loss(out: dict, batch: dict, pos_weight: float = 1.0) -> tuple[torch.Tensor, dict]:
    """Cross-entropy from the asymmetric target to the pay head's softmax
    over its candidate slots. Stats keep ties and positives apart.
    pos_weight > 1 up-weights the positive rows in the loss (the pool is 94%
    ties; the stats stay unweighted)."""
    lg = out["policy_logits"].float()
    lp = torch.log_softmax(lg, dim=-1)
    tgt = batch["pay_target"]
    ce = -(tgt * lp).sum(1)  # (B,)
    pos = batch["pay_positive"]
    w = torch.where(pos, torch.full_like(ce, float(pos_weight)), torch.ones_like(ce))
    loss = (w * ce).sum() / w.sum()
    pred = lp.argmax(-1)
    want = tgt.argmax(-1)
    ce = ce.detach()
    stats = {"pay_ce": float(loss.detach()), "n": int(ce.shape[0]), "n_pos": int(pos.sum())}
    if pos.any():
        stats["pos_ce"] = float(ce[pos].mean())
        stats["pos_top1"] = float((pred[pos] == want[pos]).float().mean())
        stats["pos_dev"] = float((pred[pos] != 0).float().mean())
    if (~pos).any():
        stats["tie_ce"] = float(ce[~pos].mean())
        stats["tie_dev"] = float((pred[~pos] != 0).float().mean())
    return loss, stats
