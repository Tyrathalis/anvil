# ADR-0069: M9 D4 — the read session adjudicates the discuss zone: NEGATIVE on the funding question (selectivity never left 1.0), and the veto-collapse signal is confounded, not read

- **Date:** 2026-08-22
- **Status:** accepted
- **Design-doc anchor:** [m9-plan.md](../design/m9-plan.md) D4 (gate
  pinned 2026-08-21 pre-data, run recipe pinned same day; done-when 4);
  [ADR-0062](ADR-0062-m8-closeout.md) (the veto-as-interface-artifact
  account whose falsifiable prediction D4 signal 2 was to read);
  [ADR-0063](ADR-0063-m9-d1-veto-knowability.md) (the knowable-veto
  baseline and instrument)

## Question

`d6-run18` landed between D4's two pre-registered branches: FUND
(≥ 7/64 positive-drill argmax accuracy) was never approached (max
4/64), and CLEAN NEGATIVE was not satisfied either — its positive half
held everywhere (never above 4/64) but its argmax-deviation half
required < 2% and the series bottomed at 0.0288 and settled at 0.0396.
The plan pinned that nothing auto-promotes from the discuss zone and
that the read session adjudicates. This ADR is that adjudication.

The read also owed a check the RESULT block did not perform:
**pre-registered signal 2 — the knowable-scoped veto trajectory, the
mechanism check's first reading — was never taken.**

## What the read added

The RESULT block's numbers reproduce exactly from the raw stores
(`data/training/d6-run18/{monitor.jsonl,iter-00*/pay-drills.jsonl}`
against `data/census/run-20260821-revalidation/score-dayzero-iter019-v2.jsonl`).
Three things go beyond it.

### 1. The negative is a selectivity measurement, not a reading of curves

The RESULT block infers "straight RL taught the MARGINAL statistic, not
the CONDITIONAL discrimination" from the shape of the accuracy curves.
That inference is correct and can be replaced by a direct measurement.
Split the argmax deviation rate (`pick != 0`) by drill kind — positive
drills are those where auto is wrong by construction, auto-correct
drills those where it is right:

| | dz | i0 | i1 | i2 | i3 | i4 | i5 | i6 | i7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P(dev \| positive) | .0938 | .1562 | .1562 | .0938 | .0625 | .0625 | .0156 | .0156 | .0469 |
| P(dev \| auto-correct) | .0841 | .1121 | .1215 | .0748 | .0607 | .0561 | .0327 | .0374 | .0374 |
| ratio | 1.11 | 1.39 | 1.29 | 1.25 | 1.03 | 1.11 | 0.48 | 0.42 | 1.25 |
| 2-prop z | +0.24 | +0.94 | +0.73 | +0.49 | +0.05 | +0.19 | −0.72 | −0.86 | +0.34 |

**At no iteration — and not pooled over the run (0.0762 vs 0.0666,
z = +0.75) — is the head's propensity to deviate on positive windows
distinguishable from its propensity on auto-correct windows.** The head
never acquired any discrimination between the two populations. Training
moved one global threshold down and left the ordering untouched.

Corroborated two ways, independent of the z-tests:

- **The deviation sets nest.** Jaccard against the previous iteration on
  the positive family: i1 vs i0 = 1.00 at equal size (10, same drills),
  i4 vs i3 = 1.00 at equal size (4, same drills), i2 and i3 are strict
  subsets. Deviations are pruned monotonically from a fixed candidate
  set; no window is ever promoted into it.
- **Precision-on-deviation is flat at chance.** 13 of 39 positive
  deviations across i0–i7 were correct (33.3%), against ~4–5 options per
  window. It does not improve at any point.

### 2. A third of the gate denominator could never move, and the threshold
encoded an unpriced precision assumption

Positive accuracy by shape (correct / n), day-zero through i7:

| shape | dz | i0 | i1 | i2 | i3 | i4 | i5 | i6 | i7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| blocker_pressure | 0/12 | 1/12 | 1/12 | 0/12 | 0/12 | 0/12 | 0/12 | 0/12 | 0/12 |
| color_hold | 2/25 | 3/25 | 3/25 | 1/25 | 1/25 | 1/25 | 1/25 | 0/25 | 1/25 |
| phyrexian | 0/13 | 0/13 | 0/13 | 0/13 | 0/13 | 0/13 | 0/13 | 0/13 | 0/13 |
| wide_choice | 0/14 | 0/14 | 0/14 | 0/14 | 0/14 | 0/14 | 0/14 | 0/14 | 0/14 |

**phyrexian (13) and wide_choice (14) are 0-correct at every scored
point including day-zero — 27 of the 64 positive drills, 42% of the
gate denominator, were dead weight.** The gate was contested on 37 live
drills, and the entire observed signal is color_hold plus one
blocker_pressure drill flickering at i0/i1. The "4/64 maximum" is two
drills above day-zero on a population whose binomial SE is ~1.4 drills.

