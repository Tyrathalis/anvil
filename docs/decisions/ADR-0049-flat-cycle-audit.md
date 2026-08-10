# ADR-0049: The flat-cycle audit — bottleneck named: learning-signal density (the §6c penalty is the only dense signal in the loop)

- **Date:** 2026-08-09
- **Status:** accepted (findings; next-step decision with the user)
- **Design-doc anchor:** §6 (training), §4 (value targets), §3a (planning)
- **Inputs:** [ADR-0048](ADR-0048-cycle3-resolution.md) (charter),
  run13 telemetry (`monitor.jsonl`), the behavioral-delta and
  interaction-holding probes (scratch scripts; numbers below are of
  record), the two-week elimination chain (ADR-0043→0047).

## The three reads

1. **Veto/§6c telemetry (existing data).** Veto rate oscillates in a
   limit cycle with entropy (troughs 0.09/0.13 at ent≈0.127; peaks
   0.20–0.29 at ent≈0.16+), never converging. Rejected-intent count runs
   3.8–8.3/trajectory: at λ=0.02 that is **0.08–0.17 shaped reward per
   trajectory — 15–30% of a win's magnitude, spent continuously on
   punishing attempted casts.** kl_mu triples across the run (0.006 →
   0.03; guard 0.06 never trips): the policy moves plenty.
2. **Behavioral delta (run13-final vs iter-019, 14.6K shared
   multi-candidate priority windows).** Agreement 95.9% overall but
   pass-dominated; **on windows where iter-019 CASTS, run13 changes the
   decision 16.9% of the time — 46% of those changes are cast→pass.**
   KL heavy-tailed (median 0.0001, p90 0.089): most positions identical,
   a minority substantially reshaped. Twenty iterations of training =
   measurable cast-suppression.
3. **Interaction-holding corpus probe (the bait-them-out question).**
   Comparative reads (raw hold-rates ~0.78 everywhere are dominated by
   target availability — caveat recorded): hold-then-cast behavior is
   ABUNDANT in exploration (~50% of affordable-interaction instances;
   model 0.53 vs heuristic 0.43) and **flat across run13's 20 iterations
   (0.51 → 0.47 → 0.49)** — the behavior exists; no credit reaches its
   timing.

## The verdict

**The bottleneck is learning-signal density, not representation, not
exploration, not curation.** The loop's only dense per-decision signal
is the §6c penalty (suppressive by construction); the outcome label at
20+ turns is too sparse/noisy to differentiate timing-quality among
explored behaviors. Every cycle therefore converges to
penalty-avoidance-plus-noise. This one mechanism explains the full
anomaly set: strength flat across five instrument-grade improvements;
run13's coin −9.1 (suppression hurts contested positions) with lost
+5.6 (passing is safe when behind); the M5 one-shot verdict (curation
composition shifts the training distribution once — it never adds
signal); and the critic's irrelevance to strength (V-trace baseline =
variance reduction on an already-sparse signal; the critic is not in
the per-decision reward path).

## What it points at (options for the user, ranked by the evidence)

1. **Dense decision-level value signal in the training path** — the
   design's own parked §4 lever: short-horizon rollout deltas as value
   targets at drilled decisions, task-token flagged; and/or the
   rank-critic's calibrated per-turn ΔV as advantage shaping
   (rollout-audited per the standing invariant). This is the direct
   antidote to the named bottleneck and the audit's primary
   recommendation.
2. **§6c economy re-tune** — λ decay or veto-conditional scheduling; the
   penalty solved veto (run5) but is now the loudest voice in the
   gradient. Cheap, likely necessary, insufficient alone (removing the
   suppressor does not add the missing signal).
3. **Tier-3 search** — remains the strategic consumer of a
   ranking-capable critic, and search-derived targets are the mature
   form of (1); but (1) is buildable now on parked machinery without
   the search substrate.

## Standing lesson

The falsification record's shape mattered: five clean nulls at one gate
with improving instruments was itself the diagnostic — the audit found
the layer in a day of existing-data reads. Corollary for future flat
stretches: audit the SIGNAL PATH (what gradient reaches which
decisions) before the next lever at any other layer.
