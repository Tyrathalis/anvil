# Upstream worklist

**Doc status:** living · the submission plan (2026-09-27, first section) + queued upstream contributions + diagnosed engine classes

Seed-pinned, deterministically reproducible engine bugs harvested from Anvil
runs, queued for upstream PRs to Card-Forge/forge (per ADR-0002: static-bug
fixes are upstream PR #1; fork API is the flagship contribution, sequenced
before M2). Forge design conversations go in PRs/Discord, never issues
(prior-work survey: stale bot, ~35 days).

Repro: `uv run python -m anvil.bridge.harness replay d3pilot-20260704-175219 <game>`
(replay caveat from the batch-harness spec applies: solo replays are
self-consistent but can drift from in-run instances via AI wall-clock
timeouts; crash repros here are engine-path crashes and expected to
reproduce — verify before filing).

## The submission plan (2026-09-27) — the big run's waiting window

**Verdict: five tiny stock-bug fixes go first, one engine PR and one GUI PR open at a time; the
AiCache series (talor's cache, then the mana-source memo) follows on TRT's condition; the
determinism hooks come back as two PRs; the maintainer-blessed Copier → Snapshot consolidation is
staged as four small PRs after those.** Every item below was re-checked against upstream master
`2ccbbb0132` (fetched 09-27): what upstream already carries is struck from the queue, and each
survivor's size is its diff against that tip.

### The rules we submit under

What the record says the maintainers accept, from #11203's review (tool4ever, 07-11), TRT's
09-16 condition on talor's cache, the #11457 thread and the stale bot:

1. **One change per PR, with its one test.** A fix and the regression test that fails first, in
   the existing test class where one exists. No bundles: the monarch PR's "bundle the ternary"
   idea is the shape to avoid.
2. **Reuse what exists; never add an abstraction a maintainer did not name.** TRT on the cache:
   "existing systems need to be reused for less technical debt — in this case AiCache."
   tool4ever on #11203: consolidate on the snapshot path, delete the duplicate. Those two named
   directions are the only abstractions this plan builds.
3. **Small test surface.** One focused test per fix; the 221-line geometry test on the hit-test
   item is trimmed to the two cases that carry the bug before it is offered.
4. **Every PR is authored on a clean upstream-master worktree** (`../forge-upstream`, the
   #11203 / #11285 / hardening pattern), never on the research fork or `playable`. The research
   fork is frozen for the big run; fixes return to it at the next boundary merge, when the
   fork-local copies are dropped (as #11203's were).
5. **The stale bot closes at ≈ 35 days of silence** (#11285 died that way on 09-14 with a
   maintainer question answered and no verdict). A PR with an open question gets a ping at day
   25; a PR nobody has touched gets one nudge, then is left to close.
6. **Two open at a time, in disjoint modules** — one engine (`forge-game` / `forge-ai`), one GUI
   (`forge-gui*`). The user's public line (Discord 09-16) was one patch at a time; two in
   disjoint areas keeps that spirit while a stalled review does not idle the stream.
7. **Evidence in the description, not in the diff:** the repro (seed, card, turn), the CR rule,
   the before / after; a perf PR carries a game-count read on stock heuristic play (what
   upstream's users see), not on our bridged scan.
8. **Design-shaped items go to Discord `#contribution-questions` first** and become a PR only
   after a maintainer nods (the survey's house rule; issues are never the venue).

### Tier 0 — the warm-up: stock bugs under 30 lines, in this order

| # | Fix | Where it lives today | Diff | Test | State on upstream tip |
|---|---|---|---|---|---|
| 0.1 | **Cabal Coffers cancel-refund** (`ManaRefundService.refundManaPaid` ignores `am.undo()`'s result and recurses anyway; CR 728.1 says reversal is all-or-nothing down the chain) | unbuilt ([playable worklist item 10](playable-fork-worklist.md)) | ≈ 5 lines | in the existing `ManaRefundServiceTest` (Swamps + Coffers, cancel after chaining) | bug present, file untouched since the pin |
| 0.2 | **`ComputerUtil.chooseTapType` STATION guard** (the power filter shrinks the list under `amount` after the size guard passed; IndexOutOfBounds) | fork `3fa6d200f4` | 7 lines | `StationTapCostTest` (fail-first, exists) | bug present at `ComputerUtil:701` |
| 0.3 | **Quest all-colors starting pool is empty** (`BoosterUtils.populateBalancedFilters` multiplies by the non-selected colors) | playable `692d166633` | 9 lines | `QuestStartingPoolTest` (54 lines, exists) | bug present, file untouched |
| 0.4 | **`ChooseSourceEffect` unbounded re-ask** on a controller that answers null (the AI's `NeedsPrevention` chooser outside combat; 150K asks, 65 min on the Build 2 arm) | fork `b482528552` | 20 lines | to write: a stub controller returning null | `do … while` still at `ChooseSourceEffect:131` |
| 0.5 | **`GameCopier` effect-source links for every copied card** (command-zone Effect cards — Prepared spells, impulse grants — resolved `EffectSource*` empty in copies; the MayPlayPlayer `.get(0)` crash class) | fork `ffbecf7869` | 14 lines | `EffectSourceCopyTest` (exists) | bug present; a #11203 follow-up in the same file |

Order rationale: 0.1 is human-visible in the GUI and rules-backed, the strongest opener; 0.2 and
0.3 are one-screen diffs with tests already written; 0.4 changes what the engine does when a
controller cannot answer, so it goes after two clean merges; 0.5 reopens the #11203 thread with
tool4ever and leads into Tier 4. Interleave: 0.1 (engine) with 0.3 (GUI), then 0.2 with a
Tier 3 GUI item, and so on under rule 6.

### Tier 1 — the AiCache series (talor's request 09-16, TRT's condition the same day)

- **1.1 The AI block-legality cache on `AiCache`** — talor author, us co-author. The fork's
  version (`8044e36366` + `6f5e1643b2`, 259 lines against the tip) keeps two identity maps on
  the controller: pure-pair legality that survives combat mutations, and context legality
  (lure, max blockers, capacity) cleared on every mutation. `AiCache` today is one global
  string-keyed multimap, linearly scanned, cleared once per `chooseSpellAbilityToPlay`, with its
  own TODO "add different scopes + staleness indicator". The PR is a rewrite of the storage,
  not of what is cached: `AiCache` gains the one scope the TODO names (a scope handle cleared by
  its owner — here `assignBlockers` per combat mutation for the context entries, per invocation
  for the pair entries), and the block cache is its first user. **Rebuild on the tip:** upstream's
  09-24 "Code cleanup" (`fb3cc67c56`) reshaped the same method region again (66 lines), on top
  of #11790. **Re-measure before proposing:** talor's 500-game read (−15.6% CPU, faster in
  478/500, determinism 500/500) was on his storage; `AiCache`'s linear scan may eat part of it —
  if the gain survives, that is the description; if it does not, the number is the evidence
  for a keyed lookup inside `AiCache`, which is the next small PR, not a reason to keep our own
  maps. The behavior-identity proof runs on a fork worktree jar (`harness --jar`, one worker),
  never on the pin.
- **1.2 The mana-source memo as the second `AiCache` user** (fork `1dd36f7342`, 56 lines,
  Anvil-shaped: a `ThreadLocal` armed by our scan under `-Danvil.scan.sourcememo`). Upstream's
  shape: `groupSourcesByManaColor` memoized for the candidate scan of one
  `chooseSpellAbilityToPlay` (every `canPayCost` per candidate rebuilds it), invalidated by the
  scope from 1.1 when a payment taps a source. **Gate:** a JFR read on stock heuristic play
  first — our 18% was the bridged scan's number; if the heuristic's own scan shows under ≈ 5%,
  drop the item rather than argue it.
- **1.3 `AiCache` staleness across games** (the M10 sweep OOM, fork `7716bbe44d`; standing rule):
  a seat that never enters `chooseSpellAbilityToPlay` never clears the map, so any external
  controller (manabrew, talor's harness, LordOfThePigs's runner) leaks one game graph per game.
  A clear on game end, or the scope from 1.1 keyed by game. Small; goes after 1.1 lands so it
  uses the same mechanism.

### Tier 2 — the determinism hooks, back as two PRs

#11285 (174 lines, two tests) was auto-closed 09-14 by the stale bot after Hanmac's one question
(07-19: is `InheritableThreadLocal` needed?) was answered (07-20) and nothing followed. Upstream
still has neither half: `MyRandom` is a static `SecureRandom`, `Match.preparePlayerZone` still
builds the library in `CardPool` iteration order before the shuffle.

- **2.1 The pre-shuffle sort** (`Match.preparePlayerZone`, 9 lines + `PreShuffleDeterminismTest`).
  Behavior-invariant (a uniform shuffle of sorted input); the argument is upstream's own
  `sim -s <seed>` (#11365): a seeded run should not depend on a hash map's iteration order
  across JVM and library versions. manabrew is the co-consumer to name.
- **2.2 Per-thread `MyRandom`** (31 lines + `MyRandomThreadLocalTest`). Hanmac's question is
  answered in the description up front (pooled threads vs dedicated spawns; why inheritable),
  and floated on Discord to him before the PR opens, so the review starts past it.

Sequenced after Tier 0 has two merges — this is the pair that needs credibility, and it is the
pair a maintainer already engaged with.

### Tier 3 — playable-branch GUI fixes, one per PR, as the GUI slot's fillers

In order of size; all stock bugs, all on files upstream has not touched since the pin unless
noted. None touches the engine.

| # | Fix | playable commit | Diff | Note |
|---|---|---|---|---|
| 3.1 | ItemManager context menu offset when the screen is embedded (mobile-dev shell; identity on phones) | `10c22003df` | 12 lines, no test | needs a before / after screenshot |
| 3.2 | `FTextField` CHANGE fires per keystroke; the online chat sends a network message per event (per-keystroke chat is broken on master today) | `881207ed27` (half) | 16 lines + 8 opt-in call sites for the local search filters | split from 3.3 |
| 3.3 | Net lobby team-selection echo (the wire listener drops the panel index; the server applies to the sender's slot) | `881207ed27` (half) | ≈ 25 lines | rebase over #11942 (disjoint hunks: icon refresh vs the team combo) |
| 3.4 | `RestartUtil` never relaunches (one command string through `Runtime.exec(String)`: quoted binary, paths with spaces) | `57e345f922` | 133 lines + a 57-line test | the largest here; offer the minimal `ProcessBuilder` form and keep the test to the two failing shapes |
| 3.5 | Nested `Graphics` transforms compose (`startRotateTransform` `idt()`s the live matrix; the sideways stack's items do not draw) | `c8ebbbd813` | 16 + 12 lines | **re-port**: upstream touched `Graphics.java` five times since the pin (shader work); pixel-identical at 90° is the safety argument; float it to the mobile maintainer first |
| 3.6 | Tapped-card hit-test by inverse rotation (`RotatedRect`; the 180-rotated field's hit-box sits h−w off the drawn card) | `7d64eebfe3` `50b19c529a` `c79b80868d` | 101 + 48 lines | after 3.5; the test trimmed to the 90° bit-identity case + the 180° bug case |

Held back from this tier: `StorageNestedFolders` (dead code upstream; only with a deck-site sync
PR), the whose-action tracking (`AwaitingInput`, 10 files — a feature, Tier 5), custom sleeves,
the tap-angle preference (Tier 5).

### Tier 4 — the blessed one: `GameCopier` → `GameSnapshot`, staged small

tool4ever's merge note on #11203 framed the duplication as debt whose removal "should also help
with your project"; that is the one large direction with a maintainer's name on it. Four PRs,
each reviewable alone, in this order:

- **4.1 The snapshot path's foretold restore** — `GameSnapshot:482–483` are still commented out
  (`setForetold` / `setForetoldCostByEffect`); the effect-card wiring is already there (#11401
  calls `copyEffectCardsToSnapshot`). A two-line fix with a test.
- **4.2 The `advanceToPhase` delegation gap** — `makeCopy(advanceToPhase, aiPlayer)` ignores the
  phase on the snapshot path (upstream's own TODO).
- **4.3 The switch** — simulation copies on the snapshot path by default
  (`EXPERIMENTAL_RESTORE_SNAPSHOT`), gated by forkcheck: the 500-game copy-vs-original digest +
  the twin determinism gate on a fork worktree jar, the 58-seed deterministic-divergence set
  (`run-20260812-fixedhash`) read on both paths. **Box time:** forkcheck is CPU-only and runs at
  nice 19 beside the big run, but it perturbs throughput; schedule it in a maintenance window.
  manabrew's restore-in-place consumer is the second voice on the thread.
- **4.4 Delete the duplicated copy logic** in `GameCopier`.

Starts when Tier 1.1 has landed (the same reviewer pool), coordinated on the PR thread as
volunteered 07-11.

### Tier 5 — Discord first, no PR until a maintainer nods

- **The engine-side combat legality surface** (Jetz 09-15: legality lives in the GUI module,
  relocation desirable but large). The small entry point: a `forge-game` validator for a block
  declaration / a damage assignment for any controller. What we carry: the block requirement
  fixed point and the `MinMaxBlocker` bounds in `forge-ai/.../anvil/CombatRealizer` (fork-side,
  Anvil-shaped; the upstream version is written fresh in `CombatUtil`). After Tier 4; khaliostr's
  `forge-engine` module is the same direction from the other end.
- **The 09-14 perf trio** (the LKI copy recomputing a full view per event; the copier's
  `CardFactory` rebuild; the per-event replacement scan in `cantHappenCheck`). Each needs a
  stock-Forge profile first (#11916's shape: cheap checks before expensive ones).
- Features with user pull: the tap-angle preference, Android incremental asset updates (never
  say "delta" there), deck-site account sync, whose-action tracking.
- Positions to hold, not PRs: evaluation-loop budgets (count-based, flag-gated, off by default);
  the host as an authoritative referee (multiplayer-hardening's open design question).

### Struck from the queue (verified on the tip, 09-27)

- **The monarch / initiative effect-card copy fix** — upstream carries the zone guard
  (`Player.mapEffectCard`: an effect card in no zone is left unset); **`getMonarchSet`'s
  inverted ternary was fixed by Hanmac on 09-25** (`8cd226407b`). Nothing to submit.
- #11916 (khaliostr's), the `FCollectionTest` fix (upstream's own), the hardening reports 1, 2
  and 4 (merged); the two declined hardening findings (never resubmit).
- **#11457 (chat rate limiting) stays parked** — open, mergeable, MostCromulent: "solving a
  problem that doesn't actually exist in practice"; tool4ever: reconsider when lobbies are
  broader. Do not chase; if the stale bot closes it, let it.
- The six load-dependent pilot crashes (#11161 covers the class), the `StackOverflowError`
  recursion class (no reproducing trace), the fireball SVar rename (does not reproduce).

### Cadence

The big run is four to six weeks. Small fixes have merged in about two days when a maintainer
picked them up (the hardening reports, #11203 in two days after review) and stalled for weeks
when none did. Tier 0 fits in the first three weeks under rule 6; Tier 1.1 starts as soon as
talor is on board and runs beside Tier 0's tail; Tier 2 opens after two Tier 0 merges; Tier 3
fills the GUI slot throughout; Tier 4 begins when 1.1 lands. Mechanics: `../forge-upstream`
tracking `upstream/master`, one branch per PR pushed to `origin` (Tyrathalis/forge), PRs opened
against Card-Forge/forge; the fork's `test-11161`-style verification branches are the model.

### The 10-05 review — what changed since the plan was written

**Verdict: Tier 2 collapses into keeping #11285 alive as one PR (the maintainers reopened it
themselves); three engine bugs found since 09-27 join the queue — the `canRegenerate` recursion
(now with a trace) and the MDFC command-zone phantom cast as Tier 0 items, the copier's token
mapping as Tier 4 evidence; everything else in the plan stands.** Upstream master moved from
`2ccbbb0132` to `837195889f` in the meantime; the per-item "state on the tip" column is re-swept on
the first PR day, not here.

- **#11285 was reopened by tool4ever on 10-05** (label `keep`, review requested from Hanmac at
  12:24 UTC). Hanmac's one new comment (12:26): the CardPool section part "will probably be
  reworked later anyway" — he wants `Map<Object, Integer>` to become a `Multiset<Object>`. The PR
  is still a draft, mergeable against today's master, and upstream has not touched `Match.java`
  or `MyRandom.java` since the PR's base, so no rebase is forced. What his rework means for the
  hunk: the sort is `ordered.sort(Entry.comparingByKey())` over `Map.Entry<PaperCard, Integer>`; a
  `Multiset`'s entries are `Multiset.Entry<E>` (`getElement` / `getCount`), so the hunk changes
  shape with his change but not meaning (sort the elements by `PaperCard`). The plan's Tier 2
  split into two PRs is withdrawn: **answer Hanmac on the thread (the sort survives the Multiset
  as "order the elements"; offer to re-cut the hunk on his rework or let him fold it in), take the
  PR out of draft, and leave the `InheritableThreadLocal` answer of 07-20 as the standing
  position.** The `keep` label is read as the stale-bot exemption; rule 5's day-25 ping still
  applies to the review itself.
- **Tier 0.6 — the `canRegenerate` ↔ mana-payment recursion** (`StackOverflowError`, 09-29 trace;
  the 09-27 plan struck this class as "no reproducing trace" — un-struck). The cycle:
  `ComputerUtilMana.payManaCost → chooseManaAbility → checkForManaSacrificeCost →
  chooseSacrificeType → shouldSacrificeThreatenedCard → predictCreatureWillDieThisTurn →
  combatantWouldBeDestroyed → canDestroyBlockerBeforeFirstStrike → ComputerUtil.canRegenerate →
  canPayCost → canPayManaCost → payManaCost`, 26 turns in the captured frames; the conjunction is a
  first-strike combat with a sacrifice-for-mana source on the paying side (Spider-Man 2099 vs
  Fantasticar). Upstream code, identical in both jars; ≈ 0.04% of games. The fix is a re-entrancy
  guard in `ComputerUtil.canRegenerate` (or `shouldSacrificeThreatenedCard`) that answers the
  conservative value when re-entered from a mana payment, with a test that builds the conjunction.
  Under 30 lines; goes after 0.2 in the engine slot.
- **Tier 0.7 — the MDFC commander back-face phantom cast** (10-05, the ADR-0122 agreement
  corpus; fork test `OptionMaskCommandZoneTest`, `94229a0c8a`, is the evidence). Two parts:
  (a) `canPlayAndPayFor` tests payability on `Spell.getAlternateHost`'s LKI copy, which carries no
  zone, so `calculateManaCost`'s cast-from lookup finds nothing and the commander tax never enters
  the test; (b) the real payment then charges the tax, fails, and is never unwound — the card
  strands in the stack zone with every land tapped and the mana floating. Part (a) is the PR:
  resolve the cast-from zone from the real host when the alternate host has none (one method,
  one test from the fork's). Part (b) is a design question (where a failed cast's payment is
  reversed) — Discord first, Tier 5.
- **Tier 4 evidence — the copier cannot map tokens under simulation** (10-03, the baseline
  reads' `simfull` arm: `GameCopier.find` "Couldn't map Construct Token", a `RuntimeException`
  inside `simulateUpcomingCombatThisTurn`, 4 of 7 games; the other workers died of heap OOM).
  `find` falls through to the exception whenever `cardMap` lacks the object, and the snapshot path
  (`snapshot.find`) is the branch that would not. Not a Tier 0 fix: file it as the repro on the
  Tier 4 thread when 4.3 opens (the switch to the snapshot path is what fixes it), not as its own
  PR. Stock simulation AI is what upstream's users run, so the report carries weight on its own.
- **Setup still owed:** `../forge-upstream` (rule 4) does not exist yet — create it from
  `upstream/master` on the first PR day. Talor's Anvil PR #5 (device selection) is handled on the
  Anvil side (adapted and credited, as #8 was), not here.

## Engine crashes — 50K pilot `d3pilot-20260704-175219` (fork `ca76c842a8`, 2026-07-06)

7 crashes in 50,000 games. All games' obs frames are readable; policy labels
usable (40.9K across the 21 readable crash+hardcap games), value-excluded via
`status`.

| game | seed | exception | turn | decks | profiles |
|---|---|---|---|---|---|
| 9204 | 5945958510859883103 | ConcurrentModificationException | 21 | dc-864165 vs dc-864162 | Experimental/Experimental |
| 9321 | 9091511573053637269 | ConcurrentModificationException | 31 | dc-864378 vs dc-863782 | Cautious/Reckless |
| 23533 | 1237691297111091176 | ConcurrentModificationException | 20 | dc-864206 vs dc-864589 | Cautious/Experimental |
| 39429 | 4871274615174445432 | ConcurrentModificationException | 25 | dc-864589 vs dc-864793 | Reckless/Cautious |
| 38257 | -3478740822025787825 | StackOverflowError | 17 | dc-863788 vs dc-864788 | Reckless/Default |
| 24846 | 7953943506196291359 | ArrayIndexOutOfBoundsException | 28 | dc-863786 vs dc-864922 | Default/Reckless |
| 7122 | 3723828607195549218 | NoSuchElementException | 41 | dc-864377 vs dc-864561 | Reckless/Default |

Notes (replay triage, 2026-07-06):
- **6 of 7 do NOT reproduce solo** (all CME + ArrayIndexOOB + NoSuchElement
  replay decisive on the pinned jar) — load/timing-dependent thread races,
  not seed-determined engine bugs. **Upstream `1f0a3e0815` (#11161, merged
  2026-07-06) fixes exactly this class**: parallel mustAttack Combat mutation
  (unsynchronized `addAttacker` → CME + silently dropped attackers) and the
  non-volatile `timeoutReached` cancellation flag (on JDK 20+ the ONLY
  cancellation signal — a wedged-eval-thread mechanism relevant to our
  runaway-frame class and timeout-pass tail). **Do not file these upstream;
  verify statistically instead**: pilot baseline ~1.4 CME/10K games under
  w=16 load; the post-bump crash census should read ~0.
- **38257 StackOverflowError reproduces deterministically** — solo, both on
  the pinned jar and on a #11161-patched build (same turn 17, ~36 s), so
  #11161 does not cover it. **This is the one genuine filing candidate.**
  Breadcrumbs: "Spider-Man 2099 … [Couldn't add to stack, failed to target]"
  immediately precedes the crash; Lumra, Bellow of the Woods also in play.
  The runner's catch doesn't print the stack — capture it with an
  instrumented build when filing.
- **#11161 is the anchor for the next dataset-boundary fork bump** (after
  d6ext completes or its stopping rule fires — never mid-run). It should
  also shrink ADR-0002's nondeterminism floor (the races are a same-seed
  divergence source) and adds a stack-dump-per-AI-timeout that turns the
  slow-tail seeds into log-diagnosable profiler samples. Cherry-pick applies
  cleanly to our fork: branch `test-11161` (verified building + playing).

## Open upstream PRs — monitor for maintainer feedback

- **[#11457](https://github.com/Card-Forge/forge/pull/11457) chat rate limiting — OPEN, parked** (mergeable; MostCromulent 08-03: a problem that does not exist in practice; tool4ever 08-04: maybe when lobbies are broader). Not chased (user, 08-31).
- **[#11285](https://github.com/Card-Forge/forge/pull/11285) determinism hooks — CLOSED 09-14 by the stale bot**, no maintainer verdict (Hanmac's 07-19 question answered 07-20, then silence). Upstream still has neither half. Returns as the plan's Tier 2 (two PRs).

- **[Card-Forge/forge#11203](https://github.com/Card-Forge/forge/pull/11203)
  — GameCopier state-fidelity fixes (PR #1): MERGED 2026-07-12** by
  tool4ever (approved + merged, merge commit `1922ce411a`; approval note:
  "acceptable — the Copier/Snapshot duplication is a longer technical debt
  (and getting rid of that should also help with your project)").
  **The flagship upstream contribution's first layer is upstream** —
  submitted 2026-07-10, first review 07-11 (CHANGES_REQUESTED on
  architecture, substance accepted), scoped-PR-plus-follow-up proposal
  accepted, merged 07-12. Our proposal read exactly as intended: this PR =
  the bug-fix layer for the default path; the consolidation follow-up
  (below) is now maintainer-blessed. On the next fork rebase (anchor
  #11161, dataset-boundary event) these fixes return to us from upstream —
  drop our fork-local copies then. Worktree `../forge-pr1` can be removed.
  History: submission 2026-07-10; review + [reply](https://github.com/Card-Forge/forge/pull/11203#issuecomment-4946992438) 2026-07-11.

## Queued PR candidate — effect-card copy fix after monarchy/initiative transfer (found 2026-07-29, M4 D2 drill sweep)

**STRUCK 2026-09-27 — upstream carries both halves:** `Player.mapEffectCard` leaves an effect card in no zone unset (the snapshot rework, #11401 era), and Hanmac fixed the `getMonarchSet` ternary on 09-25 (`8cd226407b`). Nothing to submit.

- **The bug (fork-fixed `6d728677d1`, upstream still has it):**
  `Zone.remove()` never clears the removed card's `zone` field, so after a
  monarchy (or initiative) transfer the ex-holder's cached
  `monarchEffect`/`initiativeEffect` card keeps a stale zone pointer.
  `Player.copyEffectCardsToSnapshot` (our #11203-merged method) guarded on
  the pointer (`getZone() != null`), so `GameCopier.makeCopy` of ANY game
  whose crown/initiative ever moved throws `Couldn't map The Monarch`.
  Fix = guard on zone-list membership (`!effect.getZone().contains(effect)`).
- **Evidence bundle ready:** 44/578 curated drill positions failed all K
  completions with exactly this signature (deck-diffuse,
  transfer-correlated); `MonarchTransferCopyTest` ×2, both validated
  failing first; desktop suite 299 green.
- **Bundle in the same PR:** `Player.getMonarchSet()` inverted ternary
  (`monarchEffect == null ? monarchEffect.getSetCode() : null` — NPE when
  null, null when set; the initiative twin is written correctly). Callers:
  `Game.java:985/987` monarch-leaves-game path. Not fixed fork-side (game
  path; cosmetic set-code only; boundary discipline).
- **Framing:** natural follow-up to #11203 (same method, sibling defect);
  also strengthens the consolidation argument (the snapshot path needs the
  same membership rule). Simulation-only blast radius ⇒ small review.

## Diagnosed crash class — StaticAbilityContinuous MayPlayPlayer `.get(0)` on empty (2026-07-29, upgrades the carried post-rebase IndexOutOfBounds item)

- **Deterministic repro in hand:** 9/578 M4 drill positions fail every
  `GameCopier.makeCopy` with `IndexOutOfBoundsException: Index 0 out of
  bounds for length 0` at `StaticAbilityContinuous.applyContinuousAbility:900`
  — `AbilityUtils.getDefinedPlayers(affectedCard, params.get("MayPlayPlayer"),
  stAb).get(0)` resolves EMPTY while the copy re-applies continuous effects
  (leading hypothesis: statics re-applied before remembered/defined objects
  are wired — copy-ordering, the consolidation follow-up's home turf).
  Same exception class as the carried normal-game item (2/2,000 games,
  `dc-863943` seed-pinned) — likely the same `.get(0)` reached by a rarer
  in-game path. Repro rows: `data/runs/drill-crash2-rows.jsonl` (9 decks,
  deck-diffuse; MayPlay statics = impulse-draw/play-from-exile effects).
- **Not fixed yet (deliberate):** the honest fix wants the ordering
  question answered, not a blind empty-guard; scope for its own session or
  fold into the consolidation PR. Drill accounting carries the 9 as
  excluded-with-cause meanwhile (1.6% of the map).
- **FIXED (2026-08-11, fork `b361dfcb8f`, D3 stability pass).** The
  ordering hypothesis was WRONG (remembered wiring precedes the copy's
  `checkStateEffects`); the real cause: `copyGameState` restored
  `setEffectSource` only inside its battlefield-only loop, so
  command-zone Effect cards (the Prepared mechanic's
  `MayPlayPlayer$ EffectSourceController` — 6 of the 16 repro decks carry
  Prepare cards) resolved `findEffectRoot` null in copies while the
  original kept its retained pointer. Fix: restore the link for every
  copied card whose source was also copied; no guard at the resolution
  site (a residual empty list stays a loud crash by design).
  `EffectSourceCopyTest` reproduces the field IndexOOB pre-fix, green
  post-fix; full desktop suite green. Upstream candidate (GameCopier).
- **The carried normal-game IndexOOB was a DIFFERENT class — also FIXED
  (2026-08-11, fork `9f0a2c0886`).** Traced replay of run13-finalarm-s0
  g351 captured the stack the class never had: `ComputerUtil.chooseTapType`
  runs the STATION power filter (strips power ≤ 0) AFTER the
  size-vs-amount guard, then indexes past the shrunk list — dc-863943's
  correlation is Synthesizer Labship stationing over 0-power artifact
  boards (Krang deck). Fix: re-check after the filter, return null
  (AiCostDecision maps null to a clean payment decline). Same-class
  hypothesis with MayPlay explicitly falsified (reproduced identically on
  the GameCopier-fixed jar; normal games never enter makeCopy).
  `StationTapCostTest` fail-first pair; g351 replays to completion on the
  fixed jar (won turn 15 vs crash turn 7). Stock-Forge path — clean
  upstream candidate.

## Diagnosed hang class — targeting-retry wedge in drill completions (2026-07-30/31, d6-run10; forensics QUEUED post-run)

- **Signature:** a drill completion loops "Spider-Man 2099 — [Couldn't add
  to stack, failed to target]" indefinitely, writing ~1 GiB of raw obs
  before RAW_CAP truncates; the wall-clock burn hard-caps the parent game
  and abandons its thread (the cascade that killed the d6-run10 driver
  before the stale-thread guards + ingest quarantine landed, fork
  `7249a41b60` / Anvil `eb6381f`). A *hang*, not a crash — third failure
  mode beside the monarch (fixed) and MayPlayPlayer (diagnosed) classes.
- **Deterministic and policy-independent:** the iteration-9 re-run re-hit
  the same game (734, `run9-finalarm-s0`) at the same fork point under a
  DIFFERENT drill checkpoint — the wedge does not depend on the model's
  action path (heuristic opponent or engine state itself). Recurs every
  selection-cycle rotation at the same games; cost now bounded (quarantined
  frame + lost fork point + ~10 min wall per event) but recurring.
- **Repro recipe:** one-line drillfile at game 734's selected turn, K=1,
  `-Danvil.crash.trace`, obs on — minutes to the wedge.
- **Forensics plan (post-run session):** (1) identify the looping actor
  (heuristic vs model seat) and the exact retry loop; (2) the
  copy-fidelity differential — does the same cast succeed in the MAINLINE
  at the same state? loops-only-in-copy ⇒ our GameCopier territory, likely
  a 4th member of the copy-state family (test alongside the MayPlayPlayer
  ordering question — same session could resolve both); loops-in-both ⇒
  stock AI infinite-loop bug, clean upstream filing (bundle with the
  queued monarch PR); (3) answer why per-completion ROLLOUT_TIMEOUT's
  `setGameOver` didn't stop the loop before 1 GiB accumulated — either the
  engine loop never re-checks game-over (upstream-relevant) or our
  watchdog has a blind spot (ours to fix).
- **D3 stability-pass disposition (2026-08-11): CLOSED AS BOUNDED,
  repro unreachable.** The era-exact repro cannot be rebuilt: the wedge
  state was reached by ARGMAX mainline replay, retired by the ADR-0052
  `--sample-mainline` fix — a fresh replay of g734 under current serving
  ends turn 27 without reaching the drilled turn (solo-replay drift, as
  documented). Question (3) answered by code reading: `mainGameLoop` AND
  `mainLoopStep` both check `isGameOver` per step (PhaseHandler:1034,
  :1121), and the priority do-while caps at 999 for AI seats and then
  passes priority — so the watchdog's `setGameOver` is consulted between
  steps, and the wedge must live INSIDE a single controller/resolve call
  (consistent with the recorded AI-eval-thread timeout dumps: deep
  blocker-evaluation recursion under cost adjustment). No fix without a
  reproducing state; the class stays cost-bounded by the landed guards
  (owner-bound fork frames + ingest quarantine + Obs RAW_CAP + census
  rawcap) and VISIBLE (360s ms rows + cap markers). Watch-list item: if
  a wedge row reappears in the corrected-era drill campaign, re-open
  with `-Danvil.crash.trace` armed in that run's ANVIL_EXTRA_JVM_OPTS.

## Diagnosed divergence class — deterministic copy-state divergence, post-rebase era (2026-08-12, ADR-0055 annex)

- **Signature:** 58/500 forkcheck games diverge copy-vs-mainline,
  **deterministically**: identical game set across three runs, two jars
  (`46c0c0893e` prefix, `d798917ae5` ×2), and both identity-hash modes
  (FIXED_HASH pair) — not hash-iteration, not wall-clock. Up from the
  7.0% prior-era rate; statics 0.
- **Repro:** the 58 seeds in
  `data/forkcheck/run-20260812-fixedhash/results.jsonl` (status =
  divergence) — each row carries divergenceTurn + first-divergence
  sample (library/zone/life symptoms; root mechanic not yet named).
- **Hypothesis:** rebase-introduced state GameCopier does not carry —
  #11436's depth-zero-simulation bookkeeping is the prime suspect;
  same family as the effect-source gap (`b361dfcb8f`).
- **Forensics slot:** with/after the GameCopier→GameSnapshot
  consolidation below (trace-diff the recorded snapshots at
  divergenceTurn). Does not reopen the D3 boundary.

## Queued follow-up PR — GameCopier → GameSnapshot consolidation (volunteered 2026-07-11, maintainer-blessed at #11203 merge 2026-07-12)

Make the snapshot path own simulation copies and delete GameCopier's
duplicated copy logic (maintainer-requested direction on #11203; tool4ever's
merge note explicitly frames the duplication as technical debt whose removal
"should also help with your project"). Known work items from the archaeology:

- **Snapshot path carries sibling bugs of two PR-#1 classes:**
  `setForetold`/`setForetoldCostByEffect` commented out in
  `setCardInCopiedGame` (face-down/foretold state drop); only commanders
  re-wired — the 7 field-managed effect cards re-create lazily + orphan the
  copies (call the shared `Player.copyEffectCardsToSnapshot`).
- **Delegation gaps:** `GameCopier.makeCopy(advanceToPhase, aiPlayer)`
  ignores `advanceToPhase` on the snapshot path (upstream TODO);
  `PRUNE_HIDDEN_INFO` (dormant, default false) has no snapshot equivalent.
- **Validation = forkcheck**: 500-game copy-vs-original digest baseline +
  twin determinism gate, run with simulation copies switched to the snapshot
  path. Sequencing: after D2/D3 land (it is not on the M2 critical path);
  coordinate timing with the maintainers on the PR thread.

## Fork-local maintenance

- **`ForkFidelityCheck` lacks the headless uncaught-exception handler**
  (fork `67e55ba1c1` gave it to the AnvilRun worker path only): a startup
  failure (e.g. decision-server handshake) raises Forge's MODAL bug-report
  dialog and the process sits alive holding it — found 2026-07-17 when a
  mis-launched control run parked a dialog on the desktop overnight-capable.
  Apply the same handler at the forkcheck entry; fold into the next fork
  touch (no jar rebuild urgency — it only bites operators).

## Harvested from community archaeology (2026-07-16, Discord + repo dives — see [discord-ai-plotting-survey.md](discord-ai-plotting-survey.md))

- **Determinism-hooks PR (joint with manabrew, `witchesofthehill/forge` @ `d658cbc757`):**
  their entire fork patch is ~40 lines and nearly disjoint from our determinism
  surfaces — (a) `MyRandom` static → ThreadLocal (upstream `setRandom()` already
  exists; this fixes cross-thread contamination), (b) **`Match.preparePlayerZone`
  sorts the library by name before the shuffle** — the pre-shuffle order is
  `CardPool`/`ItemPool` ConcurrentHashMap iteration order, (c) an official
  static-ID-counter reset (they reflect into 7 private `maxId` fields today).
  **Verified 2026-07-16: our fork's `preparePlayerZone` (Match.java:200) has the
  unsorted CHM iteration** — our bit-identical-replay evidence was all gathered
  on one pinned JVM; a JVM bump or rebase could silently reorder pre-shuffle
  libraries. The sort is behavior-invariant (uniform shuffle of sorted input)
  but trajectory-changing for a given seed → **dataset-boundary item: fold into
  the #11161 rebase, not mid-run.** Bundles naturally with `b4efa5a7d7`'s
  shuffle→MyRandom drift item below; we're the natural author (post-#11203
  credibility), manabrew is the co-consumer. Contact: khaliostr/Anacleto/fedepoi
  on the Forge Discord #ai-plotting.
  **2026-07-17 update — the centerpiece went maintainer-led:** after our
  #ai-plotting reply, Hanmac filed
  [forge#11260](https://github.com/Card-Forge/forge/issues/11260) ("Move
  nextId statics into Game methods", self-assigned + tool4ever +
  MostCromulent). Our design-input comment is posted (sibling-statics
  enumeration: SpellAbility, SpellAbilityStackInstance, StaticAbility,
  ReplacementEffect, Trigger, CombatView; the counter-must-travel-on-
  copy/snapshot constraint from #11203; single-shared-counter alternative;
  forkcheck verification offer). Our authored surface narrows to ThreadLocal
  MyRandom + pre-shuffle sort + tests. M3 plan D3 tracks this
  ([m3-plan.md](m3-plan.md)).
- **GameSnapshot restore has a live downstream consumer**: manabrew's
  interactive host uses `new GameSnapshot(game)` + restore for mana-payment
  cancel/rollback (ManaBrewInteractiveController.java:1234/1938/2033). Second
  voice + test consumer for the consolidation follow-up — and it exercises
  *restore-in-place*, the half forkcheck doesn't gate. Mention on the PR thread
  when the consolidation lands.
- **Card-script claim RESOLVED — does not reproduce (2026-07-17)**: manabrew's
  `fireball.txt` / `officious_interrogation.txt` "IncreaseCost→RaiseCost SVar
  misname" fix (their `d658cbc757`) probes clean on the stock script:
  `FireballRaiseCostTest` (fork commit `023e8c5da9`, sim-test) shows the
  per-extra-target raise applies correctly on the AI cost-calculation path
  (X=2: 1 target CMC 3, 2 targets CMC 4). `CostAdjustment.java:~155`'s
  collision guard pre-resolves the SVar from the static as designed; script
  unchanged upstream for years. Likely a misdiagnosis or a symptom in their
  harness's own payment path. **Keep the rename OUT of any joint determinism
  PR**; the test is available to contribute upstream as a regression test.
- **forkcheck false-positive checklist** (from manabrew's parity whitelists):
  summoning-sickness on non-creatures (Java keeps it on lands from graveyard —
  no gameplay effect per CR 302.6), transient token lifetimes in
  graveyard/exile/stack, cleanup-discard zone for Leyline-of-the-Void-class
  replacements (their sole per-matchup ignore — a real Forge bug: cleanup
  discards go to graveyard instead of exile under Leyline). Useful when the
  consolidation forkcheck run produces digest diffs.

## Queued idea — Android incremental asset updates (2026-07-18)

User pain point (weekly app updates each force the full ~160MB assets.zip
redownload) + Chronicle-relevant (collection mode is res-heavy). Archaeology:

- **No recorded discussion of why delta updates don't exist.** GitHub searches
  (issues + PRs: "incremental update", "delta assets", "redownload",
  "assets.zip") = zero on-point hits; Discussions disabled on the repo. The
  `AssetsDownloader.java` history is pure accretion of the whole-zip flow —
  repeated iteration on *prompting/versioning* (release tags, snapshot 23-hour
  allowance, version.txt/build.txt reconciliation, incomplete-res recovery)
  but never on *transfer granularity*. Conclusion: nobody decided against it;
  it's simply unbuilt. Per house survey lore, design conversations happen in
  Discord/PRs — float the design in Discord before writing code.
  **Discord cross-check (user perusal, 2026-07-18): confirmed** — "delta" on
  the server refers to netplay delta patching (reportedly troublesome —
  unrelated system, avoid the term collision when pitching); download talk is
  all card images; no asset-delta discussion exists there either.
- **Constraint to preserve:** the mandatory-download-when-build-dates-mismatch
  semantics are correct (card scripts are engine-coupled; res+engine are one
  pinned unit — same invariant as our fork discipline). Delta changes the
  transfer, not the lockstep.
- **Implementation sketch (two options):** (a) CI-generated manifest of
  per-file SHA-256 + sizes published beside assets.zip; client diffs local res
  and fetches changed files. Requires per-file hosting. (b) **Zero-hosting-change
  option: HTTP Range requests into assets.zip itself** — fetch the zip central
  directory (tail range), diff entry CRCs/sizes against local files, download
  only changed entries by offset. GitHub releases support Range. Needs a
  fallback to full download when the server ignores Range (snapshot host TBD).
  Either way typical weekly updates drop from ~160MB to single-digit MB.
- Both release and snapshot channels benefit; snapshot users (daily builds,
  23-hour update allowance) hit the pain hardest.

## Queued idea — deck-site account sync (Archidekt/Moxfield, 2026-07-18)

User wish; smaller lift than the asset-delta item. **Most of it already
shipped**: PR #10570 (merged, in forge-2.0.13) = per-deck URL import via the
sites' JSON APIs with edition+collector-number fidelity, exposed in the
desktop deck chooser (`FDeckChooser` URL panel) *with a per-deck reload
button* (providers: `forge-gui/src/main/java/forge/deck/
{Archidekt,Moxfield}DeckUrlProvider.java`, `DeckUrlLoader`). In flight:
#11045 (TappedOut/MTGGoldfish providers), #11044 (wire into the deck
importer). **Remaining gap = the actual PR**: (a) account-level sync — link a
username, enumerate the user's decks (Archidekt has public owner-listing
endpoints; Moxfield's API is unofficial and permission-etiquette applies —
polite rate limits, consider contacting them), loop the existing providers
for bulk import/update; (b) mobile/Android exposure (current UI is
desktop-chooser-only). Risk is API etiquette, not engineering.

## Queued idea — quest all-colors starting pool is empty (2026-07-30)

`BoosterUtils.populateBalancedFilters` uses the NON-selected colors as the
repetition multiplier for preferred-color filters, so a new quest created
with the BALANCED distribution and **every** color selected
(B/U/G/R/W/colorless) builds zero color filters and `generateCards`
silently produces an empty starting pool — the quest starts with only the
snow-basics grant and the deck editor offers no cards. Any five of the six
colors works. Stock bug, both clients, any world/format. Found live
(user's Random Commander Commander quest); reproduced headlessly on both
the current-master playable build and the 5-week-old research pin. Fix on
the playable branch (`692d166633`): floor the multiplier at one pass;
`QuestStartingPoolTest` rides `AITest`'s card-DB init (all-colors case
validated failing first + two controls). Clean standalone patch.

## Queued idea — RestartUtil never relaunches (2026-07-30)

Stock `forge.util.RestartUtil.prepareForRestart` builds one command *string*
and hands it to `Runtime.exec(String)`, which tokenizes on whitespace and
honors no quoting: the `"java"` binary is exec'd WITH its quote characters
(fails outright on Linux), and any install path containing a space splits
mid-path — the failure is swallowed inside the shutdown hook, so every
desktop "restart" (both `FControl.restartForge` on the Swing client and the
mobile-dev adapter's `restart()`) just exits without reopening. Found live
when our delta updater's res-only apply path called it (install dir
".../Forge Fork/"). Fix on the playable branch (`57e345f922`): rebuilt on
`ProcessBuilder` + argument list; jar launches derive the jar path from the
code source rather than re-splitting `sun.java.command`; trailing program
args recovered past the jar filename; unreconstructible commands return
false instead of relaunching garbage. `RestartUtilTest` (4 tests) rides
along. Clean standalone patch — no fork-specific coupling.

## Queued idea — mobile Graphics nested-transform composition fix (2026-07-28)

`Graphics.startRotateTransform` (forge-gui-mobile) idt()'s the live transform
matrix, so nested transforms never compose — an inner rotation silently wipes
its outer one, and `endTransform` restores to identity rather than the
enclosing transform. Every consumer of the shared-screen two-human layout is
affected: tapped cards in 180-rotated panels lose the outer 180 (masked at
stock's 90° by a hand-calibrated negation in `VCardDisplayArea.getTappedAngle`
— bare +θ ≡ true 180−θ composition only at θ=90), and the rotate-90 header's
nested children (the stack dropdown) draw at unrotated coordinates —
observed live as "the sideways stack doesn't display items". Fix on the
playable branch (`b65a74cc85`): transforms save/restore and compose (the
`Dtransforms` consumers only read the live matrix, so unaffected), negation
override deleted; pixel-identical at 90°. Found via the fork's configurable
tap angle, but the stack symptom is reachable in pure stock. Bundle with or
after the tap-angle pitch; pixel-identity-at-90 is the safety argument.

## Queued idea — StorageNestedFolders subfolder creation fix (2026-07-28)

`IStorage.getFolderOrCreate` has never worked in stock Forge:
`StorageNestedFolders.add` is a TODO stub (creates the directory, then throws
`UnsupportedOperationException("method is not implemented")`), and
`StorageImmediatelySerialized.getOrCreateSubfolder` constructs the child unit
on the **parent's** serializer, so even past the throw, items would save into
the parent directory. Dead code upstream today — no caller reaches it — but a
live API landmine; our deck-site sync was its first real caller and crashed on
first use. Fix (playable branch `ad9a9b89c2`/`195d245ae8`): route creation
through the existing load-time nested factory (child rooted at the subfolder,
with subfolder support of its own); `StorageSubfolderTest` pins it, validated
failing first. Same latent-correctness shape as the tap hit-test fix — small,
test-carried, no behavior change for any existing caller. Offer independently
of the sync feature.

## Queued idea — configurable tap angle (2026-07-26)

User wish (paper-like ~60–75° tap instead of a flat 90°). **No option exists,
and no prior discussion found** — GitHub issue/PR searches for "tap angle",
"tapped rotation", "tap angle rotation" all return nothing. Same conclusion as
the asset-delta item: nobody decided against it, it is simply unbuilt.

- **Current state = a compile-time constant on both UIs.** Desktop:
  `CardPanel.TAPPED_ANGLE = Math.PI / 2` (`forge-gui-desktop/.../view/arcane/
  CardPanel.java:89`), a `public static final double` consumed only by the tap
  animation (`view/arcane/util/Animation.java:203-212`). Mobile:
  `FCardPanel.getTappedAngle()` returns a literal `-90`
  (`forge-gui-mobile/src/forge/toolbox/FCardPanel.java:70`), consumed at three
  draw sites; the single override (`VCardDisplayArea:594`) only flips the sign
  for areas rotated 180°. Nearby prefs are unrelated:
  `UI_ROTATE_PLANE_OR_PHENOMENON`, `UI_ROTATE_SPLIT_CARDS`,
  `UI_ANIMATED_CARD_TAPUNTAP` (animation on/off, not angle).
- **Lift:** small — a new `FPref` (e.g. `UI_TAP_ANGLE`, default 90) threaded
  into one desktop constant and one mobile accessor, plus a settings entry on
  each UI. The existing `UI_ACTIONABLE_HIGHLIGHT_COLOR` pref is the shape to
  copy for a free-form (non-boolean) display setting on both UIs.
- **Wrinkle to check before pitching:** desktop's static image path rounds to
  the nearest 90° (`toolbox/imaging/FImagePanel.java`: "rotations are currently
  rounded to the nearest 90 degrees", `FImageUtil.getRotationToNearest`). A
  non-90 angle likely needs the animation/transform path to own tapped
  rendering rather than the pre-rotated image cache — verify whether the tapped
  card is drawn via the rounded image path or the AffineTransform path before
  scoping. Hit-testing also assumes the tapped footprint
  (`FCardPanel.renderedCardContains` adjusts width "to make room for tapping").
- Per house survey lore, float the idea in Discord before writing code.

**Wrinkle RESOLVED 2026-07-26 — it does not apply.** The nearest-90° rounding
lives in `FImagePanel`/`FImageUtil`, which is the **zoomer/detail** path
(`toolbox/special/CardZoomer`, split/planar image rotation). The battlefield
card is a different component: `CardPanel` holds a `ScaledImagePanel` (`:117`)
and `CardPanel.paint():307` rotates the **`Graphics2D` itself**
(`g2d.rotate(getTappedAngle(), …)`) before delegating to `super.paint(g2d)` — a
live `AffineTransform` at an arbitrary angle, with no image-cache rounding
anywhere on the path. **Arbitrary tap angles render correctly on desktop**; the
image path never sees the tap rotation. Desktop's tap animation
(`Animation.java:203-212`) is likewise already angle-generic — it scales off the
constant, so it needs no change beyond the constant becoming a preference.

The hit-testing half of that bullet **is** real, on both UIs, and is the actual
work — see the fork-side build plan, which sequences it first:
[playable-fork-worklist.md](playable-fork-worklist.md) item 5. Keep the two in
sync: the fork builds it, this entry pitches it.

**BUILT fork-side 2026-07-27** (`playable-qol` `d3bd019dc6`..`33d8c64b41`).
What the pitch can now say, with evidence:

- **The hit-test generalization stands alone as a correctness fix** and found
  a live bug while landing: on 180-rotated fields (local two-human matches)
  the mobile tapped hit-box sits offset by h−w from the drawn card (top ~40%
  of the card doesn't respond to taps). Shared `forge.util.RotatedRect` in
  `forge-gui` + a TestNG geometry test in `forge-gui-desktop` (bit-identity to
  the legacy boxes at 90° over dense grids) — upstreamable as its own small PR.
- **Pref as built:** `FPref.UI_TAP_ANGLE`, default `"90"`, discrete values
  90/75/60/45/30/15 (reuses `CustomSelectSetting`/`FComboBoxPanel`, no new widget
  class), defensive parse, localized in all nine languages, exposed in mobile
  SettingsPage, adventure SettingsScene, and desktop Graphic Options.
- Known cosmetic caveat for the pitch: at shallow angles desktop draws the
  tapped overhang OVER the right neighbour (Swing child paint order); mobile
  draws it under. Purely a <90° concern.

Per house lore: float in Discord before PRing; offer the hit-test fix
separately from the preference so the correctness fix isn't hostage to taste.

## Upstream drift watch (2026-07-10 sweep: pin `0bfdaa572f30` → `1eec01434e`, 57 commits)

Full-log review ahead of PR #1 assembly. #11161 covered above. Also relevant:

- **`2fa0705c78` (#11138): `MagicStack.thisTurnCast` changed type `Card` →
  `SpellAbility`.** This is the same this-turn state family as our residual
  13.4% divergence class (the documented GameCopier this-turn copy gaps). Any
  copier fix for the residual class must be authored against the NEW
  SpellAbility-typed representation, not our pinned Card-typed one — a fix
  written on the pin won't apply upstream. No Anvil fork code calls
  `getSpellsCastThisTurn` (checked 2026-07-10), so the API change is
  rebase-friction-free beyond the copier work itself.
- **`b4efa5a7d7` (#11172 branch): gameplay shuffle calls moved to `MyRandom`.**
  Our pin carries an unseeded `Collections.shuffle` in
  `GameAction.drawStartingHand`'s alternate-hand logic — a latent
  nondeterminism hole. Our determinism measurements (bit-identical replays,
  99–100% twin rates) say the path doesn't fire under our configs; flag if a
  future run config touches smoothed starting hands. Inherited at rebase.
  Side note: upstream demonstrably cares about seeded determinism — context
  for the fork-API flagship conversation.
- **Teacher-policy drift at rebase**: `211cb85ae4` (AI perf caching — checked:
  parameter-threading only, no new copy-fidelity surface), `17d882b784`
  (Discover AI), `c57a325ca2` (top-card reveal), `8d157a54c4` (animate
  targeting), `7a4bcbf7f1` (express-choice refactor). Post-rebase heuristic ≠
  the corpus teacher or arms opponent — rebase needs forkcheck + a fresh arms
  baseline (as the dataset-boundary rule already requires).
- Rest of the 57: card-script/edition content (pin isolates us), network/UI
  fixes (irrelevant headless), behavior-neutral perf.

## Already-known (from M0, ADR-0002)

- Fork static-corruption bug classes (two, seed-reproducible) — **FIXED in
  fork `42e15f4822` (2026-07-10)** along with card-id preservation; upstream
  PR #1 in assembly (cherry-picks clean onto `1eec01434e`, verified
  2026-07-10). Characterized in the forkcheck harness; before/after:
  statics 12%→0, divergence 50%→13.4% (`data/forkcheck/run-20260710/`).
- `GameCopier.clonePlayer` swaps non-AI controllers to heuristic AI on fork —
  **resolved without a code change** (2026-07-10): `AnvilLobbyPlayer extends
  LobbyPlayerAi`, so the instanceof check reuses it and forked games keep
  Anvil controllers (verified in play, forkcheck `-bridge`/`-grpc`). Nothing
  to upstream; the generic swap behavior remains a landmine for non-AI-derived
  controllers — fork-API-conversation material, not a PR.

- **Block realizer MinMaxBlocker gap (2026-07-17, §6c reconciliation dive):**
  min-blocker *restrictions* (menace, "except by three or more" —
  `MinMaxBlocker` statics) pass the D5 block realizer untouched (its repair
  covers *requirements* via the `mustBlockAnAttacker` fixed point only) and
  the engine silently discards the illegal block downstream — the model's
  declared block evaporates with no census record (verified: run3-i000 g269
  Hive of the Eye Tyrant single-block, g363 Troll of Khazad-dûm
  single-block). Fork fix: realizer checks `MinMaxBlocker` bounds and
  drops/re-asks under-strength blocks (census `dropped` then counts them).
  Until then the §6c reader-side derivation is the only accounting that sees
  this class. Small, serve-side, pairs with the block-drop re-ask follow-up.

## Upstream determinism convergence (2026-07-24, three merged PRs)

Three PRs merged upstream 07-24, all attacking classes we characterized in
M2 D1 — independent work (none reference #11285), complementary surfaces:

- **[#11360](https://github.com/Card-Forge/forge/pull/11360)** (liamiak,
  merged): hash-order iteration nondeterminism in AI decision paths —
  `ComputerUtil{,Cost,Mana}`, `AttackConstraints`, `ManaCostBeingPaid`,
  `TriggerWaiting`. Root-cause diagnosis matches our D1 twin-residual
  exactly (identity `hashCode` randomized per JVM launch; their measure:
  ~40% seed divergence on a reanimator deck). **This is the class behind
  our 1% twin-nondeterminism tail** (40x amplified under `-bridge` random
  policy); D1 bounded it, they fixed (some of) it.
- **[#11358](https://github.com/Card-Forge/forge/pull/11358)** (delebedev,
  merged): `TriggerWaiting.setTriggers` HashMap iteration — simultaneous-
  trigger order now preserved.
- **[#11365](https://github.com/Card-Forge/forge/pull/11365)** (delebedev,
  merged): `sim -s <seed>` CLI — seeded simulation runs upstream.

Consequences:

- **#11285 unaffected**: still MERGEABLE (no file overlap), still awaiting
  review; our per-thread MyRandom + pre-shuffle sort surface is
  complementary to all three.
- **D4 rebase dividend**: the rebase picks these up — re-measure the twin
  tail (`forkcheck -twin`/`-bridge`) expecting the hash-order residual to
  shrink; re-read the 67 repro seeds against the new baseline.
- **Technique harvest**: `-XX:+UnlockExperimentalVMOptions -XX:hashCode=3`
  (deterministic identity hashes) was liamiak's diagnostic — a natural
  forkcheck stress instrument to adopt (turns the hash-order class from
  probabilistic to reproducible). **ADOPTED 2026-07-25 (Anvil `47fea51`):
  `FIXED_HASH` mode in `scripts/forkcheck/run_forkcheck.sh`.**
- **Queued (2026-07-24, user)**: consider a comment on #11360 later —
  complementarity note (#11285's surface vs theirs), offer forkcheck twin
  data as validation, possible #11285 review nudge. Deliberately not sent
  same-evening.

## Queued 2026-09-07: `ChooseSourceEffect` unbounded re-ask on a null controller answer

- **Symptom:** `ChooseSourceEffect.resolve` wraps `chooseSingleEntityForEffect` in
  `do … while (o == null || o.getName().startsWith("--"))`. `ChooseSourceAi.chooseSingleCard`
  (`AILogic$ NeedsPrevention`) only answers from the stack or from unblocked attackers, so an AI
  seat that activates the ability with an empty stack outside combat returns null forever — the
  engine loops in one window with no priority pass (no turn/window cap can count it; only a wall
  clock ends it). Seen 09-07 on the M12 Build 2 dzla10 arm, game 989 (Dark Sphere, MAIN1, 150K+
  asks, 65 min); the heuristic never enters the state because its `canPlayAI` gates the activation,
  the learned policy picks from the legality mask and does.
- **Fix (fork, 09-07):** bound the re-ask at two attempts, then take the first real source; skip
  the pick when none exists. Behaviour-identical whenever the controller answers (forkcheck).
  Same shape as the earlier `Cabal Coffers` refund bug: engine code that assumes the AI's own
  gating happened. Upstream PR candidate; a unit test on a stubbed controller returning null.
- **Anvil guard (fork, same commit):** `Census.loopCheck` — consecutive identical callbacks per
  game past `anvil.loop.trip` (256) cap the game as a Draw with reason `loop:<method>` and the
  Surfaces force hooks answer the first option so any such engine loop exits; counted like a cap
  (the 0.5% tripline reopens repetition detection). A state-hash repetition detector at priority
  grants (model-driven no-progress cycles, bounded today by the window cap) is routed by name to
  the shakedown.

## Queued idea — an engine-side combat legality surface (2026-09-15, from #contribution-questions)

- **The opening:** Jetz (core) confirmed to Sudo_Dudo that combat / damage-assignment legality
  lives in the GUI module (`PlayerControllerHuman` + the cost / target `Input`s carry the
  validation), not `forge-game` — "not designed that way intentionally… it's just been that way
  since before the project was split into modules. Ideally any validation and legality stuff like
  that could be specified or checked entirely by the game module. But it's a lot of stuff to
  relocate in an elegant way." This is the field guide's finding from a maintainer
  ([forge-ai-field-guide.md](../forge-ai-field-guide.md): `CombatUtil.validateBlocks` runs for
  human input only; an AI-path controller can declare illegal blocks and the engine plays on).
- **What we already carry that fits:** the block requirement fixed-point (`mustBlockAnAttacker`,
  [ADR-0016](../decisions/ADR-0016-d5-closeout.md)) and evening 3's modern-rule damage
  enumerator family (the kill order realized as amounts by the lethal arithmetic,
  [ADR-0105](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)),
  both living fork-side because the engine offers no validated surface to a non-human controller.
- **Shape of the PR:** not the relocation (the "lot of stuff" Jetz means) — a small, tested
  `forge-game` entry point that validates a block declaration / a damage assignment for ANY
  controller, which the GUI's inputs can later delegate to. Consumers named in the thread: a
  new match UI (Sudo_Dudo's Arena-look client), every AI controller, the front-end forks
  (Manabrew, Endstep, Phase). Timing: the rebase era, after the Copier → Snapshot follow-up;
  no M12 dependency.

## Queued PR — the AI block-legality cache (talor, [Tyrathalis/forge#1](https://github.com/Tyrathalis/forge/pull/1); merged into the fork 2026-08-11; asked to be upstreamed 2026-09-16)

**Plan Tier 1.1 (09-27).** Upstream reshaped the same method region again on 09-24 (`fb3cc67c56`, 66 lines): the PR is rebuilt on the tip, not rebased from the fork; the fork's diff against the tip is 259 lines.

- **What:** `AiBlockController` caches `CombatUtil.canBlock` pair legality and the
  assignment-context legality (lure, max blockers, capacity) within one `assignBlockers`
  invocation; every combat mutation clears the context entries, the pure-pair entries survive
  them (fork `8044e36366` talor + `6f5e1643b2` ours: pure-pair survival + the pair-false
  short-circuit). talor's evidence: `predictNextCombatsRemainingLife` up to 60% of long games;
  hit rate 30–60%; **500 games: total CPU −15.6% (3,887 → 3,282 s), median 5.25 → 4.41 s, p90
  15.57 → 13.15 s, faster in 478/500, game-state determinism preserved 500/500.** Carried in
  every forkcheck since 08-11.
- **At the rebase:** one of the two real conflicts — upstream #11790 (liamiak, 09-06: don't block
  with creatures that die before they deal damage) rewrote 50 lines of the same method region.
  Reconcile at the merge; the new baseline forkcheck re-proves the flag-off path, the one-worker
  identity gate the cache itself (standing rule: identity gates on served arms run one worker).
- **Shape of the PR:** as reconciled, talor as author (co-author credit for the follow-up), his
  500-game read plus our forkcheck as the evidence, framed in TRT's 09-16 direction (group the
  helpers, slow / fast modes, reuse `AiCache`) — this cache is scoped to one invocation, the
  conservative version of that direction. **First in the post-launch series** (the user, Discord
  09-16 09:15: upstream patches one at a time while the big run runs).
- **TRT's condition (Discord #contribution-questions 09-16 10:46, replying to talor's post):
  "existing systems need to be reused for less technical debt — in this case AiCache."** The
  fork's cache is scoped to one `assignBlockers` invocation with the context entries cleared on
  every combat mutation; `AiCache` (forge-ai) is a global static string-keyed multimap of
  (result, args) rows with per-arg comparators, linearly scanned, cleared once per
  `AiController.chooseSpellAbilityToPlay`, its own TODO reading "add different scopes +
  staleness indicator" (users today: `AiDeckStatistics`, `ComputerUtil`, `ComputerUtilCombat`).
  So the PR is a rewrite of the storage, not of what is cached: either the pair entries live in
  `AiCache` under a key that names the combat-mutation epoch, or `AiCache` gains the scope its
  TODO names and the block cache is its first user — the latter is the smaller maintainers'
  diff and answers TRT's "group the helpers, slow / fast modes" direction from the same day.
  The behavior-identity proof (the one-worker identity gate + forkcheck) re-runs on the
  rewritten version before it is proposed; the fork keeps talor's version until then.

## Watch item — evaluation-loop budgets (khaliostr / Manabrew, 2026-09-16, not yet upstreamed)

- Manabrew added budgets inside the AI's evaluation / declaration loops for forge-wasm (no
  threaded timeout there; desktop stalls measured too — Fuzz's class: a card in hand evaluated
  against 100 board objects). khaliostr holds them back because a budget changes AI play once
  exhausted; offered to split them out for discussion.
- **Our position when it comes up:** deterministic replay is load-bearing for four Anvil systems
  (seed everything) — a wall-clock budget as a default would break it for every seeded consumer
  (ours, LordOfThePigs's harness, talor's). Count-based budgets (our search directive's budget
  unit is forward calls for this reason), flag-gated, off by default in the desktop build. TRT's
  line in the same thread — "relying on nondeterminism should remain a last resort" — is the
  same position from a maintainer.
- **The same class from our side:** the JFR read's payability mask + static / replacement scans
  per candidate × board object; the mana-source memo (fork `1dd36f7342`: the grouping built once
  per scan, identity-gated 32,306 windows) is a behavior-identical patch for it — the second
  candidate in the post-launch series, after talor's cache.
