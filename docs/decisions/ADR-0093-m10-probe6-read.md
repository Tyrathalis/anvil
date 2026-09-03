# ADR-0093: m10-probe6 read — the coupled surface consumes as PRESENCE and FOLLOWING; content sensitivity moves 10× from day zero but lands in the DISCUSS-ZONE; the on-policy loop (own plan → own casts) drifts apart

- **Date:** 2026-09-02 (evening)
- **Status:** accepted as the READ; the FUND / next-round adjudication
  is the user's (ADR-0084 discuss-zone rule)
- **Design-doc anchor:** ADR-0084 gates (verbatim), ADR-0092 build,
  the run-analysis protocol

## What ran

`m10-probe6` = probe5's recipe + ADR-0092: the full-support emitter
(2,157 joined labels: certified + natural-line casts + holds) and the
feed-and-follow consumer term (496 certified windows, post-land timing).
**Six iterations, all accepted, zero guard trips, zero halts — the
first probe to complete its planned length.** The driver exited clean
and, for the first time, left no orphans (the PR_SET_PDEATHSIG cascade
verified). Loop mechanics: KL 0.024 / 0.013 / 0.026 / 0.039 / 0.037 /
0.051 (creeping toward the 0.06 tripline under three fixed-batch
terms); seedlab per-step 2.67 → 1.24 (0.47×, no fit); paylab 0.93 →
0.49; follow 10.5 → 5.2; all shares on target; tripwire 1 dropped
trajectory in one iteration.

## The read, on the pre-registered instruments

| iter | content_flip | argmax_flip | reliance_l1 | utilization | live follow rate | follow CE (batch) | first-window plan |
|---|---|---|---|---|---|---|---|
| 0 | 0.0006 | 0.012 | 0.56 | 0.2% | 3% | 10.5 | 3.0% hold / 5.72 (day zero) |
| 1 | 0.0015 | 0.020 | 0.62 | 13.3% | 52% | 9.7 | 4.7% / 3.66 |
| 2 | 0.0051 | 0.032 | 0.73 | 25.0% | 45% | 9.1 | 10.3% / 1.78 |
| 3 | 0.0057 | 0.034 | 0.68 | 22.7% | 40% | 8.0 | 7.6% / 1.50 |
| 4 | **0.0064** | **0.066** | **1.80** | **37.8%** | 38% | 6.5 | 11.7% / 1.29 |
| 5 | 0.0053 | 0.046 | 1.16 | 18.0% | 32% | 5.2 | 13.3% / 1.94 |

(First-window = the turn's plan; revision emissions excluded per the
ADR-0091 correction. Labels: 9.7% hold / mean 1.95.)

- **KILL: does NOT fire** — content_flip ≥ 0.005 at iterations 2–5 and
  presence 3–5× above the 0.0125 floor.
- **FUND: NOT met** — content_flip peaks at 0.0064 against the 0.02
  bar (aux legs clear: seedlab 1.24 ≤ 2.13, follow 5.2 ≤ 8.39;
  utilization cleared 25% once; the degeneracy veto never bound).
- **⇒ DISCUSS-ZONE.** The session adjudicates (ADR-0084 rule E).

## Findings

1. **The coupling is consumed — as presence and as following.** The
   fed-vs-closed distribution difference tripled (reliance_l1 0.56 →
   1.80), presence flip reached 5× the floor, utilization rose from
   0.2% to a 37.8% peak, follow CE halved on the certified batch, and
   the battery reports a 6.7% behavioral delta from the init ckpt and a
   moved hold-then-cast rate (0.210 → 0.185). Every consumption axis
   that was dead in probe5 is alive in probe6, and the emitter held its
   label distribution throughout (first-window hold 5–13%, length
   oscillating 1.3–3.7 around 1.95 — an oscillation, not a drift).
2. **Content sensitivity moved 10× from day zero and then plateaued
   just above the KILL bar** (0.0051 → 0.0057 → 0.0064 → 0.0053). This
   is the ADR-0084 "presence-heavy, content-quiet" pattern — but with
   content genuinely off zero for the first time in six probes. The
   policy has learned that *a* schedule is there and to lean on it;
   it does not yet reliably read *which* schedule.
3. **The on-policy loop drifts apart.** Batch follow CE fell steadily
   (10.5 → 5.2) while the LIVE follow rate declined (52% → 32%) and
   `sched_live_ce` (the emitter's plan vs the policy's realized casts)
   rose 4.7 → 7.1 from iteration 1 on. The consumer learns to follow
   *certified arms fed on batch windows*; live play feeds the
   emitter's *own* plans (mostly natural-line-shaped), and nothing
   supervises following those — that was the retired self-referential
   term's job (ADR-0085/0087), and its retirement is why the
   emitter/consumer pair now train toward their batches and away
   from each other on-policy.
