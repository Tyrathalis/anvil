# M10 v2 aux-target probe — pre-registration spec (RESOLVED 2026-08-26: E PASS, R PASS, F FAIL — [ADR-0079](../decisions/ADR-0079-v2-target-probe.md))

*Design-round obligation 2 ([m10-plan.md](m10-plan.md)), the ADR-0074
pattern run inside the design round so the target is co-designed with
the actuation surface. Instrument = `scripts/plan_probe.py` extended
(the R1 asset, reused per its ADR). Status: DRAFTED 2026-08-26 for
adjudication; gates + leans pinned at the launch commit pre-data, per
the R1/ratesweep discipline. This session's scope is the OFFLINE probe
only — the kill/FUND/unmask numerics ride the training-probe launch
session, not this one.*

## Question

From the frozen `d6-run11/iter-019` trunk's representation at the
turn-group emission window (first own-seat window of a turn), are the
three adjudicated v2 aux targets predictable above the obs-arithmetic
baseline (ADR-0043 reconstruction discipline)? Per-target verdict:

- **PASS** ⇒ the head ships as adjudicated (BOTH resource components +
  feasibility, joint multi-task, R1 selection discipline).
- **FAIL** ⇒ the named fallback below — a design-round event, recorded
  in the closeout ADR, never silently rerouted.

## Instrument (common)

- **Features:** frozen iter-019 trunk `[STATE]` / `[PLAN]` outputs at
  the emission window (plan_probe dump machinery, boundary-bundle
  engine, obs sv=2). **Emission window = the fork-consistent MAIN1
  rule for all three targets** (first MAIN1 own-priority
  `chooseSpellAbilityToPlay` dec with obs — the sweep's fork window
  and the actuation surface's plan-emission point; refines the draft's
  looser "first own dec" wording, recorded pre-data). Off-turn own
  groups drop out under this rule by construction (they have no MAIN1
  own window) — the probe reads the own-turn scheduling surface, per
  the census terrain. Ladder per R1: obs-arith → `[STATE]` →
  `[STATE]⊕[PLAN]`. Ridge fits, alpha grid CV'd on train,
  deterministic game-grouped split (~80/20).
- **Populations:**
  - Targets E + R: `m9-rebaselinearm` s0+s1 (1,999 games, ~22.2k own
    turn-groups, census cost/affordability conventions) — **LEAN**;
    alternative = the `m10-ceiling-census-20260825-212414` store
    (identical era, ~5.3k own groups — 4× less power, but the same
    store as Target F).
  - Target F: the sweep universe — sampled turns from
    `m10-ceiling-census-20260825-212414` (frame.json keys), arms
    reconstructed deterministically (`build_arms` + sched_pins rng
    20520825), outcomes joined from `lanes-h2/*.out.jsonl`
    (96,456 rows → per-(turn, arm) aggregation across rolls).

## Target E — end-of-turn resource summary (the selection/hold half)

The (c) genre extension. Per own-turn group, axes at end of turn from
the EOT obs:

1. untapped source count (total),
2. untapped-by-color capability counts,
3. untapped chained (Signet-class) source count,
4. floating mana — **unavailable at obs sv=2** (no mana-pool field);
   recorded as unavailable, never fabricated. If the build wants an
   EOT floating read it arrives with the build's engine-side
   telemetry, not this probe.

**EOT view:** the last own obs-bearing decision of the turn (phase
recorded; turns where that is the emission window itself are kept —
single-window turns are real distribution).

**Metric:** mean Spearman over non-degenerate axes.
**Gate (GATE_C verbatim):** `[STATE]⊕[PLAN]` ≥ arith + 0.05 ∧ ≥ 0.15.
**Degenerate-axis rule:** an axis with held-out variance ~0 or <50
distinct-value support is excluded from the mean and reported
separately (the MIN_SUPPORT discipline).

## Target R — running affordability along realized sequences (the ledger half)

Per (own-turn group, slot k) row over the turn's realized schedulable
actions (census window framing). Labels from the veto-knowability v2
machinery (`source_views` + `can_pay`) evaluated on the slot-k window
obs — the obs already reflects prior casts' taps, so the running
ledger is read, not simulated:

1. afford-bit of the executed action at its window — structurally
   unsupported in this probe: the ingested decision stream records
   accepted actions only (vetoed attempts live in the census sidecar,
   not the store), so negatives cannot reach the ≥50 support floor;
   recorded as unsupported, never gated. The validity predicate's
   negative mass lives in Target F,
