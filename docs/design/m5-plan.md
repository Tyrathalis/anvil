# M5 plan — Grindstone cycle 2: the compounding question

**Date:** 2026-08-03 (DRAFT — seeded by [ADR-0034](../decisions/ADR-0034-m5-opening-sequence.md); structure pending user confirmation at the next working session).
**Anchors:** [ADR-0033](../decisions/ADR-0033-m4-closeout.md) (M4 closeout + carried inventory); [ADR-0031](../decisions/ADR-0031-a2-resolution.md) (the cycle-1 win; the curation-staleness rule this milestone obeys); [ADR-0030](../decisions/ADR-0030-d3-experiment-a-resolution.md) (curriculum-composition mechanism); [ADR-0032](../decisions/ADR-0032-d4-serving-path-resolution.md) (w=16 recipe); [m4-plan.md](m4-plan.md) (the pattern this doc follows).
**Question answered:** does the drill loop compound — and if not, why not, precisely enough to decide what replaces cycling.

## The milestone in one paragraph

M4 proved one full Grindstone cycle produces an outside-noise win (+1.98pp ± 0.71). M5 runs the loop a second time from the promoted checkpoint's own losses and measures the slope: the user's ratchet hypothesis (fixed decisions move collapse points up-level; training on the *new* collapse points narrows toward a higher level of play) against the one-shot alternative (cycle 1 harvested a fixed error stock and a second pass re-finds residue). The design is deliberately near-verbatim — the only deltas from the cycle-1 winning run are the ones forced by promotion (init/pin iter-019), staleness (selection/evalset v3), throughput (w=16, behavior-neutral by construction), and seeds — because every other delta confounds the slope reading. The curation stage itself gives an early, cheap read: cycle-2's loss profile vs cycle-1's 584-loss profile says whether collapse points actually moved before a single training game is played. One promoted secondary that does NOT touch cycle 2: critic calibration against the ~1,900 banked K-rollout ground-truth labels, adopted for cycle-3 use only on measured improvement.

## Settled and proposed decisions (ADR-0034)

1. **(User-agreed)** M5 = cycle 2 now, for cross-pass comparability; headline = Δ2 vs Δ1.
2. **(User-agreed)** Both slope verdicts are acceptable closes; a flat result must be decomposed (curation profile vs held-out transfer vs conversion trade), not just recorded.
3. **(Proposed)** Critic calibration = the promoted secondary, cycle-3-facing, Ante correctness riders attached.
4. **(Proposed)** Curation method verbatim from cycle 1 so the profile comparison is clean.
5. **(Proposed)** Escalation (b) parked unless flat-AND-signal-indicted.
6. **(Carried)** w=16 recipe; drill mainlines never ingest; D2.4 pairing protocol; fresh-seed tiebreaker; promotion on cleared gate; guards + watcher.

## Deliverables

### D1 — Cycle-2 curation, map, selection/evalset v3 (+ the migration read)

Substrate: `run11-i019-finalarm-s{0,1}` (2,000 games, standing seeds 20260710, obs on; iter-019 losses ≈ 940 games). Pipeline verbatim from cycle 1:

1. `early_doom` with the iter-019 critic (+ second-critic cross-check, the D2.1 shape) → curation.jsonl.
2. **The migration read (new, cheap, first):** cycle-2 profile vs cycle-1's — addressable fraction (was 61.2%), luck-locked share (18–38%), single-turn ≥30pp collapse count (208 across 82 decks), collapse-turn and peak-value distributions, deck overlap. Pre-registered reading: collapse points later/higher-value and addressable stock stable ⇒ ratchet-consistent; same windows re-surfacing on the same decks ⇒ one-shot-consistent. Recorded in the plan or an ADR *before* the run launches — this is the milestone's first evidence, not an afterthought.
3. K=8 ground-truth map (`grindstone plan|generate|report`) → anchor sweep on the lost bin (`drill_sweep.py`) → `grindstone select` (in-band per-game forks, later-supersedes labels) → **evalset v3** (~⅓ per bin bin-balanced holdout, baseline re-measure with `baseline_eval` pinned) → **selection v3** (holdout subtracted at the boundary; ahead-weight = whatever the released bins yield naturally, ~15–20% expected — NOT tuned, per the verbatim discipline).
4. Bookkeeping: v2 assets remain valid only for run11-era ckpts; iter-019 gets measured on both v2 and v3 so the eras chain.

