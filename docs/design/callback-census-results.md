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

---

# DC-pool re-run (2026-07-04)

**Setup:** 500 games — 100 deck pairs × 5 games, pairs sampled deterministically from pool `f568b187` (111 decks, every deck appears ≥1×; driver `scripts/census/run_dc_census.py`, seed base 20260704, 4 lanes, fork commit `80b66aa262`). Data: `data/census/run-20260704-dcpool/`. All 500 decisive, zero draws; **turns median 21, mean 23.2, p90 34, max 59** — real DC decks play only modestly longer than the precons' median 19 (the pipeline smoke game's 161 turns was an outlier, not the distribution).

## Headline numbers vs the precon census

- **567,927 callbacks; mean 1,136/game (median 1,015, max 4,379)** — up 46% on the precon mean of 776. Traffic grew faster than turns (+22%): richer decks decide more per turn.
- **64 of 109 methods fired** (precon: 45). The silent list shrank from 64 to 45; the 19 newly-awake methods are pool-driven (`chooseCardsForConvokeOrImprovise`, `chooseCardsToDelve`, `chooseCounterType`, `chooseSingleStaticAbility`, `vote`, `chooseCardName`, `payCombatCost`, …).
- **`chooseSpellAbilityToPlay` is 51% of traffic** (579.7/game; precon 56%). **Top five are 80%** (same five members as precon: priority, `payManaCost`, `playChosenSpellAbility`, `autoPassCancel`, `playSpellAbilityNoStack`) — the top-rank robustness prediction held.
- **The M0 bridged tag set covers ~52% of callbacks** (precon ~57%). The precon-near-silent tags woke up but stayed small: `chooseBinary` 55 calls (was 0), `chooseNumber` 109 (was 26), `playTrigger` 11.1/game in 65% of games (triggers are real traffic now).
- **New heavy mid-table arrivals** the precon pair never showed: `chooseOptionalCosts` 29.2/game in 35% of games (was 8.1 in 14%), `chooseCardsForConvokeOrImprovise` 28.4/game mean **with a pathological max of 2,788 calls in one game** — an apparent AI convoke/improvise re-evaluation loop worth a look before M2 (logged, not investigated), `chooseSingleReplacementEffect` 9.6/game (replacement effects are ubiquitous in the real pool), `chooseSingleStaticAbility` 9.1/game.

## Cast path: structural claims survive the pool

27,010 cast windows: **22% complete with zero nested callbacks** (precon 27%); `payManaCost` chains remain the dominant window body; `chooseModeForAbility` again appears both outside and nested (both interception points, as the CastPlan executor design expects); `chooseTargetsFor` stays out of cast windows and near-absent overall (103 calls, 7.6% of games); `announceRequirements`, `specifyManaCombo`, `chooseNewTargetsFor`, `sideboard` remain never-fired. One new in-window pattern: `chooseSingleReplacementEffect → playSpellAbilityNoStack` sequences (replacement effects triggering during casting) — mid-resolution machinery, handled by micro-step per the existing invariant, no protocol change.

## What this changes

- **Bridge-tax napkin math scales but doesn't move class:** priority-only round-trips are now ~580/game (was ~437, +33%); full M0 set ~596/game. Wall-clock per game grows roughly in step, so the measured 2.6%-at-w=16 tax should hold within noise on the real pool; re-measure only if M1's inference latency changes the equation anyway.
- **Throughput expectation for the real pool:** games are +22% turns / +46% callbacks vs precons — plan M1 corpus schedules on ~⅔–¾ of the precon-calibrated games/hour, not on the 161-turn scare number.
- **Phase-2 serialization order updated by real traffic:** after combat, the replacement/static-choice family (`chooseSingleReplacementEffect`, `chooseSingleStaticAbility`, `chooseCounterType`) now outranks the scry/surveil ordering family; `chooseOptionalCosts` grew 3.6× and reinforces the CastPlan composite-answer design.
- **M1 tag coverage basis switches from provisional (precon) to measured (pool)** — ADR-0003's provisional-basis caveat is discharged.
