# Deep dive: manabrew's Forge-integration layer (vs Anvil)

Repo: github.com/witchesofthehill/manabrew (clone at scratchpad/manabrew, HEAD as of 2026-07-16).
Forge fork: github.com/witchesofthehill/forge, branch `manabrew`, submodule pin `6ab838980b`.
All paths below are repo-relative unless noted. "Evidenced" = read in source; "inferred" flagged inline.

## Top takeaways for Anvil

1. **Their entire Forge patch is one commit, ~40 lines of engine code** (fork commit `d658cbc757`,
   verified via `gh api .../compare/master...manabrew`). Everything else is wrapper classes —
   exactly as the authors described. The patch: (a) `MyRandom` made **ThreadLocal** (upstream
   already has `setRandom()`; they only fixed cross-thread contamination for concurrent workers),
   (b) **`Match.preparePlayerZone` sorts the library by card name before the shuffle** — because
   `CardPool` is a `ConcurrentHashMap` whose iteration order "is not guaranteed", the *pre-shuffle
   deck order* is a nondeterminism surface, (c) `SpellAbility.resetIdCounter()` for cross-game
   isolation, (d) `ImageKeys.clearCaches()`, (e) two card-script bug fixes (see §5).
2. **They route around Forge's AI entirely; they do NOT solve Anvil's hash-ordered-iteration
   problem.** `DeterministicController extends PlayerController` directly (not `PlayerControllerAi`),
   answers ~100 callbacks from **canonically sorted choice spaces** (`ParityOrder`) with a shared
   seeded RNG for only 4 decision families and fixed answers elsewhere. Forge's AI decision paths
   (where Anvil's residual 1% twin nondeterminism lives) never execute. No RNG capture/restore
   exists either. Their determinism surfaces and Anvil's are **complementary, nearly disjoint**.
3. **The pre-shuffle library-order surface is worth checking in Anvil's fork.** Anvil measured
   mainline forward-play seed-deterministic across JVMs, so either Anvil's deck-construction path
   avoids `CardPool` hash order or it's stable under Anvil's pinned JVM (ConcurrentHashMap
   iteration is stable for a fixed insertion sequence *within* a JVM version; manabrew ships
   cross-platform, which is plausibly why they got bitten — inferred). A future JVM bump or the
   #11161 rebase could flip it silently; a name-sort in `preparePlayerZone` is a ~3-line vaccine
   and an easy joint-PR item.
4. **They independently rediscovered two of Anvil's hard-won lessons**: (a) live player list
   reindexes — `SnapshotExtractor` uses `getRegisteredPlayers()` "to include lost players"
   (Anvil: ADR/D1 smoke bug); (b) **decision callbacks fire inside legality/payability probing** —
   their `probingPayability` flag + silent maximally-permissive answers
   (forge-harness/.../AGENTS.md "Host payability probes must stay silent";
   `chooseSingleStaticAbility` must not consume RNG because it's called during `canPlay()`
   evaluation, DeterministicController.java:1735–1745). Same class as Anvil's "option scan is not
   a pure observer" finding.
5. **They are a live consumer of `GameSnapshot` restore-in-place**: the interactive host uses
   `new GameSnapshot(getGame())` + restore for **mana-payment cancel/rollback**
   (ManaBrewInteractiveController.java:1234, 1938, 2033). Relevant to the tool4ever
   Copier→Snapshot consolidation follow-up: there's a second downstream project whose correctness
   depends on the snapshot path, and it exercises restore (not copy-to-new-game), the half Anvil's
   forkcheck doesn't gate.
6. **Forge bugs they found** (§5): a Leyline-of-the-Void + cleanup-discard zone bug (Java puts the
   discard in graveyard instead of exile), the Fireball / Officious Interrogation
   `IncreaseCost`→`RaiseCost` SVar misname (a cost-increase static that silently never applies —
   check whether current upstream still has it; no upstream PR from them found), and
   `TargetRestrictions.getAllCandidates()` not enumerating stack-zone spell targets. None overlap
   GameCopier — they never fork mid-game.
7. **Operational tricks worth stealing**: `System.setOut(discard)` + captured `protocolOut` before
   `FModel.initialize` (stray-println-proof protocol stream); per-decision `rng_call_count` in the
   parity log + `--rng-diff` to bisect the first RNG desync; a source-hash-keyed cache of Java
   game traces (skip re-running Java when only Rust changed); runaway guards (same-name battlefield
   copies > 100 → truncate as draw; stack depth ≥ 20 → skip action space); loose-parity resync
   window for tolerating transient snapshot misalignment.

---

## 1. Determinism patch — exactly what and where

**Forge fork = upstream + 1 substantive commit** (`d658cbc757` "manabrew: headless determinism
hooks for cross-engine parity", + a merge commit). Files:

- `forge-core/src/main/java/forge/util/MyRandom.java` — `private static Random random` becomes
  `ThreadLocal<Random>`; `setRandom()` (which **upstream already has**, javadoc "Used for
  deterministic simulation") now sets per-thread. Motivation: concurrent harness workers in one
  JVM contaminating each other's seeds.
- `forge-game/src/main/java/forge/game/Match.java` (`preparePlayerZone`, +3 lines):
  `newLibrary.sort(comparing(Card::getName))` before `library.setCards(newLibrary)` — comment:
  "CardPool uses ConcurrentHashMap whose iteration order is not guaranteed". **This is the
  library-shuffle determinism**: the seed only controls the shuffle; the pre-shuffle input order
  came from hash iteration.
- `forge-game/.../spellability/SpellAbility.java` — `public static resetIdCounter()`.
- `forge-core/.../ImageKeys.java` — `clearCaches()` (memory, not determinism).
- Two cardsfolder script fixes (§5).

**Everything else is the wrapper** ("a class around forge"):

- **Seeding** (forge-harness/.../Main.java:466–474): per game,
  `MyRandom.setRandom(new CountingRandom(seed, "game"))` — covers shuffles, coin flips,
  `splitIntoRandomGroups`, everything engine-side that uses `MyRandom`. A **second, shared**
  `CountingRandom(seed, "agent")` is given to *both* players' controllers so agent-decision RNG
  consumption order is engine-independent.
- **Cross-game isolation**: `ForgeEngineReset.resetAllIdCounters()` resets 7 private static
  `maxId` counters **by reflection** (SpellAbility, SpellAbilityStackInstance, Trigger,
  IndividualCostPaymentInstance, ReplacementEffect, StaticAbility, Game) — "without modifying
  forge-game" (ForgeEngineReset.java:6–28). Plus `ParityCardMap.reset()`.
- **Decision determinism** (`parity/DeterministicController.java`, 1,903 lines): class doc says
  "RNG for 4 core decisions (play choice, attackers, blockers, targeting) and fixed values for
  everything else. This avoids RNG desync caused by Java and Rust calling non-core callbacks at
  different times." All RNG consumption funnels through `ChoiceSpace.pick*` over lists sorted by
  `ParityOrder` (canonical sort keys: action = kind|host-name|bucket|parityId|alt-cost-mode|text;
  targets = players-first-by-index then cards by name+owner+controller+parityId). Notables:
  mulligan **always keeps** (mulliganKeepHand → true, callback suppressed from the log); **X is
  forced to max** via `ComputerUtilCost.setMaxXValue` "matches Rust's choose_x_value default"
  (DeterministicController.java:380–390); extra-targets-above-minimum continue/stop via
  `pickBool(rng)`.
- **Rust side replays `java.util.Random` bit-exactly** (`parity/src/java_random.rs`): the 48-bit
  LCG, `nextInt` rejection sampling + power-of-2 fast path, and `Collections.shuffle`
  Fisher-Yates — with a library **orientation flip** (Rust top = last element, Java top = index 0;
  reverse → shuffle → reverse) so shuffles land identically. Unit-tested against Java reference
  outputs for seed 42.

**Coverage vs Anvil's machinery**: they have no RNG state capture/restore (games run start-to-end
under one seed; no mid-game forking), no copy-construction ordering work (no copying), and no AI
decision paths at all. They cover one surface Anvil hasn't explicitly audited: **pre-game deck
order from CardPool hash iteration**. Anvil covers everything else they don't.

## 2. Snapshot comparison

**Granularity** (Main.java:497–548): normal mode = one snapshot per turn at UNTAP; `--deep` =
every phase change + **every priority assignment** (`GameEventPlayerPriority`) + callback-entry
checkpoints before every decision (`DecisionLog.logCheckpoint`). Interleaved on the same stdout
stream with per-decision JSONL records; the Rust runner pairs them positionally.

**Contents & canonicalization** (`common/SnapshotExtractor.java`, mirrored by Rust
`StateSnapshot`): turn, phase (Java enum → Rust Debug-name mapping table), active/priority player,
game_over, winner; per registered player (lost players stay, indices stable — same fix as Anvil's
D1): name, life, poison, lands_played_this_turn, has_lost/has_won, zones. Canonicalization is
**identity-collapse to card names + sorted order**:
- battlefield: full card snapshots `{name, tapped, power?, toughness?, damage, summoning_sick,
  counters, controller}` sorted by (name, power, toughness, counters-string, tapped, damage,
  sickness, controller) — a deliberately deep tiebreak chain so same-name permanents in different
  states align;
- hand / graveyard / exile: **sorted name lists** (hidden hands ARE compared — this is
  cross-engine omniscient comparison, no info-set concept);
- library: **size only** + a `library_top` list of the top 10 names *in draw order* — explicitly a
  diagnostic "so silent library-order divergences surface early" (comparator.rs:~135);
- stack: source-card names, **sorted** (i.e. stack *content*, not order — order differences don't
  flag);
- counters: TreeMap, Java `CounterEnumType` renamed to Rust's names (`P1P1`→`+1/+1`, else
  lowercase enum name);
- ids: no engine ids in snapshots. Cross-engine identity uses **`ParityCardMap` parity ids**
  (common/ParityCardMap.java): sequential ids assigned at game start from hand+library, then a
  canonical per-zone sorted sweep (`syncWithGame`) so tokens/copies get identical ids on both
  engines regardless of first-touch order. Used in decision-log labels (`Name@id`), not in
  snapshot comparison itself.
- `timestamp_ms` is emitted but never compared.
- One unicode normalization hack: `Troll of Khazad-dûm` (SnapshotExtractor.java:210–215).

**Whitelists / skips (the gold)**:
- `summoning_sick` compared **only for creatures** — long comment (comparator.rs:~295): Java may
  retain sickness=true on a land played from graveyard while Rust clears at new_turn; "no gameplay
  effect for non-creatures (CR 302.6), we skip to avoid false divergences."
- `ParityCardMap.syncWithGame` **skips token cards in graveyard/exile/stack** — "avoid drift from
  transient 'dies then ceases to exist' object-lifetime differences" (ParityCardMap.java:76–78).
- `IGNORED_CALLBACKS = {"mulligan_decision"}` — "handled differently by each engine"
  (DeterministicController.java:154).
- `parity_ignore.json` — a per-matchup ignore file with reasons; currently exactly one entry, a
  **known Java Forge bug** (§5).
- `--loose-parity`: on mismatch, search a **RESYNC_WINDOW = 8** grid of skip-aheads on both sides
  and continue if the snapshots realign (parity_compare.rs:15, 284–328) — tolerates
  snapshot-*emission* misalignment as distinct from state divergence; requires ≥8 stable
  snapshots after the divergence before reporting.
- Runaway guards emit `$PARITY_GUARD` records; a guarded game reports "ABORTED AT TURN n" as a
  skip reason rather than a divergence.

**What their snapshot lacks vs Anvil's observation schema** (evidenced by absence): mana pools,
attachments, face-down state, phased-out, per-card visibility, stack targets, combat assignments,
card ids. Anvil's schema is strictly richer; the transferable value is their skip-list (which
state fields have *legitimately* divergent semantics across implementations) rather than the
schema itself.

