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
| **Kryptic** | Independent replication of Austinio's pipeline | Same scripts; strong experimental hygiene instincts (CI-width callouts, leakage hunts, codex-driven code review) | Found the train/val game-leakage bug, the heuristic-fallback fake-win bug; built seeded twin-replay divergence tooling; PPO 200 rounds/220h → 24.5%→33.2% then flat. **09-07: ran Anvil itself** on a mono-green stompy mirror (Constructed, custom pool): BC 38.9% (n=2,000) → V-trace self-play 55.2% after 25 iterations (n=1,000, se ±1.6) — the first external replication of the loop ([devlog](../devlog/2026-09-07-session2.md)) |
| **talor** (`Talor-A/forge`) | Fork continuing Austinio's work | Added unit tests (found bugs), macOS MPS backend, diverse decks from cubecobra exports, cosine-similarity reward shaping for block/target heads; **Monte-Carlo rollout visualizer using GameCopier** | Active late May; `rltrain collect` = 5000 games/16 threads JSONL; ~0.5% game-failure rate (undiagnosed) |
| **LordOfThePigs** (`npiguet`) | Sealed **deck-builder** model, now **draft agent** (Tutor-adjacent, not gameplay) | Card transformer over card text + 544-dim embeddings pre-trained on per-card stats from 1M forge-vs-itself games; MLM pretraining helps; simulated-annealing deck search → distilled single-pass (3-4ms) | **Beats Forge SealedDeckBuilder 78% Bo7.** Draft agent: BC picker 85% match/top-3 99%; RL above BC failing (offline RL on fixed corpus dead; switching to online). 3-machine harness ≈ 200K games/day |
| **manabrew** (`witchesofthehill/manabrew` — khaliostr, fedepoi, Anacleto) | **Rust/wasm GPL port of Forge** + Tauri client, self-host multiplayer | **Lockstep parity harness**: serializes java Forge gamestate, drives it via JSONL/stdin-stdout, compares snapshots every turn+priority vs the Rust engine; **patched Forge for seeded determinism** ("seed controls library order and makes sure all decisions are the same") | Public since ~June; java Forge playable through manabrew; Rust ~50% faster/lighter but "still isn't completely correct"; offered the harness for AI control use |
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
