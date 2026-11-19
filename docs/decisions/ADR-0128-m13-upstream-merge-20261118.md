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
