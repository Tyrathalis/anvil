# Upstream worklist

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

*(none currently open)*

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
