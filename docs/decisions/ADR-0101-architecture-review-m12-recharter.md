# ADR-0101: Architecture review before M12 — the value function is the central asset and was never a milestone's object; the loop is under-scaled against the design's own budget; the veto economy is an engine-legality defect; M12 RECHARTERED as a staged build to one big run (engine bundle → value head → search → surfaces → the run)

- **Date:** 2026-09-06 (session 2)
- **Status:** ACCEPTED (addendum below: the 2026-09-06 session-3 scoping pinned forks A/G/H,
  the Build 1 numbers, the day-zero arm list and band rules, a shakedown run before the big run,
  and full multi-format readiness inside Builds 0 and 4)
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

## Addendum (2026-09-06, session 3): the scoping session — pins, forks A/G/H, the shakedown run, multi-format readiness; status → ACCEPTED

The user reviewed the rechartered plan and agreed every proposal below without amendment; the
one addition the user raised (full multi-format readiness in this round, training on a second
format decided later) is item 9. m12-plan.md carries the same pins in its Forks and Build order.

1. **The big run's envelope is pinned in calendar time, not games.** Build 5 gets **four to six
   weeks of unattended box time**; games × per-game budget is derived from it, with the per-game
   search multiplier measured by Build 0's smoke. The arithmetic that forced this: 300K games at
   today's 800–1,600 g/h is 8–16 days with the flag off; a 3× search multiplier makes it 3–7
   weeks, a 10× multiplier 2.5–5 months. A leaf evaluation is a copy + every intermediate
   decision the network plays to the leaf + one value call, so the multiplier is budget ×
   decisions-per-leaf, and neither was priced before this session.
2. **The value head lives inside the shared trunk from Build 1** (one network, trainable trunk —
   not a standalone critic grafted later). Build 1 is therefore a pre-training pass on banked
   labels that produces the checkpoint the day-zero read uses, and the network-alone number moves
   before search touches it. **The day-zero read has four arms**: `iter-019` alone (the 0.5279
   reference), the Build 1 checkpoint alone, the Build 1 checkpoint + lookahead, heuristic +
   lookahead (same masked head).
3. **Build 1 pre-registered numbers** against the ADR-0098 cells (masked head one-ply Spearman
   0.277 ± 0.022 at 800 windows; state-ranking Spearman 0.27–0.48): **GO at one-ply ≥ 0.35 AND/OR
   state-ranking mean ≥ 0.50; KILL if neither clears 0.32** (two SE). 0.35 is three SE off the
   baseline and half the distance to the full-vis K=8 read (0.46).
4. **Day-zero band rules.** GO ≥ +1.5pp and kill-candidate ≤ 0 stand. **In-band (0, 1.5)
   proceeds to Build 3** (surfaces are ungated) **but the big run cannot launch without a second
   read ≥ +1.5pp after Build 4.** A "value-head pass" for the re-read = one more banked-label fit
   plus the day-zero run's own composites. A second ≤ 0 after that pass kills the charter.
5. **Control-arm rule.** Heuristic + lookahead within **1.0pp** of network + lookahead (SE 0.7pp
   at K=8/N=600) is recorded as *the value head carries it* — not a kill; it sets the Build 5
   expectation that network-alone must climb from below, and heuristic + lookahead vs heuristic
   alone is banked as "what a masked-head lookahead buys any policy."
6. **Fork A ADJUDICATED: the leaf is the acting seat's next quiescent priority window.**
   ADR-0098: eot K=1 ≈ K=8 (0.30 vs 0.33) and h2 within 0.01 of eot, so the cheap leaf loses
   nothing measurable. Two sub-pins: **intermediate decisions on the path to the leaf are played
   greedily by both seats** (CRN-stable, low-variance leaf); **the budget unit is network forward
   calls** (policy + value), not leaf count — it is what the per-device map converts and what
   tracks wall-clock. Build 0's smoke reports both.