## 3. Protocol

`docs/PROTOCOL.md` is a stub → real docs at `website/src/content/docs/protocol/*.mdx`
(rendered at docs.manabrew.app/protocol; CC-BY-4.0, deliberately license-split from the AGPL
implementation). **Generated from the `manabrew-protocol` Rust crate via ts-rs bindings**, and —
notably — the Java harness's prompt classes are **code-generated from those same bindings**
(`scripts/gen-harness-prompts.mjs`), so protocol drift is a Java compile error, not runtime
deserialize failure (forge-harness AGENTS.md "Typed prompt emission").

Shape: three engine→client message families, never conflated: `StateUpdate` (full `gameView`,
the only state carrier), `DisplayEvent` (transient UI, WIP), `AgentPrompt`
`{promptId, decidingPlayerId, sourceCardId?, input}` where `input` is a discriminated union
(~24 variants). Client answers `PromptOutput` echoing `promptId`. **Per-decision**, blocking,
one open prompt at a time. Transport-agnostic JSON (Tauri invoke / WebSocket / postMessage /
in-process mpsc).

The hard decision types Anvil cares about:
- **Priority** = `chooseAction`: engine sends flattened legal actions with opaque engine-authored
  ids (cast entries with `mode`/`modeLabel`, `activateAbility` with abilityIndex, mana abilities
  included with `producedMana`); answer = `act(actionId)` | `pass(untilPhase?)` | `concede` |
  `restoreSnapshot(checkpointId)`. Server-side priority fast-forward for held pass-untils
  (`host/PriorityFastForward.java` — keyed on (player, phase) slots because "a bare phase can't
  tell 'my end' from an opponent's").
- **Mana payment** = `payManaCost`: an **incremental re-prompt loop** — every payment step
  (tap source / untap / delve / undelve) is one offered action id; client echoes ids, engine
  re-prompts with updated state until `pay(auto?)` / `payLife` / `cancel`. "The protocol drives;
  the client only renders and echoes an id — it holds no payment state and synthesizes no ids."
  Cancel rolls back via GameSnapshot (§5). Convoke/improvise resolved at payment time, not as
  upfront cost reduction (AGENTS.md).
- **X costs** = `chooseNumber` (generic range prompt); **modal spells** = `chooseFromSelection`;
  **targeting** = `chooseBoardTargets`; **combat** = construct-shaped: `chooseAttackers` →
  `declareAttackers` assignment list `{attackerId, targetId}` (omit non-attackers),
  `chooseBlockers` analogous, plus separate `chooseDamageAssignmentOrder` and
  `chooseCombatDamageAssignment` prompts; **mulligan** = boolean prompt + separate
  `mulliganPutBack` for the London put-back; **scry/surveil** = `scry` (sort into destination
  zones) and `reorderCards`.
- **Concede is out-of-band** (a `directive`, not a prompt answer) — their AGENTS.md documents a
  hard-won deadlock lesson: never trigger game-over processing from inside an awaited prompt
  (`onPlayerLost` can consult controllers → nested prompt clobbers the open one).

Comparison with Anvil's bridge-protocol-v0: same instinct (game-agnostic answer shapes, engine
adjudicates), but manabrew's is a *human-client* protocol — per-micro-step (payment loop), no
one-shot CastPlan composite, no fallback/provenance concept, no batch/telemetry. Java Forge is
driven through it via `host/ManabrewProtocolAdapter` + `ManaBrewInteractiveController` (2,572
lines of PlayerController→prompt translation — a per-decision analogue of PlayerControllerAnvil).

