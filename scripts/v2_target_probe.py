#!/usr/bin/env python3
"""M10 v2 aux-target probe (m10-v2-target-probe-spec.md, ADJUDICATED
2026-08-26; gates pinned pre-data — ADR-0074 numerics verbatim).

Question: from the frozen iter-019 trunk at the fork-consistent MAIN1
emission window, are the three adjudicated v2 aux targets predictable
above the obs-arithmetic baseline?

  dump-er  E (end-of-turn resource summary) + R (running affordability
           along realized sequences) over the m9-rebaselinearm stores.
           Per own-turn group: [STATE]/[PLAN] at the emission window +
           obs-arith; E labels at the last own obs-bearing dec of the
           turn; R labels at each post-cast chooseSpellAbilityToPlay
           window (census cost/affordability conventions throughout).
  dump-f   F (schedule feasibility / degrade-point) over the ceiling
           sweep universe: arms parsed from sched-h2.tsv (the arm
           record), candidate features recomputed by the eligible_turns
           convention, outcomes joined from lanes-h2/*.out.jsonl
           aggregated across rolls (never per-roll rows).
  probe    the pinned ladders + gates; report JSON.

Conventions shared with schedule_census/schedule_sweep/veto_knowability:
mana-ability options excluded; costs by resolve_cost (uncertain counted,
never guessed); affordability under the `now` view; commander tax
optimistic; X=0/phyrexian-free optimism. Obs sv=2 carries no mana-pool
field: the E floating axis is recorded as unavailable, not fabricated.

Usage:
  uv run python scripts/v2_target_probe.py dump-er \
      --stores data/trajectories/m9-rebaselinearm-s0-* ...-s1-* \
      --ckpt <iter-019> --out data/runs/v2-target-probe
  uv run python scripts/v2_target_probe.py dump-f \
      --plan data/runs/sched-sweep-m10 \
      --store data/trajectories/m10-ceiling-census-20260825-212414 \
      --ckpt <iter-019> --out data/runs/v2-target-probe
  uv run python scripts/v2_target_probe.py probe --dump data/runs/v2-target-probe
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_probe import _arith, _auc, _fit_predict, _split  # noqa: E402
from schedule_census import cmc, resolve_cost  # noqa: E402
from veto_knowability import build_card_table, can_pay, source_views  # noqa: E402

COLORS = "WUBRG"
# Gates — ADR-0074 numerics verbatim (adjudication pin 4).
GATE_AUC = {"margin": 0.03, "floor": 0.60}
GATE_RHO = {"margin": 0.05, "floor": 0.15}
MIN_SUPPORT = 50
ARMVEC_KEYS = ["n_steps", "total_cmc", "max_cmc", "mean_cmc", "n_producers",
               "n_instants", "hold_n", "frac_scheduled",
               "pips_W", "pips_U", "pips_B", "pips_R", "pips_G",
               "n_hybrid", "generic_total"]


def _cmd_extra(obs: dict, seat: int) -> int:
    try:
        return 2 * min(obs["players"][seat]["cmdcast"])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0


def _afford_count(obs: dict, seat: int, table) -> tuple[int, int]:
    """Census-convention (afford_now, untapped_now) at a window obs."""
    ents = {e["e"]: e for e in obs.get("ents", [])}
    views = source_views(obs, seat, table)
    extra_cmd = _cmd_extra(obs, seat)
    seen: set[tuple] = set()
    afford = 0
    for opt in obs.get("_opts") or []:
        key = (opt.get("e"), str(opt.get("sa") or "")[:60])
        if key in seen:
            continue
        seen.add(key)
        bucket, cost, extra, _ = resolve_cost(opt, ents, table)
        if bucket == "spell" and ents.get(opt.get("e"), {}).get("z") == "command":
            extra = extra_cmd
        if bucket not in ("spell", "ability") or cost is None:
            continue
        afford += int(can_pay(cost, views.now, extra))
    return afford, len(views.now)


def _e_axes(obs: dict, seat: int, table) -> dict:
    views = source_views(obs, seat, table)
    ax = {"untapped_total": float(len(views.now)),
          "chained": float(views.chained)}
    for c in COLORS:
        ax[f"untapped_{c}"] = float(sum(1 for s in views.now if c in s))
    return ax


def _main1_window(decs: list[dict], seat: int):
    return next((d for d in decs if d.get("obs")
                 and d["obs"].get("glob", {}).get("ph") == "MAIN1"
                 and d["obs"].get("glob", {}).get("ap") == seat), None)


def _capture_features(ev, exs: list, out: Path, tag: str) -> None:
    import torch

    from anvil.training.dataset import collate

    feats_s, feats_p = [], []

    @torch.no_grad()
    def capture(batch_exs):
        chunk = collate(batch_exs)
        chunk = {k: v.to(ev.device) for k, v in chunk.items()}
        with torch.autocast(ev.device, dtype=torch.bfloat16):
            card_vecs = ev.net.cards(chunk["ent_emb"])
            tokens, pad = ev.net.assemble(card_vecs, chunk)
            o = ev.net.trunk(tokens, src_key_padding_mask=pad)
        feats_s.append(o[:, 0].float().cpu().numpy())
        feats_p.append(o[:, 1].float().cpu().numpy())

    for i in range(0, len(exs), ev.batch):
        capture(exs[i:i + ev.batch])
    np.savez_compressed(out / f"{tag}-features.npz",
                        state=np.concatenate(feats_s),
                        plan=np.concatenate(feats_p))


def dump_er(args) -> None:
    from anvil.ante.ledger import ValueEvaluator
    from anvil.store.trajectories import TrajectoryStore

    table = build_card_table()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ev = ValueEvaluator(args.ckpt)
    frame = Counter()
    groups_out, slots_out, exs = [], [], []

    for store in args.stores:
        ts = TrajectoryStore(Path(store))
        sname = Path(store).name
        for traj in ts.games(skip_undecodable=True):
            g = traj.header["g"]
            players = traj.header.get("players") or []
            seat = next((i for i, p in enumerate(players)
                         if str(p.get("name", "")).startswith("Anvil")), 0)
            by_turn: dict[int, list[tuple[int, dict]]] = {}
            for i, dec in enumerate(traj.decisions):
                if dec.get("p") == seat and dec.get("t", 0) >= 1:
                    by_turn.setdefault(dec["t"], []).append((i, dec))
            for t, idecs in sorted(by_turn.items()):
                frame["turn_groups"] += 1
                decs = [d for _, d in idecs]
                emis = _main1_window(decs, seat)
                if emis is None:
                    frame["no_main1_window"] += 1
                    continue
                emis_idx = next(i for i, d in idecs if d is emis)
                frame["own_turn_groups"] += 1

                # ---- E label: last own obs-bearing dec of the turn ----
                last = next((d for _, d in reversed(idecs) if d.get("obs")), None)
                eax = _e_axes(last["obs"], seat, table)
                eot_phase = last["obs"].get("glob", {}).get("ph", "?")

                gidx = len(groups_out)
                groups_out.append({"store": sname, "g": g, "seat": seat, "t": t,
                                   "arith": _arith(emis["obs"], seat),
                                   "e": eax, "eot_phase": eot_phase,
                                   "eot_is_emis": bool(last is emis)})
                exs.append(ev.example(emis, traj.header, seat,
                                      traj.decisions[:emis_idx]))

                # ---- R slots: post-cast windows ----
                k = 0
                for j, (di, d) in enumerate(idecs):
                    if d.get("m") != "chooseSpellAbilityToPlay" or not d.get("ret"):
                        continue
                    for r in d["ret"]:
                        if r.get("kind") == "land" or not r.get("sa"):
                            continue
                        k += 1
                        nxt = next((dd for _, dd in idecs[j + 1:]
                                    if dd.get("m") == "chooseSpellAbilityToPlay"
                                    and dd.get("obs")), None)
                        if nxt is None:
                            frame["r_slot_no_window"] += 1
                            continue
                        wobs = dict(nxt["obs"])
                        wobs["_opts"] = nxt.get("opts", [])
                        afford, untapped = _afford_count(wobs, seat, table)
                        slots_out.append({"gidx": gidx, "k": k,
                                          "untapped_after": untapped,
                                          "afford_after": afford})
                        frame["r_slots"] += 1

    print(f"{len(groups_out)} groups, {len(slots_out)} R slots; frame={dict(frame)}")
    _capture_features(ev, exs, out, "er")
    with open(out / "er-groups.jsonl", "w") as f:
        for r in groups_out:
            f.write(json.dumps(r) + "\n")
    with open(out / "er-slots.jsonl", "w") as f:
        for r in slots_out:
            f.write(json.dumps(r) + "\n")
    (out / "er-frame.json").write_text(json.dumps(dict(frame), indent=2) + "\n")
    print(f"-> {out}/er-*")


def dump_f(args) -> None:
    from anvil.ante.ledger import ValueEvaluator
    from anvil.store.trajectories import TrajectoryStore

    table = build_card_table()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = Path(args.plan)
    frame = Counter()

    # ---- arms from the schedfile (the arm record) ----
    arms: dict[tuple[int, int], dict[int, tuple[str, ...]]] = {}
    for ln in (plan / "sched-h2.tsv").read_text().splitlines():
        if not ln or ln.startswith("#"):
            continue
        p = ln.split("\t")
        g, t, _h, _seat, aid, mode = int(p[0]), int(p[1]), p[2], p[3], int(p[4]), p[5]
        if mode != "joint":
            continue
        arms.setdefault((g, t), {})[aid] = tuple(p[6:])
    print(f"schedfile: {len(arms)} turns, "
          f"{sum(len(v) for v in arms.values())} joint arms")

    # ---- outcomes from the lanes, aggregated across rolls ----
    agg: dict[tuple[int, int, int], dict] = {}
    for lane in sorted((plan / "lanes-h2").glob("lane-*.out.jsonl")):
        for ln in open(lane):
            r = json.loads(ln)
            if r.get("ev") != "sched" or not r.get("joint") or r.get("arm", 0) < 1:
                continue
            if r.get("crash"):
                frame["crash_rolls"] += 1
                continue
            key = (r["i"], r["t"], r["arm"])
            a = agg.setdefault(key, {"rolls": 0, "realized": 0, "degr": [],
                                     "why": Counter(), "sched_n": r.get("sched_n", 0)})
            a["rolls"] += 1
            if r.get("degraded_at", -1) < 0:
                a["realized"] += 1
            else:
                a["degr"].append(r["degraded_at"])
                a["why"][r.get("degrade_why", "?")] += 1

    # ---- candidate features + trunk features at the fork window ----
    ts = TrajectoryStore(Path(args.store))
    sname = Path(args.store).name
    ev = ValueEvaluator(args.ckpt)
    turn_meta: dict[tuple[int, int], dict] = {}
    exs, order = [], []
    for traj in ts.games(skip_undecodable=True):
        g = traj.header["g"]
        players = traj.header.get("players") or []
        seat = next((i for i, p in enumerate(players)
                     if str(p.get("name", "")).startswith("Anvil")), 0)
        wanted = {t for (gg, t) in arms if gg == g}
        if not wanted:
            continue
        by_turn: dict[int, list[tuple[int, dict]]] = {}
        for i, dec in enumerate(traj.decisions):
            if (dec.get("m") == "chooseSpellAbilityToPlay"
                    and dec.get("p") == seat and dec.get("t", 0) >= 1):
                by_turn.setdefault(dec["t"], []).append((i, dec))
        for t in sorted(wanted):
            idecs = by_turn.get(t) or []
            emis = _main1_window([d for _, d in idecs], seat)
            if emis is None:
                frame["f_no_window"] += 1
                continue
            emis_idx = next(i for i, d in idecs if d is emis)
            obs = emis["obs"]
            ents = {e["e"]: e for e in obs.get("ents", [])}
            views = source_views(obs, seat, table)
            extra_cmd = _cmd_extra(obs, seat)
            seen: set[tuple] = set()
            cands: dict[str, dict] = {}
            for opt in emis.get("opts", []):
                key = (opt.get("e"), str(opt.get("sa") or "")[:60])
                if key in seen:
                    continue
                seen.add(key)
                bucket, cost, extra, name = resolve_cost(opt, ents, table)
                if bucket == "spell" and ents.get(opt.get("e"), {}).get("z") == "command":
                    extra = extra_cmd
                if bucket not in ("spell", "ability") or cost is None:
                    continue
                if not can_pay(cost, views.now, extra):
                    continue
                label = str(opt.get("sa") or "")[:60]
                card = table.get(name)
                cands.setdefault(label, {
                    "cmc": cmc(cost, extra),
                    "generic": cost.generic + extra,
                    "pips": {c: sum(1 for s in cost.pips if s == frozenset(c))
                             for c in COLORS},
                    "hybrid": sum(1 for s in cost.pips if len(s) > 1)
                    + len(cost.twobrid_colors),
                    "producer": bool(card and card.prod),
                    "instant": bool(card and ("Instant" in (card.types or "")
                                              or "Flash" in (card.keywords or ""))),
                })
            turn_meta[(g, t)] = {"store": sname, "g": g, "t": t, "seat": seat,
                                 "arith": _arith(obs, seat), "cands": cands,
                                 "feat_idx": len(order)}
            order.append((g, t))
            exs.append(ev.example(emis, traj.header, seat,
                                  traj.decisions[:emis_idx]))
    print(f"{len(order)} fork windows featurized "
          f"({frame.get('f_no_window', 0)} sampled turns without one)")
    _capture_features(ev, exs, out, "f")

    # ---- rows ----
    rows = []
    for (g, t, aid), a in sorted(agg.items()):
        meta = turn_meta.get((g, t))
        if meta is None:
            frame["f_row_no_meta"] += 1
            continue
        seq = arms.get((g, t), {}).get(aid)
        if seq is None:
            frame["f_row_no_arm"] += 1
            continue
        if len(seq) == 0:
            frame["f_holdall_excluded"] += 1
            continue
        cs = [meta["cands"].get(lab) for lab in seq]
        if any(c is None for c in cs):
            frame["f_label_join_miss"] += 1
            continue
        cmcs = [c["cmc"] for c in cs]
        vec = {"n_steps": len(seq), "total_cmc": sum(cmcs),
               "max_cmc": max(cmcs), "mean_cmc": sum(cmcs) / len(cmcs),
               "n_producers": sum(c["producer"] for c in cs),
               "n_instants": sum(c["instant"] for c in cs),
               "hold_n": max(0, len(meta["cands"]) - len(set(seq))),
               "frac_scheduled": len(set(seq)) / max(1, len(meta["cands"])),
               "n_hybrid": sum(c["hybrid"] for c in cs),
               "generic_total": sum(c["generic"] for c in cs)}
        for c in COLORS:
            vec[f"pips_{c}"] = sum(cc["pips"][c] for cc in cs)
        realize_rate = a["realized"] / a["rolls"]
        degr_norm = (float(np.median([d / max(1, a["sched_n"]) for d in a["degr"]]))
                     if a["degr"] else None)
        rows.append({"store": meta["store"], "g": g, "t": t, "arm": aid,
                     "feat_idx": meta["feat_idx"], "arith": meta["arith"],
                     "armvec": [vec[k] for k in ARMVEC_KEYS],
                     "rolls": a["rolls"], "realize_rate": realize_rate,
                     "y_bin": int(realize_rate >= 0.5),
                     "degr_norm": degr_norm,
                     "why": dict(a["why"])})
        frame["f_rows"] += 1
    with open(out / "f-rows.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    (out / "f-frame.json").write_text(json.dumps(dict(frame), indent=2) + "\n")
    print(f"{len(rows)} (turn, arm) rows; frame={dict(frame)}")
    print(f"-> {out}/f-*")


def _norm(x: np.ndarray, tr: np.ndarray) -> np.ndarray:
    return (x - x[tr].mean(0)) / (x[tr].std(0) + 1e-6)


def _rho(y, p) -> float:
    from scipy.stats import spearmanr
    return float(spearmanr(y, p).statistic)


def _axis_ok(y_te: np.ndarray) -> bool:
    if len(np.unique(y_te)) < 3:
        u, cnt = np.unique(y_te, return_counts=True)
        return len(u) == 2 and cnt.min() >= MIN_SUPPORT
    return float(np.std(y_te)) > 0


def _rho_block(X_arms, Y, axes, tr) -> tuple[dict, list[str]]:
    """Per-arm mean Spearman over non-degenerate axes."""
    kept = [j for j in range(len(axes)) if _axis_ok(Y[~tr, j])]
    res = {}
    for name, X in X_arms.items():
        preds = _fit_predict(X[tr], Y[tr], X[~tr])
        if preds.ndim == 1:
            preds = preds[:, None]
        sp = {axes[j]: round(_rho(Y[~tr, j], preds[:, j]), 4) for j in kept}
        res[name] = {"mean": float(np.mean(list(sp.values()))), "axes": sp}
    return res, [axes[j] for j in kept]


def probe(args) -> None:
    out = Path(args.dump)
    report = {"gates": {"auc": GATE_AUC, "rho": GATE_RHO}}

    # ---------------- E + R ----------------
    groups = [json.loads(l) for l in open(out / "er-groups.jsonl")]
    fz = np.load(out / "er-features.npz")
    state, plan = fz["state"], fz["plan"]
    assert len(groups) == len(state)
    tr_g = _split(groups)
    arith = _norm(np.array([r["arith"] for r in groups], dtype=np.float64), tr_g)
    arms_e = {"arith": arith, "state": state,
              "state_plan": np.concatenate([state, plan], axis=1)}

    e_axes = ["untapped_total", "chained"] + [f"untapped_{c}" for c in COLORS]
    Ye = np.array([[r["e"][a] for a in e_axes] for r in groups], dtype=np.float64)
    res_e, kept_e = _rho_block(arms_e, Ye, e_axes, tr_g)
    ge = (res_e["state_plan"]["mean"] - res_e["arith"]["mean"] >= GATE_RHO["margin"]
          and res_e["state_plan"]["mean"] >= GATE_RHO["floor"])
    report["E"] = {"n": len(groups), "kept_axes": kept_e,
                   "floating_axis": "unavailable (obs sv=2 has no mana pool)",
                   "rho": res_e, "gate_pass": bool(ge)}

    slots = [json.loads(l) for l in open(out / "er-slots.jsonl")]
    gi = np.array([s["gidx"] for s in slots])
    tr_s = tr_g[gi]
    kn = _norm(np.array([[s["k"]] for s in slots], dtype=np.float64), tr_s)
    arms_r = {"arith": np.concatenate([arith[gi], kn], axis=1),
              "state": np.concatenate([state[gi], kn], axis=1),
              "state_plan": np.concatenate([state[gi], plan[gi], kn], axis=1)}
    r_axes = ["untapped_after", "afford_after"]
    Yr = np.array([[s[a] for a in r_axes] for s in slots], dtype=np.float64)
    res_r, kept_r = _rho_block(arms_r, Yr, r_axes, tr_s)
    gr = (res_r["state_plan"]["mean"] - res_r["arith"]["mean"] >= GATE_RHO["margin"]
          and res_r["state_plan"]["mean"] >= GATE_RHO["floor"])
    report["R"] = {"n_slots": len(slots), "kept_axes": kept_r, "rho": res_r,
                   "afford_bit": "no negatives in the trajectory stream "
                                 "(accepted casts); reported unsupported, not gated",
                   "gate_pass": bool(gr)}

    # ---------------- F ----------------
    rows = [json.loads(l) for l in open(out / "f-rows.jsonl")]
    fzf = np.load(out / "f-features.npz")
    fstate, fplan = fzf["state"], fzf["plan"]
    fi = np.array([r["feat_idx"] for r in rows])
    tr_f = _split(rows)
    farith = _norm(np.array([r["arith"] for r in rows], dtype=np.float64), tr_f)
    armvec = _norm(np.array([r["armvec"] for r in rows], dtype=np.float64), tr_f)
    arms_f = {"arith": np.concatenate([farith, armvec], axis=1),
              "state": np.concatenate([fstate[fi], armvec], axis=1),
              "state_plan": np.concatenate([fstate[fi], fplan[fi], armvec], axis=1)}
    yb = np.array([r["y_bin"] for r in rows], dtype=np.float64)
    res_fb = {}
    for name, X in arms_f.items():
        p = _fit_predict(X[tr_f], yb[tr_f], X[~tr_f])
        res_fb[name] = round(_auc(yb[~tr_f], p), 4)
    gf = (res_fb["state_plan"] - res_fb["arith"] >= GATE_AUC["margin"]
          and res_fb["state_plan"] >= GATE_AUC["floor"])
    # report-only refinement read: degrade slot on the degraded stratum
    has_d = np.array([r["degr_norm"] is not None for r in rows])
    yd = np.array([r["degr_norm"] or 0.0 for r in rows], dtype=np.float64)
    res_fd = {}
    trd, ted = tr_f & has_d, (~tr_f) & has_d
    for name, X in arms_f.items():
        p = _fit_predict(X[trd], yd[trd], X[ted])
        res_fd[name] = round(_rho(yd[ted], p), 4)
    report["F"] = {"n_rows": len(rows), "n_train": int(tr_f.sum()),
                   "pos_rate": float(yb.mean()),
                   "realize_auc": res_fb, "gate_pass": bool(gf),
                   "degrade_slot_rho_report_only": {
                       "n_degraded": int(has_d.sum()), **res_fd}}

    verdicts = {t: report[t]["gate_pass"] for t in ("E", "R", "F")}
    report["verdicts"] = verdicts
    (out / "probe-read.json").write_text(json.dumps(report, indent=2) + "\n")
    print("E  mean rho:  " + "  ".join(
        f"{k}={v['mean']:.4f}" for k, v in res_e.items())
        + f"  -> {'PASS' if verdicts['E'] else 'FAIL'}")
    print("R  mean rho:  " + "  ".join(
        f"{k}={v['mean']:.4f}" for k, v in res_r.items())
        + f"  -> {'PASS' if verdicts['R'] else 'FAIL'}")
    print("F  realize AUC:  " + "  ".join(
        f"{k}={v:.4f}" for k, v in res_fb.items())
        + f"  -> {'PASS' if verdicts['F'] else 'FAIL'}")
    print(f"F  degrade-slot rho (report only): {res_fd}")
    print(f"-> {out}/probe-read.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump-er")
    d.add_argument("--stores", nargs="+", required=True)
    d.add_argument("--ckpt", required=True)
    d.add_argument("--out", required=True)
    d.set_defaults(fn=dump_er)
    f = sub.add_parser("dump-f")
    f.add_argument("--plan", required=True)
    f.add_argument("--store", required=True)
    f.add_argument("--ckpt", required=True)
    f.add_argument("--out", required=True)
    f.set_defaults(fn=dump_f)
    p = sub.add_parser("probe")
    p.add_argument("--dump", required=True)
    p.set_defaults(fn=probe)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
