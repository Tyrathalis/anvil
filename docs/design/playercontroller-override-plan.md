# PlayerController override plan — design note

**Date:** 2026-07-03. **Anchors:** ADR-0001 (bridge-protocol invariants), design §9 (bridge), §3 (pointer decoder); remaining-M0-scope item 2 of 3.
**Question answered:** where does Anvil's controller hook into Forge, what is the full decision surface it must cover, and — per decision family — can a decision be answered in one bridge round-trip or does engine structure force micro-steps? This note feeds the bridge-protocol draft directly.

All line references are to the fork at `8907112` (upstream base `0bfdaa5`).

## What the archaeology found (2026-07-03)

### Injection point: clean, zero engine changes

- `Game`'s constructor asks each `RegisteredPlayer`'s `LobbyPlayer` — cast to `IGameEntitiesFactory` (`forge-game/.../player/IGameEntitiesFactory.java`) — to `createIngamePlayer(game, id)`, which constructs the `Player` and calls `Player.setFirstController(...)`. That factory is the whole wiring: **a `LobbyPlayerAnvil` implementing `IGameEntitiesFactory` injects `PlayerControllerAnvil` with no changes to forge-game**, exactly how `LobbyPlayerAi` does it (`forge-ai/.../LobbyPlayerAi.java:48-57`).
- Precedents for non-heuristic controllers exist: `PlayerControllerForTests` (`forge-gui-desktop/src/test/.../gamesimulationtests/util/PlayerControllerForTests.java:62`) extends `PlayerController` directly and runs headless; our own `forkcheck` (`ForkFidelityCheck.java`) already builds players/matches the same way `SimulateMatch` does.
- The factory interface also demands `createMindSlaveController(master, slave)` (Mind Slaver effects). Rare; heuristic fallback is fine indefinitely.

### The decision surface: 109 methods, ~88 real decisions

