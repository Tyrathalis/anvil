# ADR-0050: M6 closeout — the representation question answered; the bottleneck is one layer up

- **Date:** 2026-08-10
- **Status:** accepted (user-approved milestone close, this session)
- **Design-doc anchor:** §1/§2 (representation), §4 (value heads), §6 (training)
- **Inputs:** [ADR-0038](ADR-0038-m6-opening-sequence.md) (charter) through
  [ADR-0049](ADR-0049-flat-cycle-audit.md) (the audit that names the layer);
  [m6-plan.md](../design/m6-plan.md).

## The charter, answered

M6 asked: **can we change what the gradient sees, and does that reopen
improvement?** The answer is measured and two-part:

1. **The representation is partially gradient-reachable but was never the
   binding constraint.** The elimination chain: not arithmetic (ADR-0043 —
   `[STATE]` already encodes the derived features, median R² 0.65), not
   card function (ADR-0045), not hidden information (ADR-0047 — full-vis
   buys zero ranking), not label count at the measured slope (ADR-0046,
   ~+0.006/doubling). Partial unfreeze IS reachable (ADR-0044/0046:
   0.4528 → 0.4829, the only lever past the frozen ceiling) — but the
   graduated build consuming it (rank-critic-c2v3, the best curation ever
   measured, the a2-winning composition) produced a TIE at the strength
   gate (ADR-0048: 0.5199 ± 0.0110 vs 0.5316, no promotion).
2. **The audit named the real bottleneck: learning-signal density**
   (ADR-0049). The §6c penalty is the loop's only dense per-decision
   signal; terminal outcomes at 20+ turns cannot shape timing among
   behaviors the policy already explores. Twenty iterations trained
   measurable cast-suppression (16.9% of iter-019's casts changed, 46%
   cast→pass) while hold-then-cast sat abundant and unreinforced.

**Ckpt of record: unchanged — `d6-run11/iter-019` at 0.5316 ± 0.0110.**
M6 promoted no checkpoint; what it bought is the diagnosis and the assets
below.

## Done-when resolution

- **Headline gate (0.5316 combined paired):** exercised honestly twice
  (run13 TIE); the gate survives into M7 (subject to the D3 re-baseline).
- **The deciding probe chain:** D1 frozen probe (ADR-0039) → re-price
  (ADR-0040) → extended curve / path verdict (ADR-0041) → D2-B session
  (ADR-0042) → B-1/B-2 (ADR-0043/0044) → campaign (ADR-0046) → build +
  cycle 3 (ADR-0048) → audit (ADR-0049). Every step probe-gated; five
  clean nulls at one gate with improving instruments became the
  diagnostic itself (ADR-0049's standing lesson).

## Assets and standing rules carried out of M6

- **`rank-critic-c2v3`** (holdout 0.4833) + era-scoped isotonic map —
  curation/selection instrument of record; NOT a serve policy; its ΔV
  outside loss-adjacent populations is extrapolation.
- **`labelset-c2-v3`** (8,683 train / 1,197 frozen holdout) + the frozen
  `frozen-probe-ext2-c2` benchmark + holdout-freeze protocol
  (`label_merge.py`).
- **Standing instrument rules:** probe on `[STATE]`, never the trained
  head (ADR-0039); inner-val pool pinning; checkpoints sweep the two
  leading Ns; engineered aggregates get clips at birth; drill-mode
  labeling is the cheap population (27.3 pos/h/worker, ADR-0040).
- **Fork-index namespace fix landed** (fork `a73ee9d4e4`,
  FORK_G_BASE = 1e12, smoke-proven: g=0 mainline + fork stores join
  cleanly): the run13-crash landmine is closed; era-scoped — never mix
  pre/post-base stores in one MultiStore join.
- **Signal-path audit rule** (ADR-0049): when a gate goes flat with
  improving instruments, audit what gradient reaches which decisions
  before funding the next lever at any other layer.

## Handoff to M7

[m7-plan.md](../design/m7-plan.md), opened same session, user pins
recorded there: P0 probe gate pre-registered (RMS true Δwr ≥ 0.10 over
≥30% of split-able fork points + directional hold-then-cast check);
fork stability pass + re-baseline lands after P0 clears, before the
first M7 training run. Deferred unchanged: pool expansion, iteration
pipelining, eval thinning, B-3 encoder work, belief head for ranking.
