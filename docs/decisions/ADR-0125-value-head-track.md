# ADR-0125: The value-head track — rollout truth as a stream, the full-vis critic trained on it, the real-vis head distilled from the critic; the fixed bank retired; after the big run

- **Date:** 2026-10-29
- **Status:** proposed (the user's design call, 10-29 evening; deferred by name to the big run's closeout scoping — nothing here changes the recipe of record or the running loop; built as a worktree track with its own reads)
- **Design-doc anchor:** §3e (the value head under the loop), §4 (the asymmetric full-vis critic), §7 (the value function audited against rollouts; the Ante critic), §6 (Grindstone's drill provenance); supersedes [ADR-0124](ADR-0124-anchor-bank-refresh.md) §2–3 (the fixed segment-3 bank and the offline refit), keeps its §4–5; amends [ADR-0119](ADR-0119-value-function-first-before-the-big-run.md) item 4 (the amortized advantage head folds in)

## Context

The big run's value head slid from 0.48 to 0.33 holdout Spearman over 300 iterations while its anchor learned the
8,403-row Build 1 bank by heart ([ADR-0124](ADR-0124-anchor-bank-refresh.md): all-rows ρ 0.84 at `iter-301`). The two
boundary reads that followed said the leaf's ranking is not what caps strength at the 1pp level (rolls 4 −1.23 ± 0.83pp;
the recovery head transplanted +0.82 ± 1.20pp with-lookahead). The labeler re-price put ADR-0124's 40,000-state bank at
≈ 2.5–3.5 box-days (≈ 650 labels per box-hour at K=8 on `iter-301`; 133 worker-seconds per label). V-trace alone lands
near 0.25 on the bank (the 10-04 no-anchor control). The Ante ledger is critic-bound: `d4-critic-fullvis` corr(raw,
ledger) 0.163 and the head itself on omniscient windows 0.197 against a 1.5× bar that needs ≈ 0.58 (the 10-03 re-measure).

**The diagnosis, in one line:** every source of value truth the loop has is either noisy (one outcome per state) or fixed
(a bank), and a fixed bank fails twice — it is memorized within a run and it goes stale as the policy's states move. Both
failures come from the same property. The 10-25 design thread (the running record) already named the structural fix: a
full-vis teacher scored on real games, a real-vis student that regresses onto it after games complete, no randomized
hidden cards. What it lacked was the truth to train and audit the teacher with. **The fork's rollout labeler is that
truth, and it runs on the policy's own states if generation forks its own games.** A fork copies the whole game,
libraries included, so K rollouts from one state share the actual hidden information: their mean is a Monte-Carlo
estimate of the *full-vis* value at that state. The Build 1 bank has always been full-vis truth; a real-vis head
regressing onto it across many states integrates over the hidden-state posterior — the thread's own argument for the
teacher. So the stream and the teacher are one design at two prices: the Monte-Carlo teacher (unbiased, sparse,
expensive) and the learned teacher (dense, cheap, only as good as its calibration).

