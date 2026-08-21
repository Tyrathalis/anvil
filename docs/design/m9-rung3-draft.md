# M9 rung 3 — payment drill evalset + sub-head design

**Status: PINNED (rung-3 design session, 2026-08-20; drafted overnight
same day).** Anchors: [m9-plan](m9-plan.md) D3 item 3 + D4;
[m9-payment-surface-spec §12](m9-payment-surface-spec.md) (the goal
surface + the final pre-D4 baseline `run-20260819-paygoals2`);
[ADR-0064](../decisions/ADR-0064-d2a-affordability-probe.md) (the
`[STATE]⊕cand` substrate finding rung 3 builds the head on).

**Session decisions (user-pinned):**
1. **Sub-head = Option A** — the standing pointer-decoder `SELECT_ONE`
   path; no new architecture; goal semantics read from label text; the
   dedicated-embedding head (Option B) is the recorded D4-negative
   fallback variant.
2. **Auto-bias init = +2.0** learned per-task scalar on option 0 —
   argmax stays auto at init (bit-identity where it matters), sampled
   play explores ~10–12%/consequential window (~2–3 legal payment
   deviations/game): D4-observable signal without unpinning day-zero
   safety. (+3.0 rejected as exploration-starving; the deviation
   tripwire idea folds into the battery anomaly set, not a guard.)
