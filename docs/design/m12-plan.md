# M12 plan — SEARCH AS THE BEHAVIOR POLICY, built through to one big run (RECHARTERED 2026-09-06)

**Doc status:** living · the open milestone plan — charter + running record

*Status: RECHARTERED at the 2026-09-06 architecture review
([ADR-0101](../decisions/ADR-0101-architecture-review-m12-recharter.md)); the original draft was
chartered at the M11 closeout ([ADR-0100](../decisions/ADR-0100-m11-closeout.md)). Principles
the user set: the project can identify strength and cannot teach it — the teaching channel is
the priority; do more training and less design; push through a complete structure first (engine,
value head, search, the remaining decision surfaces), then one really big run with everything;
the model must be strong WITHOUT search, or the project is "search for the heuristic"; search
depth is a budget from day one. The scoping session pins forks and pre-registered numbers
against this doc.*

## Charter

**The behavior policy that generates training data is the network PLUS a budgeted, anytime
lookahead through the engine, evaluated by the network's own masked value head; the network is
trained to reproduce what the lookahead chose (distillation) and on what it earned (PG), at store
scale, over the WHOLE decision surface.** Search is the improvement operator at every searched
window of every game and it is also the drill-finder: re-searching a stored high-margin window is
the same machinery as searching a live one. The deployable asset is the network alone; search is
the teacher, and the gap between network-alone and with-lookahead is the one number that says
whether teaching is happening. The milestone's product is one big training run, not a probe.

## The facts it starts from (ADR-0098, ADR-0099, ADR-0100, ADR-0101)

