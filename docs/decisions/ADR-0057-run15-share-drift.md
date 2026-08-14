# ADR-0057: d6-run15 stopped at iteration 3 — seq_share drift adjudicated, per-iteration w_seq recalibration is the default (ADR-0054/0056 amendment)

- **Date:** 2026-08-13
- **Status:** accepted (amends ADR-0054 pricing; builds on ADR-0056)
- **Design-doc anchor:** §6 of anvil-design-v2.md (C-bundle credit assignment)

## Context

d6-run15 (the ADR-0056 recipe: hinged L_seq, share guard) ran three clean
iterations — guards never tripped — but the share telemetry showed the
frozen run-start w_seq drifting out of the pinned design regime:

- **seq_share iteration means 0.206 → 0.272 → 0.286** vs the 0.1 target
  and the 0.3 guard; iteration-1/2 windows closed at 0.34–0.42. Iteration
  3 would almost certainly have tripped the guard.
- **Decomposition: this is DENOMINATOR drift, not the run14 pathology.**
  The numerator (w_seq·|L_seq|) grew mildly and decelerated (seq_raw
  −0.101 → −0.134 → −0.145; growth 32% → 9% — the hinge saturating as
  designed). The driver is mean |PG per traj| falling ~3× within each
  epoch.
- **Forensic (run13 logs): the within-epoch PG fade is a standing loop
  property, not a bundle effect.** run13 (no seq term, prior era): |pg|
  head→tail 0.53×/0.27×/0.21× at iters 0/1/10; run15: 0.28×/0.34×. Opening
  PG magnitudes are roughly stable across iterations (run13 iter-0 0.011 →
  iter-10 0.0097), so the fade is per-epoch, not run-long decay. The share
  telemetry is simply the first instrument to measure anything against PG
  mass. (M7 note: outcome gradient exhausting itself within every epoch
  fit, across eras, is the ADR-0049 thin-signal diagnosis seen per-fit —
  corroboration, not a new problem.)
- **Secondary reads at the stop:** veto climbing 0.196 → 0.234 → 0.255
  (its guard at 0.294 — the run was 1–2 iterations from death by one guard
  or the other); rej 5.0 → 6.2. **The pre-registered hold-then-cast read
  moved TOWARD the heuristic for the first time: 0.221 → 0.221 → 0.243**
  (target direction ~0.345; run14 moved away at the same point).
  Encouraging, but measured at ~2.9× design share — not interpretable as
  evidence for the pinned design; watch for it to reappear in run16.

**Stop decision:** user-authorized (08-13, "stop the run if it's moving in
the wrong direction after iter-2"). Iteration 2 passed the guard by 0.014
with share still drifting and veto climbing; continuing meant ~2 more
iterations to a predictable halt, at uninterpretable share. SIGTERM'd
clean at iteration-3 generation; watchd unregistered manually (the driver's
self-unregister does not run on SIGTERM — known wrapper-pattern gap).

## Decision

1. **Per-iteration w_seq recalibration is the driver default.** Each rl.py
   invocation recalibrates over its first `--seq-calib-steps` (50) steps,
   pricing the seq term against the CURRENT iteration's PG mass and label
   population. Safe now because the ADR-0056 hinge bounds |L_seq| — the
   missing precondition that made run14's per-invocation recalibration
   dangerous. Cost: ~6% of each iteration's steps run seq-off.
   `--seq-carry-w` restores ADR-0054 run-start-only calibration (era
   reproduction of run14/run15).
2. **The within-epoch share ramp is DOCUMENTED EXPECTED BEHAVIOR:**
   calibration happens in the high-PG window at epoch start, so share ramps
   ~0.1 → ~0.3 within every epoch as PG fades under a fixed-this-epoch
   weight. Every fixed-weight loss term (entropy bonus, value aux) has this
   property; the hinge admitted L_seq to that class. The iteration-MEAN
   guard (0.3) tolerates the ramp and still catches pathological versions.
   Do not mistake the ramp for drift.
3. **Free instrument born:** per-iteration `seq_calibration.json` files now
   give a w_seq trajectory = a live PG-mass/label-population proxy across
   the run.

## Consequences

- **d6-run15 closed as a clean stop, no gate read; ckpt of record stays
  `d6-run11/iter-019`.** run15 iter-000..002 ckpts/stores carry elevated
  veto (0.255 at stop) — do not reuse in any training mixture.
- **d6-run16 = run15 verbatim + the recalibration default** (fresh
  seed_base 20260817, restart from iteration 0), `launch_d6_run16.sh`.
  No new smoke owed: the mechanism change is small, run15 validated the
  hinge+telemetry live, and the guard armory now covers both drift
  directions. Watch items: seq_share holding ≈0.1 per-iteration means
  (ramp expected within epochs), w_seq trajectory across iterations,
  veto trend, hold-then-cast (the favorable tick reappearing under honest
  pricing would be the first real evidence on the M7 axis).
- Standing-lesson reinforcement (ADR-0056 line extended): an
  auto-calibrated weight's invariant must be *held*, not just measured —
  calibrate against the quantity at the cadence it actually varies.
