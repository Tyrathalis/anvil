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
3. **The decision surfaces** — **CLOSED 09-16 ([ADR-0108](../decisions/ADR-0108-m12-build3-closeout.md)): six
   surfaces served from the e3 build, the payment head withheld to the loop, the search's shape
   priced.** One per evening, no gates: the three answer-shape heads and the
   enumerator tags (targets, discard/sac, mull tuck, modal, trigger order, library ordering,
   naming, payment classes, combat damage). Each integration: forkcheck + a one-hour smoke run +
   a 600-game paired read (a check that nothing broke — every shipped surface has landed a
   silent landmine caught by its first run).
4. **Representation completions** (**the upstream MERGE lands before this item** — [ADR-0110](../decisions/ADR-0110-m12-upstream-merge-20260916.md): engine pin `23c3d2a85d` → `97535e047f` as a merge with the tag `pre-merge-20260916`, PR 11916 already upstream, the three-cell g/h read on the merged jar; the placement per [ADR-0106](../decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md) B) — stack-entry tokens (§J-10), embedded ability text (the
   pinned LLM in place of the 33K string-id table `sa_emb`, ADR-0012; **cache keyed by text hash,
   not pool version**, so a new set is an append — fork I), and **format-as-features emitted**
   (design §2: starting life, deck size, singleton flag, command zone, mulligan variant + a small
   learned format embedding; fork I). Prerequisite, not a reward: dense distillation targets need
   a representation that can carry them. **Blast radius is a named step:** replacing `sa_emb`
   re-initializes a learned 64-dim input path, so the checkpoint gets a **re-warm on banked
   labels after Build 4** (D4-standalone cost, ~2 h) read by the Build 1 cells as its smoke.
   The **format-onboarding recipe doc** (`docs/design/format-onboarding.md`: pairs file + fixed
   population, Ante certification, ladder anchor, era-scoped calibration maps, pool `CURRENT`)
   is written when the format block lands. **Amended 09-16 ([ADR-0109](../decisions/ADR-0109-prelaunch-completeness-audit.md)):
   the void re-roll skip rides the merge (ADR-0110, landed 09-16); Build 4's surface evening = TARGETS AS A SURFACE
   (triggered-ability targets, re-targeting, the generic target choosers — the largest deferral
   left; the mode head rides it: a three-arm paired read pre-registers the playability gate's
   retirement); then THE ALLOCATION HEAD (fork L's first fit, fork D's allocation served as an
   extra output on the priority ask; the uniform floor kept) before the post-Build-4 read.**
4½. **The shakedown run = the search-budget read** (amended [ADR-0106](../decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md),
   09-14 s3; the rebase carrying PR 11916 lands between evening 5 and Build 4, so this and
   everything after it sit in one era against one fresh reference read). Two or three arms at
   EQUAL BOX TIME, the same loop settings, the same day-zero start, each closing with the
   2,000-game read vs `ref` + the network-alone vs with-lookahead gap + the state-ranking
   Spearman: shallow-wide (rate 1, rolls 1, next leaf, no surface expansion) / the recipe (rolls 2
   + surface acting) / deep (partial expansion: every candidate at the next leaf, the top-3
   re-expanded to the horizon the priority-slot leaf calibration read measured as the peak, rolls
   2). **Pre-registered: the big run takes the arm with the best network-alone gain per box-hour;
   ties within one SE go to the cheaper arm** ("no detectable difference" at 10–15K games/arm is
   itself the decision — the cheap arm). One 64-game bench cell per arm at 24 × 2 sets the
   equal-box-time split from measured multipliers. The settings pass (lr 1e-5 / KL 0.06 / replay
   4 were tuned for sparse PG from a fixed checkpoint; dense distillation turns the KL guard into
   a brake) runs on the winning arm before the launch; the run stays the last landmine catcher
   and supplies the learning-curve slope the power statement's "games to produce" line needs.
   ≈ a week (was ≈ three days). A two-ply arm is gated on the deep arm showing gain per box-hour.
   **Amended 09-16 (ADR-0109): an ALLOCATION arm (the head's rate with the floor vs uniform rate 1)
   beside the three shape arms, the same equal-box-time rule; the surface round's breadth (B = 1,
   a surface rate, or the margin gate) is a settings-pass axis.** **SCOPED 09-21
   ([ADR-0115](../decisions/ADR-0115-m12-shakedown-scoping.md)): four arms (recipe / alloc / shallow /
   deep) at equal box time by `selfplay.py --wall-hours` (30 h each, accumulated across pauses), the
   run of record's loop settings from the e1a build on the census jar, drills OFF, no per-arm day-zero
   read, each closing with the 2,000-game read + the last lookahead arm; arm order recipe → alloc →
   shallow → deep; `scripts/shakedown_chain.sh` through `anvil.runs` with `--resume-on-gone`.**
4¾. **The documentation review session** (user, 09-15) — scheduled between the shakedown's verdict
   and the big run's launch, once every piece of M12 implementation is in: the architectural
   changes since ADR-0101 (search as the behavior policy, the surfaces, the acting rule, the leaf
   family, the fleet, the rebase) and the new tooling (the quickstart, the run launcher + the
   check-in, the calibration instruments) each documented for the long haul in the place a reader
   would look, not in the running record alone. Scope = the wrap-up checklist's documentation-pass
   line in CLAUDE.md (the field guide, standing-rules prune, the design doc's §3d′ ledger and §13,
   the canonical register, the quickstart, the ops docs, the map) **plus the Now block trimmed to
   what is running, what is next and the pins** — the narrative already lives here. Its output is
   one commit and a devlog; no design decisions are taken in it (those go to ADRs before it). **Amended 09-21 (ADR-0115, user): the pass runs BESIDE the shakedown, not after its
   verdict — it needs no box, the shakedown needs no docs; the verdict lands in the docs as an
   addendum. The certifier merge lands in the same week for the big run's jar.** **DONE 2026-09-23 (one commit + the session-2 devlog): the retired-rules file + the prune, design §3e (search as the behavior policy) + §3d′ / §4 / §6 / §13 / §15, the quickstart's flag table + fleet, the field guide's seven new traps, the canonical register's M12 lines, the Now block trimmed (the narrative archived verbatim), the map. The shakedown's verdict lands as an addendum; the format-onboarding recipe doc named by Done-when 5 is UNWRITTEN (the quickstart is the Constructed instance) — routed to the closeout.**
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
- **F. Depth as the lever.** **ADJUDICATED (amended twice): depth, breadth and leaf rolls are what a
  budget buys, not flags.** The serving-budget curve (budget-per-game vs paired strength on a fixed
  checkpoint) is read on the big run's checkpoints at two budgets; **the TRAINING-signal curve
  (network-alone gain per box-hour by search shape) is a different question and is read by the
  Build 4½ multi-arm shakedown after the priority-slot leaf calibration read sets the horizon**
  ([ADR-0106](../decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md)).
- **L. (new, 09-14 s3) Search-shape allocation — the model learns which assessment is useful to
  it** (user's aim). The pivotality head generalizes from "search or not" to "which shape" (none /
  one-ply next / partial-deep / …): input the state + the first ply's margin, label the search's
  own MEASURED gain per shape at that window (the flip-and-outcome facts the calibration read
  produces; era-scoped, regenerated per cycle), the uniform exploration floor kept for every
  shape, deployment the same allocation under a per-device budget. A time-management model, not a
  value estimate; the engine adjudicates every shape's answer; the head never chooses actions.
  Built after the calibration read's first labels; served in the loop with the floor; read as
  budget-matched strength vs the uniform-rate arm ([ADR-0106](../decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md)).
- **G. Format testbed.** **ADJUDICATED (09-06 s3): no Pauper in M12.** The Pauper pool dir
  holds a flex list only (builder exists, raw decks do not); a switch is pool + decks + ruleset +
  every per-format asset at once, and it depends on Build 4. Commander is the run. Routed by
  name to the closeout; taken early only if the Build 5 mid-run kill fires.
- **H. Ship `iter-019` on Android** (ONNX export + Java ORT session replacing the gRPC call).
  **ADJUDICATED (09-06 s3): DURING Build 5, not before.** No ONNX export exists in the tree; the
  pointer decoder is awkward to export; the Python-side featurizer needs a Java port — real
  weeks, and the weeks the box is busy are the ones it fits. Playable-branch only; zero delta on
  the research fork.
- **K. (new, 09-07, from the community watch) Effect-grounded ability embeddings.** LordOfThePigs
  is retraining his card/ability embeddings on observed game effects (cost tokens ↔ what was tapped /
  what mana left the pool; effect tokens ↔ replacements, stack effects), arguing general-purpose text
  embeddings cannot carry MTG-specific meaning. OPEN for Build 4 (user, 09-07: his problem is the
  inverse of ours — card value is his whole game, we back card value out of game knowledge — but
  it is the right reminder to think these aspects through for ourselves). The option set on record:
  (a) **an effect-prediction auxiliary loss on top of the pinned text embeddings** — grounding as a
  loss, not a replacement: keeps the LLM prior on unseen mechanics, keeps cold start (his grounding
  is per token, so cold start is lost only per card), keeps the text-hash cache of fork I, targets
  the one concrete gap (near-identical text, different engine effect — "add {G}" vs "add one mana of
  any color" — scored through the same embedding by the pointer decoder); (b) **re-segmenting the
  ability text** (cost / effect / condition spans embedded separately, or per-token pooling) — may
  buy the same discrimination without a new target; (c) **both embeddings side by side** (his
  effect-grounded vector concatenated with the text one, each with its own cache key — the
  grounded one is engine-era-dependent and breaks the append property, the text one is not);
  (d) replace outright (not favoured: learns engine versions, invariant seven; loses the prior).
  First step regardless: the ADR-0049 frozen-probe benchmark asked the new question — is an
  ability's effect class linearly decodable from the pinned embedding? Decodable → nothing to
  gain; not → (a) or (b) at the Build 4 evening (user 09-07: both are cheap and sound right; the
  model will learn cards over a long run anyway, so what a better embedding buys is INTAKE SPEED
  and canonicity, not ceiling). **The read that measures exactly that (user, 09-07): the held-out-card
  probe** — once card editions are fully supported (fork I / ADR-0018 chunks), hold a set of cards
  out of every training store and introduce them at test time: does the model play them? Shape:
  the held-out cards enter through the pool's flex slots (ADR-0018) into otherwise-seen decks, read
  paired against the same decks with seen substitutes; per-card cast rate given candidacy, veto
  rate, the search margin on their windows (the search directive values them by engine effect, so
  it is the natural teacher for a card the network has never seen); intake speed = the slope of
  those numbers under continued training on a chunk that contains them. The next ADR-0018 chunk is
  the held-out set by construction while legal coverage is incomplete; once every legal card is in,
  the permanent held-out group is NON-CANON (user, 09-07): synthetic cards built by recombining
  seen ability scripts under new names / numbers (graded — seen tokens in new combinations vs a
  genuinely new keyword; Forge card scripts are text, so the engine adjudicates them like any
  other), with silver-bordered / digital-only cards as a harsher second tier where Forge scripts
  them (caveat: Un-card text is out of distribution for the LLM embedding in ways a real new set
  is not, so it over-reads canonicity failures). The pool manifest carries the held-out flag so a
  training deck can never include one. Prior: ADR-0049 (representation was not the bottleneck at M6).
  His results are the external read.
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
- Build 5 tripline, the third shape ([ADR-0118](../decisions/ADR-0118-value-head-drift-under-the-loop.md)): **the state-ranking Spearman FALLS while network-alone is flat** — the leaf is drifting off rollout truth under the loop's outcome targets and the search's labels drift with it; the per-iteration audit flags it (> 2 boot SE below day-zero), the value anchor is the response, and a run whose anchored head still falls stops for a value-head pass before more compute.

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
pass); **the certifier merge** (user, 09-09 session 2 — routed to Build 4½ or the closeout,
whichever comes first after evening 5; the trigger = the first re-certification of existing
drills on a new pin, or the first drill mined from network-played games — both likely at the big
run): one fork-and-adjudicate primitive, two entry points. Today the M9 certifier (`CensusRun
-certify`: replay from a stored coordinate, payment-only, heuristic-only) and the search copy (the
leaf family, any surface, the behavior distribution) duplicate everything downstream of reaching
the window — the goal directive, the executor, the horizon stop (a turn-began event vs the
quiescent-window rule), the snapshot (the same fields, two encodings), the row schema, the
reader — and the two runners are not trajectory-identical (AnvilRun draws AI profiles + applies
the caps; the 09-09 finding). The merge: consult `PayDirective` inside the Anvil controller's copy
path so AnvilRun replays a stored window itself (its drill-file fork points already reach a turn),
the certifier becomes a thin front (replay to the window → the search copy), CensusRun's certify
mode retires, drill mining moves to AnvilRun census rows so the mining runner and the replay
runner are one program. Keep the two ways of REACHING a window: replay-from-coordinate is what
gives a drill provenance that outlives the process that found it (the Grindstone invariant; a
re-certification on a new pin needs only deck pair + seed + turn + spell); fork-from-live-state
is what runs on the behavior distribution for every surface. Not "inside vs outside the model":
the engine adjudicates in both, the head never certifies (`end` = the engine's outcome; `eot` /
`h2` = head-valued readings of the same fork). ≈ a day of fork work + a forkcheck.

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
- **2026-09-06 (session 6) — Build 2: the acting rule landed; the day-zero read moved to the
  2,000-game instrument and launched** ([ADR-0104](../decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)).
  State review found the pinned fork-window paired read could not search inside its own
  completions (the monitor lives on the mainline; nested copies + dual-policy routing + census
  regeneration + a replay-parity proof were owed), both self-play seats would have searched
  (a symmetric read), and the reference number (0.5279) lives on the 2,000-game scale — **user
  decision: the standard 2,000-game read vs the heuristic**, arms paired game-by-game on the
  final_read pairs + seeds. The acting rule (fork `103747691cc`): margin ≥ bar → sample from
  the leaf-value softmax at T (the natural stays in the distribution), a sampled option realized
  by a single-option forbid-decline re-ask, a veto falls back to the natural line, counted;
  `-searchact/-searchtemp/-searchseats`, the `search` pins on every game header. Pins: bar
  0.05 (+ 0.10 as a fourth arm), T 0.025, rate 1, rolls 1, surfaces off. `SearchActTest`
  caught two sampler bugs before any game ran. Smokes (8 games seat 0 vs the heuristic): act
  rate 24%, act_void 0.5%, 0 crashes, ~3× wall. Forkcheck (flag off): 498/500 main-trace hashes identical to the 08-21 baseline (`run-20260906-build2-act`; fork fidelity 448/52 vs 450/50); the two misses are the standing pair — 20260969 (launch-unstable) and 20260739, which replayed twice on the same jar to the baseline hash `9e0365815606ddf6` (the identity-hash residual) — **PASS at the ADR-0025 standard; the research fork pin moves to `103747691cc`**.
  **Launched** 23:16 09-06, `scripts/build2_dayzero_read.sh` detached (chain pid 1872752, watchd `build2-dayzero` stall 60 min + each arm's own `b2-<arm>-read` registration, notify on completion / failure), jar snapshot `data/runs/build2-dayzero/forge-build2.jar` (sha `812ea09e…`, pinned in every arm's manifest); arms ref → dz → dzla (bar 0.05) → dzla10, 2 × 1,000 games each at eight workers; ETA ~80 min per plain arm, ~2.5 h per search arm → the read lands ~07:00 09-07 in `data/runs/build2-dayzero/read.json`. The heuristic control arms (`heur` / `heurla`: a heuristic seat
  named by `-searchseats` is searched and acted for through its own realization) are written
  in the fork, compiled, their forkcheck and chain (`build2_control_read.sh`) after the read.
  Standing rule: a gate's bars and its instrument share one scale. Devlog
  [2026-09-06-session6](../devlog/2026-09-06-session6.md).
- **2026-09-07 (morning)** — the day-zero read's last arm caught an engine loop (game 989: Dark
  Sphere's source choice re-asked 150K times, 65 min to the wall clock); fixed in the fork
  (`b4825285529`: bounded engine re-ask + the `Census.loopCheck` tripwire capping the game as
  `loop:<method>` + the search clock allowance 3,600 → 900 s), replay-verified in 36 s; the
  state-hash repetition detector and a per-turn discount routed by name to the shakedown
  (ADR-0104 addendum). Community watch banked (fork K). The read itself: the next entry.
- **2026-09-07 (11:01) — THE ONE GATE read: IN-BAND** ([ADR-0104 addendum](../decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)).
  ref 0.538 / dz 0.522 / dzla(0.05) 0.530 / dzla10 0.538 vs the heuristic on 2,000 paired games
  each; **dzla − dz = +0.92pp ± 1.10** (the gate arm; in-band → Build 3 proceeds, the big run
  needs a post-Build-4 read ≥ +1.5pp); dzla10 − dz = +1.58 ± 1.04 (the bracket's second arm —
  not the gate; the acts between margins 0.05 and 0.10 are net negative → the shakedown's bar
  starts at 0.10, pinned now); **dz − ref = −1.63 ± 1.15** (the value-head pretrain cost policy
  strength; the lookahead only recovers to `ref`; network-alone starts from `dz`); act rate 15% /
  9%; multiplier 1.75× forward calls / 2.1× wall vs the heuristic at eight workers. Next: the
  heuristic control arms on the loop-guard jar after its forkcheck (`build2_control_read.sh`),
  then Build 3.
