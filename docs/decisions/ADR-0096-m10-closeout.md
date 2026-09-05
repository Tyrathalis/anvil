# ADR-0096: M10 closeout — the generative planner route is NEGATIVE at the hierarchy level; the root constraint is named; the scorer flywheel is the next charter

- **Date:** 2026-09-05
- **Status:** PROPOSED — awaiting user acceptance (the user agreed on 09-05 to close M10 with an
  ADR after the two diagnostics; this is that ADR). On acceptance: move the M10 Status bullet to
  the archive, add the standing rules below to standing-rules.md, run the kill list.
- **Design-doc anchor:** m10-plan.md (doc of record), m10-reset-draft.md §C–§K, ADR-0094,
  ADR-0095; anvil-design-v2 §3/§6 (the scheduling competency, the drill economy)

## Context

M10 chartered the unified resource-scheduling competency (2026-08-25). The ceiling funded it:
an oracle picking the best of 16 within-turn schedule arms under binding execution is worth
+13.5pp/game (ADR-0078). Six probes (ADR-0085→0093) failed to consume that value through an
advisory surface; the reset (ADR-0094) restated M10 as a planner hierarchy with BINDING
execution, a reward-trained planner anchored by distillation, inline certification as the
label source, and a stratified paired strength read as the primary gate, with a pre-registered
mid-point rule: a day-zero read below minus the bar halts for adjudication.

## What was measured (2026-09-03 → 09-05)

1. **Day-zero reads (ADR-0095 + addenda).** A planner distilled from the executor's own realized
   lines (first-cast agreement 92% on the hand basis) bound at serve costs **−2.33 ± 0.70pp**
   against the same checkpoint advisory (release rule, 559 windows; previous reads −1.1, −1.8;
   monotone in how much binds). Cleaner execution of the same plans (the 09-04 WAIT refinements,
   the `quiescent_main` fix) did not move it. **HALT by the mid-point rule.** The user adjudicated
   option 1: better labels before any training.
2. **Inline certifier built and run (draft §K).** Harvest h1: 806 certified points → 799
   full-support labels, 159 certified improvements (20%, the mint's band), ~2.4 h per 480-game
   batch at 5%. The labels are content changes, not reorderings (47% disjoint card sets, 0%
   pure reorders).
3. **Learning curves.** Exact-arm head on 702 certified + 2,766 natural windows (mint + harvest):
   certified holdout exact **0.000 at 25/50/100% of the data**, first-slot 0.11 → 0.15. A
   frozen-trunk arm SCORER (MLP or linear, 11K window-arm pairs): within-window Spearman
   **0.06–0.11, flat with N**, against a label reliability of 0.66.
4. **Label reliability.** Split-half Spearman of the arm ranking 0.50 (K=8 → 0.66; K=32 →
   0.89); test-retest on fresh rolls: 27/40 certified windows re-certify (18 the same arm),
   17/20 natural stay natural. Every enumerated arm family averages BELOW the natural line; a
   family prior has no ranking power (0.06).
5. **Pivotality.** From the frozen trunk's state read-out alone, "does this window have an arm
   ≥ θ" reads **AUC 0.64 → 0.69 rising with data** (top-decile precision 0.60–0.67 vs base
   0.37). Learnable where the arm ranking is not.
6. **Instruments proven.** The paired read (CRN pairing, SE 0.7pp at K=8/N=600), the driver's
   HALT path, the certifier end to end, the harvest driver, the retest, the jar-identity proof
   (forkcheck 498/500 identical vs the 08-21 boundary run; the 2 mismatches launch-unstable on
   one jar). Replay exactness of a SAMPLED mainline is bounded by micro-batch logit jitter
   (~20% of games flip a pick somewhere) — any replay-based instrument must budget it.

## Decision

**M10 closes with a NEGATIVE answer at the hierarchy level for the generative planner route,
and a named root constraint.** The search's improvements over the executor are REAL
(reliability 0.66 at the pinned budget; +13.5pp under an oracle) but SPARSE (one window in
five), STATE-SPECIFIC (no family prior), and INVISIBLE to the executor's own representation at
any data volume a harvest or probe produces. A planner that clones the executor cannot
interpolate to them (0% exact at 4× data); a scorer on the frozen trunk cannot rank them
(0.08 vs 0.66); binding either costs the commitment tax (−2pp). Probe7 as specified is NOT run:
every read predicts its HALT. The checkpoint of record stays `d6-run11/iter-019`.

