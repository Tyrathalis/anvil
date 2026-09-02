# M10 consumer coupling — DRAFT (leans pinned for adjudication, 2026-09-02)

Session: the probe5 read ([ADR-0091](../decisions/ADR-0091-m10-probe5-read.md)).
Status **DRAFT** — the forks at the bottom go to adjudication; an ADR
stamps the outcome. Nothing relaunches before that.

## A. The requirement, read from probe5

Five probes peeled five layers; the layer now exposed is the design:
**emission and consumption are two competencies and were built with
one supervision.** Probe5's facts:

- The emitter works: with the ADR-0090 decode rule, iteration-1
  emissions track the labels (6.9% hold / 2.13 mean vs 8.1% / 2.45).
- The consumer is uncoupled: utilization ≤ 4% for four generations,
  content_flip ≤ 0.002, presence at the floor. Sensible schedules were
  emitted and the cast policy ignored them.
- The emitter drifts off-support (hold 6.9% → ~28%): the mint's labels
  cover only certified-POSITIVE windows (~19% of states); the head has
  no supervision on the other ~81%.

ADR-0087 said the retired own-emission term "was the content driver";
probe5 shows why — it was the only term that trained the shared trunk
to relate slot content to realized casts. Its retirement fixed the
emitter and orphaned the consumer. Two supervisions are needed; both
can be grounded on the same witnessed mint.

## B. Fork 1 — the consumer term: feed-and-follow supervision

**A grounded CE on the priority pointer at the mint's emission
windows, with the certified arm FED as the schedule (teacher-forced
conditioning) and the target = the arm's first cast** (the candidate
matching the label's `seq[0]` through the same `(e, sa60)` map
`build_seed_batch` uses; unmatched dropped and counted). This is the
paylab pattern on the schedule leg: grounded (certified), on-
distribution (the 499 non-hold mint windows), witnessed.

- **Feeding is the point.** Supervising the cast WITHOUT feeding the
  schedule is a BC term (state → cast); feeding the certified schedule
  and supervising its first slot trains "when the slot says X, cast X"
  — consumption. Lean: feed-and-follow, not bare BC.
- **Pure-hold labels (44) excluded** from this term (no first cast to
  follow; they stay in the emitter term).
- **Mechanics inherited verbatim** from ADR-0088: `--lab-k 4`
  subsampling, warmup ramp, carry-w, calibration against the honest
  day-zero raw, share guard at 3× target, memorize guard.
- **Mass (lean): frac 0.05** — the seedlab convention; total fixed-
  batch mass becomes seedlab 0.05 + follow 0.05 + paylab 0.1. Probe5's
  KL crept 0.010 → 0.047 by iteration 4 under two terms; the KL guard
  (0.06) is the tripline for three. If it trips, the routed answer is
  paylab → 0.05 before anything else.
- **Instrument**: `sched_follow_ce` telemetry from birth; the serve
  counters' follow rate (`sched_follow / (follow + dev)`) and
  utilization are the consumption reads; `content_flip` stays the
  competency axis.

## C. Fork 2 — the emitter support fix: uncertified turns are hold labels

The mint's stage-1 read has 2,753 witnessed-valid turns that were
READ and NOT certified: no arm beat natural by θ = 2.0. The honest
emission at such a window is hold-all — "no directive, play
naturally" — the same semantics as the 44 certified pure holds.
**Lean: mint them as hold labels** (a mint-side script over
`stage1-perturn.jsonl` ∩ `valid-turns.jsonl`; zero new rollouts) and
train the emitter on full support: ~3,250 windows, ~83% hold.

Consequences to pre-register, not discover:
- The emitter's marginal becomes hold-dominant BY DESIGN — the surface
  speaks only where a certified improvement exists, which is the
  ceiling spec's own semantics (29% certifiable turns, ADR-0078).
- **The degeneracy veto's pure-hold axis must be re-based
  label-relative**: pure-hold ≤ 1.5× the label hold prior (≈ 83% →
  bar ~95%... i.e. the axis becomes "the surface is not MORE silent
  than its labels"), and the mean-length axis is measured over
  non-hold emissions (≥ 1.0 there). Utilization and content_flip
  carry unchanged as the consumption axes.
- Under the ADR-0090 decode rule, p_stop > 0.5 at slot 0 will now be
  common and correct; day-zero re-read at the probe's iteration 0.

## D. Fork 3 — the read (ADR-0084 carried, consumption headlined)

- FUND (human): content_flip ≥ 0.02 AND **utilization ≥ 25%** (the
  veto bar, now a positive criterion) AND aux legs under their bars
  (seedlab ≤ 2.141 on the mint bank; follow CE ≤ 0.8× its day-zero,
  banked at launch) AND guards clean AND veto not firing.
- KILL (auto, from accepted 4): content_flip < 0.005 AND presence
  floor-relative < 0.005 AND all aux plateaued — verbatim.
- Discuss-zone between; presence-only movement cannot FUND.

## E. Fork 4 — probe shape and housekeeping

- `m10-probe6`: probe5 recipe + Fork 1 + Fork 2 + the re-based veto;
  6 iterations; fresh name/seed/port.
- Memorize guard refinement (ADR-0091 finding 4): the iteration-min is
  taken over WINDOWED per-step means (telemetry rows), not per-chunk
  raws — mixed-class batches (paylab) otherwise trip on auto-only
  chunks.
- Teardown cascade (workers orphaned on every stop this week): the
  driver's halt/SIGTERM path kills its worker tree — rides run-infra
  hardening but is a ~10-line change worth taking before probe6.

## Forks for adjudication

| # | fork | drafted lean |
| --- | --- | --- |
| 1 | consumer term | feed-and-follow CE on the priority pointer at mint windows, certified arm fed, first cast as target; holds excluded; frac 0.05; ADR-0088 mechanics verbatim |
| 2 | emitter support | uncertified witnessed turns minted as hold labels (~3,250 full-support windows); veto hold axis re-based label-relative, length axis over non-hold emissions |
| 3 | read | ADR-0084 verbatim with utilization ≥ 25% promoted to a FUND criterion; follow CE day-zero banked at launch |
| 4 | probe shape | probe6 = probe5 + forks 1–2 + guard refinement + teardown cascade; KL guard is the tripline for the third fixed-batch term |
