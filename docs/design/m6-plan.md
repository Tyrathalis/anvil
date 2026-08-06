# M6 plan — the representation question

**Date:** 2026-08-05 (seeded by [ADR-0038](../decisions/ADR-0038-m6-opening-sequence.md); structure user-agreed same session — M6 is OPEN).
**Anchors:** [ADR-0037](../decisions/ADR-0037-m5-closeout.md) (M5 closeout + scoping inputs); [ADR-0036](../decisions/ADR-0036-d3-critic-calibration.md) (ranking blindness — the measurement this milestone answers); [ADR-0035](../decisions/ADR-0035-d2-compounding-read-resolution.md) (one-shot verdict); [ADR-0015](../decisions/ADR-0015-d4-closeout.md) (the parked rollout-label machinery); [ADR-0033](../decisions/ADR-0033-m4-closeout.md) (carried fork inventory); [m5-plan.md](m5-plan.md) (the pattern this doc follows).
**Question answered:** can we change what the gradient sees — and does that reopen improvement?

## The milestone in one paragraph

M5 measured why the drill loop is one-shot: the value signal is representation-blind exactly where the drills mine (held-out Spearman 0.26–0.29 vs a 0.94–0.97 repeat-measure ceiling, surviving perfect recalibration, global across decks and turns). M6 is built around one cheap deciding experiment and two placeholder paths for reacting to it. The probe (D1): can *anything* learn to rank the 3,750 banked K=8 rollout labels from frozen trunk features? If yes, the features carry the live-vs-dead distinction and the critic's outcome-label training was the bottleneck — path A: unpark the ADR-0015 rollout-label machinery, re-price labeling on the modern serve stack, and train a ranking-capable value signal. If no, the representation itself is blind — path B: encoder work (feature enrichment / partial unfreeze), scoped by its own design session before anything is committed. Alongside, the proven cheap lever (curriculum composition, winnable residual −5.1pp) runs as its own attribution-clean arm, and the isotonic map adopted in ADR-0036 gets wired into the curation tooling. Headline close = the standing paired gate vs **0.5316**, honest in either direction. Pool expansion stays deferred — the probe doubles as the first measured evidence for when the frozen text-embedding representation can safely carry new cards.

## Settled decisions (user 2026-08-05, recorded in ADR-0038)

1. Probe-then-path structure; headline gate vs 0.5316; both directions honest closes.
2. Probe thresholds pre-registered: Spearman ≥ ~0.7 rising ⇒ path A; ≤ ~0.4 flat ⇒ path B; between ⇒ price both. Learning-curve + sample-efficient-probe guard against the small-N false negative.
3. Curriculum composition = an independent arm inside M6, never folded into the D2 run.
4. Efficiency posture: labeling re-price is the one efficiency item with a guaranteed customer; in-loop levers stay closed by measurement (ADR-0032); no iteration pipelining; no eval thinning (run12 seed-half lesson).
5. Disk pass = opening chore with user sign-off on the kill list.
6. Pool expansion deferred pending the probe's evidence.
7. **(Carried)** migration read gatekeeps cycle pricing; ranking-from-rollouts; era-scoped assets; combined paired read + fresh-seed tiebreaker; drill mainlines never ingest; no tree edits during runs; guards + watcher.

## Deliverables

### D1 — The frozen-trunk ranking probe (the deciding experiment, first)

Substrate: the 3,750-label calibration set (`data/runs/critic-calibration-v1/` inputs; 1,879 cycle-1 / 1,871 cycle-2, zero trace-join misses), reusing `critic_calibration.py`'s deterministic 80/20 game split and era discipline.