**Retired:** the generative planner (pointer decoder over slots) as the acting object; binding
rules 1–4 and the WAIT machinery; planner PG + KL twin and the loader's schedule action (never
built); the follow term; further hand-basis refinements. Plans survive as one option TYPE.

**Carried as assets:** the inline certifier (Java `-certify`, `anvil.certify`, `certify.py`,
finish, harvest driver) — generalizable to any decision tag; the paired strength read with its
fixed population; the hand-basis featurizer and ability table (option content encoding); the
harvest pool (799 labels, 806 spreads) + mint (2,669) as era-zero data; the retest and scorer
probes; the driver's serve-regime flags, heartbeat and paired-read wiring.

**Routing (the next milestone's charter, drafted with the user 09-05):** the OPTION SCORER —
one head scoring presented options at any decision window (cast, tutor target, trigger order,
combat damage, payment class; a schedule arm is an option whose content is a sequence), trained
on per-option Δ spreads from a certifier generalized by decision tag; **pivotality-aimed
certification** (the scorer's margin/spread as the certify weight) as the flywheel's seed;
**critic lookahead** (copy, apply one option, evaluate) as the cheap search, with a reliability
read against rollout labels before adoption; margin-gated acting replaces binding; deployment =
the network, lookahead only where pivotal and only server-side. Pre-pinned: the option-content
encoding shared by all surfaces; the per-option label format on the store row; stack abilities
visible to the model (§J item 10) before any mid-resolution surface. **Parallel candidate for
a strength number that moves:** cash the proven payment competency (+2.96pp, ADR-0075).

## Standing rules born here (to standing-rules.md on acceptance)

- **Measure a learning target's label reliability (split-half / test-retest) before building a
  head on it, and read the head's learning curve before scaling data or compute** — the scorer
  and exact-arm curves cost an hour and answered what two build sessions could not.
- **A distilled clone of the executor cannot learn where the executor is wrong from the
  executor's own features**; search-adjudicated labels need a representation trained on them
  (the density argument of ADR-0050, in its sharpest form).
- **Replay parity of a sampled mainline is bounded by serving jitter (~20% of games)**; replay
  instruments pair within-run (CRN) and budget cross-run divergence, never assume it.

## Kill list (delete on sign-off; kept unconditionally: harvest stores + labels + spreads,
## the paired-read runs of record, ckpts of record)

| dir | size | why |
|---|---|---|
| `data/training/m10-planner-distill-hand/windows.pt` | 2.3 GB | superseded corpus (hand2 rebuilt it) |
| `data/training/m10-planner-distill-hand3/windows.pt` | 2.3 GB | the not-learnable distill; ckpt retired |
| `data/training/m10-planner-distill-curve/{windows.pt,frac-*}` | 2.8 GB | learning-curve scratch; numbers in the ADR |
| `data/runs/sched-harvest-h1-b0[012]-*/workers/*/obs.zst` etc. | ~2.7 GB | raw worker output; the ingested stores (20 MB each) carry the games |
| `data/runs/sched-retest-rt1/*.scratch.*` | ~350 MB | replay scratch; `retest-read.json` carries the result |
| `data/runs/sched-harvest-h1-b03-*` | 5 MB | partial batch, never ingested |
| `data/runs/sched-harvest-smoke1*`, `data/trajectories/sched-harvest-smoke1-*` | 28 MB | smoke |
Keep: `m10-planner-distill-hand2/last.pt` (the graft of record for any re-read), the paired-read
run dirs (1.9 GB each; the read of record — trim `lanes-*/*.scratch.*` if space matters).

## Consequences

- The design doc's scheduling competency (§3) stays funded by the ceiling but its ROUTE changes:
  from a planner that emits plans to a scorer that evaluates options, with search amortized at
  training time. m10-plan.md is superseded by this ADR + the next charter.
- The drill economy (Grindstone, §6) gains its selection signal: pivotality is learnable and
  improves with data — the first grounded, learnable "where does the choice matter" since M6/M8
  tied on value-change ordering.
- Budget honesty: two build sessions + three read days produced a negative and a diagnosis; the
  diagnosis (root constraint + pivotality) is the deliverable that the six advisory probes did
  not reach.
