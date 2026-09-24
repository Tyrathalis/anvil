# M12 plan — SEARCH AS THE BEHAVIOR POLICY, built through to one big run (RECHARTERED 2026-09-06; SCOPED 2026-09-06 session 3; BUILD 0 OPEN session 4)

**Doc status:** living · the open milestone plan — charter, build order, forks, kill conditions (the record: m12-running-record.md)

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

The session-by-session record lives in **[m12-running-record.md](m12-running-record.md)** (split out
2026-09-23; append there, newest last).
