# ADR-0041: The extended ranking curve is FLAT with game diversity controlled — path B (representation work), design session next

- **Date:** 2026-08-07
- **Status:** accepted (verdict mechanical per the ADR-0039 procedure;
  the path-B build commitment waits on the design session's own ADR,
  user-gated per m6-plan D2-B)
- **Design-doc anchor:** §1 (card encoder — the component now under
  indictment), §4 (value heads), §6 (Grindstone)
- **Inputs:** [ADR-0039](ADR-0039-d1-frozen-probe-resolution.md) (the
  "between" verdict + the pre-registered flattening contingency),
  [ADR-0040](ADR-0040-d2a-labeling-reprice.md) (tranche economics),
  tranche decisions (m6-plan, user 2026-08-06: c2-only, K=8, mix
  mirrors map+sweep), `data/runs/drill-tranche-c2-offsets-20260806/`
  (component A), `scripts/tranche_b.py` + `drill-map-r11i019ext-k8` +
  `drill-tranche-c2-fresh` (component B),
  `data/runs/frozen-probe-ext2-c2/` (the final dataset, features,
  curve, and ablation).

## Question

ADR-0039 left one branch open: the frozen-trunk ranking curve was
rising at ~1.5K labels/era — label starvation and feature truncation
were indistinguishable. The pre-registered procedure: extend the curve
with a label tranche; "if it flattens in the 0.4–0.5 band, that IS the
flat-curve evidence path B's verdict was missing."

## Evidence

**Component A — same games, 2.2× labels** (4 offset arms o1/o3/o5/o6
over the full-bin map curation; 2,224 labels, 556/559 per arm; anchor
sweep behaves as the cycle-1 recovery profile predicts, wr 0.30→0.45 as
mean fired turn 13.4→8.7): c2/policy ridge curve 0.378 → 0.443 → 0.437
→ 0.449 → 0.465 → 0.456 → 0.457 (500 → 3.2K train labels). **Flat from
~2K.** Slope per doubling fell from +0.065 to ~+0.01–0.02 (holdout se
≈ 0.034).

**Component B — fresh game diversity** (1,600 fresh iter-019
eval-style games, seed base 20260806, through the unchanged standing
pipeline; fresh curation = 437 addressable losses; crash map wr 0.258 ≈
the original map's 0.229 — the population reproduces; 1,274 labels from
426 NEW loss-games): with c2 at 5,356 labels across 559 old + 426 fresh
games, the curve reads 0.361 → 0.453 → 0.434 → 0.427 → 0.446 → 0.449 →
0.459 → 0.454 → 0.455 (500 → 4.2K). **The plateau is unchanged at
2.8× ADR-0039's label count and ~1.8× its game diversity.**

**The diversity ablation** (ridge a=1000, identical holdout containing
24% fresh games, 3 deterministic subsample seeds): old-games-only vs
mixed training at fixed n — 0.432 vs 0.426 (n=2K), 0.444 vs 0.447
(n=3K). **Indistinguishable: fresh-game training diversity adds
nothing.** Game-saturation is excluded as the explanation for the
plateau.

Secondary reads, consistent throughout: d4 trunk plateaus lower
(~0.35–0.38); kNN climbs slowly with density but stays ≤0.38; ridge at
max alpha almost everywhere.

## Verdict: PATH B — representation-blind confirmed at the feature level

The frozen `[STATE]` representation's ceiling for ranking rollout truth
in the loss-adjacent population is **~0.45–0.46**, against a 0.94–0.97
repeat-measure ceiling. That is real signal (the trained value head
extracts only 0.27 of it — ADR-0039's head-blindness finding stands)
but the distance from 0.46 to 0.94 is not purchasable with labels: more
labels flat, more games flat, deeper probes no better than linear. What
the trunk computes from its frozen text-embedding inputs does not carry
most of the live-vs-dead distinction. Changing what the gradient sees
means changing the representation — §1/§4 encoder work, exactly path
B's world.

## Consequences

1. **Next step = the path-B design session** (m6-plan D2-B, its own
   ADR before any build): scope structured-feature enrichment targeting
   live-vs-dead correlates, partial trunk/fusion unfreeze during value
   training, and the §1 encoder-swap escape hatch — with
   dataset-boundary implications priced. Nothing is committed by this
   ADR.
2. **The probe benchmark becomes path B's acceptance gate.** The
   frozen assets (`frozen-probe-ext2-c2/`: 5,356-label c2 dataset,
   6,117-position feature dumps, deterministic split, the 0.455 ridge
   plateau) are a cheap pre-registered test: **any candidate
   representation must beat the 0.46 plateau on this exact benchmark
   before it earns a training run.** This converts the expensive
   path-B world into probe-first iteration — the milestone's
   probe-then-path pattern, recursively applied.
3. **Deferred items unlocked/parked accordingly:** the ADR-0015
   rollout-label campaign machinery stays parked (no distillation
   target worth training at Spearman 0.46); the fork stability pass
   remains pre-campaign (no campaign until path B produces a
   representation worth labeling for); D3 (curriculum arm) and D4
   (isotonic wiring) are unaffected and remain open.
4. **Label/store assets banked as era-scoped:** the fresh c2ext stores
   + dual-critic early-doom traces extend the standing calibration
   asset per the ADR-0036 rule (the label set grows with every
   map/sweep); `tranche_b.py` joins the standing tools (the
   fresh-population expansion recipe: generation → ingest → traces →
   curation → map+arms in one driver).
5. **Pool expansion stays deferred with sharper evidence:** the frozen
   text-embedding representation is now *measured* not-carrying
   in-distribution live-vs-dead; extending it to new cards before the
   representation question resolves would compound on a known-blind
   substrate.