2. remaining untapped source count after slot k,
3. remaining affordable-hand count after slot k (how many castable
   cards in hand `can_pay` clears at the post-slot view).

**Features add slot index k to the arith rung** — mana declines
monotonically in k, and the gate must read the state-specific
increment, not the slot counter (adversarial-shape fix, recorded
below).
**Metric:** mean Spearman over axes 2–3 (+AUC on 1 if supported).
**Gate:** `[STATE]⊕[PLAN]` ≥ arith(+k) + 0.05 ∧ ≥ 0.15.

## Target F — schedule feasibility / degrade-point from state (the realization-validity surface)

Row = (sampled turn, joint arm); the 96k forced executions are the
label mint. Rolls are stochastic replicates of the same (state, arm) —
aggregated, never per-roll rows (8× duplication would leak the split
and the target is knowable-from-state feasibility):

1. **realize-rate** — fraction of rolls with `degraded_at == -1`
   (binary AUC at the fully-realized-on-majority threshold; rate kept
   as regression read),
2. **normalized first-degrade slot** — median `degraded_at / sched_n`
   among degraded rolls (Spearman, degraded-arm stratum),
3. degrade class (`absent` vs `veto` vs void) — exploratory,
   never gated.

**Features:** trunk ⊕ **arm-arith encoding** (sched_n, total/generic
cost, per-color pips, instant-speed count, hold-set size,
includes-land) — and the arm encoding joins EVERY rung of the ladder,
so the gate reads the trunk's increment over obs-arith⊕arm-arith, not
the arm's self-description.
**Gate:** realize AUC ≥ (arith⊕arm) + 0.03 ∧ ≥ 0.60; degrade-slot
Spearman ≥ (arith⊕arm) + 0.05 ∧ ≥ 0.15. Conjunction rule to
adjudicate: LEAN = realize-AUC is the gate, degrade-slot is a
report-only second read (the head's validity-predicate role needs the
binary; slot position is refinement).

## Adversarial shape review (obligation 5 — the target's shape is a behavioral prior)

- **E:** "predict own EOT untapped" is satisfiable by always-hold
  (maximally predictable). As a PREDICTION target the aux never
  rewards the behavior directly, but the emission head can drift
  toward predictable schedules — this is exactly the FUND degeneracy
  veto's territory (utilization floor / pure-hold rate vs ~6.5% base);
  the coverage is recorded here as the E-specific reading of that
  veto.
- **R:** trivial-solution path via slot index — closed by adding k to
  the arith rung (above).
- **F:** labels were produced under degrade-to-auto-and-count arm
  semantics; the head learns "feasible under push-through," not under
  halt-and-replan. Recorded as a semantics caveat tied to the open
  fork-5(ii) (replan-at-veto vs push-through training semantics); if
  that fork lands on halt-replan, the feasibility labels remain valid
  as a lower-bound validity read (a degrade under push-through is a
  fortiori a plan break under halt).

## Fail paths (pre-registered)

- **E fails:** the selection/hold half has no dense emission-point
  support — hold signal folds into F's arm encoding (hold-set size
  already present); the EOT summary head is dropped from the birth
  build; design-round event.
- **R fails:** the running ledger is not linearly decodable at
  emission — the per-slot head moves its read point to the slot
  windows (execution-time features) rather than the emission window;
  the validity predicate stands on F; design-round event.
- **F fails:** feasibility is not predictable from state+arm — the
  invalid-schedule penalty's knowability gate falls back to the
  veto-knowability splitter alone, and the aux roster drops to E+R;
  design-round event + penalty-design revisit.

## Budget

CPU-scale: two store dumps + ridge fits; no rollouts, no GPU beyond
the frozen-trunk forward passes (ValueEvaluator, minutes). No
quiet-box requirement (no calibrated win-rate read). Runs same-day on
adjudication.

## Adjudication record (user, 2026-08-26 — all four on the recorded leans)

1. **E/R population: `m9-rebaselinearm` s0+s1** (power over
   single-store convenience; same era/ckpt, census conventions).
2. **Target R gates on the running-ledger regression axes**
   (remaining-untapped + remaining-affordable-hand, Spearman);
   afford-bit reported, gated only at ≥50 negative support — the
   validity predicate's negative mass lives in Target F.
3. **Target F gates on realize-AUC alone**; degrade-slot Spearman is
   a report-only refinement read.
4. **Gate numerics verbatim from ADR-0074** (AUC ≥ base+0.03 ∧ ≥0.60;
   Spearman ≥ base+0.05 ∧ ≥0.15 — F's base includes the arm
   encoding at every rung).
