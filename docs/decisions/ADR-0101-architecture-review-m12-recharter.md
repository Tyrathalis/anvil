# ADR-0101: Architecture review before M12 — the value function is the central asset and was never a milestone's object; the loop is under-scaled against the design's own budget; the veto economy is an engine-legality defect; M12 RECHARTERED as a staged build to one big run (engine bundle → value head → search → surfaces → the run)

- **Date:** 2026-09-06 (session 2)
- **Status:** proposed — direction agreed with the user in the review discussion; forks and
  pre-registered numbers pinned at the M12 scoping session, which adjudicates against this ADR
- **Design-doc anchor:** anvil-design-v2 §3a (search + distillation), §3d′ (decision-surface
  ledger), §4 (value head), §6 (Grindstone, calibration anchoring), §9 (throughput), §11
  (difficulty slider, Android), §14 (budget); m12-plan.md (rewritten under this ADR)

## Context

Before scoping M12 the user asked for a pass over the whole architecture: are the efforts in the
right places, and are there structural mistakes? The review read the design doc, the M12 charter
draft, the standing rules, the M3–M11 closeouts, and surveyed the package as built (model, loop,
bridge, reads, module stubs) and the run/store telemetry. The facts the review stood on:

| fact | value | where |
|---|---|---|
| Strength trajectory | BC 46.8% → M3 parity → M4 +1.98pp (the one promotion) → M5–M11 all TIE / NEGATIVE | milestone table |
| Games per training run | 480 / iteration × 10–20 iterations ≈ 5–10K; every run re-inits from `iter-019` at lr 1e-5, KL guard 0.06 | `d6-run11/loop_config.json` |
| All RL-era runs together | 299 iterations, 122 h generation, 109 h training | `data/training/*/monitor.jsonl` |
| Design §14 budget | 1–3M self-play games, 200–500 4090-hours | anvil-design-v2 §14 |
| Bridged throughput | 800–1,600 games/h at w=8; game time median 18 s, p90 342 s, max 964 s | run summaries |
| Gate resolution | ±1.1pp at 2,000 games; nothing under ~2pp is visible | `final_read.py` |
| Value head | one sigmoid head inside the policy net, terminal 0/1 at weight 0.5 in the PG loss; trained standalone once (D4, 110 min); state ranking vs rollout truth 0.27–0.48 | `model.py:82`, `rl.py:1810`, ADR-0015/0050 |
| Rollout labels on disk, unused as value targets | 106K drill-fork games; thousands of K=8 short-horizon composites | store manifests, ADR-0098 |
| Veto | 18–30% of the policy's cast attempts rejected at apply; 46% of schedule arms void at copy | ADR-0049/0098 |
| Model-decided surfaces | priority casts, keep, attackers/blockers, optional triggers, binary/number; payment infra inert | §3d′ |
| Heuristic-decided surfaces | tutor targets, trigger order, modal choice (cut at M1), scry/surveil ordering, stops, naming, mull tuck, resolution payments | §3d′ |
| Design deliverables unbuilt | belief head (stub), Tutor (stub), Mentor (stub), match play, skill token, Android embedding, concession/caps | package survey |
| Documentation | 100 ADRs, 128 devlogs in 66 days; standing-rules.md 19 KB incl. run-forensic entries | repo |

## Findings (ranked)

1. **The value function is the central asset and has never been built as one.** Search (M12's
   leaf evaluator), Ante's variance reduction (worth ~5% instead of the promised 3–4×), Mentor's
   blunder metric and Tutor's critic proxy all cap at the same head, which trains on terminal
   outcomes only while rollout-composite labels sit in the store as audit material. Invariant
   four ("audited against rollouts") should be operational: trained on them, continuously.
