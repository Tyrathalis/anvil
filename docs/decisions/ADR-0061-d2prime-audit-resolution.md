# ADR-0061: M8 D2′ entry gate resolved — the rank-critic ordering audit PASSES (0.4205 vs pinned 0.35); era transfer survived; critic-ordered curation is FUNDED at pool scale 4×

- **Date:** 2026-08-17
- **Status:** accepted
- **Design-doc anchor:** m8-plan D2′ (pinned design + same-session
  threshold amendment, both user-approved before the gated data
  existed); ADR-0036 (the extrapolation caution this audit answers),
  ADR-0060 (the pivot that chartered it), ADR-0059 (the
  instrument-correction genre the report fix joins)

## Context

D2′'s entry gate asked whether `rank-critic-c2v3`'s ordering — trained
on pre-rebase c2 labels — survives into the current engine era on the
curation-anchor population it would actually rank. Design pinned
2026-08-17 before any generation; threshold amended 0.45 → 0.35 the
same session, BEFORE any audit labels, after the pipeline smoke's
validation read measured the **in-era, same-population benchmark at
0.377** on cycle-3's real K=8 labels (1,193 points, zero era
transfer) — re-referencing the gate to test era transfer rather than
the now-measured population-type gap (0.4833 holdout was a different
population). Recorded caveat at amendment: 0.377-vs-0.35 ≈ 0.6σ at
N=500; transfer-intact ordering reads below the pin ~25% of the time.

## Instrument

Fresh stock per the freshness principle: 3,197 games (seed base
20260818, 1,600/arm × 2 seats, argmax `iter-019` serving, 1.1h) →
1,434 losses → **622 calibrated-addressable candidates** (43% of
losses; 1.9× cycle-3's 332 — the pinned 2× pool). Audit sample: 500
anchor points seeded-uniform (seed 20260818) over the pool's 2,259
(game × anchor-turn) points, NOT band-filtered; K=8 rollouts via
`plan --anchor selected` / `generate` (~3,931 completions, ~40 min at
w=16); reader `scripts/rankcrit_audit.py` (validated pre-read on
cycle-3 labels).

**Instrument correction en route (the ADR-0059 genre):**
`grindstone report` joined labels **per game**, silently keeping one
fork point per mainline — cycle-3 never noticed (always one point per
game per run); the audit's multi-turn drillfiles lost 124 of 500
points on first read. The harness had fired everything (493 label
rows on disk, fp ordinals 0/1/2, fired turns exact); the fix keys the
join per (game, turn), preserving the re-drill supersede semantics.
Labels re-joined, no regeneration. First read (n=373, biased toward
one-point games) also PASSED at 0.4317 — the fix changed coverage,
not the verdict.

## What was measured (492 joined points, 0 trace misses)

| clause | pin | measured | verdict |
| --- | --- | --- | --- |
| Gate: Spearman(calibrated critic, K=8 `sel_wr`) | ≥ 0.35 | **0.4205** (SE_z 0.045 → ~1.85σ clear) | **PASS** |
| Pool-scale rule: largest scale within 5pp of 1× precision, cap 4× | — | 1× 0.593 · 2× 0.647 · **4× 0.699** · 8× 0.660 (rising through the cap) | **4×** |

Reference frame: in-era benchmark 0.377 · home holdout 0.4833 · blind
floor 0.27 · K=8 repeat ceiling 0.94. The measured 0.4205 sits ABOVE
the in-era benchmark — **era transfer cost the ordering nothing
measurable**; the fresh-era read lands between the in-era
curation-population number and the training holdout.

Descriptive (never gating): top-quartile in-band enrichment 0.675 vs
pool 0.549. Per-truth-bin Spearman (range-restricted, indicative):
winnable 0.260 (n=139), coin 0.165, long_shot 0.115, lost 0.093 —
notable because ADR-0036's calibrated-residual read named winnable the
blindest bin; on within-bin *ordering* the winnable bin is the
critic's best here. Calibration level: mean v_cal 0.499 vs mean wr
0.466.

## Decision

1. **The funded branch fires: critic-ordered curation**
   (`scripts/critic_select.py` — calibrated rank-critic score as the
   ordering/band-membership source, a2 quotas verbatim, band-centrality
   ordering within bands). The fallback (corrected-map composition) is
   not taken; the 492 banked labels join the standing calibration set
   either way (M5 invariant).
2. **Pool scale 4× per the pinned rule** — the selectivity curve
   RISES through the cap (no winner's-curse signature; the 8× dip is
   n=47, indicative only, recorded for future cycles). The
   pre-authorized top-up generation fires: +3,200 games at a fresh
   seed base (20260819), tripling addressable candidates to ~1,250,
   critic-ranked WITHOUT additional labels — that is the method.
3. **`grindstone report` per-point join fix is standing** — multi-turn
   drillfiles are now first-class; loud counts (`drills_planned` vs
   `drills_labeled`) make a recurrence visible.
4. Next per the pinned order: top-up stock → `critic_select` over the
   combined pool → **migration read** (standing gatekeeper) → the run
   (run11 recipe verbatim, init `iter-019`) vs **0.5373 ± 0.0112**.

## Consequences

- The ADR-0036 extrapolation caution is RESOLVED for this asset and
  era: rank-critic-c2v3 ordering transfers across the d798917ae5
  boundary undegraded on the curation population. The caution stands
  as a class (each future era re-audits — the instrument is now ~40
  minutes of box time end-to-end).
- The audit machinery (`rankcrit_audit.py` sample/read + the
  selectivity-curve rule) is a standing asset: any future
  score-vs-rollout-truth ordering question runs through it.
- Audit artifacts: `data/runs/m8-audit/` (sample, plan, labels,
  report); stock `data/runs/early-doom-m8-rankcrit` + the m8stock
  run/trajectory dirs — all training-era assets, kept.
- Cost postscript: stock 1.1h + labels ~40 min, both under estimate
  (the box ran ~3,500 g/h at w=16 vs the ~1,700 planning number).