Byproduct: the map + sweep labels roughly double the critic calibration set for D3.

### D2 — The cycle-2 run + the compounding read (the spine)

`d6-run12` = run11 recipe **verbatim** except: init + critic + mainline pin `d6-run11/iter-019`, `--drill-selection` v3, `--workers 16` (chunk ceiling 30, per-batch clamp), fresh seed base, `--drill-eval-every 10` (the mid-run kill/continue read, now a standing driver phase). 20 iterations ≈ 12 h at the w=16 rate. Guards + self-registered watcher.

Gate and headline: standing 2,000-game paired read vs **0.5316** (fresh-seed confirmation if marginal, per the standing tiebreaker) + evalset-v3 decomposition on candidates. The closing ADR reports **Δ2 against Δ1 = +1.98pp ± 0.71** with the slope verdict:

- **Δ2 ≈ Δ1 or better** ⇒ ratchet live; price cycle 3 and decide whether cycling becomes the standing cadence.
- **Δ2 positive but clearly smaller** ⇒ diminishing returns; the decomposition + migration read say whether the binding constraint is stock (fewer addressable losses), transfer (held-out gains shrink), or conversion (winnable-class regression returns) — which respectively point at pool/expressiveness, escalation (b), and the curriculum-composition levers.
- **Δ2 ≈ 0** ⇒ one-shot verdict; same decomposition decides the successor; escalation (b) unparks only on the signal-quality branch (ADR-0034 decision 5).

### D3 — Critic calibration (promoted secondary, cycle-3-facing)

The banked ground truth (~1,900 labels from the cycle-1 map + sweep, plus D1's new labels) vs the critic that read 0.58 where rollouts said 0.24. Bounded: a calibration/fine-tune pass on the label set, measured on held-out labels (calibration error + rank correlation), against the current eval/Ante critic as baseline. Adopt for cycle-3 curation/eval on demonstrated improvement; documented negative otherwise. Explicitly firewalled from cycle 2 (no recipe delta). Riders attached if it lands: the M4-carried Ante correctness items (draw-poison coverage 69%, re-deal re-anchoring, node-level draw bias). Also the natural home for mechanizing the "value function continuously audited against rollouts" invariant (every future map/sweep run appends to the calibration set).

## Riders and watches

- **Upstream watches unchanged:** #11285 (+ queued #11360 comment as the nudge); consolidation follow-up only on maintainer engagement; connive-lines conflict expected at next rebase (drop ours).
- **Carried fork items:** targeting-retry hang forensics; MayPlay `.get(0)` fix (folds into the consolidation question); MinMaxBlocker realizer gap; IndexOOB class (fresh repro banked by `d4-w16val`).
- **Playable-fork + Chronicle:** separate tracks (Chronicle next = D3 iteration + D4 SDK decision).

## Risks and open questions

- **The migration read may be ambiguous** (profiles partially shifted). Pre-registering the two clean signatures (D1.2) limits post-hoc storytelling; an ambiguous profile is reported as such and the run still decides.
- **Fewer addressable losses than cycle 1** would shrink the selection below the f≈20% rotation's appetite (409 pts fed ~23 iters at 15/iter). If selection v3 lands under ~300 pts, the rotation shortens or ppi drops — a sizing note, not a blocker; record whichever adjustment is made.
- **Seed reuse in the substrate:** the finalarm reads use standing seeds, so cycle-2 curation games share seeds (not games — the policy differs) with cycle-1's substrate. Drill provenance is per-game replay, so this is sound; noted so nobody "fixes" it.
- **Winnable residual (−5.1pp) is deliberately untouched in cycle 2.** If Δ2 lands marginal and the decomposition shows the residual widening, the composition levers (ahead-weight, per-bin slices) become cycle 3's first experiment — with the slope question already answered.
- **Two-front discipline:** serve-path and driver changes land only between runs (no-tree-edits rule); the w=16 adoption is already landed and mini-run-validated.

## M5 is done when

1. **Cycle-2 curation/selection/evalset v3 are online** and the migration read is recorded (collapse-point movement + addressable-stock change, against pre-registered signatures).
2. **The compounding read is resolved:** the cycle-2 run's paired gate vs 0.5316 with decomposition; the closing ADR records Δ2 vs Δ1 and the slope verdict — either direction closes honestly.
3. **Critic calibration is measured:** adopted for cycle-3 use or a documented negative.
