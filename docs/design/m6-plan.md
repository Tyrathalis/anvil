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

**RESOLVED 2026-08-05 ([ADR-0039](../decisions/ADR-0039-d1-frozen-probe-resolution.md)): INTERMEDIATE — rising, sample-limited.** Instrument: `scripts/frozen_probe.py` (features + probe passes); dump + report in `data/runs/frozen-probe-v1/`. Held-out Spearman at full size: policy trunk **0.395 (c1) / 0.455 (c2)**, d4 trunk 0.336/0.356 — every cell beats the reproduced critic floor (0.258–0.295 on this exact split) by +0.08–0.18, none approaches 0.7; curves rising in every policy-trunk cell (c2: 0.403→0.413→0.455), ridge at max alpha everywhere = sample-limited signature. The 2K curve point is unreachable within an era (~1.5K train labels/era) — the realized curve is 500→1K→~1.5K. Supplementary: trunk concat and +`[PLAN]` add nothing (trunks redundant); policy trunk out-ranks the full-vis critic trunk in both eras. Notable: linear probe 0.45 vs trained-head 0.27 on the same `[STATE]` vector — the critic's blindness was partly *head* blindness; probe-on-[STATE] is the standing way to ask "can the model see X?". **Per the pre-registered "between" procedure: D2-A labeling re-price runs first (the sanctioned ordering), then a label-expansion tranche (~5–10K/era) extends the curve where it is still rising; the path commitment waits on that extended curve.** D3 unaffected, can run in parallel.

### D2 — The chosen path, built and gated (the spine; placeholder until D1 resolves)

**Path A — rollout-label value targets / critic replacement:**

1. **Labeling re-price first:** ADR-0015's ~17 positions/h/worker (K=8) was measured through a batch-1 server, before GPU micro-batching and the w=16 + chunk-clamp recipe existed. Port the labeler serve path onto both; re-bench. The stale "50K labels ≈ 15 days" number is the one being retired; campaign sizing waits for the new number, and a critic distillation may need far fewer than 50K anyway.

   **DONE 2026-08-06 ([ADR-0040](../decisions/ADR-0040-d2a-labeling-reprice.md)): the labeler is engine-bound; "2–4× from micro-batching" falsified.** `scripts/bench_labeler.py` (dedup-correct; smoke = the parked `-points` mode's first post-rebase run, clean): 604 unique labels / 3.41h at w=16 = **11.1 pos/h/worker deduped (177/h fleet, 0.65× ADR-0015 per-worker; fleet ~1.3×)**; server batching fully engaged (sizes 2–16) — the cost is JVM game-playing (fork-block p50 124s, p90 223s at K=8), per ADR-0032's waiting-ceiling. 50K ≈ **11.8 days** (retired 15). **The measured cheap path is drill mode:** `drill-map-r11i19-k8` = 565 labels / 2.59h at w=8 = **27.3 pos/h/worker** (no mainline completion, exact replay to the fork turn) — loss-adjacent positions, exactly the ADR-0039 curve's population, are the *cheap* ones. **Tranche plan: generate in drill mode over expanded loss-adjacent positions; 5–10K/era ≈ 1–2 days of box time per era.** Crash tax measured: 0.77% completions, ~51 crash re-launches / 32 spans, ~12% duplicate rows — the D2-A.2 stability pass is now number-justified.
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

### Tranche decisions (user 2026-08-06, post-ADR-0040)

- **c2-only first** (iter-019 era): the era of record, the policy path A would train, and the cheapest position supply (run11 closing + run12 fresh-seed stores are all iter-019-era — no old-ckpt serving). c1 extension only if the extended c2 curve is ambiguous.
- **Fork-stability pass does NOT gate the tranche** (stays the pre-campaign gate): the measured tax (0.77% completion crashes, ~12% re-launch waste) costs a 5–10K tranche hours, not days; the tranche generates fresh crash repros for the pass for free.
- **K stays 8** (ceiling/noise constants comparable to the banked set).
- **Position mix mirrors the existing map+sweep shape** (anchor offsets around loss crashes, same curation filter) so extended curve points are comparable to ADR-0039's.

**Tranche status (2026-08-06):** Component A DONE — `drill-tranche-c2-offsets-20260806` (arms o1/o3/o5/o6 over the full-bin map curation, 556/559 each, 2,224 labels, ~9.6h at w=16; bins spread cleanly with anchor depth: wr 0.30→0.45 as mean fired turn 13.4→8.7). Extended c2 set = 4,082 labels (`frozen-probe-ext-c2/`, zero trace-join misses — the early-doom traces cover every turn). **Extended curve verdict-shaped but confounded: c2/policy ridge 0.378 → 0.443 → 0.437 → 0.449 → 0.465 → 0.456 → 0.457 (500→3.2K train labels) — FLAT from ~2K on, in the 0.4–0.5 band ADR-0039 pre-registered as path-B evidence — but the offset labels re-use the same ~550 games, so game-saturation isn't excluded.** Component B (the disambiguator) LAUNCHED same day: `scripts/tranche_b.py` — fresh iter-019 mainlines (2×800 eval-style arms, seed base 20260806) → ingest → early-doom traces (both critics) → fresh curation → crash map + o2/o4 arms (`drill-map-r11i019ext-k8` + `drill-tranche-c2-fresh`); smoke-validated end-to-end before launch. If the curve stays flat with fresh-game diversity added, the path-B verdict is clean; the path ADR waits on that read.

## Efficiency notes (deferred, measure-first — ADR-0040 riders)

The labeler is engine-bound: label price scales with game length and core count, not model or GPU — serve-side work is measured-closed for labeling. Levers on file for a future efficiency examination, none built now:

1. **Mainline early-stop for the sampling labeler** (cheap, mechanical): drill mode's 2.5× is mostly `-drillstop`; the sampler's targets cap at turn 16 while mainlines play to the end — an analogous stop-after-last-fork-point would close most of the gap if a distribution-matched campaign ever runs.
2. **Parallel K completions per fork point** (the big lever, needs a determinism proof): completions are independent games with order-independent derived seeds, and RNG routes through the determinism hooks' thread-locals — thread-per-completion could approach K× on fork blocks. Must pass a twin-determinism check; obs/forkobs writers need synchronization; concurrent bridge sessions are already supported.
3. **Label semantics are a 5–10× price knob**: §4's short-horizon rollout deltas (play N turns, not to game end) vs terminal outcomes — if path A lands, choose label semantics as part of the intervention design *with* its price, not after.
4. **Cheap headroom probes**: ~40% CPU idle at w=16 on 32 cores (workers capped at 2 procs each) — a w=24 labeling arm is one bench invocation; JVM boot amortization is minor.
5. **Drill-mode width sweep before any campaign-scale labeling** (w=8/12/16 at identical chunking): the c2 offset tranche measured w=16 drill mode at ~265 labels/h fleet vs the w=8 map's 218/h — 2× workers → only ~1.2× fleet (same sub-linear shape as ADR-0032's corrected generation sweep, w8 1280 / w16 1477). The knee is somewhere in 8–16; for a days-long path-A campaign the knee matters, and this read also makes the w=24 probe (note 4) unlikely to pay. Reminder: the pre-ADR-0032 "w=16 slower" reads were the retracted chunk-tail artifact — width comparisons only at ≥2 rounds/worker, identical chunking. (Tranche-side detail: drill launches span game *indices* at ~29% drill density, so chunk sizing against indices, not drills, is what sets rounds/worker.)

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
