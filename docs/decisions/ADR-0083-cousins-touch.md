# ADR-0083: The cousins touch — cost-composition cousins, costmod per-spell, pool-tie fix, combat costs

- **Date:** 2026-08-28
- **Status:** accepted
- **Design-doc anchor:** §3c (payment surface); m10-plan actuation pin 2 (the serve contract); m9-plan payment-completion queue items 2/4/5

## Context

The M10 serve contract pins cost-composition cousins in scope **from
birth** (m10-plan actuation pin 2), so the payment-family fork touch had
to precede the training probe — enumeration changes de-sync the
certification jar from the training jar (the gate-session decision 3
rationale; "never mid-era"). Three queue items rode the same touch by
name (ADR-0077 routing): **cousins** (convoke/improvise/delve/
`payCombatCost`, item 2), **costmod per-spell refinement** (item 4,
25.48% of in-scope traffic absorbed by presence-scoping), and the
**pool-tie enumerator residual** (item 5, the lex-hidden `min_life`-side
plan).

Engine archaeology established the mechanics: cousins are applied inside
`CostAdjustment.adjust(ManaCostBeingPaid,…)` **one frame deeper than the
`payManaCost` override** (raw `toPay` is raise-adjusted only — exactly
why the old detector punted); the only directed-execution seams are the
controller callbacks `chooseCardsForConvokeOrImprovise` /
`chooseCardsToDelve`, which return the shard assignment itself and are
applied unvalidated; a convoke tap pays generic always or a colored
shard intersecting the creature's own colors (never snow/{C}), improvise
pays generic/2-hybrid, delve strictly GENERIC; the heuristic AI returns
an **empty convoke map pre-attacks on its own turn** (engine TODO), so
directed convoke unlocks a capability the auto-payer plays as a blank
(the ADR-0065 finding-6 genre). `payCombatCost`
(CantAttackUnless/CantBlockUnless/OptionalAttackCost) routes to
`PlayerController.payManaCost` on both paths with `effect=true` and a
degenerate `EmptySa` whose host is the attacker; `CostAdjustment` is a
no-op for effect costs, making combat costs the clean enumeration case.
`CostAdjustment.checkRequirement` is the engine's own per-spell
applicability predicate (deterministic, no controller calls).

## Decision

One fork touch, heuristic-game-path behavior-identical, four sub-pins
user-adjudicated 2026-08-28 (all on the recorded leans):

1. **Delve IN, type-grouped classes** — graveyard cards become delve
   atoms grouped by the shared res signature (creature P/T,
   land/artifact/other; name excluded per spec §2); goal prefix
   `spare_gy:`, new kind `spare_graveyard=6`.
2. **`payCombatCost` bridged now** — a combat marker set in the
   `payCombatCost` override widens the nested `payManaCost` window's
   scope past the `effect` gate; same `SELECT_ONE` tag, auto = option 0
   = today's `playNoStack` behavior bit-identical. Pay-vs-decline stays
   heuristic upstream (`ComputerUtilCost.canPayCost`) — that is
   ADR-0080's re-deferred genre; this is only HOW to pay. Combat window
   rows carry `combat`/`cmb` kvs; the costmod detector is skipped there
   (no adjustment on effect costs; the EmptySa host's own casting
   keywords must not trip the scan).
3. **Costmod applicability-only** — the presence-scan is replaced by
   per-spell applicability via a fork-local additive accessor
   `CostAdjustment.staticAppliesTo` (= `checkRequirement` verbatim);
   `SetCost` joins the scanned modes (previously invisible; measured
   leak 0, free conservatism). Convoke/improvise/delve LEAVE the
   detector; assist/offering/emerge stay costmod (spell-gated
   `sa.isSpell()` like the engine's own dispatch), plus
   `TapCreaturesForMana`/waterbend conservatively. The `costmod_late`
   backstop stands unchanged.
4. **GOAL_MAX 16 → 24** pre-data with recorded reason (cousin source
   classes stack on the ≤11 measured mana classes); the 0.5% truncation
   gate stays armed.

Mechanics (as-built detail in m10-build-spec):

- **Enumeration**: cousin atoms are restricted pseudo-atoms in the same
  DFS — main-cost shards only (index < the initial shard count; the
  engine applies cousins before any mana flows), no floats, no
  activation interplay; `cousinCanPay` mirrors `payManaViaConvoke` /
  `decreaseGenericMana` exactly. Cousin atoms are kept OUT of
  `Result.allAtoms` (that list is the residual-mana-capacity universe
  the schedule scorer reads — cousins are not mana). `spare(k)` goals,
  spread/lex tie-breaks, outcome dedupe, and `chainOrderFeasible`
  extend unchanged (cousin-paid shards leave the main-cost requirement
  before the temporal check).
- **Pool-tie fix**: a `spare_pool` goal (minimize floating-pool spend,
  kind 7) whenever the window enters with pool mana and other goals
  exist — on the phyrexian pool-tie board the pay-life plan is its
  argmax, so the hidden outcome surfaces; regression-tested.
- **Directed execution**: `CousinDirective` (WeakHashMap-armed per
  payer) is consumed by generated FORCE_OVERRIDES hooks on the two
  callbacks; unarmed = null = natural heuristic play. Armed on EVERY
  directed payment — an empty map is the correct directive on a
  cousin spell whose plan spares the cousins. Arm/disarm is
  finally-scoped on the bridged and sched paths; the certify path
  (PayDirective) arms before `executeDirected` and is swept at the next
  window's entry (both `payManaCost` entries disarm defensively — the
  generated controller has no post-super hook).
