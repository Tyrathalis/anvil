# ADR-0014: Ante mirror certification passes — ledger unbiased, fitted-β corrected winrate converges strictly faster than raw; variance reduction is critic-bound (~0.6% today)

- **Date:** 2026-07-12
- **Status:** accepted
- **Design-doc anchor:** §7 (Ante certification test), §13 (places it in M2);
  m2-rl-plan D4 (first half); ADR-0012 addendum (moved it to D4's front);
  ADR-0013 (the label fix the shakedown produced, and the `d4-valuefix`
  critic this certification ran under).

## Context

§7's certification test: identical-deck mirror batch — the ledger sums to
zero in expectation, and AIVAT-corrected winrate converges to the known 50%
faster than raw. Batch: `ante-mirror-20260711-222944`, 8 pool decks × 1,600
identical-deck heuristic games = 12,800 (12,793 decisive, 7 crashes, ~21 h
wall at w=16 nice-19), obs+census on, post-label-fix jar. Ledger: v0 classes
(openers, provably-uniform draws, play/draw die), counterfactual values from
`d4-valuefix` (ADR-0013's corrected-label value head), 96 min GPU for 156K
corrected nodes across 12.8K games.

## What the run found, in order

1. **The mirror sanity holds:** raw seat-0 winrate 0.4953 ± 0.0044.
2. **The draw class is zero-mean at scale:** n=124,297 corrected draws,
   node mean −3.2e-05 ± 9.6e-05 (t=−0.33).
3. **The opener class exposed a modeling error — and the ledger's own
   zero-mean test caught it** (the apparatus audits itself): openers read
   t=+2.72, and splitting by deal index localized the bias entirely to
   mulligan re-deals (deal #0: t=+0.52 clean; deal #1: +0.0076/node,
   t=+5.46). Engine archaeology explains it: Forge's London mulligan tucks
   BEFORE the keep decision (`mulliganDraw()` draws 7 then immediately asks
   `tuckCardsViaMulligan`), so a re-deal keep window shows a
   **choice-filtered best-k-of-7, not a chance outcome**. v1.1 excludes
   re-deal keeps from the opener class (6,572 of 31,840 nodes); the correct
   anchor for them — the tuck dec's pre-choice obs — is queued with the
   critic upgrade.
4. **Convergence needs the fitted control-variate coefficient at current
   critic quality.** At β=1 (pure AIVAT), corrections ADD variance (ratio
   1.074): each correction is zero-mean but noisy, and with
   corr(raw, ledger) = 0.08 the noise term dominates. The optimal-shrinkage
   estimator (split-half β̂ ≈ 0.21, out-of-sample per game) gives
   **var ratio 0.9936, bootstrap CI90 [0.991, 0.996] — strictly < 1**.

## Decision

**The certification passes, stated precisely:** the apparatus is unbiased
(every corrected class zero-mean within noise after the v1.1 re-deal fix),
and the **fitted-β corrected winrate converges to 50% strictly faster than
raw**. The fitted-β estimator is the deployment form of the ledger until the
critic improves — β̂ converges to 1 as corr(raw, ledger) grows, so it
subsumes pure AIVAT rather than replacing it. Records:
`data/runs/ante-cert-20260712.json` (v0 full run),
`ante-cert-20260712-v11.json` (v1.1 aggregation, the certificate),
`ante-cert-20260712.json.ledger.jsonl` (per-game ledger; `certify
--from-ledger` re-aggregates it under any future estimator without GPU).

## Consequences

- **Effect-size honesty: today's variance reduction is ~0.6%** (effective
  samples ×1.006). The binding constraint is critic quality exactly as §7
  says ("critic quality sets only variance removed"): ρ = corr(raw, ledger)
  = 0.08 caps reduction at ρ² ≈ 0.65%, and the ledger currently corrects
  only openers + 31% of draws (poison-rule skips) + die. §7's "3–4×
  effective samples" needs the omniscient critic and fuller chance-node
  coverage — re-run `certify --from-ledger` is cheap, re-running values
  against a better critic is 96 min; both are standing post-critic steps.
- **The ±2.5pp arms are not sharpened yet.** ADR-0012's hope that the
  certified arm immediately sharpens checkpoint evals does not cash out at
  ρ=0.08 — it cashes out when the D4 critic lands. The certified apparatus
  + the D4 critic are one deliverable pair; neither is useful alone.
- The self-audit property is demonstrated, not just claimed: the ledger's
  zero-mean test found its own modeling error (re-deal choice contamination)
  at 12.8K-game resolution. That is the §7 design working as intended.
- Draw-class game-sum t=1.95 (node-level clean, ~7 t-stats computed —
  look-elsewhere-unremarkable): watch item for the next certification pass,
  not a finding.
- Next per m2-rl-plan D4: small model-mirror through the same ledger
  (distribution check), then the critic pilot (rollout labels vs the
  d4-valuefix baseline, mid-game band per ADR-0013).
