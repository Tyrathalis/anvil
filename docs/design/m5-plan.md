# M5 plan — Grindstone cycle 2: the compounding question

**Date:** 2026-08-03 (seeded by [ADR-0034](../decisions/ADR-0034-m5-opening-sequence.md); structure confirmed by user same session — M5 is OPEN).
**Anchors:** [ADR-0033](../decisions/ADR-0033-m4-closeout.md) (M4 closeout + carried inventory); [ADR-0031](../decisions/ADR-0031-a2-resolution.md) (the cycle-1 win; the curation-staleness rule this milestone obeys); [ADR-0030](../decisions/ADR-0030-d3-experiment-a-resolution.md) (curriculum-composition mechanism); [ADR-0032](../decisions/ADR-0032-d4-serving-path-resolution.md) (w=16 recipe); [m4-plan.md](m4-plan.md) (the pattern this doc follows).
**Question answered:** does the drill loop compound — and if not, why not, precisely enough to decide what replaces cycling.

## The milestone in one paragraph

M4 proved one full Grindstone cycle produces an outside-noise win (+1.98pp ± 0.71). M5 runs the loop a second time from the promoted checkpoint's own losses and measures the slope: the user's ratchet hypothesis (fixed decisions move collapse points up-level; training on the *new* collapse points narrows toward a higher level of play) against the one-shot alternative (cycle 1 harvested a fixed error stock and a second pass re-finds residue). The design is deliberately near-verbatim — the only deltas from the cycle-1 winning run are the ones forced by promotion (init/pin iter-019), staleness (selection/evalset v3), throughput (w=16, behavior-neutral by construction), and seeds — because every other delta confounds the slope reading. The curation stage itself gives an early, cheap read: cycle-2's loss profile vs cycle-1's 584-loss profile says whether collapse points actually moved before a single training game is played. One promoted secondary that does NOT touch cycle 2: critic calibration against the ~1,900 banked K-rollout ground-truth labels, adopted for cycle-3 use only on measured improvement.

## Settled decisions (user 2026-08-03, recorded in ADR-0034)

1. M5 = cycle 2 now, for cross-pass comparability; headline = Δ2 vs Δ1.
2. Both slope verdicts are acceptable closes; a flat result must be decomposed (curation profile vs held-out transfer vs conversion trade), not just recorded.
3. Critic calibration = the promoted secondary, cycle-3-facing, Ante correctness riders attached.
4. Curation method verbatim from cycle 1 so the profile comparison is clean.
5. Escalation (b) parked unless flat-AND-signal-indicted.
6. **(Carried)** w=16 recipe; drill mainlines never ingest; D2.4 pairing protocol; fresh-seed tiebreaker; promotion on cleared gate; guards + watcher.

## Deliverables

### D1 — Cycle-2 curation, map, selection/evalset v3 (+ the migration read)

Substrate: `run11-i019-finalarm-s{0,1}` (2,000 games, standing seeds 20260710, obs on; iter-019 losses ≈ 940 games). Pipeline verbatim from cycle 1:

1. `early_doom` with the iter-019 critic (+ second-critic cross-check, the D2.1 shape) → curation.jsonl.
2. **The migration read (new, cheap, first):** cycle-2 profile vs cycle-1's — addressable fraction (was 61.2%), luck-locked share (18–38%), single-turn ≥30pp collapse count (208 across 82 decks), collapse-turn and peak-value distributions, deck overlap. Pre-registered reading: collapse points later/higher-value and addressable stock stable ⇒ ratchet-consistent; same windows re-surfacing on the same decks ⇒ one-shot-consistent. Recorded in the plan or an ADR *before* the run launches — this is the milestone's first evidence, not an afterthought.
3. K=8 ground-truth map (`grindstone plan|generate|report`) → anchor sweep on the lost bin (`drill_sweep.py`) → `grindstone select` (in-band per-game forks, later-supersedes labels) → **evalset v3** (~⅓ per bin bin-balanced holdout, baseline re-measure with `baseline_eval` pinned) → **selection v3** (holdout subtracted at the boundary; ahead-weight = whatever the released bins yield naturally, ~15–20% expected — NOT tuned, per the verbatim discipline).
4. Bookkeeping: v2 assets remain valid only for run11-era ckpts; iter-019 gets measured on both v2 and v3 so the eras chain.

Byproduct: the map + sweep labels roughly double the critic calibration set for D3.

#### Migration read — RECORDED 2026-08-04 (before any cycle-2 training)

Curation ran verbatim (decision 4): `early_doom` trace+analyze on
`run11-i019-finalarm-s{0,1}` with the iter-019 critic
(`early-doom-run11-i019`) + the d4-critic-fullvis cross-check
(`early-doom-run11-d4crit`); comparison computed by
`scripts/migration_read.py` (both critic pairings — the on-policy pair
is method-verbatim, the d4crit pair is the fixed-instrument control;
every number below replicates across both).

