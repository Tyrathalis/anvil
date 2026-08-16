# ADR-0058: M7 closeout — the credit-assignment verdict: dense per-decision signal is trainable and behavior-moving; the act−hold formulation is strength-neutral

- **Date:** 2026-08-16
- **Status:** accepted (closes M7; resolves m7-plan done-when 2 and 4)
- **Design-doc anchor:** §6 of anvil-design-v2.md

## Context

M7 (opened 2026-08-10, ADR-0050) asked: **can dense per-decision signal
reopen improvement?** The instrument phase resolved D1/D3 (ADR-0051/0052
falsified the label instruments; ADR-0053 funded the C bundle on the
sequence probe; ADR-0055 closed the D3 boundary at gate 0.5373 ± 0.0112
on era `d798917ae5`). The C bundle (ADR-0054: C-seq advantage ×
specific-cast contrast + C2a critic aux + C3 first-attempt λ=0.01) then
ran three times:

- **d6-run14** (ADR-0056): GUARD HALT iter 2 — the unbounded L_seq
  contrast ran away under a frozen w_seq. Fix: hinge at ±6 (clips at
  birth), live seq_share telemetry + guard, in-phase kl abort.
- **d6-run15** (ADR-0057): 3 clean iterations, stopped — seq_share
  drifted via within-epoch PG-mass fade (measured a standing loop
  property, run13 forensic). Fix: per-iteration w_seq recalibration.
- **d6-run16 (this ADR): the full-instrumented run.** 16 accepted
  iterations at honest pricing (share means 0.14–0.18 throughout,
  recalibration stable, w_seq trajectory = live PG-mass proxy), then
  GUARD HALT iter 16 on veto 0.361 > 1.5×0.202 — the cost curve of the
  learned behavior, not an optimizer pathology.

## The run16 evidence

**Credit assignment WORKS as machinery.** The seq term trained stably for
16 iterations, visibly taught its target (|l_seq| at calibration deepened
0.43 → 0.68 on freshly re-rolled labels at the drilled windows), and
generalized into real behavioral change — the first demonstration that a
dense per-decision term survives this loop at controlled pricing.

**What it taught was the priced direction, and that direction is
strength-neutral.** The act−hold contrast prices "cast the advantaged
spell at the fork"; the run's whole behavioral arc is that instruction
generalizing: held-out drill-eval traded lost-bin conversion (+6.9pp,
saturating by iter 9) against winnable (−5.5pp) and coin (−4.9pp) decay;
same-turn hold-then-cast slid 0.233 → 0.182, *away* from the heuristic's
0.345; argmax veto climbed 0.231 → 0.294 → 0.361 until the guard fired.
ADR-0053 had already measured this ordering — natural > greedy ≫ hold,
with act−nat ≈ −1.7pp at N=4 — and a greedy-target term performing at
baseline is what that measurement predicted.

**Gate sweep (user-approved two-candidate read, M6 two-leading
precedent; arms-selected ckpts, disclosed):**

| ckpt | corrected winrate | Δ vs 0.5373 ± 0.0112 | veto |
|---|---|---|---|
| iter-009 | 0.5364 ± 0.0110 | −0.1pp — TIE | 0.189 |
| iter-014 | 0.5340 ± 0.0110 | −0.3pp — TIE | 0.239 |

No promotion. **Ckpt of record stays `d6-run11/iter-019` at 0.5373.**
iter-009's read is impeccable (veto below era baseline) — the tie is not
an artifact of veto damage; the trade at its healthiest point was
genuinely neutral in the play-weighted sum.

**Methodological finding (standing rule):** the mid-run arms elevation
(0.575 / 0.570 at iters 9/14, pooled t≈2) that motivated the sweep was
one ~1.5σ fluctuation counted twice — both arms evals run the SAME fixed
200-game seed subset of the pairs file. **Fixed-subset arms reads are one
observation, not N; never pool repeated reads of the same seeds as
independent evidence.** (Family of ADR-0034's single-seed-set rule.)

## Decision — the done-when-4 verdict

**Dense per-decision signal did NOT move strength in this formulation at
this dose (10% PG share).** The component analysis: C-seq carried all
measured behavioral movement; C2a trained stably (aux declining) with no
attributable strength effect; C3 at λ=0.01 was well-behaved until the
learned aggression outgrew it. The failure is in WHAT was priced, not in
the pricing machinery — the term taught exactly what it valued, and what
it valued (greedy act) was already measured suboptimal by the probe that
funded it.

**M7 CLOSES.** The chartered follow-up (a NEW design round, not an M7
extension): a **natural-timing-target formulation** — price the natural
arm's cast-timing distribution rather than the act−hold contrast, aiming
at ADR-0053's measured optimum instead of an approximation known to sit
below it. Dose escalation of the act−hold form is explicitly NOT
recommended: run16's own arc shows exposure amplifies the trade's cost
side after the benefit saturates.

## Consequences

- Assets carried out of M7: the full seq-term training machinery
  (seqlabels join, seq_pass hinge, per-iteration calibration, share
  telemetry + guard, kl abort), the forced-seq campaign harness,
  `drill-selection-v5-active` + evalset v4, the analysis battery with seq
  curves, three characterized failure modes with guards for each.
- Standing rules born in M7: engineered loss terms get clips at birth
  (ADR-0056); auto-calibrated weights get their invariant instrumented,
  guarded, and re-calibrated at the cadence it varies (ADR-0057);
  fixed-subset arms reads are one observation (this ADR); blast-radius
  sweep on instrument bugs (ADR-0052); check gate thresholds against
  estimator resolvability at design time (ADR-0051).
- run14/15/16 stores are veto-elevated to varying degrees — never in a
  training mixture. Gate-sweep stores (run16-i009/i014-finalarm) are
  clean baseline-era reads and keep.
- Milestone-close stale-data pass: kill-list presented separately (user
  sign-off gate, standing habit).
