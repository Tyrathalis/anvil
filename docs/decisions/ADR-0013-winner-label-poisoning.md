# ADR-0013: end.winner was wrong for ~50% of games — every value head trained to date learned seat noise; corrected labels lift the same trunk to final-turn AUC 0.99

- **Date:** 2026-07-11
- **Status:** accepted
- **Design-doc anchor:** §4 (value head), §7 (Ante), §6 (training); corrects
  value-head claims in ADR-0006 (stopping-rule exclusion basis), ADR-0008/0009
  (the 0.573 "floor" rows), and m2-rl-plan D4's gate numbers; found during D4
  Ante ledger shakedown.

## Context

The Ante v0 ledger shakedown read a raw seat-0 winrate of 0.967 on 30 pilot
games — statistically impossible — which unraveled into this:

**The obs end-record's `winner` field is derived from the post-elimination
live player list** (`game.getPlayers()` in the AnvilRun end path — the same
reindex class the M1 D1 header fix addressed via registered players; `Obs`
itself indexes seats by `getRegisteredPlayers` throughout, this one spot was
missed). At game end the loser has been eliminated, so the surviving winner
is ~always index 0: measured **{0: 1989, 1: 11} over 2,000 pilot games**, and
identically on d6ext. The field is wrong for whichever seat actually lost —
**~50% of games**.

The harness progress log (`games.jsonl`) always carried the true winner:
verified **492/492** against an independent adjudication from final life
totals / `lost` flags on the pilot. Strength measurements (D8/D3 arms, all
winrates) always read games.jsonl — **unaffected**.

But `dataset.py` built the value head's `won` label from `end.winner`. So:

- **Every value head trained through d2-sa learned seat noise.** Scored
  against TRUE outcomes, the d2-sa value head reads **AUC 0.506 overall and
  0.52 at ≤2 turns from game end — chance**. Against the broken label it
  reads 0.62: it had learned per-matchup *seat priors* (the corpus pair
  schedule fixes deck→seat within a pair), which is also why its broken-label
  BCE (1.16 vs truth, 0.573 vs noise) looked like "signal."
- The whole M1 value-head narrative — the 0.573 "matchup-prior floor," "reads
  own hand early, board reading absent," "final-turn AUC 0.68" — was measured
  against a label that is wrong half the time. The matchup-entropy floor
  *concept* (from games.jsonl 5–0 pair rates) stands; the model's measured
  position against it was fiction.
- Policy/target/X/mulligan labels come from dec/ret records — unaffected.
  The value loss (weight 0.5) fed noise gradients into the trunk throughout;
  nothing to act on, but D7-recipe loss curves for value are meaningless.

## Decision

1. **Fork fix** (`06dd428313`): winner index derived against
   `getRegisteredPlayers`. Verified 24/24 on a fresh smoke run.
2. **Reader-side join, permanent**: `TrajectoryStore.winner_seat(g)` parses
   the true winner from games.jsonl; `dataset.py` and the Ante ledger read
   ONLY that. The existing 113,592-game corpus needs **no regeneration**.
3. **Validator cross-check**: `anvil.store validate` now compares the two
   records per game and warns loudly on mismatch — two records encoding the
   same fact must be compared somewhere; this class ran unnoticed for five
   weeks of corpus because nothing did.
4. **Value re-baseline on corrected labels** (`d4-valuefix`, 38 min,
   value-head-only — trunk and policy frozen, so the RL init is untouched by
   construction): from AUC 0.506 (chance) to, on 600 val games / 354K
   windows: **BCE 0.5495 / AUC 0.788 overall; by turns-from-end: AUC 0.989
   at 0, 0.949 at 1, 0.971 at 2, 0.927 at 3–4, 0.861 at 5–8, 0.70 at 9–16,
   0.55 at 17+; calibration clean and monotone.** The policy-trained trunk
   carried strong outcome signal all along — decided boards read nearly
   perfectly — and only the head's labels were garbage.

## Consequences

- **D4's critic gate numbers are re-based.** "BCE below ~0.60, final-turn
  AUC off 0.68" is retired (both referenced broken-label measurements).
  New baseline the rollout-labeled critic must beat: **d4-valuefix's
  corrected-outcome-label numbers above** — and the value the rollout pilot
  must demonstrate now lives in the mid-game band (turns-from-end 5–16,
  AUC 0.70–0.86), not the saturated final turns. The head-only probe is the
  floor; a full-visibility critic tower and/or unfrozen fine-tune is the
  next cheap rung before rollout labels are priced.
- **Ante corrections gained teeth**: |correction| rose ~30× under the fixed
  head (opener 0.083, draw 0.020 win-prob units), zero-mean holds. The
  mirror certification (batch in flight, 12,800 identical-deck games)
  measures the variance actually removed; per §7 the ledger is unbiased
  under ANY value function, so the apparatus certificate does not depend on
  critic quality — only the effective-sample multiplier does, and it should
  be re-measured whenever the critic improves.
- **ADR-0006's value exclusion from the stopping rule** ("measured not
  data-limited") was decided on invalid evidence; the corpus decision is
  closed and stands, but the premise transfers to the corrected-label world
  only via the new binned diagnosis (early-game AUC 0.55–0.62 = hidden info
  + matchup, exactly where the belief head / rollout labels aim).
- **ADR-0008/0009 value rows** (0.573/0.574 "floor") are label-noise
  artifacts; the numbers of record are d4-valuefix's.
- The d2-sa checkpoint of record is unchanged for policy (agreement numbers
  untouched); for anything value-related, **`d4-valuefix/last.pt` is the
  interim head of record** (same architecture, same policy weights, fixed
  value head) until the D4 critic lands.
- Standing lesson (validator-enforced): when two records encode the same
  fact, a consistency check belongs in the validation gate, not in hope.
