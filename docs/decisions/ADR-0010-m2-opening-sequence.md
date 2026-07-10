# ADR-0010: M2 opening sequence — SA-level action schema before RL

- **Date:** 2026-07-10
- **Status:** accepted (amends the entry-point ordering in ADR-0009)
- **Design-doc anchor:** §3 (action decomposition), §6 phase 2 (RL); ADR-0009

## Context

ADR-0009 listed M2 entry points with SA-level candidates after value/RL work,
based on the corpus-side measurement that same-kind host ambiguity touched
13.6% of expert actions. The D8 arms measured the play-time reality: the
executor's order rung (scan-order guessing among same-shape SAs on the chosen
host) handled **31% of casts at δ=0 and 36% at δ=+2.169** — ~2.5× the
corpus-side estimate, because battlefield permanents with multiple activated
abilities are offered every window and the agent activates far more often
than the expert-action census weighted. This is plausibly the largest single
winrate leak in the 46.8% D8 number, and it is fixable with machinery RL
needs regardless (an RL agent must know which action it took).

Also folded in from the M1 retrospective: rollout value labels can now use
the BC agent itself (~1,000 g/h, near-parity) rather than the heuristic —
on-policy targets for the policy being improved; and D9 combat constructs'
"front of M2 if M1 runs long" framing expired when M1 closed early — combat
is fully heuristic at play with labels already in the corpus, so it gets an
explicit slot rather than falling off by default.

## Decision

M2 opens in this order:

1. **Fork-API hardening** (unchanged, first under every ordering — rollout
   prerequisite and the flagship upstream contribution; `forkcheck` is the
   regression gate).
2. **SA-level action schema + BC retrain.** Candidates become (host entity,
   SA-descriptor) pairs at the action interface; the entity/state
   representation is untouched (cards stay single entities — Tutor-relevant
   identity preserved). Labels: current corpus resolves ~69% of multi-SA
   cases via the sa-string join (ambiguous cases mask out of the SA-level
   loss); every run since 2026-07-10 carries exact `oi` labels. Rider: fix
   the loader's nested-window history skew (parent rets joined from the
   future) in the same retrain. Recipe is known (3 epochs, ~14h).
3. **Re-run the winrate arms** (~12 min each) to price the schema change
   before anything else moves.
4. **Rollout-labeled value targets under the BC policy** (amended from
   heuristic rollouts).
5. **RL fine-tune** from the SA-level checkpoint (V-trace, §6 phase 2;
   start action-rich, δ=0).

**Combat constructs (D9)** are sequenced after step 2 and before/alongside
step 5 as evidence suggests — no play-time telemetry yet says combat is the
bottleneck the way the order rung's 31–36% did, so it queues behind the
measured leak but stays on the list explicitly.

## Consequences

- Avoids retraining twice: the RL init checkpoint already speaks the action
  space RL needs, and the winrate delta from step 3 cleanly attributes the
  schema change before RL confounds it.
- Mode heads and allocation heads stay behind SA-level candidates (measured
  mass 1.2% / 0.03% of casts); the modal/divided executor approximations
  stay interim until then.
- The M2 plan doc (M2's first deliverable, per the M1 pattern) absorbs this
  ordering; this ADR is its seed.