- One engine step plus the value head ranks option quality at 0.30 (one ply) and 0.46 (the
  spread's horizon, K=8) with no learning; the masked head — the only critic that may act
  (information-set principle) — is within 0.03 of the full-vis critic at every horizon.
- Nothing learns option quality from the pre-action state at 10³ labels (0.20; slope ≈ +0.03 per
  doubling). Dense search labels are 10⁵–10⁶ per run: the bet is that the slope holds for ten
  more doublings, which needs a trainable trunk and a representation that can carry the target
  (ADR-0096's rule) — hence the representation completions move BEFORE the big run.
- The value head's STATE ranking is weak (Spearman 0.27–0.48 vs rollout truth) and it has never
  been a milestone's object; 106K drill-fork games and thousands of K=8 composites sit in the
  store unused as value targets (ADR-0101 finding 1).
- The loop has run at ~10K games per run against a design budget of 1–3M; throughput (800–1,600
  g/h bridged, game-time p90 19× the median) is binding (ADR-0101 finding 2). The gate (±1.1pp)
  cannot see the gains that compound.
- 18–30% of cast attempts are vetoed at apply because Forge's `canPlay` is not payment-aware;
  the §6c penalty, the veto guard and the void pre-filter absorb an inexact mask (ADR-0101
  finding 3). The M9 payment enumerator computes exact payability.
- The heuristic still decides tutor targets, trigger order, modal choice, library ordering, stops,
  naming, mull tuck and resolution payments (§3d′); each was individually sub-gate, the sum was
  never read (ADR-0101 finding 4).
- Pivotality is learnable from the state alone (AUC 0.69, rising with data — ADR-0096); its
  label under this charter is the search's own margin, free at every searched window.
- The existing amortizers are the ones this needs: the grounded label term (ADR-0088), PG /
  V-trace, the paired strength read (SE 0.7pp at K=8/N=600), GameCopier + `Obs.peekPriority` +
  `-forceschedule`-class directives, the harvest/certify machinery (now read instruments).

## The canonical shape

1. **The search directive** (Java, inert without the flag): takes a **budget in evaluations**
   for the game and an allocation policy, not fixed (d, b, K). At a searched window with options
   O — **always including the natural line** (the executor's pick, or the heuristic's on a
   surface the network does not yet answer) — it copies the game (GameCopier, CRN roll seed),
   applies each option, advances with the network playing every intermediate decision (both
   seats) to the leaf event, snapshots the leaf, and asks `anvil.value` for V(leaf) from the
   acting seat's masked head. **Anytime**: one ply over all options first, then deepen the top-b
   (Gumbel sequential halving is the reference shape); cut at any budget, best-so-far returned.
   Illegal-at-apply options are void and COUNTED (they should be near zero once the mask is exact).
   Returns per-option leaf values, the margin, and the evaluations spent.
2. **The acting rule** (the behavior policy): margin = max V − V(natural). Margin ≥ bar → act on
   the search's pick, sampled from the leaf-value softmax at a pinned temperature (a behavior
   distribution exists for PG; exploration survives); below the bar → the natural line. Never
   worse than the fallback by construction. Full-vis NEVER acts (§7).
3. **The gate as the compute lever.** The pivotality head (input: state; label: the search's
   margin, era-scoped) allocates the game budget across windows — the time-management model —
   with a **uniform exploration floor** so ungated windows keep producing labels. Deployment uses
   the same allocation under a wall-clock budget converted by a per-device evaluations→ms map.
4. **Amortization** (two terms, both existing): distillation of the search's pick on every
   searched window (the ADR-0088 grounded-driver machinery, dense) + PG on every window with the
   behavior logp (the search softmax where it acted, the executor's otherwise; V-trace corrects
   the rest). Trainable trunk, one network.
5. **The value head**: rank/regression loss for the masked head on rollout composites (the K-roll
   means, ADR-0015) and the full-vis critic's h2 values, **as a permanent term in the loop** with
   a rollout anchor that never goes away (invariant four made operational). Read by the Build 0
   cells (one-ply ranking 0.28 →) and the state-ranking Spearman.
6. **Surfaces.** Every §3d′ family becomes a search TAG (an enumerator Java-side that includes
   the heuristic's pick) plus an answer-shape head to distill into. Three answer shapes cover the
   ledger: **entity set** (tutor/fetch targets, discard, sacrifice, mull tuck, modal), **ordering**
   (trigger order, scry/surveil, library), **name ranking** (Pithing-Needle class). Payment
   classes are the cheapest tag (apply a class, resolve, evaluate) and distill into the existing
   pay head. Combat damage assignment rides the entity-set shape.
7. **Search = drill-finding.** Grindstone's curation becomes "re-search the stored windows whose
   margins were large" at higher (d, b, K) offline — the two-second scenario of §6 — and those
   picks join the same distillation term. No separate drill pipeline.
8. **Deployment.** The network alone on a phone; where compute exists, the same directive under a
   wall-clock budget; ponder-time search (opponent's turn, user's thinking time) later. The ε-margin
   difficulty dial and the user-rating estimate come from the same ranked output (ADR-0101 §7).

## Build order

0. **The engine bundle** — ONE boundary event, forkcheck-proven before the first store:
   - exact payability in the candidate mask (the M9 enumerator as a filter; retires §6c, the
     veto guard and the void pre-filter — keep the veto counter as a tripline, expect ~0);
   - game-time and repetition caps with cap-aware reward (design §3d) — read the throughput gain
     on the p90 tail;
   - the budgeted search directive (§1–§3 above) with compute telemetry in both units;
   - the enumerators for the Build 3 surfaces (Java side only; heads come later).
   Smoke: determinism under CRN, evaluations per searched window, games/hour with the flag off
   and on at a fixed budget. **Prerequisite for everything below because a big run with search at
   today's throughput is months, not weeks.**
1. **The value head** — in parallel with Build 0, on existing stores (the 106K drill-fork games,
   the cl2 forks store, the harvest/mint composites): rank loss on rollout means + full-vis h2
   targets for the masked head; reads = the Build 0 cells (one-ply ranking 0.28 →) and the
   state-ranking Spearman (0.27–0.48 →). Pre-registered movement pinned at the scoping session.
   KILL: no movement on either cell → the leaf evaluator cannot be sharpened from banked labels;
   adjudicate before spending search compute.
2. **Search + the day-zero read — THE ONE GATE.** Wire the directive to the sharpened masked
   head; the acting rule with margin bar and temperature pinned from the smoke's margin
   distribution. **The day-zero paired read on the fixed population: with-lookahead vs the
   executor** (bars carried from the draft: **≥ +1.5pp GO / ≤ 0 KILL-CANDIDATE**; one re-read
   after a value-head pass; a second ≤ 0 kills the charter), plus a **heuristic + lookahead
   control arm** (same masked head): if it matches network + lookahead, the network contributes
   nothing yet and the strength lives in the value head — known before the run, not after.
3. **The decision surfaces** — one per evening, no gates: the three answer-shape heads and the
   enumerator tags (targets, discard/sac, mull tuck, modal, trigger order, library ordering,
   naming, payment classes, combat damage). Each integration: forkcheck + a one-hour smoke run +
   a 600-game paired read (a check that nothing broke — every shipped surface has landed a
   silent landmine caught by its first run).
4. **Representation completions** — stack-entry tokens (§J-10) and embedded ability text (the
   pinned LLM in place of the 33K string-id table). Prerequisite, not a reward: dense distillation
   targets need a representation that can carry them.
5. **The big run.** ≥ 300K games (sized by the power statement at launch: games to detect the
   target, games to produce it), resume-friendly at seeded game granularity, `nice -n 19`,
   overnight-and-away cadence. Read mid-run ONLY for guards, the network-alone vs with-lookahead
   gap, and the state-ranking Spearman (the plateau-together tripline). The pivotality head
   regenerates from the run's own margins each cycle; the uniform floor stays on.
6. **Close by the standard 2,000-game read** vs 0.5279 ± 0.0110 (network alone; promote on
   cleared gate), with-lookahead alongside as the deployment ceiling, the ladder of own checkpoints
   updated (ADR-0101 §7), and the queue routed by name.

## Forks (state after the 2026-09-06 review; the scoping session pins the rest)

- **A. Leaf event for d=1.** Lean unchanged: **the acting seat's next quiescent priority window**
  (cheap, generic across tags) vs end of the acting turn. *Scoping session.*
- **B. Amortization term.** **ADJUDICATED: distillation (dense label term) + PG.**
- **C. Behavior at searched windows.** **ADJUDICATED: sampled from the leaf-value softmax at a
  pinned temperature; the anytime search is Gumbel-shaped so its sampled action is the behavior
  distribution.** Argmax kills exploration and the PG behavior distribution.
- **D. Gate.** **ADJUDICATED (amended): the pivotality head allocates from Build 0, with a
  uniform exploration floor**; Build 0's smoke measures the margin distribution that pins the bar
  and the floor rate. The draft's "search everything, gate from Build 2" is withdrawn on cost.
- **E. Reads.** **ADJUDICATED: one gate (the day-zero paired read + the control arm); smoke reads
  at every integration; the gap + state-ranking as mid-run health; the standard 2,000-game read
  closes.**
- **F. Depth as the lever.** **ADJUDICATED (amended): depth, breadth and leaf rolls are what a
  budget buys, not flags** — the scaling curve is budget-per-game vs paired strength, read on
  the big run's checkpoints at two budgets, not as a separate build.
- **G. (new) Format testbed.** Pauper (`anvil/pool/pauper`) or another short, repetitive
  format for loop-mechanism questions, Commander for the promotable number. *Scoping session.*
- **H. (new) Ship `iter-019` on Android** through the playable build (ONNX export + Java ORT
  session replacing the gRPC call) before or during the big run. *Scoping session.*

## Done-when

1. The engine bundle landed as one forkcheck-proven boundary; veto at apply ≈ 0; the p90
   game-time tail cut; the directive runs anytime under an evaluations budget with cost telemetry
   in both units.
2. The value head's one-ply ranking and state ranking move under Build 1 (numbers pinned at the
   scoping session against the Build 0 cells).
3. The day-zero paired read and the control arm recorded and adjudicated on their bars.
4. Every §3d′ family answered by the model under search (three answer shapes, enumerators with
   the natural line), each with its smoke read on file.
5. Stack-entry tokens and embedded ability text in the representation.
6. The big run launched with a power statement, completed or resumed to its sized length; the gap
   and state-ranking series on file.
7. Closed by the standard 2,000-game read — or early by a pre-registered kill with an ADR.
8. The closeout routes by name: the skill token / human-shaped levels, ponder-time search,
   belief head, match play, Tutor/Mentor product surfaces, the Pauper testbed if not taken, the
   Android ship if not taken.

## Kill conditions (pre-registered)

- Build 1: no movement on either value-head cell from banked labels.
- Build 2: a second ≤ 0 day-zero read after a value-head pass.
- Build 5: **with-lookahead climbs while network-alone stays flat** at the mid-point — the
  teaching channel is broken; the project would be "search for the heuristic." Adjudicate
  capacity / encoding, not more compute.
- Build 5 tripline: both curves plateau together while the state-ranking Spearman is flat — the
  leaf evaluator caps both; back to the value head.

## Inherited obligations and hazards

- **Information-set principle:** leaves are valued by the MASKED head only; full-vis is
  instrument-only (§7); leaves are the acting seat's own future windows.
- **Boundary discipline:** the engine bundle is ONE boundary event, forkcheck-proven with the
  flag off; with the flag on the game path changes by design (that is the policy); stores carry
  the directive's budget, allocation, bar, temperature and floor as provenance.
- **Budgets in evaluations, never wall-clock, during training** (replay-stable; the model never
  sees the clock); the calibration map is telemetry-derived.
- **Uniform exploration floor** on every gated search (the §3d self-sealing hazard).
- **Rollout anchor in the value loss, permanently** (invariant four).
- **Power statement before every launch**; a gate that cannot resolve the effect it seeks is a
  null generator.
- **Serving jitter** bounds replay parity; reads pair within-run (CRN).
- **Reads that measure ceilings are not learnability** (ADR-0100); amortization is read as the
  network-alone gap, never inferred from label fit.
- **Compute accounting per game** is a first-class telemetry row from Build 0.
- **The playable build shares Forge's user deck store** with research; never check out
  `playable` in the research worktree.

## Out of scope / routed by name

The certifier and spread labels (read instruments only); the option scorer's spread loss and the
generative planner (retired, ADR-0096/0099); the turn-plan latent as a supervised channel
(inert); the skill token and human-shaped levels (after the big run, needs human games); belief
head; match play; Tutor / Mentor as products; the Rust subset engine (re-priced only if the engine
bundle leaves throughput binding at the big run's sizing).

## Running record

*Appended per session, newest last: what moved, what broke, what the next session picks up. The
CLAUDE.md Now paragraph is a summary of this section; when the milestone closes, the paragraph
moves verbatim to the status archive and this section stays here as the record.*

- **2026-09-06** — charter drafted at the M11 closeout (ADR-0100). Documentation restructure the
  same evening (running records live here from now on). Next: the scoping session adjudicates
  forks A–F and pre-registers the Build 1 numbers against the Build 0 cells.
- **2026-09-06 (session 2)** — architecture review before scoping
  ([ADR-0101](../decisions/ADR-0101-architecture-review-m12-recharter.md)): the value function
  named as the never-built central asset; the loop measured at ~10K games/run against a 1–3M
  design budget with throughput binding; the veto economy traced to an inexact legality mask;
  the hybrid agent's excluded surfaces summed. **M12 RECHARTERED** as a staged build to one big
  run: engine bundle → value head → search (the one gate + a heuristic-plus-lookahead control
  arm) → the decision surfaces (three answer shapes, natural line always in the option set) →
  representation completions → the big run. Search = drill-finding; budgets in evaluations,
  anytime, pivotality-allocated with a uniform floor; the network-alone gap is the charter's kill
  condition; the ladder of own checkpoints + the ε-margin difficulty dial now, the skill token
  later. Forks B–F adjudicated as recorded above; A, G (Pauper testbed), H (Android ship of
  `iter-019`) to the scoping session. Five standing rules added. Next: the scoping session pins
  the Build 1 numbers, the day-zero bars' re-read rule, the big run's power statement shape, and
  forks A/G/H; then Build 0 opens in the fork.