`PlayerController` (`forge-game/.../player/PlayerController.java`, abstract, ctor `(Game, Player, LobbyPlayer)`) has **109 abstract methods** (corrected from 110 by the census generator's parse): ~88 real decisions, ~16 pure notifications (`reveal`, `notifyOfValue`, …), ~6 utility/no-ops. By family (counts approximate):

| Family | ~Count | Examples |
|---|---|---|
| Card/entity selection | 25 | `chooseCardsForEffect`, `choosePermanentsToSacrifice`, discard/delve/splice |
| Numbers & dice | 14 | `chooseNumber`, `announceRequirements` (X), dice/planar (AI stubs these) |
| Mana & cost payment | 10 | `payManaCost`, `getCostDecisionMaker`, `chooseManaFromPool`, `orderCosts` |
| Ability/priority/trigger | 9 | `chooseSpellAbilityToPlay`, `playChosenSpellAbility`, `chooseModeForAbility`, `playTrigger` |
| Combat | 8 | `declareAttackers/Blockers`, `assignCombatDamage`, block/attack ordering |
| Confirmations | 6 | `confirmAction`, `confirmTrigger`, `confirmReplacementEffect` |
| Ordering/arrangement | 6 | `arrangeForScry/Surveil`, `orderMoveToZoneList`, `orderSimultaneousSa` |
| Binary/color/type/name | ~14 | `chooseBinary`, `chooseColor`, `chooseCardName`, `chooseSomeType` |
| Mulligan/opening/sideboard | 6 | `mulliganKeepHand`, `tuckCardsViaMulligan`, `sideboard` |
| Notifications & utility | ~22 | no decision content |

Calibrating facts from `PlayerControllerAi`: the incumbent AI itself **stubs or randomizes ~a dozen methods** (all dice-roll variants are `TODO: AI logic` → random; `chooseFlipResult` is random; several methods are `assert(false)` placeholders like `applyManaToCost`, `chooseCardsForCost`). The long tail is genuinely long and thin — full-surface coverage is not required for competent play, and Anvil can phase coverage in.

### Granularity: what one call actually means (the protocol crux)

The engine calls all controller methods **synchronously on the game-loop thread**; the stack is frozen during cast setup (`PlaySpellAbility.playAbility`), callbacks are strictly sequential, no reentrancy. A bridge call may block the game thread — that *is* the inference-server pattern (§9).

The load-bearing discovery: **`playChosenSpellAbility(sa)` is itself an abstract controller method** (`PlayerController.java:255-256`). The priority loop (`PhaseHandler.mainLoopStep`, ~1046-1157) asks `chooseSpellAbilityToPlay()` → controller returns a chosen `SpellAbility` → engine hands it back to `playChosenSpellAbility`. The controller therefore owns the whole cast flow, and there are **two proven paths through it**:

- **Human path** (`PlaySpellAbility.playAbility`): a serialized chain of blocking callbacks — optional costs → modes (`chooseModeForAbility`) → X (`announceRequirements`) → targets (`SpellAbility.setupTargets` → `chooseTargetsFor`) → cost payment (per-part confirms, per-source mana). Inherently micro-step.
- **AI path** (`PlayerControllerAi.playChosenSpellAbility:837` → `ComputerUtil.handlePlayingSpellAbility`): targets are **pre-set on the SA before it's returned** from the choose call; payment is solved in one pass by `AiCostDecision` (via the abstract `getCostDecisionMaker`, `PlayerController.java:329`); modes/X likewise decided within the AI's own evaluation. Proves **one-shot casting is achievable** — decode the full action (spell + modes + X + targets + payment plan), stuff it into the SA, play it AI-style.

Per-family verdicts:

| Decision family | Verdict | Notes |
|---|---|---|
| Cast at priority | **One-shot possible** (AI path) or micro-step (human path) | Exactly ADR-0001's one-shot-or-micro-step invariant, realized in existing engine code — the retreat is a config change, as required |
| Mid-resolution choices (`chooseCardsForEffect`, `confirmAction`, `chooseNumber`, …) | **Micro-step forced, irreducibly** | Called *during* effect resolution; legal options don't exist until ask time. The protocol MUST handle these as standalone decision requests — micro-step support is not optional |
| Combat: declare attackers | **One-shot** | Single call mutates `Combat` in place; engine validates and re-asks until legal (`validateAttackers` retry loop = free safety net) |
| Combat: declare blockers | **One-shot per defender** | Sequential calls, one per defending player |
| Combat: damage order/assignment | Micro-step (separate calls) | `orderBlockers`, `assignCombatDamage` fire as combat resolves |
| Mulligan/opening | Micro-step (2-3 calls) | `mulliganKeepHand` → `tuckCardsViaMulligan` |
| Everything else (colors, numbers, ordering, confirms) | Micro-step by construction | Each is already a single self-contained question |

**Fit with the legal-actions-only invariant:** nearly every callback arrives with its legal options materialized as a parameter (`List<SpellAbility>`, `CardCollectionView`, min/max bounds, `ColorSet`). Serialization is selection-by-index over an engine-provided list — masking is construction, as required. Two families are *construction, not selection*: **combat maps** and **targeting**, where the bridge answer is a structured object built from engine-enumerated legal candidates (`CombatUtil.canAttack/canBlock`, targeting restrictions) and validated by the engine's own retry loops.

### Threading & timeouts

- One game thread per worker calls everything; a blocking gRPC call in a callback is safe and matches batch-formation on the Python side.
- The heuristic AI's per-decision 5s timeout (`AiController` FutureTask wrapper, ~1670-1694 — source of the soak's 259 `TimeoutException`s) wraps *its own evaluation*, not the controller contract. Anvil inherits no such machinery; per the forkcheck lesson, use **watchdog draw-clocks, never thread interrupts** (an interrupted worker can leak a thread that keeps consuming the shared `MyRandom` singleton).
- Note for the harness spec: the decisions the incumbent AI times out on (complex targeting, e.g. kicked Comet Storm) are precisely where heuristic *fallback* would also be slow — bridge-answered decisions dodge that cost entirely.

### Landmine: GameCopier swaps controllers on fork

`GameCopier.clonePlayer` (`forge-ai/.../simulation/GameCopier.java:205-213`) replaces any non-`LobbyPlayerAi` lobby player with a fresh `LobbyPlayerAi(USE_SIMULATION)` — **a fork of an Anvil-controlled game silently hands the copy to the heuristic AI.** Harmless for M0 (no forking) and for forkcheck (players are AI anyway); must be fixed in the fork before Grindstone/search forks Anvil games (M2+, alongside the fork-API work). One-line fix; goes on the fork-API worklist in ADR-0002's ledger.