3. **Certification = per-shape predicates**, deterministic where the
   shape allows; paired K=8 rollouts at 2-turn horizon only where
   needed. **Drill accuracy (D4's readout) = argmax pick lands in the
   certified-best outcome-equivalence class.**
4. **Batch:** ~120-drill target with yield-driven split around the §2
   ranges; miner adopted as a standing script + tested; battery gains
   `pay_deviation` curves (sampled AND argmax from day one, the
   ADR-0063 lesson); **D4 gate values remain PIN-AT-DESIGN at the D4
   session** — set knowing the +2.0 bias and the certification yield.

Original [PIN] markers below are retained with their proposals for the
decision trail; the list above is authoritative where they differ.

**Build status + one recorded refinement (2026-08-20, same day):**
- **Sub-head BUILT and test-pinned** (Anvil `pay_class` task end-to-end:
  featurizer/collate/model/sampling/RL-gates/server tag gating;
  `tests/test_pay_class.py` 4/4 — day-zero argmax=auto holds ON the
  trained D5-era checkpoint, mu round-trip exact, load_compat keeps the
  +2.0/zero inits; fork `667564a97d` emits per-goal kind codes).
- **Refinement (recorded reason):** reconnaissance showed the pointer
  key carries NO label text (candidates score as entity-row ⊕
  sa-descriptor; `cand_sa` stays −1 by the sa_vocab pin), so pure
  Option A would distinguish options only by one representative tapped
  entity — and life/pool-only plans tap nothing. Added: a **zero-init
  `pay_kind` embedding** (6-code vocab, fork label field `"gk"`:
  pay / spare_creature / spare_land / spare_artifact / spare_other /
  min_life) folded into pay candidates' keys, entless options key on it
  alone. Zero-init ⇒ day-zero logits unchanged (the ent_proj zero-pad
  precedent); no new head — Option A's intent preserved. `pay_`
  param prefix allowlisted in `load_compat`; the server advertises the
  tag only when the ckpt carries pay_ params (`has_combat` precedent).
- **Certification harness BUILT and smoke-proven end-to-end (2026-08-20):**
  fork `28eac88c37` (`PayDirective` per-Game directive + `CensusRun
  -certify` with window-time reshuffle determinization, K paired across
  arms, roll 0 = true continuation, t+2 horizon stop; 17 fork tests
  green) + Anvil `payment_certify.py` (plan/lanes/read; lane-script
  provenance shim; per-shape paired predicates, k-roll consistency,
  **directed_ok-only certification** — salvaged arms are unverified by
  definition). Jobs contract: the fork parser takes exactly
  `JAVA_JOB_FIELDS`; lane job files strip provenance. **Smoke (8 jobs,
  105 rows): window fire rate 100%** — census replay determinism +
  the provenance shim PROVEN.
- **Salvage finding RESOLVED (2026-08-20,
  [ADR-0066](../decisions/ADR-0066-certify-salvage-host-exclusivity.md)):
  enumerator over-admission — the DFS tracked availability per CLASS,
  feasibility is per HOST CARD.** A dual's two mana abilities live in
  two classes that both pick the lowest-id copy first, so any
  two-color plan committed the same physical card twice
  (count-feasible; executor-infeasible at the second `canPlay`).
  Fixed fork-side (`37bde8051e`: `usedHosts` in the DFS + reason-coded
  salvage `exec_why` + dual-land regression test; suite 15/15).
  **Re-smoke: salvage 0.0000 on 64 directed rows [gate ok] —
  blocker_pressure 64/64 `directed_ok`; the forced family is GONE
  (jobs 0–5 enumerate zero options — all six "forced" windows were
  phantoms, the auto-payer was right to refuse).** Consequences: the
  §12c clean-forced claim is falsified for this census ("forced 6
  CLEAN" = 6 phantoms); the paygoals2 consequential read (15.99/g) is
  inflated one-sidedly by phantom options. **Routing: re-run the
  500-game paytelemetry census on the fixed jar → re-mine → re-plan
  the certification set; the existing 126-job plan is stale** (6 dead
  forced jobs + option-index misalignment wherever an option list
  shrank). The blocker_pressure 0/2 smoke certifications remain
  margin-below-threshold on true continuations — the k=8 full run
  answers whether that's noise or absent effects.

**Evalset-assembly session pins (2026-08-20, user-decided):**
1. **The 12-vs-120 gap closes by SCALING certification jobs, not by
   touching thresholds or the census.** Measured basis: threshold sweep
   to 1.0 yields only 12→16 (no mass under the bar — small true effects,
   as the run read said); certified ranks-within-shape are spread across
   the whole top-40 (bp 3/8/22, ch 26/36, wc 4/7/18/19/21/26/32) — miner
   rank does NOT predict certifiability, so deeper pool cuts yield flat;
   pool depth 1,496/3,895/1,964 per shape vs 40 used. **Batch 2 =
   `certify2`: 600 jobs (bp 240 / ch 240 / wc 120, banked 120 windows
   excluded), ~14.7k paired continuations, overnight on 4 lanes.**
   Expected at measured yields (7.5%/5%/17.5%): ~50 new positive drills
   → ~63 total.
2. **Auto-correct drills ADOPTED as a protocol change, scored as a
   SEPARATE metric.** Pinned reason: D4's failure modes are two-sided —
   never-deviates AND deviates-wrongly; a job where every cleared
   deviation consistently LOSES ≥ the same margin bar is
   engine-adjudicated evidence that auto is the certified-best class.
   Never blended into the headline accuracy: the +2.0 auto-bias init
   scores ~100% on these at day zero and would inflate/desensitize the
   readout. Reader emits `autocorrect-drills.jsonl` (batch 1: 29 —
   bp 14 / ch 14 / wc 1, margins to −20.3).
3. **Composition re-pinned yield-driven with a ~10-per-shape floor**
   (the §2 30–50-per-shape targets are unreachable at measured yields
   in one night; a floor miss triggers a top-up night, not a redesign).
4. Reader fix (measured harmless on batch 1, 0 jobs affected): best arm
   = best POSITIVE margin — a stronger negative arm no longer masks a
   cleared positive one. Batch-1 re-read bit-identical (12/120).
5. Still owed before D4: hand-built phyrexian drills (10–15, incl. the
   pool-tie board) + hand-built forced/Signet boards (ADR-0065), the
   D4 accuracy scorer over certified+autocorrect (per-kind accuracy),
   merge batches 1+2 into the evalset of record.

**Hand-built drill session (2026-08-21): mechanism = DRILL DECKS, not
constructed board states.** The design-§6.6 fallback reads
"hand-constructed **seeds**, same ddmin certification" — so the
hand-built unit is a deck/scenario, played in REAL census games on the
certification jar, with windows mined and certified through the
standing harness unchanged. Provenance-to-a-real-game holds by
construction; zero new machinery beyond a miner tag + one reader
predicate. Decisions:
1. **Two pool-only decks, both led by Najeela, the Blade-Blossom**
   (5-color identity dissolves the commander color-identity constraint
   entirely; pool-legal). Banked in `data/pool/decks/hb-{phy,signet}.dck`
   + installed to the Forge store (the `launch --pool` gate only
   verifies manifest decks — verified safe).
   - `hb-phy`: all 8 pool phyrexian-mana cards
     (`data/pool/phyrexian-cards-cf2ca6ba.txt`, pool-era-scoped scan) +
     12 any-color/pain lands + 25 basics + 14 cheap instants
     (hold-mana tension) + 40 cheap creatures.
   - `hb-signet`: 20 chain sources (Signet-class mana-cost-activated
     rocks incl. Boros Signet/Prismatic Lens/Springleaf Drum; all
     `AI:RemoveDeck:All` = in-deck auto-payer blanks per ADR-0065 —
     census decks are NOT stripped, verified) + 3 chain lands (incl.
     Arena of Glory, the ADR-0067 family) + only 28 lands total +
     36 double-pip 3–4-cmc spells → ¬auto-payable boards.
2. **Miner `phyrexian` tag** (`--phy-sa` card list; census rows carry
   no per-option labels so the join is by card name; fires only with
   ≥2 options — the min_life choice surfaced). Weight 50. Banked
   census scan: **10 natural consequential phyrexian windows in
   paygoals3** (Skrelv 8, Birthing Pod 2) — at measured yields ~0–2
   drills, confirming hand-built is needed for the 10–15 floor.
3. **Reader `phyrexian` predicate pinned:** score = life + dev +
   3·won (both sides of the mana-vs-life trade at full weight),
   MARGIN 2.0, K=8. Plan order: forced_chain → phyrexian → the rest.
4. Sizing is probe-first: 30-game self-pair probes (phy×phy,
   signet×signet) measure family window rates before the certify
   batch is planned.

**Probe results + the forced-family pin (2026-08-21, user-decided):**
- **Phyrexian: WORKS.** hb-phy self-pair = 1.00 consequential
  phyrexian windows/game (~50× the DC census 0.02/g; Skrelv/Pod/Gut
  Shot/Spellskite all firing). One deck fix en route: the alphabetical
  instant fill picked a PumpAll-class card that hit the AI's
  per-creature attack-simulation timeout — instants re-curated to
  single-target AI-simple picks (hb-phy v2). Generation run
  `run-20260821-handbuilt` (150 games, pair-*.jsonl + lane provenance
  via `run_dc_census.py --pair`, new flag): **113 phyrexian
  candidates mined → certify4 batch, all 113 jobs.**
- **Forced/Signet: the mining premise is FALSIFIED — structurally,
  not by luck.** 0 forced windows in 30 games on a signet-stuffed
  28-land deck: the forced flag fires only when a cast is ATTEMPTED,
  and the heuristic's cast decision consults the same auto-payer that
  cannot see the chain (the ADR-0065 blind spot upstream of the
  window). Heuristic play cannot reach forced windows with ANY deck;
  paygoals3's forced 0.0000 was the same fact. **Pin (user): the
  forced family DEFERS BY NAME to the D4 midpoint re-mine** — the
  model's own play (legality-derived CastPlan executor + exploration)
  walks into forced boards naturally; mine its stores, certify through
  the standing harness. The pre-run evalset ships without forced;
  ADR-0065's `DirectedPaymentAuditTest` (4/4) stays the engine-side
  proof; `pay_deviation` telemetry on forced windows is the live D4
  readout. The cast-directive alternative (directed attempts on
  board-structure-mined states) was declined as pre-D4 fork scope;
  revisit only if the D4 re-mine comes up empty. hb-signet.dck stays
  banked (a candidate D4-era drill deck under model play).

**certify4 read + final composition (2026-08-21, same session):**
13/113 certified (11.5%; margins 2.0–41.5; Birthing Pod 9 / Gut Shot 3 /
Spellskite 1) + 32 auto-correct; salvage 0.0000 on 2,944 directed rows.
**Evalset of record re-merged: 69 positive (bp 13 / ch 26 / phy 13 /
wc 17 — every shape ≥ the 10 floor) + 224 auto-correct** (b4 = the
hand-built batch; b3:202 stays retired). The §2 composition table is
CLOSED for the pre-D4 evalset with two recorded amendments: forced =
deferred to the D4 re-mine (above), and the §12a pool-tie board is
re-typed an enumerator residual (a lex-hidden plan has no arm to
certify — fork-test genre, routed to the D4 gate session), not a drill.

**D4 accuracy scorer BUILT (2026-08-21, same session):** fork certify
**OBSERVE mode** (`116476eebb`: `"mode":"observe"` jobs + `-obsout` —
replay to the window with census-identical construction, emit ONE
schema-v1 obs dec record carrying the EXACT serve-time option labels
(`PlayerControllerAnvil.paymentOptionLabels`, shared code path —
scorer/serve parity by construction), direct nothing, stop at horizon
0; payment suite 21/21) + `scripts/payment_drill_score.py`
(plan/lanes/score, 3 tests): observe jobs renumbered from the evalset
of record (obs store game idx = job id; batch job ids collide),
score = decode lane obs frames directly → standing `pay_class`
featurize → ckpt argmax → **per-(shape × kind) accuracy, positive and
auto-correct never blended**; loud exclusion classes (window miss;
`option_mismatch` = observe-time option count ≠ certify-time count,
the cross-era enumeration-drift guard — a shifted list makes the
banked best-arm index unaddressable). Known recorded skew: observe
frames carry an empty history ring (census games have no prior
bridged decisions); D4-era model play will carry real hist — the
census-mined-drill distribution caveat, not a scorer defect. First
read = day-zero calibration on the ckpt of record (expected: every
pick auto ⇒ positive 0%, auto-correct 100%).

## 1. What rung 3 owes (from the plan)

Two artifacts, both built BEFORE any run: the **payment drill evalset**
(engine-adjudicated, per-decision — the readout D4 needs because a
5-iteration run cannot read strength) and the **payment sub-head**
(decision over `{auto} ∪ goal-options`, auto-biased init, hard-masked,
riding the existing `selectOne` bridging point).

## 2. Drill evalset — proposed composition

**Mining state:** first-pass miner built and run
(`scripts/payment_drill_mine.py` over the baseline census; 5,849
provenance-traced candidates in
`data/census/run-20260819-paygoals2/drill-candidates.jsonl`):
forced_chain 6 · blocker_pressure 1,553 · color_hold 3,997 ·
wide_choice 2,464 (tags overlap). The miner is join-based ranking
only — candidacy ≠ drill. Untested first-pass instrument; adopt +
test at the session or discard **[PIN]**.

**Certification protocol (proposal):** for each candidate, exact
replay to the window (Grindstone machinery, drill provenance rule),
then paired K-rollout adjudication: play the window under goal-option
A vs `auto` (and vs each other surfaced option worth testing), roll
K seeds forward a bounded horizon, score short-horizon outcome
deltas (life swing / board delta / the drill's own success predicate).
A candidate is CERTIFIED as a drill iff some option beats `auto`
outside noise — "the choice provably flips the short-horizon outcome."
K, horizon, and the success predicate are **[PIN]** slots.

**Composition (proposal):**

| shape | source | target count [PIN] |
| --- | --- | --- |
| forced_chain | all 6 mined + hand-constructed Signet-family boards (ADR-0065 board + variants); ddmin certification for hand-built per standing rule | 15–25 |
| blocker_pressure (dork-as-blocker) | mined top-ranked, certified | 30–50 |
| color_hold (wrong-color-tap) | mined top-ranked, certified | 30–50 |
| wide_choice (coverage) | mined, certified, deduped by board archetype | 20–30 |
| phyrexian mana-vs-life | mined (`min_life` label present) + hand-built; include one pool-tie board (the known §12a residual — life plan hidden behind lex on pool ties) | 10–15 |

Era-scoping per standing rule: the evalset is ckpt-era-scoped and
regenerates from the ckpt-of-record's own play post-boundary; drill
mainlines never enter training ingest.

**Known gap to record:** census-mined candidates are heuristic-play
windows; the model's own consequential windows post-boundary may
distribute differently. Mitigation: re-mine from the D4 run's own
stores at its midpoint read (cheap, the miner is store-agnostic).

## 3. Payment sub-head — the design space

**Context:** the wire is already `selectOne(TAG_PAY_CLASS, labels)`
with `auto` = option 0 and goal labels carrying
`goals + ents/pool/phy`. The D2a finding (ADR-0064): the trunk's
`[STATE]⊕cand` substrate carries affordability signal (AUC 0.8809) —
the head should read state+candidate jointly, which the existing
pointer-decoder `SELECT_ONE` path already does.

**Option A (recommended): no new head — the standing SELECT_ONE path
+ auto-bias at the tag level.** The pointer decoder already scores
option labels against `[STATE]`; `mtg.pay_mana_class` becomes a
`pay_class` task the existing machinery handles (the `TAG_TASK`
reservation from the fallback-echo fix). Auto-biased init = a
per-task learned scalar added to option-0's logit, initialized
positive **[PIN: magnitude]** (candidate: +3.0 ≈ p(auto)≈0.95 on a
2-option window; decays only if RL pushes it). Zero architecture
change; the model reads goal semantics from the label text (goal
names + entity refs are in-vocabulary).

**Option B: dedicated goal-type embedding sub-head.** A small head
keyed on parsed goal type (spare-creature / spare-land / min_life /
…) + residual features. More inductive bias, faster early learning
in theory — but it duplicates what the label text already encodes,
adds a parse layer that must track the label format, and contradicts
the M6 lesson (representation was not the binding constraint;
signal density was). Hold as the D4-negative fallback variant, not
v1.

**Masking:** hard mask = options list length (the wire already
enforces 0..N; the head never scores absent options). Nothing to
build; assert in tests.

**Exploration/telemetry split (D4 readout hygiene):** deviation rate
must be read argmax-vs-sampled separately from day one (the ADR-0063
lesson — run17's veto elevation was exploration-side). The obs
window already records the pick; the battery needs a
`pay_deviation` curve (sampled) + an argmax re-scan **[PIN: battery
addition]**.

## 4. D4 gate slots this draft feeds (pin at the D4 session, values open)

- deviation-rate floor **[PIN]** — "the head leaves auto at all" (the
  cheap signal; ~zero deviation + flat drills = clean negative).
- drill-accuracy movement **[PIN]** — primary funding readout, on the
  §2 evalset.
- knowable-veto trajectory vs the ADR-0063 baseline (0.0588 sampled /
  0.0435 argmax) — mechanism preview, not a gate.

## 5. Boundary-bundle riders (restate, nothing new)

Obs schema version bump covers the payment window labels (now
goal-shaped); forkcheck certification; 2,000-game re-baseline;
era-scoping sweep. The §12 fork delta (`m9-payment-surface` through
`531dafdff4`) rides the ONE boundary event as designed.

## 6. Session agenda (proposed)

1. Adopt/adjust the certification protocol; pin K/horizon/predicate.
2. Pin composition counts; run certification on the mined top-N.
3. Choose Option A vs B; pin the auto-bias magnitude.
4. Pin the battery additions (pay_deviation curves).
5. Confirm the boundary-bundle rider list → bundle-readiness check.
