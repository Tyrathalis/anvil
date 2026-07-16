# Dive: austinio7116/forge `ai_investigation` — BC→RL pipeline archaeology

Clone: `<scratchpad>/austinio-forge`, HEAD `88105ef032` (2026-03-29). 147 commits since the first RL commit (`3cfa103af1`). All key docs at repo root: RLAI_PAPER.md (907 lines), RLAI_PLAN.md (723), RLAI_IMPROVEMENTS.md (210), ExIt.md (161), shaping.md (57). Java in `forge-ai-rl/src/main/java/forge/ai/rl/`, Python in `forge-ai-rl/src/main/python/`.

## Top takeaways for Anvil

1. **His entire PPO program failed, honestly documented, at scales below Anvil's D6 runs.** ~17,200 games over 43 rounds (best run) + a 9-round rerun + 13 league rounds, all plateaued 27–39% WR vs heuristic. Root-cause chain: value net useless before turn 7 → GAE advantages noisy exactly where deployment decisions live → stochastic sampling degrades collection play → 70% loss rate = "everything was wrong" gradients. He pivoted to Expert Iteration (rollout-labeled search targets) — structurally the same move as Anvil's D4 rollout-label machinery, arrived at from the opposite direction. Anvil's V-trace/one-step-off-policy design + Ante variance reduction + calibrated critic addresses each failure he hit; his record is corroboration that naive PPO at 10^4-game scale doesn't move.
2. **His headline "54% argmax parity" was a silent-fallback artifact** — the `-onnx` flag was ignored in eval mode, no server running → `super.chooseSpellAbilityToPlay()` → heuristic played vs heuristic (RLAI_PAPER.md §5.4.x correction commit `f950b0b633`; fix commit `560c40541a` "zero tolerance", verified 100 games / 5,182 decisions / 0 fallbacks). This is exactly Anvil's standing rule ("never read a bridge answer without checking `fallback` first" + arms runs keep census on) validated by someone who lost weeks to it.
3. **Aura targeting: `usesTargeting()` is TRUE for aura attach SAs in his code; the broken thing was `TargetRestrictions.getValidTgts()` strings.** His fix (commit `2134e47337`, 2026-03-22): `source.isAura()` → read the **Enchant keyword** (`hasKeyword("Enchant creature")` etc.) instead of the validTgts descriptor. Attach targets enumerate fine via `sa.getTargetRestrictions().getAllCandidates(sa, true)`; on-battlefield attachment host = `card.getEntityAttachedTo()`. Action item for Anvil: verify the CastPlan label extractor joins aura/Attach targets (they flow through normal `sa.getTargets()`, so probably fine) and that nothing downstream keys off validTgts strings.
4. **He hit the same three Forge landmines Anvil has ADRs for, plus one Anvil should re-check:** (a) AI first-fit early-exit — he patched `AiController` to evaluate ALL candidates (Anvil: ADR-0005 timing-legal scan, same conclusion, Anvil's is cheaper); (b) `LobbyPlayer.equals()` strict-class identity blocks subclassing — he patched forge-core to `instanceof` (Anvil went around via `IGameEntitiesFactory`); (c) GameCopier pre-game copy crashes — his `PhaseHandler.devModeSet` null-guard enables mulligan-time forking, **a fork-at-mulligan capability Anvil's forkcheck never exercised** (Anvil forks mid-game; Ante's re-deal re-anchoring might someday want pre-game forks). (d) **He never noticed GameCopier's fidelity bugs** — his MCTS rollout labels (March 2026, pre-PR-#11203) silently inherit the card-id renumbering / static-corruption classes Anvil measured at 50%/12%. His "MCTS should succeed" bet rests on copy fidelity he never tested.
5. **In-process ONNX serve works and is the cheapest "ship as a Forge AI" story:** `com.microsoft.onnxruntime:onnxruntime:1.20.0` (CPU EP), 9 ONNX files (~42 MB), encoder-once-then-head per decision, fully `synchronized` batch-1. No measured latency published (plan claims 1–5 ms/decision for the TCP path; Python server does 5 ms/32-item micro-batching, ~200 inf/s on GPU per ExIt.md). His GUI integration (LobbySlotType RL entry, PlayerPanel/VLobby wiring) is a ready template for Anvil's M-late "selectable AI" milestone.
6. **Model capacity scaling (§5.4.8) bought nothing measurable — it's where the project stalled.** Presets Small 23M / Medium 45M / Large 73M / XL 107M (1024-dim state, 256-dim zone embed, 4 layers); motivation = encoder reconstruction R² only 0.47/0.54 after joint training at 512-dim. XL retraining "in progress (2026-03-29)" is the last line; no XL result ever landed. The measured capacity analysis (RLAI_PLAN.md) actually argued *against* the bottleneck: effective compression ~3:1, 90% of embedding variance in 49 dims — "the bottleneck was training methodology (value-only), not capacity."

---

## 1. Negative results record

### PPO evolution (RLAI_PAPER.md §5.4, RLAI_IMPROVEMENTS.md, RLAI_PLAN.md "Bugs Fixed")

Hyperparameter timeline (each change documented with rationale):

| Param | v1 | v2 (2026-03-24) | v3 (2026-03-27) |
|---|---|---|---|
| GAE gamma | 0.999 → | 0.95 (match value-net gamma) | 0.99 (re-matched; 30-step discount 0.21→0.74) |
| GAE lambda | 0.98 → | 0.90 (horizon ~7 steps) | 0.95 (horizon ~20) |
| Entropy coeff | 0.005 | — (entropy decayed to 0.2–0.3, collapse) | 0.03 |
| Clip ε | 0.1 (deliberately conservative vs standard 0.2) | | |
| Games/round | 100 → 400 | | 800 |
| LR | heads 3e-5, value 1e-4, encoder frozen | | encoder unfrozen at 1/10 head LR |
| Value/entropy loss coeffs | 0.5 / (above) | | |

Runs and outcomes:
- **Run 1**: 20 rounds × 100 games — WR oscillated 19–34%, no trend. **Mulligan head catastrophically unstable at ~100 samples/round** (always-mulligan rounds at 1–3% WR) → excluded from PPO permanently.
- **Run 2 (main)**: 43 rounds × 400 = **17,200 games** vs heuristic. Plateau 30–39%, best 39% @ round 21. Weight L2 drift confirmed real policy movement (priority 5.2→14.9, value 11.4→33.0) — "moved weights consistently but improvements didn't translate to wins." Diagnosed cause: frozen encoder ceiling (value-only encoder retained 24% R² of basic game features; opponent-life R² = −0.02).
- **Run 3 (post joint-training + v3 hparams)**: 9 rounds × 400 on 2,000-game imitation base — best 36% @ round 2, back to 27% by round 9. Behavioral metrics improved (attack rate 55→70%, idle turns 27→20%) while WR didn't.
- **League/self-play (AlphaStar-lite)**: Elo-matched snapshot pool (cap 15, τ=200), pure self-play rounds 1–4, heuristic enters pool at 35% eval WR, per-player gRPC ports. 13 rounds: model beats old snapshots ~50% as designed but **eval vs heuristic stuck 20–26%**. Separately: 3+ rounds of plain self-play from the 39% model — infrastructure worked, judged "too weak for productive self-play, risk of degenerate strategies," reverted.
- **Two silent-killer GAE bugs** (RLAI_PLAN.md Bugs Fixed): (1) gamma mismatch (GAE 0.999 vs value trained at 0.95) made advantages ∝ V(t+1) — every decision in winning games positive, in losing games negative; value loss dropped 0.20→0.032 on fix (the value net was accurate all along, just miscalibrated against GAE). (2) `RewardShaper.initialized` never set → intermediate rewards were all 0 for the early runs.

### Reward design evolution
1. v0: flat terminal ±1 applied to *every* decision (bug, fixed).
2. v1: per-decision delta shaping recorded in Java (life ±0.01/pt, card ±0.05, board ±0.02/creature) + terminal; used in imitation-preprocessing discounted returns (γ=0.99).
3. **Investigated and intentionally disabled for PPO** (RLAI_PLAN.md): value net's per-step ΔV already is implicit shaping over the full 37K-float state; explicit deltas double-count and contradict correct plays (sac-for-cards = negative board delta). Kept only as an optional decaying coefficient (`--reward-shaping-coeff`, α·0.95^round, default 0.0; re-enabled at 1.0 for league runs as early bootstrap). shaping.md is the design note; he notes the deltas are approximately potential-based (Ng 1999) modulo the missing γ factor.
4. Value-delta-vs-terminal: value targets are discounted returns (shaping + terminal), NOT raw outcome — deliberately calibrated so early states ≈ 0. Value net accuracy by turn: mull 75%, T4 79%, T7 83%, T10 89%; win/loss separation <0.4 before turn 5 — "useful discrimination only around turn 7" (paper §5.4.6 table).

### AWR
**Built but never reported.** `training/awr_trainer.py` + `scripts/07_awr_train.sh` (argmax collection, GAE advantages, advantage-weighted CE, 4 epochs) exist (commit `b759a56daf`); RLAI_PLAN.md pitches it as "most promising alternative"; **no result, no log, no paper section — superseded by the ExIt pivot within days.** Evidence of absence: no AWR numbers anywhere in the repo.

### §5.4.8 capacity scaling
See takeaway 6. Trigger: block head 64.2%, attack 82.8% — hypothesis that 37,216→512 (72:1) compression destroys pairwise combat math. Presets landed in `4e32a786c9` (default XL, old checkpoints still load via saved config); §5.4.8 added in `5f7337fdc8`. Outcome: **none — "Retraining on 2,000 heuristic games with the XL model is in progress (2026-03-29)" is the final status.** Scaling bought nothing that was ever measured.

### Imitation numbers (for calibration vs Anvil's 0.97 honest agreement)
1,000 games → 127,156 records (104.5K priority / 9.6K attack / 5K target / 2.8K block / 2.6K mulligan / 2K binary / 650 card-select). Head val accuracy: priority 93.9% (vs 85% always-pass baseline), mulligan 98.5%, attack 81.6%, binary 81.0%, target 76.8%, card-select 76.3%, block 68.5%. True argmax WR vs heuristic: **29–31%** (not 54%). Class-imbalance finding: model amplified P1/P2 asymmetry 47/53 → 34/74 via exaggerated pass preference; fixed with inverse-frequency weighting on the priority CE. Games: 4 mono-color aggro decks; Delver Blue was unplayable by the heuristic (5–15% WR) and got replaced — "deck the teacher can't play = noise" is a data-hygiene lesson.

## 2. The aura/Attach targeting fix

- **Fix commit `2134e47337`** (2026-03-22, "Fix data quality issues"): `ActionEncoder.java` — inside the `sa.usesTargeting() && sa.getTargetRestrictions() != null` branch, aura special-case at **`features/ActionEncoder.java:108-117`**:
  ```java
  if (source != null && source.isAura()) {
      boolean enchantCreature = source.hasKeyword("Enchant creature")
              || source.hasKeyword("Enchant permanent");
      features[idx++] = enchantCreature ? 1f : 0f;
      features[idx++] = source.hasKeyword("Enchant player") ? 1f : 0f;
  } else {  // non-aura: string-match getValidTgts()
  ```
  So (evidenced): for aura spells `usesTargeting()` **does** return true in his code path; what was wrong is that `getTargetRestrictions().getValidTgts()` strings for the internal Attach spell don't contain "Creature"/"Player", so the "can target creature" flags were zero. Forge APIs used: **`Card.isAura()`**, **`Card.hasKeyword("Enchant <type>")`** (string keyword, not the `Keyword` enum).
- **Getting the actual attach target**: nothing special — aura targets ride the normal targeting machinery. Candidates: `sa.getTargetRestrictions().getAllCandidates(sa, true)` (PlayerControllerRL.java:193, MCTSDecisionMaker.java:129); chosen target: `sa.getTargets()` captured in `playChosenSpellAbility` → `recordSpellTargeting` (PlayerControllerRL.java:409-479, which re-adds chosen targets since `getAllCandidates` excludes them — a join detail Anvil's extractor should double-check).
- **On-battlefield attachment**: host encoding [202-207] uses **`card.getEntityAttachedTo() instanceof Card`** (`features/CardFeatures.java:499-509`) — power/toughness/isCreature/controller/CMC of the host (commit `a5c92860bb`, Fix 4). Target polarity [56-59] via validTgts `.YouCtrl`/`.OppCtrl`/`.YouDontCtrl` substring checks (ActionEncoder.java:141-154) — note this polarity block does NOT get the aura special-case, so aura polarity flags are still derived from the unreliable strings (evidenced gap he never closed).
- Anvil payoff: the CastPlan extractor reads `sa.getTargets()` at answer time, so aura Attach targets should already be captured — but worth a one-off validation that Duel Commander aura casts (e.g. Rancor-alikes) produce non-empty target refs in obs, and that nothing in the featurizer trusts `getValidTgts()` descriptor strings.

## 3. Decision surface (PlayerControllerRL)

Extends `PlayerControllerAi`. Twelve overrides covering 7 decision types (`PlayerControllerRL.java`):
`chooseSpellAbilityToPlay` (priority), `declareAttackers`, `declareBlockers`, `playChosenSpellAbility` (recording hook only), `chooseSingleEntityForEffect` (target), `chooseCardsForEffect` / `choosePermanentsToSacrifice` / `chooseCardsToDiscardFrom` (card-select), `arrangeForScry` (record-only, heuristic decides), `mulliganKeepHand`, `confirmAction`, `confirmTrigger`.

Everything else delegates to the heuristic — notably **NOT** intercepted: mana payment (auto via AI path), **X announcement / chooseNumber** (his model never chooses X — a gap vs Anvil's X head), **London mulligan bottoming** (the Python mulligan head has a bottom-card scorer, but no `PlayerController` override wires it — trained dead weight), attacker/blocker **ordering** (damage order), mode selection (`chooseModeForAbility` — modal spells go heuristic; his card features only flag `is_modal`), alt/optional costs (the candidate scan includes `getOriginalAndAltCostAbilities`, so alt-cost variants appear as separate priority candidates — same shape as Anvil's ADR-0005 Snuff Out fix).

Traps/notes for Anvil:
- **Candidate-set patch in `forge-ai/AiController.java`** (+96 lines): caches `lastPlayableSpellAbilities` = mechanically-legal set (`canCastTiming` + `ComputerUtilCost.canPayCost` + nonzero target candidates, mana abilities skipped) AND converts the heuristic's first-fit loop to evaluate-all (`lastEvaluatedSpellAbilities`, field so partial results survive the AI timeout). He explicitly classifies veto reasons: strategic (CantPlayAi, BadEtbEffects, CurseEffects — "safe to override if targets valid") vs mechanical (CantAfford, TargetingFailed, ...) — a ready-made taxonomy Anvil's veto-class decomposition could borrow. There's a unit test `CanPlayForRLTest.java`.
- **Targeting rejection = pass** (priorityTargetingRejected counter): if the model picks a spell whose targeting fails, he returns null (pass) — the same "silent forced pass" reward leak Anvil just fixed with re-ask-on-veto. He never built a re-ask.
- His attack override targets only `getWeakestOpponent()` (no planeswalker/multi-defender support); blockers built from `!isTapped() && !hasKeyword("CARDNAME can't block.")` with `CombatUtil.canBlock` checks at assignment — no `mustBlockAnAttacker` forced-block handling (Anvil's D5 found the engine never validates AI blocks; his games could contain silently rules-illegal blocks).
- `RecordingPlayerController extends PlayerController` + `PlayerControllerHuman` patch (+150 lines, `IGameRecorder` in forge-game) — **he records human GUI games as training data**, incl. human card selections. A capability Anvil's schema could support cheaply someday (Mentor).

## 4. MCTS status (final commits, Mar 28–29)

**Working, but it is a one-ply UCB1 bandit with flat rollouts-to-completion — not tree search.** `mcts/MCTSDecisionMaker.java` (823 lines):
- Priority: expand all (spell, target) pairs + PASS; ≥1 rollout each, then UCB1 (C=√2) over budget (default 30). Attack: {hold, all-in, each-single-creature} patterns only. Standalone target: UCB1 over legal targets. Mulligan: keep-vs-shuffle-redraw comparison, budget/3 (last commit `88105ef032`). Block/card-select/binary: heuristic, recorded.
- **Copy machinery**: spell rollouts go through `GameSimulator.simulateSpellAbility()` (+ `SimulationController`, `GameStateEvaluator.Score`) "which handles targeting, cost payment, stack resolution correctly"; attack-pattern and mulligan rollouts use **`GameCopier` directly** (`new GameCopier(game).makeCopy()`, `copier.find(player/card)`); rollout completion = `simGame.getPhaseHandler().mainGameLoop()` under a 60s (later 1800s game-level) timeout thread.
- Workarounds found: (1) `PhaseHandler.devModeSet` null-guard (forge-game patch, commit `3086970c80`) so GameCopier works pre-game; (2) `disableSimulation()` on all rollout AIs + `game.AI_TIMEOUT = 2` — nested simulation was a **300× slowdown**; (3) target injection: temporarily set target on the ORIGINAL SA, save/restore around `simulateSpellAbility` (GameSimulator copies targets from the source SA — same landmine class as Anvil's stale-target guard); (4) timeout-as-win bug — timed-out rollouts were counted as wins, fixed `45caf2d51a` (timeouts/draws = loss).
- **Determinism**: none. Every rollout does `MyRandom.setRandom(new Random(rng.nextLong()))` and restores — a swap of Forge's **global static RNG** while 4 game threads run in parallel (inferred race; he ran 4 threads per `SimulateRLTraining`). No seed capture, no twin checks, no fidelity gate. **No comment anywhere acknowledges GameCopier divergence/corruption** — he trusted the copier. Cost: ~5–15 min/game at budget 30 (vs 0.5 s heuristic), 20 games ≈ 1–3 h. Data collection + first ExIt training "in progress (2026-03-29)" — the project stalls before any ExIt result. ExIt.md cites MageZero (XMage, 300 sims/decision, 66% WR) as the existence proof.

## 5. ONNX serve path

- Dep: `com.microsoft.onnxruntime:onnxruntime:1.20.0` (forge-ai-rl/pom.xml:66-70), **CPU execution provider only**, `OptLevel.ALL_OPT`.
- `model/ONNXModelClient.java` (617 lines): 9 `OrtSession`s (encoder + value + 7 heads), model dir search chain incl. `~/.forge/res/rl/models`. `requestDecision` is `synchronized`, strictly batch-1: encode state → value → relevant head. Java side reimplements zone-tensor padding/masking to match Python `parse_game_state()` byte-for-byte; export via `tools/export_onnx.py`, checked-in models 43 MB (`.onnx` + `.onnx.data` external weights — commit `1513b5d96a` notes the .data files are required, a deployment gotcha).
- **No measured ONNX latency is published anywhere** (evidenced by absence). Claims on record: "real-time play in the Forge GUI without Python dependency" (paper abstract); TCP-server path "~1-5 ms latency per decision" (RLAI_PLAN.md:260, an estimate); Python server "~200 inferences/sec on GPU" with 5 ms / max-32 micro-batching (ExIt.md, model_server.py:41-122 — batching thread + queue, same lever as Anvil's `_Batcher`).
- GUI integration exists end-to-end: new `LobbySlotType` RL option, PlayerPanel/VLobby/FDeckChooser/GamePlayerUtil wiring, VField shows RL diagnostics. For Anvil's "selectable Forge AI" story this is a working reference implementation of the packaging, minus training quality.

## 6. Everything else Anvil should know

**Engine patches (complete list outside forge-ai-rl):**
1. `forge-ai/AiController.java` (+96): mechanically-legal candidate cache + evaluate-all loop + `canPlayForRL` facades.
2. `forge-ai/AiDecisionListener.java` (new, 48): decision event hook.
3. `forge-core/LobbyPlayer.java`: equals/hashCode strict-class → instanceof (subclass unblocking).
4. `forge-core/Localizer.java`: Java 21+ ResourceBundle fallback (headless compat).
5. `forge-game/PhaseHandler.java` (+4): devModeSet null-guard (pre-game GameCopier).
6. `forge-game/IGameRecorder.java` (new, 50) + `forge-gui/PlayerControllerHuman.java` (+150): human-game recording.
7. `forge-gui-desktop/SimulateRLTraining.java` (new, 951): headless parallel runner (16 threads, 1.3–1.6 games/s ≈ ~5,000 g/h — ~3–5× Anvil's obs-on rate, but with ~40× fewer features recorded per decision and no zstd full-state trajectory store).
8. GUI wiring (PlayerPanel, VLobby, VField, FDeckChooser, Main, GameLobby, HostedMatch, LobbySlot(Type), GamePlayerUtil, ForgePreferences).

**Engineering findings with Anvil relevance:**
- WSL2 gotcha: `localhost` resolves IPv6 `::1`, server binds IPv4 → default host changed to `127.0.0.1` (`560c40541a`).
- Encoder-training lesson (their biggest architectural finding): value-only pretraining then freeze destroyed decision-relevant information (R² 0.24); **joint multi-task round-robin training with encoder at 1/10 LR** recovered it (R² 0.47/0.54). Anvil trains jointly from the start — this is corroboration, not news, but the *encoder reconstruction R² probe* (train linear probes to reconstruct known state features from the embedding) is a diagnostic Anvil doesn't currently run and could adapt cheaply.
- Per-head encoders investigated and rejected (rare heads can't feed 3.5M params; critic/policy world-model divergence breaks advantage estimation).
- Priority class imbalance: heuristic passes ~85%; inverse-frequency weighting chosen over Anvil's post-hoc δ-calibration. Their diagnosis ("high accuracy but pass-heavy distribution collapses under sampling") is precisely the failure mode Anvil's pw=0.1 + δ recalibration was designed around.
- "Stop using head accuracy as the primary metric" (RLAI_PLAN.md, Evaluation) — mirrors Anvil's arms-as-instrument stance; his behavioral dashboards (attack rate, spells/turn, idle-turn %, per-head ablation WR) are a decent menu for D6 telemetry.
- Known-broken/undone at stall: aura polarity [56-59] still string-based; mulligan bottom scorer unwired; X/mode/order decisions heuristic; MCTS block/binary/card-select unsearched; AWR unevaluated; XL retrain unfinished; no fork-fidelity or determinism testing at all.

**Bottom line:** this is a competent, honestly-documented parallel effort that died exactly where Anvil invested first: no rollout contract (fork fidelity, determinism, seeded RNG), no variance accounting, no corpus-scale imitation (1–2K games vs Anvil's 113.6K), no calibrated critic before RL. The negative results de-risk nothing Anvil planned to do and confirm several things Anvil already decided not to do (naive PPO, entropy-bonus reliance, projecting BC winrate). The concrete new items: aura/Attach label verification, the veto-reason taxonomy, the encoder-reconstruction probe, human-game recording as a future schema consumer, and the fact that upstream now contains a second interested core developer (he's a Forge dev; PR #11203's reviewer goodwill has company).
