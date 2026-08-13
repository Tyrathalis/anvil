# ADR-0056: d6-run14 seq-term divergence — L_seq hinged, the share invariant instrumented and guarded (ADR-0054 amendment)

- **Date:** 2026-08-13
- **Status:** accepted (amends ADR-0054)
- **Design-doc anchor:** §6 of anvil-design-v2.md (C-bundle credit assignment)

## Context

d6-run14 (the M7 C-bundle run, launched 2026-08-12 21:16) GUARD-HALTED at
iteration 2: mean kl_mu 2.64 vs the 0.06 guard, veto_rate 0.384 vs 1.5× the
iter-0 baseline (0.211). The driver rejected the ckpt and exited cleanly —
ADR-0017 machinery worked as designed.

**Forensics (driver log + monitor rows):**

- `seq_raw` (raw L_seq) grew monotonically across the run: −0.22 → −0.31
  (iter 0), −0.53 → −0.65 (iter 1), then −0.75 → **−8.48** through iter 2's
  RL phase, in exact lockstep with the kl explosion (0.046 → 20.2 across
  ~300 optimizer steps) and the importance-ratio collapse (rho_mean 0.98 →
  0.23).
- **Root cause: L_seq is an unbounded log-prob contrast under a frozen
  weight.** The contrast logp(cast\*) − logp(pass) grows without bound as
  the policy saturates; w_seq was calibrated once at run start (ADR-0054)
  against |L_seq| ≈ 0.92 and never rebalanced. By the end of iter 2,
  w_seq·|L_seq| ≈ 0.022 against mean |PG per traj| ≈ 0.0005 — the seq
  gradient went from the designed ~10% of PG mass to ~40× it.
- The calibrate-once scheme's hidden assumption — |L_seq| stationary — is
  false: it grew 3× across two *in-band* iterations. (Irony on record: the
  smoke-era per-invocation recalibration "bug" fixed in `6916d03` was an
  accidental stabilizer; the carry-forward faithfully implemented the
  pinned design, whose real defect was the unbounded objective.)
- Coherent side-effects, all downstream of the runaway: rejected-intent
  chains 5 → 9 → 13/traj; in-play veto 0.211 → 0.230 → 0.384 (iter-001's
  *accepted* ckpt already carried the damage — acceptance-before-play
  latency is structural); same-turn hold-then-cast fell 0.241 → 0.213 →
  0.194, *away* from the heuristic's 0.345 — the term generalized to
  indiscriminate earlier casting, not deliberate timing.
- This violates the M6 standing rule in spirit: **engineered aggregates get
  clips at birth.** L_seq shipped without one.

**Verdict class: implementation bug, NOT a falsification.** The hypothesis
(sequence credit at ~10% of PG mass moves the gate) was never tested — the
10% invariant is precisely what broke. No gate read happened.

## Decision

Four changes (all default-on, committed with this ADR):

1. **L_seq hinged at ±margin (`--seq-margin`, default 6.0, both rl.py and
   the driver):** the contrast is clamped to [−margin, +margin]; a window
   already preferring its target by e^6 odds contributes zero gradient
   (hinge, not value-clamp — saturated windows drop out of the loss).
   Bounds |L_seq| ≤ seq_clip·margin = 1.5. margin=0 reproduces the old
   unbounded form for era reproduction.
2. **The share invariant is measured live and guarded:** rl.py logs
   `seq_share` = w_seq·|mean L_seq per step| / mean|PG per traj| per log
   window (= seq_frac at calibration by construction); the driver means it
   into the monitor row and halts on `--guard-seq-share` (default 0.3 =
   3× target). This guards the *cause*; kl growth is the symptom.
3. **Battery trend line:** monitor curves plot seq_raw + seq_share;
   anomaly on |seq_raw| final/first > 3× (the shape was visible from
   iteration 1 but nothing looked cross-iteration).
4. **In-phase kl abort (QoL):** rl.py `--kl-abort` (driver passes
   5×guard_kl) ends a diverging phase at the log window that crosses it,
   instead of finishing ~60% more runaway steps. The driver guard still
   rejects on the iteration mean.

**Not changed** (preserving the pinned experiment): λ=0.01, K=16/N=4,
P≈99, drill K=2, seq_frac=0.1, the campaign recipe, evalset v4, the worker
split, era jar, selection assets. The veto/rej growth was downstream of
the runaway — touching λ now would confound the re-run.

**Pre-registered secondary read for the re-run (not gate-bearing):** the
holding-read same-turn hold-then-cast trajectory. The hypothesis predicts
movement toward the heuristic's ~0.345; this run showed the metric is the
earliest visible symptom when the term pulls toward indiscriminate
aggression. If a properly bounded run still converts holds into immediate
casts with rising vetoes, that is evidence against this *formulation* of
the contrast (not against plan-granularity credit as an axis).

## Consequences

- **d6-run14 is closed as a halt, no gate read; ckpt of record stays
  `d6-run11/iter-019`.** iter-000/001 ckpts are contaminated (veto damage)
  — the re-run restarts from iteration 0 as **d6-run15**, same recipe +
  this ADR's deltas, fresh seed_base.
- **Validation before relaunch: a 2-iteration smoke** (the failure
  signature was *cross-iteration* growth, so run14's 1-iteration smoke
  could not have caught it): watch seq_share flat across the boundary and
  seq_raw bounded. ~5.5h against a ~55h run.
- Iteration wall re-anchored from run14: ~2h45m/iter (campaign ~2h40m is
  the pole at P=99 — the 42h estimate came from the 20-point smoke), so
  run15 ≈ 55h.
- Standing-rule reinforcement: *clips at birth* applies to loss terms, not
  just labels/aggregates; and **any auto-calibrated weight needs its
  invariant instrumented and guarded** — calibrate-once is only sound when
  the calibrated quantity is provably bounded.