The pieces exist: the harness's rollout mode (`-rollout K`, `-points M`; turn-stratified fork points; a fork block of
K=8 to the games' ends p50 152 s; fidelity 451 clean / 48 divergence / 1 mismatch per 500 — divergence is label noise
here, not a defect), the bank format and the anchor loader (`bank-state.pt`; `ValueAnchor`), `--anchor-every` and the
memorization meter (ADR-0124 §4), the full-vis window (`featurize --full-vis`, `transform.full_vis`) and the critic
trainer (`finetune_value --full-vis --trainable all`; the loop's per-iteration critic phase, off in the big run).

## Decision

Three layers, built and read in this order, each with a bar before the next starts. Numbers that set bars are fixed at
the track's scoping session, not here; the shapes are.

1. **The truth stream (layer 1 — generation forks its own games).** At a registered fraction of generation games (the
   pre-registered starting point: one in four), one turn-stratified window is forked and K real-vis rollouts are played
   to the end by the serving policy (sampled, so the label is the behavior policy's value; the rollout policy and K are
   recorded per row). Each row carries the state, the K outcomes, and provenance (store, game, window, fork commit,
   checkpoint, era). **The anchor draws from a rolling window of the last W iterations' rows** (ADR-0124 §4's budget
   applies; with a stream the gap meter should read ≈ 0, which becomes its own check), **and a frozen slice per
   segment is the evaluation holdout** — re-based per era, never shared with training. Cost at the starting point:
   ≈ 19 worker-seconds per rollout, so K=4 adds ≈ 76 s per labelled game, ≈ 9% of an iteration's generation for 120
   rows an iteration and ≈ 12,000 a segment (the whole Build 1 bank every nine iterations). Label noise at K=4 is sd
   0.25 per row; the RankNet gate on |Δwr| re-bases to it. **Bars:** (a) the generation forkcheck — a mainline played
   with forks on must trace-hash identical to the same seeds without (the fork's server traffic and RNG get their own
   key space; `noise_seed(game_seed, s)` keys on the decision sequence, so the fork's draws must not advance the
   mainline's), (b) the generation cost at the registered rate ≤ +10% of the loop's iteration wall, (c) the meter's
   gap on the rolling window ≈ 0 while the holdout Spearman on fresh truth holds or rises over a segment-length cell.
2. **The critic (layer 2 — the full-vis teacher trained on the stream).** A critic tower with its own capacity (never
   serves; its policy heads are off-distribution by construction, as `d4-critic-fullvis`'s are) reads the full-vis
   window AND the acting seat's observation (the asymmetric-critic conditioning the 10-25 thread flagged) and trains
   offline on every store of the era: the rollout mean where a row exists (low-variance, full-vis truth), the game
   outcome everywhere (dense, noisy), recency-weighted across policy iterations and blind to the engine version
   (invariant 7). **Bars:** Spearman on the stream's frozen holdout against the serving head's and `d4-critic-fullvis`'s
   on the same rows by a registered margin; corr(raw, ledger) on the Ante arms — the ADR-0119 1.5× bar (≈ 0.58) is the
   long target, the first bar is a registered gain over 0.197.
3. **The student (layer 3 — the real-vis head regresses onto the critic).** After games complete, the value head trains
   on the critic's scores at every recorded window (dense targets; no mid-game leak by construction), replacing or
   mixing with V-trace's outcome targets as a paired arm decides; the trunk stays the policy gradient's (stop-grad, the
   rung-2 recipe). **The stream stays the audit (invariant 4):** the head's per-iteration Spearman on fresh rollout
   truth, the ADR-0124 meter and pause line unchanged. **Bars:** the student's holdout Spearman on fresh truth above the
   teacher-free head's by a registered margin; network-alone identical by construction (the head does not act), the
   with-lookahead paired read within its flag; then **the search-budget re-read** (rolls 2 → 4 and the deeper leaf
   modes) on the new leaf — the door a better leaf reopens, closed since the 10-29 rolls-4 read.

**Exclusions carried from the 10-25 thread:** the full-vis object evaluates states and supplies baselines; it never
chooses an action in a trajectory the policy learns from (rollouts are real-vis play; distilling an argmax over rollout
Q is the existing search's shape and allowed). No randomized hidden cards anywhere: the real game's hidden state is one
draw from the true posterior and carries the opponents' tells. Belief sampling stays the search's problem, separable.

## Consequences

- **ADR-0124 §2–3 are RETIRED unbuilt** (the fixed 40,000-state bank and the offline refit on it): three box-days for a
  snapshot that is memorizable and stale within the run, capped at ≈ 0.75 by K=8 label noise, when the stream delivers
  the same truth continuously. **§4–5 stand** and serve the big run's remaining segments in *hold mode*: the recovery
  head transplanted onto the running checkpoint (the user leans to it; +0.82 ± 1.20pp with-lookahead, network-alone
  identical), `--anchor-every` sized to ≤ 0.25 pass of the Build 1 bank, the meter and the pause line on; the
  pre-registered expectation is a Spearman that holds near 0.41, not one that rises — a drift toward 0.35 with the gap
  near zero means the draw budget's hold is too weak (the next arm is the frequency / weight trade at the same pass
  budget, a different question from memorization). The ADR-0123 floor and the ADR-0118 line stay on the old holdout
  until the stream's holdout exists.
- **The big run's remaining segments are not where value-head growth happens** — the transplant read put a better leaf's
  worth under 1pp at the precision we can afford, and the segments are policy-gradient-driven. The track opens at the
  run's closeout scoping (the candidate center of the next milestone, as the 10-25 thread proposed), or at a segment
  boundary only if layer 1 turns out cheap enough to build and forkcheck beside the run.
- **ADR-0119 item 4 (the amortized advantage head) folds into layer 3** (the critic's scores as the baseline); the Ante
  1.5× bar becomes layer 2's long bar. Grindstone gains a free instrument: rows with high rollout variance are the
  decision-sensitive states, provenance-traced to a real game by construction.
- **Routed by name to the scoping session:** the generation fork's determinism design (its own noise-key space; quiet
  with respect to the mainline's mu bookkeeping and the server's step counts); the fork-fidelity residual read as label
  noise (48 / 500 divergence); the critic's observation conditioning; the recency weighting across eras; the rolling
  window's W and the per-segment holdout's size; the teacher-versus-V-trace mixing arm; the rollout policy (sampled vs
  argmax) as a recorded choice with one paired read.
- No standing rule yet: nothing here is measured. The rule candidate ("value truth is a stream the loop generates, never
  a fixed set") is written when layer 1 clears its bars.