The auto-correct climb the RESULT block reports (0.916 → 0.967) is half
phyrexian: 25/32 → 31/32, with a dip to 20/32 at i0/i1. **The family
where the head learned "always auto" best is the family whose positives
are permanently 0/13** — the marginal-vs-conditional finding localized
to one shape.

**Gate arithmetic in hindsight.** At the measured 33% precision-on-
deviation, ≥ 7/64 correct requires ~21/64 positive deviations (32.8%)
while the pinned auto-correct guardrail (≥ 189/214) caps auto-correct
deviation at 25/214 (11.7%) — **a selectivity ratio of ~2.8.** The run's
maximum was 1.39. FUND was not narrowly missed; it sat outside the
channel's demonstrated dynamic range by a factor of two, and nothing in
the gate session priced that because the threshold was posed on an
accuracy count rather than on a discrimination statistic.

### 3. Pre-registered signal 2 read for the first time — and it is confounded

Ran the ADR-0063 v2 instrument on `d6-run18`'s own stores at four
iterations (no new games; `data/runs/veto-knowability-d4read` and
`-d4read-mid`). kvr denominator per the ADR-0063 addendum-2 formula
(`first_veto + first_cast` from the same stores' census):

| | i000 | i002 | i005 | i007 |
| --- | --- | --- | --- | --- |
| n mana-relevant first-attempt | 2,282 | 2,276 | 1,922 | 1,487 |
| knowable fraction | 0.6056 | 0.5795 | 0.5187 | 0.5844 |
| **knowable-veto rate** | **0.0635** | 0.0621 | 0.0481 | **0.0425** |
| CI95 | [.0603,.0668] | | | [.0398,.0454] |
| first-veto rate | 0.1597 | 0.1501 | 0.1318 | 0.1176 |
| validity bar | 0.9890 | 0.9891 | 0.9902 | 0.9885 |

Monotone, −33% end to end, CIs cleanly separated, validity bar clean at
all four points. The raw veto slope over i0–i7 is −0.00762/iter
(t = −7.55), **the steepest in the run ledger.** Taken alone this reads
as ADR-0062's falsifiable prediction firing.

**It is not, and two checks kill it.**

- **Drill-free runs decline anyway.** Veto-rate slope over i0–i7 by
  campaign status:

  | run | drill campaign | i0 → i7 | slope/iter | t |
  | --- | --- | --- | --- | --- |
  | d6-run7b | none | .1567 → .1171 | −0.00435 | −1.24 |
  | d6-run8 | none | .1387 → .1314 | +0.00026 | +0.11 |
  | d6-run9 | none | .1365 → .1104 | −0.00594 | −4.20 |
  | d6-run11 | yes | .1242 → .1337 | +0.00073 | +0.44 |
  | d6-run13 | yes | .1972 → .1818 | −0.00295 | −0.50 |
  | d6-run16 | yes | .2024 → .2353 | +0.00355 | +0.95 |
  | d6-run17 | yes | .1950 → .1997 | +0.00097 | +0.41 |
  | **d6-run18** | **none** | .1997 → .1466 | **−0.00762** | **−7.55** |

  Every drill-fed run is flat-to-rising; every drill-free run is
  flat-to-falling. **D4's recipe pinned `drill_selection: None`.**
  run18's slope is the steepest of its family but sits inside it, not
  apart from it.

- **The decline carries no affordability signature.** Every taxonomy
  category fell 20–40% of denominator, and `knowable:timing` — which
  §3c cannot touch — fell **−51.6%**, more than `colors_short` (−24.6%)
  or `generic_short` (−35.4%). A targeted collapse of affordability
  probing would concentrate in the mana categories. This one does not.

One category moved the other way: **`not_knowable:autopayer_xcost` rose
+138%** (17 → 38, rate .00078 → .00186) against a −33% background — the
only category that worsened, on the cost family the goal enumerator
handles least well.

**Free confirmation:** the ADR-0063 knowability premise (≥ 0.50) holds
in-era under sampled play at all four points (0.519–0.606), the first
sampled in-era reading of it.

## Decision

1. **D4 adjudicates NEGATIVE on the funding question.** Straight RL
   through the §3c interface did not teach conditional payment
   discrimination. The finding of record is the selectivity measurement:
   P(deviate | positive) was never distinguishable from
   P(deviate | auto-correct), pooled z = +0.75, with monotone nesting of
   the deviation set and chance precision throughout. This is not a
   near-miss and does not warrant a dose or length escalation on the
   same formulation. The RESULT block's "moved and didn't help, not
   never moved" stands (`pay_kind_emb` rms 0 → 0.0337 monotone) and
   routes the negative to formulation/credit rather than dose.

2. **The CLEAN NEGATIVE branch is recorded as satisfied in substance and
   mis-operationalized in form.** Its deviation clause (< 2% argmax
   deviation) tested whether the head *collapses to a constant*, which
   is a stronger and different claim than whether the head *fails to
   discriminate*. A head that keeps a 4% undifferentiated deviation rate
   is exactly as negative as one that goes to 0%, and the pinned clause
   could not say so. The discuss zone was an artifact of that clause,
   not of the data.

3. **Signal 2 is NOT read as evidence, in either direction.** The
   ADR-0062 collapse prediction remains **untested**. D4's recipe made
   it untestable by removing the drill campaign — the condition under
   which the veto runaway occurs — in the same run that added the
   payment surface. The observed −33% kvr is consistent with the
   prediction and equally consistent with the campaign removal, and the
   taxonomy says the latter.

4. **Routing — RECOMMENDED, pending the user's call** (recorded here so
   the next session inherits the reasoning, not to pin it):
   - **Option B (dedicated-embedding `pay_kind` head) is NOT indicated.**
     It re-parameterizes the deviation knob. The measured deficit is
     that the gradient carries no conditional information at this signal
     density; a different parameterization of the same knob does not add
     any.
   - **A density/credit attack on the same surface** addresses the
     measured deficit directly, but M6 (ADR-0049), M7 (ADR-0058) and M8
     (ADR-0062) each landed on this layer and each returned
     trainable / behavior-moving / strength-neutral. The prior on a
     fourth attack through the same channel is poor.
   - **Preferred: hold the payment surface as infrastructure and take
     the §3a second act (D6), which inherits the promotion slot** — the
     surface is built, certified, faithful in live play
     (`directed_fail` 0.0028, `salvage` 0.0028 of deviations) and costs
     ~1.6% bridge tax to keep.
   - **First, one 3h control run** (run18's recipe with run17's drill
     campaign restored, §3c on) — the experiment that actually reads
     signal 2, under the condition that halted run16 at iteration 16 and
     run17 at iteration 11. It is the one remaining way §3c pays off:
     on run stability rather than payment capability. Note that run18's
     8 clean iterations do **not** establish runaway prevention —
     run16 and run17 were also quiet through iteration 9.