| Pre-registered quantity | Cycle 1 (run9) | Cycle 2 (run11-i019) |
|---|---|---|
| Substrate winrate | 0.5225 (954 losses) | 0.5303 (938 losses) |
| Addressable losses | 584 (61.2%) | **576 (61.4%)** |
| Luck-locked sweep (from turn 3, θ .30–.55) | 19.4–46.0% | 18.9–44.9% |
| Single-step ≥30pp collapses | 208 / 82 model-decks | 215 / 80 model-decks |
| crash_from_turn quartiles | 10 / 13 / 20 | 9 / 13 / 19 |
| peak_v mean | 0.723 | 0.726 |

Seed-level migration (substrates share the standing seeds, so games
match per (seat, seed) — same matchup + opener, different policy): of
cycle-1's 584 addressable losses, **28.9% converted to wins; 63.5% are
still addressable losses with the crash turn unmoved (median Δ = 0.0,
peak_v Δ +0.006)**; 35.6% of cycle-2's stock is new seeds. ≥30pp
collapse-deck overlap 68/82 (Jaccard 0.72). Same-instrument (d4crit):
29.3% converted, 66.6% retained, crash-turn Δ +0.04. **Memorization
check (supplementary, not pre-registered): drilled games converted at
28.9% vs undrilled 29.1% (z = −0.05)** — the cycle-1 gain was fully
general; drilling a game's collapse window did not preferentially fix
that game.

**Verdict against the pre-registered signatures: one-shot-consistent.**
The ratchet signature required collapse points later/higher-value with
the stock stable; the stock-stability half holds (576 ≈ 584) but the
migration half fails cleanly — every distribution (crash turn, peak
value, luck-locked share, collapse count) is unmoved, and two-thirds of
the same windows re-surface on the same seeds with the same crash
turns. The ambiguity risk did not materialize; this is the clean
one-shot profile. What cycle 1 actually did, per this read: a diffuse
general improvement that converted ~29% of the addressable stock
uniformly while the stock replenished at the same level — drainage, not
up-leveling. Recorded prediction (the read predicts, the run decides):
favors Δ2 < Δ1 with the binding constraint at transfer/conversion, NOT
stock (stock is undiminished, so D2's decomposition should not find a
stock shortfall). Sizing note resolved: 576 points ⇒ no selection-v3
shortfall vs the ~300-pt floor; the f≈20% rotation sizing carries over
unchanged.

### D2 — The cycle-2 run + the compounding read (the spine) — RESOLVED 2026-08-05 ([ADR-0035](../decisions/ADR-0035-d2-compounding-read-resolution.md)): **Δ2 = −0.58pp ± 0.73 (t=−0.79, 3,995 paired games) vs Δ1 = +1.98pp ± 0.71 ⇒ ONE-SHOT VERDICT.** Gate not cleared, no promotion (ckpt of record stays run11/iter-019, baseline 0.5316). Decomposition: stock undiminished, held-out transfer flat (drill-eval −0.2pp vs run11's +3.9pp), conversion trade returned — the migration read's pre-registered prediction held end to end. Successor lever = curriculum composition; escalation (b) stays parked (signal quality not indicted).

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

- ~~**The migration read may be ambiguous**~~ (RESOLVED 2026-08-04: it wasn't — clean one-shot profile, see the D1 migration read section).
- ~~**Fewer addressable losses than cycle 1**~~ (RESOLVED 2026-08-04: 576 vs 584 — no shortfall; rotation sizing carries over).
- **Seed reuse in the substrate:** the finalarm reads use standing seeds, so cycle-2 curation games share seeds (not games — the policy differs) with cycle-1's substrate. Drill provenance is per-game replay, so this is sound; noted so nobody "fixes" it.
- **Winnable residual (−5.1pp) is deliberately untouched in cycle 2.** If Δ2 lands marginal and the decomposition shows the residual widening, the composition levers (ahead-weight, per-bin slices) become cycle 3's first experiment — with the slope question already answered.
- **Two-front discipline:** serve-path and driver changes land only between runs (no-tree-edits rule); the w=16 adoption is already landed and mini-run-validated.

## M5 is done when

1. **Cycle-2 curation/selection/evalset v3 are online** and the migration read is recorded (collapse-point movement + addressable-stock change, against pre-registered signatures).
2. **The compounding read is resolved:** the cycle-2 run's paired gate vs 0.5316 with decomposition; the closing ADR records Δ2 vs Δ1 and the slope verdict — either direction closes honestly.
3. **Critic calibration is measured:** adopted for cycle-3 use or a documented negative.