1. **Feature dump path (the only build item):** frozen trunk pooled features at each labeled position, from BOTH trunks — the on-policy `iter-019` policy trunk (masked input) and `d4-critic-fullvis` (full-vis input, the curation instrument). Rides the existing trace join.
2. **Probe family:** ridge/linear and k-NN (sample-efficient) + a small 2-layer MLP head. Per-era fit/eval; pooled only if per-era results agree.
3. **Learning curves** at 500 / 1,000 / 2,000 / all training labels — the guard that separates "features don't carry it" from "3,000 labels aren't enough."
4. **Pre-registered readings** (comparison constants: critic floor 0.27, repeat-measure ceiling 0.94–0.97):
   - Held-out Spearman **≥ ~0.7 and rising** ⇒ **path A** — the features carry live-vs-dead; the outcome-label training was the problem. D2 = rollout-label value work.
   - **≤ ~0.4 and flat** across all probes and curve points ⇒ **path B** — representation-blind confirmed at the feature level. D2 = encoder work, design session first.
   - **Between** ⇒ record the curve shapes, price both paths, decide by cost. (If the curve is rising but low, cheap label expansion after the D2-A re-price can extend it before committing — noted as the one legitimate reason to run the re-price before the path verdict.)

Resolution = an ADR with the path verdict and curve evidence.

### D2 — The chosen path, built and gated (the spine; placeholder until D1 resolves)

**Path A — rollout-label value targets / critic replacement:**

1. **Labeling re-price first:** ADR-0015's ~17 positions/h/worker (K=8) was measured through a batch-1 server, before GPU micro-batching and the w=16 + chunk-clamp recipe existed. Port the labeler serve path onto both; re-bench. The stale "50K labels ≈ 15 days" number is the one being retired; campaign sizing waits for the new number, and a critic distillation may need far fewer than 50K anyway.
2. **Fork stability pass = the pre-campaign gate** (carried ADR-0033 inventory, conditioned on path A because at campaign scale hangs are throughput): IndexOOB class (fresh repro banked by `d4-w16val` iter-000), targeting-retry hang forensics, MayPlay `.get(0)`, MinMaxBlocker realizer gap.
3. **The intervention itself** (exact form set by an in-milestone decision once the re-price lands): a ranking-capable value signal trained on rollout labels — as a distilled critic replacement for curation/eval, and/or as in-loop drill-regime value targets per design §4 ("short-horizon rollout deltas as value targets, task-token flagged"). Then a training run consuming it.
4. **Gate:** standing 2,000-game combined paired read vs 0.5316 (fresh-seed tiebreaker on marginal t) + evalset-v3 decomposition. Ante riders trigger (D4).

**Path B — encoder / representation work:** commits nothing until a dedicated design session scopes the options (structured-feature enrichment targeting live-vs-dead correlates; partial trunk/fusion unfreeze during value training; the §1 encoder-swap escape hatch) with dataset-boundary implications priced. The session's output is its own ADR; the build follows it. This branch is deliberately under-specified here — it is the expensive world, and speccing it before the probe says we live there would be planning theater.

### D3 — Curriculum-composition arm (proven cheap lever, independent)

Recompose **selection v3** (still valid — M5 promoted nothing, so v3 remains iter-019-era and the curation-staleness rule is satisfied) against the winnable residual: ahead-weight and per-bin slice stratification, targeting the −5.1pp held-out winnable gap (ADR-0031) and the conversion trade that returned in run12 (winnable −4.7pp at iter 19). Own run, own gate read vs 0.5316, never combined with D2's lever — attribution discipline is the point. Can proceed while D2 machinery builds (it needs nothing new). Migration read not required (not a new curation cycle; it recomposes existing v3 stock).

### D4 — Riders

- **Isotonic wiring (early, unconditional):** plumb the era-scoped isotonic maps (ADR-0036 adoption) into `early_doom` / curation / doom-labeling tooling so every future curation consumes calibrated absolute values by default. Small item; lands before any new curation runs.
- **Ante correctness items** (carried since ADR-0015: draw-poison rule skips 69% of draws; re-deal opener re-anchoring; node-level draw bias on the draw class): attached to any critic replacement path A produces, per ADR-0036 decision 5.