## 4. Operational

- **Entry**: fat jar `forge-harness-jar-with-dependencies.jar`, mainClass `forge.harness.Main`.
  Headless via `GuiBase.setInterface(new HeadlessGuiBase(assetsDir))` + `FModel.initialize(null,
  null)`; assets dir auto-detected (needs `res/cardsfolder`).
- **Three modes**: one-shot CLI (`--deck1/--deck2/--seed/--max-turns/--variant Commander
  --commanders ...`); `--server` = JSONL request/response over stdin/stdout, FModel initialized
  once, one `{"command":"run",...}` per game, snapshots+decision JSONL streamed, terminated by
  `{"done":true}`; `--interactive-server` = per-action JSON-RPC (startGame/submitAction/getPrompt/
  getSnapshot/getGameOver/reset/quit) for hosted play.
- **Stdout hygiene**: real stdout captured as `protocolOut`, `System.setOut(discarding stream)`
  **before** FModel init — Forge's stray printlns can't corrupt the protocol stream (Main.java:
  134–143). Diagnostics all to stderr.
- **JVM opts** (parity/src/java_bridge.rs:97–145): `-Xmx=-Xms=512m` default (configurable),
  UTF-8 encoding props, `-Dpreset.decks.dir`, trace sysprops (`forge.parity.rng.trace`, etc.).
  No GC or ActiveProcessorCount tuning (their games are ≤ 40 turns, memory-light).
