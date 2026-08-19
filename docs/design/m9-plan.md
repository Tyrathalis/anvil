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
- **Boundary discipline: ONE boundary event.** The §3c fork delta
  rides the queued next-boundary bundle (upstream rebase + multi-format
  model-side enablement + copy-state divergence forensics + the
  fork-index store-namespace fix from run17 iter-2), held until the
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
([ADR-0063](../decisions/ADR-0063-m9-d1-veto-knowability.md)): gate
PASS in all four populations — knowable 0.5347 sampled / 0.5029 argmax
/ 0.5282 stock / 0.5993 elevated (lower bounds; validity bar
0.986–0.993). The premise stands; collapse baseline = knowable-veto
rate 0.0583 sampled / 0.0429 argmax. The elevated population is MORE
knowable (generic_short 31%→49%) — the veto climb happened in the
knowable channel.**

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
  predictable):** wire the aux prediction target into a short training
  run (aux only — no action-space change, no fork delta) and read the
  veto trajectory against the D1 baseline. This is the *minimal*
  version of "payment-aware." If aux affordability alone collapses
  knowable vetoes, the theory's mechanism is confirmed before any Java
  is written — and the D5 strength question sharpens to "does payment
  *control* (not just awareness) move strength."

**Pre-registered gates (PIN AT DESIGN — D2 session):** D2a
accuracy/AUC threshold vs a public-features-only baseline **[PIN]**;
D2b veto-collapse margin on the knowable subset **[PIN]**. Neither
gate blocks D3 — the payment surface is funded on the ADR-0062
routing regardless — but both readings are recorded premises the
closeout ADR must reconcile: a D2b that already collapses vetoes
changes what D5's veto read can attribute.

All standing training rules apply from birth to D2b: clips/hinge at
birth (ADR-0056), auto-calibrated weights instrumented + guarded +
recalibrated at drift cadence (ADR-0057), share guard + kl abort,
fixed-subset arms reads counted once (ADR-0058).

## D3 — the §3c build: engine surface + payment sub-head + the drill evalset

Three rungs, strictly ordered:

1. **Engine capability audit (before any protocol work):** can the
   fork engine *execute* a directed payment it is handed — including
   chained-activation payments (`ComputerUtilMana` cannot construct
   these; can the engine perform them if told to)? If yes, enumeration
   is archaeology over the existing cost-payment machinery; if no,
   there is real engine work and the boundary bundle gets re-priced
   before commitment. The audit result is recorded either way.
2. **The fork delta (rides the boundary bundle):**
   - **Consequential-payment flag:** engine-side detection that a
     payment window has ≥2 payment classes with different residuals
     (colors held, snow, ability-relevant permanents, chained
     activation available). Non-consequential windows never bridge —
     `payManaCost` is ~120 calls/game and the 2.6% bridge tax survives
     only if the flag keeps the surface sparse. Telemetry ships with
     the flag: consequential-window rate per game (the surface's own
     census, read before the model side is trained).
   - **Payment-class collapse:** legality-derived enumeration (the
     requirement above), interchangeable payments collapsed into
     classes, decide over classes.
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

**Pre-registered gate (PIN AT DESIGN — D4 session, before launch):**
drill-accuracy movement **[PIN]** and/or deviation-rate floor
**[PIN]** ⇒ the full run is funded (D5). Flat drills + ~zero deviation
⇒ a clean negative on the formulation for a fraction of a run's cost;
the closeout records it and the checkpoint session routes (candidates:
formulation variant, or straight to the §3a second act with the
payment surface held as infrastructure).

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

## Explicitly out of M9

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
- Pool/content growth beyond what the boundary bundle's multi-format
  enablement itself lands.

## Done-when

1. D1 knowability decomposition resolved with an ADR; the veto-collapse
   baseline is on file.
2. D2a/D2b probe readings recorded (ADR), premises reconciled forward.
3. The boundary event lands as ONE bundle (rebase + §3c surface +
   store-namespace fix + multi-format + forensics; 2-arm trim landed
   or explicitly retired), with forkcheck certification and the
   re-baseline read.
4. D4 probe resolved against its pre-registered gate, either
   direction, with an ADR.
5. One full training run (D5 payment, or D6 plan-latent on the
   negative branch) closed by the standing 2,000-game combined paired
   read vs the post-boundary baseline.
6. The M9 closeout ADR records the strength verdict AND the mechanism
   verdict (veto collapse confirmed / falsified — falsification
   explicitly first-class), and routes the second act or M10.
