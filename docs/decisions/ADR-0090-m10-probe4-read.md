# ADR-0090: m10-probe4 read — the first post-surgery emission test; degeneracy veto FIRED on a serve decode-rule defect (STOP plurality under greedy argmax), not on the supervision

- **Date:** 2026-09-02
- **Status:** accepted
- **Design-doc anchor:** m10-build-spec §2/§5 (emission surface, serve
  decode); reads the ADR-0088 grounded driver under the ADR-0084 gates;
  closes the emission-collapse question opened at ADR-0085 for the
  grounded regime

## Context

`m10-probe4` (probe3's relaunch after a false memorize-guard halt — a
units bug, per-trajectory row values compared to per-step calibration;
fixed same morning, guard re-based on per-step keys + iteration-min at
0.25×) ran three accepted iterations on the ADR-0088 recipe: 543
witnessed mint labels, `--lab-k 4`, carry-w, warmup ramp. **The loop
itself was the cleanest of the four probes**: KL 0.029 / 0.011 / 0.015
(probe2 halted at 0.061), seedlab per-step CE 2.68 → 1.35 with the
memorize guard quiet (min 0.50×, bar 0.25×), paylab 0.9 → 0.6, mu
tripwire 1 → 0 → 0 (the single violation dropped its trajectory as
designed), no impulse anywhere. The ADR-0088 fixed-batch mechanics do
what they were built to do.

## The finding: emission collapse — by the decode rule, not the fixed point

Serve emission counters per generation (init ckpt → iter-0 ckpt →
iter-1 ckpt):

| generation | pure-hold | mean length | full-6 | utilization |
|---|---|---|---|---|
| iteration 0 (day zero) | 6.0% | 4.88 | 72.3% | 0.2% |
| iteration 1 | **41.8%** | **0.99** | 3.7% | 5.5% |
| iteration 2 | **52.3%** | **1.01** | 4.7% | 5.8% |

**Degeneracy veto: all three conditions (pure-hold > 25%, mean length
< 1.0, utilization < 25%) on two consecutive accepted generations —
FIRED. Pre-registered NO-FUND.** Content flip stayed flat (0.002) and
presence at the floor — a surface that is empty on half its windows
carries nothing to consume.

**But the mint labels are healthy — 8.1% pure-hold, mean 2.45, mode
length 3 — so the head overshot far past its own targets. The
mechanism is the serve decode:** `_sched_decode_greedy` took a
whole-row argmax with STOP as one class among the candidates. The label
STOP marginal is 8% at slot 0, 17% at slot 1, 25% at slot 2, 72% at
slot 3; ~15 candidates split the remainder. Once the head learns that
marginal (one iteration of grounded supervision), STOP beats every
candidate *individually* at slot ≥ 1 and on every uncertain window at
slot 0 — emitted length collapses to ~1 (36.6% length-1, 2.7% length-3
against 41% of labels at length 3). Day zero hid it: a head that knows
nothing never picks STOP, and 72% full-6 garbage looked like "plenty
of emission." **This is not ADR-0085's empty fixed point** (self-
referential targets); the targets are grounded and non-degenerate, the
decode turns a calibrated distribution into a length collapse.

## Decision

1. **Serve decode rule (`sched_slot_pick`, model.py): STOP only when
   p_stop > 0.5 — i.e. when it outweighs all candidates combined —
   otherwise argmax over candidates 1..C.** Rows with no valid
   candidate resolve to STOP by construction; masked candidates are
   never picked. Unit-tested on the slot-1 label shape (0.17 vs five
   at ~0.166 → continue, best candidate), the slot-3 shape (0.72 →
   STOP), the uncertain slot-0 window (0.08 vs 15 × 0.061 → continue),
   the no-candidate row, and the masked row.
2. **Training is untouched** (teacher-forced CE learns the same
   calibrated marginal); **reliance floors stand** (`sched_reliance`
   feeds stored schedules and never decodes); **mu/loader parity holds
   by construction** (the emitted schedule rides in the mu row
   verbatim, the loader reconstructs from it). No graft change.
3. **Day-zero emission counters under the new rule are read at the
   relaunch's iteration 0** — the veto bars are absolute, no re-bank;
   the day-zero pure-hold/length under stop-vs-continue is a new
   baseline row, recorded not gated.
4. **Relaunch as `m10-probe5`** (fresh name/seed 20280832/port 50083
   per ADR-0076); probe4 kept frozen as the forensic asset (three
   accepted ckpts + full telemetry).
5. Housekeeping landed with the read: probe3's false halt → the
   memorize guard re-based (per-step keys `seedlab_raw_step` /
   `paylab_raw_step`, iteration-min at 0.25×; ADR-0087's memorization
   magnitudes corrected to per-step scale, 2.73 → 0.18, narrative
   intact); the cold-start poison wave (8 workers × 1 first request
   on a cold server) identified and **ADR-0085/0087's "8 skips, same
   family" re-attributed** — a launch artifact, not the copy+resume
   crash class; server warm-up forward routed by name.

## Consequences

- Standing rule born (→ standing-rules.md): **an autoregressive
  emission head with a STOP class decodes stop-vs-continue (p_stop vs
  Σ candidates), never whole-row argmax** — the plurality-STOP
  collapse is a property of any calibrated head with a dominant
  terminal class, invisible at init and unmasked by the first real
  supervision.
- The emission-collapse question (ADR-0085) is answered for the
  grounded regime: grounded supervision does NOT drive the head to
  the empty fixed point (labels mean 2.45, head CE still falling
  toward them); the observed collapse was the decode rule. Whether
  emissions hold non-degenerate under the corrected rule is probe5's
  iteration-1 read.
- The ADR-0084 gates carry verbatim to probe5; the ADR-0086 restated
  decode leg reads ≤ 2.141 on the mint bank.
- Three probes' worth of "8 BridgePoisonedException" bookkeeping in
  the crash-family rate is retracted (launch-wave artifact).