2. **The loop is under-scaled by two orders of magnitude and throughput is the binding
   constraint.** M0 retired throughput against the BC corpus at heuristic speed, not against the
   RL budget at bridged speed with training in the loop. A 10K-game run from lr 1e-5 cannot
   produce 2pp and the gate cannot see less; seven milestones of TIE are consistent with
   "mechanism negative" and equally with "every run too small." ADR-0024's 2× batch test does not
   separate them. The game-time tail (p90 19× the median) and the unbuilt §3d caps/concession are
   the cheapest throughput levers on the table.
3. **The veto economy is an engine-legality defect absorbed as an RL problem.** The design says
   actions are hard-masked by engine legality; Forge's `canPlay` is not payment-aware, so the
   §6c penalty, the veto guard, three milestones of veto literature and M12's void pre-filter all
   exist to absorb an inexact mask. The M9 legality-derived payment enumerator computes exact
   payability; run as a candidate filter it makes the mask exact and deletes the subsystem.
4. **The agent is a hybrid and the per-surface bar hides the sum.** Each excluded surface was
   probed under the ~2pp floor and re-deferred (targets 1.41pp/g, stops 0.69pp/g); together they
   plausibly exceed anything M5–M11 chased. ADR-0097 already allows one mechanism over many
   surfaces; the generic entity-set answer is that mechanism.
5. **Commander is the worst-case research testbed** (singleton, 100 cards, 40 life, ~150
   decisions per outcome bit). Right product target, wrong place to learn whether the loop learns;
   `anvil/pool/pauper` exists and format-as-features is designed.
6. **Focus.** Two months of strength mechanisms at the ±1pp floor while the named deliverables
   sat unbuilt. The Android embedding of `iter-019` (46M params, parity+2.8pp, tens of ms per
   decision vs the heuristic's minutes on token boards) is shippable through the playable track's
   existing Android/release machinery and is the design's stated contribution. Milestone cadence
   (seven in 32 days) is mismatched to a sparse-signal loop: instruments have consumed more of the
   budget than learning. The standing-rules register carries run forensics alongside design rules.

## Decision

**M12 is RECHARTERED** from a probe-gated mechanism milestone into a staged build whose product
is one big training run, with search as the behavior policy and the network alone as the
deployable asset. The user's framing: the project can identify strength and cannot teach it; do
more training and less design; push through a complete structure first, then train big.

1. **Build order** (each stage smoke-tested, not gated; see rule 2): (0) **the engine bundle**,
   one boundary event — exact payability in the candidate mask, game-time/repetition caps, the
   budgeted search directive, the enumerators for the new surfaces; (1) **the value head** trained
   on rollout composites + full-vis targets, in parallel with (0) on existing stores; (2)
   **search** wired to the masked head, with **the day-zero paired read as the single gate**
   (bars carried from the draft: ≥ +1.5pp GO / ≤ 0 kill-candidate) and a **heuristic + lookahead
   control arm** that separates the value head's contribution from the network's; (3) **the
   decision surfaces**, one per evening: three answer-shape heads (entity set; ordering; name
   ranking) over eight enumerators, the heuristic's pick always in the option set; (4) **the
   representation completions** (stack-entry tokens, embedded ability text), promoted from
   "third build on success" to prerequisite because dense distillation targets need a
   representation that can carry them (the ADR-0096 rule); (5) **the big run**: ≥ 300K games,
   sized by a power statement at launch, resume-friendly, read mid-run only for guards and the
   network-alone gap; (6) close by the standard 2,000-game read.
2. **Why the surfaces bundle now when they could not at M9.** Under the margin-gated acting rule
   with the natural line always in the option set, no surface can be dramatically worse than its
   fallback by construction; per-surface attribution stops being load-bearing and the user's
   "capabilities over heuristic fallback" default becomes automatic. Each integration gets a
   one-hour smoke run (forkcheck + a 600-game paired read) because every surface this project
   shipped landed a silent landmine caught by its first run — a check that nothing broke, not a
   promotion gate.
3. **Search = drill-finding.** Grindstone folds into search over the store: a high-margin stored
   window re-searched at higher (d, b, K) is the two-second scenario of design §6. Drills stop
   being a separate curation pipeline.
4. **The flywheel's label is the search's own margin** (max leaf V − V(natural)), dense and free
   at every searched window; the pivotality head trains on it, era-scoped, and aims the next
   run's compute. Requirements: a uniform exploration floor over ungated windows (the §3d
   self-sealing hazard), a permanent rollout anchor in the value loss, and the network-alone vs
   with-lookahead gap read as the health check (closing = amortizing; holding = capacity or
   encoding, not more compute).
