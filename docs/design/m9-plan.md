# M9 — the interface round: conscious mana payment, probe-gated, with the veto-collapse mechanism check; turn-plan latent as the second act

**Opened:** 2026-08-19 (user-approved shape, this session).
**Anchors:** [ADR-0062](../decisions/ADR-0062-m8-closeout.md) (M8
closeout + the routing + the standing veto account);
[devlog 2026-08-17-session3](../devlog/2026-08-17-session3.md) (the
M9-seed section — the veto-as-interface-artifact framing, user insight
2026-08-18); [ADR-0042](../decisions/ADR-0042-d2b-design-session.md)
(the §3a/§3c priority note + the critic-leaf dependency);
[ADR-0061](../decisions/ADR-0061-d2prime-audit-resolution.md) (the
0.42-vs-0.94 ordering measurement that constraint now carries);
[anvil-design-v2.md §3a/§3c](anvil-design-v2.md) (the design surface);
[callback-census-results.md](callback-census-results.md) (`payManaCost`
~120 calls/game, top-5 traffic; `specifyManaCombo`/`applyManaToCost`
never fired — the consequential-payment flag does not exist yet);
[m8-plan.md](m8-plan.md) (the pattern this doc follows).

## The question

Three milestones read the same signature — trainable, behavior-moving,
strength-neutral — from representation (M6), credit (M7), and curation
(M8). Every lever operated *through* the existing action interface, and
the standing veto account (ADR-0062) says why they flatlined: under
auto-payment with free re-asks, probing-via-veto is optimal play, and
no training signal routed through the interface can teach what the
interface cannot express. M9 asks: **does interface competence —
conscious mana payment first, phase-level planning second — move
strength, with veto collapse as the mechanism check?**

**The falsifiable prediction (carried from ADR-0062, the thing no
prior milestone had):** a payment-aware model shows veto collapse with
no penalty. If the mana head is built and trains and vetoes do NOT
fall, the interface theory is falsified — that is a first-class result
and the closeout ADR records it as such.

**Settled at the design session (user-approved 2026-08-19):**

- **Training signal: straight RL over `{auto} ∪ payment-classes`,
  auto-biased init. BC-from-heuristic is dropped entirely — not even
  as init.** Rationale: the head only fires in consequential windows,
  which is exactly where the auto-payer is least trustworthy
  (`ComputerUtilMana` cannot construct payments through sources that
  cost mana to access, and tap-order residuals — dork-as-blocker,
  attacker-vs-mana — are precisely the distinctions the heuristic
  never weighs). The distinguished `auto` action defers to the engine,
  so an auto-biased init makes day-zero behavior bit-identical to
  today: BC's safety without BC's teacher. Known failure mode —
  deviation reward is sparse, the head can collapse to always-auto —
  is why D4's probe reads drills and deviation telemetry, not just
  strength.
- **Boundary discipline: ONE boundary event.** **LANDED 2026-08-21
  ([ADR-0068](../decisions/ADR-0068-m9-boundary-bundle.md)), all reads
  complete same day: era `2f87180cdf`, gate re-pinned 0.5279 ± 0.0110
  corrected, evalset revalidated (zero new drift; baselines re-banked
  2/64 / 196/214, gate denominators carry), 2-arm trim retired, fidelity
  10.0% (held). Done-when 3 SATISFIED.** The §3c fork delta
  rides the queued next-boundary bundle (upstream rebase + multi-format
  model-side enablement + copy-state divergence forensics + the
  fork-index store-namespace fix from run17 iter-2 + obs choice-state
  emission — "as enters, choose a color/card" state is public at the
  table, engine-side `getChosenColor()` exists, and the obs never
  carries it: Utopia-Sprawl-class enablers are imperceivable without
  it; found at the D2a session 2026-08-19), held until the
  engine changes are ready. D1/D2 run on the current era — both are
  era-scoped instruments anyway. (The queued 2-arm campaign trim is
  likely MOOT — the forced-seq campaign belongs to the retired
  act−hold formulation; verify at the boundary and either land or
  retire it explicitly.)
- **Sequencing: strict sequence for build work** (side-project
  trackability); long runs may overlap bench work.
- **Interface-capability requirement (the trap found at design):
  payment-class enumeration must be legality-derived (what payments
  CAN exist), never auto-payer-derived (what the heuristic would
  construct)** — otherwise the chained-activation blind spot is baked
  into the interface itself and no training signal can reach it. D3
  opens with the engine capability audit this requirement implies.

## D1 — the veto knowability decomposition (entry instrument + theory premise check)

**RESOLVED 2026-08-19
([ADR-0063](../decisions/ADR-0063-m9-d1-veto-knowability.md)); baseline
RE-PINNED same day under instrument v2 (sick-aware — the ADR's
"sickness absent from the obs schema" claim was backwards; `sick` IS
emitted and fed to the model; see the ADR addendum): gate PASS in all
four populations — knowable 0.5392 sampled / 0.5097 argmax / 0.5336
stock / 0.6044 elevated (lower bounds; validity bar 0.986–0.991). The
premise stands; **collapse baseline = knowable-veto rate 0.0588
sampled / 0.0435 argmax (v2)**. The elevated population is MORE
knowable — the veto climb happened in the knowable channel; the i011
guard-halt near-doubles the knowable-veto rate (0.1049).**

**Question:** of the vetoes the current policy actually eats, what
fraction are *knowable-from-public* (the acting seat had enough public
information to know the cast was unaffordable/illegal) vs
*hidden-info-plausible*? This is simultaneously (a) the baseline
against which D4/D5's veto collapse is measured — "collapse" must mean
the knowable fraction falls, not that hidden-info probes stop — and
(b) a premise check on the interface theory: if most vetoes turn out
NOT knowable-from-public, an affordability-bearing interface can't be
what removes them, and the theory is in trouble before anything is
built.

**Method (PINNED at the D1 session, 2026-08-19):** classify logged
vetoes by joining census veto records to the raw obs stream at
`(g, s)` and computing affordability **from the observation the model
actually saw** (untapped battlefield sources via `tap` + a card table
parsed from the fork's card scripts: `ManaCost` + `Produced$`
including combos; commander tax via `cmdcast`) — so
"knowable-from-public" literally means "knowable-from-the-model's-own-
input," the exact premise D2a then probes on `[STATE]`. Seeded replay
is spot-validation only. **Instrument validity bar (pinned):** the
classifier must call ≥95% of engine-*accepted* casts affordable (the
free adjudicated negative-control population); windows the arithmetic
can't settle (cost modifiers, X-costs, alt-costs) go to an explicit
`uncertain` bucket reported separately, never silently into either
class. Output: knowable fraction ± CI per population, plus a taxonomy
of the knowable ones (colors short / generic short / timing-illegal /
other) to shape the D3 class design.

**Populations (pinned; the M8 kill list had removed the sampled-play
census — restored 2026-08-19 from the kopia 08-19 08:00 pre-kill
snapshot):** sampled-play = `d6-run17-i000*` (generation from the
run17 *init*, i.e. iter-019 itself, at training temperature; veto rate
0.195 = ADR-0062's recorded iter-0 baseline; 4,816 vetoes / 3,547
first-attempt); argmax = `d3-rebaselinearm-s0/s1` (12,167 vetoes) with
`m8stock*` (restored, argmax per `cycle_stock.py` `sample=False`,
40,597 vetoes) as supplementary N; `run17-i009/i010-finalarm` = the
elevated-population descriptive. Note: the remaining run17 iteration
dirs live only in kopia dailies expiring ~08-25.

**Pre-registered reads (PINNED 2026-08-19):**

