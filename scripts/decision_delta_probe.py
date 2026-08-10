"""P0 decision-delta probe (M7 D1, m7-plan.md — pre-registered gate).

Within a single drill fork point, the K sampled completions share an
identical game state; the only difference is the sampled action. So
conditioning outcomes on the drilled seat's first realized action class
WITHIN a fork point is an unconfounded read of the per-decision action
differential — the dense signal ADR-0049 says the loop is missing.

Classification is by REALIZATION, not candidate index (no featurizer /
obs assembly needed): mu c==0 at an eligible window (any non-land option
offered) = pass-first; any `playChosenSpellAbility` whose sa is not
"Play land" = act-first; land plays are skipped (playing a land then
holding vs then casting is still the timing question). Completions that
never reach an eligible choice are excluded from the split. Approximation
noted: ability activations realize through the same record and count as
"act" — the probe measures act-now vs hold, a superset of cast timing.

Gate (PINNED 2026-08-10 before numbers were seen, m7-plan D1):
  FUNDED iff split-able fraction >= 0.30 AND RMS true Δwr over
  split-able points >= 0.10, plus the directional check that
  hold-then-act-later outperforms act-now where holding occurs.
  Split-able (operationalized pre-run): >=2 completions in EACH class.

Usage:
  .venv/bin/python scripts/decision_delta_probe.py \
      --stores 'data/trajectories/drillmix*-forks' \
      --selection data/runs/drill-selection-v4/selection.jsonl \
      --out data/runs/p0-decision-delta/probe.json
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anvil.store.trajectories import open_store  # noqa: E402


def _bin_of(wr: float) -> str:
    # canonical bins (critic_calibration.py / grindstone report)
    return ("lost" if wr <= 0.2 else "long_shot" if wr <= 0.45
            else "coin" if wr <= 0.7 else "winnable")


_DIRNAME = re.compile(r"drillmix(\d+)-(.+)-\d{8}-\d{6}-forks$")


def classify_completion(decisions, mu, seat):
    """-> (first_class, held_then_act) with first_class in
    {'act','pass',None}; held_then_act only meaningful for 'pass'."""
    first = None
    held_then_act = False
    for d in decisions:
        if d.get("p") != seat:
            continue
        m = d.get("m")
        if m == "playChosenSpellAbility":
            sa = (d.get("args") or {}).get("sa", "")
            if sa == "Play land":
                continue
            if first is None:
                return "act", False
            held_then_act = True
            break
        if m == "chooseSpellAbilityToPlay" and d.get("by") == "bridge":
            rec = mu.get(d["s"])
            if rec is None or rec.get("task") != "priority":
                continue
            if rec.get("c", 0) == 0:
                opts = d.get("opts") or []
                eligible = any(o.get("kind") not in (None, "land")
                               for o in opts)
                if eligible and first is None:
                    first = "pass"
                # ineligible (land/empty-only window): forced pass, keep
                # scanning for a later eligible window
            # c>0: intent; realization (or veto->re-ask chain) decides —
            # keep scanning
    return first, held_then_act


def main():
    ap = argparse.ArgumentParser()
    # default = run13-era stores only (the audit's population; the pinned
    # gate applies to this read). Older runs' drillmix stores are a valid
    # SUPPORTING read (different policy/curation era) via --stores.
    ap.add_argument("--stores",
                    default="data/trajectories/drillmix*cycle3*-forks")
    ap.add_argument("--selection",
                    default="data/runs/drill-selection-v4/selection.jsonl")
    ap.add_argument("--out", default="data/runs/p0-decision-delta/probe.json")
    ap.add_argument("--limit", type=int, default=0,
                    help="debug: max stores to scan")
    a = ap.parse_args()

    sel_wr = {}
    for line in open(a.selection):
        r = json.loads(line)
        sel_wr[(r["store"], r["g"])] = r["sel_wr"]

    dirs = sorted(glob.glob(a.stores))
    if a.limit:
        dirs = dirs[:a.limit]
    if not dirs:
        sys.exit(f"no stores match {a.stores}")

    # points[(iter, arm, pg, fp)] = per-class tallies
    points = defaultdict(lambda: {"act_n": 0, "act_w": 0, "pass_n": 0,
                                  "pass_w": 0, "hta_n": 0, "hta_w": 0,
                                  "excluded": 0})
    n_scanned = 0
    for dpath in dirs:
        m = _DIRNAME.search(dpath)
        if not m:
            print(f"[skip] unparseable dir name: {dpath}", file=sys.stderr)
            continue
        it, arm = int(m.group(1)), m.group(2)
        try:
            st = open_store(dpath)
        except Exception as e:
            print(f"[skip] unreadable store {dpath}: {e}", file=sys.stderr)
            continue
        for g in st.game_indices():
            mu = st.mu_for_game(g)
            if not mu:
                continue
            try:
                traj = st.game(g)
            except Exception:
                continue
            fk = traj.header.get("fork") or {}
            players = traj.header.get("players") or []
            seat = next((i for i, p in enumerate(players)
                         if str(p.get("name", "")).startswith("Anvil")), None)
            if seat is None or "pg" not in fk:
                continue
            w = 1.0 if st.winner_seat(g) == seat else 0.0
            cls, hta = classify_completion(traj.decisions, mu, seat)
            key = (it, arm, fk["pg"], fk["fp"])
            pt = points[key]
            if cls == "act":
                pt["act_n"] += 1
                pt["act_w"] += w
            elif cls == "pass":
                pt["pass_n"] += 1
                pt["pass_w"] += w
                if hta:
                    pt["hta_n"] += 1
                    pt["hta_w"] += w
            else:
                pt["excluded"] += 1
            n_scanned += 1
        print(f"[scan] iter {it:03d} {arm}: cumulative "
              f"{len(points)} points / {n_scanned} completions", flush=True)

    # ---- aggregate ----
    def summarize(keys):
        splittable, d_obs, v_samp = [], [], []
        for k in keys:
            p = points[k]
            if p["act_n"] >= 2 and p["pass_n"] >= 2:
                splittable.append(k)
                wa = p["act_w"] / p["act_n"]
                wp = p["pass_w"] / p["pass_n"]
                d_obs.append(wa - wp)
                n, wins = (p["act_n"] + p["pass_n"],
                           p["act_w"] + p["pass_w"])
                pt = (wins + 1) / (n + 2)  # Agresti-style, avoids var=0
                v_samp.append(pt * (1 - pt) *
                              (1 / p["act_n"] + 1 / p["pass_n"]))
        ge1 = sum(1 for k in keys
                  if points[k]["act_n"] >= 1 and points[k]["pass_n"] >= 1)
        if not d_obs:
            return {"points": len(keys), "splittable": 0,
                    "split_frac_ge1": round(ge1 / max(1, len(keys)), 4)}
        m2 = sum(d * d for d in d_obs) / len(d_obs)
        vs = sum(v_samp) / len(v_samp)
        rms_true = math.sqrt(max(0.0, m2 - vs))
        return {"points": len(keys), "splittable": len(splittable),
                "split_frac": round(len(splittable) / len(keys), 4),
                "split_frac_ge1": round(ge1 / len(keys), 4),
                "mean_delta": round(sum(d_obs) / len(d_obs), 4),
                "rms_obs": round(math.sqrt(m2), 4),
                "mean_sampling_var": round(vs, 4),
                "rms_true_delta": round(rms_true, 4)}

    all_keys = list(points)
    overall = summarize(all_keys)

    per_iter = {it: summarize([k for k in all_keys if k[0] == it])
                for it in sorted({k[0] for k in all_keys})}

    by_bin = {}
    for b in ("lost", "long_shot", "coin", "winnable", "unknown"):
        ks = []
        for k in all_keys:
            _, arm, pg, _ = k
            wr = sel_wr.get((arm, pg))
            kb = _bin_of(wr) if wr is not None else "unknown"
            if kb == b:
                ks.append(k)
        if ks:
            by_bin[b] = summarize(ks)

    # directional read: hold-then-act-later vs act-now, pooled over points
    # where BOTH occur (cluster-robust SE via per-point deltas)
    dir_deltas = []
    for k in all_keys:
        p = points[k]
        if p["hta_n"] >= 1 and p["act_n"] >= 1:
            dir_deltas.append(p["hta_w"] / p["hta_n"]
                              - p["act_w"] / p["act_n"])
    if dir_deltas:
        mean_dir = sum(dir_deltas) / len(dir_deltas)
        var_dir = (sum((d - mean_dir) ** 2 for d in dir_deltas)
                   / max(1, len(dir_deltas) - 1))
        se_dir = math.sqrt(var_dir / len(dir_deltas))
        directional = {"points": len(dir_deltas),
                       "mean_hta_minus_act": round(mean_dir, 4),
                       "se": round(se_dir, 4)}
    else:
        directional = {"points": 0}

    gate = {"pinned": "split_frac >= 0.30 AND rms_true_delta >= 0.10 "
                      "(+ directional check)",
            "split_frac": overall.get("split_frac", 0.0),
            "rms_true_delta": overall.get("rms_true_delta", 0.0),
            "funded": (overall.get("split_frac", 0.0) >= 0.30
                       and overall.get("rms_true_delta", 0.0) >= 0.10)}

    out = {"stores_scanned": len(dirs), "completions": n_scanned,
           "overall": overall, "per_iteration": per_iter,
           "by_bin": by_bin, "directional": directional, "gate": gate}
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=1))
    print(json.dumps({"overall": overall, "directional": directional,
                      "gate": gate}, indent=1))
    print(f"[done] full report -> {outp}")


if __name__ == "__main__":
    main()
