# ADR-0046: Label campaign resolved — N=4 at 0.4829; capacity follows labels; the graduated build proceeds

- **Date:** 2026-08-08
- **Status:** accepted
- **Design-doc anchor:** §4 (value heads)
- **Inputs:** [ADR-0044](ADR-0044-b2-unfreeze-probe-verdict.md) (the
  campaign's charter: rising curve ⇒ buy labels, build at the N the
  expanded sweep picks), `scripts/tranche_c2.py` +
  `data/runs/tranche-c2-20260808/` (campaign of record),
  `data/runs/labelset-c2-v3/` (the merged label set),
  `data/runs/unfreeze-probe-v2/` (the deciding sweep).

## Campaign facts

12.6h wall (est. 13–14). p1 = 1,650 labels (five offset arms on the
tranche-B map, pre-spend holdout filter 437→331 games); p2 = 1,600 fresh
games → 411 raw-curated train-only losses → crash map + seven offset
arms = 2,601 labels. Merge freeze-proven (holdout 1,598 rows
byte-identical, 0 guard refusals — the plan-time filter held). Final c2
set: **8,683 train / 1,197 holdout rows** (`labelset-c2-v3`,
+4,244 train vs ext2). Zero stall alerts; one crash-tax rate consistent
with ADR-0040. Two mid-campaign instrument findings en route (below).

## The deciding sweep (3 seeds/N, lr 3e-5, frozen holdout, base-pinned inner-val)

| N | mean holdout Spearman | vs 3.6K |
|---|---|---|
| 0 (head only) | 0.4693 ± 0.0018 | 0.4528 |
| 1 | 0.4538 | 0.459 |
| 2 | 0.4691 ± 0.0022 | **0.4769** |
| 4 | **0.4829 ± 0.0010** | 0.4672 |

1. **The "frozen ceiling" was itself sample-limited:** head-only rose
   0.4528 → 0.4693 on 2.4× labels — the 0.455 plateau was a joint
   property of representation AND label count, not representation alone.
2. **Capacity follows labels, cleanly:** N=2's 3.6K advantage fully
   converged into the head-only baseline at 8.7K; N=4 (overfit at 3.6K)
   is now the uncontested winner, every seed above every other cell.
3. **Best-N curve: 0.4769 @3.6K → 0.4829 @8.7K** — rising, decelerating
   (~+0.006/label-doubling at ~1–2 days of box time per doubling).

## Decisions

1. **The graduated build proceeds at N=4** (per ADR-0044's
   pre-registration: the sweep picks). Discipline unchanged: value-tower
   / partial-layer protection for the shared policy trunk, era-scoped
   assets, mini-run validation, the standing 2,000-game combined paired
   read vs **0.5316** as the only promotion gate.
2. **No further label buying now:** ~+0.006 per doubling prices label
   expansion below the graduated build and below the queued
   full-vis-vs-masked probe (the hidden-info axis is unpriced; label
   scaling is now priced and modest). The campaign machinery is standing
   and restartable if a future N-sweep says otherwise.
3. **Instrument lessons, recorded as standing rules:**
   - *Early-stop pool pinning* (two-round ck1 lesson): inner-val
     eligibility = base-population games with NO extension labels; a
     game gaining extension labels moves wholly to train (row-level
     mixing breaks game-grouping; game-level base-filtering alone is a
     no-op when extensions land on existing games).
   - *Checkpoints must sweep capacity:* ck2 read "flat" because it ran
     N=2 only — the truth was "N=2 saturated, N=4 emerging." Any future
     mid-campaign probe checkpoint runs the two leading Ns.
4. **Next after the build (unchanged queue):** the full-vis-vs-masked
   unfreeze probe prices hidden-information headroom (needs a small
   harness tweak: assemble full-vis windows over the policy ckpt);
   ADR-0045's elimination chain makes it the leading candidate for the
   residual 0.48→0.9 gap.