1. Knowable-from-public fraction ≥ **0.50** ⇒ premise stands, the
   veto-collapse metric is defined on the knowable subset. Basis:
   **first-attempt vetoes** (the chain-independent M3 rule — re-ask
   chains can't inflate either side), **mana-relevant subset only**
   (`unpayable` + `timing`, ~74% of veto mass; `no_shape_fit` is
   realizer shape-mismatch and `restrictions`/`dangling_ref`/
   `after_stack` are engine-rule artifacts — a payment head shouldn't
   collapse those, so they'd blur both the gate and the falsification
   test). The full all-reasons decomposition is still reported and
   banked as the baseline table.
2. Below the pin ⇒ the M9 question is re-scoped at a checkpoint
   session before D3 spends fork work (the payment head may still be
   right for *strength* reasons, but the veto-collapse mechanism check
   would be measuring the wrong channel).

Cost: analysis over existing stores + replay compute; no generation,
no training. Standing-asset candidate: the classifier doubles as
run-battery telemetry afterward.

## D2 — the affordability probe pair (mechanism, no fork delta)

**D2a RESOLVED 2026-08-19
([ADR-0064](../decisions/ADR-0064-d2a-affordability-probe.md)): gate
PASS on the high branch — `[STATE] ⊕ cand` holdout AUC 0.8809 ≥ 0.75,
margin over explicit obs-arithmetic +0.0378 ≥ 0.03; transfer 0.8967
argmax / 0.8917 elevated (no refit). The veto gap is
behavioral/interface; D2b SKIPPED per the pinned routing. The finding
inside: on the auto-payer-artifact stratum the arithmetic arm is chance
(0.5385) while the trunk reads 0.8422 — the model partially predicts
the engine payer's own willingness refusals; banked as a D3 design
input. D3 (engine capability audit first) is next.**

Mirrors the ADR-0042 B-1/B-2 probe discipline: measure before building.

- **D2a — frozen-trunk affordability probe:** can affordability (will
  the engine veto this cast?) be predicted from the current `[STATE]`
  representation? Labels are free — every veto and every accepted cast
  is already engine-adjudicated in the logged stores. Fit the standing
  cheap-probe stack (ridge on `[STATE]`, per the frozen-probe
  precedent; probe on `[STATE]`, never the trained head — M6 standing
  rule) on a game-grouped split. High probe accuracy ⇒ the trunk
  already carries the ingredients and the gap is behavioral/interface;
  low accuracy ⇒ affordability is a genuine representation gap that
  the §3c surface must expose.
- **D2b — affordability aux head in-loop (conditional on D2a reading
  a representation GAP — routing pinned below, inverting the draft's
  conditional):** wire the aux prediction target into a short training
  run (aux only — no action-space change, no fork delta) and read the
  veto trajectory against the D1 baseline. This is the *minimal*
  version of "payment-aware." If aux affordability alone collapses
  knowable vetoes, the theory's mechanism is confirmed before any Java
  is written — and the D5 strength question sharpens to "does payment
  *control* (not just awareness) move strength."

**D2a pins (PINNED at the D2 session, 2026-08-19, pre-data):**

- **Label:** will-the-engine-veto on the chosen cast — positives =
  first-attempt `unpayable` vetoes, negatives = engine-accepted
  first-attempt casts (exactly the D2b aux target and the D4/D5
  metric; timing excluded — not affordability; other veto reasons
  reported descriptively, never in the primary fit). Headline number
  on the raw engine label; AUC additionally **stratified by the D1
  instrument verdict** (knowable / auto-payer artifact / uncertain) —
  the artifact stratum is the auto-payer blind spot and D3 consumes
  the stratified table.
- **Substrate:** `[STATE] ⊕ candidate-entity token` primary — both
  are trunk outputs, the exact pair the pointer head consumes
  (recorded extension of the M6 probe-on-`[STATE]` rule to
  per-candidate questions); `[STATE]`-only reported alongside as the
  literal-rule arm.
- **Baseline ladder** (the "public-features-only baseline" slot):
  base rate → cost-pips-only → obs-arithmetic (the v2 instrument's
  own verdict + untapped-source counts as explicit features) →
  `[STATE]` → `[STATE] ⊕ cand`. Claiming "the trunk carries
  affordability" additionally requires beating the obs-arithmetic
  arm by **≥ 0.03 AUC** (the ADR-0043 reconstruction discipline:
  arithmetic the trunk merely re-encodes is not a finding).
- **Gate:** held-out AUC on `[STATE] ⊕ cand` **≥ 0.75** ⇒ the trunk
  carries the ingredients, the gap is behavioral/interface; **≤
  0.60** ⇒ genuine representation gap the §3c surface must expose;
  between ⇒ both readings priced at a checkpoint session.
- **D2b routing (pinned pre-data):** high branch (≥ 0.75) ⇒ **D2b is
  SKIPPED** — an aux head predicting what the trunk already encodes
  teaches nothing new; the missing piece is the behavioral incentive,
  which only the §3c surface supplies; the short run is saved (the
  forfeited secondary falsification — "mere awareness collapses
  vetoes" — is noted deliberately: the theory predicts a no-op there
  at a full run-slot's cost). Low branch (≤ 0.60) ⇒ D2b funded as a
  genuine representation intervention (partial-unfreeze precedent
  ADR-0044 applies). Between ⇒ the checkpoint session routes.
- **Populations/split:** fit + holdout on the sampled trio (the
  training distribution), game-grouped deterministic split
  (standing); transfer reads (no refit) on argmax and elevated.
  Labels from the **v2 sick-aware instrument** windows (ADR-0063
  addendum — the D1 baseline re-pin).

If D2b runs, its veto-collapse margin on the knowable subset is
pinned at its own launch **[PIN]**. Neither gate blocks D3 — the
payment surface is funded on the ADR-0062 routing regardless — but
both readings are recorded premises the closeout ADR must reconcile:
a D2b that already collapses vetoes changes what D5's veto read can
attribute.

All standing training rules apply from birth to D2b: clips/hinge at
birth (ADR-0056), auto-calibrated weights instrumented + guarded +
recalibrated at drift cadence (ADR-0057), share guard + kl abort,
fixed-subset arms reads counted once (ADR-0058).

## D3 — the §3c build: engine surface + payment sub-head + the drill evalset

**D3 scope pins (PINNED at the D3 opening session, 2026-08-19,
pre-audit — each reversible until rung 2 commits fork work):**

- **Wire placement: follow-up micro-decision, permanently.** The
  payment-class choice is its own bridged decision at the
  consequential payment window, enumerated only for the
  already-chosen SA — NOT a slot inside the one-shot `CastPlan`.
  Rationale: payment windows are origin-agnostic (cast / activated
  ability / triggered cost / later effect+combat costs all funnel
  through `payManaCost`), so a CastPlan slot covers one origin and
  the follow-up mechanism is needed anyway; the joint-decision worry
  is answered by conditioning (the SA is already chosen; §3a's latent
  conditions further), not message shape; the round-trip cost lands
  only in consequential-flag-sparse windows; and legality-derived
  enumeration is only cheap at the actual window where
  `ManaCostBeingPaid` exists — in-plan enumeration over candidates is
  the expensive path that tempts heuristic shortcuts (the trap).
  Boundary rider: `bridge-protocol-v0.md`'s "payment-class picks
  inside CastPlan" line is retired at the bundle, replaced by the new
  answer shape; the pointer decoder's `… modes / X / payment` step
  order survives — the payment step just executes at a different
  bridging point.
- **Window scope v1: casts + activated abilities, `effect=false`
  only.** Traffic re-measured on `run-20260704-dcpool` (500 games):
  `payManaCost` is **189/g** (the ~120/g in the census doc is stale),
  decomposing ~73/g mana-ability windows (zero-mana/nested — never
  consequential; rung 1 confirms the nesting story), **~61/g in-scope
  cast/activation payments**, ~54/g `effect=true` resolution
  payments. Effect payments are OUT of v1 — they contribute zero to
  the mechanism read (no `unpayable` vetoes in the D1 baseline live
  there), they're a different genre (pay-or-suffer during resolution,
  whether-to-pay is a separate confirm callback), and they'd double
  the surface against the sparsity budget. Recorded in the
  anvil-design-v2 §3d′ ledger as an explicit deferred sub-family.
- **Cost-composition cousins (convoke/improvise/delve/
  `payCombatCost`): OUT, graftable.** Not auto-M10 (that slot's
  named candidate is §3b) — a named rider on whichever milestone next
  touches the payment family. The class abstraction is written as a
  *resource-commitment set* (not "a set of lands") so they attach
  without redesign; their callbacks are already `SELECT_K`-shaped on
  the wire, so the deferred cost is model-side only. Known confound
  recorded: where convoke/improvise fire today, the heuristic picks
  the committed cards and payment enumeration conditions on that.
- **Audit-fail routing (pre-registered): scope to what the engine can
  execute today.** If rung 1 finds the engine cannot execute a
  directed chained-activation payment, v1 ships over single-window
  tap-set/color direction; the directed executor becomes a named
  follow-on funded by a confirmed D5 mechanism (the D2a genre applied
  to engine work — a falsified mechanism means it's never built).
  The chained-activation blind spot then persists through M9 and
  D5's attribution scopes its claims to expressible classes. This is
  NOT the interface trap: scoping by engine *executability* is an
  honest recorded capability boundary; enumeration within scope stays
  legality-derived. The boundary bundle is not re-priced on this
  branch (that's the point).

Three rungs, strictly ordered:

1. **Engine capability audit (before any protocol work):** can the
   fork engine *execute* a directed payment it is handed — including
   chained-activation payments (`ComputerUtilMana` cannot construct
   these; can the engine perform them if told to)? If yes, enumeration
   is archaeology over the existing cost-payment machinery; if no,
   there is real engine work and the boundary bundle gets re-priced
   before commitment. The audit result is recorded either way.
   **RESOLVED 2026-08-19
   ([ADR-0065](../decisions/ADR-0065-d3-engine-capability-audit.md)):
   YES — the game layer is chain-capable end to end; the blind spot is
   ONE candidate-filter line (`getAIPlayableMana` skips mana abilities
   with mana costs, Forge's own comment: "the AI will miscalculate").
   Empirical probe 4/4 green (`DirectedPaymentAuditTest`, fork,
   standing regression asset): heuristic refuses the payable chained
   board; the DIRECTED chain executes and casts (Signet's nested {1}
   paid from float through `CostPartMana.payAsDecided` re-entry);
   express choice steers any-color producers. v1 executor strategy =
   float-then-apply, zero new engine execution code; boundary bundle
   NOT re-priced. Hard rule for rung 2: enumerate from
   `Card.getManaAbilities()` + `canPlay()`, never `getAIPlayableMana`
   (that helper IS the interface trap, concretely). Bonus finding:
   `AI:RemoveDeck:All` cards are revealed, not stripped — Signet-class
   cards sit in decks as auto-payer blanks the payment head can
   unlock (pool carries the class: Boros Signet et al.).**
2. **The fork delta (rides the boundary bundle):** **Design PINNED
   2026-08-19 —
   [m9-payment-surface-spec.md](m9-payment-surface-spec.md)** (hook /
   atoms + source-class signatures / legality-derived DFS enumeration
   with chained admissibility / flag = `|classes| ≥ 2` / wire =
   `SELECT_ONE` + new tag `mtg.pay_mana_class`, ZERO proto change —
   recorded simplification of this rung's "one new answer shape" /
   float-then-apply executor with reason-coded failure semantics,
   never-a-veto / telemetry incl. census telemetry-only mode /
   `K_MAX = 8`, truncation logged, 5% revisit gate). Build on fork
   branch `m9-payment-surface`, merges only at the bundle. **Fork side
   BUILT 2026-08-19 (`e857277117`): enumerator + directed executor +
   controller hook + `mtg.pay_mana_class` bridging (observation rides
   `selectOne` unchanged) + census telemetry-only mode
   (`-paytelemetry`, generator `REC_OVERRIDES` hook, regen verified
   surgical); payment suite 13/13. Flag rule AMENDED at the wiring
   session — the wiring test caught the draft `≥2` rule failing the
   motivating I+I+Signet board (exactly ONE class: the chain is the
   only payment): consequential now also fires on the FORCED window
   (`|classes| ≥ 1 ∧ ¬auto-payable`; widens-only, trap-safe; `forced`
   telemetry marker; day-zero bit-identity preserved). Python side landed same
   day (payment_read.py + obs round-trip + the decline-echo fix).
   **Census read DONE (2026-08-19, `run-20260819-payflag`, 500 games):
   consequential 20.79/g (budget ✓); TRUNCATION GATE FIRED (0.3911 vs
   0.05; monotone in turn, wide-board combinatorics); zero-class +
   forced windows = the cost-modified family (delve/affinity — raw
   `toPay` vs `CostAdjustment`); CME ×144 guard-caught → fixed
   `f98a555a95`. Pre-D4 revisit session CHARTERED: K_MAX/truncation
   design + cost-modified scoping + forced-marker cleanup, then the
   census re-runs as the final pre-D4 baseline (spec §8 read block).**
   **Revisit session RESOLVED same day (spec §12, three pins + the tail
   probe that decided them):** tail probe (`run-20260819-paytail`, 60
   games, K raised to 64) measured cap-raising OUT — consequential
   class-count p90 = 55, tail past 64, explosion = assignment
   combinatorics over ≤11 source classes — so **the decision object is
   now a preservation GOAL** (`spare(k)` min-taps per source class +
   `min_life` on phyrexian; per-goal argmax, spread-then-lex tie-break,
   outcome dedupe; wire unchanged); chained-composition reachability
   via spare-goals TEST-PROVEN (no explicit chain goal needed);
   costmod out-of-scope v1 (two-pronged detector); `forced` gated on
   `¬costmod`. Built on fork `531dafdff4`, suite 14/14, Python 209.
   **FINAL PRE-D4 BASELINE PINNED (`run-20260819-paygoals2`, 500 games,
   ALL GATES PASS): consequential 15.99/g, goal truncation 0.0000 (max
   9 options), nodecap 0.0073 (after the 200k→2M re-pin cleared a
   1.25% first-run fire), forced 6 clean, costmod 25.48% leak-zero
   (refinement = queue item 4).**
   - **Consequential-payment flag:** engine-side detection that a
     payment window has ≥2 payment classes with different residuals
     (colors held, snow, ability-relevant permanents, chained
     activation available) — or different *yields*: a
     Utopia-Sprawl-boosted forest taps for 2, so different-yield taps
     are distinct classes by definition (pinned at the D2a session,
     2026-08-19). Non-consequential windows never bridge —
     `payManaCost` is ~120 calls/game and the 2.6% bridge tax survives
     only if the flag keeps the surface sparse. Telemetry ships with
     the flag: consequential-window rate per game (the surface's own
     census, read before the model side is trained).
   - **Payment-class collapse:** legality-derived enumeration (the
     requirement above), interchangeable payments collapsed into
     classes, decide over classes. The enumeration design session must
     record its stance on the cost-composition cousins
     (convoke/improvise/delve — same residual logic, different
     callbacks; design-doc §3 ledger item 4): in, or explicitly out.
   - **Bridge protocol addition:** one new answer shape (class index
     over an enumerated list + `auto`), micro-step invariant
     preserved. Boundary obligations per standing rules: forkcheck
     certification, 2,000-game re-baseline, era-scoping of
     selection/evalset/isotonic assets.
3. **Model side + the readout, built before any probe run:**
   - **Payment sub-head:** decision over `{auto} ∪ classes`,
     auto-biased init, hard-masked by the enumerated list; rides the
     existing pointer-decoder payment slot (§3).
   - **Payment drill evalset:** scenarios where the class choice
     provably flips the short-horizon outcome (dork-needed-as-blocker,
     wrong-color-tap-loses-the-hold, chained-activation-required).
     Mining rule: search logged games for cells where a source tapped
     for payment was consequential within 1–2 turns; hand-constructed
     seeds with ddmin certification as the fallback for unminable
     shapes (design §6, standing). Engine-adjudicated, per-decision —
     the readout D4 needs because a 5-iteration run cannot read
     strength. Provenance-traced per standing rule; drill mainlines
     never enter training ingest.

## D4 — the learning-signal probe run

A short run (~5 iterations on the standing loop, post-boundary
baseline) with pre-registered signals, cheapest first:

1. **Deviation rate and placement** — how often the head leaves
   `auto`, split by game context and consequential-window taxonomy
   (pure telemetry).
2. **Veto trajectory** vs the D1 baseline, knowable-subset scoped —
   the mechanism check's first reading.
3. **Payment drill accuracy** on the D3 evalset — the primary funding
   readout.

**Pre-registered gate (PINNED 2026-08-21, D4 gate session —
supersedes the [PIN] slots):** the day-zero scorer read measured
argmax deviation 8.3% at init (the "+2.0 ⇒ argmax=auto" pin is
approximate on real windows — rung-3 draft), so the original
"leaves auto at all" deviation floor is trivially satisfied and
CANNOT fund. It is **demoted to diagnostic** and the gate re-posed
as movement-from-baseline:

- **FUND (⇒ D5): positive-drill argmax accuracy ≥ 7/68 (~10.3%)** at
  any accepted iteration — ≥5 net newly-correct drills over the
  day-zero 2/68, ~2.5× the binomial SE (~2pp) — **with auto-correct
  ≥ 85% (≥189/222) at that same iteration.** Rationale for the
  asymmetry: positive drills are the only population that can show
  capability the auto-payer structurally lacks (the funding
  question); auto-correct starts near-saturated (91.9%) from the
  +2.0 init and can only show the deviates-wrongly failure mode — a
  guardrail, never a target, never blended.
- **CLEAN NEGATIVE:** argmax deviation on consequential windows
  **< 2%** (collapse-to-always-auto, the named failure mode) with
  positive accuracy never leaving noise (**≤ 4/68**) across the
  probe — the formulation negative at a fraction of a run's cost;
  the closeout records it and the checkpoint session routes
  (candidates: formulation variant — Option B dedicated-embedding
  head is the recorded fallback — or straight to the §3a second act
  with the payment surface held as infrastructure).
- **Between the lines = discuss-zone:** recorded, the read session
  adjudicates; nothing auto-promotes.
- **Baselines:** drill-window numbers = the banked day-zero scores
  (`run-20260821-observe/score-dayzero-iter019.jsonl`: positive
  2.9%, auto-correct 91.9%, argmax deviation 8.3%); live-window
  `pay_deviation` telemetry baselines at the run's own iter-0 (no
  pre-run number exists for it; argmax and sampled read separately
  per the ADR-0063 lesson). Per-iteration drill curves are
  near-free — the observe frames are ckpt-independent, so every
  accepted iteration gets scored.

**Gate-session decisions (2026-08-21), recorded with the pins:**

1. **Auto-bias stays +2.0.** The 8.3% day-zero deviation is a
   readout-framing problem fully absorbed by movement-from-baseline;
   the PASS anchor's raw score is context-dependent (−2.43
   spot-checked) so no scalar guarantees argmax-clean anyway; and
   raising it starves the ~10–12% sampled exploration D4's sparse
   deviation reward depends on (+3.0 already rejected on those
   grounds at rung 3). D5 boundary bit-identity is a wire property,
   unaffected either way.
2. **paygoals4 NOT run — the bound accepted.** paygoals3's 15.28/g
   stands as an upper bound (the ADR-0067 fix only removes plans;
   salvage was 0.22% of directed rows); its only operational role
   (bridge-tax budget, ~1.6%) has slack, and the post-boundary
   re-baseline census supersedes the number anyway. The D4 midpoint
   re-mine works from D4's own stores.
3. **Pool-tie residual (§12a lex-hidden `min_life` plan) deferred BY
   NAME = payment-completion queue item 5** (below). No enumerator
   change pre-D5: any enumeration change de-syncs the certification
   jar from the training jar (`option_mismatch` drift is exactly the
   guard's target class; the phy shape's floor margin is 3).
4. **Post-boundary evalset revalidation pass joins the boundary
   obligations** (done-when 3): re-run the observe lanes on the
   bundle jar (~35 min), count `option_mismatch` drift exclusions,
   re-check shape floors, re-bank the day-zero scores on the
   post-boundary init. The 3 already-drifted b1/b2 drills stay
   score-excluded (re-certify only if the D4 read needs them).
5. **Forced family = D4 midpoint re-mine (user pin restated from
   2026-08-21):** the pre-run evalset ships without forced (mining
   under heuristic play is structurally impossible — the ADR-0065
   blind spot sits upstream of the window); `pay_deviation` on
   forced windows is the live readout; at the run midpoint, mine the
   run's own stores — with an hb-signet self-pair generation run
   under the D4 checkpoint as the accelerant if natural traffic is
   thin — and certify through the standing harness. Resulting drills
   form a **D4-era addendum set scored separately, never
   retroactively part of the 7/68 gate.** An empty re-mine even with
   hb-signet ⇒ revisit the declined cast-directive alternative.

### D4 run recipe (PINNED 2026-08-21, recipe session)

The gate above is unchanged; these are the run-shape pins. Standing
recipe = run17's loop_config (the run11 lineage) EXCEPT where listed.

1. **Init ckpt must be GRAFTED — launch blocker, not a preference.**
   `d6-run11/iter-019` carries no `pay_` params, and the server gates
   the payment tag on their presence (`has_pay`, server.py — the
   never-serve-fresh-init rule); iteration 0 serves `--ckpt` directly,
   so an ungrafted launch bridges ZERO payment windows at iter-0 (no
   live iter-0 baseline, no `pay_class` examples in the first ingest,
   the head appearing only from iter-1). Pre-launch step: build
   `d4-init` = iter-019 through `build_net` + `load_compat` + save —
   byte-equivalent to the in-memory state the day-zero drill scores
   were banked on (positive 2/64, auto-correct 196/214, deviation
   8.6%), so those baselines carry over unchanged. Critic needs no
   graft.
2. **`pay_` params get their own optimizer group at lr 1e-3; trunk
   stays 1e-5.** Measured basis (not a preference): the loop takes one
   optimizer step per `--traj-per-step` (4) trajectories — run17 ran
   ~1,668 traj/iter = **~417 optimizer steps/iteration, ~3,300 over 8
   iterations**. Adam displaces ≈lr/step under coherent sign, so at
   1e-5 the payment-specific params move **≤0.03 total across the
   whole run**: `pay_bias` would sit at its +2.0 init and
   `pay_kind_emb` (6×512, zero-init) would never reach the 0.08–0.26
   per-element scale every comparable embedding in the ckpt carries.
   The probe would then be measuring trunk/pointer re-purposing with
   the head pinned — a **false clean negative on a branch that retires
   the formulation.** At 1e-3 coherent signal traverses the bias's
   meaningful range in ~half the run while pure noise random-walks
   only lr·sqrt(n) ≈ 0.06 across it. Over-shoot is already covered by
   the pinned gate: a too-hot head shows as the auto-correct guardrail
   breaking (<182/214) plus the casts-floor guard — detected, not
   silently confounding. `--wd` stays 0.0 (verified default; nonzero
   would passively erode the +2.0 bias every step regardless of
   gradient).
3. **NO lr sweep.** Three arms read against one pre-registered
   threshold is the ADR-0058 counted-once trap in new costume, and it
   triples a probe priced on being cheap. Bought instead with
   instrumentation (pin 6): a negative must separate "the head moved
   and it didn't help" (retires the formulation) from "the head never
   moved" (routes to dose).
4. **8 iterations × 480 games**, gate readable at any accepted
   iteration (drill scoring is offline and ckpt-independent, so extra
   iterations cost only wall-clock). Measured budget from run17
   checkpoint mtimes: clean iterations 29–38 min wall-clock (`gen_s`
   ~1,000–1,350s dominates; `train_s` ~230s; campaign overlapped
   generation, so dropping it saves less than its 400s suggests) —
   **~30 min/iter, ~4–4.5h for 8.** An evening, not an overnight;
   headroom exists to widen games/iter if iter-0/1 telemetry reads
   starved.
5. **No drill campaign** (`--drill-selection` off). The standing asset
   `drill-selection-m8-critic` is pre-boundary-era AND
   payment-agnostic; regenerating standard curation costs a night and
   tests curation, not payment. Named escalation if iter-0/1 deviation
   telemetry reads starved: **payment-targeted forks** — the miner
   already emits `{g, seed, t}` candidates that map onto the
   `selection.jsonl` schema, so forking at consequential payment turns
   would put K=8 dense credit exactly where the head fires. Recorded
   consequence if taken: D4 then measures payment head *plus* payment
   curriculum, and the attribution line moves accordingly.
6. **Failure telemetry added, priced by NOTHING.** The serve path
   already records `exec` (`directed_ok` / `directed_salvage` /
   `directed_fail`) and `float_residue` per window
   (PlayerControllerAnvil), but the loop aggregator counts only
   `pay_windows`/`pay_deviate` — the payment head's analogue of the
   veto channel is invisible in-loop. Add exec-code + residue counters
   to the monitor row and battery series, plus the pin-3 head-movement
   series (`pay_bias` value, `pay_kind_emb` RMS per iteration).
   **No §6c-style pricing:** deterrence-family pricing is CLOSED at
   ADR-0062 and a priced failure would confound the probe. Failure
   spikes are anomaly-set entries, not guards (restating the rung-3
   deviation-tripwire pin).
7. **Drill scoring folds into the loop.** `payment_drill_score.py
   score` runs post-iteration (offline featurize+argmax over ~290
   banked observe frames, ~minutes) so the gate is readable live in
   `analysis.md` rather than at post-mortem.
8. **Arms and evalset-v4 drill-eval DROPPED for the probe.** D4 makes
   no strength claim, fixed-subset arms carry the ADR-0058
   counted-once trap, evalset-v4 is pre-boundary-era; both return at
   D5. This is also where the wall-clock for pin 4's extra iterations
   comes from.
9. **Guards unchanged** (kl 0.06 / ent-floor 0.08 / veto-mult 1.5 /
   casts-floor 0.8). Recorded reading: the veto guard is a CEILING and
   M9 predicts vetoes fall, so it should not bind; **`casts-floor 0.8`
   is the one that could halt the run on the very mechanism the probe
   exists to observe** — if it fires, that is a read, not just a halt.
10. **Veto-collapse baseline re-derived IN-ERA from existing data —
    DONE at the recipe session, and it TRANSFERS.** The D1 baseline
    (0.0588 sampled / 0.0435 argmax) is pre-boundary; D4's trajectory
    is post-boundary, so the mechanism read would otherwise compare
    across the era boundary. Free fix taken: `m9-rebaselinearm-s0/s1`
    were already on disk with `obs_schema: 2` + census + argmax play
    over 1,999 games — exactly `veto_knowability.py`'s inputs, no new
    games. **Result (`data/runs/veto-knowability-m9-postboundary`,
    instrument v2): knowable 0.5064 CI95 [0.4937, 0.5190] — gate PASS,
    validity bar 0.9934 (vs the pre-boundary 0.986–0.991 band);
    knowable-veto rate 3,024 / 69,977 first-attempt windows =
    **0.0432 CI95 [0.0417, 0.0447]** vs the pre-boundary 0.0435 (the
    same formula recomputes the pre-boundary store at 0.0435 exactly,
    so the two are comparable by construction).** The boundary did not
    move the veto channel: **the argmax collapse baseline for D4/D5 is
    0.0432 in-era**, and the pre-boundary reading stands confirmed
    rather than superseded. The sampled baseline still comes from D4's
    own iter-0 (no argmax/sampled conflation — the ADR-0063 lesson).
11. **Seed hygiene:** fresh seed base, `run.json` grepped for
    collisions (standing M8 rule). Recorded scope note: the
    re-baseline's 7.15pp seed-half anomaly binds fresh-seed
    confirmation for near-gate *strength* reads only — it does not
    touch drill reads, so it applies at D5, not here.
12. **Midpoint re-mine logistics** (the pin-5 forced-family
    obligation): midpoint = the first accepted iteration at or past
    iteration 4; hb-signet self-pair generation runs in a gap, never
    concurrent with training (GPU contention); certification gets its
    own night through the standing harness.

### D4 RESULT — `d6-run18`, 2026-08-21/22 (read session owes the ADR)

8 iterations x 480 games, all accepted, zero guard halts, ~20 min/iter
(3h wall-clock — no campaign, no arms). Recipe exactly as pinned above.

**The gate read: DISCUSS ZONE. Neither branch fired.**

| iter | argmax deviation (drill windows) | positive | auto-correct |
| --- | --- | --- | --- |
| day-zero | 0.0863 | 2/64 | 196/214 |
| 0 | 0.1223 | 4/64 | 190/214 |
| 1 | 0.1295 | 4/64 | 188/214 |
| 2 | 0.0791 | 1/64 | 198/214 |
| 3 | 0.0612 | 1/64 | 201/214 |
| 4 | 0.0576 | 1/64 | 202/214 |
| 5 | **0.0288** | 1/64 | 207/214 |
| 6 | 0.0324 | 0/64 | 206/214 |
| 7 | 0.0396 | 1/64 | 206/214 |

- **FUND (>=7/64) never approached** — the maximum was 4/64, at
  iterations 0-1, and it decayed from there.
- **CLEAN NEGATIVE not satisfied either:** its positive half holds
  everywhere (never above 4/64), but the deviation half requires
  argmax deviation **< 2%** and the series bottomed at 0.0288 and
  settled at 0.0396. The head did NOT collapse to always-auto.

**What the run measured (the substantive finding).** The head deviated
MORE than day-zero for two iterations (0.0863 -> 0.1295) with positive
at its 4/64 maximum, then retreated monotonically while auto-correct
climbed to 0.967 — well above its 0.916 baseline. Read together:
**straight RL taught the head the MARGINAL statistic ("auto is usually
right") rather than the CONDITIONAL discrimination ("here is where auto
is wrong").** It learned to stop deviating where auto wins, and lost the
deviations where deviating wins along with them.

This is corroborated by an already-banked measurement rather than
inferred: the certify-time margin distribution put over-threshold mass
mostly NEGATIVE (directed deviations usually lose to auto in real play —
the D3 sparse-consequential premise, measured at rung 3). Straight RL
over trajectory returns finds exactly that gradient; the evalset's
positive drills are by construction the rare exceptions it cannot feel.
**The indicated layer is signal density / credit, not representation** —
the same layer M6 landed on ([ADR-0049](../decisions/ADR-0049-flat-cycle-audit.md))
and the same account ADR-0062 gave for vetoes.

**The head moved — this is not a dose failure.** `pay_kind_emb` rms grew
monotonically 0 -> 0.0337 across the run while `pay_bias` oscillated in a
narrow band around its +2.0 init (min 1.9882, max 2.0065). The pin-2
instrumentation did the job it was added for: "moved and did not help" is
distinguishable from "never moved", and this run is the former. Pin 2 is
also now measured rather than argued — the loop produced 676
trajectories/iteration = **169 optimizer steps**, well under the 417
estimated from run17 (no campaign), so at trunk lr the head would have
displaced <=0.014 across the whole run; it reached 0.0096 in ONE
iteration at 1e-3.

**Live-window telemetry (pin 6, all healthy):** 5,383 consequential
windows in 480 games (11.2/g); sampled deviation 0.0659 at iter-0 (the
run's own live baseline) tracking 0.0616-0.0936 and ending 0.0439;
**directed_fail 0.0028 and salvage 0.0028 of deviations** — the executor
is as faithful in live play as at certification scale; residue 0.056 ->
0.077 of deviations leave floating mana (the one number worth carrying
forward as an over-tapping tell). Guards clean all 8 iterations;
tripwire 2/1/0 per iteration, at the historical base rate (run12 hit 3
in one iteration) and never the O(1) magnitude that indicates real skew.

**Battery (exploratory per protocol):** behavioral delta 14.5% of the
init's cast decisions changed, 75% cast->pass (the ADR-0049
cast-suppression axis); hold-then-cast MOVED 0.237 -> 0.266 (>3se) —
TOWARD the heuristic's 0.345, opposite to run16's 0.233 -> 0.182. A
recorded confound for the drill read: some argmax movement on drill
windows is trunk drift, not head learning.

**Owed at the read session:** the ADR (done-when 4, either direction —
here the discuss-zone adjudication), the routing decision (formulation
variant = the Option B dedicated-embedding head, vs a density/credit
attack on the same surface, vs holding the payment surface as
infrastructure and going to the §3a second act), and the pin-12 forced
family re-mine, which was deferred to post-run rather than run at the
midpoint (GPU contention) and is now due against the run's own stores.

### D4 READ — the adjudication (2026-08-22, [ADR-0069](../decisions/ADR-0069-d4-read-adjudication.md))

**D4 RESOLVED, NEGATIVE.** Done-when 4 satisfied. The RESULT block above
reproduces exactly from the raw stores; the read added three things.

1. **The negative is a selectivity measurement, not a reading of curves.**
   Argmax deviation split by drill kind: P(dev | positive) vs
   P(dev | auto-correct) = 1.11 / 1.39 / 1.29 / 1.25 / 1.03 / 1.11 / 0.48 /
   0.42 / 1.25 across dz–i7, 2-prop z never above +0.94, **pooled i0–i7
   z = +0.75.** The head never acquired ANY discrimination between the two
   populations. Corroborated: the positive-family deviation sets NEST
   (jaccard 1.00 at equal size for i1-vs-i0 and i4-vs-i3; i2/i3 strict
   subsets — pruned, never promoted) and precision-on-deviation is flat at
   chance (13/39 = 33.3%). Training moved one global threshold down and
   left the ordering untouched.

2. **42% of the gate denominator could never move, and the threshold
   encoded an unpriced precision assumption.** phyrexian (13) and
   wide_choice (14) positives are 0-correct at every scored point
   INCLUDING day-zero — 27 of 64 drills; the gate was contested on 37, and
   the whole signal is color_hold plus one blocker_pressure drill at
   i0/i1. Half the auto-correct climb is phyrexian (25/32 → 31/32) — the
   family whose positives are permanently 0/13. At 33% precision, ≥ 7/64
   needs ~21/64 positive deviations against an 11.7% auto-deviation
   guardrail = **~2.8× selectivity, vs a measured max of 1.39.** FUND was
   outside the channel's dynamic range by 2×.

3. **Pre-registered signal 2 was never read. The read took it, then killed
   it as evidence.** ADR-0063 v2 instrument on run18's own stores, four
   iterations, no new games: kvr **0.0635 → 0.0621 → 0.0481 → 0.0425**
   (−33%, CIs separated, validity 0.9885–0.9902), raw veto slope
   −0.00762/iter at t = −7.55, the steepest in the ledger. Two checks kill
   the attribution: (a) the ledger splits perfectly by campaign status —
   every drill-fed run flat-to-rising (run11/13/16/17), every drill-free
   run flat-to-falling (run7b −0.0044, run8 +0.0003, run9 −0.0059 at
   t = −4.20) — and D4's recipe pinned `drill_selection: None`; (b) the
   decline has no affordability signature — `knowable:timing`, which §3c
   cannot touch, fell −51.6%, more than colors_short (−24.6%) or
   generic_short (−35.4%). **ADR-0062's collapse prediction is UNTESTED;
   D4's recipe made it untestable.** One category worsened:
   `not_knowable:autopayer_xcost` +138% (17 → 38). Free confirmation:
   ADR-0063's knowability premise holds in-era under sampled play at all
   four points (0.519–0.606).

**Routing recommendation (ADR-0069 §4, pending the user's call):** hold the
payment surface as infrastructure and take the §3a second act (D6, which
inherits the promotion slot), with ONE 3h control run first — run18's
recipe with run17's drill campaign restored, §3c on — as the experiment
that actually reads signal 2, under the condition that halted run16 at
iteration 16 and run17 at iteration 11. Option B (dedicated-embedding
`pay_kind` head) argued NOT indicated: it re-parameterizes a knob whose
problem is absent conditional signal. **run18's 8 clean iterations do NOT
establish runaway prevention** — run16/run17 were also quiet through
iteration 9.

**Still owed:** the pin-12 forced-family re-mine against d6-run18's own
stores, and evalset repair (phy/wc positives unreachable as constructed)
before those 27 drills enter another denominator.

### D4 CONTROL — `d6-run19`, 2026-08-23 ([ADR-0072](../decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md))

The experiment ADR-0069 specified: run18 verbatim + a drill campaign, §3c on,
nothing else changed. 12×480 planned, **GUARD HALT at iteration 10**
(`veto_rate 0.3074 > 1.5× iter-0 (0.2029)`), 10 accepted.

Campaign restored in-era, not literally: run17's selection is not replayable
post-boundary (`_drill_phase` re-simulates from seed on the current jar), and
the free in-era stock was gate-poisoned (`m9-rebaselinearm` runs at
`final_read.py`'s default `seed_base 20260710`). Fresh stock via
`cycle_stock.py` (1,999 games, 420 addressable) → `critic_select.py` → **320
entries, run17's size**, ahead 0.1875.

**ADR-0062's prediction fails on both halves.**

| run | campaign | §3c | halt | slope i0–i7 | t | kvr i0→i7 |
| --- | --- | --- | --- | --- | --- | --- |
| run17 | Y | off | i11 | +0.00097 | +0.41 | flat |
| run18 | N | on | none | −0.00762 | −7.55 | −33% |
| **run19** | **Y** | **on** | **i10** | **−0.00008** | **−0.02** | **−3.7%** |

No collapse (kvr CIs overlap; slope inside the drill-fed band ⇒ run18's
decline was the missing campaign). Taxonomy repeats the inverted signature —
`knowable:timing`, untouchable by §3c, −61.6%, hardest of any category, while
`generic_short` ROSE +6.6%. No stability dividend — halted one iteration
EARLIER than the §3c-off run17, at a higher threshold. Capability negative
replicated at 2× head dose (selectivity 1.19, z = +1.13).

**The finding that outranks the run:** `payment_certify.py` scores a
`HORIZON = 2` board/tempo proxy, not game outcomes. The 69 certified positives
establish a better board two turns later; **the winrate value of perfect
payment play has never been measured**, and two training runs were spent
against a ±1.1pp gate without it.

**NEXT — the gating measurement, before any further §3c design: run the 69
certified drills to GAME END** instead of the 2-turn horizon (69×K, existing
machinery). Survives ⇒ the value is realizable and the model merely cannot
find those windows (supervised conditional signal, ADR-0015 machinery parked
since M2); evaporates ⇒ downstream squandering (the influence-surface
hypothesis, localized) or a non-predictive proxy; never there ⇒ payment is not
a strength lever at gate resolution and the surface is infrastructure
permanently.

### The ceiling measurement — pins (PINNED 2026-08-24, pre-launch)

**RESOLVED same day
([ADR-0073](../decisions/ADR-0073-m9-ceiling-measurement.md), run
`data/census/run-20260824-ceiling`): the proxy CONVERTS where it holds —
recert-subset Δ = +12.5pp/window (z = +3.74), Spearman +0.465, branch (c)
"never there" KILLED — and the aggregate ceiling is SUB-GATE on every
measured bound (+0.52 to +0.73pp/game vs the ±1.1pp floor). The recert
guard fired (44.6% < 70%) and was adjudicated as winner's-curse
mis-calibration, not era drift (12/65 sign-flips; margin>0 set converts
+6.6pp z=+2.70). Routing user-adjudicated: payment = infrastructure, D6
takes the promotion slot; supervised-conditional-signal = named M10
candidate contingent on the window-rate bound (exhaustive sweep priced
~one night, scheduling deferred by name to the D6 design session /
closeout). Evalset-repair inputs now empirical: phyrexian value-free at
game end (Δ = 0.0 exactly); wide_choice +7.5pp — repair is reachability,
not existence.**

**Window-rate sweep (funded at the D6 design session 2026-08-24, user;
pins PINNED pre-launch):** fresh in-era 500-game paytelemetry census
(bundle jar, seed base 20500000, paygoals2's deck pairs) → miner tags the
universe → **uniform sample of 600 tagged windows (rng 20260824)** → h2
certification (standing instrument, unchanged thresholds) → rate read.
**Primary (pinned): certifiable-positive rate with Wilson 95 CI ×
tagged-windows/game × the ADR-0073 conversions (+4.62 central / +12.5
upper) vs the ±1.1pp gate floor. M10 candidacy for the
supervised-conditional-signal attack STANDS iff the upper-bound
arithmetic's CI reaches the floor; falls otherwise.** Recorded frame
assumption: untagged consequential windows are outside the universe (no
predicate exists to certify them) — the rate is "certifiable by the
standing taxonomy," a lower bound on broader payment value. Why the sweep
can move the answer: only the top-ranked ~20% of the ~5,400-window tagged
universe was ever adjudicated, and miner rank is measured non-predictive
(paygoals3 read) — the mined 0.112/g could be several× low.

**RESOLVED same night (`rate-read.json`, ADR owed after the stage-2
conversion read): certifiable rate 19/600 = 3.17% [2.04, 4.89] Wilson 95
over a 10.15 windows/game tagged universe ⇒ 0.321 [0.207, 0.497]
certifiable windows/game — ~3× the mined bound. Perfect-play arithmetic:
central (+4.62pp/window) = +1.49pp/game [+0.96, +2.29], REACHES the
floor; upper (+12.5pp) = +4.02pp/game [+2.58, +6.21], CI entirely above
the floor ⇒ per the pinned rule, M10 CANDIDACY STANDS.** Executor
faithful at scale a third time (salvage 0.0000 / 15,128 directed rows).
**Stage 2 RESOLVED same night
([ADR-0075](../decisions/ADR-0075-window-rate-sweep.md)): direct
conversion on the uniform population +9.21pp/window ± 4.26 (z = +2.16),
19/19 faithful, recert 100% (fresh certifications don't regress —
corroborating ADR-0073's winner's-curse adjudication) ⇒ completed
arithmetic 0.321 × 9.21 ≈ +2.96pp/game, ~2.7× the gate floor,
mid-bracket of the borrowed +1.49/+4.02. M10 CANDIDACY STANDS; the
closeout routes the payment queue against a live candidate with a
measured ≈ +3pp/game ceiling.**

**Instrument (zero Java delta — `CensusRun -certify`'s `HorizonStop` already
stops at `t + horizon` OR natural game end, and rows carry `winner`/`ended`):**
two job sets over the 69 evalset-of-record positives, identical except
`horizon` — one at the certification horizon 2 (the in-era re-certification
arm) and one at horizon 999 (game end). Jobs reuse the **revalidation job ids
and seeds** (`run-20260821-revalidation/score-dayzero-iter019-v2.jsonl`), so
`rollSeed = f(seed, job, roll)` is identical across the two sets: each
(job, arm, roll) pair is the SAME determinized trajectory truncated at two
different points — the 2-turn proxy score and the game-end outcome are read
off the same game. k = 8 (the certification pairing), all arms (the non-best
arms are the free proxy-predictiveness scatter), bundle jar `2f87180cdf`.

1. **Denominator (pre-registered):** drills whose best arm executes
   `directed_ok` on ≥ 6 of 8 paired rolls in BOTH sets, arm-0 baseline
   fired, both end-rows `ended` (clock/crash rolls excluded, counted).
   Revalidation predicts ~64/69; a refire count < 55 ⇒ the read is
   QUALIFIED as instrument drift and adjudicated at a session before
   routing.
2. **Primary read:** pooled per-drill mean paired game-end win-diff Δ =
   win(best) − win(auto), win ∈ {1, 0.5 draw, 0}, equal drill weight,
   SE clustered by drill (the drill is the sampling unit; counted once).
3. **Branches (routing per ADR-0072 decision 6):**
   - **SURVIVES:** Δ ≥ +5pp AND z ≥ 2 ⇒ per-window payment value is
     realizable under heuristic continuation; the §3c program's next
     design target is FINDING the windows (supervised conditional
     signal, ADR-0015 machinery) — priced at M10 scoping, not auto-funded.
   - **DOES NOT CONVERT:** Δ < +5pp or z < 2, with in-era
     re-certification holding (≥ 70% of denominator drills still clear
     their shape margin at horizon 2 in-era) ⇒ the ADR-0072 (b)/(c)
     family: the 2-turn proxy advantage is not worth the gate's noise
     floor at game end under heuristic play; **payment surface =
     infrastructure permanently**, the payment-completion queue items
     re-route accordingly at the closeout. The Spearman secondary
     localizes (b) vs (c) for the record only — both route the same.
   - **INSTRUMENT DRIFTED (guard, not a branch):** in-era
     re-certification < 70% ⇒ the era moved under the evalset; no
     routing claim; session adjudicates.
4. **Secondaries (exploratory, never routing):** per-shape split (the
   phy/wc defect diagnostic — doubles as the owed evalset-repair
   read); Spearman(in-era 2-turn margin, win-diff) at drill level and
   across all directed arms; gate-scale arithmetic — Δ × the mined
   certified-window rate (56 mined positives / 500 games / seat as the
   stated lower bound, b4 hand-built excluded) vs the ±1.1pp gate floor.
5. **What this does NOT measure (recorded):** squandering by the
   *model's* downstream play — continuation is heuristic in both arms.
   A null here says the advantage does not convert under the engine's
   own play; it cannot separate that from model-specific squandering.

## D5 — the full run + the standing gate

One training run, run-recipe design pinned at its own session (init,
seed hygiene per the M8 lesson — grep run.json for seed-base
collisions; evalset drill-eval cadence; guard set; watchd/tripline
coverage per the detached-launch checklist). Close = the standing
2,000-game combined paired read vs the post-boundary re-baselined
ckpt-of-record number (the M9 gate number is re-pinned at the
boundary; 0.5373 ± 0.0112 is the pre-boundary reference) + evalset
decomposition + battery + the three M9-specific attributions:

1. **Strength:** the paired read, standard rules (fresh-seed
   confirmation as marginal-t tiebreaker; arms reads counted once).
2. **Mechanism:** knowable-veto collapse vs the D1 baseline —
   including the argmax-vs-sampled split (run17's elevation was
   substantially exploration-side; the prediction is about the policy,
   not the sampler). Falsification is a first-class outcome.
3. **Throughput dividend (efficiency rider, instrumented not
   anecdotal):** vetoes are wasted bridge round-trips + re-asks;
   generation rate is read before/after at identical chunking (the
   ADR-0033 cross-era rule).

## D6 — second act: the §3a turn-plan latent (tier 2)

**PROBE RESOLVED 2026-08-25
([ADR-0076](../decisions/ADR-0076-d6-probe-read.md), `d6-run20`):
mechanism VALIDATED (consumed in one iteration, FUND's letter met at
accepted i1), v1's order-free target amplifies interface probing at
compounding speed (veto 0.18→0.28→0.38) — no v1 promotion run; v2
(sequencing + resources) routed; done-when 5 = an open closeout
decision (v2-within-M9 vs close-and-carry to M10's unified
resource-scheduling competency).**

**Design session HELD 2026-08-24
([m9-d6-plan-latent-spec.md](m9-d6-plan-latent-spec.md), user-approved
forks): detached carry + dense aux supervision (emit once per turn at the
first own-seat window, carry per (seat, turn), no BPTT); aux target
decided by the R1 offline probe (action-summary vs end-of-turn delta,
ADR-0043 margin discipline; forced-seq labels = the escalation, where the
ADR-0058 chartered natural-timing formulation is routed); escape argument
+ pre-registered kill signal pinned per ADR-0073 decision 3; ADR-0053
accepted as the ceiling evidence. Sequencing: R1 probe → build/graft →
D4-shape probe run vs the kill signal → full run vs 0.5279 ± 0.0110 only
if funded.**

Pure model-side (the conditioning-token slot is reserved in the
schema; no fork delta): at turn start and on regaining priority, the
network emits a plan embedding conditioning all within-turn decoding;
end-to-end trained. Own design session (loss/architecture pinned
there), own attribution read against the then-standing gate — never
bundled into D5's read (run-level attribution discipline). Sequenced
after the payment verdict; the D5 run itself may overlap D6 design
work on the bench.

If the D4 negative branch fired, D6 is the milestone's promotion
attempt and inherits the full-run slot.

## The payment-completion queue (deferred, NOT dropped)

*(Added 2026-08-19 at the D3 opening session, user direction: the D3
scope pins leave the payment system deliberately incomplete, and these
remainders must stay top-of-mind until done — not dissolve into the
ledger. Standing rule for this queue: **every M9-deferred payment item
is routed BY NAME at the M10 scoping session and in the M9 closeout
ADR — scheduled, or re-deferred with a recorded reason. Silent loss is
not an outcome.** M10 may still rank something above them — §3b stops
is the named candidate — but outranking is an explicit decision the
scoping session records, item by item.)*

In priority order:

1. **Directed-payment executor completion** — **RESOLVED AS MOOT
   2026-08-19 ([ADR-0065](../decisions/ADR-0065-d3-engine-capability-audit.md)):
   the rung-1 audit landed on the YES branch; the capability exists
   today (float-then-apply over the existing execution primitive,
   chained activation included, 4/4 empirical probe).** The queue's
   live items are 2 and 3 below.
2. **Cost-composition cousins** (convoke / improvise / delve /
   `payCombatCost`) — same residual-commitment decision genre, wire
   shape (`SELECT_K`) already exists, class abstraction written
   graftable; the deferred cost is model-side only, so this is the
   cheapest completion on the queue. ~28/g where live (pool-dependent).
3. **Resolution-effect payments** (`payManaCost` `effect=true`,
   ~54/g) — a different decision genre (pay-or-suffer during
   resolution, often opponent's turn; whether-to-pay confirm is a
   separate callback), so it needs its own probe-then-build round per
   the §3c template, not a bolt-on. Largest deferred traffic slice.
4. **Costmod detector refinement — per-spell applicability** *(added
   2026-08-20 at the paygoals2 baseline read)*: the §12b static prong
   is presence-scoped (any ReduceCost static in play flags every
   window for that player) and absorbed **25.48% of in-scope traffic**
   with a measured leak of ZERO — conservative-correct for v1 but
   inflated; per-spell applicability (CostAdjustment `checkRequirement`
   logic) would return most of that surface to the model. Cheapest
   item after #2; pairs naturally with the cousins work since both
   touch `CostAdjustment`.
5. **Pool-tie enumerator residual — the lex-hidden `min_life` plan**
   *(added 2026-08-21 at the D4 gate session; re-typed from drill
   candidate at the certify4 read)*: on pool-tie boards the
   life-payment plan hides behind the spread-then-lex tie-break, so
   the option never surfaces and has no arm to certify — a narrow
   perceptual hole, fork-test genre. Fix + regression test land on
   the next payment-family touch (pairs with items 2/4), **never
   mid-era** — enumeration changes de-sync the certification jar
   from the training jar (the gate-session decision 3 rationale).

Ledger cross-reference: items 1a and 4 in the anvil-design-v2 §3d′
coverage ledger point here; this queue is the scheduling view, the
ledger is the capability view.

## Explicitly out of M9

- **Payment-system remainders** (directed-executor completion,
  cost-composition cousins, resolution-effect payments): out of M9 by
  the D3 scope pins, but governed by **the payment-completion queue
  above** — deferred not dropped, no-silent-loss routing at the M10
  scoping session and the closeout ADR.
- **Tier-3 pivotal-turn search:** the critic-leaf constraint is
  disqualifying — ADR-0061 measured 0.42 ordering on fresh-era
  positions vs the 0.94 K=8 ceiling; fine for curation, a real limit
  for search-leaf evaluation. Search unparks only behind a critic
  ordering improvement or a priced K-rollout-leaf design. Recorded so
  scope cannot creep into D6.
- **§3b learnable stops:** the biggest deferred episode-shrinkage
  lever (`autoPassCancel` is top-5 traffic) and philosophically part
  of the interface round — but a third decision surface in one
  milestone would wreck attribution. **Named the M10 candidate.**
- **Deterrence-family anything** (auto-scaling λ, pricing variants):
  CLOSED at ADR-0062. §6c pricing stays at the standing corrected
  0.01/window wherever the recipe carries it.
- BC-imitation of `ComputerUtilMana` payment choices (dropped at
  design, above).
- **Combo-enabler valuation (Utopia Sprawl triggers, Earthcraft untap
  chains, going infinite):** user direction 2026-08-19 — M9 owes these
  the *perception floor* only (rules text in embeddings ✓, attachments
  in obs ✓, choice-state = the boundary rider above; Earthcraft-style
  activations are already expressible through the SA interface today).
  Valuation is NOT hand-held via interface classes — it arrives later
  as targeted Grindstone drill families once the perception floor is
  proven (D2a genre: probe first, teach second). Named post-M9 drill
  candidate; Earthcraft/Sprawl/Wild Growth/Arbor Elf are all in pool
  `cf2ca6ba` (Squirrel Nest is not — no in-pool infinite-squirrels).
- Pool/content growth beyond what the boundary bundle's multi-format
  enablement itself lands.

## Done-when

1. D1 knowability decomposition resolved with an ADR; the veto-collapse
   baseline is on file.
2. D2a/D2b probe readings recorded (ADR), premises reconciled forward.
3. The boundary event lands as ONE bundle (rebase + §3c surface +
   store-namespace fix + multi-format + forensics; 2-arm trim landed
   or explicitly retired), with forkcheck certification, the
   re-baseline read, and the payment-evalset revalidation pass
   (observe lanes re-run on the bundle jar; drift exclusions counted;
   shape floors re-checked; day-zero scores re-banked — D4 gate
   session decision 4).
4. **RESOLVED (2026-08-22, [ADR-0069](../decisions/ADR-0069-d4-read-adjudication.md)):**
   D4 probe resolved against its pre-registered gate, either
   direction, with an ADR. Landed NEGATIVE, via the read session's
   adjudication of the discuss zone.
5. One full training run (D5 payment, or D6 plan-latent on the
   negative branch) closed by the standing 2,000-game combined paired
   read vs the post-boundary baseline.
6. The M9 closeout ADR records the strength verdict AND the mechanism
   verdict (veto collapse confirmed / falsified — falsification
   explicitly first-class; **RESOLVED 2026-08-23 by the ADR-0069 control
   run: the verdict is FALSIFIED — `d6-run19` restored the campaign and
   the collapse did not occur (kvr −3.7%, CIs overlapping) nor did the
   surface buy stability (guard halt at i10, one iteration earlier than
   the §3c-off run17). The closeout records a falsification, which
   ADR-0062 made explicitly first-class**), routes the second act or M10, **and routes
   every payment-completion-queue item by name** (scheduled, or
   re-deferred with a recorded reason — the queue's no-silent-loss
   rule).
