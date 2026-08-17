"""Natural-timing probe read (M8 D1, m8-plan pinned gate 2026-08-17).

Consumes single-natural-arm -forceseq -seqarms nat labels JSONL (one row
per fork point; per-completion arrays out/first_sa/first_t/land_t) and
reports the three pinned gate clauses:

  1. Split abundance: fraction of probed points with a non-degenerate
     two-bin split (in-window vs deferred, minority bin >= 12.5% of
     counted completions). PIN: >= 30%.
  2. Signal: RMS true dwr on the primary two-bin contrast over the
     split-bearing points, through the standing ADR-0051/0052 variance
     decomposition (independent binomial floor — within-natural bins
     cannot be paired). PIN: >= 0.10.
  3. Headroom: mismatch fraction (modal bin != argmax-dwr bin) x |dwr|
     scale x drilled-window play-weight (--play-weight, derived per the
     D1 ADR) => implied whole-game effect. PIN: >= ~1pp.

Descriptive (never gating): fine 4-bin classification (in-window / +1 /
+2 / >=+3-or-never, global turns), pooled per-bin winrates, land-timing
confound, top first-spell SAs.

Usage:
  python scripts/natural_timing_read.py <labels.jsonl> [...]
      [--seat-index 0] [--min-comps 32] [--play-weight <w>]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter

MINORITY_FRAC = 0.125  # pinned: minority bin >= 12.5% of counted comps
ABUNDANCE_PIN = 0.30
RMS_PIN = 0.10
HEADROOM_PIN = 0.01


def load(paths: list[str]) -> list[dict]:
    rows = []
    for p in paths:
        for line in open(p):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("seq") and r.get("arms") == "nat":
                rows.append(r)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    ap.add_argument(
        "--seat-index", type=int, default=0, help="drilled seat's winner index in out[]"
    )
    ap.add_argument(
        "--min-comps",
        type=int,
        default=32,
        help="minimum non-crash completions for a point to count as probed",
    )
    ap.add_argument(
        "--play-weight",
        type=float,
        default=None,
        help="drilled-window play-weight for the headroom clause (derived per the D1 ADR)",
    )
    a = ap.parse_args()

    rows = load(a.labels)
    if not rows:
        sys.exit("no single-natural-arm seq rows found")

    skips = [r for r in rows if r.get("seat_skip")]
    pts = [r for r in rows if not r.get("seat_skip")]
    print(f"fork points: {len(rows)} total, {len(skips)} seat_skip, {len(pts)} fired")
    tot_comps = sum(r["comps"] for r in pts)
    tot_k = sum(r["k"] for r in pts)
    anom = sum(r.get("nat_anom", 0) for r in pts)
    print(
        f"completions {tot_comps}/{tot_k} ({tot_comps / max(1, tot_k):.1%}), "
        f"crashes {sum(r.get('crash_nat', 0) for r in pts)}, "
        f"nat_anom {anom}{'  <-- TRIPLINE (must be 0)' if anom else ''}"
    )

    si = a.seat_index
    fine = Counter()  # offset bin -> [n, wins]
    fine_w = Counter()
    sa_counts = Counter()
    land_in, land_any, spell_after_land = 0, 0, 0
    probed = []  # (dwr, binvar, n_in, n_def, wr_in, wr_def, split)
    for r in pts:
        t0 = r["t"]
        wins_in = n_in = wins_def = n_def = 0
        for out, ft, lt, sa in zip(r["out"], r["first_t"], r["land_t"], r["first_sa"]):
            if out == -2:
                continue
            win = 1 if out == si else 0
            off = (ft - t0) if ft >= 0 else None
            bin4 = min(off, 3) if off is not None else 3  # >=+3 or never
            fine[bin4] += 1
            fine_w[bin4] += win
            if sa:
                sa_counts[sa] += 1
            if lt >= 0:
                land_any += 1
                if lt == t0:
                    land_in += 1
                if ft >= 0 and ft >= lt:
                    spell_after_land += 1
            if off == 0:
                n_in += 1
                wins_in += win
            else:
                n_def += 1
                wins_def += win
        counted = n_in + n_def
        if counted < a.min_comps:
            continue
        split = min(n_in, n_def) >= MINORITY_FRAC * counted
        if n_in and n_def:
            wr_in, wr_def = wins_in / n_in, wins_def / n_def
            dwr = wr_in - wr_def
            binvar = wr_in * (1 - wr_in) / n_in + wr_def * (1 - wr_def) / n_def
        else:
            dwr = binvar = None
        probed.append((dwr, binvar, n_in, n_def, split))

    n_probed = len(probed)
    splits = [p for p in probed if p[4]]
    abundance = len(splits) / max(1, n_probed)
    print(f"\nprobed (>= {a.min_comps} comps): {n_probed}")
    print(
        f"clause 1 — split abundance: {len(splits)}/{n_probed} = {abundance:.1%} "
        f"(pin >= {ABUNDANCE_PIN:.0%}) -> {'PASS' if abundance >= ABUNDANCE_PIN else 'FAIL'}"
    )

    if splits:
        dwrs = [p[0] for p in splits]
        binvars = [p[1] for p in splits]
        m = sum(dwrs) / len(dwrs)
        var_obs = sum((d - m) ** 2 for d in dwrs) / max(1, len(dwrs) - 1)
        mean_bin = sum(binvars) / len(binvars)
        var_sig = max(0.0, var_obs - mean_bin)
        rms = math.sqrt(var_sig)
        pos = sum(1 for d in dwrs if d > 0)
        neg = sum(1 for d in dwrs if d < 0)
        print(
            f"clause 2 — two-bin contrast (in-window - deferred) on split points:\n"
            f"  mean dwr {m:+.4f} | SD(point) {math.sqrt(var_obs):.4f} "
            f"| indep floor {math.sqrt(mean_bin):.4f}\n"
            f"  var_signal {var_sig:.5f} -> RMS true dwr {rms:.4f} "
            f"(pin >= {RMS_PIN}) -> {'PASS' if rms >= RMS_PIN else 'FAIL'}\n"
            f"  direction: {pos} pos / {neg} neg / {len(dwrs) - pos - neg} zero"
        )
        # clause 3: modal bin = the bin with more completions; argmax-dwr
        # bin = sign of dwr. Mismatch = policy's usual timing is not the
        # better-scoring bin.
        mism = sum(
            1 for d, _, n_in, n_def, _ in splits if (n_in > n_def) != (d > 0) and d != 0
        )
        mism_frac = mism / len(splits)
        mean_abs = sum(abs(d) for d in dwrs) / len(dwrs)
        print(
            f"clause 3 — mismatch fraction {mism_frac:.1%}, "
            f"mean |dwr| {mean_abs:.4f} (upward-biased; RMS true {rms:.4f} is the "
            f"shrunk scale)"
        )
        for label, scale in (("naive", mean_abs), ("rms-true", rms)):
            if a.play_weight is not None:
                imp = mism_frac * scale * a.play_weight
                print(
                    f"  implied whole-game effect ({label}): {imp * 100:.2f}pp "
                    f"(pin >= {HEADROOM_PIN * 100:.0f}pp) -> "
                    f"{'PASS' if imp >= HEADROOM_PIN else 'FAIL'}"
                )
        if a.play_weight is None:
            print("  (no --play-weight given: supply the ADR-derived value to close clause 3)")

    print("\ndescriptive — fine bins (global-turn offsets; NEVER gating):")
    names = {0: "in-window", 1: "+1 (opp turn)", 2: "+2", 3: ">=+3 or never"}
    for b in sorted(fine):
        n = fine[b]
        print(f"  {names[b]:>14}: {n:5d} ({n / max(1, sum(fine.values())):.1%})  wr {fine_w[b] / max(1, n):.3f}")
    print(
        f"land confound: {land_any} comps played a land ({land_in} in-window); "
        f"{spell_after_land} first-spells landed on/after the land turn"
    )
    print("top first spells:")
    for sa, n in sa_counts.most_common(10):
        print(f"  {n:5d}  {sa}")


if __name__ == "__main__":
    main()
