# M12 plan — SEARCH AS THE BEHAVIOR POLICY, built through to one big run (RECHARTERED 2026-09-06; SCOPED 2026-09-06 session 3; BUILD 0 OPEN session 4)

**Doc status:** living · the open milestone plan — charter + running record

*Status: RECHARTERED at the 2026-09-06 architecture review
([ADR-0101](../decisions/ADR-0101-architecture-review-m12-recharter.md)); the original draft was
chartered at the M11 closeout ([ADR-0100](../decisions/ADR-0100-m11-closeout.md)). Principles
the user set: the project can identify strength and cannot teach it — the teaching channel is
the priority; do more training and less design; push through a complete structure first (engine,
value head, search, the remaining decision surfaces), then one really big run with everything;
the model must be strong WITHOUT search, or the project is "search for the heuristic"; search
depth is a budget from day one. SCOPED 2026-09-06 (session 3, ADR-0101 addendum): forks A/G/H/I
adjudicated, Build 1 numbers, day-zero arms and band rules, the shakedown run, full multi-format
readiness — every pin below is the record. Build 0 OPENED 2026-09-06 session 4 ([ADR-0102](../decisions/ADR-0102-m12-build0-pins.md): six pins, fork J).*

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
  been a milestone's object; rollout-mean labels sit in the store unused as value targets
  (ADR-0101 finding 1) — **corrected at Build 0 (ADR-0102): 1,321 drill fork points, 806 harvest
  windows, 3,294 mint per-arm rows, ~6,000 cl2 per-arm leaves over 800 windows — of order 10⁴,
  not the "106K games" (95,616 of which are the cl2 store's completions)**; plus dense full-vis
  h2 targets and terminal outcomes.
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

0. **The engine bundle** — pinned at Build 0's opening ([ADR-0102](../decisions/ADR-0102-m12-build0-pins.md)):
   **the boundary carries only game-path changes**, forkcheck-proven against the 08-21 seed set
   (which also discharges the recording jar's owed proof by transitivity):
   - **exact payability in the mask = the executor's own predicate** (`canPayCost` before
     targets, the existing `PAYCHECK` path ON by default) — filter and apply-time adjudicator
     agree by construction; residual veto classes (late-priced cost modifiers, the model's own
     X/mode) are counted, never absorbed. The M9 enumerator is an apply-time RESCUE only if the
     smoke shows chain-payable casts dominating the residual. Mask cache key extended, re-gated
     by the obs-diff protocol, ON/OFF decided by the smoke's games/hour;
   - **deterministic caps**: a per-game priority-window cap and a turn cap at the rebaseline's
     99.5th percentile (≤ 0.5% of games truncate), the wall-clock clock demoted to a crash
     guard; reward unchanged (loss/draw/cap = 0 both seats). Repetition detection DEFERRED
     with a tripline (cap or clock hits > 0.5% of games reopen it);
   - **provenance in the game header + manifest, not in records**: registry ids for format and
     pool, `-pool <id>` on `AnvilRun`, bridge `format_tag`/`fork_commit`/`engine_commit`
     populated, **`OBS_SCHEMA_VERSION` → 3** as the era gate (reader takes the version per
     store; sv=2 and sv=3 never join), `launch --pool` refuses a `pool_version` mismatch.
   AFTER the boundary, as ADR-0025-exempt commits each with its 500-game proof:
   - the value RPC + **the budgeted search directive** (§1–§3 above) with **uniform
     determinization of the opponent's hand** (fork J) and compute telemetry in both units;
   - the enumerators for the Build 3 surfaces (Java side only; heads come later).
   Smoke (bridged, `iter-019`, on the boundary jar): residual veto classes, cap-hit rate,
   games/hour cache off/on, the priority-window quantile; then with the directive: determinism
   under CRN, **network forward calls AND leaf evaluations per searched window** (the budget
   unit is forward calls — fork A), decisions-per-leaf, games/hour flag off/on at a fixed
   budget — the per-game search multiplier that sizes Build 5. **Prerequisite for everything
   below because a big run with search at today's throughput is months, not weeks.** Honest
   sizing: the game-time tail is wide boards as much as long games (slowest decile = 31% of
   wall time, 1.75× per-turn cost), so caps buy ≈10%; the multiplier is the search's.
1. **The value head** — in parallel with Build 0, on existing stores (the 106K drill-fork games,
   the cl2 forks store, the harvest/mint composites): rank loss on rollout means + full-vis h2
   targets for the masked head **inside the shared trunk** (one network; not a standalone critic
   grafted later — so this is the pre-training pass that produces the day-zero checkpoint);
   reads = the Build 0 cells (one-ply ranking 0.277 ± 0.022 →) and the state-ranking Spearman
   (0.27–0.48 →). **Pre-registered: GO at one-ply ≥ 0.35 and/or state-ranking mean ≥ 0.50; KILL
   if neither clears 0.32** (two SE) → the leaf evaluator cannot be sharpened from banked labels;
   adjudicate before spending search compute. Read at the corrected label scale (~10⁴ rollout-mean labels, ADR-0102 item 6);
   the ADR-0099 slope (+0.03 per doubling from 10³) is the prior.
2. **Search + the day-zero read — THE ONE GATE.** Wire the directive to the sharpened masked
   head; the acting rule with margin bar and temperature pinned from the smoke's margin
   distribution. **The day-zero paired read on the fixed population, FOUR arms**: `iter-019`
   alone (the 0.5279 reference), the Build 1 checkpoint alone, the Build 1 checkpoint +
   lookahead, heuristic + lookahead (same masked head). Bars: **≥ +1.5pp GO / ≤ 0
   KILL-CANDIDATE**; **in-band (0, 1.5) proceeds to Build 3 but the big run cannot launch
   without a second read ≥ +1.5pp after Build 4**; a value-head pass for the re-read = one more
   banked-label fit + the day-zero run's own composites; a second ≤ 0 after that pass kills the
   charter. **Control-arm rule:** heuristic + lookahead within 1.0pp of network + lookahead is
   recorded as *the value head carries it* — not a kill; it sets the Build 5 expectation that
   network-alone must climb from below — and heuristic + lookahead vs heuristic alone is banked
   as what a masked-head lookahead buys any policy.
3. **The decision surfaces** — one per evening, no gates: the three answer-shape heads and the
   enumerator tags (targets, discard/sac, mull tuck, modal, trigger order, library ordering,
   naming, payment classes, combat damage). Each integration: forkcheck + a one-hour smoke run +
   a 600-game paired read (a check that nothing broke — every shipped surface has landed a
   silent landmine caught by its first run).
4. **Representation completions** — stack-entry tokens (§J-10), embedded ability text (the
   pinned LLM in place of the 33K string-id table `sa_emb`, ADR-0012; **cache keyed by text hash,
   not pool version**, so a new set is an append — fork I), and **format-as-features emitted**
   (design §2: starting life, deck size, singleton flag, command zone, mulligan variant + a small
   learned format embedding; fork I). Prerequisite, not a reward: dense distillation targets need
   a representation that can carry them. **Blast radius is a named step:** replacing `sa_emb`
   re-initializes a learned 64-dim input path, so the checkpoint gets a **re-warm on banked
   labels after Build 4** (D4-standalone cost, ~2 h) read by the Build 1 cells as its smoke.
   The **format-onboarding recipe doc** (`docs/design/format-onboarding.md`: pairs file + fixed
   population, Ante certification, ladder anchor, era-scoped calibration maps, pool `CURRENT`)
   is written when the format block lands.
4½. **The shakedown run** — ~20–30K games with everything on, same loop shape as Build 5. The
   loop's lr 1e-5 / KL 0.06 / replay 4 were tuned for sparse PG from a fixed checkpoint and dense
   distillation turns the KL guard into a brake; the shakedown tests those settings, is the last
   landmine catcher, and supplies the learning-curve slope the power statement's "games to
   produce" line needs.
5. **The big run.** **Envelope: four to six weeks of unattended box time**; games × per-game
   budget derived from it with Build 0's measured search multiplier (300K games at today's
   800–1,600 g/h is 8–16 days flag-off; ×3 is 3–7 weeks; ×10 is 2.5–5 months). Power statement
   at launch — *detect*: the 2,000-game read resolves ±1.1pp so the promotable target is ≥ +2.5pp
   over 0.5279, the paired read resolves 1.4pp at two SE per checkpoint pair; *produce*: the
   shakedown's slope, re-issued at the 50K-game checkpoint from the run's own curve.
   Resume-friendly at seeded game granularity, `nice -n 19`, overnight-and-away cadence. **Fork H
   (the Android ship of `iter-019`) runs during this build on the playable branch.** Read
   mid-run ONLY for guards, the network-alone vs with-lookahead gap, and the state-ranking
   Spearman (the plateau-together tripline). The pivotality head regenerates from the run's own
   margins each cycle; the uniform floor stays on.
