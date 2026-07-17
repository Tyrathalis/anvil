# Anvil — Consolidated Design v2

A neural agent for Magic: The Gathering built on the Forge rules engine: unified deckbuilding + piloting, a drill-driven data economy, luck-adjusted evaluation, coaching as a product surface, and mobile deployment as the upstream contribution. Non-commercial, GPL-aligned, designed to be contributed back to Forge.

**Module naming scheme** (Magic vocabulary under the smithy umbrella):
- **Anvil** — the project and the pilot agent
- **Tutor** — the deckbuilder (searches the pool for what the deck needs)
- **Mentor** — the coaching product
- **Grindstone** — the drill economy (grinds scenarios, sharpens the model)
- **Ante** — the luck ledger (accounts what chance took and gave)

**Initial scope:** 1v1 Duel Commander. *[Amended by ADR-0018 (2026-07-16): the ruleset is 1v1 Commander at 40 life — Forge ships no DC game type and all data to date is 40-life; Duel Commander is the pool's provenance. Content breadth (precons, then set-sized chunks; modes via bridge-tag coverage; 4-player classified as a feature) sequences after core features.]* The card pool is defined as the **union of current DC meta decklists plus common flex slots** (~1–2K cards) — a living object updated as the meta moves, via the same onboarding path as new sets — resolving the earlier tension between "curated pool" and "real meta priors." Expansion toward the full ~20–30K pool rides on text-embedding generalization. Multiplayer politics explicitly deferred; the pilot is 1v1, while Tutor and Mentor may serve multiplayer Commander.

---

## 1. Card Encoder (shared trunk for Anvil and Tutor)

Per-card representation fuses three sources through a 2-layer MLP into a ~256-dim card vector:

- **Frozen text embedding** of oracle text from a pretrained encoder. Precomputed, cached (~15MB fp16 full-pool). Carries tail generalization. Never ships at inference — only the fused output does.
- **Structured features:** mana pips, type-line one-hots, P/T, loyalty, keyword flags, **Scryfall Tagger functional tags** (multi-hot over frequency-cleared tags, via `otag:` queries) with an **LLM gap-filler** for under-tagged tail cards prompted with the existing taxonomy. Handles what embeddings are unreliable about (numbers).
- **Learned per-card ID embedding** (32–64d): escape hatch for operational quirks; head trains it, tail falls back on text.

**Dynamic features** ride alongside, never baked in: current Scryfall price (budget conditioning), refreshed at inference.

**New-card/pool onboarding:** embeddings + tags computable at spoiler time; ID embedding initialized at the **centroid of text-embedding neighbors**. Error accounting flags new cards as high-uncertainty and schedules Grindstone work. Meta-driven pool updates use the identical path.

**Encoder-swap escape hatch:** card vector defined as fusion output; when the text encoder ages out, distill the new fusion stack to reproduce old vectors, then continue training.

**Cross-game hygiene:** the text tower is game-agnostic; keep Magic-specific assumptions (zone lists, feature names) out of the Python-side schema. Costs a naming convention now, preserves multi-game optionality forever. Format-as-features (§2) is the pilot study for multi-game conditioning.

## 2. State Representation

**Entity tokens into a vanilla transformer** (8–12 layers, d=512, 8 heads; ~30–80M trainable params total). Each game object is one token: card vector + dynamic features (zone, controller, tapped, counters, damage, sickness, combat assignments).

- **Multiset deduplication:** identical entities → one token + count feature, mirroring engine-side canonicalization. Action heads point at equivalence classes.
- **Derived characteristics, not provenance** (post-layer-system current state); non-reducible residue as child tokens with parent-link features.
- **Own decklist as state:** remaining library as deduplicated card tokens with remaining counts. Known-position library cards promoted to entities with position features.
- **Global tokens:** per-player vitals, turn/phase/priority, unattached continuous effects, commander-zone state and tax.
- **Loop-detector feature (new):** engine-side repetition detection output as input — cycle running, controller, iteration count, available interrupts. Detection is the engine's job; response is the model's.
- **Action-history window:** ~30–60 recent actions, for tempo-reading; less load-bearing given explicit decklist state.
- **Format as features:** starting life, deck size, singleton flag, command zone, mulligan variant explicit (banlist implicit via masks/populations) + small learned format embedding for residue.
- **Conditioning tokens:** skill token, deck-goal token, opponent-information regime flag, drill-regime task token, **turn-plan latent** (§3a).

Realistic boards 50–150 tokens post-dedup, worst ~300.

## 3. Policy Head

Autoregressive pointer decoder (~5–10M params): action type → source pointer → target pointers → modes / X / payment, each step **hard-masked by engine legality**. Combat as (blocker-class, attacker) sequences with done-token. Mulligans (own drill category and eval), concession (§3c), play/draw.

### 3a. Planning (three tiers)
- **Implicit:** the trunk computes over the whole board; multi-step lines are learnable but grind-heavy and fail silently on long lines (tap/untap engines are the stress case: locally-negative actions cashing out 3–4 steps later).
- **Turn-plan latent (in base architecture):** at turn start and on regaining priority, the network emits a plan embedding conditioning all within-turn decoding — a scratchpad for intent. Near-zero cost, end-to-end trained.
- **Pivotal-turn engine search (explicit):** own-turn sequencing is deterministic (no chance nodes except opponent priority responses) — the best case for search. Policy proposes k candidate lines; forking machinery rolls each out; critic scores end states with opponent responses priced by the belief head; best line executes *advisorily* (re-plan on opponent response, no tunneling). Triggered on critic-identified pivotal turns and payment-consequential turns. **Expert-iteration distillation** feeds search-improved lines back as policy targets, so the search-free path (which mobile requires) internalizes the lines over time.

### 3b. Priority & timing — learnable stops (audit fix)
Naive auto-yield either barely fires (pass-only-when-nothing-legal) or bakes heuristic judgment into exactly the held-instant decisions that matter. Resolution: **stop-setting is part of the action space** — MTGO-style macro-actions ("yield until end of turn," "stop at opponent combat"). The agent learns its own attention schedule; preserves most episode shrinkage; when-to-hold-priority becomes a first-class skill; yield behavior stops leaking information in deployment. Throughput napkin math haircut accordingly.

### 3c. Mana payment (audit fix)
Engine auto-payment as the default action; policy override via a payment-choice sub-head **only when the engine flags the choice as consequential** (multiple payment classes with different residuals — colors held, snow, ability-relevant permanents). Interchangeable payments collapse into classes; decide over classes. Which-lands-to-tap is downstream of which line you're on, so plan-then-execute (§3a) answers most cases.

### 3d. Concession & degenerate endings
- Engine-side: repetition detection via the canonicalization hash (recurring canonical state, no progress delta); CR-compliant loop handling (mandatory loops draw, optional loops shortcut with declared iteration counts) enforced as caps and shortcuts, never simulated at length. Turn/decision caps with **cap-aware reward design** — draws must not be exploitable by a stalling leader.
- Model-side: concede as an ordinary decision over the loop-detector feature. Scores exactly as a loss (no discount); small per-decision time cost makes conceding hopeless positions weakly preferred — a real compute rebate at self-play scale. **Gated behind a confidence threshold, disabled in early training** (self-sealing-error risk: a miscalibrated critic conceding winnable positions never generates corrective data), and audited by rolling out sampled conceded positions and measuring regret. Game-1 information-denial concession is a separate, retained decision.

## 4. Value, Belief, and Auxiliary Heads

- **Asymmetric critic:** sees both hands/decklists in training; policy never does.
- **Belief head:** posterior over opponent hand and decklist, initialized from the meta prior (population embedding), updated by evidence; **match-persistent** across sideboarding. Supervised free in self-play. Uncertainty doubles as Mentor's per-advice confidence. Caveat: the posterior inherits the self-play population prior — deployment against off-population decks degrades it; population breadth is the mitigation.
- **Win probability** as sole reward-bearing target; auxiliary *predictions* only (life diff, card advantage, material, opponent hand, turns-to-end).
- **Drill regime:** short-horizon rollout deltas as value targets, task-token flagged; drills capped as a fraction of value batches.

## 5. Tutor (deckbuilder head)

Set-transformer over the candidate pool (shared encoder), conditioned on deck-so-far, autoregressive picks to legality.

**Signals:** sparse game outcomes + dense pilot-derived per-card realized advantage from the critic + predicting the pilot's card-quality assessments.

**Goal conditioning (hindsight relabeling):**
- **Theme:** target tag histogram / theme embedding.
- **Budget:** soft scalar + **hard price masking** during picks. Native, not iterative-removal — budget decks are different decks (correlated blocks like manabases), not degraded expensive ones.
- **Power:** target-winrate scalar + opponent-population embedding (opponent lists through the encoder, pooled). Anchors: precons; brackets as UI labels over measured winrate. Critic-proxy scores; real rollouts audit. Playgroup-conditioning ("50% against these four decks") is direct.

**Sideboarding** = same head as a 15-card constrained edit conditioned on belief-head archetype, game-1 trajectory, play/draw.

**Metagame outer loop:** PSRO/double-oracle, deferred; sealed/pool-constrained first.

**Separate tool:** budget swap-search via critic-proxy Pareto frontier (dollars saved vs. winrate lost).

## 6. Training Pipeline

**Phase 1 — Offline:** ~500K heuristic self-play games (personality/pool randomized), BC + value learning. Metric: held-out action agreement (target high-80s%).

**Phase 2 — Online:** V-trace/IMPALA actor-critic (AWR for the most off-policy mixtures); hand-rolled (~2K lines). Not PPO (chronically off-policy data), not MuZero (real simulator available; learned models smooth rare adversarial branches).

**Grindstone (drill sidecar):**
1. **Error accounting** flags (card, context) cells: held-out value error, policy disagreement, appearance starvation.
2. **Mining** heuristic (later pro) games for pivotal instances — select by ε-pivotality (decision flips rollout outcome), brevity as tiebreaker only.
3. **LLM as filter** (verification, not generation) + semantic ablation ordering.
4. **ddmin against engine rollouts:** certified-extraneous state → wildcards; domain randomization with pivotal structure preserved.
5. **Position-initialized drills:** 2-sec scenario rollouts vs. 30-sec games — the biggest throughput lever.
6. Fallback for unminable cards: hand-constructed seeds, same ddmin certification.

**Calibration anchoring:** ground-truth rollout trickle on trained positions; widening predicted-vs-rolled-out gaps re-queue regions.

**Phase 3 — Offline consolidation** (expert-iteration/reincarnation family) once the critic clears a calibration bar; anchoring trickle mandatory (no grading its own homework).

**Expert-iteration regeneration:** advise heuristic games at high-disagreement nodes, fork, roll out, engine adjudicates → contrastive blunder pairs, falsified disagreements (→ error queue), trajectory diversification. Never train on unverified model-advised trajectories.

**Search distillation:** pivotal-turn search lines (§3a) as policy targets — the same expert-iteration channel.

**Pro-game corpus:** advantage-weighted imitation (upweight critic-endorsed moves); confident model-pro disagreements → error queue or drill miner.

**Skill conditioning:** trajectories labeled with generating-checkpoint Elo; skill token; continuous difficulty slider calibrated against the frozen ladder. Maia lesson: weak human play is a different distribution, not strong play + noise — temperature titration feels "rigged." Human-shaped levels via fine-tuning on rating-binned human games once the recording flywheel (§11) delivers. Skill-conditioned model doubles as Mentor's blunder model ("level-typical mistake" vs. "missed something subtle for your level").

**Continual learning:** replay mixing (reservoir samples every batch); shrink-and-perturb soft resets / head reinits at set boundaries (plasticity); frozen anchor eval suite (pro-agreement, ladder Elo, per-mechanic drill accuracy) to catch silent regression; bans = population removal.

**Adversarial auditing:** periodic exploiter trained against the frozen policy **at max skill setting**; extractable winrate measures the belief-head-instead-of-CFR bet.

**Reward-hacking hygiene:** anomaly monitor — winrate wildly exceeding critic prediction = bug report until proven otherwise; ddmin repurposed for minimal bug reproductions → high-quality upstream reports.

## 7. Ante (evaluation & luck ledger)

**AIVAT-style control variates:** at each chance node, correction = value(actual) − E[value over the known distribution] via the omniscient critic. Zero-mean by construction → **unbiased regardless of critic quality**; critic quality sets only variance removed. Boundary rule: choices are decision nodes, resolutions are chance nodes; expectations over the distribution as it stood after prior decisions (fetch-shuffles reset it).

**Tiered deployment (audit fix):** the exact ledger costs 60–90 critic evals per draw step in singleton — fine for evaluation, ruinous for every training game.
- **Exact ledger:** evaluation games, deck-vs-population measurement (3–4x+ effective samples), Mentor decompositions, periodic audits.
- **Amortized approximation for training advantages:** a small head predicting the expectation in one pass, periodically audited against exact computation; baselines need only correlation to reduce variance.

**Certification test:** identical-deck mirror batch — ledger sums to zero in expectation; corrected winrate converges to 50% faster than raw. An afternoon that certifies the apparatus.

**Other eval:** checkpoint Elo ladder (standing job); **pro-game move agreement** ranked by decision difficulty (the headline "is it actually good" metric); exploiter winrate; anomaly monitor; mull/keep accuracy vs. rollouts; **human playtesting on desktop Forge well before the mobile milestone** — the difficulty slider's deliverable is feel, and only humans measure it. Calibrated-difficulty results double as self-rating (§11).

## 8. Data Sources

1. **Heuristic self-play** (primary offline corpus).
2. **Tournament decklists** (published, structured): meta priors + populations — ~80% of "current meta" value for ~2% of the work. DC meta primarily from league results (French/European scene; thin video pipeline).
3. **Video reconstruction** for premier paper events: beam search over reconstructions — known 75s + engine legality enumeration make it a discrimination problem; vision model provides evidence, engine prunes; human review on beam collapse. Scope to premier coverage.
4. **Structured digital logs** (MTGO replays, consenting Arena logs): order of magnitude cheaper per game.
5. **Recording flywheel** (§11): consenting Forge players → rating-binned human games.

Pro games punch above volume: eval benchmark, Grindstone seeds from the true competitive distribution, advantage-weighted fine-tune.

## 9. Engine & Infrastructure

**Forge as ground truth.** Largest scripted pool, native Commander support, maintainers explicitly interested in ML bots. XMage: rules engine entangled with client-server plumbing (though MageZero demonstrates harnessing is possible). Magarena: clean but small pool, slowed development. Cockatrice: no rules enforcement — non-starter.

**Fork discipline:** pinned versions per run; engine hash on every trajectory; upgrades are dataset boundary events (replay old decision points, diff legality/resolutions, evict touched trajectories). Small, tested, human-reviewed upstream PRs. **Model never sees engine version** — formats are rules to play to; versions are bugs not to learn.

**Canonicalization patch** (first surgical contribution): characteristics-hash → equivalence classes → class-level combat search (counts, not entities). Fixes the N-identical-tokens blowup; same function feeds neural dedup **and** repetition detection (§3d) — one function, three jobs. Differential-testable; never touches rules code.

**Bridge:** inference-server pattern. 20–40 long-lived JVM workers stream observations via gRPC/protobuf to one Python server batching decisions per GPU pass (low single-digit ms at batch 256 / 80M params). Featurization Java-side; embedding lookup Python-side. Instrument batch formation (actor and GPU starvation share a timeout-tuning fix).

**Disposable workers; pause/resume where convenient (2026-07-03).** Workers already need periodic recycling (RSS drift), so the harness treats them as disposable: graceful stop (SIGTERM/stop-file → finish current game, write progress, exit) and seeded game-granularity resume (games are independent and ~seconds long — resume = relaunch for the remainder at the right seed offset) are first-class. Long-running jobs launch at low OS priority (`nice -n 19`) so the desktop preempts them without pausing; calibrated measurements (scaling curves) are the exception — schedule those, don't share them. Training side is pause-friendly by construction: PyTorch checkpoints + V-trace's tolerance of dying actors.

**Training stack:** PyTorch, bf16, single 4090, hand-rolled V-trace + replay. **Provenance-tagged trajectory store** (source, engine hash, checkpoint, drill-template ID), memory-mapped NVMe, hundreds of GB — powers reservoir sampling, error queries, bisection, skill labels. wandb/MLflow + ladder job. Seed everything; deterministic replay.

**State forking with seed control** (load-bearing for four systems now: Mentor counterfactuals, ddmin oracle, position drills, pivotal-turn search): same-seed pairs when the branch doesn't perturb the library; expectation-over-reshuffles when it does.

**Throughput is the binding constraint — CPU games/hour.** Priority order: canonicalization patch, allocation profiling, learnable-stop macroization, serialization trimming, Grindstone position economy. GPU sophistication deferred until demonstrably saturated.

**Phase-two bet (conditional):** LLM-assisted Rust subset engine for the pool (~15–20% of comprehensive rules), differentially tested against Forge on millions of random games — the asymmetry ygo-agent didn't face (ygopro-core already existed as fast embeddable C++; Magic has no equivalent). Full-port rejected: verification is the actual work; rules bugs are silent training poison. Greenlight only after throughput is measured as binding.

## 10. Match Play (Bo3)

**Match is the episode:** match-level credit, belief persistence across sideboarding, sideboards in populations, play/draw, strategic concession. Game 1 partly information-gathering — emergent from match-level credit. Duel Commander is friendly: the commander is public pre-game, collapsing the archetype posterior (offsetting singleton opacity).

**Opponent-information regimes** (per-game flag, one network): fully visible / archetype-prior / fully hidden. Critic always sees truth. Never train visible-only and deploy hidden.

## 11. Products, Deployment & Community

**Mentor (coaching):** blunder detection (win-prob delta as centipawn-loss); Ante luck decomposition per game ("80% mana screw, 20% the turn-five attack" — mechanized tilt-attribution correction); counterfactual lines via seeded forking; **evidence-grounded explanation** — system compiles structured facts, LLM narrates *only* the evidence packet (sportscaster over telemetry, never analyst), cheap claim-checker re-validates prose; confidence flags from belief uncertainty + population spread, with humility in bluff-heavy spots while training is heuristic-descendant-heavy.

**Deckbuilding coaching (added 2026-07-03, lower priority):** Mentor's surface extends to deck advice, backed entirely by Tutor's evaluation machinery — playgroup-conditioned list scoring, critic-proxy slot attribution audited by real rollouts, Ante-corrected deck-vs-population winrate (3–4× effective samples), budget swap-search Pareto frontier — narrated through the same evidence-packet pipeline as move coaching. Deck-level claims are *more* rollout-verifiable than move-level ones ("this swap gained 3% against your pod" is directly measurable). No new ML: a product framing over Tutor + Ante + the explanation pipeline; sequenced after gameplay coaching works.

**Android embedding in Forge:** search-free inference + card-vector lookup table (text encoder never ships) = mobile-native by design. ONNX Runtime Mobile / LiteRT via Java bindings; fork's featurization relinks directly (network call → local session). Int8 ~80MB optional downloadable asset; critic head fp16 if win-prob display drifts. Tens-to-low-hundreds of ms/decision vs. the heuristic AI's multi-minute token boards. Watch: old-device memory, belief-state serialization across app lifecycle. **Continuous difficulty slider** via skill token. Friendly issue thread with maintainers before building.

**Game recording (separate from the bot, strictly opt-in):**
- v1: local recording + **export-a-file** button — players own and can access their data (many will want it anyway); no automatic submission, no collection infrastructure required.
- v2: one-time manual upload per submission.
- Transparent contents: actions + decklists, no PII (decklists are personal the way chess repertoires are — say so).
- Trajectory schema from the provenance store doubles as the interchange format.
- **Self-rating bonus:** results against calibrated difficulty levels estimate the player's own rating — submitted games arrive pre-binned by skill, exactly the labeled corpus the Maia-style fine-tune wants. Sandbagging partially detectable via Ante decision-quality signatures.

**Legal (non-commercial framing):** WotC Fan Content Policy is designed for exactly this; Scryfall terms are friendly to non-commercial use; GPL becomes the natural license of the contribution itself rather than a constraint. Revisit only if commercial ambitions ever emerge.

**Deployment surfaces:** Forge (desktop + Android), Mentor, Tutor. Arena/MTGO ladder play is ToS-walled — don't build toward a demo that can't ship.

## 12. Related Work & Positioning

- **MageZero** (XMage, AlphaZero-style): decomposes MTG into deck-specific subgames — per-deck specialist agents, matchup-local target spaces — explicitly to avoid LLM-scale resources; alpha released with precompiled XMage + training CLI. The instructive contrast: their bet is decomposition-now, ours is generalist-encoder for generalization, onboarding, and Tutor (structurally unreachable per-deck). Useful as baseline, community, and collaborator. **Cross-engine bridge** for benchmarking (same decklists, different engines) is *also* a differential-testing harness — desyncs are Forge-or-XMage bug reports.
- **LearnForge:** old abandoned RL-on-Forge attempt; an hour of archaeology for what killed it.
- **Academic Gymnasium MTG benchmark (2026):** Standard decks, flat 3,077-dim observation vector, 478 masked actions, 2–15 typically legal, 10–20 decisions/turn. The flat-vector choice is exactly what entity tokens reject — fixed vectors can't grow with boards or pools.
- **Generalised card representations for MTG (2024):** argues end-to-end RL of draft+play impractical for unrestricted pools; models human decisions generally instead. Validates the difficulty assessment (hence curated pool) and the representation bet, while Anvil uses the engine to escape the human-imitation ceiling.
- **ygo-agent (Yu-Gi-Oh):** the strongest analog — ygoenv (envpool + ygopro-core C++), JAX/LSTM agents, superhuman ambitions, shipped human-AI battles in standard YGOPro clients. Existence proof that solo-scale teams reach strong play in a comparably complex TCG. **Required reading before M0**: entity encoding, action decomposition, client integration all map. Their luck: a fast embeddable engine already existed — the gap our phase-two Rust bet closes.
- Context: Hearthstone ecosystem (SabberStone, AI competitions), draft-bot literature + 17lands (deckbuilding-from-human-data flank), Cowling–Ward–Powley ensemble-determinization MCTS (pre-deep ancestor), EDHREC (collaborative filtering: knows what people play together, not what wins).

**Cross-game generality:** the *pattern* transfers wholesale (entity tokens, pointer decoding, Grindstone, Ante, skill conditioning; the text tower is game-agnostic); *weights* are a research question (shared trunk with game-token conditioning: maybe). Shared codebase with per-game weights is nearly free once the bridge exists; ygoenv is the cheapest second game. Design nothing extra now; keep the schema game-agnostic (§1).

## 13. Sequencing

- **M0 — Harness:** batch harness + bridge + random-legal agent. Exists to measure games/sec; **the number calibrates every schedule after it** (2 min/game instead of 20 sec → everything stretches 5x, Rust bet moves to phase one). Survey ygo-agent and MageZero first. **Done 2026-07-04 ([ADR-0003](../decisions/ADR-0003-m0-closeout.md)): ~1,700 g/h bridged / 3,016 g/h heuristic at w=16, bridge tax 2.6% — no stretch, Rust bet stays phase-two.**
- **M1 — BC:** encoder + trunk + policy head, pure supervised. Validates representations with zero RL machinery.
- **M2 — RL:** critic + Ante certification test + first V-trace self-play from BC start.
- **Then, attaching to a running loop:** Grindstone + error accounting → match play & sideboarding → Tutor → Mentor → pro-data pipeline → skill conditioning → pivotal-turn search + distillation → Android + recording. Build vertically to a trained artifact at each stage.

## 14. Budget to "Beats the Heuristic AI"

~20–30K lines (60/40 Python/Java; the Java is archaeology-heavy); ~500K BC games (2–4K core-days) + 1–3M self-play games; ~200–500 4090-hours total; the existing 4090 + a 32-core box (~$1–2K used or $3–6K cloud); 4–8 months solo at nights-and-weekends with heavy LLM assistance. Risk concentrated almost entirely in the M0 games/hour number — measure first. **Measured ([ADR-0003](../decisions/ADR-0003-m0-closeout.md)): throughput risk retired — 64 games/min heuristic / 29 games/min bridged at w=16 on the existing box, no 32-core purchase; the ~500K-game BC corpus ≈ 6 days wall-clock. Remaining calendar risk shifts to representation quality (M1) and RL machinery (M2).**

## 15. Standing Probability Estimates (selected)

| Claim | P |
|---|---|
| Pilot clearly beats Forge heuristic, curated pool, this budget | ~80% |
| BC reaches high-80s action agreement (M1) | 80% |
| Post-optimization Forge: 10+ games/min on 32 cores | **resolved true, 6× margin pre-optimization ([ADR-0002](../decisions/ADR-0002-fork-api-gate-resolution.md)/[0003](../decisions/ADR-0003-m0-closeout.md)): 64 g/min heuristic, 29 g/min bridged, 16 cores** |
| Own-decklist state pays for itself in sample efficiency | 90% |
| Zero-shot generalization to unseen cards via text embeddings | ~50% (the open research question) |
| Belief head + asymmetric critic suffice sans CFR (exploiter test) | 70% |
| Exploiter finds >65% vs. frozen v1 | 60% (base rate; the finding is the point) |
| Agent finds ≥1 exploitable Forge rules bug in first serious run | 80% (budget upstream reports) |
| Match-persistent belief beats reset baseline on games 2–3 | 80% |
| Format-as-features: two formats near specialist parity, one net | 65% |
| Continual training across 4 sets without late-caught regression | 60% with replay+resets; ~25% without |
| Ante: ≥3x effective samples for deck evaluation | 75% |
| Ante bookkeeping bug-free first attempt | 55% → hence the certification test |
| Tiered ledger keeps training GPU non-bottleneck | 85% |
| Learnable stops preserve most auto-yield gain + fix instant-speed learning | 80% |
| Turn-plan latent alone handles 3–4 action tap/untap lines post-drilling | 65% |
| — with pivotal-turn search layered on | 90% |
| Search distillation recovers most search gain into the mobile path | 70% |
| Repetition detection + gated concession cuts self-play wall-clock >15% | 75% |
| Skill-token levels rank correctly, feel coherent | 80%; human-*like* 50% pre-human-data, 75%+ after |
| Budget-conditioned Tutor beats iterative removal at matched budget | 80% |
| Quantized model <500ms/decision on mid-range 2024+ Android | 90% |
| Int8 costs <~2% head-to-head winrate | 80% |
| Export-and-submit yields a usable human corpus within a year of bundling | 60% (adoption-dominated) |
| Self-rating bins accurate enough for the Maia-style fine-tune | 70% |
| MageZero per-deck specialist beats Anvil on a fixed single matchup | 60% — while losing on generalization/Tutor/onboarding: 85% |
| LLM-assisted **full** Forge port reaches training-grade correctness | <15% (rejected) |
| Rust **subset** engine, differentially tested | 55–65% (phase-two bet) |
| 4–8 month solo calendar holds | 55% (fat right tail; competes with Dry Run et al.) |

---

**Design invariants:** the engine adjudicates every claim any learned component makes; every LLM judgment is downstream-verified; every drill is provenance-traced to a real game; the value function is continuously audited against rollouts; detection is the engine's job and response is the model's; the error-accounting queue is the spine everything reports to. Recurring economy: the expensive infrastructure (goal conditioning, provenance store, forking, the ladder, the canonicalization hash) keeps making each new feature nearly free — one function, three jobs.
