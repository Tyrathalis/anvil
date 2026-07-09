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
  isn't made on vibes at 300K): at each learning-curve checkpoint — **matched
  compute = fixed step count (113K steps, one 50K-corpus epoch) per arm
  regardless of corpus size** (smaller arms repeat epochs; this folds the
  epochs-vs-fresh-data question into the same runs), evaluated on the
  600-batch final eval (nonpass SE ~0.33%) — **if doubling the corpus improves
  val nonpass agreement by less than 2× its standard error AND the rare-label
  heads (X, optional-cost) have also stopped improving, generation stops** and
  the corpus is whatever it is.
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
- **Pair-space saturation tempers expectations:** the pool is 113 decks
  (~12.6K ordered pairs) and the 50K pilot already touches most of them —
  marginal games buy within-matchup draw/personality diversity, not new
  matchups, and matchups are measurably lopsided (21.4% of pairs 5–0). The
  first doubling (100K) is the informative checkpoint; an early stop is a
  plausible outcome, not a failure. If the rule fires early, the corpus-growth
  levers shift to **pool expansion or new decklists within the existing pool**
  — noted, not near-term.
- Generation (16 CPU workers, nice 19) and training runs will share CPU;
  run4 needed only 8 loader workers, so coexistence should be fine — if
  training throughput visibly drops, pause generation during GPU runs (the
  chunk mechanism makes this free) rather than debugging contention.

## Resolution (2026-07-08)

**The rule fired at the first (100K) checkpoint; generation stopped at 63,576
extension games (~113.6K total corpus, ~23% of the 500K ceiling, ~42 h of
background generation).** Both clauses, measured on fixed bases at
pre-registered power:

- **Nonpass clause:** 50K→100K doubling = **−0.61pp** nonpass on the pilot-val
  600-batch basis (0.8746 → 0.8685; threshold was +0.7pp). Honest and value
  flat to the fourth digit. Full curve (10K/25K/50K/100K, 113K steps each):
  0.8548 / 0.8695 / 0.8746 / 0.8685 — saturated by ~50K games.
- **Rare-label clause:** X accuracy on the fixed 672-window basis:
  0.573 / 0.637 / 0.674 / **0.647** — the 10K→50K climb (+10pp) stopped;
  doubling X *diversity* (~63K unique casts) at matched compute bought
  nothing. X's remaining headroom is a drills/architecture question, not a
  corpus-scale question (consistent with the §6 drill-economics premise).

Residual ambiguity, honestly noted: at matched compute the 100K arm makes
only ~0.58 passes over its data; a repetition-vs-diversity control (2 epochs
of 50K, 226K steps) remains queued as a *training-recipe* question for D7 —
it cannot reopen the corpus decision, which this rule closes.

D6 is complete at ~113.6K games. The run is paused, not deleted: `resume`
continues the same deterministic stream if a future milestone (M2 value
labels, drill seeding) wants more uniform games — but the D7 gate trains on
the corpus as it stands.
