# PlayerController callback census — results

**Date:** 2026-07-03. **Anchors:** [playercontroller-override-plan.md](playercontroller-override-plan.md) (this was its "first implementation step"); [bridge-protocol-v0.md](bridge-protocol-v0.md) (ranks tag coverage; sizes the bridge-tax napkin math).
**Setup:** 500 games (4×125, disjoint seed ranges from base 20260800), Commander precons (Abzan Armor vs Arcane Maelstrom — same pair as the soak/scaling runs), heuristic AI both seats, `forge census` (fork commit `9c4a7cd4cf`; `CensusPlayerController` logs all 109 callbacks with turn/phase/stack depth). Data: `data/census/run-20260703/`; analyzer: `scripts/census/analyze_census.py`. All 500 games decisive (the 300 s census draw clock never fired), median 19 turns.

Correction recorded: the decision surface is **109** abstract methods, not the 110 previously quoted (that count included the class declaration). Docs updated.

## Headline numbers

- **388,157 callbacks; mean 776/game (median 708, max 2,288).**
- **45 of 109 methods ever fired.** 64 are completely silent across 500 Commander games on this deck pair — the long tail isn't just thin, most of it is *mute* until the card pool widens. Phasing by measured traffic is vindicated.
- **`chooseSpellAbilityToPlay` is 56% of all traffic** (437/game mean). Top five methods (`chooseSpellAbilityToPlay`, `payManaCost`, `autoPassCancel`, `playChosenSpellAbility`, `playSpellAbilityNoStack`) are **84%**.
- The M0 bridged set (priority + mulligan + triggers + binary + number) covers ~57% of all callbacks — and the only high-frequency one is the priority pick. (`chooseBinary` and `chooseNumber` are near-silent here: 0 and 26 calls. They stay in the set because they're one-field answers, not because they matter for traffic.)
- **Bridge-tax napkin math, now with real numbers:** bridging priority only = ~437 round-trips/game ≈ 29/s per worker at w=16 pace (~15 s/game wall). At ~0.3 ms loopback gRPC that's ~1–2% overhead — consistent with the protocol draft's single-digit-percent expectation. Full M0 set adds ~2%.

## Top of the frequency table (full table in `data/census/run-20260703/analysis.txt`)

| method | total | mean/game | % games |
|---|---|---|---|
| chooseSpellAbilityToPlay | 218,409 | 436.8 | 100% |
| payManaCost | 59,761 | 119.5 | 100% |
| autoPassCancel | 19,694 | 39.4 | 100% |
| playChosenSpellAbility | 17,229 | 34.5 | 100% |
| playSpellAbilityNoStack | 10,148 | 20.3 | 100% |
| chooseColor | 8,462 | 16.9 | 98% |
| notifyOfValue | 7,649 | 15.3 | 98% |
| orderAndPlaySimultaneousSa / orderSimultaneousSa | 6,320 each | 12.6 | 100% |
| declareAttackers | 4,797 | 9.6 | 100% |
| chooseOptionalCosts | 4,035 | 8.1 | 14% (kicker-heavy games) |
| assignCombatDamage | 3,231 | 6.5 | 81% |
| declareBlockers | 1,821 | 3.6 | 87% |

Notable near-silent decisions: `chooseTargetsFor` 96 calls (9% of games), `chooseModeForAbility` 359, `chooseNumber` 26, `chooseBinary` 0. Never fired at all: `announceRequirements` (X), `specifyManaCombo`, `applyManaToCost`, `chooseNewTargetsFor`, `sideboard`, and 59 others.

## The cast path, observed (resolves the override plan's one inferred claim)

17,229 `playChosenSpellAbility` windows, nested callbacks identified by stack depth:

- **27% of casts complete with zero nested callbacks** — fully pre-decided by the AI evaluation, exactly the one-shot shape `CastPlan` will reuse.
- **`payManaCost` is the dominant in-window callback** (47K of its 60K calls are nested in cast windows; the typical window is 1–5 `payManaCost` calls, one per cost component/mana ability). `chooseColor` is almost entirely in-window (8,447/8,462) — color picks during payment.
- **`chooseTargetsFor` never fires inside the window** (0/96): targets really are pre-set on the SA before `playChosenSpellAbility`, confirming the AI path mechanism the plan inferred.
- **`announceRequirements` (X) never fires on the AI path, anywhere.** The AI decides X inside its own evaluation and pre-sets it. So `CastPlan`'s X (like its targets) is *injected onto the SA*, not answered through a callback.
- **`chooseOptionalCosts` always fires OUTSIDE the window** (4,035/4,035) — during `chooseSpellAbilityToPlay` evaluation, before the cast decision returns. One-shot casting must fold optional-cost picks into the priority answer, which is precisely the composite-`CastPlan` shape the protocol drafted.
- **`chooseModeForAbility` fires in BOTH positions** (204 outside during evaluation, 155 inside during play). Mode picks are the one component a `CastPlan` realization must be able to answer at *two* interception points; the worker-side plan executor needs to serve mode answers wherever they're asked.
- Mid-resolution choices (`chooseSingleEntityForEffect`, `confirmAction`, `chooseCardsForEffect`, …) fire 100% outside cast windows — they belong to stack resolution, as the granularity analysis said: irreducibly micro-step, always their own decision requests.

## What this changes

- **Nothing structural.** The override plan's verdicts and the protocol's answer shapes survive contact with data; the two `CastPlan` refinements (X/targets injected, modes answered at two interception points, optional costs folded into the priority answer) are worker-side implementation details of the plan executor, not protocol changes.
- **Phase-2 serialization order is now data:** payment (`payManaCost`/`chooseColor`) is the second-biggest surface after priority — but per §3c the *engine-default* payment answer is the design intent anyway; bridging it is deferred until the consequential-payment flag exists. Combat (`declareAttackers`/`assignCombatDamage`/`declareBlockers`) is the real next serialization target, then the ordering family (`orderSimultaneousSa`, `orderMoveToZoneList`, scry/surveil).
- **Caveat for the record:** single deck pair. The 64-silent-method list will shrink as the DC pool arrives (e.g. `sideboard` never fires in single games by construction; X-spells are absent from these precons' AI-playable range). Frequency *ranks* among the top ~15 should be robust; re-run the census when the DC decklist pipeline lands — it's one command.
