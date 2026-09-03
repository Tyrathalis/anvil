# ADR-0092: consumer coupling — two supervisions for two competencies; the emitter schedules every turn

- **Date:** 2026-09-02
- **Status:** accepted — four forks user-adjudicated on the drafted
  leans (Fork 2 revised on user direction the same day); the full
  statement of record is
  [m10-consumer-coupling-draft.md](../design/m10-consumer-coupling-draft.md)
- **Design-doc anchor:** m10-build-spec §2/§4 (emission surface,
  targets/aux losses); executes the [ADR-0091](ADR-0091-m10-probe5-read.md)
  routing; the every-turn plan of the M9 D6 lineage

## Context

Probe5 ([ADR-0091](ADR-0091-m10-probe5-read.md)) established that the
M10 surface has a working emitter and an uncoupled consumer: with the
decode rule fixed, emissions tracked the labels at iteration 1, and the
cast policy ignored them (utilization ≤ 4%, content_flip ≤ 0.002,
presence at the floor). The retired own-emission term (ADR-0086) had
been the only coupling between slot content and realized casts;
retiring it fixed emission degeneracy and orphaned consumption.
Separately, the emitter drifted off-support toward hold because the
mint's labels covered only certified-positive windows (~19% of
states).

## Decision

1. **Consumer term — feed-and-follow supervision (Fork 1).** A grounded
   CE on the PRIORITY pointer at the mint's certified emission windows
   with the certified arm FED as the schedule (teacher-forced
   conditioning) and the target = the arm's first cast (the candidate
   matching `seq[0]` through the `(e, sa60)` map `build_seed_batch`
   already uses; unmatched dropped and counted). Feeding is the point:
   supervising the cast without feeding the schedule is BC; feeding it
   trains "when the slot says X, cast X". Pure-hold labels excluded
   (no first cast). Restricted to CERTIFIED windows — feeding and
   following the natural line would clone what the policy already
   does. Mechanics inherited verbatim from ADR-0088/0090: `--lab-k`
   subsampling, warmup ramp, carry-w, calibration against the honest
   day-zero raw, share guard at 3× target, memorize guard. **Mass frac
   0.05**; the KL guard (0.06) is the tripline for a third fixed-batch
   term, and paylab → 0.05 is the routed first response if it trips.
   Telemetry from birth: `sched_follow_raw` / `_step` / share; the
   serve counters' follow rate and utilization; `content_flip` stays
   the competency axis.
2. **Emitter support — schedule EVERY turn (Fork 2, revised).**
   Uncertified ≠ no schedule: it means no enumerated arm beat NATURAL
   play by θ, and natural DID cast. The full-support emitter label is
   the certified arm where one exists (543), the natural line's
   realized casts on the witnessed uncertified turns (~2,700, read
   from the FROZEN mint store — the retired own-emission target as a
   fixed era asset, so the ADR-0085 self-referential fixed point
   cannot form; the loader's target construction already exists), and
   hold only where natural cast nothing. ~3,250 witnessed windows,
   minted from `stage1-perturn.jsonl` ∩ `valid-turns.jsonl` + the
   source store; zero new rollouts. The emitter learns to always emit
   the plan it would play; certified arms are the improvements layered
   on top. **The veto axes stay absolute.** The seedlab day-zero
   re-banks on the full-support set (the FUND decode leg's 0.8× reads
   the new bank).
3. **The read (Fork 3).** ADR-0084 verbatim with the consumption
   axes headlined: **FUND = content_flip ≥ 0.02 on the fixed reliance
   population** (primary) AND utilization ≥ 25% as a FLOOR (it inflates
   on natural-line windows — never sufficient alone) AND aux legs
   under their bars (seedlab ≤ 0.8× its full-support day-zero; follow
   CE ≤ 0.8× its day-zero, both banked at launch) AND guards clean AND
   veto not firing. KILL verbatim. Presence-only movement cannot FUND.
4. **Probe shape and housekeeping (Fork 4).** `m10-probe6` = probe5
   recipe + decisions 1–2 + the re-based read; 6 iterations; fresh
   name/seed/port. Landed with it: the memorize guard reads the
   iteration MIN over WINDOWED per-step means (telemetry rows), not
   per-chunk raws (the probe5 paylab artifact); the driver's halt/
   SIGTERM path cascades to its worker tree (orphans on every stop
   this week).

## Consequences

- Standing rule born (→ standing-rules.md): **a supervised emission
  head needs FULL-SUPPORT labels — positives-only labels drift the
  head off-support toward its terminal class** (probe5: hold 6.9% →
  ~28% under labels at 8%).
- Build order: full-support label mint → follow term (on the seedlab
  batch machinery, with fed-schedule side tensors synthesized from
  the label) → day-zero banks at the init ckpt → guard windowed-min →
  teardown cascade → `launch_m10_probe6.sh` (smoke-axes declared) →
  launch.
- The emission-collapse question is closed; the open question is now
  M10's own: does a coupled consumer read the schedule content
  (content_flip), and does it follow certified improvements
  (utilization on certified windows, follow rate)?