7. **Fork G ADJUDICATED: no Pauper in M12.** The Pauper pool directory holds a flex list only
   (the builder exists, raw decks do not); a switch is pool + decks + ruleset + every per-format
   asset at once, and it depends on Build 4 (the string-id table is what makes a card-set change
   expensive). Commander is the run. Routed by name to the closeout; taken early only if the
   Build 5 mid-run kill fires.
8. **Fork H ADJUDICATED: the Android ship of `iter-019` runs DURING Build 5, not before.** No
   ONNX export exists in the tree; the pointer decoder is awkward to export; the Python-side
   featurizer needs a Java port. Real weeks, and the weeks the box is busy on the big run are
   the ones it fits. Playable-branch work only; zero delta on the research fork.
9. **Fork I (new) ADJUDICATED: full multi-format readiness lands in this round**; training on a
   second format is decided later. What exists: the ruleset is already a flag (`AnvilRun -f`,
   default Commander; Forge has a Pauper deck format under the Constructed game type; the only
   Commander-specific Anvil branch is the commander-player constructor); the pool pipeline is
   generic (`anvil.pool.pauper` builds decks + banlist + flex → versioned manifest); the Python
   schema is not Commander-bound (life clipped to [−10, 150], race features relative); cards are
   text-embedded; ADR-0018 already lands content in chunks as boundary events. What lands now:
   - **Build 4 — format-as-features emitted** (design §2: starting life, deck size, singleton
     flag, command zone, mulligan variant + a small learned format embedding; the obs carries
     none today, so a 20-life game would read as Commander at half life); **the ability-text
     embedding cache keyed by text hash, not pool version** (retires the pinned pool-derived
     `sa_vocab`, ADR-0012, the one architectural blocker to open vocabulary — a new set becomes
     an append).
   - **Build 0 — format id and pool id on every store/trajectory row** as explicit provenance
     (rides the directive-provenance change); a `CURRENT` pointer per pool directory.
   - **A format-onboarding recipe doc** (`docs/design/format-onboarding.md`, written when the
     Build 4 format block lands) naming the per-format assets that are discovered one at a time
     today: pairs file + fixed population, Ante certification, ladder anchor, era-scoped
     calibration maps, pool `CURRENT`. A format switch becomes a checklist and one boundary event.
   Caveat kept on record: readiness means the interface exists; two formats in one network at
   near-specialist parity is the design's 65% bet and stays a later, separately powered run.
10. **Plan amendments.** (a) **Build 4½ — a shakedown run** of ~20–30K games with everything on
    before Build 5: the loop's lr 1e-5 / KL 0.06 / replay 4 were tuned for sparse PG from a fixed
    checkpoint and dense distillation turns the KL guard into a brake; the shakedown tests those
    settings, is the last landmine catcher, and supplies the learning-curve slope the power
    statement's "games to produce" line needs (without it that line is a guess at launch).
    (b) **Build 4's blast radius on `iter-019` is a named step**: the 33K table is the
    spell-ability embedding (`model.py:77`, a learned 64-dim input); replacing it with a
    projection of the text vectors re-initializes that input path, so the checkpoint gets a
    **re-warm on banked labels after Build 4** (D4-standalone cost, ~2 h), read by the Build 1
    cells as its smoke.
11. **Power statement shape** (for every Build 5 launch and mid-run re-issue): *detect* — the
    2,000-game read resolves ±1.1pp, so the promotable target is ≥ +2.5pp over 0.5279; the paired
    read at K=8/N=600 resolves 1.4pp at two SE per checkpoint pair; *produce* — the shakedown's
    slope extrapolated, re-issued at the 50K-game checkpoint from the run's own curve.
12. **Routed items settled.** Cadence: M12 is one long milestone by construction. Standing-rules
    prune: the next documentation pass, not now.

### Standing rules born in the addendum → standing-rules.md

- **A big run is preceded by a shakedown run of the same loop shape** (~10% of its size, every
  flag on) that tests the training settings under the new label mix and supplies the
  learning-curve slope for the power statement.
- **Every store row carries an explicit format id and pool id**, and a new format onboards by
  the recipe doc as one boundary event (extends ADR-0018's content-in-chunks rule to formats).
