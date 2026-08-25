# ADR-0074: D6 R1 aux-target probe — both targets clear their pinned gates decisively; the plan latent's dense supervision is JOINT (action summary + end-of-turn delta)

- **Date:** 2026-08-24
- **Status:** accepted
- **Design-doc anchor:** [m9-d6-plan-latent-spec.md](../design/m9-d6-plan-latent-spec.md)
  §5 (R1 pins, committed pre-data at `12b220c`); [ADR-0073](ADR-0073-m9-ceiling-measurement.md)
  decision 3 (the D6 routing this executes)

## Question

Before any model surgery: from the frozen trunk's representation at the
plan-emission point (the first own-seat window of a turn group), are the
candidate dense aux targets predictable above the obs-arithmetic
baseline (the ADR-0043 reconstruction discipline)? If neither is, the
detached-carry formulation has no premise and the build does not start.

## Instrument

`scripts/plan_probe.py` over `d6-run18-i000/i001` (post-boundary mirror
generation from the grafted init — nearest to ckpt-of-record behavior),
both seats: **20,191 turn-groups** (16,067 train / 4,124 held-out,
deterministic game-grouped split), features = frozen `iter-019` trunk
`[STATE]` / `[PLAN]` outputs at the emission window, ridge fits with a
small alpha grid CV'd on train.

## Result — both gates PASS, with wide margins

| target | metric | base ladder: arith → [STATE] → [STATE]⊕[PLAN] | pin | verdict |
| --- | --- | --- | --- | --- |
| (a) action summary (53 classes) | macro-AUC | 0.7528 → 0.9078 → **0.9235** | ≥ arith+0.03 ∧ ≥0.60 | **PASS** (+0.171) |
| (c) end-of-turn delta (6 axes) | mean Spearman | 0.4462 → 0.5599 → **0.5665** | ≥ arith+0.05 ∧ ≥0.15 | **PASS** (+0.120) |

**Selection (per the pinned rule): JOINT multi-task aux.**

Free finding: the static `[PLAN]` token's readout adds a real increment
over `[STATE]` alone on action prediction (0.9078 → 0.9235) — the
reserved slot already computes non-redundant summary signal with zero
training ever aimed at it.

Recorded noise: one ill-conditioned ridge warning at the smallest alpha
(CV selects larger); no bearing on the read.

## Decision

1. **R1 RESOLVED, positive.** The turn-start representation encodes the
   turn's realized intent far above explicit-feature reconstruction —
   the premise of "distill intent into the latent via dense
   supervision" stands.
2. **The aux loss is multi-task (a)+(c)** per the pinned selection rule.
   Weighting between the two tasks is a build-session detail under the
   standing auto-calibration rules (ADR-0057 instrumentation applies to
   each task share).
3. **D6 proceeds to the build/graft rung** (spec §8 step 2): injection +
   emission head + collate/featurize mirror + day-zero bit-identity
   verification + banked day-zero reliance/aux baselines.

## Consequences

- The forced-seq escalation target stays parked (not needed at this
  rung); the ADR-0058 chartered formulation remains routed as the
  escalation, unchanged.
- Assets: `scripts/plan_probe.py` (turn-group dump + pinned arm-ladder
  probe — reusable as the aux-holdout instrument during training);
  `data/runs/plan-probe-r1/` (20,191-group feature dump + probe read).
- Owed at the build session: aux-task weighting instrumentation; the
  probe-run funding gate + kill-signal numerics (spec §7, pinned at the
  recipe session, pre-launch).
