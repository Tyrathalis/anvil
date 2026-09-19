# ADR-0113: M12 Build 4½ pre-work — the loop wiring (the search as the behavior policy inside the training loop)

- **Date:** 2026-09-18
- **Status:** accepted
- **Design-doc anchor:** §3d′ (the search directive as the behavior policy) / §6 (the loop); m12-plan Build order 4½; ADR-0112 item 5

## Context

ADR-0112 found that the loop did not run the search: `selfplay.py` passed no search flags and
`rl.py` had no term for the search's rows or its behavior distribution, while the shakedown and
the big run both assume "the same loop settings" with the search on. The review this morning
(the b4post act arm's rows, the server's behavior record, the fork's controller) turned that
finding into four facts the wiring had to honour:

1. **An acted mainline window writes two records.** The natural ask over the full option list
   gets a behavior (mu) record for the policy's own sample and a `ret` as if realized — the pick
   was computed, never played. The forced single-option re-ask that plays the search's pick
   writes a second dec (`by: "search"`) and a second mu record with the pass logit masked at
   serve. The pre-wiring loader would train the first as a played decision and fail the mu
   tripwire on the second: a searched store was not merely unused, it was mislabeled on the acted
   windows (2,512 act + 488 acted-pass + 37 act_void of 36,396 rows on one act arm seat).
2. **The search row carries what the record needs**: the acted option, its behavior
   log-probability and the full distribution over the row's options, the natural line, the
   margin, the applied class, and on the alloc arm the head's probability and selection reason.
3. **V-trace alone barely learns from the search's picks**: on an acted window the behavior
   probability is near one while the policy's may be a few percent, so the clipped ratio scales
   that window's gradient down by the same factor — correct, and the reason the plan carries a
   distillation term.
4. **The store did not carry the rows**: ingest keyed label rows by a fork-point field the search
   rows lack, so they were dropped.

## Decision

Six decisions, each the review's recommendation (user, 09-18):

1. **The acted-window record = MERGE.** One training window per decision: the natural dec's full
   option set with the choice rewritten to the acted candidate, the choice's behavior probability
   = the search's mass on that candidate (the row's `p` summed over the wire options the
   featurizer collapses onto it), the plan factors (targets, X) and their log-probs from the forced
   ask's record; the forced dec and the natural ask's re-ask chain are dropped. An acted pass
   joins the class with candidate 0. An act_void window played the natural line, so its behavior
   probability is the mass on the natural plus the mass on the voided pick. A natural window that
   carries `p` (the rule fired and sampled the natural) takes the search's mass on the natural.
   Un-searched and below-the-bar windows keep their recorded mu (the acting rule plays the current
   policy there). A window whose record cannot be built (no forced record, no mass, entity rows
   that differ) is DROPPED, never trained under a wrong mu; an acted window with no row (an
   orphaned forced dec) is dropped with its chain. The join lives in the RL loader
   (`anvil.training.search_join` + `rl.game_trajectories`), keyed by the game's seed and
   (t, ph, seat) + the row's option count + its labels, restricted to the search's own candidate
   windows (quiescent MAIN1/MAIN2, the seat active — read from the dec's obs) and anchored on the
   forced dec for acted rows; it reports its census every log window and aborts the phase below a
   99% match rate.
2. **The distillation dose = the pick-distillation CE on the acted windows only** (their label IS
   the search's realized pick after the merge — realized through the model's own CastPlan, so the
   ADR-0111 over-generalization class is excluded by construction), share-calibrated per
   iteration like the plan and schedule terms (`--distill-frac`, default 0.05; a settings-pass
   axis). No value-head distillation toward the leaf (the leaf is the value head's own output).
3. **The allocation head in the loop = a BCE term on every searched window** with the label
   margin ≥ the acting bar, trained with the trunk (`--alloc-frac`, default 0.02); the floor's
   windows keep the skipped region covered. **Tau is re-derived each iteration on the searched
   windows weighted to the population** (a floor window stands for 1 / floor rejected windows —
   see the addendum: the floor's windows alone are not an unbiased sample) under the trained
   head at the recall target (0.90) and written into the checkpoint's `alloc_fit` record — the
   server's serve condition — with the AUC on the sample and the weighted recall the previous tau
   would have had; too few positives keeps the previous record. The driver reads the serving ckpt's tau
   into `-searchalloc` on every generation launch.
4. **The guards on a searched store**: the KL guard, the KL abort and the mu tripwire measure
   un-acted windows only (on acted windows the policy and the behavior differ by design); the
   acted windows' fraction, mean ratio and KL are their own series; forced-ask vetoes are counted
   apart and act_void windows get no rejected-intent penalty (the executor rejected the search's
   pick, not the policy's intent — route (b)'s territory).
5. **The loop's recipe**: `--search-recipe` (verbatim AnvilRun flags) + the allocation flags from
   the serving ckpt's record, labels on, searched on both seats in mirror games and the bridged
   seat against the heuristic, the fleet at one server per twelve workers, `--jar` pinning one jar
   for the run; run11's other settings verbatim until the settings pass. A **with-lookahead arm**
   beside the argmax arm in the mid-run paired read (the network-alone vs with-lookahead gap, the
   plateau-together tripline; `--arms-lookahead on`).
6. **Validation** = the two-iteration smoke (`loopwire-smoke`, 96 games per iteration at 24 × 2
   under the recipe with the head): the join's census, the acted-window classes, the tripwire on
   un-acted windows, the two terms' calibration, the tau re-derivation, the next iteration
   carrying the new tau, the lookahead arm. Numbers in the addendum below.

Built: `anvil/training/search_join.py` (pure), the loader + learner in `rl.py` (`--search`,
`--search-bar`, `--distill-frac/-w`, `--alloc-frac/-w`, `--alloc-recall`, `--alloc-floor`,
`--search-join-min`; `search_join.json` beside the ckpt), the store (`search.jsonl` at ingest,
`search_rows_for_game`, `anvil.store search-rows` to backfill), the driver (`--search-recipe`,
`--search-alloc`, `--search-floor`, `--search-bar`, the term fracs + carry + share guards,
`--arms-lookahead`, `--jar`; the monitor row's `search` block). Tests: `test_search_join.py`
(12), `test_selfplay_search.py` (4). The join on the b4-tgtlab pool: 20,304 rows matched 100%,
1,511/1,511 acted rows paired with their forced dec on identical entity rows.

## Consequences

- The loop's behavior policy is the search from here: a searched store trains its acted windows
  under the search's distribution, and a store without search rows under `--search` aborts the
  phase (no silent fallback to the policy's record).
- The shakedown's arms run through `selfplay.py` unchanged in shape (the recipe string is the arm;
  the equal-box-time split sets games per arm).
- Standing rules born here (added to standing-rules.md in this commit): the acted-window record;
  drift guards read un-acted windows; the allocation tau is re-derived per cycle on the unbiased
  sample.
- Routed by name: the distillation dose and the alloc share as settings-pass axes (Build 4½);
  route (b) (ADR-0111: the target decoder co-distilled on realized plans) next; the payment head's
  loop term (ADR-0105 addenda: PG on outcomes over payment windows) rides the shakedown's settings
  pass; the deep round's rows (`deep` block) are not yet a loader term (the shape arm's labels for
  fork L).

## Addendum 09-18 evening — two pre-existing breaks the smoke exposed, and the fixes

The first smoke (`loopwire-smoke`) voided every acted pick and served a third of the allocation
asks "unserved"; the second (`loopwire-smoke2`) joined 100% and trained, but the mu tripwire
dropped six trajectories. Neither was the wiring. Both were the SAMPLED serve path, which had not
run since Build 3 landed (every M12 read served greedy):

1. **The fleet batcher applied noise all-or-none from its first slot** (09-14). A sampled server's
   queue now mixes sampled mainline asks with greedy ones — the search copies, the value and
   allocation wire, the tuck and surface tags. A greedy first slot ran the batch greedy (no
   `logp_*` for the sampled asks → `KeyError('logp_choice')` → decline → the forced ask voided);
   a sampled first slot padded over a None (the value / alloc asks declined → unserved). Plus
   `make_noise` raised on the tasks added since M2 (`mull_tuck`, the surfaces). **Fixed:** one
   forward per noise group; tasks without a sampled head are served greedy with no mu record
   (`sampling.sampled_tasks`); model errors print a traceback the first three times per tag.
2. **The loop launched without `--sched` never reconstructed the M10 schedule carry the server
   injects.** Every M12 build descends from the M10 graft and carries `sched_*` params; the server
   activates the carry on their presence (advisory, binding off) and injects the slot tokens on
   every window; the loader rebuilt the windows without them (zero-vector tokens still renormalize
   attention) → 2.3% of priority windows recomputed > 0.2 nats off, 0/4,096 with `sched=True`.
   Found by elimination: the acted-window classes, the wire history, the ability table, the
   representation paths, padding and the model paths were each excluded by a direct test (the
   served observation dumped and re-featurized; act() vs forward() on the same tensors; the
   backend replayed in-process). **Fixed:** the driver probes the serving ckpt and passes the
   carry-only flags (`--sched --sched-frac 0 --sched-lr 0 --sched-proj-lr 0`: no aux term, the
   surface's params frozen, no PG pay mask; `--sched-carry auto|on|off`).
3. Along the way, **the wire history's host rule**: the engine back-fills a single-entity answer's
   host (a bare dict in the store — the served entity surfaces), which both `store_wire_hist` and
   the encoder's `history_tokens` read as −1 (5.9% of priority windows rebuilt with a different
   history). Mirrored on `Obs.retHostId`; the parity test's two Python paths agree.

Also from the smoke's read: the floor's windows are NOT an unbiased sample of all candidate
windows (the floor draws only among head-rejected windows, so the previous tau's recall read 0 on
them by construction) → the tau derivation and its recall are weighted, a floor window standing
for 1 / floor rejected windows; and the `act_void` / sampled-natural classes carry the search's mu
without being acted, so the tripwire and KL masks read `search_mu`, the distillation reads `acted`.

Standing rule (added): the trainer reconstructs every carry the server activates for the serving
checkpoint; the loop's trainer flags derive from the checkpoint, never from the launcher's memory
of the recipe.

## Addendum 09-18 17:05 — the smoke (`loopwire-smoke3`) reads clean

Two iterations × 96 games at 24 × 2 under the recipe with the head, arms at 24 games per seat
with the lookahead arm, calibration at 10 steps (the smoke's dose; the loop's default is 50).
Iteration 0: generation 1,183 s (both seats searched in the mirror half), train 40 s; **the join
2,690 / 2,690 rows matched (100%)** — 376 act + 47 acted-pass merged, 7 act_void, 2,260 natural,
377 anchored on their forced dec, 3 chain decs dropped; **tripwire 0**, KL on un-acted windows
0.00014; acted windows 0.96% of the trajectory with mean ratio 0.061 and KL 7.2 (the policy's
own probability of the search's pick is ≈ e⁻⁷: the search acts where the policy would not);
w_distill and w_alloc calibrated and applied at shares 0.046 / 0.020 (targets 0.05 / 0.02);
**tau re-derived 0.369 → 0.217** at weighted recall 0.90 over 2,690 searched windows (430
positives; the previous tau's weighted recall under the trained head 0.69; AUC 0.65 on the loop's
sampled play vs the offline fit's 0.80 on greedy play — a population, not a regression, to watch
at the shakedown), searched-window share 0.61; **iteration 1 launched with `-searchalloc
0.21734`** (the record round-trips through the checkpoint). The arms: 48 games each, 0 crashes,
28 wins both (a trend instrument at this n); the lookahead arm's veto rate 12.4% vs 5.4% on the
argmax arm = the searched arms' banked 14% class (ADR-0112). One informational anomaly flag
(the masked value head's v0 vs the shaped reward, the no-critic smoke's expected basis mismatch);
no guard fired. The server: 0 model errors, 0 fallbacks over both iterations.
Iteration 1 (under `-searchalloc 0.21734`): generation 1,893 s, train 53 s; the join 3,754 / 3,754
(376 act + 65 pass merged, 13 act_void, 11 chain decs dropped), tripwire 0, no anomaly flag, no
guard; the terms at shares 0.054 / 0.016; **tau 0.217 → 0.068 at weighted recall 0.90** (454
positives; AUC 0.69; the searched-window share 0.61 → 0.56, stable — the head's output scale
moves under its BCE while the population it must cover does not, which is exactly why the
threshold is re-derived per cycle and never fixed). The wiring is closed on this smoke.

