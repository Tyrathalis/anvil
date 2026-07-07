# ADR-0006: 500K corpus — default-on staged generation with a pre-registered stopping rule

- **Date:** 2026-07-06
- **Status:** accepted
- **Design-doc anchor:** m1-bc-plan.md D6 (amends the go/no-go framing); §15 corpus rows

## Context

D6 was framed as a commitment decision: D5 learning curves "price the 500K,"
then the ~33-night generation run gets a go/no-go. Two things changed that
framing:

1. **The cost structure measured this week is asymmetric.** Generation runs at
   ~1,508 g/h in the background of desktop use (measured, D3 pilot) and is
   interruptible without waste: deterministic config, chunk/manifest resume,
   mergeable by seed range, fork commit frozen per run.json. Training runs are
   21 minutes (20K steps) to ~2 h (a full 29M-window epoch). Data is a slow
   background commodity; training iterations are the scarce, attention-bound
   resource. A generation run stopped at 100K games is a 100K corpus, not a
   failed 500K.
2. **The full-epoch run (pilot-run4) split the heads into data-limited and
   not.** Policy/target/X gained enormously from fresh data at fixed
   architecture (nonpass 0.708 → 0.837, X 0.41 → 0.67); the value head gained
   nothing (BCE 0.578 → 0.575). More data demonstrably buys policy quality;
   it demonstrably does not buy value quality at this architecture/label
   design (see devlog 2026-07-06 session 5 for the full diagnosis).

## Decision

- **Generation is default-on, not go/no-go.** The 500K run launches as soon as
  the fork hardening lands (runaway-frame guard, hard-cap frame close —
  the ~1-in-50K corrupt-frame class measured in the pilot), nights/nice-19,
  standard chunk discipline, fork commit frozen across all chunks.
- **Pre-registered stopping rule** (written before the curves, so the decision
  isn't made on vibes at 300K): at each learning-curve checkpoint — matched
  full-epoch-equivalent compute per arm, evaluated on the 600-batch final eval
  (nonpass SE ~0.33%) — **if doubling the corpus improves val nonpass
  agreement by less than 2× its standard error AND the rare-label heads
  (X, optional-cost) have also stopped improving, generation stops** and the
  corpus is whatever it is.
- **Value BCE is excluded from the stopping rule.** Measured: not data-limited.
  Value-head quality is pursued on the M2 path instead (rollout-labeled
  targets — first workload for the fixed fork API), not by corpus size.

## Consequences

- No idle-lever regret: games accumulate while the D5 matrix runs; the
  stopping rule caps the spend at measured-diminishing-returns.
- The learning-curve arms in the D5 matrix become the stopping rule's
  instrument, not a one-shot pricing exercise; they re-run as the corpus
  grows (runs are cheap — a full epoch is ~2 h).
- §15's corpus-size planning assumption (~500K) becomes an upper bound with
  an empirical exit, not a target.
- Fork hardening is the only gate in front of launch; it stays small and
  fork-side (no Anvil-side dependencies).