6. **Close by the standard 2,000-game read** vs 0.5279 ± 0.0110 (network alone; promote on
   cleared gate), with-lookahead alongside as the deployment ceiling, the ladder of own checkpoints
   updated (ADR-0101 §7), and the queue routed by name.

## Forks (state after the 2026-09-06 review; the scoping session pins the rest)

- **A. Leaf event for d=1.** **ADJUDICATED (09-06 s3): the acting seat's next quiescent priority
  window.** ADR-0098: eot K=1 ≈ K=8 (0.30 vs 0.33) and h2 within 0.01 of eot, so the cheap leaf
  loses nothing measurable. Sub-pins: **intermediate decisions on the path to the leaf are played
  greedily by both seats** (CRN-stable, low-variance leaf); **the budget unit is network forward
  calls** (policy + value), not leaf count — it is what the per-device map converts.
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
- **G. Format testbed.** **ADJUDICATED (09-06 s3): no Pauper in M12.** The Pauper pool dir
  holds a flex list only (builder exists, raw decks do not); a switch is pool + decks + ruleset +
  every per-format asset at once, and it depends on Build 4. Commander is the run. Routed by
  name to the closeout; taken early only if the Build 5 mid-run kill fires.
- **H. Ship `iter-019` on Android** (ONNX export + Java ORT session replacing the gRPC call).
  **ADJUDICATED (09-06 s3): DURING Build 5, not before.** No ONNX export exists in the tree; the
  pointer decoder is awkward to export; the Python-side featurizer needs a Java port — real
  weeks, and the weeks the box is busy are the ones it fits. Playable-branch only; zero delta on
  the research fork.