5. **Budgets.** The directive takes a budget, not fixed (d, b, K): evaluations during training
   (deterministic, replay-stable — the model never sees the clock), wall-clock at deployment via a
   per-device calibration map; anytime (one ply over all options, then deepen the top few —
   Gumbel sequential halving is the reference shape); per-game allocation with the pivotality head
   as the time-management model; ponder-time search later. Telemetry carries both units from
   day one.
6. **The deployable asset is the network alone; search is the teacher.** Kill condition for the
   charter: with-lookahead climbs while network-alone stays flat. The plateau-together failure
   (both curves capped by a weak leaf evaluator) is read via the state-ranking Spearman alongside
   the gap.
7. **Difficulty and self-assessment.** Now: a frozen ladder of own checkpoints (the stable
   scoreboard the moving heuristic cannot be; the retroactive skill-label source via provenance);
   an ε-margin difficulty dial from the search's ranked options ("accept mistakes up to ε" in
   win-probability units), a user rating from average margin given up, adaptive difficulty from
   the same number. Deferred: the skill token and human-shaped levels, until after the big run and
   until the recording flywheel yields rating-binned games.
8. **Retired / inert.** The turn-plan latent as a supervised channel (strength-neutral; depth in
   the search is the planning mechanism); the generative planner and option-scorer heads stay
   retired; the payment head learns only by distillation from the payment search tag.

## Raised, not adjudicated — routed by name to the scoping session

- **Pauper (or another short, repetitive format) as the loop-mechanism testbed**, Commander
  kept for the promotable number.
- **Android embedding of `iter-019` in the playable build** (ONNX export + Java ORT session
  replacing the gRPC call), converging the side stream with the research deliverable.
- **Milestone cadence**: fewer, longer milestones sized to the effect they seek.
- **Standing-rules prune** to rules that change a future design decision; ADRs keep forensics.
- **Power analysis** as a launch obligation (games to detect, games to produce).

## Standing rules born here → standing-rules.md

- **Size every run to its effect**: a power statement (games needed to detect the target, games
  needed to produce it) precedes every launch; a gate that cannot resolve the effect it seeks is
  a null generator, not a measurement.
- **The natural line is always in the searched option set**; under a margin-gated acting rule a
  surface cannot be dramatically worse than its fallback, so surfaces bundle without per-surface
  attribution (amends the ADR-0097 one-mechanism rule for search-acted surfaces).
- **Search budgets are in evaluations during training, never wall-clock**; a per-device
  calibration map converts at deployment; the model never sees the clock.
- **A gated search keeps a uniform exploration floor**, and its pivotality labels are the
  search's own margins, era-scoped and regenerated per cycle.
- **Every search cost is priced per game against generation rate**; throughput is the binding
  constraint until measured otherwise.

## Consequences

- m12-plan.md rewritten to this shape (same doc, running record continues); CLAUDE.md Now
  bullet, map Now panel / M12 block / ADR index, design doc §13 M12 clause updated.
- The M11-routed queue (tutor targets, trigger order / combat damage, §3b stops, mull tuck,
  stack-entry tokens, semantic option content) is absorbed into Build 3 and Build 4 by name.
- The `-lookahead d b K` flag shape from the draft becomes a budgeted directive; the day-zero
  read keeps its bars; every other pre-registered number is pinned at the scoping session.
- The value-head sharpening moves ahead of the day-zero read (a 0.28-ranking leaf evaluator would
  land in the kill-candidate band and trigger it anyway).
