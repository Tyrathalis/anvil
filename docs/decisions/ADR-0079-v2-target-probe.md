# ADR-0079: M10 v2 aux-target probe — both resource components clear their gates (E decisively, R clearly); the feasibility head FAILS its linear premise and does not ship at birth

- **Date:** 2026-08-26
- **Status:** accepted
- **Design-doc anchor:** [m10-v2-target-probe-spec.md](../design/m10-v2-target-probe-spec.md)
  (adjudicated + pinned pre-data, commit `1a56dee`); [m10-plan.md](../design/m10-plan.md)
  design-round obligation 2; ADR-0074 (the pattern this executes)

## Question

From the frozen `d6-run11/iter-019` trunk at the fork-consistent MAIN1
emission window, are the three adjudicated v2 aux targets predictable
above the obs-arithmetic baseline? Pass ⇒ the head ships as
adjudicated; fail ⇒ the pre-registered fail path, loudly.

## Instrument

`scripts/v2_target_probe.py` (committed pre-data with the spec).
E/R population: `m9-rebaselinearm` s0+s1 — 22,224 own-turn groups,
38,948 realized-cast slots (1.75/turn, matching the census mean; 1
slot dropped for a missing follow-window). F population: the ceiling
sweep universe — 600/600 fork windows matched, 7,950 (turn, arm) rows
(584 hold-alls excluded by rule, 189 crashed rolls skipped, ~240
schedfile arms with no surviving outcome rows). Ladder per R1:
obs-arith → `[STATE]` → `[STATE]⊕[PLAN]`; F's arm-arith encoding joins
every rung; R's arith rung carries slot index k. Deterministic
game-grouped 80/20 split; gates = ADR-0074 numerics verbatim.

## Result

| target | metric | arith → [STATE] → [STATE]⊕[PLAN] | pin | verdict |
| --- | --- | --- | --- | --- |
| E — EOT resource summary (7 axes) | mean Spearman | 0.3374 → 0.5078 → **0.5438** | ≥ arith+0.05 ∧ ≥0.15 | **PASS** (+0.206, 4.1× margin) |
| R — running ledger (2 axes, 38,948 slots) | mean Spearman | 0.5826 → 0.6320 → **0.6490** | ≥ arith(+k)+0.05 ∧ ≥0.15 | **PASS** (+0.066) |
| F — schedule realize (7,950 rows, pos 21.3%) | AUC | 0.8073 → 0.7940 → **0.8048** | ≥ (arith⊕arm)+0.03 ∧ ≥0.60 | **FAIL** (−0.003 increment) |

- The reserved `[PLAN]` slot adds a real increment again on both
  passing targets (E +0.036, R +0.017 over `[STATE]` alone) — the
  ADR-0074 free finding replicates on resource axes.
- F's report-only degrade-slot read: ρ 0.2926 → 0.3281 (+0.036, below
  the 0.05 margin as well). Every degenerate-axis and support rule was
  clean; the E floating axis recorded unavailable (obs sv=2 has no
  mana-pool field).

## The F reading (recorded with the verdict, not softening it)

The baseline is HIGH in absolute terms: obs-arith ⊕ arm-arith alone
reaches 0.807 AUC — h2 schedule feasibility is largely knowable from
cheap explicit features (capacity-vs-demand arithmetic), and the trunk
adds nothing measurable on top. Two candidate accounts, deliberately
not adjudicated here: (a) structural — a linear probe cannot express
state×arm interactions, and the linearly-expressible part of
feasibility is exactly what the cheap features already capture; (b)
substantive — the emission-point trunk carries no realization-relevant
residual. Either way the pinned premise fails at the pinned
instrument.

The reassuring corollary for the penalty design: knowably-invalid
schedules ARE detectable from cheap afford-arithmetic at 0.81 AUC —
the knowability splitter's material exists independent of the trunk.

## Decision

1. **The v2 aux roster at birth is E + R** (the adjudicated BOTH
   resource components, joint multi-task) — obligation 2 resolved;
   the build proceeds on the two-head roster.
2. **The F aux head does not ship at birth** (pre-registered fail
   path): the validity predicate stands on R (per-slot affordability)
   + the veto-knowability splitter; the invalid-schedule penalty's
   knowability gate falls back to the splitter alone.
3. **Penalty-design revisit is a named design-round event** — folded
   into the numerics-pinning session (the penalty rule was already
   pinned knowability-gated + ADR-0053-calibrated; the revisit
   confirms the splitter-only gate suffices).
4. **A nonlinear/interaction-aware F re-probe is a NAMED future
   instrument, not a silent reroute:** if the build session wants the
   feasibility head later, it pre-registers a new probe (interaction
   features or a small MLP probe rung) against the same 96k-row label
   mint — routed on the canonical-register watch pattern, funded by
   need (e.g., validity-telemetry gaps at birth).

## Consequences

- Assets: `scripts/v2_target_probe.py` (E/R dump reusable as the
  aux-holdout instrument during training, per the plan_probe
  precedent); `data/runs/v2-target-probe/` (22,224-group + 38,948-slot
  + 7,950-row feature dumps + probe read).
- The sweep-row label mint remains an era-asset either way — F labels
  are minted and banked even though the head is not built.
- Owed at the build session: aux-task weighting for E+R under the
  ADR-0057 instrumentation; the graft + day-zero banking; kill/FUND/
  unmask numerics + read-protocol pin (the standing next item).
