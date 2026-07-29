# M4 plan — Grindstone: a different signal source

**Date:** 2026-07-28. **Anchors:** [ADR-0027](../decisions/ADR-0027-m4-opening-sequence.md) (this plan's seed — opening sequence + user decisions); [ADR-0026](../decisions/ADR-0026-m3-closeout.md) (M3 closeout, standing agenda); [ADR-0024](../decisions/ADR-0024-run8-batch-lever.md) (the absent-signal diagnosis this milestone answers); [ADR-0025](../decisions/ADR-0025-d4-rebase-closeout.md) (re-baseline; the mechanism question D1 resolves); `data/runs/early-doom-run7b-{i14,d4crit}/` (curation method + old-scale list); design doc §6 (Grindstone), §7 (Ante); [m3-candidates.md](m3-candidates.md) (leftover menu); [m3-plan.md](m3-plan.md) (the pattern this doc follows).
**Question answered:** what M4 builds, in what order, and what closes it — such that the training loop gains a signal source that reaches the measured headroom the standing recipe cannot, on the engine we actually live on, without the generation cost silently eating the milestone.

## The milestone in one paragraph

M3 closed with a precise negative: the standing recipe (§6d mix + §6c penalty + §6f critic @ lr 1e-5) is at its ceiling, and the ceiling is not luck (early-doom: ~60% of losses addressable) — it is *absent signal* in near-tie windows whose advantage is a coin flip no amount of averaging fixes (ADR-0024). M4's spine is Grindstone v0: mine the value-crash windows from real losses, replay-and-fork to those positions with the machinery the fork already carries, and feed position-initialized games back into the loop — K outcomes from the same position collapse advantage variance exactly where the diagnosis says signal is missing. Because drill positions only replay on the engine that produced them, the milestone opens by re-grounding everything on the rebased fork: a cheap adaptation probe that doubles as the resolution of the re-baseline mechanism question (opponent-fit vs stronger heuristic) and produces the new-engine stores curation needs. In parallel, one promoted infrastructure deliverable: the serving path, now ~80% of run cost, gets profiled and improved so the milestone's many runs don't pay a hidden tax. Upstream stays watch-paced; expressiveness stays deferred.

## Settled decisions (user 2026-07-28, recorded in ADR-0027; consequences here)

1. **Identity: split, Grindstone spine.** The strength program is the spine; infrastructure gets one promoted deliverable (D4) by explicit user preference — efficiency work mixed in, not deferred until the grind hurts. Upstream is a watch, not a track: the queued #11360 complementarity comment (doubling as the #11285 review nudge), the consolidation follow-up only if maintainers engage.
2. **D1 is a run, not a read.** The re-baseline mechanism question resolves under training (opponent-fit is recoverable; a stronger heuristic is not) — no standalone decomposition read. Interpretation pre-registered in ADR-0027; the probe's byproducts (new-engine stores, closing read, adapted-or-not baseline) are D2/D3 inputs regardless of which way it resolves.
3. **Signal source (a) first — drill-mixed generation.** The learner does not change in the first pass; drills enter as generation-side position-initialized games mixed at a controlled fraction. (b) K-rollout advantage baselines and (c) per-action contrastive/expert-iteration are the documented escalation, in that order, entered only on a resolved-negative or resolved-insufficient (a).
4. **Grindstone v0 scope: no LLM filter, no ddmin.** Stages 3–4 of design §6 wait for a demonstrated-signal pass. Provenance tracing (source game seed, store, window, generating ckpt) is invariant and non-negotiable from day one.
5. **Track C expressiveness deferred** (mode heads, AR combat decoder, pool breadth) — re-entry only on telemetry that indicts expressiveness.
6. **Carried rules:** every M4 run generates on fork `master` @ `5fbc2ac98d`; no pre-rebase store ever mixes into training; the falsified-lever ledger (temperature, batch, feature-alone) is planned *against*, not re-probed without a stated post-rebase reason; promotion protocol = paired 2,000-game Ante-corrected `final_read`; guard suite standing on every run.

## Deliverables

### D1 — New-engine grounding: the adaptation probe (`d6-run9`)

Standing recipe **verbatim** (run-7b config: lr 1e-5, 480 g/iter, heur_frac 0.5, penalty 0.02, re-ask, critic-steps 2000, guards), init `run7b/iter-014/{train,critic}`, rebased fork, fresh seed base, ~10 guarded iterations, arms every 5. Post-collate cost ≈ one overnight (generation ~25 min + train ~8 min per iteration).

- **Pre-registered interpretation:** arms recover toward ~0.55 vs the new heuristic ⇒ the −4pp was opponent-specific fit (§6d family); the adapted checkpoint is promoted (2,000-game paired read) and becomes the M4 baseline. Arms flat ⇒ the heuristic got stronger; 0.5121 stands as the honest floor. Partial recovery ⇒ both mechanisms real; record the split.
- **Closing read doubles as D2 substrate:** the 2,000-game read keeps obs on (standing rule) and its stores feed curation regeneration; the probe's own critic (new-engine-trained) generates the value traces.
- **Deliverable artifacts:** run record + ADR resolving the re-baseline mechanism question; the M4 baseline number; fresh new-engine self-play stores.

### D2 — Grindstone v0: curated-position drills end-to-end

1. ~~**Curation regeneration, new engine:** rerun `early_doom.py` + curation on D1's closing read.~~ **DONE 2026-07-29 (records `data/runs/early-doom-run9-{i009,d4crit}/`):** the shape survived the rebase almost exactly — **584 addressable losses (61.2% of 954; old scale 531/59.6%), doom ceiling 0.82–0.91, luck-locked 18–38%**; 208 single-turn ≥30pp collapses across 82 model decks (old: 185/102), median crash turn 13, median drop 25.5pp. Two-critic agreement (run9-i009 critic vs `d4-critic-fullvis`) within **0.3pp** on every headline number. The new-engine drill seed list is live: `early-doom-run9-i009/curation.jsonl`.
2. **Drill machinery = re-aim the parked D4 rollout apparatus:** replay the source game (seed + generating ckpt, twin-determinism-certified) to the curated crash window, fork, and play completions with per-completion library re-randomization — `-rollout K -points M` already does all of this at *sampled* windows; v0 feeds it *curated* (store, g, window) targets instead. New: a drill manifest format (provenance: source seed, store, window, ckpt, crash metadata), harness verb to generate from a manifest, ingest of drill games into a store with a `drill` provenance tag.
3. **Re-price the economics under micro-batching.** The 17 positions/h/worker figure is batch-1-era; the micro-batched server does ~189 rps. A drill game is a *partial* game (fork at turn ~15 of ~20) — cheaper than a full game, not 33× more expensive. Measured price goes in the plan for D3's mixing fraction.
4. **Drill eval suite (the frozen-anchor seed, §6):** a fixed held-out drill set with per-drill winrate/value tracked per checkpoint — the per-mechanic regression instrument, small and standing.

Deliberately out (ADR-0027): LLM filter, ddmin/wildcarding, hand-constructed seeds for unminable cards, skill conditioning.

### D3 — Signal integration (a): drill-mixed generation runs

Mix drill-generated games into the V-trace iteration store at fraction f (opening pin: modest, e.g. 10–25% of games/iteration — priced by D2.3; the exact pin is a launch-time decision recorded in the run config). Learner unchanged; μ records, re-ask, guards, §6 anomaly monitor all standing. Drill games are position-initialized: value/return from mid-position is well-defined (terminal reward, V-trace indifferent to episode start), and the store already carries provenance to keep drill and full-game trajectories distinguishable.

- **Watch items, pre-registered:** distribution shift toward drill contexts (the standing 400-game arms are the regression guard — drills must not buy drill-winrate at full-game cost); drill-fraction sensitivity (one knob, priced before swept); staleness (drills mined from checkpoint N trained into checkpoint N+k — refresh cadence is a finding, not a pin).
- **Escalation path if (a) resolves negative/insufficient:** (b) K-rollout advantage baselines at pivotal windows (per-position multi-outcome baselines — the direct variance-collapse mechanism; moderate learner surgery); then (c) per-candidate-action rollouts → contrastive/AWR labels (design §6 expert iteration; gated behind critic calibration + the anchoring trickle; never train on unverified model-advised trajectories).
- **The gate is the standing promotion protocol:** paired 2,000-game Ante-corrected read vs the D1 baseline.

### D4 — Serving-path throughput (promoted infrastructure)

Generation is ~80% of run cost; w=8 saturates ~189 rps; 5.3 ms/request for a 42M model points at per-request Python overhead (featurization/gRPC), not GPU compute. Protocol, in order:

1. **Noise floor first** (the ADR-0026 note): repeat the `bench_generation.py` measurement enough to know what a real improvement looks like.
2. **Profile the serve path** end-to-end (per-request breakdown: proto decode, featurization, tensor assembly, GPU, response) on the RL-loop-exact config.
3. **One measured lever at a time** — candidates from the profile, not guessed in advance (plausible: featurization caching across consecutive decisions of one game, batched tensor assembly, proto handling). Each lever lands with a before/after at the bench and the standing parity/tripwire gates (serve-vs-recompute μ tripwire catches any numeric drift for free).

Done honestly: a measured throughput gain, or the overhead attributed with a documented negative. No open-ended optimization: the deliverable is bounded by the profile's top findings.

### Riders and watches

- **Pool-manifest mtime-selection hazard** (raised stakes since `final_read` derives provenance through `latest_pool_manifest()`): fix selection to explicit/pinned rather than mtime — small, attach to the first session that touches `pairs.py`.
- **Ante correctness items** (draw-poison coverage 69%, re-deal re-anchoring, node-level draw bias): ride with whichever D2/D3 critic retrain touches them; not standalone.
- **Upstream watches:** #11285 (post the queued #11360 complementarity comment as the review nudge); connive-lines conflict expected at next rebase (drop ours); `IndexOutOfBoundsException` class (deck `dc-863943`, seed-pinned) — replay with `-Danvil.crash.trace` when convenient, plausible upstream filing; MinMaxBlocker illegal-block-discard realizer gap (pairs with block-drop re-ask if D3 telemetry re-indicts it).
- **Playable-fork track:** separate track, not part of M4 (its own worklist; residue = T2 only).

## Risks and open questions

- **The adaptation probe may resolve "both."** Partial recovery leaves the baseline choice ambiguous; the pre-registered rule is: baseline = the best *promoted* checkpoint on the new engine, whatever its provenance story.
- **Drill-mixing may buy drill-winrate, not game-winrate.** Overfitting to crash contexts is the known failure mode of curriculum-by-failure; the arms guard it, and the drill eval suite makes the divergence visible early rather than at the 2,000-game read.
- **Crash windows may be symptoms, not causes.** The value crash marks where the critic *noticed*, not necessarily where the decision error lives; upstream-of-crash windows (the curation list already records peak_turn vs crash_turn) are the first refinement if drills-at-crash underperform.
- **Curation shape may not survive the rebase.** If the new-engine doom analysis finds a materially different addressable fraction, D2/D3 sizing re-prices — that's the analysis doing its job, not a plan failure.
- **Serving profile may point at gRPC/proto rather than Python we own** — a harder lever. The bounded-deliverable rule keeps D4 from becoming a rewrite; a documented negative is an acceptable close.
- **Two-front discipline.** D4 touches the serve path while D3 runs train through it; the μ tripwire + parity tests are the guard, and serve-path changes land only between runs, never mid-run (no-tree-edits rule).

## M4 is done when

1. ~~**The re-baseline question is resolved:** the adaptation probe has run under guards, its best checkpoint has a paired 2,000-game corrected read, and an ADR records the mechanism verdict and the M4 baseline number.~~ **SATISFIED 2026-07-29 ([ADR-0028](../decisions/ADR-0028-d1-adaptation-probe.md)):** `d6-run9` ran 10/10 under guards (zero halts); iter-009 read 0.5233 ± 0.0110 corrected, paired +1.15pp ± 0.90 vs run7b-i14 (t=1.28) — a directionally-positive tie. **Verdict: the heuristic got stronger; the M4 baseline stands at 0.5121, ckpt of record unchanged.** Veto re-fit was real (first-attempt 0.118→0.082) and strength-neutral, a third confirmation of the wasted-intent lesson. `d6-run9/iter-009` = designated D3 init (adapted, veto-clean); closing-read stores = D2's curation substrate.
2. **Grindstone v0 is online:** the curation analysis is regenerated on new-engine games; drills mined from real losses replay, fork, and play end-to-end with full provenance; the drill economics are re-priced under micro-batching; the drill eval suite reports per-checkpoint.
3. **A drill-signal run beats the M4 baseline outside noise** on the standing paired 2,000-game Ante-corrected read — or the (a)→(b)→(c) escalation is exhausted with each stage's negative recorded to ADR standard.
4. **The serving path is profiled with a noise floor, and either a measured throughput improvement has landed** (bench before/after, parity gates green) **or the per-request overhead is attributed with a documented negative.**

Clause 3 is the spine's gate. Clause 1 is deliberately cheap and first. Clause 4 is bounded by construction. The upstream watches have no clause — they report what they find or stay silent.