- **2026-09-07 (11:20)** — forkcheck `run-20260907-build2-control-loop` 498/500 vs the 08-21 seeds (fork fidelity 449/51), the standing two misses, 20260739 replays to the baseline hash `9e0365815606ddf6` twice on the same jar — **PASS; the research fork pin moves to `b4825285529`** (the control arm `1d4b2d817c3` + the loop guard). **Control chain launched 11:20 09-07** (`scripts/build2_control_read.sh`, chain pid 519465, watchd `build2-control` + per-arm registrations, notify on completion; jar snapshot `data/runs/build2-control/forge-control.jar` sha `8a5aab9c…`): `heur` (no seat bridged, `-searchseats` names the read seat, no search) then `heurla` (bar 0.05 / T 0.025 / rate 1), read against the day-zero arms; ETA ~14:40.
- **2026-09-07 (14:02) — the control arms: the value head carries it** ([ADR-0104 addendum](../decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)).
  heur 0.500 (the mirror's symmetry check, clean) / heurla 0.526; **heurla − heur = +2.51pp ± 1.00
  (t 2.5)** = what a masked-head lookahead buys any policy; heurla − dzla = −0.46 ± 1.28 → within
  1.0pp → *the value head carries it* (ADR-0101 §3 item 5; not a kill; Build 5's network-alone must
  climb from below). The lookahead gained the heuristic more than it gained the network at day
  zero; heurla ≈ dzla ≈ ref. Build 2 CLOSED with its two reads on file. Next: Build 3 (the decision
  surfaces, Python side: the loader reads the named `opts`, the three answer-shape heads, the
  distillation term from `sub` rows), one per evening, each with forkcheck + smoke + a 600-game
  paired read.
- **2026-09-07 (afternoon–evening) — BUILD 3 OPENED: evening 1 (entity one + entity set) and the
  ability representation pin** ([ADR-0105](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  State review: the Java side complete and proven, the Python side untouched, three unnamed gaps
  (no surface wire tag, no mainline surface acting, no payment tag); 220K free imitation labels in
  the Build 2 arms; option strings for modes/triggers ~99% outside the SA vocabulary. User pins:
  train + serve together one surface per evening; one option-set decoder (three decoding modes);
  **the ability representation = the pinned LLM over the ability's canonical engine text (script
  parameters + description), hash-keyed, one shared table** — fork K resolves (re-segmentation by
  construction; the auxiliary loss = the frozen probe first); imitation warm start then sub-row
  distillation; the sub-row pool generated first; evening order one/set → mode → order + damage
  → payment tag → mainline acting; naming to the closeout. Landed: fork `b0567608938` (`AbilityKey`,
  `ak` on every ability option/answer, the per-game `abil` side table, `-abilities` dump: 1,701
  cards → 5,148 abilities) + `a0ed9e314b5` (the serve wire `mtg.surface.entity_one/entity_set`,
  `selectSet`, `args.sak`); the ability cache + **the frozen probe: every effect class decodable
  (AUC 0.98–1.00; description-only 0.80–0.99; zone destination 0.84 vs 0.68)**; the Python side
  (`anvil/policy/surfaces.py`, the loader's `surf_*` tasks, `AnvilNet._surface_decode` with
  `surf_query`/`surf_key` as copies of the cast decoder's maps, featurize + server tags,
  `surface_fit.py`); the surface-label run launched 14:56 (1,000 self-play games, acting ON at
  0.10, `-searchsurf 2`; the 5 s worker deadline poisoned the first launch under the 8-worker
  burst → 20 s); wire smoke 21/21 bridged answers accepted. Fold 0 adapter-only baseline: surf_one
  0.257 / surf_set exact 0.355 vs first-option 0.20. Devlog
  [2026-09-07](../devlog/2026-09-07.md). Next: fold 0 with the role copies → folds → build →
  the forkcheck (**PASS 17:05: 497/500, 20260853 replays to the baseline hash on the same jar → fork pin `a0ed9e314b5`**) → the build ckpt `m12-build3-e1` (pooled cross-fit surf_one 0.308 / surf_set 0.465) → the served-head smoke (203/203 bridged answers; it exposed that served surfaces were no longer traced on copies → the trace fix `1ac2ec8dc0b`, **PROVEN 498/500 → fork pin `1ac2ec8dc0b`**) → **the 600-game paired read (18:18): surfaces withheld 0.513 / served 0.530, on − off +2.06pp ± 1.83 (t 1.1), 3,227 bridged answers accepted, no new crash class — EVENING 1 CLOSED (entity one + entity set served).** Next: the label run's read + ingest (tonight), evening 2 = mode (the enumerator fixes first: repeat-allowed multisets, sizes in [min, max]), the sub-row distillation term, `mtg.mulligan_tuck` serve.
- **2026-09-07 (evening, session 2) — BUILD 3 EVENING 2 OPENED: mode** ([devlog](../devlog/2026-09-07-session2.md),
  [ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  The label run's 2,519 `mode:idx` misses were exactly two enumerator gaps (a size-1 neighbour of
  an empty natural under "choose two"; distinct subsets under "choose three, repeats allowed");
  **the heuristic answers no modes in ~half of traced mode windows** (all but 12 of 1,136
  Confluence windows, all 120 Jitte windows) — a modal spell the network casts frequently fizzles
  by the heuristic's hand, the leak shared by every network arm in the Build 2 reads; the mode head
  addresses it directly. No store carried ability keys (the modes of one host indistinguishable);
  the sub-row distillation had no state (8% of mode sub rows joinable to a mainline frame). User
  pins: **the distillation state = the copy's surface-window frame captured into the sub row**;
  the keyed pool regenerated on the e1 ckpt with the entity surfaces served; `Constraints.repeat`
  on the wire; sizes inside [min, max] + multisets under repeat; the tuck serve + the orchestrator
  deadline ride. Fork `950f318a9e6` (enumerator fix, `Surface.repeat`, the sub-row `frame`,
  `mtg.surface.mode`; tests 15; smoke 66 sub rows / 0 misses / a frame on every row) + Anvil
  `0637050` (`surf_mode`, the distillation term `surface_distill.py`, tags per fitted task, the
  tuck serve, the deadline auto-raise). **Launched 19:36–19:38: the keyed label run
  (`build3-surface-labels2`, 1,000 games) ∥ the forkcheck `run-20260907-build3-mode`.** Next: the
  forkcheck read → pin; the keyed pool's read + ingest; the mode fit (imitation + distillation,
  cross-fit) → build → the served-head smoke → the 600-game paired read.
- **2026-09-07 (20:50)** — forkcheck `run-20260907-build3-mode` 498/500 vs the 08-21 seeds, 20260969
  the standing crash, 20260853 replays to the baseline hash twice on the same jar — **PASS; the
  research fork pin moves to `950f318a9e6`** (ADR-0105 addendum). The keyed label run continues on
  the proven jar (217/1,000 clean at 20:30, ~340 g/h).
- **2026-09-07 (23:50)** — the keyed pool landed (24,992 sub rows, `mode:idx` 0, every option keyed,
  frames on every sub row; ingested); **the key-stability bug** (in-play descriptions carry runtime
  state → 10,325 store-only keys per 1,000 games) fixed in fork `1e17923c82c` (`stripRuntime`; the pool
  re-dump byte-identical; forkcheck `run-20260908-build3-keyfix` pending); the evening-2 fit chain
  launched 23:10 (`build3-e2`: three surfaces, imitation + distillation → `m12-build3-e2`).
- **2026-09-08 (00:20)** — forkcheck `run-20260908-build3-keyfix` 498/500, 20260969 the standing crash,
  20260744 replays to the baseline hash twice on the same jar — **PASS; the research fork pin moves
  to `1e17923c82c`** (ADR-0105 addendum; the key-stability rule → standing-rules). The fit chain:
  folds 0–1 surf_mode 0.351 / 0.312, the entity tasks at evening-1 levels.
- **2026-09-08 (01:00)** — the evening-2 chain landed: pooled cross-fit surf_one 0.338 / surf_set 0.450
  / surf_mode 0.393 (unkeyed-dominated; the keyed-only held-out mode fold 0.461 vs first-option
  0.409); build `m12-build3-e2`; the served-head smoke on `1e17923c82c` clean (45 mode answers incl.
  the Confluence triples, 5 tuck, 0 errors, 0 misses). The 600-game paired read launched.
- **2026-09-08 (02:50) — EVENING 2's reads.** The paired read: withheld 0.512 / served 0.478,
  on − off −3.24 ± 1.87 (t −1.7) — a flag; the attribution arms on the same seeds: `notuck`
  −0.85 ± 1.92 (t −0.4), `tuckonly` −0.34 ± 1.02 (t −0.3) — no component carries it; the full-set
  number banked as an open small-N observation (ADR-0105 addendum). No new crash class; every
  answer accepted. Evening 2 closed on components; the served set from here = the user's call
  (default: all four). Next: evening 3 (ordering + damage).
- **2026-09-08 (midday) — the mode mechanism + the gate.** Variant (a) (mode by imitation only)
  −0.69 ± 1.90, mode-exposed −3.9 ± 3.8: the third losing mode arm; the answer-size split puts the
  loss in choose-one windows (−7.3 ± 3.2 pooled). Mechanism: the head's mode-only choice vs the
  heuristic's joint mode + target choice; a mode the AI would not play gets the mandatory chooser's
  targets at cast. **User: the playability gate** (serve-only stopgap; `Surfaces.playableModes`).
  Routed: mainline surface acting on modes (the principled replacement; a test of the value head on
  modes first), targets as a surface (after evening 3), the legal-target count as an option feature
  (ADR-0105 addendum).
- **2026-09-08 (11:30)** — the gated read +1.19 ± 1.86 vs withheld (the mode loss gone; the ladder
  on one reference in the ADR); forkcheck `run-20260908-build3-gate` 499/500 (the standing crash) —
  **PASS; the research fork pin moves to `bc01efe1609`**. The served-set arm (entity + gated mode
  + tuck) runs as the closing read.
- **2026-09-08 (12:00) — EVENING 2 CLOSED.** The served set (entity one + set + gated mode + tuck)
  −0.17 ± 1.80 vs withheld — nothing broke, within noise; the ladder on one reference in the ADR.
  Served from here: all four. Next: evening 3 (ordering + damage). Routed for the mode head:
  mainline surface acting on modes, targets as a surface, the legal-target count feature.
- **2026-09-08 (13:45) — BUILD 3 EVENING 3 OPENED: ordering + damage** ([devlog](../devlog/2026-09-08.md),
  [ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  The pool's facts: combat ordering never fires (the modern rule), ordering = trigger order +
  move-to-zone order (headroom at noise), damage has zero sub rows by construction (copies stop
  before combat) with ~350 mainline windows per 1,000 games. User: imitation only for both (RL in
  the loop later), damage as a kill order realized by the engine's lethal arithmetic, the enumerator
  family and the snapshot null guard ride. Fork `41ac60d6b21` + Anvil `ee6c512`; launched the
  forkcheck `run-20260908-build3-e3` ∥ the fit chain `build3-e3` (five tasks, e2's recipe). Next:
  the forkcheck read → pin; the chain read → the served-head smoke → the 600-game paired read.
- **2026-09-08 (14:30)** — forkcheck `run-20260908-build3-e3` 498/500, the standing pair, 20260853
  replays to the baseline hash twice on the same jar — **PASS; the research fork pin moves to
  `41ac60d6b21`** (ADR-0105 addendum). Folds 0–1: order 0.74 / 0.73 (trigger ordering 0.85 vs
  keep-the-order 0.77; move-to-zone 0.65 below it), damage 0.38 / 0.37.
- **2026-09-08 (16:30) — EVENING 3 CLOSED: ordering + damage served.** Pooled cross-fit order 0.732
  (trigger 0.846 vs keep-the-order 0.774; move-to-zone 0.626 below it), damage 0.376; build
  `m12-build3-e3`; smoke clean (0 errors, 0 null-obs frames); **the paired read +0.52 ± 1.82 vs
  withheld (n 580)**, every served answer accepted (1,585 orderings, 61 kill orders), the standing
  crash class only. Finding: the exposure split keyed on one arm's game is post-treatment (its sign
  follows the conditioning arm: trigger +9.6 keyed on ON, −2.2 keyed on OFF) → a standing rule;
  attribution = ablation arms on one reference. Served from here: six surfaces + tuck. Next:
  evening 4 = the payment tag; evening 5 = mainline surface acting (modes first).

- **2026-09-08 (evening) — BUILD 3 EVENING 4 OPENED: the payment tag** ([devlog](../devlog/2026-09-08-session2.md),
  [ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  Facts: the pay head has never been trained (design init in every M12 ckpt; 97.3% auto, the rest
  the untrained pointer's), search copies bridged the pay tag (leaf noise in every read since
  Build 2), imitation is empty (auto = option 0 = the init), the headroom ≈ +3.0pp/game in ~3% of
  windows (ADR-0075), the ADR-0077 queue is closed but for resolution-effect payments. User pins:
  the asymmetric target (auto unless a goal clears a margin bar; rolls ≥ 2), the end-of-turn leaf
  for payment answers (horizon and variance, not depth — spent in the offline pool; the horizon-2
  certify rollout as the calibration instrument), the copy-side pay gate, the payment surface's
  own expansion slot, the rescue class as a flag-gated second commit with its own arm, a serve-side
  margin bar, the queue untouched (resolution-effect payments → the Build 4½ opener conditional on
  the calibration; the measured argument paid by a new census row — first sample: 170/170
  zero-cost), "train enough" = a learnability read on positives vs ties. Fork `e44d83a8327` + the
  Python side (`pay_distill.py`, `pay_fit.py`, `--pay-bar`). **Launched 19:33: the forkcheck
  `run-20260908-build3-e4` ∥ the payment pool `build3-surface-labels3` (1,000 games, pay withheld
  on the mainline, `-searchpay 2` eot, rolls 2).** Next: the forkcheck read → pin; the pool read →
  the pay fit → build → smoke → the paired read; the rescue bundle; the calibration sample.
- **2026-09-08 (20:15)** — forkcheck `run-20260908-build3-e4` 499/500 vs the 08-21 seeds, 20260969 the
  standing crash — **PASS; the research fork pin moves to `e44d83a8327`** (ADR-0105 addendum); the
  rescue bundle `c26e99824b8` (flag-gated `-payrescue`) landed, its forkcheck `run-20260908-build3-e4r`
  running behind. **The served-tag confound** (user review): every M12 network arm served the
  untrained pay head, `iter-019` never did → dz − ref carries an unmeasured term (ADR-0104 addendum);
  no read redone; **the ablation arm** (e3 pay-withheld vs the evening-3 on arm) queued behind the pay
  chain; standing rule: served-tag parity or a declared arm. The overnight chain runs the pool → pay
  fit → build → smoke → the paired read unattended.
- **2026-09-08 (20:55)** — forkcheck `run-20260908-build3-e4r` 499/500 vs the 08-21 seeds, 20260969 the
  standing crash — **PASS; the research fork pin moves to `c26e99824b8`** (the rescue bundle, flag
  off = byte-identical; ADR-0105 addendum). The pool at 105/1,000 (80 g/h); the chain and the ablation
  arm waiting.
- **2026-09-09 (community watch, fork K)** — LordOfThePigs' effect-model design doc read (the survey
  doc carries the summary): per-unique-ability-text encoder over the SCRIPT surface (prose paired) +
  a state-conditional effect head over seven observed-effect record kinds from three Forge hooks;
  keyword-expansion dropout; identity-only baseline + card-disjoint-by-newest-set held-out. Fork K
  stands (our hash-keyed canonical script text already carries the effect language; the frozen probe
  decodes every effect class); two of his devices are cheap to borrow when Build 4 touches the table:
  keyword-expansion dropout as an augmentation, and the identity-only baseline as the floor for the
  held-out-card probe. `@manabrew/forge-wasm` assessed: not for the loop (engine-bound; the prompt
  surface; no search machinery); the RL-needs list drafted for khaliostr; Mentor-in-browser routed
  with fork H. talor's M4 Pro question answered from ADR-0003 / ADR-0032 / the rl bench.
- **2026-09-09 (throughput + depth, user session)** — **Throughput finding:** the box is idle, not the
  JVM: a worker is one busy core (flag-off 19 ms per window, search 32 ms per copy decision; bridge
  wait ≈ 5 ms of it; GameCopier 2.1% of search wall); 8 workers on 32 cores; the server at 92 rps
  under the pool (mean micro-batch 1.75 on the flag-off arm — the flag-off w=16 ceiling of 08-03 is
  the per-batch forward latency, which does not bind search runs). **Routed for this week (after the
  chain unregisters):** a 16- vs 24-worker bench on a 100-game search run (the Build 5 sizing line
  was written at 8–16); a JFR profile of one worker per regime (suspects: the payability predicate,
  state-effect / trigger churn per ask, the obs snapshot write); the micro-batch window under load.
  The Rust subset engine stays gated (throughput is not binding while cores idle). **Dreaming /
  learned dynamics:** not taken (the design's MuZero rejection stands: a real simulator exists,
  learned models smooth the rare adversarial branches; a dreamed rollout is an unadjudicated claim);
  the value head + distillation IS the cheap form. **Routed by name to the closeout (user, 09-09):
  depth-aware budget allocation** — the model reasoning over search depth to spend a clock budget:
  first the value head's calibration by horizon (the rollout audit per depth; ADR-0098's eot ≈ h2 is
  the first point), then a deepening RULE (deepen where the top candidates sit within the leaf noise
  at a pivotal window, stop where one line dominates — engine-adjudicated by construction, the
  baseline), then the learned version (the pivotality head extended to the value of one more ply,
  trained on whether deeper search changed the pick), alongside ponder-time search.
- **2026-09-09 (13:10) — the pool read + the pay head's capacity** ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)):
  42.9 groups / game, 5.7% positives at 0.03 (split-half best-goal agreement 0.65 vs chance 0.26 —
  reliable), the resolution-effect slice 0.23 consequential / game of 48.8 (the queue's measured
  argument); the pay-only head moves toward auto on every fold (pos_top1 ≤ 0.02) — capacity, not
  data or target. **User: the pay role-copy head** (`pay_query`/`pay_key` from `ptr_query`/`ptr_key`,
  pay windows only; day-zero identical; no drift) built on a worktree while the chain runs; the
  trunk-unfreeze variants = the capacity probe. The chain's read = nothing-broke + the rescue arm.
- **2026-09-09 (13:40) — the served-tag term measured: +2.56 ± 1.88pp** (the e3 ckpt pay-withheld vs
  serving the init head; [ADR-0104 addendum](../decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)).
  Corrected: dz − ref ≈ +0.9 ± 2.2 (the day-zero cost not distinguishable from zero), heurla − dzla
  ≈ −3.0 ± 2.3 (the control rule unresolvable at this n). The served set withholds the pay tag until
  a fitted head exists (the server's `has_pay` gate reads the ckpt's `pay_fit`). The chain resumed
  from its smoke (the pay-only build; the rescue arm's read); the set-key head's fold 0: pos_ce 5.90
  → 3.59, argmax still auto, the pos-weight-8 fold pending.
- **2026-09-09 (15:15) — the evening-4 paired read (the pay-only build):** on − off −2.91 ± 1.85,
  rescue − off −3.42 ± 1.90, with 0.14 deviations per game and the deviation-free games reading the
  same → **the bridged pay path itself costs ~2.7pp** (two independent reads, combined t ≈ 2.1); the
  probe-path arm (the tag bridged, auto on every window) decides whether the auto-payability probe's
  RNG draws + memory writes are the mechanism; the rescue class fires 0.09 / game — unreadable at
  this n, stays flag-gated. The set-keyed head's 5-fold fit runs ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **2026-09-09 (15:45) — the probe path is the cost:** the tag bridged with auto on every window
  reads −2.91 ± 1.86 vs withheld, identical to serving the head; three reads one way → the
  auto-payability probe (RNG draws + reservation-memory writes per bridged window) cost every M12
  network arm ≈ 2.7pp; fork `15863de0b4a` (`quietProbe`) fixes it, forkcheck running; the set-key
  head's read on that jar (off / on / autoonly) is the proof + the head's own read on one reference
  ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **2026-09-09 (16:05)** — forkcheck `run-20260909-build3-e4p` 498/500 (the standing crash + the
  identity-hash residual 20260744 replaying to the baseline hash) — **PASS; the research fork pin
  moves to `15863de0b4a`** (the game-neutral payment probe; ADR-0105 addendum). The set-keyed head's
  read on that jar (off / on / autoonly) running.
- **2026-09-09 (community watch, routed)** — Shedletsky's "chess problems" harness question (Astra
  recommended Anvil's drills); itemfive's sources. Routed by name: **the Possibility Storm puzzle
  battery** as a Build 4 read (Forge ships 278 of them as `.pzl` states; off-pool cards need fork
  I's open vocabulary, or the search directive solves them as a value-head benchmark with exact
  answers) and **17lands play data** as the skill-token human corpus candidate at the closeout. The
  Grindstone summary for the reply in the survey doc.
- **2026-09-09 (17:15) — evening 4's reads on the probe jar:** autoonly − off +0.34 ± 0.48 (8 divergent
  games of 591: the probe fix holds, the served-tag cost is gone); the set-keyed head at bar 0.2
  −0.34 ± 0.68 and at argmax −1.02 ± 0.72 vs autoonly, on 0.09–0.12 deviations per game (6 / 12
  outcome-changing games) — learnable, outcome unresolved and leaning negative (the mode head's
  shape); the head withheld, the payment target's horizon-2 calibration routed next. Evening 4
  proposed closed ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **2026-09-09 (17:40) — EVENING 4 CLOSED: the payment tag** ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  User: keep the set-keyed head, withhold it, calibrate its target (the horizon-2 certify rollout
  on its deviation windows) before training it further; its training home is the loop. Assets: the
  pool, the payment surface kind + gate + eot leaf, **the probe fix (pin `15863de0b4a`)** — the
  evening's finding: a probe that was not a pure observer cost every network arm ≈ 2.7pp since
  Build 1, now gone (autoonly − off +0.34 ± 0.48); the head (learnable, unserved); the queue item
  closed by measurement; three standing rules (served-tag parity, game-neutral probes, a fit record
  to serve). Served set unchanged. Next: the calibration read, the worker bench + JFR profile, then
  evening 5 = mainline surface acting.
- **2026-09-09 (19:12, session 2) — the payment target's calibration LAUNCHED** ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md),
  [devlog](../devlog/2026-09-09-session2.md)). The zero-fork route was dead on arrival: the
  CensusRun certify replay is by construction not the AnvilRun path (seed-derived AI profiles, the
  caps — its own comment says so), so no certify job can line up with a search window. The
  instrument moved INSIDE the search directive: fork `287e8cca45` gives the pay slot a leaf family
  (`-searchpayleaf next|eot|h<N>|end`; `end` = the copy to its outcome, no head call), a per-roll
  certify-axes `snap` on every pay answer, `-searchclock`; search-copy / recording only. The chain
  `build3_pay_calibration.sh`: three heuristic-control arms on one seed set (eot / h2 / end; 2 × 200
  games each, rate 0.25, rolls 4, B 2, the e3 value head), the sub rows joined across arms by
  `pay_calibration.py` (the join rate = the mainline-identity proof; smoke 12/12, outcomes and turns
  identical across the three arms) → the CONVERSION of the eot leaf's positives by the rollout.
  Cost from the smoke: end ≈ 7.7 s per answer at rolls 2 (a heuristic half-game ≈ 2–4 s), eot ≈ 0.5
  s, h2 ≈ 1.7 s → ≈ 6 h. Forkcheck `run-20260909-build3-paycal` alongside. Housekeeping: the
  b3label worktree moved to main, the merged vram worktree + branch removed; the community-thread
  QoL (`selfplay --device` / `--no-autocast`) on branch `qol-device` (worktree `anvil-wt-e4head`),
  tests 37 pass, merges after the chain.
- **2026-09-09 (19:54)** — forkcheck `run-20260909-build3-paycal` 499/500 vs the 08-21 seeds, 20260969 the
  standing crash — **PASS; the research fork pin moves to `287e8cca45`** (the calibration instrument;
  ADR-0105 addendum). The chain's eot arm at 133/200; h2 and end follow.
- **2026-09-10 (community watch, noted)** — Shedletsky's Forge-MCP / "UCI for MTG" thread (itemfive:
  the blocker is choice representation, the K'un-Lun example; Shedletsky: English as the
  representation, at the cost of search). User: a Forge MCP is not very useful to us, a neat idea.
  Banked in the survey doc with the assessment: not on the loop's path (engine-bound; an LLM seat is
  a Mentor surface, fork H); his labeled-positions goal is the drill question (engine-adjudicated
  labels, never an LLM's); the UCI answer is the engine's own callback surface + `AbilityKey` — the
  bridge protocol is UCI-shaped but engine-specific by construction. Nothing routed.
- **2026-09-10 (17:49) — THE CALIBRATION READ** ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md),
  `data/runs/build3-paycal/read.md`): 1,252 windows joined across eot / h2 / end, **1,252 identical /
  0 mismatched** (the mainline-identity proof at scale); the eot leaf's positives at the fit bar
  convert **+4.2pp ± 2.7 (t 1.6)** by the outcome, +2.9 ± 1.4 (t 2.0) at 0.01, ties ≈ 0 — **the target
  is not myopic** (no sign flip; the argmax arm's lean was noise); **the h2 leaf converts at t 2.9
  (+5.8 ± 2.0 on 133 positives vs eot's 62)** at 3× eot's copy cost vs 12× for the outcome leaf →
  proposed: h2 = the payment target going forward (the pool re-labelled at the next label run), the
  bridged-seat read on the h2 judge next (the bar0 seeds, `-searchpay 4 -searchpayleaf h2`, hours).
  Coverage: the rollout arms lose clipped late windows (end −280, h2 −78, mostly turn ≥ 21). Chain
  wall 22.5 h with two restarts (the chunk fix, the clock); the end arm's straggler tails ≈ 3 h per
  seat. The user decides the routing.
- **2026-09-10 (20:00) — THE h2 RELABEL LAUNCHED (user: swap the target now, not at the next label
  run — the loop's label run is weeks out and the pool is a dataset, not a checkpoint).**
  `scripts/build3_h2_relabel.sh`: the evening-4 pool recipe under `-searchpayleaf h2` (rolls 4, 16
  workers, the clock 2,400 s, seed base 20260910, the e3 ckpt serving every tag but pay, jar = the
  pin `287e8cca45`) → `data/runs/build3-surface-labels4/` (watchd `build3-b3-surflab4`), and the
  evening-4 pay chain waiting on it (`data/runs/build3-e4h2/`, watchd `build3-paychain`: the pool
  read → `pay_fit` 5 folds at pos-weight 8 / min-rolls 3 → the build `m12-build3-e4h` → the
  served-head smoke → the paired read `b3e4h` off / on at argmax on the pinned jar). Expected: the
  pool ≈ 08:00 09-11, the read ≈ 16:00. The bridged-seat read on the h2 judge and the throughput
  bench follow in the daytime gaps.
- **2026-09-10 (21:50) — routed by name: MODEL-SERVER SCALING (user).** The h2 relabel's first launch
  found the loop's real ceiling under search: one model server = one Python batcher thread (110% CPU
  at 16 workers of network-played h2 copies, the GPU at 52%, the workers at 30% waiting on the
  bridge); the harness takes ONE `--bridge` address, so more workers cannot help and the recipe had
  to shrink 4× instead. **The item (the throughput week, ahead of the 16- vs 24-worker bench — the
  bench is meaningless until the server scales):** (1) the harness accepts a list of bridge
  addresses and assigns workers round-robin (`--bridge a,b,c`; one line in the worker command
  builder); (2) the launchers (`selfplay`, `final_read`, the label + read chains) start N servers on
  consecutive ports, N = ceil(workers / 8) by default (a `--servers` knob; one `_start_server` loop);
  (3) **autoscale**: the driver watches the servers' batcher occupancy (the server already counts
  asks and micro-batch sizes — expose a `/stats` line per minute) and adds a server + rebalances at
  the next chunk boundary when the mean queue wait exceeds the forward latency (the harness assigns
  chunks, so a rebalance is a per-chunk address choice, not a live migration); (4) the Build 5 sizing
  line re-issued with servers as a variable (the GPU has ≥ 2× headroom at 52%). Measured argument:
  the calibration's heuristic copies ran 16 workers at load 22 with no server pressure; the same
  recipe on self-play copies saturated one server at 29 g/h.
- **2026-09-11 (17:30) — the h2 head's paired read: WITHHELD at argmax; the bar arms running**
  ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  The h2 pool: 23.1 groups / game at rate 0.5, positives 11.4% at 0.03 (2,598 — the calibration's 2×
  reproduced); the fit `m12-build3-e4h` pos top-1 0.080 / pos dev 0.188 / tie dev 0.097 (e4s 0.094 /
  0.155 / 0.045); the paired read on − off **−1.36 ± 1.20 (t −1.1)** with 0.77 deviations / game
  (e4s: 0.115). Attribution = the serve-bar arms (0.2 / 0.5) vs the same off reference (≈ 1 h);
  then the bridged-seat read on the h2 judge if no bar reads > 0.
- **2026-09-11 (19:05) — the serve-bar arms: no bar recovers the h2 head** (argmax −1.36 / bar 0.2
  −1.74 / bar 0.5 −0.87, each ± 1.2; deviations 0.77 → 0.42 / game). Four served pay heads, four
  negatives vs a leaf whose positives convert on heuristic games → the picks are not the leaf's
  picks (pos top-1 0.08) is the hypothesis; the offline pick-vs-leaf read on the pool decides
  between "the head" and "the transfer" before any replay run ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **2026-09-11 (19:15) — the pick-vs-leaf read: the loss is the DECISION TO DEVIATE, not the picks
  or the target** ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  By the h2 leaf, a head's deviations on true positives are worth +8 to +10pp (ceiling +12), its
  deviations on ties −2 to −3pp, and out of sample 3 of 4 deviations are on ties → net zero (e4s
  −0.001 / deviation; e3 −0.003; e4h +0.024 in-sample only). Next: a positive-window GATE (P(margin
  ≥ bar) with BCE on the pool's free label; the pivotality pattern), served as deviate-only-above-p*;
  the pool's arithmetic needs precision ≥ 0.26 for a net-positive deviation. `pay_fit --eval` +
  `pay_vals` on the loader landed (tests 27).
- **2026-09-11 (19:40) — the deviation gate built + the gated fit chain launched** (Anvil `98c4f8e`;
  [ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)):
  `pay_gate` (P(positive window), base-rate init), the gate BCE in the distillation loss, the gate
  curve + `gate_pstar` (argmax total admitted leaf gain) in `pay_fit`'s read, `--pay-gate` on the
  server (gate-fitted ckpts only), the chain's `GATE_WEIGHT` / `PAY_GATE=auto`. Chain
  `data/runs/build3-e4h2g/` → `m12-build3-e4hg` → the paired read `b3e4hg` (≈ 22:15).
- **2026-09-11 (22:20) — the gated read: −0.84 ± 0.81 on 0.24 admitted deviations / game → THE
  PAYMENT HEAD CLOSES AS A SERVE CANDIDATE AT BUILD 3 FIDELITY** ([ADR-0105 addendum](../decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
  The gate: AUC 0.68, precision 0.23 at p* 0.6 vs the 0.26 the leaf's arithmetic needs → break-even
  by the leaf, ≈ 0 by outcome; the ladder of five served pay heads (−1.02 / −1.36 / −1.74 / −0.87 /
  −0.84) each within one SE of the leaf's prediction. The head's serve routes to the loop (Build 4½
  PG on outcomes; the h2 pool + the gate = the warm start); the served set unchanged. Evening 5 next.
- **2026-09-14 (s2) — THE MODEL-SERVER FLEET LANDED (the throughput week, item 1 of the 09-10
  routing; user session).** Decisions: the server module owns the fleet (`anvil.bridge.server
  --servers N` → `anvil.bridge.fleet.supervise`: N children on consecutive ports, SIGTERM fan-out,
  per-child output parts `.sN` for `--mu-out/--drill-mu-out/--bind-trace/--counts-out` APPENDED /
  SUMMED into the base paths at shutdown — every launcher changes by one flag, the counts merge
  lives in one place; child 0 opens the base port LAST so a base-port poll sees the whole fleet);
  the harness `--bridge` takes a comma list and assigns chunks round-robin by invocation index
  (`bridge_for(m, inv)`, one line in the worker command; Java untouched); static N = ceil(workers /
  8) by default (`--servers` on selfplay / final_read / grindstone, `SERVERS` on the label chain,
  the read chain passes it through; the campaign fleet moves to port+8); the batcher's `--max-batch`
  / `--window-ms` exposed and a per-minute `[server] stats` line (asks, rps, mean batch, queue wait
  p50/p90/p99, forward ms, busy %, queue max — the occupancy an autoscale rule would read); the
  bridge deadline 20 s on EVERY served run unless pinned (the bar arms' 15 poison crashes at 16
  workers, 09-11); **the crude autoscaler = the GPU YIELD** (user pin: `harness/gpu_yield.py` — a
  compute process from outside the run's session using ≥ 1 GiB or ≥ 20% SM for 60 s gates NEW
  chunk launches, active chunks finish, resume after 120 s quiet; a `YIELD` file is the manual form;
  `gpu-yield.json` + `status` show it; default on for grpc runs, `--no-yield-gpu` /
  `ANVIL_NO_GPU_YIELD`). The full autoscale (add a server on occupancy) stays routed. Smoke: 2
  servers under 16 search workers, 32 games (`fleet-smoke-20260914-112514`): 32/32, chunks
  alternated ports, each server ≈ 120 rps at mean batch 2.2 and ≈ 80% forward-busy, merged counts
  `servers: 2`. Tests 309 (+13). **The fleet bench LAUNCHED 11:35** (`scripts/fleet_bench.py`,
  `data/runs/fleet-bench-20260914/bench.md`: cells 8:1 / 16:1 / 16:2 / 24:3 / 32:4 at 64 self-play
  search games each, both seats network-played, rolls 2 — the h2 relabel's saturating regime; g/h +
  server occupancy per cell; ≈ 2 h) → the Build 5 sizing line re-issued with servers as a variable.
- **2026-09-14 (13:51) — THE FLEET BENCH READ** (`data/runs/fleet-bench-20260914/bench.md`; five
  cells, 64 pool self-play games each, both seats network-played, `-search -searchrate 1
  -searchrolls 2`, the e3 ckpt, the pin's jar; the same 64 seeds in every cell). **The wall-based
  g/h is tail-dominated and unreadable** (every cell 23–26 min = one 1,200 s draw-clock game in the
  last chunk; 146–166 g/h flat) — **the steady-state number is the harness's cumulative rate at its
  peak (every worker busy, before the tail):** 8:1 **316** → 16:1 **381** → 16:2 **433** → 24:3
  **468** → 32:4 **323** g/h. Reading: (a) one server DID carry 16 workers at rolls 2 (+21% over 8;
  the relabel's saturation was rolls 4 + the pay copies), the second server adds +14% at 16 (server
  rps 138 → 190 total); (b) **24 workers / 3 servers is the sweet spot — 468 g/h**, +8% over 16:2;
  (c) **32 workers is the CORE ceiling, not the GPU's**: games ran 2.5× slower (median 253 s vs
  84–111; the game-hours sum 4.78 vs 2.3–2.5), the 08-12 w-bench's "peaks at 24, regresses at 32"
  reproduced under search with the servers scaled; (d) **the GPU is not the ceiling anywhere in the
  grid**: forward ms/batch 12 → 14 → 14 → 17 → 25 (the card time-shares at 4 servers but queue max
  ≤ 3 and busy ≈ 62% per server throughout; mean batch 1.7–2.8 = the card stays starved). **Hazard
  found: the load changes the behavior policy.** Asks per game fell 15% at 32 workers (2,656 vs
  3,026–3,234 on the same seeds): `-searchclock` is a WALL-clock allowance (900 s default; search
  switches off past it), so a saturated box searches less — a read at 32 workers reads a weaker
  policy than the same recipe at 16. Standing rule: a search run's load (workers × servers) is part
  of its recipe and stays under the core ceiling (≤ 24 on this box); the allowance's basis (wall
  → game-time or forward calls) routed to the closeout. **The Build 5 sizing line re-issued with
  servers as a variable:** at 24 workers / 3 servers the rolls-2 search recipe runs ≈ 470 g/h
  steady-state ≈ 11K games/day on the idle box → the 20–30K shakedown is 2–3 days, the four-to-six-week
  envelope holds ≈ 300–450K searched games at rolls 2 (≈ 3× the pre-fleet rate of the h2 relabel's
  115 g/h at 16 workers under the lighter recipe; rolls 4 halves it). The lever left on the table:
  the per-server GIL (each server's forward is busy 62% at mean batch 2 — featurization on the
  gRPC threads shares the GIL; moving featurization worker-side or into a subprocess pool would
  let 2 servers do 3's work; the JFR/profile week's Python-side item). The occupancy autoscale
  stays routed (static 24:3 is the run's recipe now).
- **2026-09-14 (15:47) — THE 24-WORKER SERVERS CURVE (`fleet-bench-20260914b`, the user's question:
  does a server lose efficiency at 8 workers, does a fourth pay?):** peak steady-state g/h **24:2 489 /
  24:3 468 / 24:4 418** (rps/server 100 / 74 / 71; wait p90 15.9 / 13.0 / 20.0 ms; forward 15.1 / 16.9
  / 20.3 ms per batch; busy 61 / 60 / 71%; queue max ≤ 2 everywhere). (a) **A server at 12 workers
  is not binding** — 24:2 ≈ 24:3 within one cell's noise; the 8-per-server pin was conservative →
  **N = ceil(workers / 12)** (`fleet.PER_SERVER_WORKERS`; 16 → 2, 24 → 2, 32 → 3). (b) **A fourth
  server costs −11%**: the card time-shares four processes (forward +35%, mean batch 1.9) — the GPU's
  process count is the second ceiling, below the card's compute. **The recipe: 24 workers × 2
  servers (≈ 490 g/h at rolls 2 ≈ 11.7K games/day).** **CORRECTION of the 13:51 hazard:** the
  asks-per-game spread (2,650–3,276) is NOT the search clock — the copy kinds show **0 timeouts in
  every cell**, the copy-crash class is the standing paperCard-null copy crash in every cell, and the
  same 64 seeds produced 4,590–5,441 search windows across the 24-worker cells: bf16 micro-batch
  composition moves the served logits (the first row's leaf values differ in the 3rd decimal between
  cells), the games diverge, and asks follow the games. The standing rule re-worded: load is part of
  the recipe for throughput (the core ceiling at 32, the process ceiling at 4 servers) and served
  runs are not seed-reproducible across fleet configurations — a paired read pins its fleet on both
  arms (it always has: one server per read). The `-searchclock` basis item is withdrawn.
  `fleet_bench.py` reports the peak cumulative rate in its own column from here.
- **2026-09-14 (16:30) — routed by name: upstream PR [#11916](https://github.com/Card-Forge/forge/pull/11916)
  (khaliostr: cheap checks before expensive ones in `StaticAbilityAlternativeCost.alternativeCosts`
  and `ComputerUtilCombat.canGainKeyword`; merged upstream) goes into the research fork AT THE NEXT
  REBASE / engine bump whether or not the sync reaches it (user).** `getAlternativeCosts` sits under
  `getAllPossibleAbilities` = our option enumeration at every window and every search copy's
  heuristic playout; his 53% → 16% CPU was four-player Commander. NOT ADR-0025-exempt: the
  `canGainKeyword` reorder skips `canPayCost` calls, whose mana test draws the game RNG and writes
  AI memory (the 09-09 quietProbe finding), so seeded games diverge — a boundary by construction.
  [#11917](https://github.com/Card-Forge/forge/pull/11917) (the Coram LKI NPE; not in the pool)
  rides the same bump. The JFR read decides whether the bump moves up. **The JFR plan agreed
  (user):** two recordings (one worker on the idle box, 16 games at the recipe; one worker inside
  a 24:2 fleet run), the copy path's hot frames + the engine / bridge / GameCopier / snapshot split
  as the result; then the harness chunk rule for the straggler tail (work-stealing stays routed);
  the AI eval-thread timeout class deferred by name to the horizon leaves' use; the server-side GIL
  lever deferred (24:2 is the recipe, the GPU is starved).
- **2026-09-14 (19:00) — THE JFR READ** (`data/runs/jfr-20260914/`: `idle-read.md` = one worker on the idle box,
  16 pool self-play games at the recipe, 77K samples; `fleet-read.md` = 22 workers of a 24:2 fleet run, the
  first 284 s, 248K samples; `scripts/jfr_hot.py`). **The shape is the same on the idle box and under the
  fleet** (GC 0.5% → 1.4% of CPU; contention at 24 workers is core oversubscription, not a different hot
  path). 92% / 79% of samples sit under the search copies. The cost centres (inclusive, idle / fleet):
  **the exact payability mask 24.5% / 21.4%** (`ComputerUtilMana.canPayManaCost` per candidate, 98% from
  `AnvilOptions.payable`; `groupSourcesByManaColor` 17.9% — the player's mana sources regrouped for EVERY
  candidate of a window); **replacement-effect scans 22.9% / 26.7%** (75% `cantHappenCheck`: every card in
  the game walked per event — engine); **static-ability checks 23.6% / 11.7%** (44% the state check, 32%
  via `getAlternativeCosts` = PR 11916's path, 12.8% / 6.0% inclusive); **GUI view maintenance 19.9% /
  18.2%** (`CardView` via `updateStateForView` + `updateKeywords` + `updateAbilityTextForView`, on LKI
  copies (52%) and on every card the copier builds (47%) — a headless worker maintains views nobody
  reads); **the game copy 17.5% / 22.0%** (one per option per window; `CardFactory.getCard` 11–17%: the
  copier REBUILDS cards from scripts instead of cloning). The 09-09 suspects: the payability predicate
  confirmed; trigger churn negligible (0.1%); the obs snapshot 0.5–1.5%; the bridge 0.2–1.7%. The
  exception count (14K/2 games) was a false lead (`getStackTrace` for a depth field; 0.0% of samples).
  **Levers, ranked by share × ease:** (1) the mask: memoize the mana-source grouping per window and/or an
  exact-safe upper-bound prefilter (total available mana < the cost's pips ⇒ skip the test) — ours,
  mask-exact by construction, forkcheck-provable, ≈ −10–15%; (2) a headless-views switch (no
  `TrackableObject` updates when no GUI) — one engine flag, ≈ −15%, forkcheck decides (views are read by
  `canBeShownTo` in the copier's hidden-info prune); (3) PR 11916 at the rebase ≈ −5%; (4) the copier's
  card rebuild and (5) the per-event replacement scan are upstream-scale (routed to the closeout; the
  Rust-subset argument's numbers). Together (1)–(3) ≈ −30% of worker CPU ≈ +40% g/h at the core ceiling.
  **The chunk rule landed** (final_read / fleet_bench: chunk = ceil(games / 4·workers); selfplay's
  `batch_chunk` 2 → 4 rounds). **Incident 17:58:** `jfr print --json` ×2 on the idle recording (~4 GB RSS
  each) with 24 recording JVMs live → OOM → the desktop killed; the fleet run died at 16/64 (its 22
  recordings are the fleet read). `jfr_hot.py` streams now; memory note updated.
- **2026-09-14 (19:30) — THE MANA-SOURCE MEMO LANDED (the JFR read's first lever; user: memo scoped to one
  scan, the prefilter dropped as not exact-safe, the 08-11 mask cache left off).** Fork `1dd36f7342`:
  `ComputerUtilMana.groupSourcesByManaColor` is built once per `AnvilOptions.buildPriorityOptions` scan
  (a ThreadLocal memo armed for the scan's duration, a fresh copy per consumer, the heuristic AI's own
  payment calls never see it; `-Danvil.scan.sourcememo=off` = the per-candidate rebuild). **Proofs:**
  the identity gate (`scripts/build3_memo_gate.sh`, memo off vs on on ONE jar, obs-diff window by window)
  **32/32 games, 32,306 windows identical** at one worker; the forkcheck `run-20260914-memo` **499/500**
  vs the 08-21 baseline, 20260969 the standing crash → **PASS → fork pin `1dd36f7342`** (ADR-0025-exempt:
  the mainline heuristic path never arms the memo; the bridged path's identity is the gate's). **Finding
  — the eight-worker obs-diff gate is no longer an identity instrument on a served arm:** the first
  gate at 8 workers diverged 13/120 games on IDENTICAL masks (a near-tie argmax pick flipped between
  two `Play land` options: bf16 micro-batch composition), and the same games replayed identical at one
  worker → standing rule: an identity gate on a served arm serves batches of one (`WORKERS=1`). The
  gate's walls hint at the win (off 356 s / on 337 s on the no-search recipe). The re-profile (one
  worker, 16 games) + the 24:2 bench cell on the memo jar launched 19:30 (`data/runs/jfr-20260914-memo/`,
  `fleet-bench-20260914-memo`); the reference: 489 g/h, the mask 24.5% of samples.
- **2026-09-14 (20:35) — THE MEMO'S READ: the profile moved as predicted, the single bench cell is
  inconclusive.** Re-profile (one worker, 16 games, the memo jar, `data/runs/jfr-20260914-memo/idle-read.md`):
  `groupSourcesByManaColor` **17.9% → 5.2%**, `canPayManaCost` 24.5% → 12.9%, `AnvilOptions.payable` 25.5%
  → 14.0% (the remaining half is the per-shard payment logic proper); per search copy the option playout
  fell 212 → 194 ms p50 (−8%; −16% adjusting for the memo run's wider boards — copy_ms, a pure board-size
  proxy the memo cannot touch, ran 86 → 97 ms). The 24:2 bench cell read **445 g/h peak vs 489** — but
  its games were much wider (copy_ms p50 138 vs 81, ms/window 352 vs 290, the servers at 79 rps / 47%
  busy vs 100 / 61%: the workers were slower on the engine, not waiting on anything), so the cell is a
  board-size draw, not a memo read. **Lesson: one 64-game cell has a ≥ 10% noise floor under search
  (the games diverge per cell, the draw-clock games land where they land); per-lever reads use the
  one-worker profile's shares and per-copy ms, and a g/h read needs ≥ 3 cells per arm** — the next
  lever (the headless-views flag) is read that way, and the g/h of the whole batch of levers is read
  once, at three cells per arm, before the Build 5 sizing line is touched. The memo stays (exact, free,
  the profile's −12 points).
- **2026-09-14 (20:50) — THE VIEWS LEVER DROPPED; THE THROUGHPUT WEEK CLOSES (user).** The survey: the
  engine reads card views AS STATE outside the GUI (the state name via `CardTraitBase` / `CardState`,
  zone + controller in `Game.forEachCardInGame`, card text in `SpellAbility` (two compares) and `Card`
  (the transform marker), visibility in the copier's hidden-info prune) → a blanket views-off switch
  changes rules outcomes; the safe subset (name / zone text / damage / marker / image keys) is ≈ a third of
  the 20% for a change on the layer every rebase touches, whose failure mode is a silent post-rebase
  forkcheck mismatch. Dropped as an Anvil-side change. **Routed by name to the closeout's upstream
  list:** the LKI copy recomputing a full view per event (52% of `updateStateForView`; clone the view
  props instead), the copier's `CardFactory` card rebuild (17–22%), the per-event replacement scan in
  `cantHappenCheck` (17%) — small reviewable PRs in the vein of #11916. **The throughput week's
  assets:** the fleet (`--servers N`, the bridge list, the stats line, the GPU yield), the recipe (24
  workers × 2 servers ≈ 490 g/h at rolls 2), the chunk rule (four rounds per worker), the mana-source
  memo (the mask's share halved; fork pin `1dd36f7342`), PR 11916 queued for the rebase, `jfr_hot.py` +
  `fleet_bench.py` + the one-worker gate as standing instruments; the three-cell g/h read follows the
  rebase. **Next: evening 5 = mainline surface acting (modes first) — a design session before code.**
- **2026-09-14 (session 3, evening) — THE DESIGN SESSION BEFORE EVENING 5; THE REBASE PLACED; THE
  SEARCH-SHAPE READS** ([ADR-0106](../decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md)).
  State review: Build 3 one evening from closing (six surfaces + tuck served, all −0.17 ± 1.80 vs
  withheld; the pay head withheld → the loop), the throughput week closed, the box idle. **Evening 5
  pinned (seven):** the (option, answer) pair chosen at the priority window (no mid-action fork;
  the second round already values it; the mainline arms the `SurfaceDirective` consumed at the
  callback); the natural line = the served behavior (the gated head); bar 0.10 / T 0.025 / rolls 2,
  no bar sweep; the rule kind-agnostic, modes served first, entity acting a second arm if modes are
  not negative; the multiplier measured by the smoke; the 600-game paired read (acting within one
  SE of the gated arm → the gate retires on searched windows). **The rebase lands between evening
  5 and Build 4** (user): one era for the post-Build-4 read + shakedown + big run + close, the
  shakedown as the rebase's landmine catcher, drift 263 commits now vs ≈ three months' after the
  run; cost one to three days + a reference re-read on the new jar (owed anyway — the probe cost).
  Sizing re-issued: ≈ 490 g/h → 330–500K games; with surface acting (≈ 2.5×, est.) ≈ 350 g/h →
  235–350K; launch two to three weeks out, close six to nine. **The search-shape reads (user: worth
  the week — signal strength has been the recurring bottleneck, depth the lever):** (1) the leaf
  calibration on the PRIORITY slot first (the pay slot's leaf family plumbed over; three
  heuristic-control arms on one seed set; signal-to-noise per horizon, flip rate vs the one-ply
  pick, outcome agreement — hours, no training, runs while the acting code is written); (2) the
  shakedown = the multi-arm search-budget read at EQUAL BOX TIME (shallow-wide / the recipe /
  partial-deep at top-3 × the measured peak horizon; the arm with the best network-alone gain per
  box-hour wins, ties to the cheaper); (3) the partial-expansion slot in the fork; (4) **the
  allocation head** (fork L) — the pivotality head generalized to "which shape", labels = the
  search's measured gain per shape, the floor kept: the model learns which assessment is useful to
  it. The two-ply shape (72 copies/window, ≈ 10–12×, ≈ 50K games) is gated on the deep arm. Not a
  fresh model: the subject is the day-zero ckpt, the early signal its 1.6pp pretrain debt and
  whether network-alone moves. Standing rule: search recipes compare at equal box time, never
  equal games. **Next: evening 5's fork code (the acting rule over sub rows, the mainline arm, the
  leaf plumb `-searchleaf`, the partial-expansion slot) ∥ the priority-slot calibration read.**
- **2026-09-14 (session 4, late evening) — EVENING 5's CODE: THE LEAF PLUMB, THE PRIORITY-SLOT
  CALIBRATION CHAIN, MAINLINE SURFACE ACTING** ([devlog](../devlog/2026-09-14-session4.md)). Four
  determinations before code (the user took the recommendations): **the pair rule = the bar-lifted
  joint pick** (stage 1 per expanded candidate: answer margin = max V(answer) − V(natural answer),
  ≥ bar → an answer sampled from the answers' softmax at T and the candidate's option value LIFTED to
  it; stage 2 = Build 2's option rule on the lifted values — a flat softmax over pairs would weight an
  expanded candidate by its answer count, max-over-answers is the winner's curse; surfaces off =
  Build 2 byte-identical); the natural option outside the top-B = its own `ans_unsearched` class, B
  stays 2; the mainline arm lives to the seat's next quiescent window (the copy's leaf) and is
  label-guarded; the calibration read sized at rate 0.1 / rolls 4 / 200 games per seat / 24 × 2. **The
  leaf plumb** (fork `de9745d089`: `-searchleaf next|eot|h<N>|end` on the first-ply copies, the
  surface slot following, `snap` per roll under a horizon leaf) → **the calibration chain LAUNCHED
  22:29** (`data/runs/build3-priocal/`: arms next / h2 / end on heuristic control; next done in 40
  min, h2 ≈ 1 h per seat run; the read `scripts/prio_calibration.py`; caveat: a heuristic seat voids
  what its AI would not play — the spread reads over the heuristic-playable set, ≈ 61% of windows
  with ≥ 2 valued candidates on the 09-11 arms). **Mainline surface acting** (fork `e28f40d476` →
  `abec2b2982`): `Pending.SurfAnswers` + the two-stage `decide` + the row's `lifted` / `ans` verdict,
  `SurfaceDirective.armMainline` (per (game, seat), label-guarded, taken at the next quiescent
  window; census `surfaceAct` kind / ord / outcome act | miss:* | unfired), `-searchactkinds`
  (pay never; pinned `actkinds`), tests 14. **The first arm design never fired** (14/14 unfired: a
  cast spell's entity choices fire at resolution, after the play returns; and the served-path traces
  carried the method name as the label) — fixed in `abec2b2982`; the mechanism smoke (4 games, all
  kinds, bar 0.02) then fires arms at the next window (entity one / set / order act, a few
  unfired). The recipe smoke (8 games, modes, bar 0.10): 547 windows, 259 sub rows (23 mode), 3
  mode windows on acted options all below the bar — **mode acting is rare at bar 0.10; the 600-game
  read will say how rare**; ≈ 3,800 copy forward calls per game at rate 1 / rolls 2 / surf 2. Forkcheck
  `run-20260914-build3-e5b` on `abec2b2982`: **498/500, the standing pair (20260739 replayed to the
  baseline hash on the same jar) — PASS 00:30 09-15 → fork pin `abec2b2982`** (the partial run on
  `e28f40d476`: 450/452, the same pair). **The paired read (A6) QUEUED** (`scripts/build3_e5_read_queue.sh`:
  on = the served set under the search recipe vs act = + `-searchactkinds mode`, 300 games per seat,
  24 × 2, jar snapshot `abec2b2982`; GO set on the forkcheck PASS; launches when the chain's
  read lands). Next: the calibration read (≈ 04:30 09-15); the
  paired read; then the partial-expansion slot (C3) sized by the calibration read.
- **2026-09-15 (morning) — THE PRIORITY-SLOT CALIBRATION READ; THE PAIRED READ RELAUNCHED**
  ([devlog](../devlog/2026-09-14-session4.md)). C1's read (`data/runs/build3-priocal/read.md`, 1,360
  windows joined identical, 828 read): **next is the resolved leaf** (spread 0.086 vs roll SD 0.009,
  91% resolved; the acting rule converts by the outcome at bar 0.10: +0.062 ± 0.025 on 81 positives);
  **h2 is ≈ 8× noisier per roll** (SD 0.073, 35% resolved, ρ 0.34 vs next, flips on 53% of windows)
  **yet its flips read right by the outcome** (+0.022 ± 0.008, 87 up / 58 down) and its acting
  conversion is ≈ 2× next's at the same bar; the end leaf is binary at 4 rolls (median spread 0).
  **Caveat: CRN across arms** — an h2 copy and the end copy of the same roll share their first turns,
  so the deeper leaves' agreement with the outcome is optimistic by construction; the clean read = an
  end arm on independent roll seeds (routed: `-searchrollsalt`, one arm, after the paired read).
  Provisional: next stays the recipe's leaf; h2 is the shakedown's deep arm, not a winner; no second
  ply read. The paired read failed at launch (the harness refuses `-search` without `-labels`; the
  launcher now passes it) and was **relaunched 08:30** (on / act, 300 per seat, 24 × 2, jar
  `abec2b2982`).
- **2026-09-15 (midday) — THE PAIRED READ: MODE ACTING NEARLY INERT AT BAR 0.10; RUN HYGIENE REBUILT;
  THE ENTITY ARM** ([devlog](../devlog/2026-09-14-session4.md)). act − on **−0.69 ± 0.81pp** (n 579,
  9 up / 13 down): in 21,903 searched windows the mode answer stage reached 115 and cleared the bar
  9 times (9 arms fired clean) — "nothing broke", not a mechanism read; the gate decides only
  unacted windows by construction, nothing to retire; pin 4 → the entity arm (`actent`:
  entity_one + entity_set + mode) launched 12:39 on the same reference — **the first real launch
  through `anvil.runs`** ([ADR-0107](../decisions/ADR-0107-run-launcher-and-checkin.md): the
  launcher as the checklist, the alert queue, the check-in task; the quickstart's §7½; the
  documentation review session routed as Build order 4¾). The salt plumb (`-searchrollsalt`) for
  the de-confounded end arm written; its forkcheck + arm queue behind the entity arm.
- **2026-09-15 (afternoon) — EVENING 5 CLOSED; BUILD 3 CLOSES WITH IT** ([ADR-0106
  addendum](../decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md)). The entity
  arm −0.69 ± 0.91 (n 579; 70 acted answers in 600 games, 63 fired clean); with the mode arm −0.69 ±
  0.81: neutral at low exposure, nothing broke, the gate moot. **Recipe pin: surface acting ON**
  (`-searchactkinds entity_one,entity_set,mode`, bar 0.10; the bar a settings-pass axis). C1
  provisional (next the resolved leaf; h2's flips right by the CRN outcome but optimistic by
  construction) → the salted end arm running (fork `e63a0cac20`, forkcheck ∥). Next: the salt read
  → C1's verdict + the partial-expansion slot; Build 3's closeout ADR; the rebase; Build 4.
- **2026-09-15 (night) — C1's VERDICT: NEXT STAYS THE LEAF** ([ADR-0106
  addendum](../decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md)). The salted
  end arm as the judge: h2's flips vs next +0.010 ± 0.010 (from +0.022 ± 0.008 under CRN — half was
  the shared rollouts); the CRN end leaf's flips −0.006 ± 0.008 (noise as a picker); acting
  conversion next +0.033 ± 0.016 at bar 0.05, h2 +0.081 ± 0.030 at bar 0.10 (a hint, +0.046 ±
  0.038). The shakedown's deep arm provisional at top-3 × h2 × rolls ≥ 4; no second ply. Standing
  rule: outcome arms under an independent roll salt. Routed: the pay slot's 09-11 h2 result
  re-read salted. The check-in routine off (idle box). Next: the partial-expansion slot, Build 3's
  closeout ADR, the rebase.
- **2026-09-15 (night) — THE PARTIAL-EXPANSION SLOT (ADR-0106 C3): PRICED, GATED, BUILT**
  ([devlog](../devlog/2026-09-15-session2.md); [ADR-0106 addendum](../decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md)).
  **The price**: an h2 copy is ≈ 10× a next copy in wall on the calibration arms (2,877 vs 304 ms
  mean per valued copy) and ≈ 13× in forward calls on the network arm (≈ 65 vs ≈ 5) — C2's 2.3×
  assumed 3×; the deep arm as drafted (top-3 × h2 × rolls 4 on every searched window) would be
  ≈ 8–10× the recipe per window and play ⅛ the games at equal box time (unreadable). **The shape**
  (the user took the recommendations): the deep round runs at decide time where the first ply's
  natural margin lies in [lo 0.02, bar) — the shallow rule sees something but not enough to act on
  (11% of heuristic windows; the natural is within 0.01 of the best on 77%) — plus a seeded floor
  (0.1) on the rest for fork L's labels; the deep set = the top-B by lifted value + the natural; the
  deep copies play the (option, lifted answer) pair; the option stage runs on the deep values over
  the set only (the rest pruned) under its own bar (default the acting bar); surfaces stay at next;
  rolls 4, CRN across the set. Fork: `-searchdeep B [-searchdeepleaf h2] [-searchdeeprolls 4]
  [-searchdeeplo 0.02] [-searchdeepfloor 0.1] [-searchdeepbar]`, `Pending.DeepRound`, the row's
  `deep` block (gate verdict, shallow margin + argmax, the set + values, the copies), header pins;
  tests 24. **The smoke** (4 games, recipe + deep 3, jar `5e333e96930`): 4/4, 0 copy crashes; the deep round on 23% of windows (band 82 / floor 11 of 399), 18.8 s p50 per round, 84% of copy forward calls (≈ 6× the recipe in calls, ≈ 3× in one-worker wall), flips the first-ply argmax on 55/93 rounds, clears the bar on 9 (all acted). Standing rule: a shape's per-copy price is measured before its arm is sized.
  Launched: the queue (forkcheck on the deep tip → the 24 × 2 bench pair recipe / recipe + deep →
  `deep_bench_read.py`); **forkcheck PASS 22:15 (499/500, the standing crash) → fork pin `5e333e96930`**; **THE PRICE (23:03)**: the bench pair (24 × 2, 64 games each, jar `5e333e96930`): recipe 294 g/h peak (213 wall; 69.5 searched windows/game, 3,723 copy forward calls/game = first ply 2,208 + surfaces 1,515, copy wall 131 s/game) vs recipe + deep 3 **104 g/h peak (88 wall)** — the deep round on 20% of windows (band 653 / floor 254 of 4,475), 16,553 calls/game (deep 13,181), deep copy wall 559 s/game, deep acts 98 (2.2% of windows; 11% of its rounds), deep copies leaf 9,639 / end 1,249 / crash 9, 0 game crashes → **the deep arm = ×4.45 forward calls, ×2.83 box time per game** (one cell per arm: a draw for g/h, the call ratio the per-lever number). At equal box time the deep arm plays 35% of the recipe's games (≈ 2.5K/day at 24 × 2; a three-day shakedown arm ≈ 7.5K games). The slot is CLOSED: built, proven, priced. Routed: the pass-through next peek on deep copies; the deep bar / band /
  floor as settings-pass axes. Next: the queue's reads → the fork pin + the deep arm's multiplier;
  Build 3's closeout ADR; the rebase.
- **2026-09-16 — THE PRE-LAUNCH COMPLETENESS AUDIT ([ADR-0109](../decisions/ADR-0109-prelaunch-completeness-audit.md))**:
  the user's two questions (what still defers to the heuristic; are we using every throughput
  lever). Coverage: 14 bridged tags; deferred = payment (withheld on purpose → the loop),
  **targets outside a cast (not traced — the largest true gap, the mode head's mechanism)**, the
  closed enumerations + naming (cheap, unserved), the low-weight class (piles, shield division,
  play/draw, Leylines, confirms, concession); the search's window coverage (main-phase priority
  only) and combat legality (GUI-owned) are boundaries, not deferrals. Throughput: Java CPU binds
  at 24 workers; unexploited and ours = the allocation head (acts on 9.5% of windows at rate 1;
  ≈ 1.5–2× the games), the void re-roll skip (29.6% of first-ply copies void; ≈ 7% of copy CPU,
  exact), the surface round's breadth (41% of copy calls for 70 acts / 600 games), the mask cache
  (small residual). **Decision (user): before the run — targets as a surface (Build 4's evening;
  the mode head rides it, the gate's retirement pre-registered on a three-arm read), the
  allocation head (before the post-Build-4 read; an allocation arm in the shakedown), the void
  skip at the rebase; ≈ a week; the rest after the run by name.** Standing rule: surface coverage
  closes before a big run. The §3d′ ledger updated.
- **2026-09-16 — BUILD 3 CLOSED ([ADR-0108](../decisions/ADR-0108-m12-build3-closeout.md))**: the
  record of five evenings (09-07 → 09-15) — six surfaces served from `m12-build3-e3` (entity one +
  set +2.06 ± 1.83, the gated mode + the whole set −0.17 ± 1.80, ordering + damage +0.52 ± 1.82,
  surface acting −0.69 ± 0.81 / 0.91: nothing broke), the payment head withheld to the loop after
  five negatives, the probe fix (≈ 2.7pp recovered for every network arm), C1 (next the resolved
  leaf, h2 a hint), the partial-expansion slot priced (×2.83 box time); the shakedown's three arms
  pinned (shallow-wide / recipe / recipe + deep 3); the recipe's real rate 294 g/h (the ≈ 350
  estimate was high); a standing rule born (a served answer is realized with everything the
  heuristic's answer bundles); twelve items routed by name. Next: the rebase (ADR-0106 B), then
  Build 4.
- **2026-09-15 (community watch, noted + routed)** — the Discord read (the survey doc's 09-14/15
  follow-up). chrismaghuhn's **pre-release freeze** (predictions committed before Arena data, the
  17lands comparison after; where Anvil and the heuristic disagree and which lands closer to
  human play, over several sets = a bias map) → routed by name as a closeout-era read (set-sized
  pool chunks, Build 4's unseen-card readiness; no M12 dependency). talor's `tinymtg` (TS, <10K
  LOC, deterministic, forge-script translated ahead of time, 4,500 cards, no benchmark yet) → the
  Rust-subset item stays gated; a data point that the translation is tractable, fidelity via a
  twin harness the only entry. LordOfThePigs's per-card win-rate table + Bo1 outcomes shared on
  Drive → routed to Tutor (not downloaded). **Jetz (core) confirmed combat / damage-assignment
  legality lives in the GUI module, relocation to forge-game desirable but large** — the field
  guide's finding from a maintainer → an engine-side legality surface (the block requirement
  fixed-point, the lethal-assignment rule) routed to the upstream worklist for the rebase era.
  manabrew is dropping its Rust port (the table corrected). Nothing on the M12 path changes.
- **2026-09-16 (session 2: the upstream survey before the rebase; community watch)** — the user's
  ask: read upstream's patches since the engine pin before pinning. Upstream `23c3d2a85d` →
  `97535e047f` (09-16 10:36): 283 commits, ≈ 45 engine / AI; **the controller API unchanged**
  (`PlayerController` + `PlayerControllerAi` diff = one storage-land hunk); the overlap 13 files,
  two real conflicts (`ComputerUtilMana`: the memo vs the AiCardMemory refactor #11667;
  `AiBlockController`: talor's cache vs #11790). **Pin = the tip `97535e047f`**; #11916 and #11925
  (khaliostr's, not ours) merged 09-14 / 09-16, nothing to carry. Four changes touch our decisions:
  **#11667 reopens the probe leak** (a new typed set `MemorySetMana.UNPAID_COSTS` written on the
  test-mode payment path `autoPayable` runs; the probe's snapshot list is six card sets → snapshot
  every entry of the memory map, a unit test + the divergence read); **#11780 is the views lever
  we dropped 09-14** (`setNoGUIUser` → `DummyCardView`, copies get it free via `GameCopier`; a
  flag on the harness games, flag-on/off forkcheck, re-profile); **CR 605.1a (#11778) is a rules
  change** (a library-moving activated ability is no longer a mana ability; one pool card,
  Chromatic Sphere); **#11861 rewrote the AI timeout machinery** (our bridged path overrides above
  it; the heuristic seats move). The reference moves (blocks #11790, pump timing, any-color mana,
  storage lands, reveal effects; 8 of 1,701 pool scripts, Hogaak + Emrakul the ones that play
  differently) → the ability-key re-dump + diff on the new jar; three LKI NPE fixes may retire part
  of the copy-crash class (read, don't assume). Recommendation (open): land it as a MERGE with a
  pre-merge tag (a rebase rewrites the twelve pinned tip hashes every run header cites), the
  archaeology ≈ a day + a box day; the probe extension and the views flag ride the same jar. The
  full survey: the 09-16 session-2 devlog; the rebase ADR's context when the user confirms.
  **Community watch:** Shedletsky's runner fleet at ≈ 1,000 games/min over 4 machines / 92 workers
  (heuristic-only; noted, nothing routed); the AI-speed thread (khaliostr's unupstreamed
  evaluation budgets → a determinism watch item on the upstream worklist, our position count-based
  + flag-gated); **talor asks that his block-legality cache (Tyrathalis/forge#1, our fork's
  `AiBlockController` delta) be upstreamed → queued as the first post-launch upstream patch**;
  khaliostr's Java `forge-engine` module (the front-end / engine split) = the engine-side legality
  surface's direction from the other end. The user stated the upstreaming schedule publicly: one
  patch at a time while the big run runs.
- **2026-09-16 (session 2, continued) — THE UPSTREAM MERGE LANDED
  ([ADR-0110](../decisions/ADR-0110-m12-upstream-merge-20260916.md))**: the user's call — a merge
  (the "rebase" wording was imprecise), the pin at the tip, the archaeology resized to a day.
  Tag `pre-merge-20260916` on `5e333e9693`; worktree `../forge-merge`, branch
  `merge-upstream-20260916`; the merge of `97535e047f` = two conflicts (`AiBlockController`:
  #11790's restructure + the fork's `canBlockCached`; `FCollectionTest`: upstream's deterministic
  test) + one rename (`predictMana`) → `4112a89563`; the riders → `1db054ade4`: the probe snapshot
  (whole-map `snapshotAll/restoreAll`, `AiMemorySnapshotTest`), the views flag `-Danvil.nogui=on`
  (`AnvilGames.noGui` at the four game-creation sites), the void re-roll skip `-searchvoidskip`
  (rolls ≥ 1 of a roll-0-void candidate recorded `skip`, arrays unchanged). Tests 69 + 2 pass.
  The runner gained `JVM_ARGS`; `scripts/merge_boundary_queue.sh` = the flag-off baseline
  `run-20260916-merge-baseline` (compared to 08-21 for the record) → the flag-on proof
  `run-20260916-merge-nogui` vs the new baseline; launched 09:40 through `anvil.runs`
  (`merge-boundary`). Standing rule: engine bumps land as merges with a pre-merge tag. Next on
  the merged jar: the pin move, `compare.py`'s default, the reads (heuristic ref + `iter-019`,
  three-cell g/h, the probe's divergence read), the ability-key diff, Build 4.
- **2026-09-16 (session 2, continued) — THE ALLOCATION HEAD'S FIRST FIT (ADR-0109 item 2; forks
  D / L): the frozen-trunk read.** `scripts/alloc_fit.py`: every search row of the six pre-merge
  search runs (the 09-15 bench pair + the four b3e5 act / actent arms; **52,697 windows, 1,328
  games, joined 100%** to their priority decs in the ingested stores) featurized with the e3
  ckpt's serve featurizer, the frozen `[STATE]` + scalars (n_opts, turn, phase, seat, the value
  head's win) → a logistic head, five game-grouped folds, `data/runs/alloc-fit-1/probe.json`.
  **Label margin ≥ 0.10 (the acting bar; 9.2% of windows): AUC state + scalars 0.802 ± 0.014,
  state alone 0.780, scalars alone 0.692** (bars 0.05 / 0.02 the same within 0.01). **The
  allocation curve at the 0.1 uniform floor: 90% of the acts captured at 67% of the search's
  forward calls (53% of windows) → ×1.49 in search cost, ×1.25 in whole-game box time at the
  recipe's copy share (131 of 213 s per game, 09-15); 80% at 56% → ×1.80 / ×1.38.** The frozen
  probe already clears the M10 head's 0.69 that ADR-0109 sized from; the trained head (the extra
  output on the priority ask, the loop's own labels) is the served version. Reads: the head's
  arm in the shakedown at equal box time (pre-registered in ADR-0109). Next for the head: the
  output on the priority forward pass + the Java rate draw as the head's probability with the
  floor (`-searchfloor`), on the merged jar, during Build 4.
- **2026-09-16 (session 2, continued) — THE BOUNDARY LANDED (ADR-0110 addenda 10:12 / 11:15).**
  The new baseline `run-20260916-merge-baseline` on jar `1db054ade4`: fidelity 451 / 48 / 1
  (08-21: 450 / 50), 332 / 500 identical to 08-21 (the boundary's drift, for the record);
  `compare.py` defaults to it. The views-flag proof `run-20260916-merge-nogui`: **499 / 500
  identical, 20260969 the standing launch-unstable seed → PASS**; the default flips on the flip
  tip `8137d0c41c` (+ the fork's console modes headless; its forkcheck heads the g/h queue).
  **The fork pin → `1db054ade4`**, `master` fast-forwarded (unpushed). **`merge-ref` (iter-019 on
  the merged jar, 2,000 games, 1 crash): 0.5300 raw / 0.5348 ± 0.0110 Ante-corrected — the era's
  reference number** (0.5279 was the previous era's). The ability-key drift 15 / 5,148 (the OOV
  path = host + kind, verified; the table's extension routed). Running: `merge-heur` (the
  mirror) and `merge-gh` (the flip forkcheck → three 24 × 2 recipe cells; the recipe's rate on
  the merged jar with the views lever + the void skip in = the big-run sizing line).
- **2026-09-16 12:05 — `merge-heur` READ**: the mirror's two seat arms play the same games (no
  bridged seat) → one population of 1,000: 980 decided, 19–20 draws, 1 NPE crash; **seat 0 wins
  0.470 ± 0.016** (the fixed deck-pair population's seat asymmetry; the Build 2 "0.500" was the
  two arms' mean by construction); 23.2 turns mean. ADR-0110 addendum.
- **2026-09-16 13:25 — THE BOUNDARY CLOSED (ADR-0110 addendum).** The flip tip `8137d0c41c`
  proven (499 / 500) → the pin; three 24 × 2 recipe cells on it: **peak 347 / 353 / 288 → 347 g/h
  (+18% vs the pre-merge 294; wall 272 / 166 / 186 carries the tails)** → the big-run sizing line
  **235–350K games in the four-to-six-week envelope** at ≈ 8.3K games/day. The era's assets:
  the baseline, the reference 0.5348 ± 0.0110, the mirror population, the Ante arms, the key
  drift + the OOV path, the allocation head's frozen read. Build 4 opens on this jar: the targets
  surface first (the ability table extended with the 16 new keys before any served arm).
- **2026-09-16 (session 3) — BUILD 4 OPENED: the ability table extended, the representation scope
  pinned, the mask-cache gate re-read launched.** The user's premise corrected (the void re-roll
  skip landed as an ADR-0110 rider). Decisions (user): the order = the table → the targets
  evening on the current trunk → the three representation items under ONE re-warm → the
  allocation head on the re-warmed trunk → the post-Build-4 read; **the scope = all three items**
  — the finding: the obs records every stack instance but the encoder consumes only `stack_size`,
  so stack-entry tokens are a strength item for the network-alone windows; `sa_emb` is still the
  string-id table; format-as-features is a Python-side lookup from the row's format id (inert
  single-format, rides the re-warm). **The table:** the pin's re-dump = the riders' key set;
  `scripts/extend_ability_table.py` → `abil-cf2ca6ba-b4-qwen3` (15,489 keys; the 15,473 served
  rows byte-identical, cosine check 1.00000); `bridge.server --abilities` serves it to the e3
  build; the pool dump re-pinned; fit defaults → b4 (ADR-0110 addendum 14:40). **The mask-cache
  gate** (`maskcache-gate`, 120 games at one worker, off vs on on the pin jar, e3 serving) launched
  14:11; the read ≈ 14:50 — any mask-class first divergence = OFF stays.
- **2026-09-16 14:50 — the mask-cache gate re-read: FAIL (108 / 120 identical at one worker, 9
  mask-class first divergences on the ADR-0102 classes) → the cache stays OFF, closed for the era
  (ADR-0110 addendum 14:50).** **The target surface's real site found by the 4-game smoke on the
  callback tip: 47 `playTrigger` vs 3 `chooseTargetsFor` — the AI targets its triggers inside
  `doTrigger` (`PlayerControllerAi.prepareSingleSa`), never through the callback ADR-0109 named.**
  The fix: `PlayerControllerAi.preparedTrigger(sa)` (a protected no-op hook between a trigger's
  preparation and its play, at both sites — the first fork delta in that file) overridden in the
  census controller: one TARGET window per targeting ability in the prepared chain
  (`playTriggerTargets`), the heuristic's picks = the natural line, a directed / bridged answer
  re-targets the ability under `canTarget` + `isTargetNumberValid`; every other decision the
  trigger logic made (modes, X, optional yes/no) is kept — exactly the joint choice ADR-0109 wants
  (fork `5dd8ab3ede` on the callback tip `23b8e36c03` + test fix `9438db1146`). The smoke +
  forkcheck queue relaunched on it 14:46 (`build4-targets-queue2`); the superseded forkcheck
  killed at 38/500.
- **2026-09-16 15:05 — ADR-0111 (Build 4 opens) written; the evening's chain armed.** The label
  pool `b4-tgtlab` (1,000 games, 24 × 2, the recipe with surface acting, the e3 build serving its six
  on the b4 table, `-searchsurf 2` / rolls 2) launched 14:52; `scripts/build4_targets_chain.sh`
  (`build4-targets-chain`) waits on it: ingest → the b4s table (the pool's side keys folded in) →
  the six-plus-`surf_target` fit chain (5 folds, e3's recipe, distillation on entity + mode + target)
  → `m12-build4-e1` → the served-head smoke → the three-arm read (`b4e1`: off / on / nogate, 300 per
  seat, network alone, one jar `forge-targets-gate.jar` = tip `a36975497b`). Forkchecks: the retarget
  tip `5dd8ab3ede` running (`run-20260916-build4-targets`), the gate tip queued behind it
  (`run-20260916-build4-gate`). Reads land overnight.
- **2026-09-16 15:20 — the representation completions BUILT (worktree `anvil-wt-b4rep`, branch
  `b4-representation`, commit `dc6b362`; not yet on main — the main tree is under the evening's
  chain), all three additive and ZERO-INIT so the day-zero forward is byte-identical (the identity
  contract in `tests/test_representation_b4.py`; the worktree's full suite 313 pass):**
  (1) format-as-features — the explicit scalars (start life, deck size, singleton, command zone,
  mulligan variant) from `vocab_mtg.json`'s `format_features` table ride the globals after the
  one-hot (`TRANSFORM_VERSION` 5; load_compat's end-of-globals pad; the one-hot through
  `state_proj` was already the learned format embedding); (2) the stack entries — `assemble`
  passes the recorded stack through, `anvil.encoder.stack_fields` maps up to 8 entries (top-first)
  onto host rows / ability-table rows / controller / first card target / first player seat, and
  `StateAssembler` adds each entry onto its HOST token (text + controller + position), its card
  target's token and the [STATE] token for a player target — **additive, not new tokens: a
  zero-vector token would still renormalize the attention, so a token design cannot be
  identity-preserving; the additive form is, and the re-warm only improves from the current
  strength** (the token variant stays the alternative if a probe says the stack information does
  not land); (3) the ability text beside the string id — `cand_ak` per priority candidate (the
  option's `ak` through the AbilityCache) → `cand_abil_proj` (zero-init, 2560 → 64) added to
  `sa_emb`'s descriptor, so an OOV string keys on its text alone and a new set is an append (the
  string path is dropped later, after the loop has trained the text path — a flag at the closeout,
  not a re-init now). Fork tip `7343c40d84`: the ability key on every recorded stack entry
  (recording-only; its forkcheck `run-20260916-build4-stackak` queued behind the gate tip's).
  **OPEN for the next session (the user's call): the re-warm's recipe** — `value_pretrain fit
  --build` (the Build 1 recipe) has no init flag (it starts from `iter-019` by design), so the
  re-warm is either (a) the Build 1 fit re-run with the new fields present → a new day-zero ckpt
  → the surface chain on it (the served set re-fit on the moved trunk), read by the Build 1 cells
  (one-ply ≈ 0.39, state ≈ 0.375 to hold) — the clean lineage; or (b) a continuation fit from
  tonight's `m12-build4-e1` on the banked priority labels + the value targets with the new paths
  unfrozen — cheaper, keeps the surface heads. The new fields get no gradient until one of these
  runs; until then every build serves byte-identically.
- **2026-09-16 15:50 — forkcheck PASS on the retarget tip `5dd8ab3ede`** (`run-20260916-build4-targets`
  499/500, 20260969 the standing seed, fidelity 451/48/1 = the baseline's). The gate tip's and the
  stack-key tip's forkchecks follow; the pin moves to the read's jar once it is proven.
- **2026-09-16 16:27 — forkcheck PASS on the gate tip `a36975497b` (499/500, the standing seed) →
  THE FORK PIN = `a36975497b`** (the target surface's two tips + `-modegate off`; the evening's read
  jar). The stack-key tip's forkcheck starts now; the pool at 705/1,000.
- **2026-09-16 17:20 — forkcheck PASS on the stack-key tip `7343c40d84`** (499/500; 20260853's fork
  status flip = the identity-hash residual, its same-jar replay clean + identical) **→ THE FORK PIN
  `7343c40d84`.** Every Build 4 fork tip is proven; the pool at 987/1,000 (the tail games).
- **2026-09-16 17:30 — the target label pool LANDED** (`b4-tgtlab-20260916-145238`: 1,000 games in
  2.6 h ≈ 385 g/h at 24 × 2 with the recipe's surface acting; 986 won / 13 draws / **1 crash of a
  NEW class, `StackOverflowError`** (the prior pools' standing crash is an NPE) — game 500 replayed
  with the crash trace to classify it before the build serves); 69,380 windows, act rate 8.6%,
  27,932 sub rows (27.9/game); **target: 3,251 sub rows (3.3/game), 14,292 answers, mean n 5.3,
  spread ≥ 0.02 on 11.9%** (entity_set 17.8%, mode 14.4%, order 2.0%) — the search sees headroom on
  targets at the entity-set scale; misses `target:unfired` 619 / `target:idx` 39 (no `legal`
  misses: every directed answer applied). Key coverage: 570K ability options all keyed; the pool's
  side table 18,530 entries, 765 keys outside b4 → folded into **`abil-cf2ca6ba-b4s-qwen3` (17,431
  keys, the b4 rows byte-identical)**. The fit chain started 17:32 (six tasks + `surf_target`, 5
  folds; distillation on entity + mode + target).
- **2026-09-16 17:40 — the pool's `StackOverflowError` is NOT a Build 4 class:** the same status
  appears in the 09-07 Build 2 arm `b2-dzla05arm-s1` and in three pre-M12 runs (d3pilot, d6ext,
  d6-run12) — a rare pre-existing engine recursion class (1 / 1,000 here). The one-worker replay of
  game 500 with the crash trace played a different game (53 turns, a draw): a 24-worker pool game
  is not replayable at one worker (the bf16 micro-batch rule), so the trace is not obtainable that
  way; routed with the standing crash class to the upstream worklist. The chain proceeds.
- **2026-09-16 17:40 — the fit chain FAILED at fold 0 (a CUDA gather assert, 16 s in) — TWO BUGS,
  one of them Build 3's:** (1) `surf_method_emb` had `n_methods + 1` rows while the method vocab's
  OOV id is `n_methods` (+1 for the pad) → the first surface method the pinned vocab never saw
  (`playTriggerTargets`) indexed one past the end; fixed (+2 rows, the compat pad) and the
  evaluate's method-name lookup guarded (`<oov>`). (2) **`surface_fit.load_net` set the NET's
  ability table from the ckpt config or the module default while the loaders keyed the options on
  the `--abilities` stem — in Build 3 the day-zero ckpt has no stem, so e1–e3 trained the surface
  heads with the 5,148-row pool table against loaders keyed on the 15,473-row folded table: every
  store-only key (two thirds of the table) trained on the clamped LAST row and served on its real
  vector (a train / serve mismatch on the in-play abilities). Fixed: the net's table = the
  loaders'.** Tonight's refit (six tasks + target) runs on the corrected path; its paired read's
  arms share the build, so the fix is common-mode there; the ladder vs e3 is a separate read. The
  chain relaunched 17:40 (`build4-targets-chain2`; resumable — straight to the fit).
- **2026-09-16 20:10 — THE TARGETS EVENING READ (ADR-0111 addendum 20:10): on − off +0.00 ± 1.19
  (n 593) — nothing broke, the target head serves (1,249 bridged answers, 0 invalid, 0 crashes);
  nogate − off −1.19 ± 1.29 (t −0.9) → within one SE of on → the playability gate RETIRES on the
  pre-registered rule (at the noise floor, sign negative; re-measured by the post-Build-4 read).**
  The build `m12-build4-e1` (pooled target 0.512, the six surfaces at or above e3 on the corrected
  table path) = the served set: seven surfaces + tuck. **The re-warm's recipe DECIDED (user, 20:00):
  option 4 — the offline distillation toward the search** (the policy KL toward the search's
  leaf-value softmax + the value head toward the leaf values, on the pools' searched windows, the
  new representation paths + the top layers unfrozen; read by a held-out KL / top-1 agreement, the
  value head's Spearman vs leaf values, and a 600-game paired read vs the un-re-warmed build) —
  "a stronger sense of whether things are working, and a head start for the shakedown". Data on
  hand: the b2 arms (6 × ~38K searched windows), b3-surflab / surflab2 (~70K each), the pay pools,
  the target pool (69K) — ≈ 600K searched priority windows with per-option leaf values.
- **2026-09-16 21:00 — THE RE-WARM LAUNCHED (`build4-rewarm`, from the worktree; ≈ 1 h):**
  `anvil.training.search_distill` (worktree commit) — the policy KL toward the search's
  leaf-value softmax at the recipe's T 0.025 on the windows whose recorded margin clears the
  recipe's bar 0.10 (**the acting rule's own distribution**: below the bar the search played the
  policy's line, so those windows carry no policy term), the value head toward Σ p v on every
  window (a consistency term — the leaf values are the value head's own estimates one window on,
  Spearman 0.97 before training — weight 0.25); the join = search row → its priority dec in the
  run's obs frames, featurized on the wire path (the serve featurizer, the Build 4 fields
  included); trainable = the new paths + the pointer / value heads + the top 2 trunk layers;
  init = tonight's `m12-build4-e1`; data = the dz / dzla Build 2 arms + the four Build 3 pools +
  the target pool (≈ 460K searched windows; the heuristic-control arms excluded — their margins
  are against the heuristic's line, not ours); 8,000 steps × 64; held-out fold 1/10 by game hash.
  **The smoke's baseline: on acted windows the policy's top-1 agreement with the search is 0.00 by
  construction and its KL ≈ 11 nats — the policy puts ~e⁻¹¹ on the search's pick where the search
  overrides it; the read after = how far that closes.** Output `data/training/m12-build4-rw`;
  then the 600-game paired read vs `m12-build4-e1` (network alone) = the strength read.
- **2026-09-16 21:10 — `b4-representation` MERGED into main (`8949d58`; 315 tests pass):** the
  representation completions (format scalars, the additive stack-entry fields, `cand_ak` +
  `cand_abil_proj`), `TRANSFORM_VERSION` 5, the search-distillation trainer. Every served build
  serves byte-identically until the re-warmed checkpoint (the new paths are zero-init). The
  strength read queued behind the re-warm (`build4-rewarm-read-queue`): `m12-build4-e1` (arm on)
  vs `m12-build4-rw` (arm alt), 300 per seat, network alone, `-modegate off` on both, jar
  `a36975497b`; `build3_surface_read.sh` gained `CKPT_ALT` / the alt arm.
- **2026-09-16 20:30 — the re-warm's first held-out read (step 1,000 of 8,000; 0.7 s/step):** on
  1,843 held-out windows of unseen games, 133 acted (7.2%): **top-1 agreement with the search on
  acted windows 0.045 → 0.970, KL 14.1 → 0.08 nats**; top-1 over all windows 0.366 → 0.391; the
  value head's Spearman vs the leaf values 0.980 → 0.983 (a consistency term). The policy learns
  to reproduce the search's override where the margin is large — the one-ply lookahead the trunk
  can approximate from its own value knowledge (M11's asset, now inside the policy). The strength
  read (queued: e1 vs rw, 600 games) is the arbiter of whether that transfers to outcomes and of
  any cost on the un-acted windows the term never touched.
- **2026-09-16 22:40 — THE FIRST RE-WARM COLLAPSED AT SERVE: alt − on −46.7 ± 2.1 pp (4 up / 275
  down; `b4rw`).** Not a serve bug: on the same held-out windows the re-warmed policy's pass mass is
  0.55 vs 0.09 for e1, it argmaxes pass on 60% of windows (e1 9%), its entropy 0.61 vs 0.17, argmax
  agreement with e1 17% — a PASS-HAPPY policy, while every held-out number the trainer reported
  (acted-window top-1 0.97, KL 0.06) was true. **The design flaw:** the policy term shaped the 7%
  acted windows and nothing anchored the other 93% (the search's best is pass on only 12% of acted
  windows — the pass-happiness is drift, not the target), so the shared pointer heads + top layers
  generalized freely. **The fix = the acting rule's own semantics:** below the bar the rule plays the
  CURRENT policy's line, so the target there is the frozen teacher's distribution — KL(teacher ||
  student) on every un-acted window (`--w-anchor 1.0`, a frozen copy of the init); the eval now
  reports pass mass + entropy so a collapse is visible without a serve. The re-warm relaunched
  (`build4-rewarm2` → `m12-build4-rw2`) with the read queued (`b4rw2`). Standing rule candidate: a
  distillation that touches a subset of windows anchors the rest to the teacher.
- **2026-09-16 23:00 — the anchored re-warm's step-1,000 held-out read (`build4-rewarm2`):**
  acted-window top-1 with the search 0.045 → 0.759 (KL 14.1 → 0.62), top-1 over all windows 0.366
  → 0.445, **pass mass 0.138 → 0.095, entropy 0.15 → 0.32** — the policy takes the search's
  overrides while the anchor holds the rest (train: anchor 0.16 nats, acted KL 0.35 — the two terms
  compete as designed). The read `b4rw2` (e1 vs rw2, 600 games) lands ≈ 01:30 09-17.
- **2026-09-17 00:57 — THE ANCHORED RE-WARM STILL LOSES: alt − on −18.8 ± 2.1 pp (`b4rw2`, 32 up /
  141 down)** with a sane held-out distribution (step 8,000: acted top-1 0.72, pass mass 0.109,
  entropy 0.20, all-window top-1 0.43). The diagnostic on held-out windows: rw2's argmax agrees
  with e1's on 96.4% of un-acted and 57% of acted windows (94.9% overall); zeroing the candidates'
  ability keys changes 0.6% of rw2's picks — **the text path is not a serve mismatch**. A 5%
  argmax change costing 19 pp points at the OTHER HEADS: the re-warm unfroze the top two trunk
  layers with only the priority policy anchored, and the combat, trigger, binary, number,
  mulligan and surface heads read the moved trunk unanchored (and the stack additive changes
  every head's input on non-empty-stack windows). **Launched 01:05 (`build4-rewarm3-queue`):**
  (1) the PRIORITY-ONLY read of rw2 vs e1 (every other head the heuristic's; tags priority +
  mulligan keep) — isolates the re-warmed policy itself; (2) the frozen-trunk re-warm
  (`--unfreeze 0`: the new paths + the pointer / value heads only) → `m12-build4-rw3`; (3) rw3's
  full and priority-only reads. If the policy alone reads ≥ e1 → the fix is a full-head anchor
  (every head matched to the teacher on its own windows) or the frozen trunk; if the policy alone
  is worse → the offline distillation of the search's overrides itself hurts at serve and the
  route is the loop.
- **2026-09-17 01:40 — the priority-only read of rw2: altoff − off −21.4 ± 2.2 pp — the re-warmed
  POLICY ITSELF, with a fivefold veto rate (27.1% vs 5.6%: the executor refusing its picks).
  01:30 — THE ROOT CAUSE, in the trainer's join:** the search row's option indices are contiguous
  over the SEARCHED options (the mana abilities the search skips removed) while the dec's option
  list is the mask with them in, and the row truncates labels to ≈ 25 chars while the dec renders
  120 — the join matched 12.5% of rows (the mana-free windows: a biased early-game slice) and
  both re-warms trained on that slice. Fixed (`align`: in-order label alignment on the shorter
  prefix, the row's contiguous index → the dec's option index): **1,018 / 1,018 rows matched on
  a worker, every option value mapped**; on the full set 11.9% of windows are acted (7.2% on the
  slice). The frozen-trunk diagnostic (rw3) was killed — its data was the same broken join.
  **Relaunched 01:35 (`build4-rewarm4-queue`, unattended, ≈ 07:30):** rw4 (the anchored recipe,
  unfreeze 2) → its full + priority-only reads; rw5 (the trunk frozen) → its full read.
- **2026-09-17 02:39 — rw4 (the corrected join, anchored, top-2 trunk layers unfrozen): alt − on
  −7.3 ± 2.1 pp (55 up / 98 down)** — from −47 / −19 to −7, still negative. Final held-out (9,600
  windows): acted top-1 0.027 → 0.452, KL 10.4 → 1.10, all-window top-1 0.358 → 0.435, pass mass
  0.274 → 0.230, entropy 0.22 → 0.93 (the reads serve greedy, so entropy is a symptom, not a
  cost). **The mechanism, from the served arm's census: vetoes 17.0% vs 4.9%, and the excess is
  `no_shape_fit` — 3,935 vs 797 — the TARGET DECODER's cast plans failing to fit.** The re-warm
  never trained that decoder but moved the two trunk layers it reads, and the distilled policy
  now picks exactly the options that need a plan: on acted windows the search's override is a
  spell (149) or an ability (111) of 311, where the natural line was pass (157) or a land (55).
  On the copies those plans were realized by the same decoder on the unmoved trunk. **Prediction
  for rw5 (the trunk frozen; queued): `no_shape_fit` back near the on arm's 797 / 600 games and a
  read ≥ 0; if the vetoes stay high with the trunk frozen, the pointer heads alone are choosing
  spells the decoder cannot plan, and the decoder must be co-trained (the priority task's own
  cast-plan labels) or the acted target restricted to options whose copy plan was realized as the
  first-fit plan.** The priority-only read `b4rw4p` runs; rw5 follows.
- **2026-09-17 03:17 — rw4's priority-only read: altoff − off −7.35 ± 2.23 (65 up / 108 down;
  vetoes 23.9% vs 5.3%) = the full read's −7.3** → the whole loss sits in the priority policy and
  the cast plans of its picks; the surfaces and the other heads contribute nothing to it. rw5 (the
  trunk frozen) decides between the decoder-on-a-moved-trunk mechanism and the picks themselves.
- **2026-09-17 04:09 — rw5 (the trunk FROZEN): alt − on −9.0 ± 2.0 (48 up / 101 down); vetoes 22.2%
  vs 4.9%, `no_shape_fit` 5,758 vs 787 — MORE than rw4's, on an unchanged trunk and an unchanged
  target decoder → the prediction FAILED: the plans are not degraded; the distilled policy picks
  options the model's own planner cannot plan.** The mechanism, confirmed in the fork: a search copy
  realizes its directed option through `heuristicRealize` (the AI plans the targets / X), so every
  leaf value the search records is the value of the option under the HEURISTIC's plan; the mainline
  realizes the policy's pick through the model's CastPlan (the target decoder's refs), which fits
  only the options that decoder was trained to plan — the heuristic's usual picks. The search's
  overrides are, by construction, options the heuristic did not choose (spells / abilities where the
  natural line was pass / a land), so the decoder has rarely planned them: no_shape_fit → the re-ask
  → second choices. **The finding generalizes beyond the re-warm: the acting rule realizes acted
  options the same heuristic way, so part of the with-lookahead advantage is the heuristic's planning
  of the search's picks — a component the network alone cannot reproduce by learning WHICH option,
  and a named risk for Build 5's kill criterion ("with-lookahead climbs, network-alone flat").**
  Two routes: (a) serve-side — on a plan veto, realize the model's pick through `heuristicRealize`
  instead of re-asking (the model chooses the option, the engine's AI plans its details: the same
  division the payment and mode surfaces settled on; a flag-gated serve change, read as rw4's alt arm
  with the fallback on); (b) the target decoder learns the heuristic's plans for the search's picks
  (record the realized plan on acted windows and copies; co-distill the decoder). (a) is the cheap
  decisive read and is built next; (b) is the training-side completion routed to Build 4's close.
- **2026-09-17 05:10 — the fallback read (`b4rw4f`, jar `d734937c56`): rw4 + the heuristic-plan
  fallback −9.2 ± 2.0 vs the served build; the served build + the fallback −0.2 ± 0.9 (neutral).
  The decisive number: of 4,767 fallback attempts on the rw4 arm, 237 realized — the heuristic's
  own evaluation refuses 95% of the distilled policy's vetoed picks.** So the picks are not merely
  un-plannable by the decoder; they are casts the engine's AI would not make in those states. The
  distilled policy learned "cast instead of pass" from the acted windows and over-generalizes it
  into unplayable casts — and the loss never taught playability: the options that VOIDED on the
  copies (the heuristic could not / would not realize them there; 30% of first-ply copies) were
  excluded from the target rather than pushed to zero, and the acted KL was normalized over the
  valued options only, so mass on un-valued options was invisible. **rw6 (launched next): the
  void options as explicit negatives — a playability term (−log(1 − the policy's mass on void
  options), every window) — and the acted KL's student normalized over every legal option.** The
  serve-side fallback is retired (neutral where it fires); route (b), the decoder co-distilled on
  realized plans, stays routed.
- **2026-09-17 05:20 — `build4-rewarm6-queue` launched (≈ 10:00):** rw6 = rw4's recipe + the void
  term; rw7 = the same, softer (w_kl 0.3, T 0.05); each read against the served build. Note the
  served build's own void mass is already 0.012 on held-out windows — the term is a guard for the
  distilled policy's new states more than a correction of the old one; the expectation is modest.
- **2026-09-17 06:03 — rw6 (the void term): alt − on −8.9 ± 2.1 (49 up / 101 down); vetoes 8.9% vs
  5.1% (halved from rw4's 17%) — the loss unchanged.** The vetoes were a symptom: the distilled
  policy plays worse even when its picks realize. Held-out: acted top-1 0.40, all-window 0.39,
  void mass 0.044 (up from 0.012 — on its new preferences the policy lands on options that void
  in new states). Six builds of option 4, every one negative once the join and the anchor were
  right (−7.3 / −9.0 / −9.2 / −8.9): **the search's overrides do not distill into a stronger
  network-alone policy — the policy generalizes them into casts that are wrong in states the
  search never checked.** rw7 (softer: w_kl 0.3, T 0.05) is the last data point (≈ 08:00); then the
  re-warm closes as a serve candidate with the finding as its deliverable (ADR-0111 addendum
  04:40), route (b) routed, the representation paths to the loop.
- **2026-09-17 07:00 — rw7 (softer: w_kl 0.3, T 0.05, the void term): alt − on −0.7 ± 1.9 (63 up /
  67 down), vetoes at baseline, 21% of the search's overrides taken on held-out windows. THE RE-WARM
  CLOSED as a serve candidate (ADR-0111 addendum 07:00; user): the harm scales with the dose, the
  gentle dose is neutral; no offline re-warm — `m12-build4-e1` is the day-zero build, the paths
  train in the loop; route (b) (the target decoder on realized plans) before the shakedown.**
- **2026-09-17 (session 2) — THE ALLOCATION HEAD SERVED ([ADR-0112](../decisions/ADR-0112-m12-build4-allocation-head-served.md)).**
  The review's four decisions (user: the recommendations): (1) the head's probability enters as
  a dedicated **`anvil.alloc` ask on the value wire** (the rate draw fires before the mainline's
  priority ask, so the "extra output on the priority response" needed the search moved inside
  the controller's ask; the ask costs ≈ 2% of a game's forward calls, mirrors `anvil.value` /
  `anvil.certify`, carries a shape id later); (2) the rule = **p ≥ tau plus a seeded uniform
  floor** (`-searchalloc tau -searchfloor 0.1`; unserved = the uniform rate); (3) the first fit =
  the frozen-trunk logistic folded into the in-model head with a fit record (the pay-gate
  pattern; the loop-native term rides the loop wiring); (4) the order: the head → the post-Build-4
  read → the loop wiring → route (b) → the documentation pass → the shakedown. **The finding:
  the loop does not run the search yet** (`selfplay.py` passes no search flags; `rl.py` has no
  search-row / behavior-logp term; the harness's `forge_args` and the row's `logp` exist) — Build
  4½ pre-work, routed by name. Built: fork `a37bc6a8b4` (`AnvilRun`: the ask after the rate draw,
  the options scanned once and handed to `doSearch`, the peek under an RNG snapshot, `ev: alloc`
  rows on skips, `alloc {p, by, ms}` on searched rows, census `searchAlloc`, header pins
  alloc / floor; off = byte-identical) + Anvil `6d12084` (`alloc_head` on the `[STATE]` read-out,
  base-rate init, the `alloc_` compat prefix; the server serves the tag only with `alloc_fit`;
  `alloc_fit.py fit`; `alloc_smoke_read.py`; ALLOC on the act smoke, the `alloc` arm on the
  surface read; `build4_alloc_chain.sh`). **The fit** (`data/runs/alloc-fit-2`: `b4-tgtlab`'s
  69,380 windows joined 100% on the e1 trunk, 8.7% positives at 0.10): **AUC 0.800 ± 0.012 OOF**
  (0.830 in sample; state alone); tau 0.489 / **0.369** / 0.276 at 80 / 90 / 95% recall → OOF
  recall 0.77 / 0.87 / 0.93 at cost share 0.52 / 0.62 / 0.71 (windows 0.40 / 0.51 / 0.60; × games
  1.91 / 1.60 / 1.42). **The pin: tau 0.369, floor 0.1 → `data/training/m12-build4-e1a/last.pt`**
  (e1 + the head; the policy byte-identical). The wire smoke on the unfitted build: 224 asks, 224
  declined, every window unserved + searched, 7 ms per ask, 0 crashes. Tests 320.
  **The served smoke (4 games, e1a, tau 0.369): head 57% / floor 5.5% / skip 37% of 330 windows
  (searched 63%); acts 34/189 on head windows, 0/18 on floor; the ask 19 ms; 4/4 clean.**
  **LAUNCHED 15:14 through `anvil.runs`: `build4-alloc-chain`** (pid 56516, stall alarm 60 min,
  sinks queue + desk) — forkcheck `run-20260917-build4-alloc` → the post-Build-4 read
  `build3-surface-read-b4post` (on / act / alloc, 1,000 per seat, 24 × 2; gate act − on ≥ +1.5pp,
  alloc − act the neutrality check) → `read.json` / `read-alloc.json` / `alloc-census.txt`;
  ETA ≈ 04:00–05:00 09-18. Next: the read → the fork pin (on PASS) → the loop wiring (Build 4½
  pre-work: search flags on `selfplay.py`, the search-row terms + the behavior logp + the alloc
  BCE in `rl.py`) → route (b) → the documentation pass → the shakedown.
  **THE POST-BUILD-4 READ (22:35 09-17): act − on +2.29pp ± 1.02 (t 2.24, n 1,964) → THE LAUNCH
  CONDITION CLEARED** (on = e1 alone 0.5265 ± 0.0112 raw = the reference within noise; act =
  + the recipe 0.5494; act rate 9.0% over 72,275 searched windows; ×3.5 wall on the searched
  seat). The `alloc` arm runs ≈ 1,070 g/h vs act's ≈ 750 (the head's saving, in flight).
- **2026-09-18 — THE POST-BUILD-4 READ CLOSED ([ADR-0112](../decisions/ADR-0112-m12-build4-allocation-head-served.md)
  addendum 09:30): on 0.5265 / act 0.5494 / alloc 0.5528 (± 0.0112 each, 2,000 games, 0 crashes);
  act − on +2.29 ± 1.02 (t 2.24) → THE LAUNCH CONDITION CLEARED; alloc − on +2.70 ± 1.00;
  alloc − act +0.25 ± 0.61 (t 0.41) at 51.3% of the windows searched → THE HEAD ALLOCATES FREELY.**
  The census over 73,266 candidate windows: head 46% / floor 5.3% / skip 48.7%; acts 16.6% on
  head windows vs 2.6% on floor windows → recall 0.86 (the fit's OOF 0.87 — the offline table
  held exactly, windows 0.51); the search's wall overhead −40% (wall × 2.53 vs 3.54); 477 copy
  calls/game. Served build of record → `m12-build4-e1a`. Banked: the searched arms' 14% mainline
  veto rate vs 4.5% alone (first look at the loop wiring). Next: the loop wiring (Build 4½
  pre-work) → route (b) → the documentation pass → the shakedown (the allocation arm included).
- **2026-09-18 — run hygiene ([ADR-0107](../decisions/ADR-0107-run-launcher-and-checkin.md) addendum):
  the overnight read went unread 8.5 h (the check-in task off since 09-16, no session wait, the
  CLI's login silently expired) → the supervisor now runs its own event-driven `claude -p`
  check-in (failed / stalled / gone / long done), a launch self-test in the coverage line,
  `--watch` roots for chains whose arms write elsewhere, `sweep` for dead supervisors; verified
  end to end (15 s: push + the supervising session messaged + acked). The scheduled task retired.
- **2026-09-18 (session 2) — THE LOOP WIRING ([ADR-0113](../decisions/ADR-0113-m12-loop-wiring.md);
  Build 4½ pre-work).** The review's four facts (an acted window writes two records — the natural
  ask marked realized though never played, the forced re-ask with the pass masked; the row carries
  the pick, its logp, the distribution, the margin, the class; V-trace's clipped ratio scales an
  acted window's PG down by ≈ the policy's own probability of the pick; the store dropped the rows)
  → six decisions (user: the recommendations): MERGE for the acted-window record; the pick-
  distillation CE on acted windows only; the alloc head's BCE on every searched window with tau
  re-derived per cycle (weighted to the population — the floor's windows alone are not unbiased);
  the guards + tripwire on un-acted windows; the recipe + the serving ckpt's tau + a with-lookahead
  mid-run arm; a two-iteration smoke. Built: `search_join.py`, the loader + learner in `rl.py`, the
  store's `search.jsonl`, the driver's `--search-recipe` family, `--jar`, `--arms-lookahead`,
  `--sched-carry`. The join on `b4-tgtlab`: 20,304 rows 100%, 1,511/1,511 acted rows paired.
  **Two pre-existing breaks of the SAMPLED serve path** (unrun since Build 3): the fleet batcher's
  all-or-none noise (every acted pick voided, a third of alloc asks unserved) → one forward per
  noise group + greedy serving of tag tasks without a sampled head; the M10 schedule carry the
  server injects for every M12 build, never reconstructed by a loop launched without `--sched`
  (2.3% of priority windows > 0.2 nats off, 0/4,096 with the carry) → the driver probes the ckpt;
  the wire history's single-entity host (5.9% of windows) → mirrored on `Obs.retHostId`.
  **`loopwire-smoke3` clean:** join 100% (2,690 rows; 376 act + 47 pass merged), tripwire 0, the
  terms at shares 0.046 / 0.020, tau 0.369 → 0.217 → 0.068 at weighted recall 0.90 across the two cycles (the searched share
  stable 0.61 → 0.56), both arms 48/48 with 0 crashes (lookahead veto 12.4% vs 5.4%), 0 server errors. Tests 348.
  Next: route (b) → the documentation pass (4¾) → the shakedown through `selfplay.py`.
- **2026-09-19 — ROUTE (b) RE-SCOPED ([ADR-0114](../decisions/ADR-0114-m12-route-b-rescoped-void-rescue.md); user: the recommendations).**
  The pre-build review found route (b)'s premise false on a network arm: a copy's seats inherit the
  mainline's bridged tags, so the forced option on a copy is a single-option ask to the MODEL realized
  by `CastPlanRealizer` — `heuristicRealize` fires only on the unbridged control arm and behind the off
  veto fallback; on `b4-tgtlab` 88,395 of 90,955 void copies made exactly one forward call (the forced
  ask). The leaf values ARE under the model's plan, the acted window's label is that plan (ADR-0113
  decision 2 already relies on it), and there is no train/serve plan gap to distill across; the
  re-warm's harm stands on the fallback read. ADR-0112's banked 14% "mainline" veto rate = the copies'
  forced asks in the census (622K single-rung asks vs 58K). **The Build 5 risk re-signs: the search's
  ceiling is the decoder's coverage** — 35.8% of first-ply copies void (43.8% of spells, 98%
  `no_shape_fit`), never valued, never actable. Route (b) as written closed; its replacement measured
  first: **the void-rescue instrument** (fork `57337a7e38`, `-searchvoidrescue`: a voided candidate
  gets one more copy on roll 0's seed with the forced option realized by the heuristic's planner on the
  bridged seat; `vr` + `h {kind, v, calls, ms, plan (Obs.planJson), refuse}` on the row, outside the
  acting rule; census `searchRescue`; header pin). Smoke (4 games, the recipe): 117 void / 117
  instrumented, 33 rescued to a leaf, 84 refused (`CantPlayAi`), every plan targeted, +3.9% calls;
  `void_rescue_read.py` reads. **Launched 20:31 through `anvil.runs` (`build4-voidrescue-chain`,
  `data/runs/build4-voidrescue/`): forkcheck `run-20260919-build4-voidrescue` ∥ the arm `b4vr`
  (150 / seat, the recipe without the allocation head + the instrument, 24 × 2) → the read.**
  Pre-registered: the acting extension (the rescued values as candidates, the mainline playing the
  heuristic's plan on acted rescues, the pick-distillation CE extended to the plan factors) is built
  if rescues clear the bar on ≥ 2% of searched windows at ≤ +30% calls; else route (b) closes on the
  number. Also noted (Discord, Kryptic's four-deck run): the cross-deck over-generalization hypothesis
  (one tactic applied to every deck) — a per-deck decision census on our arm stores is the instrument;
  kept in mind for our own reads, not scheduled.
- **2026-09-19 21:16 — THE READ: ROUTE (b) CLOSED ON THE NUMBER ([ADR-0114](../decisions/ADR-0114-m12-route-b-rescoped-void-rescue.md) addendum).**
  `build3-surface-read-b4vr` (300 games, 298 decisive, the arm 0.534 ± 0.029 = the recipe's): the
  void class 14,523 / 49,338 first-ply copies (29.4%; 93.4% `no_shape_fit`, 4.1% `restrictions`;
  87.5% spells) on 60.7% of searched windows; **the heuristic's planner refuses 91.0% of it**
  (`CantPlayAi` 12,574) — 9.6% of void spells / 1.4% of void abilities / 80% of the 61 void lands
  reach a leaf; the rescued leaves read **−0.015 mean vs the best valued candidate** on the same
  roll seed (p90 +0.063; 6.4% ≥ the bar), +0.016 vs the natural; 86.7% of the rescued plans carry
  targets; price +1.5% calls. **A rescue clears the bar on 80 / 10,597 searched windows = 0.8%**
  (76 natural, 4 acted) — below the pre-registered 2% → the acting extension is not built. The
  coverage bound is ≈ 29% of first-ply options by count and ≈ 3% by playability, worth less than
  the valued set on average; the loop's PG on the decoder's own casts is the route; `vr` stays a
  standing census (routed: recorded unconditionally on the next fork commit). **Forkcheck PASS
  21:16 (499/500, 20260969 the standing seed, fidelity 451/48/1) → the fork pin `57337a7e38`.**
  Next: the documentation pass (4¾) → the shakedown through `selfplay.py` (the allocation arm).
- **2026-09-21 — THE PRE-SHAKEDOWN REVIEW ([ADR-0115](../decisions/ADR-0115-m12-shakedown-scoping.md); user).**
  Decisions: the shakedown launches first and the documentation pass (4¾) runs beside it; the 09-19 census
  items land first; drills OFF in the shakedown, the certifier merge during its week for the big run's jar
  (under item 7 the big run's drill-finding is the search; its offline re-search needs the merge). The box
  across reboots: the whole system is LUKS behind a GRUB passphrase (an unattended reboot stops there; a
  power outage is a UPS question), all recent reboots manual → `anvil.runs pause` / `relaunch` +
  `--resume-on-gone` + the heartbeat + headless workers when no display exists (ADR-0107 addendum 09-21);
  the pacman pin (kernel + `linux-cachyos-nvidia-open` + `nvidia-utils` + JDK, hard-dependent; the user's
  edit) with the unpin on the run-close checklist; the Remote Control trial unit at boot. **The fork's
  census bundle `cbe386d2c6`** (`vr` unconditional, `act_vr` on the mainline's forced ask, `copy:true`
  on search-copy census rows; the smoke: 120/120 void candidates keyed, the copies 3× the mainline's
  priority rows) — **forkcheck PASS 11:53 (499/500, the standing seed) → THE FORK PIN**. `selfplay.py
  --wall-hours` (accumulated box time). **The shallow-wide bench cell: 587 g/h peak (24 × 2)**, ≈ 1.7×
  the recipe. **The contention smoke: a foreign job at 88% SM trips the yield, 4/4 games finish, 0
  deadline poisons, per-game wall 2.7×.** The shakedown scoped: four arms (recipe / alloc / shallow /
  deep) at equal box time (30 h each), sequential from e1a on the census jar, the run of record's loop
  settings, no per-arm day-zero read, each closing with the 2,000-game read + the last lookahead arm;
  `scripts/shakedown_chain.sh` ready. Next: the launch (the user's go on WALL_HOURS) → the certifier
  merge + the documentation pass while it runs.
- **2026-09-21 (community watch, noted + routed)** — Kryptic's iter-50 read: the aggregate flat within
  noise since iter 30 (51.1 / 50.6 / 52.5 ± 1.1), the monitor's veto rate / KL / rejected-per-trajectory
  all turning up at iter ≈ 22–30 (a regime our guards halt), the sampled pay head deviating on 95% of
  windows (our evening-4 untrained-head cost), the Red mirror 34% the one hard matrix fact (3.5 SE);
  chrismaghuhn's interference tests (gradient cosine between deck batches the cheapest direct one);
  khaliostr's wasm question — inference yes (the fork H export: ≈ 45M inference params, ≈ 45 MB int8,
  50–150 ms per forward in ORT-web), training no (the games are the bottleneck, not the net; the
  Leela-Zero volunteer-generation shape is the one browser story — and with the experimental
  forge-wasm fork (the user, 09-21) it is on the table for Forge too, decided by the per-tab game rate).
  Survey doc 09-21 section + draft replies. Routed by name: **fork H's export doubles as the wasm
  export** (one ONNX graph, two runtimes) — noted on fork H, no new item.
- **2026-09-21 (evening) — THE SHAKEDOWN PAUSED ON A KNOWN-WRONG HEAD ([ADR-0116](../decisions/ADR-0116-player-target-positions.md); user).**
  Kryptic's finding, confirmed and measured here: the cast-target decoder's player label copied the
  registered seat into a self-first row; on b4post the model targets ITSELF on 46% of player-targeted
  casts from either seat (the heuristic 11%) — a coin flip, since the encoder is perspective-invariant
  and has no seat feature; exposure ≈ 1.1% of casts (the class avoided: the heuristic's 1.9%), the search
  inherits it, and self-picks on spells that cannot target self land in the `no_shape_fit` veto class
  (ADR-0114's coverage bound re-read on the corrected build). Fixed at both ends through one helper
  (`self_first_turn_order_v1`; n-player-correct, byte-identical for 2 — the model can identify
  individual players for any n; multiplayer itself stays routed); the convention pinned in checkpoints;
  the audit a battery row; the whole-path permutation test the standing rule. The target decoder's refit
  on heuristic mirror stores launched 18:33; then the paired read + audit; then the shakedown relaunches
  from the refit build as its day-zero (ADR-0115 amended).
- **2026-09-21 20:37 — THE SHAKEDOWN RELAUNCHED FROM THE REFIT BUILD (ADR-0116 addendum; ADR-0115 amended).**
  The corrected head's read: self-target 37.5% → 15.3% (the heuristic ≈ 21%), refit − served −1.34 ± 1.03
  (noise), `no_shape_fit` unchanged (the coverage bound is not the target bug), the first-divergence read
  (every game parts by turn 2; the per-draw sign test agrees with the paired diff). Served build of record →
  `m12-build4-e1a-tgt`; the chain's step 0 = its own 2,000-game day-zero read; then the four arms at 30 h.
- **2026-09-22 (routed by name): the `nan-guard` branch** (Kryptic's NaN finding: the target term's
  unguarded `ignore_index` mean; fixed + tested on the branch, pushed) **merges into main when the shakedown
  closes** — the running trainer re-imports `model.py` per iteration, and the arms stay on one tree.
- **2026-09-23 — THE CERTIFIER MERGE LANDED beside the shakedown ([ADR-0117](../decisions/ADR-0117-certifier-merge.md)).**
  The recipe arm closed 04:30 at 0.5240 ± 0.0112 (30.6 h, 16 iterations, 7,680 games; +0.55pp over the
  day-zero 0.5185, inside noise); the alloc arm since 04:30. The merge: `AnvilRun -replay <jobs.jsonl>`
  = the certifier's front over SEARCH COPIES (fork `05fea7938d`): the fork point is the window where the
  seat's natural pick is the stored option (a controller pick hook; turn + phase + seat + profiles on
  the coordinate), one copy per (arm, roll) with the option forced and the pay SurfaceDirective answering
  the arm, every copy continuing the mainline's decision (the seat's own chooser under the pre-decision
  RNG, the pick verified), roll 0 the true line, CensusRun's row contract. Three miss classes read off
  the smokes, each a landing (the random bridge has no cast plan → `-bridgeseats 2`; the first window
  holding the option is one the AI declines → the phase, then the natural pick; `canPlaySa` re-rolls →
  trajectory continuation). The native replay: 35 fired / 6 diverged / 19 never_fired on 60 jobs (option
  counts 35/35; 200/200 directed arms `directed_ok`; the never_fired = opponent-turn + in-response
  casts, no fork point by design); the M9 witness pair: CensusRun 22/30 on today's jar vs `-replay`
  4/30 on the phase-less census coordinates (the two runners' play agrees rarely → the M9 evalset
  re-certifies through the witness; new drills mine + certify on AnvilRun's construction); observe rows
  scored off the rows. The Python side on the branch `certifier-merge` (merges with `nan-guard` after
  the shakedown). The forkcheck inside a shakedown pause window (`anvil.runs pause` at the boundary):
  PASS 12:33 (499/500, 20260969 the standing seed; fidelity 451/48/1 = the baseline's). Standing rule: the replay coordinate = the natural pick + turn + phase + profiles, the
  fork point that pick's window continued through the seat's own chooser. Routed: a `-search` front over
  a stored WINDOW; the deletion of `CensusRun -certify` + `PayDirective` at the big run's launch ADR. **Found 13:58: the pause
  truncated the alloc arm's iteration-4 main generation (34/240; the harness honours the STOP too) → a
  57% iteration inside the intact budget; routed: `pause` writes STOP to the loop root only (after the
  shakedown).**
- **2026-09-23 (evening) — THE VALUE HEAD DRIFTS OFF ROLLOUT TRUTH UNDER THE LOOP ([ADR-0118](../decisions/ADR-0118-value-head-drift-under-the-loop.md)).**
  The state-ranking checkpoint-eval path built (`value_pretrain eval`: the frozen 1,197-row holdout scored
  by any checkpoint's value head, CPU, ≈ 25 s; reproduces the Build 1 records 0.3921 / 0.374). The read:
  day-zero 0.374 → recipe iter 0 / 4 / 9 / 15 = 0.321 / 0.275 / 0.302 / **0.256**; alloc iter 0 / 4 / 8 =
  0.333 / 0.275 / **0.256** (boot SE ≈ 0.027) — ≈ four SE, from the first cycle, in both arms, while
  network-alone strength stayed flat and the lookahead gap drifted up (+0.3 → +3.3pp, ± 2.5). The
  mechanism: the head trains on V-trace outcome targets at weight 0.5 with no critic and no anchor to
  the rollout composites it was fit on, and it is the search's leaf. A third shape beside the Build 5
  kill and tripline — the landmine the shakedown exists to catch. Decisions (user): the arms run to
  their verdict; the Spearman becomes a per-iteration battery row + guard; the settings pass opens with
  a value-anchor arm (a replay term on the Build 1 banks; bar: within one SE of 0.374 across the pass);
  the eval merged into main (`8099b8d`). Also recorded: the alloc head's admission 51% → 66% by iteration
  8 (tau 0.369 → ≈ 0.02 under the trained head; 34 vs 27–29 copy calls per searched window; per-game
  wall −14%). Next: the documentation pass (4¾).
