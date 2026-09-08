"""M12 Build 3 evening 2 (ADR-0105 item 4): the sub-row distillation term.

The search's expansion round (-searchsurf B) enumerates the answers of the
first traced surface on the top-B candidates' paths and values each with a
leaf copy; the sub row carries, from the evening-2 fork, the surface
window's own dec record (`frame`: options + obs + hist, the wire shape) —
the state the answers were chosen in on the COPY, not the mainline (only
8-19% of sub rows share their option with the mainline). This module turns
a run directory's sub rows into option-set examples and trains the decoder
toward the leaf-value softmax over the enumerated answers:

    p(a) ∝ exp(V(a) / T)        (T = --distill-temp; the acting rule's 0.025)
    loss = -Σ_a p(a) · log q(a),  q(a) = softmax over the SAME answers of the
                                   decoder's teacher-forced sequence log-prob

so the term only compares answers the search actually valued (no reward for
mass outside the enumerated set). One group = one sub row; a batch holds
whole groups (collate_groups) so the within-group normalization is exact.

Reads a harness run directory (workers/inv-*/labels.jsonl + obs.idx.jsonl
/ obs.zst for the parent game's header, keyed by seed) or a flat smoke
directory (search.jsonl + obs.idx.jsonl). Sub rows without a frame (a jar
before the capture, an unfired directive) are skipped and counted.
"""
from __future__ import annotations

import glob
import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import torch
from torch.utils.data import IterableDataset, get_worker_info

from anvil.bridge.featurize import wire_history
from anvil.encoder.transform import HISTORY_K, assemble
from anvil.policy.surfaces import SURF_BUILT, SURF_MAX, SURF_TASK, AbilityCache, surface_fields
from anvil.store.trajectories import decode_frame
from anvil.training.dataset import (
    T_MAX,
    TASKS,
    X_CLASSES,
    EmbeddingCache,
    MethodVocab,
    collate,
    default_methods,
)

CMB_KEYS = ("cmb_rows", "cmb_count", "atk_label", "cmb_count_label", "atk_tgt_kind", "atk_tgt_idx",
            "blk_label", "blk_atk_rows")


def _label_files(run: Path) -> list[Path]:
    files = sorted(Path(p) for p in glob.glob(str(run / "workers/inv-*/labels.jsonl")))
    for flat in ("search.jsonl", "labels.jsonl"):
        if (run / flat).exists():
            files.append(run / flat)
    return files


def _idx_files(run: Path) -> list[Path]:
    files = sorted(Path(p) for p in glob.glob(str(run / "workers/inv-*/obs.idx.jsonl")))
    if (run / "obs.idx.jsonl").exists():
        files.append(run / "obs.idx.jsonl")
    return files


class HeaderIndex:
    """seed -> game header, decoded lazily from the run's obs frames."""

    def __init__(self, run: Path, sv: int = 3):
        self.sv = sv
        self.where: dict[int, tuple[Path, int, int]] = {}
        for idxf in _idx_files(run):
            zst = idxf.with_name("obs.zst")
            for ln in open(idxf):
                try:
                    e = json.loads(ln)
                    self.where.setdefault(int(e["seed"]), (zst, int(e["off"]), int(e["clen"])))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        self.cache: dict[int, dict | None] = {}
        self._data: dict[Path, bytes] = {}

    def get(self, seed: int) -> dict | None:
        if seed in self.cache:
            return self.cache[seed]
        hdr = None
        loc = self.where.get(seed)
        if loc is not None:
            zst, off, clen = loc
            if zst not in self._data:
                self._data[zst] = open(zst, "rb").read()
            try:
                hdr = decode_frame(self._data[zst][off:off + clen], self.sv)[0]
            except Exception:
                hdr = None
        self.cache[seed] = hdr
        return hdr


