# ADR-0128: the M13 upstream merge (engine `97535e047f` → `2d8fef80a0`): one merge commit, the count budget, one crash fix and one restored surface inside the boundary

- **Date:** 2026-11-18
- **Status:** accepted (the user, 11-18: the merge's shape is ADR-0127's pin; the crash fix "before closing this boundary, whether it gets merged upstream or not"; the copy-target hook is not yet ruled on, see item 5)
- **Design-doc anchor:** §9 (fork discipline; engine upgrades as dataset boundaries); [m13-plan.md](../design/m13-plan.md) Build 0, step 1; [m13-upstream-merge-scoping.md](../design/m13-upstream-merge-scoping.md)

## Context

M13 opens with an upstream merge as its dataset boundary ([ADR-0127](ADR-0127-m13-charter.md)). The user pinned its shape: one commit after a tag, landed alone, with the Monte Carlo count budget on the merged jar. The scoping read upstream at `0f82b4f469` and predicted seven textual conflicts and a larger semantic risk in six files that merge cleanly.

Upstream had moved 21 commits by the time of the merge. The merged tip is `2d8fef80a0` (2026-11-18 UTC): 1,361 commits past the 09-16 merge base, 138 of them in `forge-ai`, 6,663 files.

## Decision

1. **A merge, as one commit after a tag** ([ADR-0110](ADR-0110-m12-upstream-merge-20260916.md)'s rule). Tag `pre-merge-20261118` = `94229a0c8a`. The merge commit is `c3fa2fae0b` on the fork's `master`.
2. **The seven conflicts were the scoped seven.**
   - `MyRandom.java`, `CardMockTestCase.java`, `MyRandomThreadLocalTest.java`: upstream's form of PR #11285 taken whole. Our delta in these files is now zero.
   - `AiBlockController.java`: upstream's structure with the fork's block-legality cache kept. Two additions: upstream's new `completeRequiredBlocks` resets the cache on entry, and its `removeIllegalBlocks` removes through the helper that invalidates the cache.
   - `AiController.removeUnpayableAttackers`: upstream's two-argument form, kept public. `CombatRealizer` passes the bridged player.
   - `GameCopier.java`: upstream's command-zone effect-source loop, its Planechase planes and `copyLeftThisTurn`, followed by the fork's zone-independent effect-source loop. The fork's loop is a superset of upstream's and never writes a null.
   - `SimulateMatch.deckFromCommandLineParameter`: upstream's three-argument form, package-visible, with a two-argument overload for `AnvilRun`, `CensusRun` and `ForkFidelityCheck`.
3. **The count budget rides as its own commit**, `f3d0048edb`: a clean cherry-pick of `d0e50c61c7` (`FLAT_MC_COUNT_BUDGET`, default false). Upstream's 15 commits after the patch's base add no clock use that it misses. The upstream branch stays unpushed.
4. **One crash fix is inside the boundary**, `1d4048fa2f` (the user, 11-18). `ComputerUtilAbility.paysOffFor`, new upstream code (#12809, 11-12), passed a cast trigger's comma-separated `ValidCard` to the single-restriction `isValid`. A list with properties threw inside the AI's candidate evaluation; a plain list never matched. The fix splits the list. It changes games, so it lands before the baseline and before any read, as the plan's rule for a crash fix says. No upstream issue or PR exists for it as of 11-18.
5. **The target surface is restored on a spell copy's new targets**, `9074a909c1`. Upstream #11977 picks a copy's new targets inside `PlayerControllerAi.chooseNewTargetsForCopy` and no longer calls `chooseTargetsFor`, the callback the surface was served on. A no-op hook, `preparedCopy`, is called after upstream's method; `CensusPlayerController` offers each targeting node under the `chooseTargetsFor` name, with the AI's picks as the natural line. It acts only on a bridged or directed seat. This was the session's call, made under the user's standing default (keep a model capability unless it is dramatically weaker) and because a serve-path change after the era bridge would be a second boundary for served games. The user has not ruled on it; dropping it is a revert of one commit before the bridge.
6. **Five fork tests moved to the merged engine's behaviour** (`9159271002`, test-only). Each pinned a heuristic blind spot that upstream closed: the Signet-chain payment (#12149) and the commander tax on a modal card's back face (#12283). The fork's 25 test classes pass, 114 of 114 with the two new classes.
7. **The boundary's forkcheck baseline is `run-20261118-mergefix-baseline`**, on the fixed jar, Monte Carlo off, the standing seed set 20260703+500. `compare.py`'s default baseline moves to it. Every later tip is proven against it. The jar that serves runs is `data/runs/merge-20261118/forge-merge-20261118-copytgt.jar`.

## What the forkcheck read

Identity with the old jar was not expected. It was read for crashes, for the copier's fidelity, and for whether the new baseline reproduces.

| Run | Jar | Clean | Divergent | Outcome mismatch | Mainline crash | Hashes identical to |
|---|---|---|---|---|---|---|
| `run-20260916-merge-baseline` (the old era) | `1db054ade4` | 451 | 48 | 1 | 0 | — |
| `run-20261118-merge-baseline` | the merge + the count budget (`f3d0048edb`) | 424 | 56 | 1 | 19 | the old era: 2 of 500 |
| `run-20261118-merge-repeat` | the same jar | 424 | 56 | 1 | 19 | the pass above: 500 of 500 |
| `run-20261118-mergefix-baseline` | + the fix (`1d4048fa2f`) | 439 | 60 | 1 | 0 | the unfixed merge: 386 of 500 |
| `run-20261118-mergefix-repeat` | the same jar | 439 | 60 | 1 | 0 | the pass above: 500 of 500 |
| `run-20261118-copytgt-baseline` | + the copy-target hook (`9074a909c1`) | 439 | 60 | 1 | 0 | the fixed baseline: 500 of 500 |

- **The unfixed merge crashed 19 of 500 mainline games, all on the one bug.** The forkcheck's precon pair holds Melek, Izzet Paragon, whose trigger text has the throwing shape. The same exception also aborted about 280 AI decisions in games that finished. No other exception class appears in the log, and no copier crash.
- **With the fix no game crashes, and the fix changes 114 of the 500 games on this pair.** The log holds no exception from the game path and no AI deadline fired.
- **The copier's fidelity is unchanged within noise.** 60 of 500 games diverge after the fork (12.0%) against 48 of 500 on the old copier (9.6%). The difference is 2.4pp with a standard error near 2.0pp. Upstream's `copyLeftThisTurn` and Planechase additions did not break a copy.
- **The merged jar reproduces.** Two passes on the same jar and seeds gave identical hashes on all 500 games, for the unfixed jar and for the fixed one, on a near-idle box.
- **Two of 500 games match the old era's hash.** The heuristic's play has changed almost everywhere, as the scoping expected. The standing launch-unstable seed 20260969 played clean and identically in both passes.

## What the served smoke read

200 games of `big-run/iter-405` against the heuristic on the fixed jar (`merge-smoke`, 24 workers, seed base 20261118, which is not the era bridge's). It was read for crashes and for the bridged seat's callbacks per game against the 11-07 confirm's arms on the old jar. Its win rate is not a read.

- **No game crashed, and every served surface but one was reached at a comparable rate.** Attacks, blocks, the zone-change choice, the trigger targets, the orders, the modes, the entity sets, the mulligan and the tuck all sit within a third of their old rate per game.
- **`chooseTargetsFor` was gone:** 1.18 calls and 0.57 bridged answers per game on the old jar, none in 200 games. The cause is item 5 above.
- **The old rate was one card's loop.** 72% of the old jar's `chooseTargetsFor` windows were copies of Chain of Smog and another 20% copies of one counterspell; the rest come to about 0.04 per game.
- **With the hook the callback fires again.** A second 200-game smoke on the jar that carries it (`merge-smoke2`, the same seeds) had three copy windows, all three offered to the bridge and answered, and no crash. 200 games held no Chain of Smog loop, so the smoke confirms the path and not the rate.
- **Three census rows moved a great deal without touching a served surface.** `playChosenSpellAbility` doubled (32 to 69 per game), `playTrigger` fell to a fifth (5.2 to 0.9) and `chooseManaFromPool` rose from 0.3 to 5.4. They follow upstream's restructured play and payment paths.

## What else the boundary changes

- **The heuristic pays Signet chains and filter lands.** The payment surface's forced window (a plan the auto-payer cannot build) was built on that blind spot. On the merged engine a window is consequential on a real choice far more often than on a forced one. The served `pay` head will be asked at a different mix of windows.
- **The phantom back-face cast from the command zone is fixed upstream** (#12283). The 57-case option-mask class of ADR-0122's 10-05 addendum loses its largest shape.
- **162 of the pool's 5,149 ability keys changed, across 150 cards** (`data/runs/merge-20261118/abilities-f3d0048edb.jsonl` against the pool's dump; 15 keys at the 09-16 merge). 167 pool card scripts changed upstream. A served option whose key is outside the table is keyed on its host row and kind alone (ADR-0110, addendum 09-16), so the served build degrades on those abilities until the table is extended.
- **The AI's deadline is wall-clock and it can fire in a harness game.** Four deadlines fired in the unfixed jar's first pass, in combat prediction and block assignment, and none in the fixed jar's passes. `Game.AI_TIMEOUT` is 5 seconds and no harness changes it. Every repeat still matched. Under 24 workers the deadline will bind more often, and a deadline that binds changes the game.
- **Upstream now ships six AI profiles.** `Hard.ai`, `Hardest.ai` and `Reckless.ai` are new; the harness's draw of four is unchanged (plan pin 5).
- **The bug's reach in our pool is two cards.** 37 card scripts have the throwing shape and none is in the pool. Sram, Senior Edificer and Ral, Monsoon Mage have the silent shape: unfixed, the heuristic never ordered them before the spell they pay off for.

## Consequences

- **The fork pin moves to `9074a909c1`** (pushed to `Tyrathalis/forge` with the tag). Its proof is `run-20261118-copytgt-baseline`: 500 of 500 hashes identical to the boundary's baseline, fidelity 439 / 60 / 1. The lineage has the era's rows.
- **The checkpoint rows of the state table do not move.** Their numbers are the old era's, on the old jar. The era bridge (Build 0, step 2) gives the new era's, and nothing is compared across the merge until it has run.
- **Before the era bridge (Build 0, step 2):** the ability table is extended with the 162 new keys and the pool dump re-pinned, so the bridge does not confound the heuristic's change with unknown keys. The bridge's kill condition (3pp) reads a served build; this is the hook-side cause it would otherwise have to rule out.
- **Routed by name:**
  - *The AI deadline in harness games.* Read whether it binds under generation load (count the "AI eval thread at timeout" lines in a 24-worker cell) before the arms; if it does, the harness raises `Game.AI_TIMEOUT` for its games. Routed to Build 0's Monte Carlo read (step 3), which already measures wall cost per game under load.
  - *The payment surface's ask mix on the merged engine.* Read from the era bridge's census (`pay` asks per game against the 11-07 confirm's); a retrain of the `pay` head is decided there. Routed to Build 0, step 2.
  - *The upstream PR for the fix.* Branch `cast-payoff-validcard-list` in `../forge-upstream` (`b9abe24ad1`, one commit on `2d8fef80a0`, unpushed). The engine slot is held by #12180; the user's call on opening it beside that PR as a crash fix ([upstream-worklist.md](../design/upstream-worklist.md), Tier 0.11).
  - *The stale `2.0.15` jars in `../forge/forge-gui-desktop/target/`.* The harness picks the newest jar, so they are harmless today; they go at the next stale-data pass.
- **The playable fork's merge and the copier's four-player failures are untouched** (the scoping's "not yet looked at"; Build 0, step 6).
- No standing rule is born here. ADR-0110's rule (a merge after a tag) and the plan's rule (a crash fix that changes a game belongs in the merge's boundary) were applied.

## Addendum 11-18, evening: three copier fixes, the copy-target hook ruled in, the crash fix opened upstream

- **The copy-target hook stays** (the user, 11-18). Decision item 5 is ruled on.
- **The copier's divergence is halved: 467 clean and 33 divergent of 500, against 439 / 60 / 1.** The user asked for a quick look at the divergence classes for fixes worth taking at this boundary. Every mainline hash is unchanged (`run-20261118-copier-baseline`, 500 of 500 against the era's baseline), 28 games became clean and none became divergent. The pin moves to `09133a7ad4`; the serving jar is `data/runs/merge-20261118/forge-merge-20261118-copier.jar`.
- **The instrument** (`1faef2f33c`): a divergent game's forkcheck notes now carry the first game-log entry after the fork point where the copy and the mainline differ. The turn digests say where a divergence shows; this says which play made it. The 61 divergent seeds rerun with it gave identical hashes.
- **The three fixes** (`09133a7ad4`, `GameCopier` only, one test each in `CopierStateTest`):
  - *An effect card's replacement effects and triggers.* A copy kept only the static abilities, so the commander effect lost "put it into the command zone instead" (CR 903.9b). A commander bounced or shuffled away inside a copy went to the hand or library. This was the first difference in 17 of the 61 games. It applies to every search copy and rollout in Commander, and to emblems and spell-made effects.
  - *The turn a card entered its zone.* `Zone.add` stamps the current turn, so in a copy every card had entered this turn (Oran-Rief, the Vastwood; any `ThisTurnEntered` check).
  - *What exiled a card, and the cards a permanent has exiled* (upstream's `TODO ExiledWith`). Hideaway had nothing to play in a copy (Mosswort Bridge).
- **They change copies only.** A game that makes no copy is unchanged, which the forkcheck's mainline hashes show. A searched game does change, since its copies are now more faithful. No searched read has run on this engine, so nothing is invalidated.
- **What is left in the 33**, by first differing play: block declarations (11, not traced), mana and land choices (11), and singles. Known and not taken, because none is a few lines: spells cast this turn are not copied (upstream's `TODO update thisTurnCast`; Kalamax's "first instant each turn", storm), and upstream lists creatures attacked this turn, counters added this turn and the controller timestamps as TODOs. The AI's memory is not copied either (the field guide's standing explanation).
- **The crash fix is open upstream as [#12949](https://github.com/Card-Forge/forge/pull/12949)** (the user, 11-18: submit it directly, without the test). It is the one changed line; the description offers the test. The three copier fixes go on the upstream queue and are not expedited ([upstream-worklist.md](../design/upstream-worklist.md), Tier 0.12).
- **The fork's tests:** 26 classes plus upstream's two simulation suites, 377 tests, all pass on `09133a7ad4`.


## Addendum 11-18, night: the ability table extended; three hook-side findings before the era bridge

- **The served table for the merged engine is `data/embeddings/abil-cf2ca6ba-m13-qwen3`, 17,745 keys.** It is `abil-cf2ca6ba-b4s-qwen3` with its 17,431 rows byte-identical and 314 new ones (`scripts/extend_ability_table.py`, the pinned model, revision check cosine 1.00000). A checkpoint's config still names `b4s`; a server on the merged jar takes `--abilities data/embeddings/abil-cf2ca6ba-m13-qwen3`. The pool dump is re-pinned to the merged jar's (`data/pool/abilities-cf2ca6ba.jsonl`; the old one kept as `-pre-merge-5bd040351f`).
- **The 314 keys:** the 162 the pool dump changed, and 152 in-play keys seen in the two merge smokes and absent from all 5,000 games of the 11-07 confirm's `iter-405` arm (`data/runs/merge-20261118/abilities-inplay-new.jsonl`). Keys that were already outside the table on the old jar were left out, so the bridge's two sides miss the same keys.
- **What a missing key does:** `AbilityCache.index` returns −1 and the option is keyed on its host row and kind alone. Nothing counts it at serve time. The old era ran with 1.67% of its key mentions outside the table (the 11-07 arm, 20.2M mentions).
- **A fresh 200-game smoke** (`m13-abil-smoke`, `iter-405`, the copier jar, seed base 20261119, the new table): 1.93% of key mentions miss, against 2.69% on the same games under `b4s`. Every pool-dump key resolves. One game crashed (a `NullPointerException` in `SpellAbilityStackInstance`, a charm with no sub-ability). The win rate is not a read.
- **Finding 1: the excess over the old era is one class of key.** 0.89% of mentions are keys whose text carries an entity id ("… by Aang, Swift Savior (100) (by paying {2} …)"), against 0.20% on the old jar. Upstream's alternative-cost description now names the granting card with its id, so the key differs per game and no table can hold it.
- **Finding 2: the harness draws opponents from six AI profiles on the merged jar.** `AnvilRun` draws each seat's profile from `AiProfileUtil.getAvailableProfiles()`, which now lists `Hard` and `Hardest` beside the old four. The "What else the boundary changes" line above ("the harness's draw of four is unchanged") is wrong, and plan pin 5 does not hold on this jar. About a third of the smokes' seats drew one of the two.
- **Finding 3: a bridged cast that fails once is asked for 999 times.** Upstream added a failed-cast memory (`AiController.hasFailedToCast`, cleared per turn): after one failure `handlePlayingSpellAbility` refuses that cast at once. The heuristic's chooser consults it; the bridge's option list does not. The network re-picks the option until `PhaseHandler`'s loop guard ends the window. 39 guard firings in 600 smoke games on the merged jar against 20 in 7,500 on the old one, about 24 times the rate, nearly all on modal spells whose chosen mode had no target. Each firing loses the spell for the turn and costs about 30 seconds.
- **None of the three is fixed here.** Each fix is in `AnvilRun` or the bridge's controller and changes served games, so it belongs before the era bridge or it is a second boundary for served games. Put to the user with the bridge's sizing.

## Addendum 11-18, late night: the three bridge-side fixes are inside the boundary; the pin moves to `26e81c65f1`

- **The user ruled the three findings fixed before the era bridge** (11-18). One fork commit, `26e81c65f1`; the serving jar is `data/runs/merge-20261118/forge-merge-20261118-bridgefix.jar`.
- **Hard and Hardest do not cheat** (the user's question). They are `Default` with a higher in-danger life threshold (5 and 6 against 4) and a larger Monte Carlo allowance, which is inert with the game flag off. Both files state that no hidden information is used. The one cheat property, `CHEAT_WITH_MANA_ON_SHUFFLE`, is set alike in all six profiles and acts only when the game's rules allow it. Plan pin 5 stands as written.
- **The profile draw is a named set.** `AnvilRun` draws from `Cautious, Default, Experimental, Reckless` unless `-profiles <csv>` names another; a missing profile is fatal. The seed-to-profile map is the old era's.
- **A cast the engine refuses for the turn is not offered.** The priority option scan skips an option that `AiController.hasFailedToCast` holds, the rule upstream's own chooser follows. The cost: a modal spell whose first cast failed is unavailable until the next turn, where the old engine let the seat choose its modes again.
- **`AbilityKey.stripRuntime` strips " by <source> (<id>)" when a cost note follows it.** No pool-dump key changes.
- **The proof.** `run-20261118-bridgefix-baseline`: 500 of 500 mainline hashes identical to the era's baseline and to the copier jar's pass, fidelity 467 / 33 / 0. The fork's anvil, simulation and view test classes pass with a test for each fix. A heuristic-only game is unchanged; a served game changes, and none had been read.
- **The smoke on the fixed jar** (`m13-bridgefix-smoke`, 200 games, the seeds of `m13-abil-smoke`): no loop-guard firing (19 before), the four profiles only, id-bearing keys 0.02% of mentions (0.89% before), mean game 27 s (32 s before). The first-attempt veto rate is 2.3% against the old era's 1.5%. One game crashed in both smokes with the same `NullPointerException` (`SpellAbilityStackInstance`, a charm with `ChoiceRestriction` and no chosen mode); it stays with the crash routed to Build 1.
- **The table is rebuilt on the fixed jar's keys:** `abil-cf2ca6ba-m13-qwen3` is now 17,798 keys, the `b4s` rows plus the 162 changed pool keys and 205 in-play keys new to the merged engine. It replaces the 17,745-key build of the addendum above, which served only its smoke.

## Addendum 11-18, night: the era bridge closes inside its bar

- **The kill condition is not tripped.** `big-run/iter-405` reads 0.6064 ± 0.0069 on the merged jar against the plain heuristic (5,000 games, the 11-07 confirm's seeds, network alone, masked, raw, table `abil-cf2ca6ba-m13-qwen3`). Paired on seed against its old-jar arm (0.6214) that is −1.53 ± 0.75pp on 4,909 pairs. The bar was −3pp.
- **The reference `d6-run11/iter-019` reads 0.5208 ± 0.0071,** paired −0.69 ± 0.78pp against its old-jar arm (0.5280).
- **The trained checkpoint keeps its lead:** +8.54 ± 0.79pp over the reference on the merged jar, against +9.46 ± 0.77pp on the old one.
- **The drop is not attributed.** It is 2.0 standard errors for `iter-405` and 0.9 for the reference. The plan requires attribution only past the bar.
- **The old-jar side stands as filed.** A 1,000-game re-run of `iter-405` on the old jar reads +0.00 ± 0.41pp against the filed arm; 872 of 1,000 games are identical in winner, turns and windows. It ran against `../forge-baselines`, whose `forge-gui/res` equals the old pin's; its `run.json` records that worktree's commit, not `5bd040351f`.
- **The routed census items.**
  - *The key-miss rate:* 1.64% of mentions on the 5,000 `iter-405` games, against the old era's 1.67%. Closed.
  - *The loop guard:* no firing in 10,000 games. Closed.
  - *The `pay` ask mix:* not readable from this run. A network-alone read serves no payment window, on either jar. `payManaCost` calls on the model's seat fell from 98.9 to 87.7 per game. The `pay` head's retrain is decided at the first read that serves the surface; routed by name to the first run that serves it.
- **A new engine crash, not fixed.** `SacrificeEffect.resolve` (line 124) indexes a one-part message array by a multi-part `SacValid`: 28 games in 10,000, all in deck `dc-864561`; the card is not identified. The old era's arms had 19 crashes in 10,000 of other kinds; the bridge had 35. A crash fix is a boundary, so it is routed to Build 1 with the `NullPointerException`.
- **The day-zero figures are the state table's merged-engine entry.** Numbers are still not compared across the merge except through these pairs.
