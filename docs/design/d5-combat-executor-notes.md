# D5 combat executor — fork archaeology notes (2026-07-13, session 2)

Read-through of the declare-combat paths in the fork ahead of the executor
implementation (realizers + CONSTRUCT wire path). Companion to the D5 design
settled 2026-07-13 (factorized heads; serve = legal-candidate materialization
+ fixed-point per-assignment drop + forced-add logging, no heuristic
fallback). File references are to the fork at `../forge`.

## Engine flow — attackers

`PhaseHandler.declareAttackersTurnBasedAction()` (PhaseHandler.java:536):

- **The engine re-asks on invalid declarations**: `do { controller.declareAttackers(...) }
  while (!CombatUtil.validateAttackers(combat))`, with a `notifyOfValue`
  nudge between rounds. The proto's `retry_of` field was designed for this.
  A deterministically-invalid realizer answer = infinite loop → the realizer
  must self-validate before returning (see design below).
- **Attack taxes (Propaganda) are paid post-declaration**: the engine taps
  attackers provisionally, runs `checkPropagandaEffects` per attacker
  (payment goes through the controller's mana methods = heuristic fallback
  at D5), and removes attackers whose costs aren't paid, re-validating after
  each removal. The AI *pre-drops* unpayable attackers
  (`AiController.removeUnpayableAttackers`, **private** — widen to
  `protected` in the fork, one line) to avoid pay-then-cancel churn.
- Exert/enlist are separate callbacks after declaration (measured ≈0 in
  corpus, out of D5 scope — heuristic keeps answering them).
- Vigilance/tap mechanics are engine-side; the realizer never taps.

**Requirements machinery is reusable**: `CombatUtil.validateAttackers`
compares the declaration's violation count (`AttackConstraints.countViolations`)
against the best achievable legal attack
(`combat.getAttackConstraints().getLegalAttackers()` → `(Map<Card,GameEntity>, violations)`).
"Must attack" is therefore checkable AND satisfiable without us re-implementing
any of it. The AI's own invalid-fallback (AiController.java:1306) is
`clearAttackers()` + re-add the `getLegalAttackers()` map — our guaranteed-
termination fallback.

## Engine flow — blockers

`PhaseHandler.declareBlockersTurnBasedAction()` (PhaseHandler.java:658):

- Asked per defending player, only when `combat.isPlayerAttacked(p) &&
  CombatUtil.canBlock(p, combat)` (1v1: one call per combat).
- After the controller returns, the engine itself runs a **per-assignment
  drop pass**: unpaid block costs remove that assignment; then a
  fixed-point loop drops "can't block alone"-class keyword violations.
  So per-assignment legality gating + the engine's own post-pass compose.
- **NOBODY validates must-block on the controller path.**
  `CombatUtil.validateBlocks(combat, defending)` (returns a String error or
  null) is called ONLY by the human input path (`InputBlock.java:102`). The
  AI satisfies lure/must-block proactively inside `AiBlockController`. If
  our realizer ignores requirements, games proceed **silently rules-illegal**
  — worse than a veto. The realizer must forced-add.
  `CombatUtil.mustBlockAnAttacker(blocker, combat, freeBlockers)` (public
  static) is the structured per-creature check; `validateBlocks` is the
  final gate.

## Candidate bases line up with training

- Obs `sick` is haste-aware (`Card.isSick()` = sickness && !HASTE &&
  creature; ObsSnapshot.java:256), and `tap` is direct — the loader's
  derived basis (untapped/unsick battlefield creatures) is exactly
  reconstructible serve-side from the same obs the wire ships, and is a
  superset of engine-legal (Pacifism/defender stay candidates with learned
  0-labels; engine legality gates at realization — ADR-0005 semantics).
- The engine asks only when a possible attacker/block exists, so bridged
  windows always have candidates; if the server still derives none, it
  answers the empty map without a GPU pass (mirrors the loader's
  forced-empty skip).

## Wire design (recommendation)