- **I. (new) Multi-format readiness.** **ADJUDICATED (09-06 s3): full readiness lands in this
  round; training on a second format is decided later.** Already there: the ruleset is a flag
  (`AnvilRun -f`, default Commander; Forge has a Pauper deck format under Constructed; the only
  Commander-specific Anvil branch is the commander-player constructor), the pool pipeline is
  generic (`anvil.pool.pauper`), the Python schema is not Commander-bound (life clipped to
  [−10, 150], race features relative), cards are text-embedded, ADR-0018 lands content in chunks.
  Lands now: format-as-features + text-hash-keyed ability embeddings (Build 4), format/pool ids
  on every row + per-pool `CURRENT` (Build 0), the onboarding recipe doc (with Build 4).
  Caveat on record: readiness = the interface exists; two formats in one network at
  near-specialist parity is the design's 65% bet and a later, separately powered run.

- **J. (new, 09-06 s4) Hidden information in search copies.** **ADJUDICATED
  ([ADR-0102](../decisions/ADR-0102-m12-build0-pins.md)): every copy is determinized to the
  acting seat's information set** — libraries reshuffled (already default) AND the opponent's
  hand resampled uniformly from their unknown set, one sample per leaf roll; the sampler is a
  named teacher setting in provenance. A thinner channel (values only) does not close the
  leak — the leak is what the value is conditioned on. Routed by name: **L2 belief-sampled
  determinization** (the belief head's first consumer; labels free and dense; quality =
  log-likelihood of the true hand vs uniform), consistency rejection later; **L3
  information-set search** out of scope — the strategy-fusion residual is a named suspect if
  the Build 5 gap holds while with-lookahead climbs.

## Done-when

1. The engine bundle landed as one forkcheck-proven boundary; veto at apply ≈ 0; the p90
   game-time tail cut; the directive runs anytime under an evaluations budget with cost telemetry
   in both units.
2. The value head's one-ply ranking and state ranking move under Build 1 (numbers pinned at the
   scoping session against the Build 0 cells).
3. The day-zero paired read and the control arm recorded and adjudicated on their bars.
4. Every §3d′ family answered by the model under search (three answer shapes, enumerators with
   the natural line), each with its smoke read on file.
5. Stack-entry tokens, embedded ability text (text-hash-keyed cache) and format-as-features in
   the representation; the post-Build-4 re-warm read on file; format id + pool id on every row;
   the format-onboarding recipe doc written.
5½. The shakedown run on file with its slope and the settings it pinned.
6. The big run launched with a power statement inside a four-to-six-week envelope, completed or
   resumed to its sized length; the gap and state-ranking series on file.
7. Closed by the standard 2,000-game read — or early by a pre-registered kill with an ADR.
8. The closeout routes by name: the skill token / human-shaped levels, ponder-time search,
   belief head, match play, Tutor/Mentor product surfaces, the Pauper testbed if not taken, the
   Android ship if not taken.

## Kill conditions (pre-registered)