- **Crash/hang mitigation**: `rules.setSimTimeout(120)`; turn limit → `setGameOver(Draw)`;
  **stack depth ≥ 20 → skip action space** (combo-loop damper); **>100 same-name battlefield
  copies → truncate as draw with `$PARITY_GUARD` marker** (both engines implement the same guard);
  server `quit` waits 5 s then kills; per-game `ImageKeys.clearCaches()` + `System.gc()`;
  reflection ID-counter reset between games. No per-game watchdog timeout on the Rust side found
  (evidenced absence).
- **Scale-out**: `--java-workers N` server-process pool; rayon-parallel matrix mode; `--continuous`
  round-robin + SQLite + web dashboard (pass-rate threshold gate for CI, games/minute stat);
  **source-hash-keyed cache of Java traces** (java_cache.rs — Java only re-runs when Java sources
  or the matchup key change). There's even an automated repair loop (`scripts/parity-repair-agent.py`,
  `infra/llm.rs`, github_issues.rs) that files/triages divergences with an LLM; its prompt rules
  include "Never match a Java bug by breaking Rust."
- **Throughput numbers: none published** in docs/comments (searched); the dashboard exposes
  games/minute at runtime only. Their unit of work is a 10–40-turn seeded matchup, not bulk
  self-play.
- Bonus: `forge-harness/native/` holds GraalVM native-image/Espresso configs (reflect/JNI/proxy
  json) — they run the Java engine embedded via j4rs/Espresso for hosted play.

