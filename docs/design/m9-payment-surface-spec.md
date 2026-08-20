# M9 D3 rung 2 — the §3c payment surface: fork-delta design spec

**Pinned:** 2026-08-19 (D3 rung-2 design session).
**Anchors:** [m9-plan.md](m9-plan.md) D3 (scope pins + rung-1
resolution); [ADR-0065](../decisions/ADR-0065-d3-engine-capability-audit.md)
(the capability audit this spec builds on — every mechanism named here
was verified there); [ADR-0064](../decisions/ADR-0064-d2a-affordability-probe.md)
(the artifact-stratum design input); [ADR-0063](../decisions/ADR-0063-m9-d1-veto-knowability.md)
(the `conditional_production` enumeration family);
[bridge-protocol-v0.md](bridge-protocol-v0.md) (the wire this extends);
[anvil-design-v2.md §3c/§3d′](anvil-design-v2.md).

Everything here is fork-side design; the Java lands on branch
`m9-payment-surface` (never on research `master` pre-boundary) and
merges as part of the ONE boundary bundle. Numeric pins are
design-session values; each is revisitable at build **with a recorded
reason**, none silently.

## 1. Decision surface

**Hook:** `PlayerControllerAnvil.payManaCost(toPay, costPartMana, sa,
prompt, matrix, effect)`.

**In-scope window (all must hold):**
- `effect == false` (resolution-effect payments = payment-completion
  queue item 3, OUT of v1);
- `toPay` has nonzero mana component (skips the ~73/g zero-mana /
  nested mana-ability windows);
- the payer is the Anvil-controlled seat (inherent in the override).

**Flow:** enumerate payment classes (§3) → if `< 2` classes, never
bridge (auto-payment, zero round-trip) → if `≥ 2`, emit the obs
payment window (§6), bridge the decision (§5), execute the answer (§7).
Telemetry records every in-scope window either way (§8).

## 2. Source atoms and source classes

**Atom:** `(card, manaAbility)` for every card the payer controls
where the ability `canPlay()` — built from `Card.getManaAbilities()`
directly. **Hard rule (ADR-0065 finding 5): `getAIPlayableMana` is
never called anywhere in enumeration** — it is auto-payer-derived
filtering, the concrete interface trap. Atoms therefore INCLUDE
mana-cost-to-activate producers (Signets), the `conditional_production`
family (RestrictValid/tapXType — ADR-0063), and sick-but-nontap hosts.

**Atom signature** (equivalence key; the resource-commitment-set
abstraction the cousins graft onto later):
`(production options, predicted yield, activation-cost shape,
residual-relevance)` where
- *production options* = the color-multiset alternatives the ability
  can add (fixed / combo / any / reflected, via `AbilityManaPart`
  `canProduce`);
- *predicted yield* = amount including known boosts, via
  `predictManafromSpellAbility` (prediction arithmetic, not willingness
  filtering — allowed; mispredictions are caught by the executor's
  engine adjudication and counted, §8). **Yield-differing atoms are
  different classes by definition** (the D2a-session pin — a
  Sprawl-boosted forest is not a forest);
- *activation-cost shape* = tap-only / mana+tap / sac / life / other;
- *residual-relevance* = what tapping loses: `(isCreature, P/T if so,
  hasNonManaActivatedAbilities, isSnow, cardType land|artifact|other)`.
  Card NAME is deliberately excluded — two different-named vanilla
  G-producing lands are the same class.

**Source class** = atoms grouped by identical signature.

## 3. Payment-class enumeration (legality-derived)

**Payment class** = `(multiset of source classes activated, pool mana
spent by color, phyrexian-life count)`. Two concrete payments identical
under this key are interchangeable — the model decides over classes,
never over individual permanents (§3c design text).

**Algorithm:** deterministic DFS over the cost's shards (the
`getNextShardToPay` order), assigning class-level counts; pool mana and
phyrexian life are explicit assignment options (phyrexian pay-life-vs-
mana IS a class distinction — it addresses a named D1 artifact family).
Feasibility via `ManaCostBeingPaid` arithmetic + `canPayForShardWithColor`
(engine primitives, not re-implemented arithmetic; conversion matrices
applied the way the execution path applies them).

**Chained activation:** an atom with a mana activation cost is
admissible in a plan iff a valid activation ordering exists — checked
greedily: order candidate activations by net mana gain (zero-cost
first, then net-positive), require running float ≥ each successive
activation cost. This is exactly the float-then-apply order the
executor uses (§7), so enumeration feasibility = executor feasibility
by construction.

**Caps (all truncation LOGGED, never silent — the no-silent-caps
rule):**
- `K_MAX = 8` distinct classes surfaced (+ `auto`); DFS order is
  deterministic, so truncation is reproducible;
- plan size ≤ `shard count + 2` activations;
- truncation-rate watch: if telemetry reads > 5% of consequential
  windows truncated, the cap design is revisited before D4.

## 4. The consequential flag

`consequential(window) := in-scope ∧ |classes| ≥ 2`. Nothing else —
residual/yield distinctions are already inside the class definition, so
the flag falls out of enumeration for free. Non-consequential windows
never bridge; the flag ships with its own census telemetry (§8) and the
consequential-window rate is **read from a census run before any model
side trains** (m9-plan rung-2 text).

## 5. Wire

