"""M10 R5: best-arm seed supervision for the schedule decode head
(the ceiling spec's co-design dividend 9; minted by
scripts/seed_sched_labels.py from the ADR-0078 certified positives).

A fixed batch of emission windows whose decode target is the certified
best ARM (the empirical-oracle schedule, select/score split so the labels
are winner's-curse-priced), applied per optimizer step. Since ADR-0086
this is the PRIMARY (only) decode/emission supervision: the dense
trajectory-derived decode CE it originally enriched was retired after
m10-probe1 — the decode head IS the emitter, so training it on the
policy's own realized casts is self-referential with a degenerate fixed
point at empty (one RL iteration reached it). Labels are ERA-ASSETS
(certified under iter-019; the sweep is the re-runnable mint — re-mint
per era if the state distribution walks away from the label population).
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


def build_follow_batch(labels_path: str, store_path: str, feat, seg: int = 64) -> "dict | None":
    """ADR-0092 Fork 1 — feed-and-follow: certified non-hold label rows ->
    collated segments with the certified arm FED as the schedule (the
    discrete-carry conditioning tensors synthesized from the label through
    sched_cond_tensors, statuses all 'n', afford/pay by the census
    conventions at the emission window) and follow_tgt = the candidate
    index of the arm's first cast. Supervising the priority pointer on
    these rows trains "when the slot says X, cast X" — consumption, not
    BC (natural-line rows are excluded on purpose). Rejoin/mapping are
    build_seed_batch's verbatim."""
    from anvil.bridge.featurize import store_wire_hist
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import SCHED_CAP, collate, norm_sa
    from anvil.training.sched_targets import (
        pay_summary_class,
        sched_cond_tensors,
        slot_afford,
        source_views_of,
    )

    rows = [json.loads(x) for x in open(labels_path)]
    meta = rows[0] if rows and rows[0].get("k") == "meta" else {}
    rows = [r for r in rows if r.get("k") != "meta"
            and r.get("src", "certified") == "certified"
            and r.get("arm", 0) >= 0 and r.get("seq")]
    by_game: dict[int, list[dict]] = {}
    for r in rows:
        by_game.setdefault(r["g"], []).append(r)

    ts = TrajectoryStore(Path(store_path))
    exs, tgts = [], []
    miss = unmatched = retimed = 0
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
            if hit is None or not hit[0].get("obs"):
                miss += 1
                continue
            dec, pos = hit
            # The arm's executor is LAND-FIRST: at the emission window (the
            # first MAIN1 ask) the arm-consistent action is the land drop
            # when one is available, and the first spell comes a window
            # later — supervising seq[0] at the emission window taught the
            # wrong thing on 58% of windows (day-zero diagnostic: CE 16.6
            # with argmax = land on 130/134 such windows). Follow window =
            # the first own priority ask of the turn, from emission onward,
            # at which the target is a candidate AND no land play remains —
            # the natural line's post-land window, on-distribution by
            # construction.
            e0, sa0 = r["seq"][0][0], r["seq"][0][1]
            seat, turn = dec.get("p", 0), dec.get("t", 0)
            chosen = None
            for k in range(pos, len(prior)):
                d = prior[k]
                if d.get("t") != turn:
                    break
                if (d.get("m") != "chooseSpellAbilityToPlay" or d.get("p") != seat
                        or not d.get("obs")):
                    continue
                opts_k = d.get("opts") or []
                has_target = any(o.get("e") == e0 and str(o.get("sa") or "")[:60] == sa0
                                 for o in opts_k)
                has_land = any(o.get("kind") == "land" for o in opts_k)
                if has_target and not has_land:
                    chosen = (d, k)
                    break
            if chosen is None:
                unmatched += 1
                continue
            if chosen[1] != pos:
                retimed += 1
            dec, pos = chosen
            wire = dict(dec)
            if "hist" not in dec:
                wire["hist"] = store_wire_hist(prior[:pos], pos)
            ex, aux = feat.example(wire, traj.header, "priority")
            opts = dec.get("opts") or []
            key_of: dict[tuple, tuple] = {}
            for j, fo in enumerate(aux["cand_first_opt"]):
                if j == 0 or fo < 0 or fo >= len(opts):
                    continue
                key = (opts[fo].get("e"), str(opts[fo].get("sa") or "")[:60])
                key_of.setdefault(key, (j, opts[fo]))
            slots = []
            for e, sa60 in r["seq"][:SCHED_CAP]:
                h = key_of.get((e, sa60))
                if h is None:
                    break  # later slots may be post-window; the fed schedule
                    # is the matched prefix (the first slot is guaranteed)
                slots.append((e, h[1], h[0]))
            if not slots:
                unmatched += 1
                continue
            obs, seat = dec["obs"], dec.get("p", 0)
            views = source_views_of(obs, seat)
            sched = {
                "slots": [(e, feat.sa_vocab.id(norm_sa(opt.get("sa", "")))) for e, opt, _ in slots],
                "st": "n" * len(slots),
                "afford": [slot_afford(opt, obs, seat, views) for _, opt, _ in slots],
                "pay": [pay_summary_class(opt, obs) for _, opt, _ in slots],
            }
            ex.update(sched_cond_tensors(sched, aux["row_of"]))
            exs.append(ex)
            tgts.append(slots[0][2])
    if not exs:
        return None
    segs = []
    for i in range(0, len(exs), seg):
        chunk = collate(exs[i : i + seg])
        chunk["follow_tgt"] = torch.tensor(tgts[i : i + seg], dtype=torch.int64)
        segs.append(chunk)
    return {"segs": segs, "n": len(exs), "miss": miss, "unmatched": unmatched,
            "retimed": retimed, "labels": str(labels_path), "era": meta.get("era")}


def follow_pass(net, segs: list, forward_segments, w: float, grad: bool = True) -> float:
    """One pass: CE on the priority pointer toward the fed certified arm's
    first cast. Every row is a certified emission window with its arm fed;
    means over the rows of the passed segs (the seed_pass contract)."""
    n = sum(int(s["follow_tgt"].numel()) for s in segs) or 1
    tot = 0.0
    for seg, fwd in forward_segments(net, segs, grad=grad):
        ce = F.cross_entropy(
            fwd["policy_logits"].float(), seg["follow_tgt"], reduction="sum"
        ) / n
        if grad:
            (w * ce).backward()
        tot += float(ce.detach())
    return tot
