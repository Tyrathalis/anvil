"""Forced-seq label join for the C bundle (ADR-0054).

Turns a forced-seq campaign's labels rows + the drill phase's fork stores
into the training-side seq batch:

- **Labels** (`-forceseq` labels.jsonl, one row per fork point): the
  drilled seat's paired arm winrates give the advantage
  Â = clip(wr_act − wr_hold, ±0.25) (clips at birth — the standing
  engineered-aggregate rule), cast* = `act_first_modal` when
  `act_first_agree` ≥ the threshold (else the cast-mass fallback), and
  wr_nat = the natural arm's winrate = the C2a aux target wr_K(fp)
  (the 3-arm harness gives it on the same rows — no separate drill-label
  read needed).
- **Windows**: the drill fork stores' completions are keyed by
  (header.fork.pg, header.fork.fp) = the labels row's (i, fp). One
  completion per fork point supplies the mainline fork window — its first
  mu-covered priority decision for the drilled seat, featurized on the
  serve-identical path (`game_trajectories`).
- **Batch**: collated segments with three extra tensors per segment —
  `seq_adv` (float), `seq_tmask` (bool, aligned to the segment's candidate
  padding; True at every candidate whose SA string matches cast*, or at
  all non-PASS candidates in mass-fallback mode), `seq_wr` + `seq_has_wr`
  (the C2a aux target). L_seq itself lives in rl.py; the critic-phase aux
  in finetune_value.py consumes the same batch's full-vis twin.

Labels are policy-conditional (the act arm is the generating policy's
preferred cast) — a seq batch is valid for the iteration whose campaign
produced it, and the driver regenerates fresh each iteration (ADR-0054
pin: freshness beats K-precision).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import torch

_SEAT = re.compile(r"\((\d+)\)")


def load_rows(paths: list[str], agree_min: float = 0.5, clip: float = 0.25) -> list[dict]:
    """Parse forced-seq labels files (or run dirs) into join-ready rows."""
    files: list[Path] = []
    for p in map(Path, paths):
        files += sorted(p.glob("workers/inv-*/labels.jsonl")) if p.is_dir() else [p]
    rows = []
    for f in files:
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not r.get("seq") or r.get("seat_skip") or not r.get("triples"):
                continue
            m = _SEAT.search(r.get("seat") or "")
            if not m:
                continue
            seat = int(m.group(1)) - 1
            n = r["triples"]
            adv = (r["w_act"][seat] - r["w_hold"][seat]) / n
            rows.append(
                {
                    "key": (r["i"], r.get("fp", 0)),
                    "seat": seat,
                    "adv": max(-clip, min(clip, adv)),
                    "cast_star": (
                        r.get("act_first_modal")
                        if (r.get("act_first_agree") or 0.0) >= agree_min
                        else None
                    ),
                    "wr_nat": r["w_nat"][seat] / n,
                    "triples": n,
                }
            )
    return rows


def _first_fork_window(store, g: int, feat, seat: int, full_vis: bool = False):
    """The fork completion's first mu-covered priority window for `seat`,
    featurized serve-identically. Returns the example dict or None."""
    from anvil.training.rl import game_trajectories

    trajs, skip = game_trajectories(store, feat, g, full_vis=full_vis)
    if skip is not None:
        return None
    for p, exs, _reward, _rej, exs_fv in trajs:
        if p != seat:
            continue
        for j, (ex, rec) in enumerate(exs):
            if rec.get("task") == "priority":
                return (ex, exs_fv[j] if full_vis else None)
    return None


def build_seq_batch(
    label_paths: list[str],
    store_paths: list[str],
    stem: str,
    methods: list[str],
    seg: int = 256,
    agree_min: float = 0.5,
    clip: float = 0.25,
    full_vis: bool = False,
) -> dict | None:
    """Join labels to fork windows and collate the seq batch. Returns
    {"segs": [...], optional "segs_fv": [...], counters} or None when
    nothing joins (callers treat None as seq-off and say so loudly)."""
    from anvil.bridge.featurize import Featurizer
    from anvil.store.trajectories import open_store
    from anvil.training.dataset import SaVocab, collate, default_sa_vocab, norm_sa

    rows = load_rows(label_paths, agree_min=agree_min, clip=clip)
    if not rows:
        return None
    by_key = {r["key"]: r for r in rows}

    feat = Featurizer(stem, methods)
    sa_vocab = SaVocab(default_sa_vocab())
    picked: dict[tuple, tuple] = {}  # key -> (ex, ex_fv, row)
    for sp in store_paths:
        store = open_store(sp)
        for g in store.game_indices():
            try:
                header = store.game(g).header
            except Exception:
                continue
            fk = header.get("fork") or {}
            key = (fk.get("pg", -1), fk.get("fp", -1))
            row = by_key.get(key)
            if row is None or key in picked:
                continue
            got = _first_fork_window(store, g, feat, row["seat"], full_vis=full_vis)
            if got is not None:
                picked[key] = (*got, row)

    n_mass = n_cast = 0
    plain, plain_fv, meta = [], [], []
    for ex, ex_fv, row in picked.values():
        n_cand = len(ex["cand_rows"])
        if n_cand < 2:
            continue  # PASS-only window: no contrast to train
        tgt = [False] * n_cand
        sid = sa_vocab.id(norm_sa(row["cast_star"])) if row["cast_star"] else -1
        if sid >= 0:
            for j in range(1, n_cand):
                if ex["cand_sa"][j] == sid:
                    tgt[j] = True
        if not any(tgt):
            # cast-mass fallback (agreement below threshold, unresolvable
            # modal SA, or no matching candidate at this window)
            for j in range(1, n_cand):
                tgt[j] = True
            n_mass += 1
        else:
            n_cast += 1
        plain.append(ex)
        plain_fv.append(ex_fv)
        meta.append((row["adv"], tgt, row["wr_nat"]))

    if not plain:
        return None

    def _collate_with_meta(examples, metas):
        segs = []
        for i in range(0, len(examples), seg):
            batch = collate(examples[i : i + seg])
            ms = metas[i : i + seg]
            c_max = batch["cand_mask"].shape[1]
            tm = torch.zeros(len(ms), c_max, dtype=torch.bool)
            for b, (_, tgt, _) in enumerate(ms):
                tm[b, : len(tgt)] = torch.tensor(tgt)
            batch["seq_adv"] = torch.tensor([m[0] for m in ms], dtype=torch.float32)
            batch["seq_tmask"] = tm
            batch["seq_wr"] = torch.tensor([m[2] for m in ms], dtype=torch.float32)
            segs.append(batch)
        return segs

    out = {
        "segs": _collate_with_meta(plain, meta),
        "n": len(plain),
        "n_cast_target": n_cast,
        "n_mass": n_mass,
        "n_labels": len(rows),
        "n_joined": len(picked),
        "mean_abs_adv": sum(abs(m[0]) for m in meta) / len(meta),
    }
    if full_vis:
        out["segs_fv"] = _collate_with_meta([e for e in plain_fv], meta)
    return out