- **Python twin**: `PAY_KINDS` += `spare_graveyard=6`, `spare_pool=7`;
  `pay_kind_emb` grows to (8, d) zero-init; option labels carry cousin
  hosts in `ents` for free (the plan's atoms), so `_pay_mark`'s
  remove-consumed-ents affordability math degrades correctly.

**Proofs banked:**

- Fork tests: PaymentEnumeratorTest 16/16 (6 new: convoke color
  discipline, improvise generic-only, delve classes+kind, pool-tie
  regression, Electromancer per-spell split, CousinDirective consume
  semantics), PaymentWiringTest 3/3, PaymentCertifyTest 4/4,
  DirectedPaymentAuditTest 4/4. Anvil suite 253 green.
- **ADR-0025 jar gate PASSED** (the 7c4af49fa4 protocol, rerun vs the
  banked proven-jar outputs): sched smoke 9,969 census rows + 72/72 +
  72/72 labels rows identical modulo ms, schedfile byte-identical;
  choice smoke 17,409 census rows + 84/84 + 84/84 labels rows
  identical modulo ms, choicefile byte-identical; internal re-run
  determinism holds on both — **ZERO diff classes total** (the touch's
  deltas are dormant outside directed/bridged/enumerating contexts).
- Graft regenerated (`m10-sched-init`, pay_kind_emb (8,512) all-zero);
  **day-zero reliance re-banked: argmax_flip 0.012513 / content_flip
  0.0 EXACT / reliance_l1 0.786172 / sched_rms 0 — identical to the
  banked floor** (aux head losses moved within fresh-init RNG noise, as
  at the R5 regen).

## Consequences

- The serve contract's payment scope is COMPLETE as pinned: M9
  in-scope + cousins + costmod-refined + pool-tie + combat costs, all
  before the probe ckpt trains — no second enumeration-era boundary.
- **Banked observe frames can drift** (spare_pool adds options on
  phyrexian pool-tie windows; per-spell costmod returns windows to the
  surface): the evalset revalidation + holdout observe mints re-run on
  this jar before the probe ingests labels, `option_mismatch` counted
  loudly (`paylabels.py` already excludes drifted windows). This rides
  the probe-launch session's pre-flight.
- **Census read obligations move to the next census run** (probe
  launch pre-flight or first big run): post-refinement costmod rate
  (expect ≪ 25.48%), cousin window/option rates, nodecap + goal-trunc
  gates re-read under graveyard-widened boards, combat window rate.
  PaymentTelemetry's enumeration census still skips effect=true rows,
  so combat windows get RATE telemetry (the outer callback census row)
  but not option-census there — recorded gap, closes free at the first
  bridged-mode read.
- Canonical-register item 8 (exact payment matching in the schedule
  scorer) has its funding trigger armed for real now: the
  salvage/fail counters watch cousin-bearing plans from birth.
- Upstream blind spot recorded, not fixed: `removeUnpayableAttackers`
  (and the heuristic's cast decision generally) consults the auto-payer
  BEFORE the window, so attackers/casts only payable via directed
  chains or cousins never reach the surface on heuristic play — the
  known ADR-0065 blind-spot genre; model-era generation reads it.
- `PlayerControllerAi`'s empty-convoke-pre-attacks TODO means directed
  convoke is a real capability unlock, not just refinement — worth a
  named read at the probe (follows the pay-family telemetry).
