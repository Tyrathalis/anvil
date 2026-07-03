# Fork-fidelity differential test — design note

**Date:** 2026-07-03. **Anchors:** ADR-0001 M0 deliverable (b); design doc §9 (state forking), §15; survey §5.3.
**Question answered:** when you fork a live Forge game via `GameCopier` and let the fork play forward untouched, does it reproduce the mainline trajectory? This is the second measurement (after the soak) gating the "stable single-step fork API as flagship upstream contribution" bet → ADR-0002.

## What the archaeology found (2026-07-03, fork @ `0bfdaa5`)

- `GameCopier` (`forge-ai/.../simulation/GameCopier.java`) is the mature copy path: rebuilds a fresh `Match`+`Game`, maps players/cards via BiMaps, restores zones, counters, combat, phase (`devModeSet`). **15+ documented copy gaps** (`creatureAttackedThisTurn`, `thisTurnCast`, `countersAddedThisTurn`, `ExiledWith`, controller history, …). **Stack not copied by default** (`GameSimulator.COPY_STACK = false`; the copy path exists but matches spells by description — fragile).
- `GameSnapshot` (forge-game) is the experimental ID-based alternative behind `Game.EXPERIMENTAL_RESTORE_SNAPSHOT`; less proven. Not v1's subject; candidate for a later comparison run.
- **Existing fidelity checking is single-point-in-time only**: `GameSimulator.ensureGameCopyScoreMatches()` diffs one AI eval score. Nobody has ever tested forked-game *forward play*. There is no trajectory recording anywhere in the engine.
- **All randomness funnels through `MyRandom`** (static singleton over one `java.util.Random`; seedable via `setRandom()`, no per-game seed). `java.util.Random` is serializable → RNG state can be cloned at the fork point.
- **Resume is plausible without engine surgery**: `PhaseHandler.mainGameLoop()` / `mainLoopStep()` are public and separate from `startFirstTurn()`; the copy has real `PlayerControllerAi` controllers (`clonePlayer` reuses the original `LobbyPlayerAi` when players are already AI — same heuristic profile, no forced `USE_SIMULATION`).
- Game events post on a **synchronous Guava EventBus per game** (`Game.subscribeToEvents`); `GameEventTurnBegan` fires on the game thread at turn start — a clean, stack-empty interposition point requiring no patch.

## Test design

Two tiers, one driver class in the Forge fork (`forge-gui-desktop`, alongside `SimulateMatch`), invoked headlessly.

> **Implemented 2026-07-03** as `forge forkcheck` (fork commit `d68d3ed`): `ForkFidelityCheck.java` + a 1-method engine patch (`PhaseHandler.devResumeAtPriority()` — a fresh copy otherwise skips priority for the forked phase, since `givePriorityToPlayer` defaults to false). Deltas from the sketch below, discovered during archaeology:
> - **Fork point is a quiescent MAIN1 priority event**, not turn-begin: `GameEventTurnBegan` fires mid-`advanceToNextPhase` (before untap effects), so a copy taken there would never untap. At a `GameEventPlayerPriority` event with empty stack, the driver additionally **drains pending triggers** (replicating `checkStateBasedEffects`) and defers to a later priority event if anything lands on the stack — `GameCopier` does not copy the waiting-trigger queue.
> - Tier 1 (static digest compare) runs at the fork point only in v1, not every turn; the trajectory tier subsumes it there.
> - Inline watchdog draw-clocks (`setGameOver(Draw)`) instead of thread-interrupting timeouts, so a hung fork can't leak a thread that keeps consuming the shared RNG singleton.
> - **`-perturb` sensitivity mode**: injects a 1-life delta into the fork after the static compare; the trajectory detector must report divergence. Validated 3/3 — each perturbed fork detected at exactly the first turn boundary after the fork, with the diff sample pinpointing the life line.
> - Smoke (3 seeded games): 3/3 clean — fork + replay reproduced mainline trajectory and outcome exactly; copy cost 11–30 ms.

**Setup per game:** seed `MyRandom.setRandom(new Random(seed))` before match creation; two heuristic AI players, Commander precons (same decks as the soak, for comparability); drive the game like `SimulateMatch` does but subscribe a `GameEventTurnBegan` listener before start.

**Tier 1 — static copy fidelity (every turn):** in the turn-began handler, `new GameCopier(game).makeCopy()` and compare orig vs copy with a custom **state digest** (turn, phase, active player; per player: life, poison, counters, mana pool, and per zone the sorted multiset of card names + load-bearing card state: tapped, damage, counters, attachments, P/T; stack size). Record: digest match/mismatch, which section diverged, copy wall-time. Also run the existing eval-score cross-check as a baseline (it's what upstream considers "fidelity" today).

**Tier 2 — trajectory fidelity (one fork per game, random mid-game turn):** at the chosen turn:
1. Serialize the current `MyRandom` RNG → state S (three clones: fork-replay, mainline-restore, record).
2. `makeCopy()` the game; set the copy's age to `Play`; subscribe a digest recorder to the copy.
3. Restore RNG from S and run the fork to completion inline (`mainGameLoop()`, own timeout), recording a per-turn digest sequence + final outcome.
4. Restore RNG from S again and let the mainline continue, recording the same digest sequence.
5. Compare from the fork turn onward: first-divergence turn (if any), outcome match (winner, end turn, final life).

**Success/failure accounting per game:** `copy_crash` (GameCopier throws), `resume_crash` (fork can't play forward — the single-step-API gap made concrete), `static_mismatch` (tier 1), `divergence@turn` (tier 2, with digest section), `clean` (identical trajectory + outcome). Plus copy cost distribution.

## Known confounds (classify, don't pretend away)

- **Wall-clock nondeterminism in the heuristic AI**: per-decision timeouts (259 seen in the 6K-game soak, ~0.04% of decisions) can make orig and fork legitimately choose differently. Expected to show up as a low, irreducible divergence floor.
- **Identity-hash iteration order**: fresh objects in the copy have different identity hash codes; any engine/AI logic iterating a `HashSet<Card>` can order differently even with identical RNG. If this shows up, it's a *finding about fork fidelity in principle*, not test noise — exactly what the upstream API bet needs to know.
- Fork at turn start only (empty stack) in v1; mid-stack forking (needs `COPY_STACK` + fragile SA matching) is a documented non-goal until the clean-point number is known.

## Scale

Tier 1 rides along on every game. Tier 2 target: ≥300 games (each costs ~2× a normal game — mainline + one inline fork replay), overnight-able alongside nothing else. Divergence rate resolution ~0.3% — sufficient for the ADR gate (the question is "is this basically sound or basically broken", not a third decimal).
