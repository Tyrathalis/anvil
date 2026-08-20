# M9 rung 3 DRAFT — payment drill evalset + sub-head design

**Status: DRAFT for review (written overnight 2026-08-20; nothing here
is pinned).** Anchors: [m9-plan](m9-plan.md) D3 item 3 + D4;
[m9-payment-surface-spec §12](m9-payment-surface-spec.md) (the goal
surface + the final pre-D4 baseline `run-20260819-paygoals2`);
[ADR-0064](../decisions/ADR-0064-d2a-affordability-probe.md) (the
`[STATE]⊕cand` substrate finding rung 3 builds the head on).

Everything marked **[PIN]** is a decision for the rung-3 session, per
the PIN-AT-DESIGN rule. This draft proposes and gives one
recommendation each; it decides nothing.

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