### Opening chore — the disk pass

~150G of `data/runs` (213G total) is six forensic dumps from closed runs — every question they answered has a closed ADR: `d6-run2-i000` 23G + `d6-run2-i005` 30G (entropy collapse, ADR-0017), `d6-run4-i000` 26G + `d6-run4-i001` 20G (feature-alone control, ADR-0022), `d6-run9-i002` 18G (adaptation probe, ADR-0028), `d6-run11-i011` 22G (mid-run diagnostic of a closed-verdict run), `d6-run10-i007` 7.4G, plus `_bench_scratch` 889M and `_contaminated` 420M. Procedure: inventory each dir → confirm nothing ADR-referenced or calibration-feeding inside → kill list → **user sign-off** → delete or zstd cold-archive (user's choice). Kept unconditionally: ckpts of record, all drills.jsonl dirs, selection/evalset assets, baseline-era finalarm/confarm stores, Ante certification records. Hygiene, not necessity (2.3T free).

**DONE 2026-08-05 (user signed off: delete all nine).** Verification before the list: zero operational references in `docs/decisions/`, `scripts/`, `anvil/` (only `bench_learner.py:146`, which recreates `_bench_scratch`); `critic_calibration.py`/`migration_read.py` read only from `critic-calibration-v1`, `drill-map-*-k8`, `drill-evalset-v2/v3`, `drill-selection-v2`, `drill-sweep-*`, `early-doom-*` — none inside a candidate; no drills.jsonl/ckpt/selection/evalset assets or symlinks inside any candidate; ckpts of record confirmed under the separate `data/training/` tree. Bulk anatomy: each dump's weight was one worker's forensic `census.jsonl` (17–26G). Deleted plain (no cold archive): the seven dumps + `_bench_scratch` + `_contaminated`; `data/runs` 213G → 68G (~145G freed).

## Riders and watches

- **Upstream watches unchanged:** #11285 (+ queued #11360 nudge); consolidation follow-up only on maintainer engagement; connive-lines conflict expected at next rebase (drop ours).
- **Playable fork + Chronicle:** separate tracks (Chronicle next = D3 iteration + D4 SDK decision).
- **Explicitly deferred in M6:** pool expansion (the probe is its readiness evidence); iteration pipelining (on-policyness recipe delta); eval thinning (seed-half lesson); escalation (b) remains parked (ADR-0035: signal quality not indicted).

## Risks and open questions

- **The probe can false-negative on sample size** — mitigated by the sample-efficient probe family and learning curves; a "blind" verdict requires flat curves, not a low endpoint. If intermediate, the labeling re-price (cheap) can fund label expansion before the path commitment.
- **Path B is open-ended by nature.** The design-session gate exists precisely so M6 doesn't wander into encoder work without a scoped bet; if B is the verdict, expect the session to produce its own ADR before any build.
- **The probe measures ranking on the *curated-loss* population.** A head that ranks there still needs the in-loop wiring question answered (replace the curation critic, feed value targets, or both) — that decision is deliberately deferred to post-re-price, when the cost of more labels is known.
- **Two-front discipline:** serve/driver/labeler changes land only between runs (no-tree-edits rule), mini-run-validated like the w=16 adoption.
- **Era discipline:** all label fits per-era; rollout truth is policy-conditional.

## M6 is done when

1. **The frozen-trunk ranking probe is resolved** against the pre-registered readings — path verdict (A / B / priced-intermediate) recorded in an ADR with learning-curve evidence.
2. **The chosen path's intervention is built and gated:** standing 2,000-game combined paired read vs 0.5316 + evalset-v3 decomposition; either direction closes honestly.
3. **The curriculum-composition arm is measured** as an independent run with its own gate read.
4. **Isotonic wiring is landed** in curation/doom tooling; Ante riders landed or documented-deferred with the critic outcome.
