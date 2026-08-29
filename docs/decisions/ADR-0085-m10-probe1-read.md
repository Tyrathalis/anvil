# ADR-0085: m10-probe1 read — the decode-on-own-emissions loop is degenerate; no FUND, not a channel-KILL

- **Date:** 2026-08-28
- **Status:** accepted
- **Design-doc anchor:** §6 (training loop) + m10-build-spec §2/§5; probe numerics ADR-0084

## Context

The M10 training probe (`m10-probe1`, D4-shape 6×480 on the standing
recipe + R5 label stack, launch commit `20028fd`) ran 2 accepted
iterations and GUARD-HALTED at iteration 2 (`sched_share 1.504 > 0.3`,
ckpt rejected, deterministic halt). Every gate number was pre-registered
(ADR-0084); the user adjudicated: stop and read rather than amend and
push through.

## The forensics (all numbers from banked artifacts)

**The halt statistic was an outlier-mean artifact; the outlier was the
real disease.** Step-level decode CE: median stable and improving
(3.77 → 3.31 → 3.23) while the max exploded **7.7 → 46.8 → 543.5** —
the head's confidence sharpening makes rare off-mode targets
exponentially more surprising each iteration (~e^2–3×/iteration).
Iteration-2's mean share 1.504 vs median 0.178 (under the guard): the
share guard fired on a statistic no step ever showed, but the spike
growth it keyed on is halt-worthy in itself.

**The emission collapse is a one-step event that holds, not a slide**
(mu-file forensics, all three generation ckpts):

| generation ckpt | pure-hold | mean len | character |
|---|---|---|---|
| day-zero (`m10-sched-init`) | 6.3% | ~5.3 raw | 72% full-6-slot zero-init garbage; 17% one slot ×6 |
| iter-000 (1 RL iteration) | 62.3% | 0.59 | mode flipped to empty; remainder len 1–2 |
| iter-001 (2 RL iterations) | 60.5% | 0.69 | flat; len-2 emissions +47% (marginal recovery) |

**Mechanism:** the dense decode aux trains on the policy's OWN carried
schedules, and the head IS the emitter — a self-referential loss with a
degenerate fixed point at empty. From the garbage-full init,
immediate-EOS is the minimum-CE hedge on unpredictable targets; one
iteration reaches it; emissions then feed back as easy targets while
sampled off-mode emissions become the CE tail. The pre-flight predicted
the incentive: `sched_penalty_derive.py` found void arms cost ≈ nothing
— nothing in the reward opposes empty schedules, and the aux actively
prefers them. The intended anchor (seed supervision, 170 certified
windows at frac 0.05) is ~20× too small against the dense own-emission
term.

**Conditioning trajectory:** content_flip 0.0138 → 0.0036 → 0.0013 (an
iteration-0 consumption event at 2.8× the KILL bar — D6-speed — then
unwound as the targets emptied); presence flip ended BELOW the banked
0.012513 day-zero floor. Aux heads on the pinned population stayed
healthy (CE 1.14 → 0.95 → 1.07, E/R improving) — the instrument split
localizes the failure to the emission loop, not the heads or the carry.

**Degeneracy veto status:** conditions met on BOTH accepted-ckpt
emission measurements (62.3%/0.59 and 60.5%/0.69 vs the 25%/1.0 bars).
Formal KILL never reachable (requires accepted-iteration 4 + aux
plateau).

**Healthy lines (carried as assets):** paymark follow 3.4% → 6.2% →
9.2% (iter-0 baseline recovered offline from mu rows —
`data/training/m10-probe1/paymark-iter0-baseline.json`; the serve-side
counts for iteration 0 were lost to the `_stop_server` SIGINT defect,
fixed below); pay-label positive CE 0.77 → 0.52 → 0.43; serve-carry
tripwire 0 throughout; all other guards clean; the R1–R6 infrastructure
performed to contract.

## Decision (user-adjudicated 2026-08-28)

1. **The probe closes HALTED-AND-READ: no FUND — and explicitly NOT a
   channel-KILL.** The conditioning channel demonstrated consumption
   (the iteration-0 content movement); what failed is the
   emission/decode self-supervision loop as built. The verdict routes
   to surgery on that loop, not to abandoning the v2 surface, the
   carry, or the conditioning path. The strategy stands; the specific
   defect gets fixed.
2. **Surgery routed by name (the rework the next build round
   inherits):**
   - **Ground the dense decode targets** — retire or heavily gate the
     own-emission dense decode term; train decode against
     certified/minted schedules (the 96k-sweep label mint + seed-label
     pipeline are the existing machinery; this is re-weighting toward
     supervision we already produce at scale).
   - **Anchor the emission head directly** — supervised emission
     against certified best arms and/or a non-zero cost on empty
     emission (the reward provides no anchor; the void-arms-are-free
     derivation is now confirmed in vivo).
3. **Housekeeping landed in this batch (both defects found by the
   probe):**
   - `_stop_server` sends **SIGTERM** (was SIGINT): under a detached
     launch the server inherits SIGINT=SIG_IGN, CPython installs no
     KeyboardInterrupt handler, and the stats/counts-dump path was
     skipped into a 30s timeout + SIGKILL. (Mid-run this was worked
     around with an external SIGTERM rescue daemon, which recovered the
     counts for iterations 1–2.)
   - **Share guards read the step MEDIAN** (mean fallback for pre-0085
     rows) across all five share guards, and a new **spike tripline**
     `--guard-sched-spike` (default 100× median step CE) names the
     confidence-blowup class directly. Regression test built from the
     real iteration-2 numbers.

## Consequences

- M10 returns to a short design round for the two surgery items before
  any relaunch; the serve surface, R5 label stack, telemetry, and
  numerics package carry unchanged. The ADR-0084 kill/FUND numbers
  remain the standing gates for the relaunched probe (day-zero floors
  re-bank if the graft changes).
- Assets banked: 2 accepted iterations' full telemetry (counts rescued
  for 1–2), the emission-trajectory forensics, the paymark iter-0
  baseline (unmask follow bar 0.0685), `m10-probe1` stores/ckpts kept
  for the design round (iteration-2 REJECTED marker in place).
- **Standing rule born** (→ standing-rules.md): a dense aux term never
  trains on the policy's own emissions without a grounded anchor of at
  least comparable mass — self-referential decode collapsed to its
  degenerate fixed point (empty) in ONE iteration here.
- The probe-first discipline is the quiet win: the defect cost ~90
  minutes and 2 iterations instead of a promotion-scale run.