**Design simplification vs the plan text (recorded):** no new proto
answer shape is needed. The decision is `SELECT_ONE` over an
engine-enumerated option list — a new **decision tag**
`mtg.pay_mana_class`, zero schema change (the bridge-protocol-v0
hygiene rule working as designed: new decisions add tags, not shapes).
The plan's "one new answer shape" pin is satisfied by tag + option
semantics; m9-plan carries a pointer to this paragraph.

- Option 0 = `auto` (defer to `ComputerUtilMana`) — always present,
  making day-zero behavior bit-identical under the auto-biased init.
- Options 1..K = payment classes, each carrying: entity refs of the
  sources a representative concrete plan taps (chosen deterministically
  within class, lowest entity id), pool-spend vector, phyrexian-life
  count, predicted post-payment float. Entity refs are what the model
  side pointer-encodes ([STATE] ⊕ cand — the D2a-validated substrate).
- Micro-step invariant preserved: one decision per consequential
  window, the game thread blocked as usual.
- `bridged_tags` handshake gates it per session — serving old
  checkpoints with the tag un-bridged reproduces today's behavior
  exactly.

## 6. Obs emission (rides the boundary bundle's schema delta)

New decision-context record at the bridged window: cost pips remaining
by shard, floating pool by color, host-SA entity ref, and the option
list from §5. Game-agnostic framing per the hygiene convention (entity
refs + numeric vectors, no Magic vocabulary in the schema). Obs schema
version bumps with the bundle; **sa_vocab is untouched** — payment
classes are not SAs, no vocab regeneration (the ADR-0012 pin stays
safe).

## 7. The directed executor (float-then-apply, per ADR-0065)

On a class answer:
1. Map class → concrete plan: within each source class pick atoms
   deterministically (lowest entity id); order activations zero-cost
   first, then net-positive chained (the §3 ordering).
2. Pre-validate each activation (`canPlay` + activation cost payable
   from current float) immediately before executing it.
3. Execute via the audited primitive: `CostPayment.payComputerCosts`
   → `stack.addAndUnfreeze` per atom, express choice set per the
   plan's color assignment (§ADR-0065 finding 3).
4. Hand the window back to `ComputerUtilMana.payManaCost` — the pool
   now covers the plan's spend, and the engine's own pay-from-pool-
   first path completes the payment (auto completion = the salvage
   path too, see below).

**Failure semantics (pinned at the D3 opening session, restated):**
- a pre-validation failure mid-plan → stop directed activations,
  fall through to step 4 with whatever floated → reason
  `directed_salvage`;
- total payment failure after salvage → the engine's own unpaid-cost
  rollback, reason `directed_fail` — **never counted as a veto** (else
  D5's mechanism read measures itself);
- executed yield ≠ predicted yield → `yield_mismatch` count (the
  prediction-arithmetic guard, §2);
- leftover float after the window → `float_residue` count (phase-end
  mana loss is the exposure; expected ≈ 0 since plans are exact).

## 8. Telemetry (census + run stores, ships WITH the flag)

Per game: in-scope windows; consequential windows (the rate the 2.6%
bridge-tax budget is checked against — in-scope traffic is ~61/g,
census-measured 2026-08-19); class-count histogram; `K_MAX` truncation
count; answer distribution (`auto` vs class index); executor outcomes
(`directed_ok` / `directed_salvage` / `directed_fail` /
`yield_mismatch` / `float_residue`). Census workers run
enumeration+telemetry with bridging disabled (telemetry-only mode) so
the consequential rate is readable on heuristic play — the
pre-training read rung 2 owes.

## 9. Model side (built at rung 3 / D4 — recorded here for interface
completeness)

Payment sub-head over `{auto} ∪ classes`, auto-biased init (M9 design
session, settled), hard-masked by the enumerated list, riding the
pointer-decoder payment step at the new bridging point (the D3 wire
pin: conditioning, not message shape, joins line-choice and payment).
Straight RL; no BC-from-heuristic anywhere.

## 10. Test plan

Fork-side units (branch, ride into the bundle):
- enumeration on constructed boards: Signet chain surfaces a chained
  class (the ADR-0065 board); dork+land vs land-only boards split
  classes on residual-relevance; single-basic board → 1 class → never
  bridges; boosted-yield land → distinct class; `K_MAX` truncation
  logged on a wide board; phyrexian cost → life-count class split;
- executor: directed_ok on the chained board (extends
  `DirectedPaymentAuditTest`); forced mid-plan failure → salvage path
  → no veto recorded;
- flag telemetry: census smoke reads a consequential rate consistent
  with the ~61/g in-scope traffic decomposition.

Boundary obligations (standing, restated): forkcheck certification,
2,000-game re-baseline, era-scoping of selection/evalset/isotonic
assets, obs schema version bump.

## 11. Pinned constants

| pin | value | revisit trigger |
| --- | --- | --- |
| `K_MAX` classes | 8 (+`auto`) | truncation > 5% of consequential windows |
| plan-size cap | shards + 2 activations | truncation telemetry, same gate |
| chained admissibility | greedy net-gain ordering | executor `directed_salvage` rate > 1% |
| in-scope traffic budget | ~61/g ceiling, flag-sparse below it | census telemetry read pre-training |
| enumeration primitives | engine arithmetic only; `getAIPlayableMana` BANNED | never (the trap rule) |
