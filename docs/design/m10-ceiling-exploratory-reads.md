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

## 5. Auto-pay marginal attribution (funded + run at the build design session, 2026-08-26)

*Producer: `scripts/schedule_explore2.py marginal` (logic committed
`d55e348` before output was looked at) → `marginal-read.json` /
`marginal-perturn.jsonl`. 197 both-read marginal-stratum turns.*

- **Certification barely moves with payment mode**: joint 26.4%
  [20.7, 33.0] vs auto 23.9% [18.4, 30.3]; 2×2 = 43 both / 9
  joint-only / 4 auto-only / 141 neither. **83% (43/52) of
  joint-certified schedules also certify under Forge's auto-payer.**
- **Same-schedule twin deltas are a sparse one-sided tail**: 137/197
  exactly zero; 60 nonzero (35+/25−, median +0.25); **all 13 deltas
  with |d|≥2 are positive** (+2.1 … +11.9 composite).
- **Feasibility is a wash**: twin degrade rates 72.85% (joint) vs
  72.91% (auto) over all twin pairs — directed payment does not make
  schedules more executable at this resolution.

**Caveats:** the stratum is uniform and payment-consequential windows
run ~0.32/game vs 8.17 eligible/game, so ~96% of these turns never
contained a consequential payment decision — this measures payment's
marginal value ON SCHEDULING TURNS, not the standalone leg (+2.96pp/game
stands, separately measured). Detector-not-ranker applies to magnitudes.

**Design consequences:** (a) no h2-visible super-additivity — the joint
ceiling on uniform turns ≈ the schedule ceiling; (b) the sparse positive
tail is the ADR-0075 conditional shape again ⇒ payment supervision stays
on the 5,076-window conditional-label universe, and the v2 target's loss
should not be diluted making payment-assignment slots earn their keep on
uniform turns; (c) re-advertised actuation stays justified
(capabilities-over-fallback; executor perfect, cost ~0) but its value
story is the M9 number plus this sparse tail — say so in the build ADR.

## 6. Critic-binned gain (the LordOfThePigs instrument prototype — funded + run 2026-08-26)

*Producer: `scripts/schedule_explore2.py binned` — pre-turn critic
P(win) at the fork window, both critics per the early_doom convention
(era `iter-019/critic` + `d4-critic-fullvis`; cross-critic Spearman
0.98, all conclusions survive both) → `binned-read.json` /
`binned-perturn.jsonl` (per-turn values kept for re-binning). 583 read
turns / 170 positives.*

- **Certification rate is nearly flat across the value range** (quintile
  rates 25.9 / 29.1 / 26.1 / 32.5 / 32.2% on the era critic) —
  certifiable schedules exist everywhere, mildly more when ahead.
- **Conversion concentrates almost entirely in behind/contested
  states**: mean Δwr by era-critic quintile +11.7 / +16.7 / 0.0 / +4.6
  / −3.3pp (d4: +13.3 / +13.0 / +5.7 / +0.7 / −1.9). Split at v=0.45:
  **+14.1pp on 65 positives below vs +0.5pp on 105 above** — the whole
  +5.69pp stage-2 mean is carried by the behind stratum.
  Spearman(v, Δwr) = −0.21 / −0.19.
- The h2-vs-game-end mismatch is now LOCALIZED: the h2 margin detects
  board improvement everywhere, but improvement only converts where the
  game is contested — certified-when-ahead turns are real improvements
  that don't change outcomes.

**Design consequences:** (a) the binned-gain curve WORKS as a competency
instrument prototype — "where the competency lives" is a readable curve
(behind/contested states), candidate shape for the M10 competency read;
(b) label/curation lean: ~60% of certified turns sit where conversion
≈ 0 — game-end-conversion-aware weighting (or a pre-state critic gate)
concentrates seed supervision where value converts, worth a fork at the
label-design session (exploratory, n≈30–38/bin — routing signal, not a
pin); (c) the pre-turn critic rank-orders conversion better than the h2
margin (|−0.21| vs 0.109) — mining/prioritization should condition on
pre-state, not on h2 margin size.
