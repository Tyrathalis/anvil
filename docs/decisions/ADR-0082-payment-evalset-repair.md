# ADR-0082: Payment-evalset repair — the "unreachable" positives were an instrument defect (exact-index scoring on multi-arm outcome classes); class scoring adopted, phyrexian retired, the ratesweep set becomes the pre-registered conditional holdout

- **Date:** 2026-08-27
- **Status:** accepted
- **Design-doc anchor:** ADR-0069 consequence 3 (the owed repair, "cheap
  to settle against the certification harness"); ADR-0073 decision 5
  (the empirical inputs); [m10-plan.md](../design/m10-plan.md)
  design-round obligation 4 / [m10-build-spec.md](../design/m10-build-spec.md)
  R5

## Question

ADR-0069 found phyrexian (13) and wide_choice (14, later 17) positives
0-correct at EVERY scored point including day-zero — "unreachable as
constructed. Either the shapes are mis-mined or the head cannot express
their goals." Which is it, and what survives repair?

## Finding (settled offline against the banked certification data)

**Neither. The scorer was unfair.** `payment_drill_score` promised
outcome-equivalence-class scoring in its docstring and checked
`pick == best` exact-index in its code — and the certify read's
`best = max(cleared_pos)` tuple-comparison tiebreaks EQUAL margins by
HIGHEST ARM INDEX, an arbitrary choice no model can infer. Re-applying
the read's own certification predicate per arm over the banked
certouts:

| shape | positives | windows with ≥2 independently-certified arms |
| --- | --- | --- |
| wide_choice | 17 | **11** (many margin-IDENTICAL: 7.5×5 arms, 9.75×3, 3.0×3) |
| phyrexian | 13 | 7 (one 41.5×4) |
| color_hold | 26 | 9 |
| blocker_pressure | 13 | 3 |

A model picking a certified-equivalent arm scored 0. This is the
ADR-0066 rule surfacing a second time: **the unit of exclusivity must
be the unit the consumer consumes** — here the outcome class, not the
arm index. (It also means every historical positive-accuracy series,
including D4's, UNDERCOUNTED — the D4 negative stands regardless: its
0/13 and 0/14 shapes stay near-0 under any scoring given the always-auto
argmax, and the verdict rested on the discrimination statistic, not
these counts.)

## Decision

1. **Positives carry their outcome class** (`cls` = the full
   cleared-positive arm list, the read's predicate re-applied per arm;
   invariant `best ∈ cls` verified on every row). Scoring and training
   both consume the class: `payment_drill_score` counts `pick ∈ cls`;
   ingestion trains class-CE (−log Σ_cls p).
2. **phyrexian's 13 positives RETIRE** (ADR-0073: +0.0pp at game end —
   value-free at both horizons; class scoring cannot rescue a shape
   with no game-end value). The shape's auto-correct rows stand (their
   claim is class-free). Retired rows live in `retired-drills.jsonl`
   with reason, never silently deleted.
3. **`payment-evalset-v2`** = the repaired training evalset: 56
   positives (23 multi-arm) + 224 auto-correct + 13 retired.
4. **`payment-holdout-v1`** = the ADR-0075 ratesweep-certified set
   (19 positives, 9 multi-arm + 123 auto-correct) with the same class
   treatment — **the pre-registered conditional holdout**
   (uniform-drawn, unlike the shape-quota'd evalset; NEVER ingested).
   Fresh observe frames minted on the build-era jar
   (`run-20260827-holdout-observe`, 142/142 windows reproduced, zero
   misses). Day-zero on `m10-sched-init`: positives 0/19, auto-correct
   119/123 = 96.7% — the +2.0-bias calibration point, banked.

## Consequences

- The ADR-0075 label ingestion (`anvil/training/paylabels.py`) trains
  on v2's class labels at the post-boundary revalidation observe
  frames (265/280 joined; misses and option-mismatches counted loudly)
  — the pay head's only training signal under the M10 PG staged mask.
  Day-zero class-CE: positive 3.85, auto 0.31.
- The per-iteration holdout score (`--pay-drill-dir` →
  `run-20260827-holdout-observe`) is the generalization read the
  evalset itself can no longer provide once ingested — the
  train/holdout split is the instrument-conflict fix, recorded here.
- The pre-boundary observe frames (`run-20260821-observe`, obs sv=1)
  are historical; the strict reader gate refuses them by design.
- Standing-rule candidate (added to standing-rules.md): a certified
  "best" on a rolled-out arm set is a CLASS statement — any consumer
  (scorer, labels, gate) that collapses it to one index must show the
  collapse is behavior-neutral.
