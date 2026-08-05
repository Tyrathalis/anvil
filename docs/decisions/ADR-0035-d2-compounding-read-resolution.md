# ADR-0035: M5 D2 resolution — the compounding read is flat; one-shot verdict

- **Date:** 2026-08-05
- **Status:** accepted (measurement resolution under ADR-0034 decision 2,
  which pre-approved both slope directions as honest closes; milestone
  close itself remains user-gated)
- **Design-doc anchor:** §6 (Grindstone); resolves m5-plan.md D2
- **Inputs:** [ADR-0034](ADR-0034-m5-opening-sequence.md) (the design),
  the m5-plan D1 migration read (pre-registered prediction, recorded
  2026-08-04 before the run), `d6-run12` (20 iters, zero guard trips),
  `run12-i019-finalarm` + `run12-i019-confarm` closing reads,
  `scripts/paired_arms.py` game-level joins vs the run11-i019 closing
  stores on matched seeds.

## Result

`d6-run12` ran the run11 recipe near-verbatim (only the forced deltas:
init/critic/mainline pin `d6-run11/iter-019`, selection v3, w=16, fresh
seed base 20260804) plus the mid-run drill-eval phase. Clean run: 20/20
iterations, zero guard trips, throughput in the validated w=16 band.

The standing gate, both halves paired game-by-game against the run11
closing stores on shared seeds:

| Read | Paired Δ (run12 − run11) | n |
|---|---|---|
| Standing seeds (20260710) | +1.20pp ± 1.04 (t=1.15) | 1,997 |
| Fresh seeds (20260711, the marginal-t tiebreaker) | −2.35pp ± 1.03 (t=−2.28) | 1,998 |
| **Combined** | **−0.58pp ± 0.73 (t=−0.79)** | **3,995** |

**Δ2 = −0.58pp ± 0.73 against Δ1 = +1.98pp ± 0.71 (t=2.77). The slope
verdict is one-shot: the second cycle of the identical drill loop
produced no measurable gain.** Absolute reads: 0.5442 ± 0.0109
(standing) and 0.5335 ± 0.0110 (fresh) vs baseline 0.5316 ± 0.0110.
The two halves disagree by 3.5pp (~2.4σ) — seed-set sensitivity worth
remembering when a single-set read looks conclusive; the combined
number is the read of record.

**Gate NOT cleared ⇒ no promotion. Ckpt of record stays
`d6-run11/iter-019`; baseline stays 0.5316 ± 0.0110. Selection/evalset
v3 remain valid for iter-019-era candidates.**

## The decomposition (all three probes agree)

Every stage of the cycle told the same story before the gate confirmed it:

1. **Stock is NOT the constraint.** Curation found 576 addressable
   losses vs cycle 1's 584 (61.4% vs 61.2%); the K=8 map was a
   near-clone (22.9% rollout winrate vs 0.585 v_before; cycle 1:
   23.7%/0.584). The error stock replenishes at the same level it
   drains.
2. **Held-out transfer is flat.** The mid-run drill-eval (evalset v3):
   iter 9 overall 0.3416, iter 19 overall 0.3467 vs baseline 0.3488.
   Run11's closing read on its own evalset was +3.9pp; run12's is
   −0.2pp.
3. **The conversion trade returned.** Iter-9 lost-bin +5.3pp faded to
   +2.6pp by iter 19 while winnable/coin went −4.7/−4.0pp: the drills
   still teach dead positions early, but the gains trade away against
   ahead-position play instead of compounding.

This is precisely the pre-registered prediction of the D1 migration
read (recorded before the run launched): one-shot-consistent profile,
Δ2 < Δ1, binding constraint at transfer/conversion, not stock. The
prediction chain — same-seed window recurrence + drilled=undrilled
conversion ⇒ cycle-1's gain was diffuse, not window-specific ⇒ a
second identical pass has nothing window-specific to compound — held
end to end.

## Decisions

1. **Cycling the identical drill loop is NOT the standing cadence.**
   One cycle of a given curation method appears to extract what that
   method can express; re-running it from the improved checkpoint
   re-finds the same windows and converts nothing further.
2. **Escalation (b) stays parked** (ADR-0034 decision 5): the flat
   read does NOT indict signal quality — the drills demonstrably
   taught their positions mid-run (lost-bin +5.3pp at iter 9). What
   failed is retention/composition: the gains traded away against
   ahead-position play. That indicts curriculum composition, not
   per-position advantage variance.
3. **The successor lever is curriculum composition** (the m5-plan risk
   note's branch): the winnable residual (−5.1pp at M4 close) and the
   ahead-weight/per-bin-slice levers deliberately excluded from cycle 2
   are now the first candidates for cycle 3 — with the slope question
   answered, they are no longer confounded.
4. **D3 (critic calibration) proceeds as planned** — unaffected by
   this verdict, and now materially richer: cycle 2 banked ~1,700 new
   K-rollout labels (map 565 + sweep arms + evalset re-measures) on
   top of the ~1,900 existing.

## Consequences

- M5 done-when clause 2 is SATISFIED (the compounding read resolved
  with the slope verdict, to ADR standard, in the negative direction —
  which ADR-0034 decision 2 pre-approved as an honest close).
- The Grindstone value proposition sharpens: the drill loop is a
  one-shot corrector per curation method, not a ratchet. Future cycles
  must change something material (composition, signal source, or
  curation method) to justify their cost.
- `d6-run12` artifacts retained (stores feed nothing — drill mainlines
  never ingest; the closing stores are paired-read substrate only).
- The migration read earns standing-tool status: it predicted the run
  outcome from curation-stage data at ~1/40th the compute. Future
  cycle proposals should run it first and treat a one-shot profile as
  a strong prior against an unmodified re-run.