- Build 1: neither value-head cell clears 0.32 (one-ply Spearman) from banked labels.
- Build 2: a second ≤ 0 day-zero read after a value-head pass. In-band (0, 1.5) is not a kill but
  blocks the Build 5 launch until a post-Build-4 read clears +1.5pp.
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
bundle leaves throughput binding at the big run's sizing); **the Pauper testbed** (fork G — the
closeout, or early on the Build 5 mid-run kill); **training on a second format** (fork I — after
the readiness lands, its own powered run); **the standing-rules prune** (the next documentation
pass).

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
- **2026-09-06 (session 3) — the scoping session** ([ADR-0101 addendum](../decisions/ADR-0101-architecture-review-m12-recharter.md),
  status → ACCEPTED). The plan reviewed as coherent; what was missing was arithmetic and pins.
  The big run priced (8–16 days flag-off at 300K games; a leaf evaluation = copy + intermediate
  decisions + one value call, so the search multiplier was unpriced) → **envelope pinned at four
  to six weeks of box time**, games × budget derived. Pinned: the value head inside the shared
  trunk from Build 1 (four day-zero arms); Build 1 GO 0.35 / 0.50, KILL < 0.32; the in-band rule
  (proceed, but no Build 5 launch without a post-Build-4 read ≥ +1.5pp); the control-arm 1.0pp
  rule; fork A = next quiescent window, greedy intermediates, budget unit = forward calls; fork G
  = no Pauper in M12; fork H = Android ship during Build 5; **fork I (new) = full multi-format
  readiness in this round** (format-as-features, text-hash-keyed ability embeddings, format/pool
  ids on every row, the onboarding recipe doc), training on a second format decided later. Two
  amendments: **Build 4½ shakedown run** (settings under the dense label mix + the slope for the
  power statement) and the **post-Build-4 re-warm** as a named step. Two standing rules. Next:
  **Build 0 opens in the fork** — exact payability filter first (the veto tripline should drop to
  ~0), then caps, then the directive + format/pool provenance; **Build 1 in parallel** on the
  106K drill-fork games, the cl2 forks store and the composites. Housekeeping unchanged: the
  recording jar's ADR-0025 proof is owed before any jar generates a training store.
