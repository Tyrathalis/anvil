"""M9 D2a — the frozen-trunk affordability probe (m9-plan D2a, PINNED 2026-08-19).

Question: can affordability — will the engine veto this cast? — be
predicted from the current representation? High probe accuracy => the
trunk already carries the ingredients and the veto gap is
behavioral/interface; low => a genuine representation gap the §3c
surface must expose.

Pins (m9-plan D2a, pre-data):
- LABEL: will-the-engine-veto on the chosen cast. Positives =
  first-attempt `unpayable` vetoes; negatives = engine-accepted
  first-attempt casts/activations (land plays excluded — not casts,
  zero cost; pass excluded). Timing excluded (not affordability).
  Headline on the raw engine label; AUC additionally STRATIFIED by the
  D1 v2 instrument verdict (knowable / auto-payer artifact / uncertain).
- SUBSTRATE: `[STATE] ⊕ candidate-entity token` primary (both trunk
  outputs — the pointer head's input pair; recorded extension of the
  M6 probe-on-[STATE] rule); `[STATE]`-only reported alongside.
- BASELINE LADDER: base rate → cost-pips-only → obs-arithmetic (the v2
  instrument's own uncorroborated verdict + source-view counts as
  explicit features) → `[STATE]` → `[STATE] ⊕ cand`. Claiming "the
  trunk carries affordability" requires beating the obs-arithmetic arm
  by >= 0.03 AUC (the ADR-0043 reconstruction discipline).
- GATE: held-out AUC on `[STATE] ⊕ cand` >= 0.75 => behavioral/
  interface gap; <= 0.60 => representation gap; between => checkpoint.
  D2b routing: high => SKIPPED; low => funded (ADR-0044 precedent).
- POPULATIONS: fit + holdout on the sampled trio (training
  distribution), game-grouped deterministic split (the frozen-probe
  convention); transfer reads (NO refit) on argmax and elevated.

Leakage guard: the obs-arithmetic arm runs `classify_window` with
corroborated=False on every example — the corroborated path branches on
the engine's own unpayable verdict, which IS the label. Stratification
uses the official corroborated D1 v2 verdicts (labels only, never
features).

Trunk: `policy-i019` (data/training/d6-run11/iter-019/train/last.pt),
the ckpt of record and the sampled population's own policy; probed on
its own masked view.

Usage:
  uv run python scripts/affordability_probe.py labels   --out data/runs/affordability-probe-d2a
  uv run python scripts/affordability_probe.py features --out data/runs/affordability-probe-d2a
  uv run python scripts/affordability_probe.py probe    --out data/runs/affordability-probe-d2a
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veto_knowability import (  # noqa: E402
    Cost,
    build_card_table,
    can_pay,
    classify_window,
    cost_from_sa,
    frame_index,
    scan_census,
    source_views,
)

ROOT = Path(__file__).resolve().parent.parent
TRUNK_CKPT = "data/training/d6-run11/iter-019/train/last.pt"
WINDOWS_V2 = ROOT / "data/runs/veto-knowability-m9d1/windows.jsonl"

# fit population first; the rest are transfer reads (no refit), pinned order
POPS = {
    "sampled": [
        "data/runs/d6-run17-i000-20260818-101603",
        "data/runs/d6-run17-i000h0-20260818-102516",
        "data/runs/d6-run17-i000h1-20260818-102923",
    ],
    "argmax": [
        "data/runs/d3-rebaselinearm-s0-20260811-222754",
        "data/runs/d3-rebaselinearm-s1-20260811-225502",
    ],
    "elevated": [
        "data/runs/run17-i009-finalarm-s0-20260818-215538",
        "data/runs/run17-i009-finalarm-s1-20260818-222434",
        "data/runs/run17-i010-finalarm-s0-20260818-231500",
        "data/runs/run17-i010-finalarm-s1-20260818-234006",
    ],
}
FIT_POP = "sampled"
NEG_CAP_PER_POP = 40_000  # seeded subsample above this; dropped counts logged
RIDGE_ALPHAS = [1.0, 10.0, 100.0, 1000.0, 10000.0]
CV_FOLDS = 5
GATE_HI, GATE_LO, ARITH_MARGIN = 0.75, 0.60, 0.03
STRATA = ("knowable", "not_knowable", "uncertain")

COLORS = "WUBRGC"


# ---------------------------------------------------------------- shared


def match_opt(dec: dict, pick: str) -> dict | None:
    for o in dec.get("opts", []):
        sa = str(o.get("sa") or "")
        if sa == pick or sa.startswith(pick) or pick.startswith(sa):
            return o
    return None


def held_out(run: str, g: int) -> bool:
    # frozen-probe convention: deterministic game-grouped 80/20
    return hashlib.sha256(f"{run}:{g}".encode()).digest()[0] % 5 == 0


def auc(y: np.ndarray, score: np.ndarray) -> float:
    """Mann-Whitney AUC via rank sum (ties averaged)."""
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score), dtype=float)
    s = score[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    pos = y == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


# ---------------------------------------------------------------- labels


def cmd_labels(args):
    verdicts = {}
    for line in open(WINDOWS_V2):
        d = json.loads(line)
        verdicts[(d["pop"], d["run"], d["g"], d["s"])] = (d["verdict"], d["why"])
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260819)
    stats = {}
    with open(out / "labels.jsonl", "w") as f:
        for pop, dirs in POPS.items():
            rows, n_neg_raw = [], 0
            for d in dirs:
                rd = ROOT / d
                for w in sorted(rd.glob("workers/inv-*")):
                    bases, vetoes, accepted = scan_census(w)
                    for g, by_s in vetoes.items():
                        for s_, r in by_s.items():
                            if r.get("veto") != "unpayable" or r.get("reask"):
                                continue
                            v, why = verdicts.get((pop, rd.name, g, s_), ("uncertain", "unjoined"))
                            rows.append({
                                "pop": pop, "run": rd.name, "worker": w.name,
                                "g": g, "s": s_, "obs_s": s_ - bases.get(g, 0),
                                "y": 1, "stratum": v, "why": why,
                                "pick": (r.get("pick") or "")[:60],
                            })
                    for r in accepted:
                        n_neg_raw += 1
                        rows.append({
                            "pop": pop, "run": rd.name, "worker": w.name,
                            "g": r["g"], "s": r["s"],
                            "obs_s": r["s"] - bases.get(r["g"], 0),
                            "y": 0, "stratum": "accepted", "why": "",
                            "pick": (r.get("pick") or "")[:60],
                        })
            negs = [r for r in rows if r["y"] == 0]
            poss = [r for r in rows if r["y"] == 1]
            if len(negs) > NEG_CAP_PER_POP:
                negs = rng.sample(negs, NEG_CAP_PER_POP)
                print(f"[labels] {pop}: negatives capped {n_neg_raw} -> "
                      f"{NEG_CAP_PER_POP} (seeded)", file=sys.stderr)
            for r in poss + negs:
                f.write(json.dumps(r) + "\n")
            stats[pop] = {"pos": len(poss), "neg": len(negs), "neg_raw": n_neg_raw,
                          "strata": dict(Counter(r["stratum"] for r in poss))}
            print(f"[labels] {pop}: {len(poss)} pos / {len(negs)} neg "
                  f"(raw {n_neg_raw}) strata={stats[pop]['strata']}", file=sys.stderr)
    (out / "labels-meta.json").write_text(json.dumps(
        {"pops": POPS, "windows": str(WINDOWS_V2), "neg_cap": NEG_CAP_PER_POP,
         "stats": stats}, indent=1))


# ---------------------------------------------------------------- features


def _cost_of(opt: dict, name: str, table: dict) -> tuple[Cost | None, bool]:
    """Coarse cost resolution for the FEATURE arms (classify_window stays the
    verdict authority): abilities via cost_from_sa, spells via the front-face
    table cost. Returns (cost, resolved)."""
    sa = str(opt.get("sa") or "")
    if opt.get("kind") == "ability":
        cost, _free = cost_from_sa(sa)
        return (cost if cost is not None else Cost()), True
    card = table.get(name)
    if card is None:
        return None, False
    return card.cost, True


def _feats(dec: dict, opt: dict, table: dict) -> tuple[np.ndarray, np.ndarray]:
    """(cost-pips-only features, obs-arithmetic features) — NO engine verdict
    anywhere (leakage guard: corroborated=False)."""
    obs = dec.get("obs") or {}
    seat = dec.get("p")
    ents = {e["e"]: e for e in obs.get("ents", [])}
    ent = ents.get(opt.get("e")) or {}
    name = ent.get("n", "")
    cost, resolved = _cost_of(opt, name, table)
    c = cost or Cost()
    pips = Counter()  # pips are frozensets (any member pays) — count per color
    for pip in c.pips:
        for col in pip:
            pips[col] += 1
    extra = 0
    if ent.get("z") == "command":
        try:
            extra = 2 * min(obs["players"][seat]["cmdcast"])
        except (KeyError, IndexError, TypeError, ValueError):
            extra = 0
    total = c.generic + len(c.pips) + len(c.twobrid_colors)
    f_cost = np.array(
        [c.generic] + [pips.get(col, 0) for col in COLORS]
        + [len(c.twobrid_colors), float(bool(c.phyrexian)), float(bool(c.x)),
           float(bool(c.snow)), total, extra, float(not resolved)],
        dtype=np.float32)

    v = source_views(obs, seat, table)
    fake = {"veto": "unpayable", "pick": str(opt.get("sa") or "")[:60]}
    verdict = classify_window(fake, dec, table, corroborated=False)["verdict"]
    onehot = [float(verdict == k) for k in STRATA]
    colors_now = len(frozenset().union(*v.now)) if v.now else 0
    f_arith = np.concatenate([f_cost, np.array(
        [len(v.now), len(v.cond), len(v.full), colors_now,
         float(can_pay(c, v.now, extra)), float(can_pay(c, v.cond, extra)),
         float(can_pay(c, v.full, extra)), float(v.chained),
         float(v.var_amount), float(v.unknown_untapped)] + onehot,
        dtype=np.float32)])
    return f_cost, f_arith


def cmd_features(args):
    import torch

    from anvil.ante.ledger import ValueEvaluator
    from anvil.encoder.transform import assemble
    from anvil.store.trajectories import decode_frame
    from anvil.training.dataset import collate

    table = build_card_table()
    out = ROOT / args.out
    labels = [json.loads(line) for line in open(out / "labels.jsonl")]
    ev = ValueEvaluator(TRUNK_CKPT)

    def example_with_row(dec, header, seat, prior, pick_eid):
        # ev.example builds the collate-exact tensor dict; one extra assemble
        # recovers entity_row_of (row construction is history-independent —
        # rows come from the obs entity loop, transform.py)
        o = assemble(dec, header, perspective=seat, history=[],
                     full_vis=ev.full_vis)
        row = o["entity_row_of"].get(pick_eid, -1)
        return ev.example(dec, header, seat, prior), row

    @torch.no_grad()
    def capture(exs, rows):
        ss, cc = [], []
        for i in range(0, len(exs), ev.batch):
            chunk = collate(exs[i : i + ev.batch])
            chunk = {k: v_.to(ev.device) for k, v_ in chunk.items()}
            with torch.autocast(ev.device, dtype=torch.bfloat16):
                card_vecs = ev.net.cards(chunk["ent_emb"])
                tokens, pad = ev.net.assemble(card_vecs, chunk)
                o = ev.net.trunk(tokens, src_key_padding_mask=pad)
            r = torch.tensor(rows[i : i + ev.batch], device=o.device)
            ar = torch.arange(len(r), device=o.device)
            ss.append(o[:, 0].float().cpu().numpy())
            cc.append(o[ar, 2 + r].float().cpu().numpy())
        return np.concatenate(ss), np.concatenate(cc)

    by_wg: dict[tuple, dict[int, list]] = {}
    for r in labels:
        by_wg.setdefault((r["pop"], r["run"], r["worker"]), {}).setdefault(
            r["g"], []).append(r)

    drops = Counter()
    for pop in POPS:
        t0 = time.time()
        keys, exs, rows, ys, strata, fcs, fas = [], [], [], [], [], [], []
        for (p_, run, worker), by_g in sorted(by_wg.items()):
            if p_ != pop:
                continue
            wdir = ROOT / "data/runs" / run / "workers" / worker
            idx = frame_index(wdir)
            with open(wdir / "obs.zst", "rb") as fh:
                for g, rs in sorted(by_g.items()):
                    if g not in idx:
                        drops[f"{pop}:frame_missing"] += len(rs)
                        continue
                    off, clen = idx[g]
                    fh.seek(off)
                    try:
                        header, decs, _end, _marks = decode_frame(fh.read(clen))
                    except Exception:
                        drops[f"{pop}:frame_undecodable"] += len(rs)
                        continue
                    by_s = {d["s"]: (i, d) for i, d in enumerate(decs)}
                    for r in rs:
                        hit = by_s.get(r["obs_s"])
                        if hit is None or hit[1].get("m") != "chooseSpellAbilityToPlay":
                            drops[f"{pop}:dec_missing"] += 1
                            continue
                        i, dec = hit
                        opt = match_opt(dec, r["pick"])
                        if opt is None:
                            drops[f"{pop}:pick_unmatched"] += 1
                            continue
                        if opt.get("kind") == "land":
                            drops[f"{pop}:land_excluded"] += 1
                            continue
                        ex, row = example_with_row(dec, header, dec.get("p"),
                                                   decs[:i], opt.get("e"))
                        if row < 0:
                            drops[f"{pop}:entity_row_missing"] += 1
                            continue
                        fc, fa = _feats(dec, opt, table)
                        keys.append(f"{run}:{r['g']}:{r['s']}")
                        exs.append(ex)
                        rows.append(row)
                        ys.append(r["y"])
                        strata.append(r["stratum"])
                        fcs.append(fc)
                        fas.append(fa)
        state, cand = capture(exs, rows)
        np.savez_compressed(
            out / f"features-{pop}.npz",
            keys=np.array(keys), run_g=np.array(
                [k.rsplit(":", 2)[0] + ":" + k.rsplit(":", 2)[1] for k in keys]),
            state=state, cand=cand, y=np.array(ys, dtype=np.int64),
            stratum=np.array(strata), f_cost=np.stack(fcs), f_arith=np.stack(fas))
        print(f"[feat] {pop}: {len(keys)} examples "
              f"({int(np.sum(ys))} pos), {time.time() - t0:.0f}s", file=sys.stderr)
    print(f"[feat] drops: {dict(drops)}", file=sys.stderr)
    (out / "features-meta.json").write_text(json.dumps(
        {"trunk": TRUNK_CKPT, "drops": dict(drops)}, indent=1))


# ---------------------------------------------------------------- probe


def _standardize(xtr, *rest):
    mu, sd = xtr.mean(0), xtr.std(0) + 1e-8
    return tuple((x - mu) / sd for x in (xtr, *rest)), (mu, sd)


def _ridge_fit(x, y, alpha):
    xb = np.hstack([x, np.ones((len(x), 1))])
    eye = np.eye(xb.shape[1])
    eye[-1, -1] = 0.0
    return np.linalg.solve(xb.T @ xb + alpha * eye, xb.T @ y)


def _ridge_pred(x, w):
    return np.hstack([x, np.ones((len(x), 1))]) @ w


def _cv_alpha(x, y, games):
    fold_of = {g: hashlib.sha256(f"cv:{g}".encode()).digest()[0] % CV_FOLDS
               for g in sorted(set(games.tolist()))}
    fold = np.array([fold_of[g] for g in games])
    best, best_a = -2.0, RIDGE_ALPHAS[0]
    for a in RIDGE_ALPHAS:
        ss = []
        for f in range(CV_FOLDS):
            m = fold == f
            if (y[m] == 1).sum() < 10 or (y[m] == 0).sum() < 10:
                continue
            w = _ridge_fit(x[~m], y[~m].astype(float), a)
            ss.append(auc(y[m], _ridge_pred(x[m], w)))
        s = float(np.nanmean(ss)) if ss else -2.0
        if s > best:
            best, best_a = s, a
    return best_a, best


def _stratified(y, stratum, score):
    outp = {}
    neg = y == 0
    for st in STRATA:
        m = (y == 1) & (stratum == st)
        if m.sum() < 20:
            outp[st] = {"n_pos": int(m.sum()), "auc": None}
            continue
        yy = np.concatenate([np.ones(int(m.sum())), np.zeros(int(neg.sum()))])
        sc = np.concatenate([score[m], score[neg]])
        outp[st] = {"n_pos": int(m.sum()), "auc": round(auc(yy, sc), 4)}
    return outp


def cmd_probe(args):
    out = ROOT / args.out
    data = {p: np.load(out / f"features-{p}.npz", allow_pickle=False)
            for p in POPS}
    d = data[FIT_POP]
    # keys are f"{run}:{g}:{s}"
    ho = np.array([held_out(k.rsplit(":", 2)[0], int(k.rsplit(":", 2)[1]))
                   for k in d["keys"]])
    games = d["run_g"]
    arms = {
        "cost_pips": d["f_cost"],
        "obs_arith": d["f_arith"],
        "state": d["state"],
        "state_cand": np.hstack([d["state"], d["cand"]]),
    }
    report = {"pins": {"gate_hi": GATE_HI, "gate_lo": GATE_LO,
                       "arith_margin": ARITH_MARGIN, "fit_pop": FIT_POP,
                       "label": "unpayable-vs-accepted, first-attempt, land/pass excluded"},
              "n": {"fit_train": int((~ho).sum()), "fit_holdout": int(ho.sum()),
                    "prevalence_holdout": round(float(d["y"][ho].mean()), 4)},
              "arms": {}, "transfer": {}}
    fitted = {}
    for name, x in arms.items():
        (xtr, xte), (mu, sd) = _standardize(x[~ho], x[ho])
        a, cv_s = _cv_alpha(xtr, d["y"][~ho], games[~ho])
        w = _ridge_fit(xtr, d["y"][~ho].astype(float), a)
        sc = _ridge_pred(xte, w)
        report["arms"][name] = {
            "alpha": a, "cv_auc": round(cv_s, 4),
            "holdout_auc": round(auc(d["y"][ho], sc), 4),
            "stratified": _stratified(d["y"][ho], d["stratum"][ho], sc),
        }
        fitted[name] = (mu, sd, w)
        print(f"[probe] {name:11s} holdout AUC {report['arms'][name]['holdout_auc']}",
              file=sys.stderr)
    for pop in POPS:
        if pop == FIT_POP:
            continue
        dd = data[pop]
        armsx = {"cost_pips": dd["f_cost"], "obs_arith": dd["f_arith"],
                 "state": dd["state"],
                 "state_cand": np.hstack([dd["state"], dd["cand"]])}
        report["transfer"][pop] = {}
        for name, x in armsx.items():
            mu, sd, w = fitted[name]
            sc = _ridge_pred((x - mu) / sd, w)
            report["transfer"][pop][name] = {
                "auc": round(auc(dd["y"], sc), 4),
                "n_pos": int(dd["y"].sum()), "n": int(len(dd["y"])),
                "stratified": _stratified(dd["y"], dd["stratum"], sc),
            }
    sc_auc = report["arms"]["state_cand"]["holdout_auc"]
    ar_auc = report["arms"]["obs_arith"]["holdout_auc"]
    report["gate"] = {
        "state_cand_auc": sc_auc,
        "verdict": ("behavioral_interface" if sc_auc >= GATE_HI
                    else "representation_gap" if sc_auc <= GATE_LO
                    else "between_checkpoint"),
        "beats_arith_by": round(sc_auc - ar_auc, 4),
        "trunk_adds_beyond_arithmetic": bool(sc_auc - ar_auc >= ARITH_MARGIN),
        "d2b_routing": ("skip" if sc_auc >= GATE_HI
                        else "funded" if sc_auc <= GATE_LO else "checkpoint"),
    }
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report["gate"], indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(required=True)
    for name, fn in (("labels", cmd_labels), ("features", cmd_features),
                     ("probe", cmd_probe)):
        c = sub.add_parser(name)
        c.add_argument("--out", required=True)
        c.set_defaults(func=fn)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
