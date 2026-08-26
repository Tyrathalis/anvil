# M10 ceiling sweep — exploratory reads (2026-08-26)

*The spec's named secondary reads ([m10-ceiling-spec.md](m10-ceiling-spec.md)
"Secondary / exploratory reads": inform routing, NEVER gate), run after
[ADR-0078](../decisions/ADR-0078-m10-ceiling-measurement.md) closed the
funded verdict. Producer: `scripts/schedule_explore.py` →
`data/runs/sched-sweep-m10/exploratory-reads.json`. Consumer: the M10
build design session.*

## 1. Best-arm shapes (the fork-9 dividend) — bespoke subsets dominate

Of the 170 certified turns' selected arms:

| shape | certified | read (all 583) |
|---|---|---|
| non-canonical ordered subset | **96 (56%)** | 266 |
| greedy-max-spend | 28 | 97 |
| curve-ascending | 20 | 42 |
| hold-interaction | 19 | 88 |
| ramp-first | 14 | 58 |
| **hold-all** | **11** | 129 |
| curve-descending | 1 | 9 |

Certified schedule lengths: 0×11 / 1×29 / 2×35 / 3×70 / 4×25 — and
**73/170 (43%) are PARTIAL subsets** of the affordable set.

**Design consequences:** (a) the value is not reachable through a
fixed-menu heuristic-shape classifier — a **learned pointer decoder over
candidates is justified** (the soft-emission vocabulary lean holds);
(b) *selection* (what to cast and what to hold back) carries as much
value as *ordering* — the v2 target must express "cast exactly these,
hold the rest", not just a sequence over everything; (c) **eleven pure
holds certified at h2** despite the ADR-0053 bias direction — restraint
is a real learnable action, not a measurement artifact.

## 2. Certification-rate strata — value concentrates where scheduling binds

- **resource_bound 31.3%** (136/434) vs unbound 22.8% (34/149) — the
  charter's premise measured: the rate is ~1.4× where demand exceeds
  capacity.
- By affordable-set size: n=2 → 26.8%, n=4 → 32.7%, n=6+ → **35.3%**
  (218 turns) — wider choice, more certifiable value; supports the
  ARM_CAP=16 spend on big sets.
- Mana-rock presence ~neutral (29% either way) at this resolution.

## 3. Divergence + payment-leg health

- Degrades are dominated by **veto** (forced-cast realization failing:
  56,354 arm-rolls) over **absent** (8,557) across all directed arms;
  selected arms: 1,680 veto / 631 absent, mean degrade point 44% through
  the schedule. The instrument note for the build: the realizer's
  targets/X fitting on masked single candidates is the binding
  interaction surface — follow/validity telemetry (the staged
  hard-execution evidence bar) should count exactly this class.
- **The payment executor was perfect at sweep scale: 25,570 directed
  executions, 0 salvages, 0 fails** (auto 11,800 non-consequential;
  costmod 9,072 out-of-scope per §12b). The M9 salvage-diagnosis genre
  can stand down at this resolution; float-then-apply is production-firm.

## 4. Natural slack (fork-1 free read — context only)

From the 170 certified positions at game end: natural mean win 57.0%
(the model is already ahead where it certifies), selected arm 63.3%
(the +5.7pp conversion), best-of-8 determinizations 81.8% — the last
confounds policy slack with library-order luck and is an envelope, not
a target.

## Not run (named, for the design session to fund or drop)

- Binned-gain by pre-turn critic score (the LordOfThePigs instrument) —
  needs critic inference over the sampled turns' obs; cheap GPU pass.
- Marginal-attribution read on the 200-turn auto-pay stratum (joint vs
  auto-pay super-additivity) — the rows exist in the sweep output;
  the read is a variant of stage1 with auto-arm ids.
