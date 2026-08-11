"""Cycle-over-cycle collapse-point migration read (M5 D1.2, ADR-0034).

Compares two early_doom output dirs (same-format summary.json +
curation.jsonl + traces.jsonl) against the pre-registered signatures in
m5-plan.md D1.2:

  ratchet-consistent: collapse points later/higher-value AND
                      addressable stock stable
  one-shot-consistent: same windows re-surfacing on the same decks

Because closing reads share the standing seed set, games are matched
per (model_seat, seed) across cycles — same matchup, same opener,
different policy. Optionally takes the prior cycle's drill selection to
split conversion by drilled/undrilled membership (memorization check).

Usage:
  uv run python scripts/migration_read.py \
      --prev data/runs/early-doom-run9-i009 \
      --curr data/runs/early-doom-run11-i019 \
      --selection data/runs/drill-selection-v2/selection.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median, quantiles

BIG_DROP = 0.30


def load(d: str):
    d_path = Path(d)
    summary = json.loads((d_path / "summary.json").read_text())
    cur = [json.loads(x) for x in (d_path / "curation.jsonl").read_text().splitlines()]
    traces = {}
    for x in (d_path / "traces.jsonl").read_text().splitlines():
        r = json.loads(x)
        traces[(r["model_seat"], r["seed"])] = r
    return summary, cur, traces


def profile(name: str, s: dict, cur: list[dict]) -> set:
    big = [c for c in cur if c["drop"] >= BIG_DROP]
    ct = [c["crash_from_turn"] for c in cur]
    pv = [c["peak_v"] for c in cur]
    q = lambda xs: [round(v, 3) for v in quantiles(xs, n=4)]
    decks = {c["decks"][c["model_seat"]] for c in big}
    print(f"--- {name}  (critic {s['ckpt']})")
    print(f"  games={s['games']} losses={s['losses']} winrate={s['winrate']}")
    print(
        f"  addressable={s['addressable_losses']}"
        f" ({s['addressable_loss_frac'] * 100:.1f}% of losses)"
    )
    d3 = s["doom"]["from_turn_3"]
    print("  luck-locked (from_turn_3):", {th.split("_")[1]: d3[th]["loss_doom_frac"] for th in d3})
    print(
        f"  >={BIG_DROP * 100:.0f}pp single-step collapses: {len(big)}  model-decks: {len(decks)}"
    )
    print(
        f"  crash_from_turn quartiles {q(ct)} mean {sum(ct) / len(ct):.2f};"
        f" peak_v quartiles {q(pv)} mean {sum(pv) / len(pv):.4f}"
    )
    return decks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prev", required=True, help="prior cycle early_doom dir")
    ap.add_argument("--curr", required=True, help="current cycle early_doom dir")
    ap.add_argument("--selection", help="prior cycle selection.jsonl (optional)")
    args = ap.parse_args()

    s1, c1, _ = load(args.prev)
    s2, c2, t2 = load(args.curr)
    d1 = profile("prev", s1, c1)
    d2 = profile("curr", s2, c2)

    print("--- deck overlap (>=30pp model-decks)")
    print(
        f"  prev={len(d1)} curr={len(d2)} overlap={len(d1 & d2)}"
        f" (jaccard {len(d1 & d2) / len(d1 | d2):.3f})"
    )

    key = lambda c: (c["model_seat"], c["seed"])
    k1 = {key(c): c for c in c1}
    k2 = {key(c): c for c in c2}
    retained = [k for k in k1 if k in k2]
    conv = [k for k in k1 if k in t2 and t2[k]["won"]]
    still_lost_dark = [k for k in k1 if k in t2 and not t2[k]["won"] and k not in k2]
    print(f"--- seed-level migration of prev addressable ({len(k1)})")
    print(f"  converted to wins:      {len(conv)} ({len(conv) / len(k1) * 100:.1f}%)")
    print(f"  still addressable loss: {len(retained)} ({len(retained) / len(k1) * 100:.1f}%)")
    print(f"  lost, no longer addressable (luck-locked/no-crash): {len(still_lost_dark)}")
    new = [k for k in k2 if k not in k1]
    print(
        f"  curr addressable on NEW seeds: {len(new)}/{len(k2)} ({len(new) / len(k2) * 100:.1f}%)"
    )
    if retained:
        dt = [k2[k]["crash_from_turn"] - k1[k]["crash_from_turn"] for k in retained]
        dv = [k2[k]["peak_v"] - k1[k]["peak_v"] for k in retained]
        print(
            f"  retained: crash-turn delta mean {sum(dt) / len(dt):+.2f}"
            f" (median {median(dt):+.1f});"
            f" peak_v delta mean {sum(dv) / len(dv):+.4f}"
        )

    if args.selection:
        sel = {key(json.loads(x)) for x in Path(args.selection).read_text().splitlines()}

        def rate(keys):
            ks = [k for k in keys if k in t2]
            w = sum(t2[k]["won"] for k in ks)
            return w, len(ks)

        dw, dn = rate(sel & set(k1))
        uw, un = rate(set(k1) - sel)
        p = (dw + uw) / (dn + un)
        se = math.sqrt(p * (1 - p) * (1 / dn + 1 / un))
        print("--- drilled vs undrilled conversion (memorization check)")
        print(f"  drilled   {dw}/{dn} = {dw / dn * 100:.1f}%")
        print(f"  undrilled {uw}/{un} = {uw / un * 100:.1f}%")
        if se > 0:
            print(f"  diff {100 * (dw / dn - uw / un):+.1f}pp, z = {(dw / dn - uw / un) / se:.2f}")
        else:
            # zero conversions both sides — definitional in a same-game
            # method-change read (same policy, same trajectories)
            print("  diff n/a (zero conversions both sides)")


if __name__ == "__main__":
    main()
