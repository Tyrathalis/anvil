# ADR-0051: P0 decision-delta probe — gate NOT MET; natural-variation dense labeling falsified, the antidote is search-shaped

- **Date:** 2026-08-10
- **Status:** accepted (pre-registered resolution; routing per the pin)
- **Design-doc anchor:** §4 (value targets), §6 (expert iteration), §3a (tier 3)
- **Inputs:** [m7-plan.md](../design/m7-plan.md) D1 (gate PINNED before
  numbers: split_frac ≥ 0.30 AND RMS true Δwr ≥ 0.10 + directional check);
  `scripts/decision_delta_probe.py`; run13-era fork stores
  (21 stores, 299 fork points, 2,392 completions) + old-era supporting
  read (run11-training drillmix stores: 797 points).

## Method (what the probe measured)

Within a fork point the K=8 sampled completions share an identical state;
classifying each by the drilled seat's first realized action (act-now vs
hold, land plays skipped, realization-based so no candidate-index
mapping) gives an unconfounded within-point outcome differential Δwr.
Aggregation subtracts binomial sampling variance (random-effects) to
estimate the true between-action signal.

## Results

| read | points | split-able (≥2/≥2) | split frac | RMS obs Δ | sampling var | **RMS true Δ** | directional (hta − act) |
|---|---|---|---|---|---|---|---|
| run13 era | 299 | 12 | **0.040** | 0.361 | 0.124 | 0.082 | −0.096 ± 0.072 |
| old era (support) | 797 | 52 | **0.065** | 0.335 | 0.115 | **0.000** | +0.024 ± 0.044 |

Sensitivity: ≥1/≥1 splits are only 7.4% / 10.5% — the starvation is not
an artifact of the ≥2 threshold.

## Verdict — gate NOT MET, on both arms, with a sharper diagnosis

1. **Diversity starvation:** the sampled policy is confident at ~95% of
   drilled decisions — natural variation at K=8 produces both actions
   almost nowhere. Natural-variation contrastive labeling (the C2b v1
   design) is starved at any plausible drill scale.
2. **Resolution starvation (the deeper failure):** where splits exist,
   observed differentials are pure sampling noise (old era: RMS true
   exactly 0). Power arithmetic: per-cell sampling variance ~0.115 means
   the RMS-true estimator's SE at n≈52 cells is ~0.023 in m² — a true
   RMS of 0.10 shifts m² by 0.01, ~0.4σ. **The pinned threshold is
   unreachable by this estimator at any split count the drill economy
   can produce. The method fails as an instrument, not merely as a
   result.**

## Routing (per the pre-registered pin)

The pin: if the true signal is unresolvable at this horizon, "the
antidote must be search-shaped — tier-3 moves up." The concrete minimal
object, now the D2 candidate:

- **Forced-branch paired rollouts at drilled decisions** — fork, force
  branch A (act) vs branch B (hold) as the first decision, K completions
  per branch with PAIRED seeds (twin machinery exists; pairing cancels
  shared downstream luck), Δwr per decision. This is simultaneously
  tier-3's first rung (1-ply search targets), the contrastive-pair
  generator design §6 always wanted, and the instrument that CAN measure
  what P0 could not (paired variance shrinks with K by construction —
  K is a dial, not a hope). Needs the forced-action harness feature
  (Java: scripted first decision post-fork) — scoped small in the design
  session, deliberately deferred then; now justified by measurement.
- **C2a (fork-point wr value targets)** is NOT falsified by P0 (it needs
  no action splits) but its mechanism premise — V accurate enough that
  bootstrap differentials rank actions — is exactly what P0 could not
  certify. It rides as a cheap bundled aux loss when a training run
  happens; it does not justify one alone.
- **C3 (§6c re-tune)** is untouched by P0 (its evidence is ADR-0049's
  telemetry) and stays necessary-but-insufficient.
- **D3 boundary re-decision:** the pin ("stability pass after P0
  clears") triggered on a clear that did not happen. The pass now rides
  with the forced-branch build — that build is fork-rollout-heavy, which
  is the same justification, and the forced-action feature is a harness
  change on the same surface.

## Standing lesson

Pre-registering the gate paid out in one session: the probe cost zero
box time, produced a decisive negative, and the routing was already
agreed before the numbers existed. Corollary recorded: when a gate's
threshold sits below an estimator's noise floor, the gate fails on
method — check resolvability against the pinned threshold at design
time, not after the scan.