def sub_row_groups(run: Path, kinds: set[str], temp: float, counts: Counter) -> Iterator[dict]:
    """Yield {seed, frame, task, kind, answers: [(indices, p)]} per usable sub row."""
    for f in _label_files(run):
        for ln in open(f):
            if not ln.startswith('{"ev":"search"'):
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            for s in r.get("sub") or []:
                kind = s.get("kind")
                task = SURF_TASK.get(kind)
                counts[f"sub:{kind}"] += 1
                if kind not in kinds or task not in SURF_BUILT:
                    continue
                if not s.get("frame"):
                    counts["no_frame"] += 1
                    continue
                vals: dict[tuple, float] = {}
                lo, hi = int(s.get("min", 0)), int(s.get("max", 0))
                for ans in s.get("ans") or []:
                    vs = [v for v in ans.get("v") or [] if v is not None]
                    if not vs:
                        continue
                    a = list(ans["a"])
                    if task in ("surf_set", "surf_mode"):
                        a = sorted(a)
                    key = tuple(a)
                    # only answers the decoder can emit: inside [min, max]
                    # (the heuristic's empty Confluence answer is valued but
                    # sits below min — STOP is closed there), no repeats
                    # unless the window allows them, within the slot count
                    if len(key) > SURF_MAX or (task == "surf_one" and len(key) != 1):
                        continue
                    if task != "surf_one" and not (lo <= len(key) <= hi):
                        counts["answer_out_of_range"] += 1
                        continue
                    if len(set(key)) < len(key) and not s.get("rep"):
                        continue
                    vals.setdefault(key, sum(vs) / len(vs))
                if len(vals) < 2:
                    counts["one_valued_answer"] += 1
                    continue
                keys = list(vals)
                v = np.array([vals[k] for k in keys], dtype=np.float64)
                z = (v - v.max()) / max(temp, 1e-6)
                p = np.exp(z)
                p /= p.sum()
                yield {
                    "seed": int(r["seed"]),
                    "frame": s["frame"],
                    "task": task,
                    "kind": kind,
                    "rep": bool(s.get("rep")),
                    "n": int(s.get("n", 0)),
                    "answers": [(list(k), float(pk)) for k, pk in zip(keys, p)],
                    "spread": float(v.max() - v.min()),
                }


class SubRowFrames(IterableDataset):
    """One item = one sub row = a list of examples (the same frame, one
    answer's labels each, `_w` = the target probability)."""

    def __init__(
        self,
        run: str | Path,
        embedding_stem: str | Path,
        abilities_stem: str | Path | None,
        kinds: set[str] | None = None,
        temp: float = 0.025,
        seed: int = 0,
        shuffle: bool = True,
        history_k: int = HISTORY_K,
        max_rows: int | None = None,
    ):
        self.run = Path(run)
        self.embed = EmbeddingCache(Path(embedding_stem))
        self.abil = AbilityCache(abilities_stem) if abilities_stem else None
        self.methods = MethodVocab(default_methods())
        self.kinds = kinds or {"entity_one", "entity_set", "mode"}
        self.temp = temp
        self.seed = seed
        self.shuffle = shuffle
        self.history_k = history_k
        self.max_rows = max_rows
        self.counts: Counter = Counter()

    def _example(self, grp: dict, header: dict, ans: list[int], w: float) -> dict[str, Any] | None:
        frame = grp["frame"]
        if frame.get("obs") is None:
            return None
        p = int(frame["p"])
        hist = wire_history(frame.get("hist"), p, self.history_k)
        out = assemble(frame, header, perspective=p, history=hist)
        row_of = out["entity_row_of"]
        task = grp["task"]
        surf = surface_fields(frame, row_of, self.abil, self.methods.id(frame["m"]), False)
        if surf is None or surf["task"] != task or surf["_n"] != grp["n"]:
            return None
        n = surf["_n"]
        labels = np.full(SURF_MAX + 1, -1, dtype=np.int64)
        for t, j in enumerate(ans):
            if not 0 <= j < n:
                return None
            labels[t] = j
        labels[len(ans)] = n  # STOP (collate remaps to the batch width)
        h = np.full((self.history_k, 3), -1, dtype=np.int64)
        for i, e in enumerate(out["history"][-self.history_k:]):
            h[i] = (self.methods.id(e["m"]), e["self"], row_of.get(e["e"], -1))
        return {
            "entities": torch.from_numpy(out["entities"]),
            "ent_emb": torch.tensor([self.embed.row(nm) for nm in out["entity_names"]], dtype=torch.int64),
            "globals": torch.from_numpy(out["globals"]),
            "players": torch.from_numpy(out["players"]),
            "history": torch.from_numpy(h),
            "cand_rows": torch.tensor([-1], dtype=torch.int64),
            "cand_sa": torch.tensor([-1], dtype=torch.int64),
            "cand_kind": torch.tensor([-1], dtype=torch.int64),
            "label": torch.tensor(0, dtype=torch.int64),
            "label_row": torch.tensor(-1, dtype=torch.int64),
            "tgt_kind": torch.full((T_MAX + 1,), -1, dtype=torch.int64),
            "tgt_idx": torch.full((T_MAX + 1,), -1, dtype=torch.int64),
            "x_val": torch.tensor(-1, dtype=torch.int64),
            "task": torch.tensor(TASKS[task], dtype=torch.int64),
            "bool_label": torch.tensor(-1, dtype=torch.int64),
            "num_label": torch.tensor(-1, dtype=torch.int64),
            "num_lo": torch.tensor(0, dtype=torch.int64),
            "num_hi": torch.tensor(X_CLASSES - 1, dtype=torch.int64),
            "ctx_row": torch.tensor(-1, dtype=torch.int64),
            "forced": torch.tensor(0, dtype=torch.int64),
            "has_outcome": torch.tensor(0, dtype=torch.int64),
            "won": torch.tensor(0, dtype=torch.int64),
            **{k: torch.tensor([], dtype=torch.int64) for k in CMB_KEYS},
            "opt_row": torch.tensor(surf["opt_row"], dtype=torch.int64),
            "opt_pi": torch.tensor(surf["opt_pi"], dtype=torch.int64),
            "opt_ak": torch.tensor(surf["opt_ak"], dtype=torch.int64),
            "opt_kind": torch.tensor(surf["opt_kind"], dtype=torch.int64),
            "surf_labels": torch.from_numpy(labels),
            "opt_min": torch.tensor(surf["opt_min"], dtype=torch.int64),
            "opt_max": torch.tensor(surf["opt_max"], dtype=torch.int64),
            "opt_repeat": torch.tensor(surf["opt_repeat"], dtype=torch.int64),
            "surf_ctx_ak": torch.tensor(surf["surf_ctx_ak"], dtype=torch.int64),
            "surf_method": torch.tensor(surf["surf_method"], dtype=torch.int64),
            "_w": w,
        }

    def __iter__(self) -> Iterator[list[dict]]:
        headers = HeaderIndex(self.run)
        groups = list(sub_row_groups(self.run, self.kinds, self.temp, self.counts))
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
            exs = []
            for ans, w in grp["answers"]:
                ex = self._example(grp, header, ans, w)
                if ex is None:
                    exs = []
                    break
                exs.append(ex)
            if len(exs) < 2:
                self.counts["unbuildable"] += 1
                continue
            self.counts[f"group:{grp['kind']}"] += 1
            yield exs


