# ADR-0091: m10-probe5 read — the decode fix validated; the emitter works and the consumer is uncoupled: degeneracy veto FIRED on utilization, conditioning channel unconsumed on a live surface

- **Date:** 2026-09-02
- **Status:** accepted
- **Design-doc anchor:** m10-plan (probe shape), ADR-0084 gates, reads
  the ADR-0088 driver + ADR-0090 decode rule; the emission-collapse
  question (ADR-0085) CLOSED for the grounded regime

## What ran

`m10-probe5` = probe4's recipe + `sched_slot_pick` (ADR-0090). Four
accepted iterations, guard halt at iteration 4 (read below). The loop
mechanics stayed clean through all five: KL 0.022 / 0.010 / 0.014 /
0.028 / 0.047 (creeping toward the 0.06 bar by iteration 4 — noted),
seedlab per-step CE 2.68 → 1.30 (min 0.99 = 0.37×, no fit), paylab
0.94 → 0.54 with holdout auto-correct flat at 96–98%, tripwire 0 from
iteration 1 on. **The ADR-0088 fixed-batch mechanics are validated
over a full probe.**

## Findings

1. **The decode fix is validated in vivo.** Iteration 1's emissions
   under stop-vs-continue tracked the mint labels: pure-hold 6.9%
   (labels 8.1%), mean length 2.13 (labels 2.45) — versus 42% / 0.99
   at the same point in probe4. Day-zero baseline under the new rule:
   3.3% / 5.70 (a uniform head never reaches p_stop > 0.5), recorded.
2. **The emitter drifts off-support toward hold — the head, not the
   decode.** Pure-hold 6.9% → 29.7% → 27.4% → 18.4%; mean length 2.13
   → 1.63 → 1.17 → 1.62: it settles into a short, hold-heavy regime
   rather than collapsing monotonically. `sched_live_ce` (decode CE on
   the policy's own realized casts) climbed monotonically 7.3 → 12.1.
   Read: the mint's labels are certified-POSITIVE windows only — the
   ~19% of states where an arm beats natural by θ — so the head has no
   supervision on the other ~81% of live windows and generalizes there
   toward STOP-confidence. The read-but-uncertified turns (2,753 of
   3,406) are a legitimate label class ("no schedule beats natural ⇒
   emit hold-all, play naturally") the mint currently discards — a
   support gap, not a decode or optimizer defect.
3. **The conditioning channel is UNCONSUMED on a live surface — the
   first clean test of M10's actual question.** content_flip 0.0008 /
   0.0008 / 0.0002 / 0.0021 / 0.0013 (KILL bar 0.005, FUND 0.02);
   argmax_flip 0.015 / 0.007 / 0.008 / 0.013 / 0.018 (presence floor
   0.0125 — at the floor, twice below it); **utilization 0.2% → 1.8% →
   3.4% → 4.0% → 3.3% against the 25% bar — the degeneracy veto FIRED
   on this condition alone from iteration 2 onward.** Schedules of
   sensible shape were emitted and the cast policy did not follow
   them: nothing in the post-ADR-0086 recipe couples the priority head
   to the emitted schedule. This is ADR-0087's finding seen from the
   other side — the retired own-emission term was the coupling (it
   trained the shared trunk to relate slot content to realized casts),
   and retiring it cured emission degeneracy and removed consumption
   in the same move.
4. **The iteration-4 guard halt is a statistic artifact, read not
   amended:** paylab's iteration-MIN per-step chunk raw 0.227 < 0.25 ×
   0.999. Paylab is a mixed batch (positives ~3.7 CE, autos ~0.35); a
   4-window chunk of autos sits near 0.23 by construction, so the min
   over chunks tracks chunk composition, not fitting. The mean
   (0.54×) and the flat holdout say slow learning over ~10 epochs, not
   the impulse class. Refinement routed: the memorize guard reads the
   iteration min of the WINDOWED (telemetry-row) per-step mean, not
   the per-chunk min, for mixed-class batches.
5. No auto-KILL fired (the rule requires all aux heads plateaued;
   seedlab was still improving >10%/iteration) — the KILL numerics
   behaved as designed on a run whose verdict the veto already
   carried.

## Correction (2026-09-02 evening, from probe6's read): finding 2 RETRACTED as measured

The serve counters `sched_len_*` lump FIRST-WINDOW emissions (the
turn's plan) with REVISION emissions (opponent-action / end-step /
exhaust / veto re-emits, ~81% of rows), and revisions are legitimately
emptier late in the turn. Splitting probe5's mu rows by the `rev`
flag: first-window pure-hold **0.1% / 9.0% / 6.3% / 4.1%** and mean
length **2.87 / 2.42 / 1.73 / 2.14** at iterations 1–4 — the emitter
tracked its labels (8.1% / 2.45) throughout. **There was no off-
support hold-drift**; the 6.9% → 29.7% → 27.4% → 18.4% trajectory was
the revision share. The NO-FUND verdict stands unchanged (utilization
is not an emission axis). The label-support gap remains a design
argument (positives-only labels cover ~19% of states), not a measured
drift; ADR-0092 Fork 2 stands on that argument and on the user's
every-turn direction. Read convention from here: **the degeneracy
veto's emission axes read first-window emissions**; the counter split
by `rev` is routed as serve telemetry.

## Decision

1. **probe5 closes NO FUND on the degeneracy veto (utilization).**
   The emission-collapse question is CLOSED for the grounded regime:
   grounded supervision does not drive the emitter to the empty fixed
   point; with the decode rule corrected the surface is live at
   iteration 1; the residual hold-drift is a label-support gap.
2. **The M10 build gains a named missing piece: the CONSUMER coupling.**
   Design goes through the draft-and-adjudicate path
   ([m10-consumer-coupling-draft.md](../design/m10-consumer-coupling-draft.md)):
   a grounded, on-distribution supervision of the priority head toward
   the certified arm at emission windows (the paylab pattern on the
   schedule leg), plus the emitter support fix (uncertified read turns
   as hold labels). No relaunch before adjudication.
3. Guard statistic refinement (finding 4) and the non-cascading
   SIGTERM/halt teardown (workers orphaned on every stop this week)
   ride the run-infra hardening session.
4. probe5 kept frozen (4 accepted ckpts, full telemetry, the rejected
   iteration-4 ckpt) as the forensic and baseline asset for the
   coupling probe.

## Consequences

- Five probes have now peeled five layers (training signal, optimizer
  mechanics, replay integrity, guard instrumentation, serve decode) —
  each root-caused, each closed by a standing rule, none a threshold
  change. The layer now exposed is the design itself: emission and
  consumption were built as one surface and turned out to need two
  supervisions.
- The ADR-0084 gates carry unchanged to the coupling probe; the
  utilization axis of the veto — hitherto never the binding one — is
  now the headline instrument for consumption alongside content_flip.