**Answer in observation-namespace entity refs, not option indices.** The
proto's v0 `AttackMap`/`BlockMap` (index-into-enumerated-options form) was
never implemented on either side — safe to reshape. Precedent: the M1
CastPlan rung-1 amendment ("the server answers with observation-namespace
refs...; the worker realizes refs against the engine and adjudicates
legality"). This removes any need to ship engine enumerations in the
request, avoids index-space determinism questions, and matches how the
model actually works (rows over obs entities).

- Proto: `AttackMap.Assignment` → `{EntityRef attacker, EntityRef defender}`;
  `BlockMap.Assignment` → `{EntityRef blocker, EntityRef attacker}`.
  (`EntityRef` already carries entity-id / registered-player-index.)
- Tags: `mtg.attack` / `mtg.block` join the bridged-tag set.
- Request: the dec record, exactly as priority does it — `Obs.dec(...)` (the
  generic combat dec CensusPlayerController already logs) +
  `Obs.lastDecForBridge(game)` as the observation bytes. No options payload.
- Java: `AttackMapAnswer`/`BlockMapAnswer` transport-agnostic structs in
  `forge.ai.anvil` mirroring `CastPlanAnswer.Ref`; `AnvilBridge` gains
  default-null methods (local-random/echo arms unchanged); `GrpcBridge`
  translates proto ↔ struct.
- Server: featurizer derives `cmb_rows` with the loader's `_eligible_rows`
  (same code, no fork); `act()`'s `atk_yes`/`cmb_count`/`atk_tgt`/`blk_pick`
  translate per row — dedup rows expand to k first-fit member entity ids
  (aux needs row → member-ids, the existing `row_min_id` generalized);
  `atk_tgt` player-position maps back to registered index via perspective;
  `blk_pick` attacker-slot maps to a first-fit member of that attacker row
  (two blockers pointing at one dedup row of attackers stack on its
  first-fit member — multiset-tie semantics, same as the labels).

## Realizer design (worker side)

**Attack** (`mtg.attack` bridged):
1. Resolve each assignment; gate with `CombatUtil.canAttack(card, defender)`
   and defender ∈ `combat.getDefenders()`; `combat.addAttacker` or
   drop + census (`dropped`, reason).
2. Pre-drop unpayable taxes (`removeUnpayableAttackers`, widened).
3. Self-validate: if `validateAttackers` false → tier 1: union-merge the
   missing entries of `getLegalAttackers()` into the model's map (census
   `forced` count) → still false → tier 2: wholesale `getLegalAttackers()`
   (census `fallback_best`). Returns only valid declarations, so the
   engine's re-ask loop terminates by construction; if a re-ask fires
   anyway (`retry_of`), answer tier 2 immediately.

**Block** (`mtg.block` bridged):
1. Per assignment: gate with `CombatUtil.canBlock(attacker, blocker,
   combat)`; `combat.addBlocker` or drop + census.
2. Forced-add loop (bounded by defender creature count): while some
   creature has `mustBlockAnAttacker(...)` → add a block to the model's
   chosen attacker if legal, else the first legal attacker (census
   `forced`).
3. Final `validateBlocks` check; if still non-null → clear +
   `AiBlockController.assignBlockersForCombat` (census `forced_fallback`;
   expected ≈never in-pool — the census will say). The engine's own
   post-pass (block costs, can't-block-alone) then applies regardless.

No model re-ask at D5 (parked with the shared cast-veto re-ask lever). No
heuristic judgment anywhere in the normal path — engine legality only.

## Follow-on notes

- Eval runs keep obs on (standing rule), so the obs-join label path works
  on model games unchanged (the combat flags land in post-declaration
  windows exactly as in the corpus).
- Expressiveness gaps accepted at D5, return with the drill era: no
  multi-block (menace answers limited to 2+ distinct rows... actually to
  none — the pointer picks one attacker per blocker; corpus had 0
  multi-blocks), no banding (`reinforceWithBanding` is AI-only, skipped),
  within-group attacker-target ties (identical attackers on different
  defenders collapse to one row).
- Census per window: `by=bridge, n_assign, dropped, forced, fallback` —
  the D5 telemetry that prices every deviation from the model's raw intent.
- Parity test extension: combat windows through featurizer vs loader
  (byte-identical tensors), plus `act()`-pick → wire → realized-map
  round-trip on a scripted position.