def collate_groups(items: list[list[dict]]) -> dict[str, torch.Tensor]:
    flat = [ex for grp in items for ex in grp]
    w = torch.tensor([ex.pop("_w") for ex in flat], dtype=torch.float32)
    out = collate(flat)
    out["distill_group"] = torch.tensor([gi for gi, grp in enumerate(items) for _ in grp], dtype=torch.int64)
    out["distill_w"] = w
    return out


def distill_loss(out: dict, batch: dict) -> tuple[torch.Tensor, dict]:
    """Cross-entropy from the leaf-value softmax to the decoder's within-group
    softmax of sequence log-probs. Returns (loss, stats)."""
    lg = out["surf_logits"].float()  # (B, S+1, O+1)
    lab = batch["surf_labels"]
    valid = lab >= 0
    lp = torch.log_softmax(lg, dim=-1)
    seq = (lp.gather(-1, lab.clamp(min=0).unsqueeze(-1)).squeeze(-1) * valid).sum(1)  # (B,)
    grp = batch["distill_group"]
    w = batch["distill_w"]
    b = seq.shape[0]
    g = int(grp.max().item()) + 1
    m = torch.full((g, b), -math.inf, device=seq.device)
    m[grp, torch.arange(b, device=seq.device)] = seq
    lse = torch.logsumexp(m, dim=1)  # (G,)
    logq = seq - lse[grp]
    loss = -(w * logq).sum() / g
    # top-1 agreement: the search's best answer is the decoder's best answer
    best_w = torch.full((g,), -1.0, device=seq.device).scatter_reduce(0, grp, w, "amax")
    best_q = torch.full((g,), -math.inf, device=seq.device).scatter_reduce(0, grp, logq, "amax")
    agree = ((w == best_w[grp]) & (logq == best_q[grp])).float()
    top1 = torch.zeros(g, device=seq.device).scatter_reduce(0, grp, agree, "amax").mean()
    return loss, {"distill_top1": float(top1), "groups": g}