4. **Instrument corrections landed with this probe**: the veto's
   emission axes read first-window emissions (ADR-0091 corrected);
   the memorize guard reads the iteration median; the cold-start
   poison wave recurs at every iteration's server restart (8 workers
   × 1 first request; it only trips the 2% non-decisive flag when
   engine crashes stack on it).

## Routed by name (the next design round, for adjudication)

- **Close the on-policy loop without self-reference**: a consumer
  term that follows the policy's OWN emitted plan at live windows —
  safe now because the emitter is anchored by grounded full-support
  labels (the ADR-0085 fixed point needed the emitter itself to be
  the target; with the emitter frozen-anchored, a follower cannot
  empty it). Instrument: live follow rate and `sched_live_ce` are the
  reads that should reverse.
- **Content sensitivity as its own target**: the reliance instrument
  measures cast change under schedule A vs B; a contrastive follow
  term (two certified arms fed at the same window, follow each) is the
  direct supervision for the axis FUND reads.
- **KL headroom**: three fixed-batch terms drove KL to 0.051 by
  iteration 5; paylab → 0.05 is the pre-routed first response before
  any fourth term.
- **Serve telemetry**: split `sched_len_*` by `rev`; per-iteration
  server warm-up forward (the cold-start wave).

## Consequences

- probe6 kept frozen: six accepted ckpts, full telemetry, the battery
  report, the mu rows (the first-window/revision split's instrument).
- The M10 build spec gains the honest state: emitter DONE (grounded,
  full-support, decode-correct, stable over six iterations); consumer
  PARTIAL (presence + following consumed, content sensitivity weak);
  on-policy closure OPEN.

## Addendum 2026-09-02 (late) — ADJUDICATED: NO-FUND, no KILL; the routed design round SUPERSEDED by the reset draft

- **User adjudication: NO-FUND, no KILL.** probe6 kept frozen.
- **Corrected reading, from a label-shaped content probe run at the
  adjudication** (`scripts/sched_content_probe.py`: the certified arm
  fed at the 496 follow-batch windows, the natural line fed at 539
  windows the follow term never trains on; slots 0↔1 swapped as a
  legal-candidate content change):

  | ckpt | certified: follow fed / closed | swap-flip | natural: follow fed / closed | swap-flip |
  |---|---|---|---|---|
  | init | 9.7% / 9.1% | 0.0% | 67.0% / 67.9% | 0.0% |
  | iter-2 | 12.3% / 10.1% | 2.5% | 69.9% / 68.5% | 2.9% |
  | iter-5 | 19.0% / 14.1% | 2.8% | 65.3% / 66.4% | 2.9% |

  1. The live follow rate and utilization headlines above are
     **natural-line inflation**: on natural windows the schedule adds
     nothing (fed = closed), so 32–52% live following is the policy
     playing its own line — the inflation ADR-0092 predicted for
     utilization applies to follow rate too.
  2. On the training windows themselves, schedule-conditioned following
     is ~5pp (fed − closed); half the follow term's effect is behavior
     cloning of certified first casts.
  3. The content plateau is real on both populations (~3% swap-flip on
     label-shaped inputs, ~0.6% on the pinned population whose fed
     schedules are day-zero six-slot emissions, 36% one card repeated
     six times). Finding 1 ("consumed as presence and following") is
     therefore overstated: consumption is a few percent real.
- **Findings 3 and the ADR-0088 staleness tell are one fact.** Policy
  gradient never reaches the emitter (its logits appear in the learner
  only in the grad-free live-CE block); the live-gap ratio
  `sched_live_ce / seedlab_raw_step` read 3.3 / 3.1 / 3.5 / 3.8 / 4.9 /
  5.7 — above the 3× tell throughout (the ratio's day-zero ≈ 1.0 needs
  re-basing on the full-support batch; the trend is the signal).
- **The routed design round (own-plan follow term, contrastive term) is
  SUPERSEDED**: the follower fixes fidelity, not planning; the funded
  ceiling was measured under binding `-forceschedule` execution while the
  live surface is advisory. The user directed a step back →
  [m10-reset-draft.md](../design/m10-reset-draft.md) (planner hierarchy,
  binding execution, planner PG anchored by mint distillation, the
  certifier as an asynchronous era-weighted labeler, stratified paired
  strength as the primary probe read, retirement list). The own-plan
  follow term is recorded there by name as the deferred alternative
  (§F.1). KL headroom and the serve-telemetry items ride the reset build.
- Standing rule born (→ standing-rules.md): serve-side follow and
  utilization counters inflate on natural-line plans; a consumption read
  must be schedule-conditioned (fed vs closed) on label-shaped inputs.