## Standing rules born here

- **Gate a capability on a discrimination statistic, not an accuracy
  count.** An accuracy threshold silently encodes a precision
  assumption; D4's ≥ 7/64 encoded an unpriced demand for ~2.8×
  selectivity from a channel whose selectivity had never been measured.
  Where the question is "can it tell A from B", the pre-registered
  number should be P(act | A) vs P(act | B).
- **A sub-population that is 0-correct at day-zero is a gate defect, not
  a hard drill.** Score it excluded or re-mine it before the run; 27/64
  of D4's denominator could not move and diluted every readout computed
  on it.
- **A recipe pin that removes a condition must be re-checked against
  every pre-registered readout.** `drill_selection: None` was priced
  against the training budget and against nothing else; it silently
  disarmed signal 2. The recipe session and the gate session were
  different sessions, which is how it got through.
- **Read every pre-registered signal, including the ones the headline
  gate does not depend on.** Signal 2 sat unread through the RESULT
  block, the devlog and the status compression.

## Consequences

- **Done-when 4 is satisfied** — D4 has its ADR, in the negative
  direction, with the discuss zone adjudicated.
- **D5 design inputs:** (a) the control run above is the entry
  condition for any further §3c work; (b) the X-cost enumeration family
  needs a look — `autopayer_xcost` is the only category §3c made worse;
  (c) near-gate reads still bind fresh-seed confirmation per ADR-0068's
  seed-half flag.
- **The evalset needs work before it gates anything again:** phyrexian
  and wide_choice positives are unreachable as constructed. Either the
  shapes are mis-mined or the head cannot express their goals — that
  distinction is cheap to settle against the certification harness and
  should be settled before those 27 drills appear in another
  denominator.
- **Unchanged:** the payment-completion queue (m9-plan), the M9 gate pin
  (0.5279 ± 0.0110), the ckpt of record (`d6-run11/iter-019`). No
  promotion; D4 was a probe and ran no gate.
- **Still due:** the pin-12 forced-family re-mine against `d6-run18`'s
  own stores, deferred past the run midpoint for GPU contention.
- **Assets:** `data/runs/veto-knowability-d4read` (i000/i007) and
  `-d4read-mid` (i002/i005) — the first in-era sampled kvr curve, and
  the drill-free/drill-fed veto-slope comparison table above, which is
  reusable as a control-family reference for any future veto claim.