## 5. Gaps/bugs they hit in Forge

- **Leyline of the Void + cleanup discard** (parity_ignore.json, the only entry): "Java Forge
  incorrectly puts cleanup hand-size discards into the graveyard instead of exiling them under
  Leyline of the Void." They whitelisted the matchup rather than patch Forge.
- **`IncreaseCost` → `RaiseCost` SVar misname** in `fireball.txt` and `officious_interrogation.txt`
  (fixed in their fork, commit `d658cbc757`): the static's `Amount$` referenced an SVar name the
  script didn't define under the expected key, so the "costs {1} more per extra target" static
  presumably never applied. **Not found upstreamed** (no PRs from witchesofthehill to Card-Forge).
  Cheap for Anvil to verify against current upstream and carry as a trivial PR if still live.
- **`TargetRestrictions.getAllCandidates()` doesn't enumerate stack-zone spell targets** even when
  the restriction zone is Stack — the engine special-cases `canTargetSpellAbility()`; their
  harness mirrors it (DeterministicController.java:440–445 comment) and converts stack Cards to
  their SpellAbility (CounterEffect.resolve filters for SpellAbility instances) — counterspell
  targeting breaks otherwise (commit 10258aea "Java harness Card/SpellAbility type mismatch").
- **Decision callbacks fire during legality probing** (`CostAdjustment`/`ComputerUtilMana` call
  regular PlayerController choosers mid-`canPay` test): solved with `probingPayability` silent
  answers. Also `chooseSingleStaticAbility` is called during `canPlay()` action-space evaluation —
  consuming RNG there desyncs (DeterministicController.java:1735–1745).
- **`CombatUtil.validateBlocks` is human-input-only** — implied by EngineHandler's design
  (AGENTS.md: post-validates "whole-answer constraints a per-option set can't express (e.g.
  CombatUtil.validateBlocks)") — independently corroborating Anvil's D5 finding that the engine
  never validates AI blocks.
- **GameCopier/state-copy overlap: none.** They never copy games for search. Their single
  state-copy use is `GameSnapshot` create/restore around interactive mana payment
  (ManaBrewInteractiveController.java:1938/2033) — i.e. they depend on the snapshot path's
  *restore* fidelity, which Anvil's PR #11203 review thread is about to make the canonical path.
  One engine-side RNG-adjacent fix on the Rust side references a Forge behavior quirk:
  "skip Aggregates.random sync on CopyPermanent token path" (commit 7f932c77) — inferred to be an
  RNG-consumption-order mismatch around token copying, not a Forge bug per se.

## 6. Convergence assessment

A joint upstream determinism PR is **realistic but small, and the two projects barely overlap —
which is exactly why it's cheap**. Manabrew's needs are already satisfied by ~40 fork lines:
ThreadLocal `MyRandom` (strictly safer than upstream's mutable static for anyone running
concurrent games in one JVM), deterministic pre-shuffle library ordering in
`Match.preparePlayerZone` (behavior-invariant for players — sorted input to a uniform shuffle is
still uniform), and a public/unified static-ID-counter reset (they currently do it by reflection,
which is fragile across Forge refactors — an official `Game`-scoped or test-API reset is the
obvious shared ask). None of that touches Anvil's surfaces (RNG capture/restore, copy-construction
ordering, hash-ordered iteration inside AI decision paths), so a bundled "determinism hooks for
headless/testing use" PR could carry both sets without design conflict, and Anvil's merged #11203
credibility plus the maintainer-blessed Snapshot consolidation makes Anvil the natural author.
What Anvil gains: the pre-shuffle ordering fix closes a latent cross-JVM-version corpus
reproducibility hole before the next fork rebase; manabrew's whitelist knowledge (non-creature
sickness semantics, token lifetime in hidden zones, cleanup-discard zone bug) is a free checklist
for forkcheck digest false-positive classes; and their GameSnapshot-restore dependency is a second
voice (and test consumer) for the consolidation follow-up. What Anvil offers them: fork fidelity
they'll eventually want (any future "rewind/branch" feature on the Java backend inherits Anvil's
fixed copier), the `forkcheck` twin gate pattern, and upstreaming muscle — they have shipped zero
upstream PRs and even their card-script fixes (Fireball) sit unshared in the fork. Worth an
issue/discussion on their repo before writing anything; their parity harness would also directly
benefit from Anvil's fixed `GameCopier` if they ever want mid-game checkpoint/restore in the
hosted client (their protocol already reserves `restoreSnapshot` in `ChooseActionOutput`).
