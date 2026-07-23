# ADR-0023: M3 D2 closeout — the full-vis critic closes done-when #2

2026-07-23. Status: accepted.

## Context

ADR-0022 handed D2 a ceiling datum: the run-5 recipe (lr 2e-5, 480 g/iter,
masked critic, mirror generation) could not push past run-3's iter-012
(0.5213 ± 0.0110 corrected) — late-run arms declined and the 2,000-game
read was a dead tie. D2's pre-registered done-when: **a guarded run beats
iter-012 outside noise at the 2,000-game corrected read.**

Levers tried, in order (user-sequenced):

1. **§6d mixed-opponent generation (run-6, 2026-07-19→21):** heur_frac 0.5.
   Bought STABILITY (no late decline on paired seeds where run-5 fell
   0.540→0.475) but no gains; the per-batch reward split diagnosed why —
   τ=1 sampled play sat at parity with the eval opponent (0.5064 ± 0.0081).
2. **Generation temperature (§6e, 2026-07-21): FALSIFIED.** The τ-strength
   curve on run-6 iter-19 was flat in τ ∈ [0.3, 1.0] (CRN-paired τ0.3 vs
   τ1.0: +1.25pp ± 2.0). The sampling tax lives in near-tie windows at any
   temperature — it is the price of exploration, and the actionable defect
   is CREDIT: exploration variance never attributed back to the decisions
   that caused it.
3. **§6f full-vis critic in the loop (run-7/7b, 2026-07-21→23):**
   asymmetric V-trace — pass-A values (baseline + bootstrap) from a frozen
   full-vis critic, adapted per iteration (`finetune_value --full-vis
   --trainable all` on the replay mixture); masked head keeps training
   (v0_masked A/B); leak boundary test-pinned (fv windows never labeled,
   masked policy stream byte-identical).

## What happened

- **run-7 (lr 2e-5): GUARD HALT at iter 6** — veto 0.306 > 1.5× baseline,
  ~10 min wasted (vs run-2's 9.5h; the guards' second live catch). Not
  run-3's monotone leak: veto OSCILLATED with growing amplitude
  (0.151→0.099→0.306) while KL ran 0.014–0.059/iter — 3× run-6 at the same
  lr. Diagnosis: the critic multiplied effective advantage magnitude; step
  size must scale down to match. **Extension of ADR-0017's lesson: lr
  brackets are per-SIGNAL-REGIME, not absolute — "the drift rate was the
  stability margin" generalizes to lr × gradient scale.**
- **run-7b (lr 1e-5, all else identical, init run-6 iter-19): 20/20
  iterations, ZERO guard halts, zero tripwire violations.** KL 0.002–0.010
  per iteration, first-attempt veto equilibrium 0.08–0.13, casts/game
  36–39 throughout, entropy 0.143→0.130, critic calibrated (v0 within
  ~2pp of realized nearly every iteration). Arms: 0.4950 (i4, real dip —
  conservative consolidation phase) → 0.5525 (i9) → 0.5625 (i14, project
  high-water) → 0.5475 (i19, tie with i14). Checkpoint of interest:
  iter-014 (run-5 precedent: best-by-arms).

## The closing read (record `data/runs/run7b-best-arms-report.json`)

2,000 games, 2,000 decisive, 0 crashes; first-attempt veto 0.0899 argmax
(bar 0.1358); raw **0.5545 ± 0.0111 / Ante-corrected 0.5530 ± 0.0109**.

- **Paired vs run-3 iter-012 (ckpt of record): +3.26pp ± 1.16 (t=2.80,
  302 up / 237 down) — done-when #2 SATISFIED.**
- Paired vs its own init (run-6 iter-19): +2.20pp ± 1.01 (t=2.17) — the
  run added strength outside noise on its own account.

## Decisions

1. **RL checkpoint of record → `d6-run7b/iter-014/train/last.pt`**
   (0.5530 ± 0.0109 corrected) — the first outside-noise supersession;
   run-3 iter-012 retires to history after six days as the record.
2. **The critic loop is the standing recipe**: §6d opponent mix + §6c
   penalty + §6f critic at lr 1e-5. The with-critic lr bracket is
   (1e-5 stable, 2e-5 unstable); the without-critic bracket (1e-5, 3e-5)
   from ADR-0017 no longer applies to this loop.
3. **v0/v0_masked A/B stays in the monitor** — the masked head never
   diverged pathologically in run-7b; the §6f information-gathering caveat
   remains a watch item, unobserved so far.
4. M3 done-when state: #1 ✓ (ADR-0022) · **#2 ✓ (this ADR)** · #3 shipped,
   pending #11285 review cycle · #4 open (rebase).
5. Next-lever sequencing (scale at the stable operating point, Grindstone
   drill seeding, D4 rebase timing) = a session-level decision with the
   user, on fresh context.

## Honest notes

- iter-14 vs iter-19 is a paired tie (−1.50 ± 2.00); the "climb" between
  i9 and i14 was inside noise. What is outside noise is the DESTINATION:
  the closing read vs both the record and the init. The run earned its
  verdict at 2,000 games, not from the 400-game trajectory.
- The early dip (i4: −4.50 ± 2.14 paired vs init) was real, coincided with
  peak conservativeness (casts/game 36.1, veto 0.075), and fully recovered
  — recorded so future critic-loop runs expect the consolidation phase
  rather than halting on it.
- Veto at the closing read (0.0899 first-attempt) remains under the D5
  bar; the §6c equilibrium survived a lever that doubled gradient scale.
