# ADR-0052: K-sizing read — instrument validated, per-decision Δwr below resolution; drill-map serving mismatch found

- **Date:** 2026-08-11
- **Status:** accepted
- **Design-doc anchor:** §6 (Grindstone / drill economy), §4 (value targets), m7-plan D2 pin 7

## Context

m7-plan pin 7 required a sizing read before any forced-branch campaign:
20–30 real drilled fork points at K ∈ {4, 8, 16} per branch, measuring the
paired SE of Δwr = wr_act − wr_hold against ADR-0051's noise-floor
arithmetic. The read ran on the cycle3 drill population (curation from
iter-019's losses, the ckpt of record) and, in resolving it, surfaced a
standing instrument defect that reframes several past verdicts.

## What was measured

**1. The forced-branch instrument is mechanically validated.** Across five
runs on the crash-anchored population and six on the corrected population
(~5,800 forced completions total): deterministic coverage funnel
(identical forced-point sets across K), 100%/94% pair completion, zero
completion crashes, zero act-skips on model-active winnable states, paired
SD measurably below the independent binomial floor (common random numbers
work), and the hold branch reproduces natural continuation (corr **0.885**
vs natural rollouts, means within 0.002).

**2. The drill map has not been measuring the source states (the serving
mismatch).** `grindstone generate` has always launched its server
`sample=False`. Argmax mainline replay of *sampled* source games diverges,
so map winrates priced argmax-continuation states, not the real
trajectories' states. Correct in the M4 era (argmax sources; the
plausible 23.7% map, 7/8 exact replay); silently wrong since curation
moved to sampled sources. Evidence on cycle3 crash-anchor points: map wr
**0.374** vs true (sampled-exact replay, natural K=16 rollouts) **0.062**,
per-point correlation **0.23**; fork-fire rate 75% (argmax-era map: 96%+
under matched serving). The training generation path (`--sample-forks`)
pins the same argmax mainline, so **drills trained on the same divergent
states the map priced** — internally consistent, but provenance-broken:
the curated failure frequently does not exist in the drilled state.

**3. True crash-anchored states are nearly dead.** 78% of fired points
0-for-16; band [0.25, 0.85] holds 9% of the population (mean true wr
0.06–0.08). The winnable band the selection machinery assumed exists — but
upstream: at crash−2 the same games are contested (mean true wr **0.491**,
52% band mass; crash−4: 0.522; peak: 0.556). Corrected maps for all three
anchors live in `data/runs/drill-map-cycle3-true/` (sampled mainline,
96%+ fire rate; `--sample-mainline` landed in `grindstone generate`,
`mainline_serving` recorded in map manifests).

**4. The corrected sizing read is still null — and now that is a real
verdict about the game, not the instrument.** On 59 forced points with
true wr in [0.25, 0.85] at crash−2 (both seats), pooled:

| | K=4 | K=8 | K=16 |
|---|---|---|---|
| SD(point Δwr) | 0.131 | 0.106 | 0.080 |
| indep binomial floor | 0.166 | 0.129 | 0.092 |
| var_signal → RMS true Δwr | 0 | 0 | 0 |

SD tracks 1/√K (pure sampling noise); mean Δwr ≈ 0 (+0.009/−0.004/−0.006,
n.s.); direction reads null both seats. Upper bound on RMS true Δwr at
K=16 ≈ 0.08 (conservative; likely < 0.05 given measured pairing
efficiency). The pinned 0.10 threshold is **not met at any K ≤ 16**, and
the scaling says larger K chases a signal that is small in truth:
single-decision cast-now-vs-hold deltas at drilled decisions are tiny even
at genuinely contested states.

**Coverage funnel for any future forced-branch campaign:** drilled → ~96%
fire (corrected serving) → ~33–40% model-seat-active (crash-anchor turn
parity; the pin-5 seat guard) → forced. Budget ~3× overshoot or filter
drill selection to model-active windows.

## Decision

1. **Pin 7 resolved: no forced-branch Δwr-label campaign at K ≤ 16.**
   Per-decision contrastive winrate labels are below the training-signal
   threshold pinned in m7-plan. C2b as designed (per-action Δwr targets)
   is falsified at affordable K on this population — consistent with
   ADR-0049's timing framing: the damage accrues across decision
   *sequences*; single-decision deltas don't carry it.
2. **The map-serving mismatch is fixed forward:** `--sample-mainline` is
   the required mode for maps over sampled-source curation;
   `mainline_serving` stamps the manifest. The forced-branch harness and
   the corrected three-anchor maps are standing assets.
3. **Blast-radius rule (standing lesson):** when an instrument bug is
   found, sweep past **null/flat** verdicts whose data crossed the buggy
   path, cost-ranked by what they still gate; positives survive (they
   happened despite the bug), nulls are suspect. Companion to ADR-0051's
   design-time resolvability check.

## Blast radius of the serving mismatch

| Verdict | Status |
| --- | --- |
| run11 +1.98pp (ADR-0031) | Survives; mechanism reread as **distributional supplementation** (mid-game/behind coverage), not case-content — the curated cases were largely absent from the drilled states. a→a2 composition flip, one-shot pattern, and migration-read prediction all consistent. |
| One-shot verdict (ADR-0035/0037) | Reread: applies to distributional supplementation. **Provenance-faithful case-drilling has never actually been tried.** M5/M6 pessimism partially priced against a broken instrument. |
| M6 strength-gate tie (ADR-0048) | Population-mislabeled curation ("best ever measured" was banded on divergent states). Verdict stands (no promotion) but strike its "curation exhausted" flavor from priors. |
| Winnable residuals (−5.1pp M4, −56pp ADR-0036) | Priced on fantasy states; re-derive from corrected maps if used again. |
| Critic ranking-blind (ADR-0036), c2 labelsets, rank-critic | Internally consistent (labels joined the replay runs' own obs windows) but describe argmax-replay states; transfer to real-game windows unverified. Note: corrected-map aggregate v_before 0.479 vs true wr 0.491 at crash−2 — first rollout audit on faithful states looks healthy at the mean. |
| P0 (ADR-0051) | Noise-floor arithmetic stands (estimator math). Population claim inherits the caveat; verdict unchanged (natural variation remains falsified — now doubly, by the forced read). |
| ADR-0049 credit-assignment verdict | Untouched (real stores, independent derivation). The two mechanisms compose: wrong states AND thin signal. |
| Paired strength reads, final_read, Ante, BC | Untouched (never cross the drill replay path). |

## Consequences

- **D2's candidate list re-forms for the user's routing decision:**
  (a) tier-3 search-derived targets (ADR-0051's standing fallback — search
  values aggregate over sequences, exactly where the signal lives);
  (b) corrected-population drill mixtures + C2a value targets from
  corrected maps (cheap: maps are trustworthy now; "case-drilling tried
  for the first time");
  (c) C3 §6c re-tune (untouched, still queued);
  (d) sequence-level contrastive labels (multi-decision branches) as the
  Δwr rescue — unpinned, needs a design round.
- The corrected maps make **C2a value targets** trustworthy for the first
  time on this population.
- Selection/evalset assets derived from divergent maps
  (drill-selection-v4 band values, sweep winrates) are era-marked
  suspect for reuse.
- The forced-branch harness remains tier-3's fork/eval substrate
  (branches + paired completions are the search primitive) even with
  Δwr labels dead.
- The reconstructed minimal source dirs (`cycle3-s0/s1` run.json +
  pairs.txt, sha-verified from drill-map manifest) stand in for the
  stale-data-pass deletions; future stale-data passes keep source
  `run.json` + `pairs.txt` (bytes, not GB) when downstream tooling may
  replay.