## The override plan

**Class design: `PlayerControllerAnvil extends PlayerControllerAi`** (not `PlayerController` directly), overriding decisions selectively as bridge coverage expands.

- Why: 110 abstract methods means a direct subclass starts life as 110 hand-written stubs (the `PlayerControllerForTests` graveyard). Extending the AI inherits a *legal* answer for every method on day one, plus the AI-path cast machinery (`handlePlayingSpellAbility`, `AiCostDecision`) that one-shot casting reuses. Anvil's fork already carries forge-ai; upstream-cleanliness is not a constraint for a class that will never be PR'd.
- **Provenance rule (hard):** every decision record is tagged `answeredBy: bridge | heuristic-fallback`. Fallback decisions are not the model's decisions; training and Ante must be able to filter them. A game's trajectory metadata carries the fallback rate; alarms if it grows.
- The M0 **random-legal agent** is then: bridge answers `chooseSpellAbilityToPlay` with a uniform pick over the materialized legal list (plus a few cheap high-frequency methods below); everything else falls back. This measures exactly what M0 needs — games/sec **with bridge round-trips in the loop** — without first solving 110 serializations.

**Phased bridge coverage** (each phase = protocol messages actually needed, not speculative):

1. **M0:** `chooseSpellAbilityToPlay` (the hot path — fires every priority window), `mulliganKeepHand`/`tuckCardsViaMulligan`, `confirmTrigger`/`playTrigger`, `chooseBinary`, `chooseNumber`. All are index/int/bool answers over materialized lists.
2. **M1 (pointer decoder era):** one-shot cast (modes + X + targets + payment plan decoded together, played via the AI path), combat declarations (structured construction), card-selection family, scry/surveil ordering.
3. **Later:** the long tail, in order of measured callback frequency (see census run below), heuristic fallback shrinking as coverage grows. Dice/Un-set corner cases may stay fallback forever (the incumbent AI randomizes them anyway).

**Module placement:** package `forge.ai.anvil` inside forge-ai (the class extends `PlayerControllerAi`, and forge-ai is where `GameCopier` already lives); launcher command `anvil` in `forge-gui-desktop` alongside `SimulateMatch`/`ForkFidelityCheck`, registered in `Main.java` — the exact forkcheck precedent, no parent-pom surgery. Lives in the fork only, never upstreamed (the fork-API contribution is separate and stays Anvil-agnostic).

**First implementation step — instrumented callback census** (*done 2026-07-03: [callback-census-results.md](callback-census-results.md) — 500 games, 388K callbacks; verdicts below confirmed, cast-path claim resolved*)**:** before any bridge code, wrap `PlayerControllerAi` in a logging decorator (or subclass logging `method, args-summary, phase, stack-depth` then delegating to `super`), run a few hundred games, and get (a) the **empirical frequency of every one of the 110 callbacks** under real Commander games — this ranks phase-2/3 serialization work by actual traffic, and (b) the **exact callback sequence on the AI cast path for modal/X/optional-cost spells** — the one place where this note's granularity analysis is inferred from code reading rather than observed (the human path's mode/X callbacks may or may not fire on the AI path depending on how `AiCostDecision` and mode-choosing interleave). Cheap (a session), and its output is a table the bridge-protocol draft can cite as ground truth.

## What this resolves for the bridge-protocol draft (next item)

- The protocol's decision-request envelope is **per-callback**: `decisionType` (one per bridged method), engine-materialized `options` (or legal-candidate sets for combat/targeting), and an answer that is an index/indices/int/bool/structured-construction. Micro-step is the base case; one-shot cast is a *composite answer* to the priority decision, not a different protocol mode — which is precisely ADR-0001's "retreat is a config change" requirement.
- Fallback answering (heuristic answers locally, bridge notified or not at all) must be a first-class response mode with provenance tagging.
- Blocking synchronous request/response per game thread is safe; no async protocol machinery needed for M0.
