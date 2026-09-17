# Forge Discord #ai-plotting survey

**Doc status:** survey · Forge Discord #ai-plotting, read 2026-07-16

**Date read:** 2026-07-16 (full channel history, 2025-08-08 creation → present, ~965 messages, read via the desktop app; read-only — nothing posted).
**Where:** Forge Discord server, channel `#ai-plotting` (under "Features"). One thread ("@infinitecursive did you publish"). Sibling channel `#ai-decks` hosted a 2022 tree-search plan by marthinwurer; `#ai-dumb-not-cheating` is player-complaint territory, not ML.
**Why this doc:** complements [prior-work-survey.md](prior-work-survey.md). Design conversations for Forge happen in Discord/PRs, never issues — this is the standing record of who is doing AI-on-Forge and what they've hit.

**Follow-up archaeology (2026-07-16, same day):** deep dives landed as companion docs — [survey-dive-austinio-rl-branch.md](survey-dive-austinio-rl-branch.md) (his 54%-parity headline was a silent-fallback artifact; true 29-31%; PPO program fully documented-failed; MCTS is a one-ply UCB1 bandit over unfixed GameCopier), [survey-dive-manabrew-harness.md](survey-dive-manabrew-harness.md) (their whole Forge patch is ~40 lines; **found our shared pre-shuffle CardPool-hash-order determinism hole** — queued in [upstream-worklist.md](upstream-worklist.md); they're a live GameSnapshot-restore consumer), and [survey-dive-pricepredictor-magezero.md](survey-dive-pricepredictor-magezero.md) (price-predictor = a working Tutor prototype with counter-based per-card labels + auditor-scorer reward-hacking canary; MageZero searches with `see_opponent_hand: true` — determinized-leaky training environment). Corpus-side checks (aura label integrity, never-cast pool audit) recorded below in §2 updates.

## 1. Who is doing what (projects and approaches)

| Person (GitHub) | Project | Approach | Status (as of Jul 2026) |
|---|---|---|---|
| **Austinio** (`austinio7116`, **Forge core dev**) | `forge:ai_investigation` branch — full BC→RL gameplay pipeline, built with Claude Code in days (Mar 2026), ~8K LOC | forge-ai-rl module, **PlayerControllerRL**, feature encoders, model server, trajectory recording; 1000-game heuristic corpora → value net + 7 decision heads → ONNX in-game inference; then PPO self-play (value-delta GAE rewards, terminal-anchored) | Imitation ≈ 25-35% WR vs heuristic; PPO plateaued (~33%); moving toward ExIt/search ideas; paused since mid-April (RLAI_PLAN.md / RLAI_PAPER.md / RLAI_IMPROVEMENTS.md in-branch) |
| **Kryptic** | Independent replication of Austinio's pipeline | Same scripts; strong experimental hygiene instincts (CI-width callouts, leakage hunts, codex-driven code review) | Found the train/val game-leakage bug, the heuristic-fallback fake-win bug; built seeded twin-replay divergence tooling; PPO 200 rounds/220h → 24.5%→33.2% then flat. **09-07: ran Anvil itself** on a mono-green stompy mirror (Constructed, custom pool): BC 38.9% (n=2,000) → V-trace self-play 55.2% after 25 iterations (n=1,000, se ±1.6) — the first external replication of the loop ([devlog](../devlog/2026-09-07-session2.md)). **09-17: a second run on four mono-coloured decks** (`constructed-four-rl-4000`, 8,000-game BC 40.6% → 40 iterations × 2,000 games → **51.1% at iter 30 / 50.6% at iter 40**, n 8,000 each, a plateau from iter 20; a 40,000-game heuristic reference matrix; the red mirror 35–39% the one structural deficit, Blue Tempo +5 to +11 where the heuristic plays it at 15–27%) — the §5 09-17 follow-up; decks + workbook at [community/constructed-four/](community/constructed-four/) |
| **talor** (`Talor-A/forge`; `talor-a/tinymtg`) | Fork continuing Austinio's work; **09-15: `tinymtg`**, an own TypeScript engine (<10K LOC, deterministic, forge-script translated ahead of time, 4,500 cards, no perf work yet) | Added unit tests (found bugs), macOS MPS backend, diverse decks from cubecobra exports, cosine-similarity reward shaping for block/target heads; **Monte-Carlo rollout visualizer using GameCopier**; **08-10: the AI block-legality cache as a PR against our fork ([Tyrathalis/forge#1](https://github.com/Tyrathalis/forge/pull/1), merged 08-11; 09-16 he asks that it be upstreamed)** | Active late May; `rltrain collect` = 5000 games/16 threads JSONL; ~0.5% game-failure rate (undiagnosed) |
| **LordOfThePigs** (`npiguet`) | Sealed **deck-builder** model, now **draft agent** (Tutor-adjacent, not gameplay) | Card transformer over card text + 544-dim embeddings pre-trained on per-card stats from 1M forge-vs-itself games; MLM pretraining helps; simulated-annealing deck search → distilled single-pass (3-4ms) | **Beats Forge SealedDeckBuilder 78% Bo7.** Draft agent: BC picker 85% match/top-3 99%; RL above BC failing (offline RL on fixed corpus dead; switching to online). 3-machine harness ≈ 200K games/day |
| **manabrew** (`witchesofthehill/manabrew` — khaliostr, fedepoi, Anacleto) | **Rust/wasm GPL port of Forge** + Tauri client, self-host multiplayer | **Lockstep parity harness**: serializes java Forge gamestate, drives it via JSONL/stdin-stdout, compares snapshots every turn+priority vs the Rust engine; **patched Forge for seeded determinism** ("seed controls library order and makes sure all decisions are the same") | Public since ~June; java Forge playable through manabrew; Rust ~50% faster/lighter but "still isn't completely correct"; offered the harness for AI control use. **09-15 (itemfive): the Rust port is being dropped**; the product is Java Forge built to wasm (`@manabrew/forge-wasm`) behind their protocol; **09-16 (khaliostr): upstreaming engine perf found by profiling forge-wasm (Card-Forge #11916 merged 09-14, #11925 merged 09-16), evaluation-loop budgets held back (they change play once exhausted), a Java `forge-engine` module that splits the front end from the engine (Java / wasm / server), Endstep's server-side patches integrated** |
| **coda** | **Python port** of Forge (Claude-assisted) | JSON-over-Websockets protocol mirroring Forge's; Pyodide/wasm ambitions; browser TCEC-style tournament server idea | Early; engaged and thoughtful about authoritative-server/hidden-info hygiene |
| **wingedsheep** | `mtg-llm-benchmark` + **argentum-engine** (own rules engine: Portal, Onslaught, Khans, Dominaria, Bloomburrow) | LLMs draft/deckbuild → exported to Forge (Forge AI plays); engine has an LLM AI mode | Side project cadence |
| **marthinwurer** | AlphaZero-on-Forge ambition (since 2022 in #ai-decks) | **PR #8427 "Break out main loop step"** — mainLoopStep()/setupFirstTurn() so you can "copy the game state and step through priority by priority… important for any kind of tree-search AI"; plan: random player → MCTS | Engine-side groundwork only; low activity since Sep 2025 |
| **infinitecursive** (`benhunter/forge` PR #4) | "Simple AI" / multi-AI plumbing | Minimum-viable "None" AI (pass everything, first option) + GUI AI-picker spike; proposal: common interfaces shared by all AIs, tests for unenforced interface behaviors | Jan 2026; wants consensus before upstream PRs; wary of "refactors rejected due to unintended consequences" |
| **PFR-Science** | Bitpacked game-record format + decoder model (Standard-only) | Game-state deltas, <1KB/game target, "1+ billion games on a retail SSD"; BC off Forge AI then self-play with noise/node-masking | Mostly talk (Aug 2025 era); described the BC→RL shape Anvil uses |
| **Verinax** | Gemini-in-Forge | LobbyPlayerGemini/PlayerControllerGemini + GameStateSerializer→JSON→Gemini API; falls back to default AI on timeout | Working demo (Gemini Lite), May 2026 |
| Others | int_matt/krafczyk `mtg_draft_ai` (JPype pack sampler, phone-inference interest); Eternalyze0 `mtg_bot`; MattDTO (PettingZoo/gym proposals, 10M-URL HF dataset); GreySim (Threadripper compute offers); xanxer6rB, itemfive, Fuzz (channel shepherd, monthly check-ins) | | |

Adjacent XMage projects referenced: **MageZero** (WillWroble — AlphaZero-style, ~250 g/h with 300 MCTS sims/decision) and **Mage Bench** (mage-bench.com — LLMs play via XMage, $0.62–$40/game in tokens; HN thread mid-Feb 2026). MTG Bench (CallumFerg, HN 6/11/26) = LLM benchmark with **no rules engine** (noted disapprovingly by coda).

### Repo activity snapshot (GitHub, checked 2026-07-16)

| Repo | Last real commit | 30-day pace | Verdict |
|---|---|---|---|
| `witchesofthehill/manabrew` | **today** (ops/staging deploys) | ≥100 commits | Production-mode, hottest project |
| `wingedsheep/argentum-engine` | **today** (PR #1298; VOW cleave cards, CR 702.149c) | ≥100 commits, multiple outside contributors | Very active, real OSS traction (43★) |
| `npiguet/price-predictor` | Jun 14 (Jun 10: **"draft-agent live Forge integration spec"**) | steady docs/specs cadence | Active, matches his Jun 15 Discord status |
| `WillWroble/MageZero` | May 22-23 (+README Jun 19) | 1 commit | Simmering (41★) |
| `Talor-A/forge` | May 29 (loss graphs, direnv) | 0 | Quiet ~7 weeks |
| `austinio7116/forge` `ai_investigation` | **Mar 29** — final commits went beyond Discord: mulligan/block **MCTS budgets**, XL **107M-param** presets, paper §5.4.8 | 0 | Stalled 3.5 months at its most interesting point |
| `benhunter/forge` | AI work Feb 1-8 (`ai-simple`, plus unmerged `codex/add-mcts-ai-option-and-factory`, per-slot AI profile branches); master = upstream sync Jun 20 | 0 (AI) | AI thread dormant; PR #4 closed Feb 1 |
| `krafczyk/mtg_draft_ai` | Oct 2025 | 0 | Dormant |
| `Eternalyze0/mtg_bot` | Sep 2025 | 0 | Dormant |
| `wingedsheep/mtg-llm-benchmark` | Aug 2025 | 0 | Superseded by argentum-engine |
| `misprit7/MTGAI` | Dec 2020 | 0 | Dead |

coda's Python port has no public repo yet (nothing linked in-channel; nothing findable under that handle).

## 2. Engine pain points they hit (Anvil-relevant)

Independent rediscoveries of things Anvil already engineered around — strong confirmation of our design choices, and a map of what bites newcomers:

- **Engine reliability at scale:** LordOfThePigs: "Forge AI crashing, hanging, or going into a quasi-infinite loop is a common enough occurrence that my harness launches single-threaded workers with a supervisor killing stuck processes." talor: ~0.5% of games fail (10K-game runs), undiagnosed. (= our chunked workers, hard-cap, failure census.)
- **Server-fallback corpus poisoning:** Austinio found "a nasty bug where if the RL AI player can't connect to the ML server it reverts to using the heuristic AI so this could even give some fake wins" — trajectories carry `fallback=True`. (= our "never read a bridge answer without checking `fallback`" rule and 0-fallback gates.)
- **Train/val leakage by game:** Kryptic caught random splits ignoring file/game identity (val acc 95%→80% after fix; "this issue or similar in 4 places", plus 2-files-per-game double leakage). (= our deterministic hash splits by game and pair.)
- **Eval resolution ignorance → late correction:** rounds evaluated on 100–400 games (±9 / ±4.5pp CI) while chasing 1–3pp effects; Gemini/GreySim's "10,000 games to confirm 1%" landed mid-project. (= our paired-seed arms, Ante variance reduction as first-class.)
- **AI-path omniscience:** talor: "the RL player is technically omniscient… the repos linked above do use this." Their models train on hidden info. (= our leak-tested info-set transform; a real differentiator.)
- **Factorized-decision coupling:** Austinio: choosing the spell first, then being forced into a bad target — "I need to make the spell and target decision together." (= CastPlan composite actions.)
- **Aura/Attach targeting invisible to features:** `sa.usesTargeting()` is false for auras (Enchant mechanic ≠ normal targeting), so their aura target/polarity features were silently all-zero and the model couldn't learn aura placement. **Action item: verify Anvil's CastPlan/obs join captures Attach/aura placement targets** (our sub-target serialization may already cover it — worth a 20-minute check against a Rancor-style deck).
- **Encoder collapse under value-only training:** Austinio's 512-dim embedding retained almost no factual state (opp-life R² < 0; "learned to discard everything but win-prob correlates") until joint multi-head training. Rhymes with our D5 input-conditioning diagnosis (different mechanism, same "value head can't read the board" symptom class).
- **Entropy-bonus overdose:** raised ent coef 0.005→0.03 chasing exploration, then self-corrected: "we went too high — the model doesn't need to randomly bounce its own creatures to 'explore'"; proposed **per-head entropy** (high for attacks, near-zero for targeting). ADR-0017's collapse is the same force; per-head entropy floors are an idea worth stealing if the hinge floor proves too blunt.
- **Idle-turn leak:** losses had 29.1% idle-turns-with-castable-spells vs 8.6% in wins — their version of our veto/forced-pass leak (they saw it in outcomes; we measured it at the mechanism).
- **Heuristic-teacher bias in corpora:** LordOfThePigs' deck models learned Forge-AI biases (over-values creatures, W/G over R/U "because the Forge AI knows how to use creatures well"); also **"a list of about 2-3 thousand cards that the Forge AI will never play under any circumstances"** is common knowledge ("yes of course lol"). Relevant to pool curation and to interpreting BC ceilings.
- **Observer purity:** Kryptic wanted "what would the heuristic do" recorded at every decision under the RL policy; codex concluded it can't be done without side effects outside PRIORITY/DECLARE_ATTACKERS/DECLARE_BLOCKERS. (= our D2 finding that the option scan is not a pure observer.)
- **Performance:** their fleet numbers are comparable to ours (Austinio 1,600 g/h on 16 threads for a 4-deck toy meta; 30s JVM init amortized by process reuse — LordOfThePigs). Kryptic's trajectories are ~65MB/game (260GB per 4K games) vs our ~47KB/game — three orders of magnitude; our zstd-framed store is a genuine asset. Token-heavy board-state slowdown is community-known (64KB Claude-written optimization proposal cross-posted from the contribution channel, Mar 8).

## 3. GameCopier / GameSnapshot / PR #11203

- **Zero Discord mentions of PR #11203, GameSnapshot, or the consolidation** (server-wide searches). The review conversation lived entirely in the PR.
- **GameCopier has users who don't know it was broken:** talor (Jun 3) uses it for Monte-Carlo rollouts/MCTS ("gamecopier allows cloning a game and then you can run it in a parallel thread… only useful in training because tree rollouts reveal hidden information"). Austinio's Claude-generated plan (Mar 27) recommends ExIt "since the game engine supports state copying." Both predate the #11203 merge (2026-07-12); both forks are pinned before the fixes.
- Only other mention: a newcomer reading GameCopier to learn the codebase (2024), and marthinwurer's 2022 #ai-decks tree-search plan.

## 4. Engagement opportunities (Forge conversations happen here, not in issues)

Ranked by value-for-effort; all are single messages into #ai-plotting unless noted:

1. **Answer Fuzz's monthly check-in (posted today, 2026-07-16, unanswered).** A natural, zero-cost opening to introduce Anvil publicly: repo is public, PR #11203 is merged, and the channel is *exactly* the audience. Content that would land: BC agent at ~47-51% vs the heuristic in real games (they're stuck at 25-35%), 113K-game corpus at 47KB/game, and the RL loop running.
2. **Tell the rollout users about #11203 + forkcheck.** talor and Austinio both build on GameCopier for search/rollouts with no fidelity gate. One message: "GameCopier had id-renumbering + two static corruption bug classes; fixed upstream in #11203 (merged Jul 12) — rebase past `1922ce411a`; we maintain a fork-fidelity regression harness (`forkcheck`) if you want the gate." This also builds the constituency for the maintainer-blessed Copier→Snapshot consolidation follow-up (tool4ever's "should also help with your project" applies to them too).
3. **manabrew's determinism patch vs ours.** They independently patched Forge for seeded determinism ("seed controls library order… all decisions same across games and engine"). Comparing notes could converge on an upstreamable determinism surface — which is load-bearing for four Anvil systems. Their lockstep parity harness is also conceptually adjacent to forkcheck's twin mode; both sides would learn something.
4. **The common-interface conversation (infinitecursive/MattDTO/Fuzz).** "An abstraction layer to plug AI into" is exactly `PlayerControllerAnvil` + the bridge protocol's six game-agnostic answer shapes. When the multi-AI refactor conversation resumes, Anvil's decision-surface census (109 methods, ~88 real decisions) and the bridge protocol doc are the strongest prior art in existence. fedepoi's "standardized mtg open interface" vision points the same direction.
5. **Warn about the entropy/self-play failure mode (optional, goodwill).** ADR-0017's diagnosis (always-on entropy bonus has no equilibrium under near-zero advantages; mirror self-play makes it the only persistent gradient) directly explains behavior Austinio saw and half-fixed by intuition. A short write-up would be a high-credibility introduction.
6. **LordOfThePigs' harness/scale** (200K games/day on 3 machines, java process reuse) and his card-transformer embedding results (per-card stats from 1M games beat raw features for deck quality) are worth reading before Tutor work starts.

## 4b. Corpus checks triggered by the survey (2026-07-16, full-corpus sweep; record `data/runs/never-cast-audit-20260716.json`)

Both checks ran over the whole BC corpus (113,592 games / 65.8M priority windows / 6,114,435 casts; cast count cross-checks the D2 sweep exactly; 0 unresolved hosts).

- **Aura/Attach label integrity: CLEAN — Anvil does not have Austinio's bug in any form.** 64,035 aura casts across all 49 pool auras; 63,830 carry the attach target in the CastPlan's top-level `tgt` (Forge exposes aura attachment as normal SA targeting; `usesTargeting()` is true — Austinio's bug was in *his* encoder's use of `getValidTgts()` descriptor strings, which Anvil never reads). The **only** target-less residue is Demonic Ruckus × 205 = its **Plot** mode (exile-from-hand, correctly targetless; its 363 real casts all targeted). Animate Dead (enchant-from-graveyard templating) shows 2,170/2,170 targeted. The serve-side realizer applies targets on every `usesTargeting()` node symmetrically (CastPlanRealizer), so the path is clean end-to-end.
- **Never-cast pool audit: 138/1,701 pool cards have zero cast labels in the corpus.** Decomposition: **95 are `AI:RemoveDeck:All`** (the community's known "2–3K cards the Forge AI never plays" mechanism — 125 such cards are in our pool, so 30 flagged cards *do* get cast; the flag gates deck inclusion, not casting), 9 more carry weaker `AI:RemoveDeck` flags, and **34 are unflagged heuristic blind spots** — cards the AI had as a timing-legal candidate, often *millions* of times, and never once cast: Intuition (2.39M candidate windows), Sauron's Ransom (1.16M), Tithe (736K), a cluster of **6 auras** (Sentinel's Mark, Saving Grace, Dog Umbra, Brilliant Wings, Military Discipline, Treachery — the AttachAi apparently never fires for them), Yawgmoth's Will, Expropriate, and **Rick, Steadfast Leader — a maindeck payoff in two Winota lists with 16K candidate windows and zero casts** (correction 2026-07-16: an earlier revision of this doc called him a commander — he is not; he's maindeck in decks 864092/864793, commanded by Winota). Only **6 cards were never even a candidate**, all name-representation artifacts of split/room cards ('Dead', 'Fire', 'Life', 'Double Jump', 'Roaring Furnace', 'Walk-In Closet' — the fused faces cast under other names). Implications: (a) the 34+95 are **structural BC blind spots** — no imitation signal exists; under the legality-only realizer they remain *reachable*, so they're RL-exploration-only cards and prime Grindstone drill candidates; (b) teacher-corpus decks carrying them donate dead slots — relevant to interpreting per-deck arms; (c) for Tutor, `AI:RemoveDeck` flags and cast-rate-given-candidacy are cheap card features our store already yields.

## 5. Corrections/notes for our records

- The prior-work survey's "Forge's GameCopier/simulation layer is reportedly unstable" now has a named community witness (Hanmac, Jan 2026): the boardstate-simulation AI path "isn't used that much, I think because it's too expensive" — cost, not just instability.
- The channel is livelier than "lightly-used" suggests: bursty (dead Oct–Dec 2025; very hot Mar–Jun 2026), driven by Claude Code/codex lowering the barrier — three independent BC→RL pipelines appeared in four months, all hitting walls Anvil has already documented and passed.
- Nobody in the channel knows about Anvil (searches for the project return only the Oni-Cult Anvil card).
- **2026-09-07 update (LordOfThePigs, Discord, two messages):** (1) he is now training embeddings
  *effect-grounded* — the tokens of an ability's cost related directly to the observed effect (what
  card was tapped, what mana left the pool) and likewise for every effect type (replacements,
  stack-based effects); concept doc
  [2026-09-04-ability-effect-model-design.md](https://github.com/npiguet/price-predictor/blob/master/experiments/2026-09-04-ability-effect-model-design.md),
  no results yet. His claim: token embeddings that have proven able to predict their own game effect
  are a much better basis for a game-playing agent than his current ones, and raw-text pre-trained
  embeddings from another project cannot do it well because words carry MTG-specific meaning general
  embeddings miss. (2) On the teacher-bias line in §2: most of his three models' bias comes from the
  *target* they optimise (decks the Forge AI plays well), not from the teacher (Forge's deck builder /
  drafter); the models' behaviour is fairly different from their teachers'. He was disappointed the
  card embeddings carried little information, surprised that even so the models vastly outperform the
  teacher; the probes gave him what the new version needs. **Anvil relevance:** claim (1) is a direct
  challenge to ADR-0007/0012 (pinned Qwen3 text embeddings) at the moment Build 4 of M12 re-decides
  the ability-text path (text-hash-keyed LLM embeddings, fork I). Our store already carries the
  observed effects (the obs stream + the payment telemetry), so an effect-grounded target is buildable
  from banked data. Routed by name as a **Build 4 fork** for the user: effect-grounded ability
  embeddings vs the pinned LLM text embeddings, with ADR-0049 (representation was not the bottleneck
  at M6) as the prior and his results, when they land, as the external read. Not acted on.
- **2026-09-08/09 update (Discord, banked 09-09).** (1) **LordOfThePigs' design doc read**
  ([2026-09-04-ability-effect-model-design.md](https://github.com/npiguet/price-predictor/blob/master/experiments/2026-09-04-ability-effect-model-design.md);
  status *not yet run*, collection + first pretraining pending, feasibility verified in Forge source
  09-04..09-06): the data = his gen-4 corpus (974K Forge self-play games) instrumented by three Forge
  patches (a `TriggerHandler` attribution hook with a closed 147-member mutation enum, a replacement
  execution hook, a resolution-bracket pointer for sub-abilities) into seven record kinds (resolution,
  rewrite, continuous-effect, trigger-fire, playability verdicts, combat, counterfactual probes) over
  33,680 card names (89% of unique ability texts appear once; 21.9% of cards never cast). The model =
  an offline **ability encoder keyed per unique ability text** (script surface primary, prose paired;
  cost vs effect role tags; **keyword-expansion dropout**: keyword tokens replaced by their definition
  text with probability p in training, always expanded for unknown keywords at inference) + an
  in-game state-conditional effect head over entity tokens predicting per-entity outcomes (zone,
  tapped, damage, counters, P/T, control, attachments), per-player deltas, token creation, and an
  [ACT] slot (playability, cost paid, trigger fired); multi-task, Poisson count heads, an
  identity-only baseline as the memorization ceiling, card-disjoint-by-newest-set and game-disjoint
  held-outs, behavioural canaries (ward vs its spelled-out twin, role polarity of {R} in cost vs
  effect, zero-shot one-keyword-withheld). **Anvil relevance (fork K stands as adjudicated 09-07):**
  our pin is the engine's canonical script text hash-keyed per ability, which already resolves his
  "words mean something specific" objection by construction (the script parameters ARE the effect's
  language; the ADR-0105 frozen probe decodes every effect class at AUC 0.98–1.00 from that
  embedding); what his design adds that ours does not have is (a) keyword-expansion dropout — a cheap
  augmentation for our own table (Forge's reminder-text templates are the same source), and (b) the
  held-out-by-newest-set + identity-only-baseline evaluation, which is our held-out-card probe
  (m12-plan fork K) stated as a benchmark; his per-record-kind effect targets are the effect-prediction
  auxiliary loss we deferred pending the probe. Nothing changes now; his results are the external read.
  (2) **Kryptic's follow-ups**: the 55.2% mirror result stands; his question "what should the new
  benchmark be" — our answer on record: the heuristic is strong with blind spots, ~65% vs the
  heuristic looks reachable on our pool by the headroom accounting (ADR-0075's payment headroom, the
  planning gap), not yet taught. **chrismaghuhn** asked about rejected/traj 0.24 → 0.49 — the
  user's answer: incidents per 64-step segment, not the share of invalid outputs; a degenerate
  "let the engine pick" behaviour we hold down (the M9 finding: not the strength mechanism), fine
  under `--reask` unless it keeps growing. (3) **talor**: "not much result playing with the veto
  penalty"; asked whether anyone looked at manabrew ("their JSON API … less hacky than working around
  forge's rpc limitations"); reported **good results on Modal** (its lowest GPU tier ≈ 5× his
  MacBook for the train step — "with such a small model the limiting factor is cycles"); hardware =
  **M4 Pro, 48 GB**. (4) **khaliostr (manabrew maintainer)**: the manabrew protocol is ready for
  interop with Forge or any engine; **`@manabrew/forge-wasm`** released standalone
  ([npm](https://www.npmjs.com/package/@manabrew/forge-wasm), v0.2.0, 2026-08-31, AGPL-3.0, 72 MB
  unpacked: Forge compiled with **GraalVM Web Image**, runs on a worker thread in Node ≥ 20 or a
  cross-origin-isolated browser, one synchronous game per worker, a `cardset.rkyv` archive with
  per-game card-script selection, `createForgeEngine({onState, onPrompt}) → startGame({deck,
  opponentDecks}) → respond(prompt.id, action)`, typed by `@manabrew/protocol` ^5.4, multiplayer
  seats, `directive()` for out-of-band concession); "happy to support more RL-specific scenarios if
  you give us leads".

  **Assessment for Anvil (forge-wasm):** not relevant to the research loop, for three reasons we have
  measured rather than assumed. (a) *The transport is not our bottleneck*: the gRPC bridge tax is
  +2.6% at 16 workers (ADR-0003) and the serve path is wait-dominated (0.05 ms Python-active vs 5.3 ms
  wall per request, ADR-0032) but hidden behind worker parallelism; the clock is the JVM engine
  (generation ≈ 80% of an iteration on a CUDA box — Kryptic's monitor: gen_s ~1,400 vs train_s
  ~290) and, in the train phase, the loader (the GPU sits ~90% idle, rl.py bench 07-25). A WASM Forge
  under GraalVM Web Image runs without HotSpot's JIT profile and one synchronous game per worker —
  slower per game than the JVM by an unmeasured factor (2–5× is the usual Web Image gap), the wrong
  direction for a throughput-bound loop. (b) *The decision surface*: their protocol speaks the human
  prompt surface (`Prompt`/`PromptOutput`); Anvil's census counts 64 firing `PlayerController`
  callbacks, many of them fired inside legality/payability probing (the 07-18 review's gap list,
  §2 of the survey dive), and manabrew's `DeterministicController` routes around Forge's AI. (c) *The
  search machinery has no counterpart there*: GameCopier copies with seeded determinization, RNG
  capture/restore, the forkcheck proof, the surface directives — all fork-side Java. Where it could
  matter later: a browser-hosted Mentor surface (WASM Forge + an ONNX policy) — the same shape as
  fork H's Android ship, routed with it. **The one actionable item is his ask**: the RL-harness needs
  list we can hand him — (1) state forking with seed control and restore-in-place (GameSnapshot /
  GameCopier semantics), (2) RNG capture/restore and a per-thread `MyRandom`, (3) callback coverage
  beyond the prompt surface with a probing-vs-real flag (the field guide's "option scan is not a pure
  observer"), (4) batched headless multi-game per process with per-game seeds and provenance pins
  (engine commit, cardset version — his `BUILD_COMMIT` / `CARDSET_ARCHIVE_VERSION` already do this),
  (5) an AI-opponent seat that stays deterministic. The M3-candidates item "determinism-hooks
  collaboration with manabrew" is the same conversation, still open.

  **Configuring Anvil on an M4 Pro (talor; the honest picture, from our own measurements):** the loop
  is engine-bound, not GPU-bound. Generation scales with worker count: `--workers` ≈ physical cores −
  2 (an M4 Pro's 12–14 cores → 10–12 workers; JVM heap 2–3 g each fits 48 GB), and an M4 P-core's
  single-thread speed is at or above a desktop x86 core, so per-worker games/hour should match ours —
  fewer workers is the whole difference. The model server is fine on `--device mps` or even `cpu`
  (the forward is small; the serve path is wait-dominated anyway) — the one thing to verify is the
  hard-coded bf16 autocast (`torch.autocast(device, bfloat16)` in the server and rl.py: supported on
  MPS only in recent torch; a `--no-autocast` switch is a two-line change if not). The train phase
  is where his 5× Modal number lives, but train is ~20% of an iteration on a CUDA box, so a 5× slower
  train step makes an iteration ~1.8× longer, not 5×; `selfplay.py` does not expose `--device` for
  the rl/server subprocesses today (a small patch: forward it to both). Splitting generation (local)
  from training (Modal) is feasible because `anvil.training.rl` is a standalone step over the ingested
  store — rsync the store up, pull `last.pt` down — but the loop does not do it for you.

### Draft replies (09-09; the user posts; nothing posted from here)

To khaliostr:

> Thanks — congratulations on shipping forge-wasm. For our loop the engine, not the transport, is the
> clock (our gRPC hop costs ~2.6% at 16 workers), so we'll stay JVM-side, but here is what an RL
> harness needs from an engine interface, in case it helps the protocol: (1) state forking with seed
> control and restore-in-place; (2) RNG capture/restore (and a per-thread RNG — you already did that
> one); (3) decision callbacks beyond the human prompt surface, with a flag that says whether a
> callback fires inside a legality/payability probe or for real; (4) batched headless multi-game per
> process with per-game seeds and engine/cardset version pins on every record (your BUILD_COMMIT /
> CARDSET_ARCHIVE_VERSION are exactly right); (5) an AI-opponent seat that stays deterministic. Happy
> to compare notes on (1)–(3); we have a fork-fidelity harness that measures them.

To Kryptic (the RPC question):

> The "limitations" aren't really the RPC: our bridge tax measures +2.6% at 16 workers and the serve
> path hides its latency behind worker parallelism. The hard part is Forge's decision surface itself —
> ~64 controller callbacks that fire during play, some of them inside legality/payability probing —
> and any interface, JSON or gRPC, has to answer those consistently. That's engine work either way.

To talor (the M4 question):

> Our loop is engine-bound: generation is ~80% of an iteration on a CUDA box and it's JVM work, so an
> M4 Pro's cores matter more than its GPU — `--workers` ≈ cores − 2 (10–12 for you, heap ~3 g each
> fits 48 GB) and per-worker throughput should match ours; fewer workers is the whole difference. The
> server runs fine on `--device mps`/`cpu` (check the bf16 autocast on your torch). The 5× Modal gap
> you saw is the train step, which is the smaller phase — expect ~1.8× longer iterations locally, not
> 5×. Modal-for-training-only is feasible (rl is a standalone step over the store) but the loop won't
> split it for you yet.
- **2026-09-09 update (Discord, Shedletsky / itemfive).** **Shedletsky** (mtgbattles.com; learning
  draft pick rank from what Forge can play well, by simulated games) asked for a test harness with
  a stack of benchmark positions — "chess problems for M:TG" — sensitive enough to read decision
  quality without the 20,000+ games a subtle improvement needs for significance; **Astra pointed him
  at Anvil as "maybe the most sophisticated version of this"** and told him not to write his own.
  **itemfive** offered two sources: [Possibility Storm](https://www.possibilitystorm.com/) ("can you
  win this turn?", 150+ puzzles over 10 years) and the [17lands public datasets](https://www.17lands.com/public_datasets)
  (draft picks AND play data, "match the human choices"; Shedletsky asked whether it filters by
  player skill). **Facts for us:** (a) **Forge ships the puzzles already** — `forge-gui/res/puzzle/`
  holds 371 `.pzl` files (metadata: goal / turns / difficulty; `[state]`: life totals, active
  player and phase, every zone's cards by name and set), **278 of them Possibility Storm** — so a
  puzzle battery is a harness over an engine format we already drive, not a scrape; (b) the
  puzzles' cards are mostly OFF our pool (the network's card table is the pool manifest, 1,701
  cards), so the battery is playable by the network only after **Build 4's open-vocabulary card
  text** (fork I) — or by the search directive alone (the engine values off-pool cards fine; the
  heuristic + lookahead control arm shape) as a puzzle-solving read of the value head; (c) 17lands
  play data is human Limited play on Arena formats — off-pool and off-format, but **the first
  human-games corpus the closeout's skill token / human-shaped levels item needs** (m12-plan done-when
  8; it "needs human games"), reachable once multi-format readiness lands. **Routed by name:** the
  Possibility Storm puzzle battery as a Build 4 read (the search directive solving "win this turn"
  puzzles = a deterministic value-head + search benchmark with exact answers, no games to simulate)
  and 17lands as the skill-token corpus candidate at the closeout. Neither scraped now.

  **Grindstone, honestly, for the reply** (the milestone table + standing rules): what works — drills
  as CERTIFIED evaluation instruments: a window is a drill only if the engine rolled out the
  alternatives (paired counterfactual rollouts, ~8 rolls, horizon part of the label's type), the
  certified "best" is an equivalence CLASS never an index, every drill is provenance-traced to a real
  game, re-certified in era against the winner's curse; certified windows convert to game outcomes
  (+9.2pp per window at game end, ADR-0075). What did not — drills as a TRAINING lever: the first
  drill win (+1.98pp, M4) was one-shot per curation method (M5: −0.58pp on the repeat), critic-ordered
  curation TIED uniform (M8), the natural-timing probe failed (ADR-0060), no promotion since M4 —
  the signal the loop lacked was density, not selection (M6/M7), and the search directive replaced
  drills as the teacher in M12. On his sensitivity question: a certified battery is far more
  sensitive PER GAME for the decisions it covers, but it reads only the positions you selected and
  selection is the hard part (mined windows were non-predictive; uniform sampling found 3.2% of
  payment windows certifiable) — and the aggregate strength claim still needs games: paired by
  seed (common random numbers) 600 games resolve ±1.8pp and 2,000 resolve ±1.1pp, which is where
  his 20,000 unpaired games go.

### Draft reply (09-09; the user posts)

To Shedletsky:

> Anvil's drill system is the thing Astra meant, and here's the honest version. What works: drills
> as certified *evaluation* instruments — a position becomes a drill only when the engine has rolled
> out the alternatives (paired counterfactual rollouts, the horizon is part of the label), the
> "correct answer" is an equivalence class of equally good lines rather than one index, every drill
> traces to a real game, and we re-certify to catch the winner's curse. Certified positions do
> convert to game outcomes (+9pp per position at game end in our last measurement). What didn't:
> drills as a *training* lever — the first drill-curated run gained ~2pp, the repeat gained nothing,
> critic-ordered selection tied uniform, and we moved on to search-based teaching. On sensitivity:
> a battery is much more sensitive per game for the decisions it covers, but it only reads the
> positions you picked, and picking is the hard part (our mined "interesting" windows were
> non-predictive; uniform sampling found ~3% of windows where the choice mattered). The aggregate
> strength claim still needs games — but pair them by seed (common random numbers): 600 paired
> games resolve about ±1.8pp for us, 2,000 about ±1.1pp. Two useful facts: Forge already ships
> 278 Possibility Storm puzzles as loadable `.pzl` states under `forge-gui/res/puzzle/`, so a
> "win this turn" battery is a harness over a format the engine has, not a scrape; and 17lands'
> play data is the only human-play corpus around, though it's Limited on Arena.

### 09-10 follow-up: the Forge MCP / "UCI for MTG" thread (the user posted the drill reply 09-09 17:17; read 09-10, nothing posted)

- **Shedletsky (09-10 09:47):** has anyone built an MCP server for Forge so an LLM (Astra) can play a
  seat directly; wants to "scalably generate thousands of game positions with labeled answers that
  are at least directionally correct"; wishes for a UCI-like common protocol so any two MTG AIs can
  be plugged together. Astra priced a Forge MCP at 3–6 weeks (his gloss: "so it could implement it
  in 30 minutes", the multiplayer plumbing reusable). talor: "mcp is a great idea actually".
- **itemfive (10:07–10:35):** human ↔ human / human ↔ AI-on-server protocols exist (the Manabrew
  protocol, `docs.manabrew.app/protocol/`, a Forge fork supports it); AI ↔ AI is the hard one —
  card state, token representation, **choice selection and ordering**. His K'un-Lun Warrior example
  ("you may sacrifice an artifact or discard a card; if you do, draw"): the same ability prompts as
  a yes/no chain, as a three-button choice with a paid-cost mark, or other shapes — two engines /
  AIs that pick different shapes cannot talk. The Manabrew protocol "is fine for LLM-style AIs",
  not for tree search.
- **Shedletsky:** "possibly the best representation is just English, but that makes any tree
  search suck"; his prior project (an AI mafia server) converged on English because the LLMs that
  can reason over a formalization reason as well over the prose and lose nothing.
- **Fuzz (00:53):** confirms the channel is for AI (and advanced AI workings).

**Assessment (user, 09-10: a Forge MCP is probably not very useful to us, but a neat idea).** Agreed,
with the reasons on record:

- **Not on the loop's path.** The loop is engine-bound (bridge tax 2.6%, the server wait-dominated,
  cores idle at 8 workers); an MCP seat is a prompt-per-callback LLM — orders of magnitude slower
  per decision than the 64-callback gRPC bridge, no search machinery, no batching. The same verdict
  as `@manabrew/forge-wasm` (09-09): relevant only as a Mentor surface (fork H) — an LLM coach
  sitting on the bridge's callback stream, which is exactly what `PlayerControllerAnvil` already
  exposes; an MCP over the bridge would be a thin adapter, not a new engine binding.
- **His actual goal ("thousands of labeled positions, directionally correct") is the drill
  question again**, answered in the 09-09 reply: labels must be engine-adjudicated (paired rollouts),
  never an LLM's opinion of a position — the design invariant (every LLM judgment downstream-
  verified). An LLM playing a seat generates trajectories, not labels; the labels still come from
  the certifier / the search directive's leaf family.
- **The UCI question is the interesting one, and itemfive has it right: the blocker is choice
  representation, not state.** Our answer, for the record: the canonical representation of a
  choice is **the engine's own callback surface** — the seat is asked exactly what Forge asks its
  heuristic (the 20 named callbacks, the priority option list, the seven answer shapes), and the
  option identity is the ability's canonical engine text (`AbilityKey`, the 09-07 pin). That is
  UCI-shaped (any AI plugs in at that boundary and speaks the same protocol — Anvil, the
  heuristic, a random bridge, an LLM) but engine-specific: it canonicalizes by choosing ONE
  engine's prompt shapes, which is the only way the K'un-Lun ambiguity resolves (Forge's
  `PermanentCreatureAi` confirmAction shape IS the shape). A cross-engine UCI would have to
  standardize prompt shapes per rules text, i.e. re-derive one engine's choice model for every
  engine — the same 3–6-week estimate multiplied by engines. Not our problem to solve; the bridge
  protocol spec ([bridge-protocol-v0.md](bridge-protocol-v0.md)) is the public artifact if anyone
  asks "what would a Forge UCI look like".
- **"English as the representation"** is the LLM-native answer and is right for Mentor's
  narration layer; for search it is what fork K rejected (the ability text is embedded once,
  hash-keyed, and the decision surface stays structured — the effect probe AUC 0.98–1.00 says the
  structure loses nothing an LLM would recover).

Routed: nothing new. Mentor-in-browser / an LLM seat over the bridge stays with fork H; a
"what a Forge UCI looks like" note could be a short reply if the thread asks.

**User (09-10):** the Manabrew protocol (`@manabrew/protocol` v5, JSON) is the cross-engine contract
— manabrew's Rust engine and Forge (via `@manabrew/forge-wasm`, or the patched JVM Forge behind
their lockstep harness) both speak it — so any MCP / "UCI" effort in the community ought to start
there rather than invent a protocol; Anvil stays plugged into Forge's controller directly (the
protocol is the human prompt surface, not the 64-callback controller surface, and none of the
search machinery lives there) — no conversion, at least for now.

### 09-13 follow-up: LLM puzzles, LordOfThePigs's draft stack + ability-effect model, Dan B (statisticaldrafting.com) on self-play for limited (read 09-13; the user posted the short reply below)

- **Fuzz (09-10 19:51):** LLMs can already solve puzzles (they know the rules); the in-play gain
  would come from memory; infinite combos are the slow part. **itemfive (21:05):** a Phase developer
  has put serious work into auto-recognizing and executing infinite combos in play.
- **LordOfThePigs (09-11 05:34–09:08), the draft stack in one post** (specs in `npiguet/price-predictor`):
  per-card played/win statistics from ~1M forge-vs-forge sealed games
  (`specs/2026-05-03-card-winnability-pretraining.md`) → a text-only card encoder that predicts
  those statistics for unseen cards (`experiments/2026-05-11-sealed-encoder-hparam-sweep.md`) →
  a deck scorer trained on game outcomes → a deck builder over it (simulated annealing first,
  then a small transformer, `specs/2026-05-19-one-shot-deck-picker.md`) → a draft agent trained
  online (GRPO, `specs/2026-08-04-draft-agent-gen3-online-grpo.md`) to maximize its own deck score
  minus the pod's average; **Forge AI piloting its decks wins >80% vs Forge-built decks**, on all
  draftable sets (>28K cards), not a restricted pool. Behaviour analyses:
  `experiments/2026-08-28-encoder-preferences.md`, `2026-08-27-scorer-preferences.md`,
  `2026-08-29-draft-agent-behaviour.md`. **Now:** ability-level embeddings trained by predicting
  what an ability does to the battlefield when it resolves — two transformers (abilities, game
  state), `experiments/2026-09-04-ability-effect-model-design.md` — with no concrete plan yet for
  a player on top; the candidate is a **"game state scorer"** (per-player visible-info views of
  full-game snapshots labelled by outcome, then a tree search over score increase).
  *Our record:* the ability-effect model is fork K's probe as a training objective (our pin keeps
  the pinned LLM over canonical ability text, hash-keyed; the effect loss stayed an instrument at
  AUC 0.98–1.00, [ADR-0105](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md));
  the state scorer + tree search is Build 1 + Build 2 of M12 (the value head inside the trunk,
  the budgeted lookahead) — our numbers for what that buys are in the reply below. Not Anvil-changing.
- **Dan B (09-12 20:03; maintains statisticaldrafting.com, pick orders learned from 17lands
  data):** 17lands is the bottleneck; wants self-play agents for limited; asks how much work has
  been done on self-play agents that play games of limited, and specifically **how easy/hard it
  would be to train an MCTS-type approach to play a set (his example: the Hobbit set) at a
  reasonably strong level, and how much compute per game.** The presumed purpose: card-quality
  statistics for drafting without 17lands.

**The compute estimate for Dan B (from our run records; one consumer box = Ryzen 9 7950X 16c/32t +
RTX 4090 throughout).** Everything below is "match the Forge heuristic", which is the level every
Forge-based learner in this channel has reached and roughly where all of them sit; "reasonably
strong" beyond it is the open problem (our M12).

| Stage | What it cost us / others | Source |
|---|---|---|
| Engine throughput, heuristic vs heuristic | 64 games/min at 16 workers (~5 s of one core per game); 1,700 g/h with a network seat over the bridge at w=16 | [ADR-0003](../decisions/ADR-0003-m0-closeout.md), [ADR-0009](../decisions/ADR-0009-m1-closeout.md) |
| Imitation (BC) on the heuristic's games | 113,592 games (~30 h generation) → 46.8% vs the heuristic on a 1,701-card pool; **4,000 games → 38.9% on a single-deck mirror** (Kryptic) | [ADR-0009](../decisions/ADR-0009-m1-closeout.md), [devlog 09-07](../devlog/2026-09-07-session2.md) |
| Self-play to parity (V-trace, no search) | Kryptic's mirror: 25 iterations × 480 games ≈ 12K games, ~28 min/iteration (gen ~1,400 s + train ~290 s) ≈ **12 h on one box, 38.9% → 55.2%**; our full pool: parity at M3 (0.5121) then +2pp by M4 over several 20-iteration runs | [devlog 09-07](../devlog/2026-09-07-session2.md), [ADR-0026](../decisions/ADR-0026-m3-closeout.md), [ADR-0033](../decisions/ADR-0033-m4-closeout.md) |
| The failure mode to avoid | Austinio/Kryptic PPO: 200 rounds / 220 h → 30–35%, flat (small-N per-round evals, value-delta rewards) | §1, [devlog 09-07](../devlog/2026-09-07-session2.md) |
| Search on top ("MCTS-type") | our budgeted one-ply lookahead at the day-zero settings: 1.75× forward calls, 2.1–3× wall vs plain play, buys **+2.5pp** for the heuristic and for the network alike (the value head carries it); MageZero (AlphaZero-style on XMage, 300 sims/decision) ≈ 250 g/h ≈ 15× slower than plain play | [ADR-0104](../decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md), §1 |

So for one limited set (~250–300 cards, sealed/draft decks): **on the order of 10⁴–10⁵ heuristic
games for imitation (hours to a day of one 16-core box) plus ~10⁴–10⁵ self-play games (a day or
two on one 4090 + the same CPU) gets a plain policy to heuristic parity; per game that is ~5 CPU-
seconds at heuristic speed, ~2–3× that with a shallow value-head lookahead, ~15× with a full
MCTS budget.** The CPU is the bottleneck, not the GPU (the loop is engine-bound; the 4090 idles at
8 workers). A set is larger than Kryptic's mirror but far narrower than our pool, so the cost sits
between his numbers and ours, closer to his — the deck distribution is the thing he has to supply
(Forge's sealed builder, or LordOfThePigs's drafter, which already beats it >80%).

The caveats that matter for his purpose:

- **"Match the heuristic" ≠ strong.** No learner in this channel has beaten the Forge heuristic
  by more than a few pp with a network alone; our whole M12 is about whether search as the
  behaviour policy gets past that (the day-zero read: lookahead +2.5pp for either policy). A
  self-play limited agent's card statistics will therefore look like the heuristic's card statistics
  plus a small correction — and the heuristic's known holes (declines half of mode choices, no
  combat-ordering sense, payment slack ≈ +3pp/game, [ADR-0075](../decisions/ADR-0075-perfect-payment-headroom.md))
  are exactly the places where a card's value is mis-measured.
- **For card quality you may not need a learned player at all.** LordOfThePigs's stack derives
  per-card played/win statistics straight from ~1M forge-vs-forge games and pretrains a text-only
  encoder on them; that is the 17lands-replacement he is asking for, and it is already built and
  analysed. A learned player only changes those statistics where it plays differently from the
  heuristic in card-relevant ways — which is the same open question.
- **The rule we would push hardest:** never read strength from per-round small-N evals; a
  2,000-game paired read every 5–10 iterations (±1.1pp) is what separates the runs that climbed
  from the ones that reported climbing ([standing-rules.md](../standing-rules.md)).

**Posted reply (the user, 09-13; supersedes the longer draft below, which stays for the numbers):**

> Well, how strong do you need? LordOfThePigs is getting really good drafting data from running
> Forge's standard heuristic bot against itself, but if you want less-consistently-biased play, my
> guess is that the Anvil architecture can currently get to par with Forge on most arbitrary sets
> with a few days of training time on one consumer box. Kryptic recently tried Anvil on a
> single-deck mirror, and it reached a 55% winrate against the heuristic with less than a day of
> training. For scale, Forge itself runs ~5 CPU-seconds per game heuristic-vs-heuristic, so a
> 16-core desktop does ~60 games/min. The CPU is the bottleneck, including on ML bots. Shallow
> search added another ~2.5pp in our read, to either Anvil or the heuristic bot, at ~3× the
> compute. But I don't think anyone's managed to get much past 55% against the heuristic bot, so
> if you don't care about its issues with signets, sticking with the heuristic is probably good
> enough.

Unposted longer draft (the numbers, if he follows up):

> Some numbers from Anvil (BC → V-trace self-play on Forge, 1v1 Commander, ~1.7K-card pool), all
> on one box (7950X + 4090). Forge runs ~64 games/min heuristic-vs-heuristic at 16 workers, ~1.7K
> games/h with a network seat in the loop; the engine's CPU is the bottleneck, the GPU mostly
> idles. Imitation on ~114K heuristic games got us to ~47% vs the heuristic; V-trace self-play
> from there reached parity (~51%) and then +2pp. The clean data point for a narrow pool is
> Kryptic's run last week on a single-deck mirror: 4K BC games → 39%, then 25 iterations × 480
> self-play games (~12h, ~28 min/iteration) → 55%. A set is between that and our pool, so I'd
> budget ~10⁴–10⁵ heuristic games + ~10⁴–10⁵ self-play games, a few days on one consumer box, to
> match the Forge heuristic on one set. Per game: ~5 CPU-seconds plain, ~2–3× that with a shallow
> value-head lookahead (what we run; it's worth about +2.5pp for either policy), ~15× with a full
> AlphaZero-style MCTS budget (MageZero on XMage ran ~250 games/h at 300 sims/decision). Two
> caveats: nobody here has beaten the heuristic by more than a few pp with a network yet, so
> "reasonably strong" past parity is the open problem, and the card statistics such an agent
> produces will mostly be the heuristic's statistics; and for card quality per se,
> LordOfThePigs's card-winnability stats from ~1M forge-vs-forge games are already the thing —
> a learned pilot only moves them where it plays differently from the heuristic. Also: read
> strength with ≥2,000-game paired evals every few iterations, never per-round 100-game evals —
> that's what separated the runs that climbed from the ones that reported climbing.

**Dan B's follow-up (09-13 21:06):** the goal is 17lands-style draft statistics from self-play; a
few misplays are fine, "a reasonably-human play style would be a big plus."

*Assessment (for the record):* his stats split in two. The game-side family (GIH WR, OH WR, IWD)
needs per-game draw/cast logs plus the outcome and a pilot whose errors are **card-uniform**; the
heuristic's known holes are card-class-correlated (declined modes → charms/Confluences, payment
slack → mana rocks, no combat ordering → tricks), and Anvil inherits the payment one (the head
withheld after five negative reads). The pick-side family (ATA, ALSA) is circular in self-play:
it describes the drafter, not the cards. Useful honesty check: each card's winrate under two
pilots (heuristic vs trained, plain vs search) — the cards whose number moves are where pilot bias
is the error bar. Ante's AIVAT correction applies to per-card winrates and would cut games per
card. Human-like play: no human Forge corpus exists (17lands has draws and outcomes, no in-game
decisions); ours arrives only after blunder detection gives Forge players a reason to record
games — the Mentor route. Not Anvil-changing; nothing routed.

**Posted reply (the user, 09-13):**

> Hm, yeah, human-like is trickier. I'm hoping to eventually give Anvil the ability to target
> human-like skill levels, but I'm not aware of any human-play database usable to train such a
> thing, since 17lands doesn't have within-game decisions. My plan was to eventually use the Anvil
> model to implement blunder detection, so Forge players could record their games and have the bot
> identify mistakes, and then convince some of those players to send me their recorded games to
> calibrate human play and difficulty ratings.
>
> Is your hope to use self-play data to determine the value of cards in the draft? Or are you
> hoping to directly generate pick orders from bot drafting? For the former, I'd guess that both
> the heuristic bot and Anvil are good enough for most purposes, but you'll get a systematic bias
> on the cards they aren't good at, like signets. I'm still hoping I'll be able to fix that
> problem, but it's been persistent, even in Anvil. For draft orders themselves, LordOfThePigs
> seems to be significantly outperforming the Forge default drafting bot, but probably neither
> drafting bot really drafts in a human-like way.

**09-14 follow-up (the morning thread; nothing posted):** Dan B ran 30K HOB games on the stock bot
(blue loses, Smaug top common — the instants bias at colour level), asked where Anvil is
(itemfive: the repo); Shedletsky (100K games/day, offering raw Forge logs; decklist-level pilot
hints; the two-card-synergy question), LordOfThePigs (1M games = a week on 3 machines; rules of
thumb: good at combat, bad at spells, esp. instants), talor (fixed-deck curricula train faster;
cubecobra decks through Forge show white/red aggro over-realized), chrismaghuhn (pilot bias
leaks into rankings; keep win/loss as reward, plans as conditioning; paired seeds). Two
corrections for our record: **17lands' replay data does carry per-turn human actions** (casts,
attacks, blocks; no decision context) — routed as a Mentor calibration lead; and the repo needed
a newcomer path → [quickstart-custom-pool.md](quickstart-custom-pool.md) (09-14), which also
exposed and fixed the selfplay/final_read Commander hard-coding.

### 09-14/15 follow-up: pre-release freeze proposal, tinymtg, LordOfThePigs's card win rates, the GUI-owned combat legality (read 09-15; the user posted the quickstart link 09-14)

**#ai-plotting (09-14 → 09-15):**

- **The user (09-14 10:48)** posted the [custom-pool quickstart](quickstart-custom-pool.md) for the
  external users, with the position on pre-release meta prediction: no bot is human-like enough to
  decipher a Limited meta before release; break the question into what the existing tools can
  answer precisely; the fixed-matchup route works (Kryptic's single-deck mirror was the fastest
  climb seen here); a specific release lets you check against the real meta afterwards, but
  human-like play needs full replay data.
- **chrismaghuhn (09-14 10:52) — the pre-release freeze proposal:** freeze the pre-release
  predictions before Arena data exists, then compare against 17Lands afterwards — not just
  archetype win rates but **where Anvil and Forge disagree and which one lands closer to human
  play**; over a few sets that maps the simulator's and the pilot's biases instead of a one-off
  tier list. *Our read:* a cheap, well-posed external validation that costs us nothing until a new
  set is in the pool — the pool pipeline is set-sized by construction ([ADR-0018](../decisions/ADR-0018-ruleset-scope-clarification.md)),
  the quickstart already builds a pool from any decklist, and Build 4's text-hash-keyed ability
  text + format-as-features is what makes an unseen set playable by the network. The disagreement
  read (Anvil vs the heuristic vs 17lands per card / archetype) is the same instrument as the
  17lands skill-token corpus routed at the closeout. **Routed by name: "the pre-release freeze"
  as a closeout-era read** (a Limited set through the pool pipeline, predictions committed before
  release, the 17lands comparison after; a set that lands during the big run's envelope is the
  natural first sample). Nothing to build now; the sets are not on the M12 path (no Pauper / no
  Limited in M12).
- **talor (09-14 18:53 → 09-15 16:13) — `tinymtg`** ([github.com/talor-a/tinymtg](https://github.com/talor-a/tinymtg),
  public 09-15): a TypeScript rules engine under a 10K-LOC target, "a fun side project" —
  playable state, no performance work yet, **fully deterministic**, 4,500 cards from Forge's
  catalog playable. The card model: a `CardDef` (attributes + abilities authored in JS, a mix of
  callbacks and structured effects); `forge/parser.ts` translates forge-script to it **ahead of
  time** — the engine never interprets Forge's grammar, so it is not tied to Forge. Effects are an
  array, not forge-script's `SubAbility` chain, which he already finds limiting (Rite of
  Consumption plumbing a variable across effects; replacement effects are callbacks for the same
  reason). chrismaghuhn's questions (language, gameplay vs throughput, card implementation,
  determinism / snapshot / fork, the benchmark unit, open source) are the right checklist; the
  "faster than any alternative" claim is a goal, not a measurement (no optimization done, no
  benchmark named). itemfive: "forge-script does the same thing, we just took different routes.
  And forge works." *Our record:* a translated-subset engine over forge-script is the shape the
  gated Rust-subset item assumed; a 4,500-card ahead-of-time translation is a data point that the
  translation is tractable. Throughput is still not binding for us (the JFR week: the mask memo,
  PR 11916, the box's cores), so the item stays gated. Fidelity is the question for any such
  engine — and the only way it enters our world is through a forkcheck-style twin against Java
  Forge (manabrew's lockstep harness is that instrument). Not Anvil-changing; watch the benchmark
  when it comes.
- **itemfive — `mtgish`** ([github.com/i5jb/mtgish](https://github.com/i5jb/mtgish) + a proof-of-
  concept card creator): a common card format so that rules-engine authors can "interpret mtgish"
  once and have the whole library; documents the rules and provides test cases. His own TS engine
  has 10K lines of type definitions, 2K for tokens + layer-1 copy, 5K of tests, "and it doesn't
  even work". Adjacent to fork I (the open card vocabulary) only as a format; nothing routed.
- **LordOfThePigs (09-15 05:17, 05:42) — the card win-rate data, shared for Shedletsky:** a
  `cards-win-rates.7z` on Google Drive plus a folder with the **Bo1 match outcomes and the list of
  cards played by both players per match** used to derive them (from his forge-vs-forge sealed
  harness; the ~1M-game corpus behind the winnability pretraining, §1 09-13). *Our read:* a
  heuristic-derived per-card played/win table across all draftable sets is a Tutor pretraining
  asset and a pool-curation signal (the "cards the Forge AI never plays" list, §2), and a natural
  comparison for our own pool's card statistics; it carries the heuristic's biases (§2) exactly
  as our corpora do. **Not downloaded** (the user decides; the Drive links are in the channel).
  Worth pulling when Tutor work opens — routed by name there.
- Fuzz: "deck hints" as an LLM-AI input (a Forge deck-file feature); nothing for us.

**#contribution-questions (09-15):**

- **Sudo_Dudo (12:55) asked why the GUI module owns combat / damage-assignment legality rather
  than forge-game. Jetz (core): not a design choice — it predates the module split; "ideally any
  validation and legality stuff like that could be specified or checked entirely by the game
  module. But it's a lot of stuff to relocate in an elegant way." The same holds for
  `PlayerControllerHuman` and the cost / target `Input`s, which carry a lot of validation logic
  (at least in the shared gui module, not duplicated across desktop and mobile).** *Our record:*
  this is the field guide's finding stated by a maintainer — the engine never validates AI-path
  combat ([forge-ai-field-guide.md](../forge-ai-field-guide.md): `CombatUtil.validateBlocks` runs
  for human input only; the requirement fixed-point is ours, [ADR-0016](../decisions/ADR-0016-d5-closeout.md)),
  and evening 3's damage surface had to carry its own modern-rule enumerator family for the same
  reason ([ADR-0105](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  A maintainer naming the relocation as desirable-but-large is the opening for an engine-side
  legality surface as an upstream contribution (blocks: the requirement fixed-point; damage: the
  lethal-assignment rule) — small, tested, and both a GUI rewrite (Sudo_Dudo's Arena-look client)
  and every AI controller would consume it. **Routed by name to the upstream worklist** (the
  rebase era; no M12 dependency).
- Sudo_Dudo wants an Arena-look match UI; his friends won't play on Forge's. talor pointed at
  manabrew.app as a web front end over Forge; itemfive listed the front-end landscape:
  **Manabrew and Endstep (forge-ish forks), Phase (independent; some forge-isms), Argentum.**
  MostCromulent: coordinate rather than reinvent, ideally something incorporable into Forge proper.
  itemfive: **Endstep keeps a patches repository; manabrew is dropping its port-Forge-to-Rust
  effort** and contributed the patches that build Forge to wasm for the web; the state of their
  generic engine-to-frontend protocol and whether it would ever be incorporated is unknown.
  *Our record:* the §1 manabrew row is out of date on the port (the Rust engine is being dropped;
  the product is now Java Forge in wasm behind their protocol) — corrected in the table. The
  Arena-look demand is the playable branch's / Chronicle's audience; nothing routed.

### 09-16 follow-up: Shedletsky's runner fleet, the AI-speed thread, talor's cache PR, khaliostr's engine module (read 09-16; the user posted once, 09:15)

**#ai-plotting (09-15 22:29 → 09-16 09:15):**

- **Shedletsky (09-15 22:29): "finally got all of the bottlenecks out of my ersatz distributed
  mtg compute cluster"** with a dashboard screenshot — *Simulation capacity · Runner fleet*:
  4 recent machines, 92 maintained workers (requested target 92), 90 active games, **1,097
  games/min over the last minute (+189 vs the previous), 1,024.80 over 5 min, 1,020.93 over 15
  min**, workers 98% busy, 2 failures in the last minute, 3 runners online. ≈ 61K games/hour;
  ≈ 12 games per worker-minute ≈ 5 s per game per worker (heuristic-only play, presumably the
  Limited formats of his winnability corpus — inferred, not stated). Failures ≈ 0.2% of games,
  the same order as talor's 0.5% (§2) and our crash census. *Our record:* the same shape as our
  fleet supervisor (a maintained worker count, a requested target, busy %, a per-minute rate) but
  multi-machine; our recipe is 294 g/h on one box because the search and the served network are
  the price, not the engine. A multi-machine runner fleet is the lever if the big run's envelope
  ever needs more than the box — noted, nothing routed.
- **LordOfThePigs (04:36): Forge AI "several times faster"** after moving his checkout from March
  to last week. **khaliostr (04:50):** work is happening; on some boards the AI is still really
  slow — forge-wasm sees the AI take minutes on a choice. **Fuzz (05:05):** the AI needs to skip
  past thinking on big board states — "a card in hand and evaluates every possible use for that
  card against 100 board objects." **khaliostr (05:28):** the same in production; instrumenting
  decision latency in the browser made the pathological states visible (exhaustive evaluation of
  actions / targets); **they added budgets inside the evaluation / declaration loops** (needed on
  wasm, no threaded timeout there; desktop stalls measured too) — **not upstreamed because, unlike
  the cache / perf work, a budget changes AI play once it is exhausted**; offered to split them
  out. **TRT (06:01):** many API heuristics are written poorly or check more accurately than they
  need to; a clean effort should group helpers, give them slow / fast modes, reuse `AiCache`;
  **"relying on nondeterminism should remain a last resort."** *Our record:* (a) the March → September
  speedup is upstream's own cache / perf work (khaliostr's #11916 and #11925 among it; §1 corrected:
  khaliostr is the author of both, they were never ours — we had queued #11916 for the rebase as
  a pending upstream PR, and it merged 09-14); (b) Fuzz's class is the JFR read's — the payability
  mask, the static checks, the replacement scans per candidate × board object — and our
  mana-source memo (fork `1dd36f7342`) is a patch for exactly that class, an upstream candidate;
  (c) **the budgets are a hazard for us if they land as wall-clock defaults: deterministic replay
  is load-bearing for four systems; our position when the split-out comes is count-based budgets
  (the search directive's budget unit is forward calls for this reason), flag-gated, off by
  default; TRT's line is the same position** → routed to the upstream worklist as a watch item.
- **talor (08:35, again in #contribution-questions 08:44): "this should probably get upstreamed"
  — [Tyrathalis/forge#1](https://github.com/Tyrathalis/forge/pull/1)**, his AI block-legality
  cache PR against OUR fork (opened 08-10, merged 08-11 as fork `8044e36366` + our follow-up
  `6f5e1643b2`): `predictNextCombatsRemainingLife` was up to 60% of long games re-walking static
  abilities for the same attacker / blocker pairs across assignment passes; a per-invocation cache;
  hit rate 30–60%; **500-game read: total CPU −15.6% (3,887 → 3,282 s), median 5.25 → 4.41 s, p90
  15.57 → 13.15 s, faster in 478/500, determinism preserved 500/500.** *Our record:* this is the
  fork's `AiBlockController` delta (195 lines) and one of the rebase's two real conflicts (upstream
  #11790 changed the same region 09-06) → **queued on the upstream worklist as the first post-launch
  upstream patch**, talor as author.
- **The user (09:15):** preparing the long Anvil run, then proposing upstream patches one at a
  time while it runs; asked for priorities. *Our record:* the upstream worklist's schedule is now
  stated publicly — the big run's envelope is the upstreaming window.

**#contribution-questions (09-16 03:38 → 08:44), continuing the 09-15 GUI-legality thread:**

- **khaliostr (03:38, 05:22):** keen to collaborate with upstream; a batch of engine perf
  improvements from profiling forge-wasm being upstreamed; **Endstep's patches integrated for
  server-side play** (not their wasm path — one game per browser runtime — but the hosted case);
  **the Forge front-end / back-end boundary split as a module that lives entirely in Java and
  keeps Forge semantics** — Manabrew's web UI sits on it through their protocol, nothing
  Manabrew-specific in the layer; **their `forge-engine` layer runs as a Java module, compiles to
  wasm (browser / node, callable from other languages), or runs as a server exposing Forge through
  the Manabrew protocol**; not upstream — that would need the module upstreamed and the existing
  UI bindings moved onto its API, "a fairly sizable undertaking," but working in their repo.
  **Fuzz (05:11):** an engine independent of the UI is the end state. *Our record:* the engine-side
  legality surface (the 09-15 item) and khaliostr's module are the same direction from two ends —
  a validated engine API for any controller is what his module needs and what our controller
  carries fork-side. The §1 manabrew row corrected (the module, the perf upstreaming, Endstep).
  Nothing on the M12 path changes.

### 09-17 follow-up: TRT's AiCache condition on the cache PR, the anytime-search / metrics thread, Kryptic's four-deck matchup read (read 09-17; the user posted twice on Jev, nothing else)

**#contribution-questions (09-16 05:11 → 14:14), the tail of the engine-module thread:**

- **TRT (10:46), replying to talor's cache PR post ([Tyrathalis/forge#1](https://github.com/Tyrathalis/forge/pull/1)):
  "thanks, though existing systems need to be reused for less technical debt — in this case
  AiCache."** *Our record:* a maintainer's condition on the first post-launch upstream patch,
  recorded on the worklist item. `AiCache` (forge-ai) is a global static string-keyed multimap of
  (result, args) rows with per-arg comparator functions, linearly scanned, cleared once per
  `AiController.chooseSpellAbilityToPlay` (its own TODO: "add different scopes + staleness
  indicator"); today `AiDeckStatistics`, `ComputerUtil` and `ComputerUtilCombat` use it. talor's
  cache is scoped to one `assignBlockers` invocation with the context entries cleared on every
  combat mutation — a scope `AiCache` does not have, and its once-per-priority clear is coarser
  than the mutation clears the block cache needs. So "reuse AiCache" means either (a) the pair
  entries move into `AiCache` under a key that names the combat mutation epoch, or (b) `AiCache`
  gains the scope its TODO names, and the block cache is the first user. (b) is the smaller
  diff for the maintainers and the one that answers TRT's "group the helpers, slow / fast
  modes" direction from the same day. The fork keeps talor's version until the PR is written
  (identity-gated in every forkcheck since 08-11; the PR is a rewrite of the storage, not of
  what is cached) — routed to the worklist item.
- Fuzz on Java → JavaScript: a few methods unsupported, a `returnSelf()` workaround, TypeScript
  might have fared better. Colour; nothing for us.

**#ai-plotting (09-16 09:32 → 09-17 08:49):**

- **khaliostr (09:32) on talor's cache:** anything that cuts AI thinking time and the cost of
  statics / effects is welcome for their use case. Confirms the cache PR's audience beyond us
  (Manabrew's wasm build has no threaded timeout — every AI millisecond is a UI stall there).
- **Shedletsky (13:05): with the exhaustive search the AI sometimes has "infinite options and
  will hang forever"**; two PRs for the cases he found; the better fix is up the tree — chess's
  standing "winning line": keep the current best answer, improve it while there is time, return
  it when time runs out, so a move is always ready within the budget. **~1% of games between
  random decks of unlimited cards hang past his 3–10 minute cutoff, and the hangs correlate with
  specific cards, not an independent draw, so they bias his statistics.** TRT (13:13): the AI is
  greedy — "first thing playable" is already the shape; reusing an earlier phase's answer would
  obviously misplay. Shedletsky (13:46): "i don't think it matters what the AI does if it takes
  10 minutes to figure it out." *Our record:* (a) the anytime shape is exactly the search
  directive's contract — a budget in forward calls, the natural line always in the option set,
  so an answer exists at any cutoff ([ADR-0101](../decisions/ADR-0101-architecture-review-m12-recharter.md)
  Build 0) — the count-based budget is the point (the 09-16 watch item: a wall-clock cutoff
  breaks seeded replay); (b) the hang class is ours too: Build 0's game-time / repetition caps,
  then the Build 2 loop game → the loop guard (fork `b4825285529`: a bounded engine re-ask,
  `Census.loopCheck`, the 900 s clock allowance), and the crash census counts the residual by
  seed and class; (c) **his statistics point is right and worth restating to the channel: a hang
  cap is a card-correlated censor, so a fleet that drops hung games biases every per-card rate
  toward the cards that never hang** — our census records the seed and the kill reason so the
  censored set is a named population, not a silent drop. His two PRs are the upstream shape;
  the loop guard is a candidate to describe when the budget conversation resumes. Nothing routed
  beyond the existing watch item.
- **Dan B (19:33 → 20:36): an AlphaZero-style agent for a limited format** — MageZero as the
  agent, distributed CPU training on AWS (Ray), games between random 17lands decklists; asked
  Forge vs XMage, MageZero vs LordOfThePigs's baseline. **chrismaghuhn (19:51):** XMage for
  MageZero — the state extraction and MCTS / self-play plumbing exist there, Forge would mean
  building the ML interface; **MageZero is deck-local, and random 17lands decks want a policy over
  arbitrary pools — the bigger architectural problem than the distributed training**; prototype
  one format + a small fixed deck pool, validate legal-action completeness / hidden information
  / throughput, then Ray / AWS. Dan B settled on deck 1 vs deck 2 first, then any-vs-any. *Our
  record:* the deck-local warning is the §1 MageZero note (a fixed-deck agent searching with
  `see_opponent_hand: true`) said by someone else; "one format + a fixed pool, then widen" is the
  pool-scaling rule ([ADR-0018](../decisions/ADR-0018-ruleset-scope-clarification.md)) restated for
  limited. Anvil already plays arbitrary decks from a pool (the card-text embedding path is the
  answer to "deck-local"); if he asks, the quickstart is the reply. Nothing routed.
- **The metrics sub-thread (talor 20:04, chrismaghuhn 20:09 / 20:16):** talor — spells cast and
  game length are cheap and track learning ("more spells cast seems to correlate with better
  performing, since at the start the ai needs to learn to do anything at all"); the harder ones
  are target sanity (own creature targeted with a good effect, opponent's with a bad one).
  chrismaghuhn — two families: **behavioral sanity** (spells cast, mana spent, passing with a
  playable action, bad targeting) and **strength on a fixed evaluation set** against frozen
  checkpoints / scripted baselines; keep matchups separate, not an aggregate; deck 1 vs 2 for a
  clean curve, then a cross-play matrix; **checkpoint × opponent × archetype separates genuine
  improvement from getting stuck from cycling between strategies**; his four rows — environment
  health (spells cast, game length, illegal actions, hangs), behavior health (bad targets,
  wasted mana, idle turns, pass-with-play), learning (value error, policy entropy, BC agreement,
  training curves), actual strength (large fixed eval sets, per-matchup win rates, frozen
  opponents / checkpoints, held-out decks). *Our record:* this is the monitor's panel set named
  from outside — environment health = the crash census + veto rate; behavior health = casts /
  game, first-veto rate, the pay directed-fail / salvage rows, the drills; learning = kl_mu,
  entropy, v0, BC agreement; actual strength = the arms read vs the frozen heuristic and
  `final_read.py`'s 2,000-game paired protocol on a fixed population ([ADR-0096](../decisions/ADR-0096-m10-closeout.md)).
  His "cycling between strategies" is the mirror-population hazard of the fixed-population rule.
  Kryptic's workbook below is the checkpoint × opponent × archetype matrix built the same day.
  Nothing new to route; the four-row framing is a good structure for the quickstart's "what to
  watch" paragraph — noted for the documentation pass.
- **talor (20:23, 21:43): TypeSafe's Jev** (a "System One" decision model, no chat) — can it play
  MTG? Their chess post: Jev V13 vs frontier LLMs at 5+0 blitz, one API call per move — Fable
  outplayed it, Astra was quick. **The user (20:31, 21:53) posted:** it likely plays passably
  and fast, and would lose to Fable or Astra at their own speeds. Colour; nothing for us.
- **Shedletsky (09-17 00:42): the fitness metrics of his deck-evolution population**
  ([mtgbattles.com/Lab](https://mtgbattles.com/Lab)): (1) the 25th / 50th / 75th / 100th
  percentile decks (clusters of five) against a fixed set of **standard-candle decks** that never
  change — the win rate should rise if learning is happening; (2) **periodically resurrect decks
  cut from the population as unfit and count how many are re-eliminated after X generations** —
  most should be if fitness is increasing. *Our record:* (1) is the frozen-reference rule (the
  heuristic + `iter-019` as our candles); (2) is a held-out re-test of the selector against its
  own past verdicts — a curation-audit shape we do not have and Tutor could use (a resurrected
  deck's re-elimination rate is a selector consistency read that needs no new opponents).
  **Routed by name to Tutor's scoping** (the deck-search fitness audit); nothing on M12.

**Kryptic (09-17 08:49): a second Anvil run — gen / clone / RL on the four mono-coloured decks**
(the same four he and Austinio used months ago; the `.dck` files and the workbook are kept at
[community/constructed-four/](community/constructed-four/)). Blue Tempo (Delver, Augur, Snapcaster,
Counterspell, Mana Leak, Spell Pierce, Opt, Ponder, Thought Scour, Vapor Snag), Green Stompy
(Elves, Mystic, Tusker, Baloth, Strangleroot, Experiment One, Rancor, Aspect of Hydra, Vines,
Giant Growth), Red Aggro (Bolt, Shock, Swiftspear, Goblin Guide, Eidolon, Lava Spike, Searing
Blaze, Rift Bolt, Shard Volley, Skullcrack), White Weenie (Lions, Vanguard, Dryad Militant,
Soldier of the Pantheon, Precinct Captain, Thalia's Lieutenant, Honor of the Pure, Path, Brave
the Elements, Raise the Alarm); 20 basics each. His command line (the second reference
Constructed recipe, after the 09-07 mirror):

```
python -m anvil.training.selfplay --name constructed-four-rl-4000 \
  --ckpt data/training/constructed-four-auto-20260909-211341/last.pt \
  --pairs-file data/pool/custom/constructed-four-rl-pairs-40k.txt \
  --format Constructed --pool-version constructed-four-v1 \
  --iterations 40 --games 2000 --games-per-pair 2 --heur-frac 0.5 --workers 4 \
  --reask --penalty 0.01 --penalty-grouping first --chunk 10 --port 50076 \
  --seed-base 20260904 --rl-workers 0 --rl-seg 64 --guard-kl 0.15 --guard-veto-mult 20.0 \
  --traj-per-step 4 --epochs 1 --lr 1e-5 \
  --arms-every 10 --arms-games 4000 --arms-pairs data/pool/custom/constructed-four-arms-pairs-800.txt \
  --no-inhibit
```

(For the first ~25 iterations the arms read was 2,000 games every 5; from there 4,000 every
10. The workbook's Wilson CIs; crashes / non-won games count as non-model wins, as
`arms_report.json` does. Every off-diagonal cell pools both seat assignments; his mirror cells
compare against 50%.)

*The reads, verbatim from the workbook:*

| Arm | Games | Model wins | Overall (95% CI) |
|---|---|---|---|
| Heuristic vs heuristic (`HvH_40000`) | 40,000 | — | the reference matrix |
| BC (`constructed-four-auto`, 8,000 imitation games) | 8,000 | 3,248 | **40.6% [39.5, 41.7]** |
| RL iter 5 / 10 / 15 / 20 | 4,000 each | 1,749 / 1,805 / 1,968 / 2,025 | 43.7 / 45.1 / 49.2 / 50.6 |
| RL iter 30 | 8,000 | 4,091 | **51.1% [50.0, 52.2]** |
| RL iter 40 | 8,000 | 4,051 | **50.6% [49.5, 51.7]** |

The heuristic-vs-heuristic matrix (row deck's win rate, 40,000 games, seat 0 on the diagonal):
Blue Tempo 51.3 / **15.1** / **26.5** / **16.3**; Green Stompy 84.9 / 50.9 / 66.2 / 51.0; Red
Aggro 73.5 / 33.8 / 51.6 / 32.2; White Weenie 83.7 / 49.0 / 67.8 / 52.8 (columns Blue / Green /
Red / White). Under the heuristic the deck order is Green ≈ White > Red ≫ Blue; the seat-0
edge in the mirrors is 1–3pp.

The model-vs-heuristic matrices (model deck = row, 500 games per cell, each cell's 95% CI
≈ ±4.4pp, a cell-vs-cell difference ≈ ±6.2pp), as the change vs the heuristic's own rate in the
same matchup (mirror cells vs 50%):

| Model deck → heuristic deck | vs Blue | vs Green | vs Red | vs White |
|---|---|---|---|---|
| Blue Tempo (iter 30 / 40) | +5.8 / +2.6 | **+10.7 / +5.1** | +2.1 / −1.7 | +5.1 / +6.1 |
| Green Stompy | −0.1 / −0.9 | −0.6 / −1.4 | +4.4 / +3.6 | −3.2 / −5.4 |
| Red Aggro | +2.9 / +7.3 | **−7.6 / −7.4** | **−14.8 / −11.2** | +2.2 / +8.0 |
| White Weenie | +6.7 / +5.1 | −0.4 / −5.8 | +4.4 / +6.0 | +0.6 / +0.2 |

vs the BC every cell is up (+0.9 to +27.2); the BC's Red row was the catastrophe (BC Red Aggro
14.9–18.1% off-diagonal, 16.7% in the mirror, 53.6% vs the heuristic's Blue where the heuristic
itself takes 73.5) — imitation on 8,000 games could not play burn at all, and the loop recovered
most of it (Red vs Blue 53.6 → 80.8, Red vs White 14.9 → 40.2) but not to the heuristic's level
against Green or in the mirror.

*His monitor (40 iterations, the screenshot):* reward 0.459 → 0.495 and v0 0.45 → 0.48–0.50
(peaking at iters 32–35); **entropy RISING 0.25 → 0.34 (iter 32) → 0.29** — the opposite of
his 09-07 mirror's decline; kl_mu 0.005 → 0.12 (iter 35) → 0.075, against his 0.15 guard;
veto rate 0.025 → 0.12–0.25 (×5–10; his guard sits at ×20, never tripped); first-veto rate
0.025 → 0.16–0.22; rejected / traj 0.35 → 2.2–3.6 (×7–10); casts / game 20 → 21–25 with a
spike at iters 30–36 coincident with the entropy / kl / veto excursion; turns median 12–13;
**pay deviation (sampled) 0.32 → 0.10 (iter 10) → 0.85–0.97 (iters 30–40)** with directed_fail
and salvage exactly 0 throughout (every deviation executed clean); pay_bias 1.481 → 1.486 →
1.476 and pay_kind_emb rms 0.0001 → 0.003 (the head's own parameters barely moved — the
deviation rate rode the shared trunk); gen_s ≈ 6,200–7,300 for 2,000 games on 4 workers
(≈ 1,100 g/h), train_s ≈ 1,450 → ≈ 2.2 h per iteration, ≈ 88 h for the run.

*Our read (for the record; a draft reply below):*

1. **The aggregate is a plateau from iter 20** (50.6 → 51.1 → 50.6; iter 40 − iter 30 = −0.5pp
   ± 1.55 at n 8,000 + 8,000 — a null, not a decline). His "gains slowed" is the right reading;
   "went down" is not supported. Per-cell iter-30-vs-40 differences are ±6pp reads on 500 games
   each, so the "some matchups better, some worse" pattern between 30 and 40 is noise except
   possibly the Blue row (−3 to −6) and the Red row (+3.6 to +5.8), both marginal. The rule he
   already applied on 09-07 (small-N per-round evals never carry a claim) applies to cells.
2. **The plateau's onset coincides with the guard curves' climb** (iters 20–35: vetoes ×5–10,
   rejected intents ×7–10, entropy +0.09, kl_mu to 0.12). Under the standing veto account the
   veto channel is the model's affordability probe and its rise is not by itself the strength
   mechanism ([ADR-0072](../decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md)) — but
   this run's entropy RISES while the vetoes climb, which is the policy broadening onto casts it
   cannot afford rather than collapsing; his 09-07 run had the opposite entropy slope under a
   ×4 veto guard. The `--guard-veto-mult 20` he chose never binds; the ×4 of the first run
   would have paused the run near iter 20, roughly where the strength stopped moving. Not a
   claim of cause; the one cheap test is an arms read of the iter-20 ckpt at 8,000 games against
   iter 30 / 40 (if 50.6 at n 4,000 holds at n 8,000, twenty iterations bought nothing, and the
   guard question is live).
3. **The red mirror is the one structural deficit:** 35.2 [31.1, 39.5] / 38.8 [34.6, 43.1]
   against 50 — −11 to −15pp, real at 500 games — plus Red vs Green at −7.5. Burn is the deck
   whose decisions are the ones imitation learns worst and the loop reaches slowest: face vs
   creature for every burn spell (the target choice, coupled with the cast in our CastPlan but
   trained only from the heuristic's targets), Eidolon's symmetric trigger, Searing Blaze's
   landfall timing, Rift Bolt's suspend line and Shard Volley's land sacrifice as sequencing
   choices. The BC's Red row (15–18%) says the imitation had almost nothing to start from; the
   loop's +20pp on it is the largest single-row gain in the run and it still sits below the
   heuristic. A trace-level read of Red-mirror games (face-vs-creature target rate, burn spells
   cast per turn, Eidolon kept or traded) against the heuristic's would locate it — talor's
   "bad targeting" metric class; our instrument for it is the drill (Grindstone), which he does
   not have to build.
4. **Blue Tempo's gains are the interesting positive:** the heuristic plays the deck at 15–27%
   against the other three; the model as Blue gains +5 to +11 vs Green and White (the
   counterspell / bounce decisions the heuristic is known to play badly — a spell-focused deck
   is where a learned policy beats a scripted one first), and the model AGAINST the heuristic's
   Blue gains +3 to +7 (Red, White) — exploiting the heuristic's Blue, a different thing from
   playing Blue well. His question "is mono-blue just bad, or is the heuristic bad at it?" has
   a bounded answer: at least +5 to +11pp of the heuristic's deficit is play, not deck; the
   deck's ceiling under good play is not identifiable from this data.
5. **The pay panel is a watch item for him:** the sampled deviation rate at 0.9 with zero
   directed failures means the head directs nine of ten payments and the engine executes
   every one — but our five served pay heads each read within one SE of zero-to-negative
   ([ADR-0105](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)
   addenda: −0.3 to −1.7pp), and the headroom under perfect payment is ≈ +3pp/game in ≈ 3% of
   windows ([ADR-0075](../decisions/ADR-0075-window-rate-sweep.md)) — a 90% deviation rate
   is far past where auto was already right. On the M12 recipe the tag is withheld
   (`final_read.py --server-tags` without the pay tag reads the same ckpt with auto payment);
   an ablation arm of that shape would price it on his run in one 8,000-game read. **And the
   probe cost: if his fork jar predates 09-09 (`15863de0b4a`, `quietProbe`), every bridged
   payment window draws RNG and writes AI memory — the ≈ 2.7pp every M12 network arm carried
   ([ADR-0105](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)
   evening 4)**; his BC dir is dated 09-09 21:13, five hours after the fix landed, so it is a
   question, not a diagnosis.
6. **Design notes we take from it:** (a) the per-matchup matrix at equal cell weights is the
   right shape (chrismaghuhn's checkpoint × opponent × archetype, built), and the cell CI is
   the reason our reads pair seeds and fix the population — 500 games per cell reads a ±6pp
   change, the aggregate ±1.5; (b) the second external run on a different pool again lands
   the loop at parity with the heuristic from a BC well below it (40.6 → 50.6–51.1 over 20
   iterations) — the 09-07 mirror reached 55.2 by iter 25 on one deck, this one plateaus at
   parity across four; a four-deck population is the harder and more honest read; (c) his
   40,000-game heuristic matrix is a free calibration set for the format-as-features work
   (the deck-strength prior the value head has to learn is right there). Nothing on M12
   changes; the four `.dck` files are the natural second smoke pool for the quickstart.

### Draft replies (09-17; the user posts; nothing posted from here)

To Kryptic:

> This is a great read — the matrix is exactly the checkpoint × opponent × archetype shape
> Chris was describing last night, and 40,000 heuristic games as the reference is more than
> most papers manage. A few thoughts:
>
> 1. On "went down from 30 to 40": at 8,000 games each, 51.1 → 50.6 is −0.5 ± 1.5, so it's a
> plateau since ~iter 20, not a decline. And each cell is 500 games (±4.4pp), so a cell-to-cell
> change needs ~±6pp before it means anything — the mixed per-matchup picture between 30 and
> 40 is mostly noise. Your own round-112 lesson from the PPO days, applied to cells.
>
> 2. The plateau starts right where the guard curves take off (iters 20–35: veto rate ×5–10,
> rejected/traj ×7–10, entropy rising, kl_mu brushing your 0.15 guard). With `--guard-veto-mult
> 20` the veto guard never binds; the ×4 you used in the stompy run would have paused it near
> iter 20. I can't claim cause from here, but the cheap test is an 8,000-game arms read of the
> iter-20 ckpt next to 30 and 40: if it's the same 50.6, the last twenty iterations bought
> nothing and the guard setting is the first suspect.
>
> 3. The red mirror at 35–39% vs 50 is the one real structural deficit (Red vs Green −7.5 is
> the other). Burn is the deck imitation learned worst (your BC Red row was 15–18%!) and the
> loop recovered +20pp of it, but every burn spell is a face-vs-creature target decision plus
> Eidolon / Searing Blaze / Rift Bolt sequencing, and those are trained only from the
> heuristic's choices. If you want to locate it: face-vs-creature rate and burn-per-turn in the
> red-mirror traces vs the heuristic's — talor's "bad targeting" class.
>
> 4. The blue result is the interesting positive: the heuristic plays the deck at 15–27%, and
> as Blue the model gains +5 to +11 vs Green / White (counterspells and bounce are where a
> learned policy beats a script first). Note it also gains +3 to +7 *against* the heuristic's
> Blue — that's exploiting the heuristic's blue play, a different thing. So at least +5–11pp of
> mono-blue's deficit is play, not deck; the deck's ceiling isn't identifiable from this.
>
> 5. One thing from your monitor I'd look at: pay deviation (sampled) at ~0.9 by iter 30. That
> is the payment head directing nine of ten payments (all executing clean, good), but my reads
> on five served payment heads were each zero to slightly negative, and the headroom over auto
> payment is only ~3pp in ~3% of windows. On the M12 recipe the tag is withheld. An 8,000-game
> arm of iter-40 with the pay tag off (`final_read.py --server-tags` minus the pay tag) would
> price it. Also: which fork commit is your jar? If it predates 09-09 (`15863de0b4a`), the
> bridged payment probe drew RNG and wrote AI memory on every window and cost every network
> arm ~2.7pp on my pool — your BC directory is timestamped five hours after that fix, so this
> is a question, not a diagnosis.
>
> And the 40,000-game heuristic matrix by itself is useful to me — thanks for the .dck files;
> they'll be the second smoke pool in the quickstart.

To Shedletsky (the hang / anytime point):

> Your statistics point deserves restating: a hang cap is a card-correlated censor, so a fleet
> that drops hung games biases every per-card rate toward the cards that never hang. Two
> things from my side, for what they're worth: Anvil's search runs on a count budget (network
> forward calls) with the natural line always in the option set, so an answer exists at any
> cutoff and seeded replay still works — a wall-clock cutoff would break replay for every
> seeded consumer, which is why I'd argue for count-based budgets if the split-out lands. And
> for the residual hangs I run a loop guard in the fork (a bounded engine re-ask plus a
> repetition check) and count what it kills by seed and class, so the censored set is a named
> population rather than a silent drop. Happy to describe either if useful.