- **2026-09-06 (session 4) — Build 0 OPENED** ([ADR-0102](../decisions/ADR-0102-m12-build0-pins.md)).
  State review against the tree: the payability filter already exists (`PAYCHECK`, off since M1
  for late-pricing + cost reasons) and the apply-time veto uses the same Forge predicate; a 300 s
  wall-clock draw clock exists and the trainer already scores caps as 0; no Java leaf-value
  callback exists (the directive is new surface); the bridge hardcodes the format tag; the
  "106K drill-fork games" double-counts cl2 (real: ~10⁴ rollout-mean labels); the game-time tail
  is wide boards as much as long games. Six pins, all accepted by the user: the executor's own
  predicate as the filter (enumerator = rescue only if the smoke says so); the boundary = mask +
  caps + provenance header, the directive and enumerators after it as exempt commits; deterministic
  window/turn caps at p99.5, repetition deferred with a tripline; provenance in the header +
  manifest under sv=3; **fork J** — search copies determinized to the acting seat's information
  set (uniform now, belief-sampled next, the belief head's first consumer); the Build 1 record
  corrected. Next: the fork — (a) mask ON + cache key + obs-diff gate, (b) caps, (c) provenance +
  sv=3 + bridge fields + Python reader/harness, (d) the boundary jar's forkcheck vs the 08-21
  seeds + the bridged smoke, (e) the value RPC + directive + enumerators as exempt commits.
- **2026-09-06 (session 4, later)** — the boundary bundle landed in the fork (`5d5283eb233`:
  executor-predicate mask + payshadow counter, deterministic caps 52 / 1,650 with the
  draw-status fix, sv=3 provenance header); Python side (`de3d23a`); the smoke chain launched
  15:12 (A filter-on / B cache-on / C payshadow / the boundary forkcheck); the search directive
  scaffold compiled (SearchDirective, anvil.value, SearchMonitor with fork J determinization) and
  the server's value ask + greedy search sessions committed. Latent bug fixed on the way: a forced
  Draw recorded a WIN since M0 (~1/2,000). Devlog
  [2026-09-06-session4](../devlog/2026-09-06-session4.md). Next: the smoke read + cache decision +
  cap pins, the search jar + its smoke (the multiplier), the enumerators, Build 1.
- **2026-09-06 (session 4, note) — warm-starting the mask on search copies.** The mask cache
  cannot be shared with a copy (its entries hold the parent's `SpellAbility` objects), but the
  copy's first window IS the searched window, so the parent's mask can be carried over as
  (host-card id, ability index) — ids survive GameCopier — and rebuilt without the legality +
  payability scan; the directive needs that translation anyway (today it finds the forced option
  by scanning and label-matching). Saves one scan per candidate copy (13 of 14 at a wide window);
  the leaf's scan stays unless the value ask goes opts-free; intermediate windows scan as normal.
  Build it only if the search smoke's per-option breakdown (copy_ms vs ms) shows the scan share
  on copies is material — user question, 09-06.
- **2026-09-06 (session 4, close)** — Build 0 done-when 1 LANDED. Boundary forkcheck 499/500 vs
  08-21; the mask filter −97% unpayable vetoes at zero wall cost, shape-fit now the dominant veto
  (Build 3 targets); enumerator-rescue class 9.4% of rejected options → Build 3 payment; caps
  52 / 1,650; the mask-cache gate root-caused (payability test draws game RNG) → scans on a
  throwaway RNG (standing rule), cache stays OFF (still +10/120 divergences vs an OFF/OFF
  control); the search directive smoked end to end: ms/window p50 296, forward calls per leaf
  p50 4, **multiplier ≈ 2.6× forward calls at rate 1** (pure mana abilities excluded from
  candidates), leaves 85% / void 15%. Final forkcheck on the Build 0 jar `aac9f808bcf`: 497/500 identical, the three misses all the identity-hash residual (one replayed to the baseline hash) — PASS.
  Playable worklist item 10 (Coffers refund bug). Next: Build 3 enumerators (exempt commits),
  **Build 1 in parallel**. ADR-0102 addendum is the record.
- **2026-09-06 (session 5)** — **Build 1 launched; Build 3 enumerators landed in the fork**
  ([ADR-0103](../decisions/ADR-0103-m12-build1-value-head-and-build3-enumerators.md)). Build 1
  = `anvil/training/value_pretrain.py`: iter-019 + value head + top-4 trunk layers, a KL anchor
  to the frozen teacher (a POLICY day-zero checkpoint, not a critic tower), three label families
  already on disk in the iter-019 era (labelset 9,600 rows / cl2 106,144 leaves with the banked
  full-vis values / 48,000 rebaseline outcome windows), the one-ply read CROSS-FIT over five
  game-hash folds (standing rule), state ranking on the frozen holdout; bars unchanged. Build 3
  enumerators: `Surfaces` + `SurfaceDirective` + the search's second round (`-searchsurf B`) —
  every §3d′ callback names its option list in the observation, a directive forces an index
  answer on a copy, seven answer shapes enumerated natural-first, the first traced surface on the
  top-B candidates' paths expanded. Devlog
  [2026-09-06-session5](../devlog/2026-09-06-session5.md). Numbers: the ADR addendum.
- **2026-09-06 (session 5, close)** — **Build 1 GO**: one-ply 0.277 → **0.390 ± 0.019** (cross-fit,
  n 647), h2/K=8 0.44 → **0.69**, state ranking 0.39 (its 0.50 bar not cleared), policy drift nil
  (KL 0.002, argmax agree 99.3%); day-zero ckpt `data/training/m12-build1/last.pt` (a state-only
  early-stop variant reads alongside; selection by inner-val, declared before the read). **Build 3
  enumerators PROVEN exempt**: forkcheck 498/500 vs 08-21, both misses the identity-hash residual
  (20260739 replays to the baseline hash twice) → fork pin `6eb64b6c538`. Smoke: 148 windows,
  116 sub-rows, 0 copy crashes, 1 miss; modal choice shows the visible headroom (Δ ≥ 0.02 at 4/6),
  tutor targets in the tail. Next: **Build 2** — wire the directive to the sharpened head, pin the
  margin bar/temperature from the smoke's margins on the day-zero ckpt, regenerate the fixed
  population on the boundary jar, the four-arm day-zero paired read.
- **2026-09-06 (session 5, late)** — the search smoke on the day-zero ckpt (40 games, rate 0.2):
  565 windows, 0 crashes, margins on the sharpened head ≥ 0.05 at 19.5% / ≥ 0.10 at 11.5% (p99
  0.32, max 0.63), argmax ≠ natural 41%, void 20.6%, multiplier ≈ 2.4× at rate 1. Build 2's bar
  bracket is 0.05 / 0.10 (ADR-0103 addendum).

