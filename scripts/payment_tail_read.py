#!/usr/bin/env python3
"""M9 pre-D4 revisit: the payment-class TAIL-PROBE read.

Reads census JSONL from a -paytelemetry run made with the tail-probe jar
(-Danvil.pay.tailK=64: raised class cap + node budget, telemetry-only) and
answers the two questions the K_MAX revisit session needs
(m9-payment-surface-spec §11; census 2026-08-19 fired the 5% gate at 0.3911):

1. HOW FAR does the true class-count tail go?  The K=8 census piled
   everything >=8 into one censored bin (4,233 windows).  This read reports
   the true histogram, quantiles on consequential windows, and coverage
   curves ("a cap of K covers X% of consequential windows uncensored").
2. WHY does it explode?  Cross-tab of distinct SOURCE classes vs payment
   classes on the formerly-censored (>8) windows:
   - few source classes but many payment classes  => assignment
     combinatorics (generic mana spread over the same sources) => a
     spend-profile/coarser plan key is viable;
   - many source classes => genuinely many distinct residuals => selection
     (diversity pruning) is the honest fix.

Also reports measurement censoring at the probe's own caps (kcap@tailK,
nodecap) — if those still bind, the tail is deeper than measured.

Usage: payment_tail_read.py <census.jsonl> [more.jsonl ...]

Records without the tail kvs (srcclasses/nodes/kcap/nodecap) are counted
but excluded from cause attribution (pre-probe jars).
"""

import json
import sys
from collections import Counter


PINNED_K = 8  # the spec §11 wire cap the probe is evidence about


def pct(n, d):
    return n / d if d else 0.0


def quantile(sorted_vals, q):
    if not sorted_vals:
        return 0
    i = min(len(sorted_vals) - 1, int(q * len(sorted_vals)))
    return sorted_vals[i]


def read(paths):
    games = set()
    scoped = 0
    conseq = 0
    tail_kvs = 0          # records carrying the probe kvs
    kcap = 0              # probe class cap hit (true count >= tailK)
    nodecap = 0           # probe node budget hit
    class_hist = Counter()
    conseq_counts = []            # true class counts, consequential windows
    over_pinned = []              # (classes, srcclasses, turn) where classes > PINNED_K
    src_hist_over = Counter()     # srcclasses distribution on the over-pinned set
    by_turn = Counter()
    by_turn_over = Counter()
    nodes_over = []

    for path in paths:
        with open(path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("ev") == "start":
                    games.add((path, r.get("g")))
                    continue
                if r.get("m") != "payManaCost" or r.get("effect") or "classes" not in r:
                    continue
                scoped += 1
                k = r["classes"]
                class_hist[k] += 1
                turn = r.get("t", 0)
                by_turn[turn // 5 * 5] += 1
                if "srcclasses" in r:
                    tail_kvs += 1
                    if r.get("kcap"):
                        kcap += 1
                    if r.get("nodecap"):
                        nodecap += 1
                if r.get("conseq"):
                    conseq += 1
                    conseq_counts.append(k)
                if k > PINNED_K:
                    over_pinned.append((k, r.get("srcclasses", -1), turn))
                    src_hist_over[r.get("srcclasses", -1)] += 1
                    by_turn_over[turn // 5 * 5] += 1
                    if "nodes" in r:
                        nodes_over.append(r["nodes"])

    return dict(games=len(games), scoped=scoped, conseq=conseq, tail_kvs=tail_kvs,
                kcap=kcap, nodecap=nodecap, class_hist=class_hist,
                conseq_counts=sorted(conseq_counts), over_pinned=over_pinned,
                src_hist_over=src_hist_over, by_turn=by_turn,
                by_turn_over=by_turn_over, nodes_over=sorted(nodes_over))


def main():
    paths = [p for p in sys.argv[1:] if not p.startswith("-")]
    if not paths:
        print(__doc__)
        sys.exit(1)
    s = read(paths)

    print("payment-class tail-probe read (pre-D4 revisit evidence)")
    print(f"  games                {s['games']}")
    print(f"  scoped windows       {s['scoped']} ({s['scoped']/max(1,s['games']):.1f}/g)")
    print(f"  consequential        {s['conseq']} (rate {pct(s['conseq'], s['scoped']):.4f})")
    print(f"  probe-kv coverage    {s['tail_kvs']}/{s['scoped']}")
    print(f"  PROBE CENSORING      kcap@tailK {s['kcap']} ({pct(s['kcap'], s['scoped']):.4f} of scoped)"
          f" | nodecap {s['nodecap']} ({pct(s['nodecap'], s['scoped']):.4f})")

    hist = s["class_hist"]
    print("\n  true class-count histogram (scoped):")
    for k in sorted(hist):
        print(f"    {k:>3}: {hist[k]}")

    cc = s["conseq_counts"]
    print("\n  consequential-window class-count quantiles:")
    for q in (0.50, 0.75, 0.90, 0.95, 0.99):
        print(f"    p{int(q*100):<3} {quantile(cc, q)}")
    print(f"    max  {cc[-1] if cc else 0}")

    print("\n  coverage: fraction of consequential windows FULLY enumerated at cap K:")
    for k in (8, 12, 16, 24, 32, 48, 64):
        cov = sum(1 for c in cc if c <= k)
        print(f"    K={k:<3} {pct(cov, len(cc)):.4f}")

    over = s["over_pinned"]
    print(f"\n  formerly-censored set (classes > {PINNED_K}): {len(over)} windows")
    if over:
        src = sorted(v for _, v, _ in over if v >= 0)
        cls = sorted(c for c, _, _ in over)
        print(f"    classes    p50 {quantile(cls, .5)}  p90 {quantile(cls, .9)}  max {cls[-1]}")
        print(f"    srcclasses p50 {quantile(src, .5)}  p90 {quantile(src, .9)}  max {src[-1] if src else 0}")
        print(f"    srcclasses histogram: {dict(sorted(s['src_hist_over'].items()))}")
        ratio = sorted(c / v for c, v, _ in over if v and v > 0)
        print(f"    classes-per-srcclass ratio p50 {quantile(ratio, .5):.1f}  p90 {quantile(ratio, .9):.1f}")
        no = s["nodes_over"]
        if no:
            print(f"    DFS nodes on this set: p50 {quantile(no, .5)}  p90 {quantile(no, .9)}  max {no[-1]}")

    print("\n  by-turn: scoped windows / over-pinned share:")
    for t in sorted(s["by_turn"]):
        n = s["by_turn"][t]
        o = s["by_turn_over"].get(t, 0)
        print(f"    t{t:>2}-{t+4:<3} {n:>6}  over-{PINNED_K} {pct(o, n):.3f}")


if __name__ == "__main__":
    main()
