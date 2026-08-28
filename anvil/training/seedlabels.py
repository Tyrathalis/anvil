"""M10 R5: best-arm seed supervision for the schedule decode head
(the ceiling spec's co-design dividend 9; minted by
scripts/seed_sched_labels.py from the ADR-0078 certified positives).

A fixed batch of emission windows whose decode target is the certified
best ARM (the empirical-oracle schedule, select/score split so the labels
are winner's-curse-priced), applied per optimizer step beside the dense
trajectory-derived decode CE — enrichment on the windows where scheduling
measurably binds, never a replacement for the dense signal. Labels are
ERA-ASSETS (certified under iter-019; the sweep is the re-runnable mint).
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn.functional as F


def build_seed_batch(labels_path: str, store_path: str, feat, seg: int = 64) -> "dict | None":
    """Minted seed labels + the ceiling census store -> collated segments
    with sched_tgt decode targets. Rejoin is exact (the banked emission dec
    id); label actions map to candidate indices through the featurizer's
    own collapse (first-fit, the executor's label-match convention).
    Returns None when nothing joins."""
    from anvil.bridge.featurize import store_wire_hist
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import SCHED_CAP, collate

    rows = [json.loads(x) for x in open(labels_path)]
    meta = rows[0] if rows and rows[0].get("k") == "meta" else {}
    rows = [r for r in rows if r.get("k") != "meta"]
    by_game: dict[int, list[dict]] = {}
    for r in rows:
        by_game.setdefault(r["g"], []).append(r)

    ts = TrajectoryStore(Path(store_path))
    exs, tgts = [], []
    miss = unmatched = 0
    for traj in ts.games(skip_undecodable=True):
        g = traj.header["g"]
        wants = by_game.get(g)
        if not wants:
            continue
        dec_by_s = {}
        prior = []
        for dec in traj.decisions:
            dec_by_s[dec.get("s")] = (dec, len(prior))
            prior.append(dec)
        for r in wants:
            hit = dec_by_s.get(r["s"])
            if hit is None:
                miss += 1
                continue
            dec, pos = hit
            wire = dict(dec)
            if "hist" not in dec:
                wire["hist"] = store_wire_hist(prior[:pos], pos)
            ex, aux = feat.example(wire, traj.header, "priority")
            opts = dec.get("opts") or []
            key_of: dict[tuple, int] = {}
            for j, fo in enumerate(aux["cand_first_opt"]):
                if j == 0 or fo < 0 or fo >= len(opts):
                    continue
                key = (opts[fo].get("e"), str(opts[fo].get("sa") or "")[:60])
                key_of.setdefault(key, j)
            tgt = torch.full((SCHED_CAP + 1,), -1, dtype=torch.int64)
            ok = True
            for k, (e, sa60) in enumerate(r["seq"][:SCHED_CAP]):
                j = key_of.get((e, sa60))
                if j is None:
                    unmatched += 1
                    ok = False
                    break
                tgt[k] = j
            if not ok:
                continue
            if len(r["seq"]) < SCHED_CAP:
                tgt[len(r["seq"])] = 0  # STOP
            exs.append(ex)
            tgts.append(tgt)
    if not exs:
        return None
    segs = []
    for i in range(0, len(exs), seg):
        chunk = collate(exs[i : i + seg])
        t = torch.stack(tgts[i : i + seg])
        chunk["sched_tgt"] = t[:, :SCHED_CAP]
        chunk["sched_tgt_full"] = t
        segs.append(chunk)
    return {"segs": segs, "n": len(exs), "miss": miss, "unmatched": unmatched,
            "labels": str(labels_path), "era": meta.get("era")}


def seed_pass(net, seed_segs: list, forward_segments, w: float, grad: bool = True) -> float:
    """One pass: teacher-forced decode CE toward the certified best arm.
    Every row is an emission window; means over the whole batch."""
    n_lab = sum(int((s["sched_tgt_full"] >= 0).sum()) for s in seed_segs) or 1
    tot = 0.0
    for seg, fwd in forward_segments(net, seed_segs, grad=grad):
        ce = F.cross_entropy(
            fwd["sched_logits"].flatten(0, 1).float(),
            seg["sched_tgt_full"].flatten(0, 1),
            ignore_index=-1,
            reduction="sum",
        ) / n_lab
        if grad:
            (w * ce).backward()
        tot += float(ce.detach())
    return tot
