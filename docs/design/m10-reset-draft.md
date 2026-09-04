# M10 reset — ADOPTED (user-adjudicated 2026-09-02/03, [ADR-0094](../decisions/ADR-0094-m10-reset.md))

Session: the probe6 adjudication ([ADR-0093](../decisions/ADR-0093-m10-probe6-read.md)
addendum). The user adjudicated probe6 NO-FUND / no KILL and asked for a
step back before the next probe: are there underlying issues in the
strategy, and is there a more canonical version of the plan? This
document is that step back. It restates the M10 loop as a planner
hierarchy, moves execution to the regime the ceiling was measured in,
makes the certifier the loop's signal source, inverts the probe reads,
and lists what retires. Six forks with drafted leans; the learned-
fidelity follower is recorded by name as the deferred alternative.
**Fork 1 ADJUDICATED 2026-09-02 (user): binding execution, all three
sub-pins. Fork 2 ADJUDICATED 2026-09-02 (user): reward-trained planner
with the mint anchor, all five sub-pins. Fork 3 ADJUDICATED 2026-09-03
(user): INLINE certification in the generation workers (revised from the
drafted daemon), the era-zero anchor rule, uniform sampling for probe7,
the pivotal-moment head as the named extension. Fork 4 ADJUDICATED
2026-09-03 (user): stratified paired strength as the primary read with a
DAY-ZERO read and a halt-for-adjudication rule; headroom shrinkage
demoted to promotion-only. Fork 5 ADJUDICATED 2026-09-03 (user): the
budget STAGED around the day-zero read; probe6 iter-5 = the day-zero
ckpt and probe7's init. Fork 6 ADJUDICATED 2026-09-03 (user): DEFERRED
by name to the probe7 read.** All six forks adjudicated; this document
is the statement of record ADR-0094 points at.

Adjudication principle, stated by the user at Fork 1 and carried into
the remaining forks: **prefer the simpler, more elegant architecture that
lets the model act correctly and coherently, even when it costs more
data and training time.**

## A. The facts the step back starts from

1. **The checkpoint of record is `d6-run11/iter-019`, promoted
   2026-08-03.** M5, M6, M7, M8, M9 and the six M10 probes have all
   closed as ties, no-promotion, or competency-without-strength. A month
   of loop and instrument building has moved the strength number by
   zero. Each milestone answered a real question; none moved the prize.
2. **The proxies have repeatedly measured the wrong thing**: presence
   for content (ADR-0084/0087), lumped serve counters for hold drift
   (ADR-0091, retracted), and — found at the probe6 adjudication —
   natural-line inflation for following and utilization.
3. **The probe6 label-shaped content probe** (`scripts/sched_content_probe.py`;
   the certified arm fed at the 496 windows the follow term trains on,
   the natural line fed at 539 windows it never trains on, slots 0 and
   1 swapped = a legal-candidate content change):

   | ckpt | certified: follow fed / closed | swap-flip | natural: follow fed / closed | swap-flip |
   |---|---|---|---|---|
   | init | 9.7% / 9.1% | 0.0% | 67.0% / 67.9% | 0.0% |
   | iter-2 | 12.3% / 10.1% | 2.5% | 69.9% / 68.5% | 2.9% |
   | iter-5 | 19.0% / 14.1% | 2.8% | 65.3% / 66.4% | 2.9% |

   On natural windows the schedule adds nothing (fed = closed within
   noise); the 32–52% live follow rate is the policy playing its own
   line. On the training windows themselves, schedule-conditioned
   following is ~5pp and half the follow term's effect is behavior
   cloning of certified first casts. Content sensitivity is ~3% on
   label-shaped inputs and ~0.6% on the pinned day-zero population
   (86% six-slot, 36% one card repeated six times) — a fair miss of the
   0.02 bar on either population, not an instrument artifact.
4. **Policy gradient never reaches the emitter.** The only learner use
   of the schedule logits outside the mint term is the grad-free live-CE
   telemetry (`rl.py` sched aux block). The emitter is a supervised
   planner distilling a frozen 08-28/29 mint; the live-gap ratio
   (`sched_live_ce / seedlab_raw_step`) read 3.3 / 3.1 / 3.5 / 3.8 /
   4.9 / 5.7 across probe6 — above the ADR-0088 3× tell throughout and
   climbing. "Drifting apart" and "staled mint" are one fact.
5. **The regime mismatch.** The funded ceiling (+13.5pp/game, +14.1pp on
   v<0.45, [ADR-0078](../decisions/ADR-0078-m10-ceiling-measurement.md))
   was measured with the engine-side `-forceschedule` executor: the arm
   was played as written. The live surface is advisory (slot tokens
   perturb attention; the cast head may deviate silently). Six probes
   have been learning binding execution through attention tokens and a
   496-window batch — the hard road to something the serve path does
   for free. Purposeful passing is the advisory design's worst case:
   following a hold means learning the absence of an action.

## B. The four underlying issues

1. **A signal-density diagnosis answered with small fixed batches.**
   ADR-0049 found signal density is the binding constraint; the
   responses since have been 170, 543, 2,157 and 496 windows at frac
   0.05 under a memorize guard, and a standing rule (ADR-0087) already
   says such a batch cannot carry a channel. The canonical answer is
   search distillation at scale: the search produces dense on-policy
   targets every iteration and the network distills them. Every piece
   exists here (forkable seeded engine, rollout certifier, forced
   executor, Grindstone's economy); what is missing is running the
   certifier continuously as a background labeler with era-weighted
   labels instead of as an offline mint at per-era cadence.
2. **Surfaces before couplings, and the accretion that follows.** The
   probe6 recipe carries eight loss terms (PG, value, entropy, §6c
   penalty, sched E/R, seedlab, follow, paylab) and thirteen guards,
   plus instruments whose floors must be banked pre-probe. Five of six
   probes ended on a self-inflicted layer. Two half-finished couplings
   sit side by side: the payment head has stayed PG-masked through all
   of M10 (its unmask conditions never met), and the schedule is
   advisory.
3. **Two action abstractions deciding the same thing.** The window-level
   cast head and the turn-level schedule both choose casts; everything
   hard about M10 has been arbitrating between them.
4. **Inverted reads.** Probes read competency proxies and defer strength
   to a 2,000-game closeout; 480 games/iteration cannot see strength,
   but the ceiling's own stratified paired instrument can.

## C. The canonical shape — the hierarchy statement

**Turn planner.** One learned component whose action is the turn's
schedule: an ordered list of ≤6 casts plus the implicit hold-set
(m10-build-spec §1 verbatim), decoded at the first own MAIN1 window and
re-decoded at the four revision triggers. The action carries a
log-probability (the autoregressive slot decode under the ADR-0090 stop
rule) and is trained by reward AND by distillation from certified
labels. Its degrees of freedom are exactly the milestone's goal:
ordering, and purposeful passing (a hold IS a decision).

**Window executor-reactor.** The existing cast/combat/target/trigger
policy, which now owns everything the planner does not: land drops
(the executor's land-first convention, as in the mint), off-plan
windows, combat, targets, triggers, off-turn windows, payments (still
masked), and the revision decision through the four triggers.

**Binding execution.** At an own priority window where no land play
remains, if the NEXT slot's (e, sa) is a legal candidate, it is played
without consulting the cast head. The forced answer carries no cast-head
log-prob and drops out of the cast PG (the auto-pay convention). A NEXT
slot that is not a legal candidate at a post-land window is trigger 1
(the slot failed) — a revision, not a silent deviation. A pure-hold
schedule is binding on spells for the turn (abilities and lands stay the
executor's). Deviation becomes structured (a revision, telemetry
first-class) instead of silent.

**What this removes by construction:** the consumer problem, the follow
term, the content-flip / argmax-flip / reliance instruments as gates,
the utilization floor, the follow rate. What remains to learn is
planning — the emitter — and the read becomes the one already pinned:
strength on the behind stratum.

## D. Forks (drafted leans in bold)

### Fork 1 — execution coupling

**Lean: binding execution at serve (§C).** Alternative, recorded by name
(§F.1): keep the advisory surface and learn fidelity with a dense
own-plan follow term. Sub-pins for the lean:
- Post-land binding only (the follow-window retiming of ADR-0092
  carried over: 133/232 certified windows had a land drop before the
  first spell; forcing seq[0] at the emission window would skip it).
- Hold is binding on spells. Reason: purposeful passing must be a
  reward-visible planner decision; an "abstain to the executor" class
  would be a reward-neutral degenerate the planner could hide in. The
  day-zero planner distills the natural line (full-support labels), so
  binding hold at day zero ≈ natural play; the veto watches first-window
  pure-hold > 25% absolute.
- Forced-cast vetoes (the engine rejects the forced play) are trigger 1
  and attributed to the planner (§6c's veto penalty applies to the
  planner's action at that window, not to the cast head).

**ADJUDICATED (user, 2026-09-02): binding execution with all three
sub-pins, on the principle above.** The tradeoff as discussed, recorded
so it does not have to be re-derived:

- The objection to binding is "no plan survives contact with the enemy."
  But the revision mechanism is already built and orthogonal to this
  fork: revise-on-trigger at the four engine-detectable events (slot
  vetoed, any opponent action resolved during our turn, end of turn,
  exhausted), with unprovoked revision structurally impossible (user pin
  2026-08-27). Advisory coupling adds a SECOND channel on top — silent
  deviation by the cast head between triggers — and the fork is whether
  that channel earns its keep. It does not: it lets a different component
  absorb fragility, so the planner never pays for it and never learns
  robustness.
- Binding is cheaper here than it sounds because of the plan's scope:
  own-turn casts only (off-turn windows carry no schedule; hold-up is
  the hold-set's job). Own-turn interaction is almost entirely reactive
  — counters and removal in response to a cast — and arrives as trigger
  1 or trigger 2, both wire-visible.
- What binding buys: fragility becomes reward-visible. A plan that dies
  at the first counterspell costs a turn, and a reward-trained planner
  learns plans that survive (bait first, hold mana, sequence around the
  likely response). "Put the implication of interaction into the plan"
  is what this produces, learned rather than designed; an explicit
  contingency language is a later extension of the planner's action.
- What binding costs, both promoted to pre-flight items: (1) **trigger-
  detector misses** — trigger 2 is an honest approximation (rolling
  wire-history non-self signature); under binding a missed interaction
  plays a stale plan until the next trigger. Illegality self-corrects
  (the NEXT slot is legality-checked at every own window; failure is a
  revision); the residual is a slot still legal but now wrong — the
  missed-trigger residual becomes a load-bearing read (Fork 4).
  (2) **Revision windows are the least-supervised decodes** — the mint
  labels the MAIN1 emission window; a revision decodes from a partially
  executed state and is trained only by reward. Binding makes revisions
  matter more; labeling post-interaction states is a named certifier
  extension (Fork 3), a cost item not a design problem.

### Fork 2 — planner training

**Lean: PG on the schedule action with the mint CE as the anchor.**
- The emission (and each revision) is an action at its window: the mu
  row records the sampled slots and their log-probs (`sched.lp`);
  the loader re-scores the recorded slots teacher-forced through the
  head at the current parameters for the V-trace ratio; advantages are
  the trajectory's at that step (the critic unchanged).
- Anchor: the mint term at frac 0.05 with the ADR-0088 mechanics
  verbatim (lab-k, warmup, carry-w, memorize guard), on the era-weighted
  label pool of Fork 3. This is the ADR-0085 standing rule's "grounded
  anchor of comparable mass", by construction.
- Why the ADR-0085 fixed point does not recur: that term was a decode
  aux on its own emissions, where empty was the min-CE hedge and cost
  nothing. Under binding execution an empty schedule is a real hold,
  reward-visible; under PG the planner learns whether plans help. The
  degeneracy veto's first-window axes stay armed.
- Keep: E/R aux (cheap, measured, funded at ADR-0079). Retire: the
  follow term (Fork 1 makes it moot), the v1 plan machinery (already
  off), the contrastive term (never built).
- Planner KL guard: a KL between generating and current planner on
  emission rows, the cast head's `guard_kl` twin, pinned at pre-flight.
- Alternative (recorded): supervised-only planner + re-mint cadence
  (the probe6 loop with binding execution). Cheaper, but the planner
  then never learns from outcomes and the goal is not addressed.

**ADJUDICATED (user, 2026-09-02): PG on the schedule action with the
mint CE as the anchor, on density grounds** — "we've had a lot of
problems with weak signal, so we want to take easy wins on that where we
can." A planner acts ~once per turn (~7k actions per 480-game iteration
vs ~200k cast decisions); the certifier is the high-quality sparse
signal, reward the dense cheap one, and PG costs no extra data. Sub-pins
adopted as drafted:
1. **Revisions are actions too** — every trigger decode gets PG; reward-
   only in probe7 (no labels until the Fork 3 revision-window extension).
2. **Planner KL guard** (mu vs current on emission rows) at the cast
   head's 0.06 to start; planner entropy is a read, not a bonus — a floor
   only if it collapses (the M2 ADR-0017 failure mode).
3. **Anchor mass fixed** at frac 0.05 with carry-w; staleness is Fork 3's
   era weighting, not an annealed anchor (one knob per job).
4. **E/R aux heads stay** (passive, ADR-0079-funded; retiring them is a
   separate experiment).
5. **Learning rates unchanged** (head 1e-3, trunk 1e-5).

Expectation pre-registered: six iterations of PG on ~7k actions each
will not move the planner far past its labels — probe7 mostly measures
binding execution of a distilled planner (a quarter of whose labels are
certified improvements); the reward-trained contribution is a longer-
horizon claim the promotion-scale run reads. The budget clause holds
regardless.

### Fork 3 — the certifier as the loop's signal source

**Drafted lean (superseded at adjudication): an asynchronous background
labeler with era-weighted labels** — a daemon watching the driver's
accepted-iteration marker, certifying windows from the newest store on
the generating ckpt under the ADR-0088/0089 witnessed-parity discipline,
appending to an era-stamped pool with recency weights. Alternative: per-
era re-mint only (the current cadence). Kept here as the record of what
was on the table.

**ADJUDICATED (user, 2026-09-03): INLINE certification — the generation
worker certifies a sampled fraction of live MAIN1 windows as the game
runs, and the label rides in the trajectory store.** The user's question
("why not just insert labelling into the engine as it runs each game?")
was the better design; the walk-through that adopted it:

- **The label rule under binding execution.** On scheduled windows the
  realized casts are the planner's own emission, so "the natural line"
  is no longer an independent witness and a label of "what was cast"
  would be the ADR-0085 self-target in a new coat. Rule: **a window gets
  a label only if the certifier rolled it out, and the label is the
  search-adjudicated best of {the planner's own plan (arm 0), the
  enumerated arms}**, θ as the tie-break toward the own plan. "Natural"
  = "the search confirmed the plan" — the engine adjudicating, not the
  planner grading itself. Unrolled windows never get a label. The 08-30
  mint satisfies this already (every label from a rolled-out window;
  pre-binding) and is era zero.
- **Correction to the draft's sizing**: under full support every rolled-
  out window yields a label, not only certified ones — ~60 labels per
  45-min iteration at 8 lanes (44 s/window), ~90 at 12; a few hundred
  over probe7, a mint-sized pool over a 30-iteration promotion run.
- **What inline removes.** (1) The replay path and its parity witness
  for fresh labels — the ADR-0089 defect class existed only because the
  mint reproduced states after the fact; certifying from the live state
  has nothing to reproduce (batch re-mint machinery kept for boundary
  events, off the critical path). (2) The era pool and its weighting —
  labels are per-window store annotations (the `cand_paymark` idiom),
  the store is the era stamp, and the driver's four-iteration replay
  window at its recency weight is the weighting. (3) The fixed-batch
  subsystem for this term (lab-k, warmup, carry-w, memorize guard):
  labels that turn over with the stores are not a fixed batch. The mint
  term becomes **decode CE on search-labeled emission rows inside the
  main RL pass** — the retired ADR-0086 pipeline (today's live-CE
  telemetry) with the target swapped from the planner's own emission to
  the search's verdict. Grounded AND dense AND on-distribution (the
  ADR-0088 requirement) by construction.
- **What it costs: certification on the generation critical path.**
  ~44 s lane time per window against ~25 min for 480 games at 8
  workers: sampling 2% of ~4,000 eligible windows adds ~20% for ~80
  labels; 5% adds ~50% for ~200. The user's pin: fine, as long as the
  rate is a clean knob with an off switch. **Rate 2% for probe7**,
  raised at the promotion run where label volume outranks wall clock.
- **Idle JVM time** (the daemon's advantage: JVMs idle through the
  ~40% training phase) is a property of the synchronous iteration, not
  of the problem — the V-trace loop was chosen for the asynchronous
  actor-learner shape and the overlap-campaign plumbing is its first
  step; once generation overlaps training the advantage disappears, and
  inline is the design that stays correct in both regimes.
- **Fixed era windows are fine except at the start**: each labeled row is
  visited ~4× over its replay-window life (gentler than the fixed-batch
  regime); the trap is the first iterations, when the in-store pool is a
  few hundred labels and the 2,157-label mint would age out. **Era-zero
  anchor rule**: the 08-30 mint stays an explicit anchor batch under the
  existing fixed-batch mechanics until the in-store labeled pool is
  larger than it, then retires. One comparison, no half-life.
- **Smart sampling is strictly easier inline**: the decision to certify
  is made at the window with the server's live signals in hand (critic
  value, cast-head entropy, planner top-plan margin) at zero cost; a
  daemon sees only what was recorded. **The sampling hook takes a
  weight function; uniform for probe7** so fresh labels stay comparable
  with era zero.
- **Named extension — the pivotal-moment head.** Every certified window
  produces the spread of scored Δwr across its arms: a direct, engine-
  adjudicated measure of how much the choice mattered. A head trained
  on it learns decision leverage from search results (what separates it
  from the M6 rank critic / M8 critic-ordered curation, which ranked by
  value change and tied). Three uses of one head: certification yield
  (certify ∝ predicted pivotality with a uniform floor so the head keeps
  learning about "dull" windows; today's 19–28% certified rate is mostly
  "nothing beat natural"), drill extraction (Grindstone's selection
  problem with a grounded signal), and **live search at deployment**
  (inline certification IS live search with the result not played; at
  deployment it is played and the head decides where to spend rollouts
  — the same code path serves training labels and test-time search; the
  Mentor product's natural feature). Not in probe7's budget; **the arm
  spread is recorded on the row from the first inline certification**
  so the label costs nothing later. Zero-cost first version needing no
  head: weight sampling by the critic's value band (the ceiling's
  v<0.45 finding) — also held out of probe7 for population
  comparability.
- **Verification done at the adjudication (2026-09-03):**
  (1) *Live forking exists.* AnvilRun's rollout-label mode (M2 D4) forks
  the live game at `-points` sampled quiescent MAIN1 windows per game
  and completes `-rollout k` copies under the bridge; the schedule-
  forcing executor (`ScheduleDirective`) is armed per fork copy by the
  sched-rollout mode. **The gap: the directive reads its arms from a
  launch-time TSV; inline needs the arm set decided at the window** — a
  per-fork directive over the wire, the `-forcechoice` ChoiceDirective
  idiom (one Java session at ADR-0079/M11). Arm enumeration stays
  Python-side from the wire options at the window; the bridge answers
  "these arms" or "none" (a weighted sampler = answering "none" more
  often with `-points` oversampled). Fork completions serve through the
  existing `-forkobs` path.
  (2) *Heap.* Generation workers run 2g (`orchestrator.py` default);
  the mint's lanes needed 4g (the AiCache mainline-accumulation OOM
  class). Forking workers go to 4g: 8 × 4g = 32 GB against 62 GB total
  / 57 GB available on the box (32 cores) — fits with the server and
  learner resident.

### Fork 4 — the reads (inverted)

**Drafted lean: the primary probe read is a stratified paired strength
read** (kept below as adopted, with the pins the walk-through added).

**ADJUDICATED (user, 2026-09-03), all pins as drafted in the walk-through:**

- **Two candidate primary reads were on the table.** (a) *Headroom
  shrinkage* — the ADR-0084-pinned competency read: re-run the
  certification sweep at the candidate ckpt on 600 fresh-seed turns and
  report the certified arm's mean gain over the candidate's own play on
  v<0.45 against the banked +14.1pp. Pinned, machinery exists, but it
  measures how much better search could still do (shrinks also when the
  candidate got worse in ways search cannot fix), never says the
  candidate beat anything, and costs the full sweep (~7.3 h at 8 lanes,
  ~81,600 completions). (b) *Stratified paired strength* — from each
  behind-state window, K completions with the candidate at the seat and
  K with the baseline, paired rollout seeds (the M7 forced-branch paired-
  rollout machinery with two POLICIES as the branches, served through the
  M4 D2.4 dual-policy fork path), everything else identical; the per-
  window win-rate difference averaged over the stratum is a direct
  strength claim where the ceiling said the value lives. ~9,600
  completions at 600 windows × K=8 ≈ an hour. **(b) is PRIMARY; (a) is
  an exploratory secondary at the promotion run only.**
- **A fixed population**: generated ONCE at the baseline ckpt with fresh
  seeds; own-turn MAIN1 windows selected by the eval critic at v<0.45
  (600); reused for every candidate from probe7 through promotion so the
  series is comparable. v≥0.45 windows recorded for context, never
  gating (the curve is context — ADR-0084 rule 5 verbatim).
- **The baseline is the same init ckpt under ADVISORY serve** — the
  policy as it plays today — so the comparison isolates the reset.
- **The bar**: the ADR-0078 threshold scale (the ~+2.2pp-per-game
  equivalent) on the v<0.45 stratum with the interval excluding zero;
  exact number pinned at pre-flight with the other numerics.
- **The DAY-ZERO read (the fork's addition).** Under binding execution
  probe7's iteration-0 ckpt already plays the distilled planner's plans
  as written, so the paired read BEFORE any training measures binding
  execution of the distilled 08-30 mint alone, and the terminal read
  measures what six iterations added — the claim decomposed into its
  two parts for an hour. **Rule: a day-zero read below MINUS the bar is
  a HALT for adjudication (human), not an auto-KILL** — six iterations
  of ~7k planner actions will not repair a distillation that forces
  clearly-worse plans, and the negative is a distillation-quality
  finding that may route to more labels rather than to closing the
  fork.
- **Secondary reads (exploratory, never gating)**: planner axes (first-
  window hold and length, revision rate by trigger, forced-cast rate,
  forced-veto rate); planner KL and entropy; mint CE split by label
  class (certified vs search-confirmed — the split the probe6 read
  lacked); the missed-trigger residual (Fork 1); headroom shrinkage at
  promotion only.
- **KILL (auto, from the 4th accepted iteration)**: the degeneracy
  veto's first-window axes (pure-hold > 25% or mean length < 1.0)
  sustained two iterations, OR forced-veto rate above a pre-flight bar
  sustained two iterations. The planner KL guard is a guard, not a kill.
- **Retired as gates**: content_flip / argmax_flip / reliance_l1, the
  utilization floor, follow rate and follow CE; and, falling out of
  Forks 1 and 3, the label-shaped content probe (moot when the policy no
  longer reads the schedule) and the live-gap staleness ratio (moot when
  labels are fresh by construction) — both stay as scripts, neither is a
  read. Payment's reads untouched.

### Fork 5 — probe shape and budget

**Lean: m10-probe7 = the reset recipe at D4 shape (6×480), on a fixed
budget: two build sessions + one probe.** Pre-registered outcomes:
- FUND: the stratified read clears its bar with the veto clean.
- KILL (auto, from the 4th accepted iteration): first-window pure-hold
  > 25% or mean length < 1.0 sustained two iterations (the veto,
  absolute), OR forced-veto rate above a pre-flight bar sustained two
  iterations.
- Day-zero read below minus the bar = HALT for adjudication (Fork 4).
- Nothing on the stratum with a clean loop = **a legitimate negative
  answer to M10 at the hierarchy level**; the milestone may close on it
  with the assets carried. The reset must not become another month of
  infrastructure.

**ADJUDICATED (user, 2026-09-03): the same envelope, STAGED around the
day-zero read.** The consideration: the day-zero read needs only the
binding serve rule and the paired-read script — nothing on the learner
(no schedule log-prob in the loader, no planner PG, no inline
certifier), i.e. about a third of the build — and it is the first
strength number the milestone would have produced in a month. So:

1. **Session one**: the binding serve rule (Fork 1 sub-pins), the paired
   read script, the fixed v<0.45 population generated once at the
   baseline, and the **day-zero read** — one session to the first
   strength number.
2. **The mid-point decision rule** (Fork 4's, applied before the learner
   is built): below minus the bar ⇒ HALT for adjudication — the cheap
   response to a bad distillation is better labels, not a training
   loop; flat or positive ⇒ proceed. A FLAT day-zero read is NOT a
   negative: it says the distilled mint executed as written is worth
   about nothing (consistent with a quarter of its labels being
   improvements) and leaves training as the open question; only a
   clearly negative read changes the plan.
3. **Session two**: the learner side — the loader's schedule action,
   planner PG + the KL twin, the inline certifier (Java directive +
   Python enumeration/scoring, workers at 4g) — then the smoke and the
   pre-flight pins.
4. **The probe** (6×480) answers the narrower question — what training
   adds on top of binding + distillation — with the day-zero number as
   its own baseline.

**The day-zero ckpt and probe7's init = probe6 iter-5**
(`m10-probe6/iter-005/train/last.pt`). The comparison is one ckpt
played two ways (binding vs advisory), so the planner must already be
distilled; the graft init's emitter is zero-init (forcing garbage
schedules tests nothing). probe6 iter-5's emitter reached mint CE 1.24
on the full-support labels, it is an accepted ckpt with full telemetry,
and playing it under both serve modes isolates execution mode exactly.
Recorded caveat: its cast head carries six iterations of movement
including the follow term's cloning (harmless for the comparison). The
cleaner alternative — a fresh head-only distillation of the graft — is
a small script spent before knowing the answer is worth having; named,
not built.

Not covered by the staging: the day-zero read exercises nothing on the
learner, so session two's build is validated by the smoke, not by the
read.

### Fork 6 — payment under the same principle (named, not decided)

The schedule-consistent payment scorer (ADR-0078's engine asset) could
execute payments for scheduled casts the way binding execution executes
the casts, retiring the PG-masked pay path or re-basing its unmask
conditions. **Lean: defer until probe7 reads; record here so it is not
lost.** The ADR-0075 fact (+2.96pp as a supervised conditional
competency) is the ceiling this fork would go after.

**ADJUDICATED (user, 2026-09-03): DEFERRED by name to the probe7 read.**
Three reasons: probe7's budget is spoken for; the day-zero read will say
whether binding execution of schedules is worth anything before the same
idea is extended to payments; and the payment scorer exists only inside
the forced-schedule directive, so it becomes reachable on the live path
exactly when the per-fork directive (Fork 3) lands in session two. The
trigger for the decision is the probe7 read, with the pay leg's own
telemetry from a binding-era run in hand. Nothing lost: ceiling
(ADR-0075 +2.96pp), executor (the schedule-consistent payment scorer),
and trigger are all named here.

## E. Retirement list

| item | disposition |
|---|---|
| follow term (`--follow-frac`, `follow_pass`, `guard_follow_share`) | RETIRE (Fork 1) — code kept for §F.1 |
| live-gap staleness ratio (`sched_live_ce / seedlab_raw_step`); label-shaped content probe | RETIRE as reads (Forks 3/4: labels fresh by construction; the policy no longer reads the schedule) — scripts kept |
| content_flip / argmax_flip / reliance_l1 gates; utilization floor; follow rate/CE reads | RETIRE as gates; `sched_reliance.py` stays telemetry |
| v1 plan machinery (`--plan`, plan reliance, `guard_plan_share`) | already off; strip from the recipe |
| seedlab term | KEEP as the mint anchor on the era-weighted pool |
| E/R aux, `guard_sched_share/spike` | KEEP |
| paylab + pay mask + PG-unmask conditions | KEEP unchanged; Fork 6 names the alternative |
| KL guard (cast head) | KEEP; add the planner twin |
| degeneracy veto | KEEP, first-window axes, absolute |
| §6c veto penalty | KEEP; forced-cast vetoes attributed to the planner |
| memorize / share guards on fixed batches | KEEP (one fixed batch remains) |
| per-era re-mint + replay parity witness | batch fallback for boundary events only (Fork 3: fresh labels are minted live, nothing to reproduce) |
| labbatch mechanics for the mint term (lab-k, warmup, carry-w, memorize guard) | RETIRE for in-store labels (they turn over with the stores); KEEP only for the era-zero anchor batch until it retires |

## F. Deferred alternatives, recorded by name

1. **Learned fidelity (the advisory design's follower).** A dense
   own-plan follow term at live post-land windows: feed the policy's
   own carried schedule, CE on the priority pointer toward the NEXT
   slot when it is a candidate; gradient-stopped at the plan (the plan
   is a sampled discrete object, so the emitter is not in the graph);
   frac 0.05, ADR-0088 mechanics; reads = live follow rate and
   `sched_live_ce` reversing, swap-flip on certified windows well past
   3%. This is probe1's mechanism minus the self-reference and is the
   test of whether soft conditioning can reach high fidelity at all.
   Revisit if binding execution turns out to need a soft escape hatch
   between triggers.
2. **Contrastive two-arm follow term** (ADR-0093 routing) — moot under
   binding execution; kept by name.
3. **Label-shaped content read** — built (`scripts/sched_content_probe.py`);
   telemetry only under the reset.

## G. Build order and hazards

Build order (STAGED per Fork 5 — items 1, 5 and the day-zero read are
session one; the mid-point decision rule sits between; 2–4, 6, 7 are
session two): (1) serve rule in `sched_serve.py` + the server answer path
(forced answers flagged in the mu row, no cast logp; emission/revision
rows gain `sched.lp`); (2) loader: the schedule as a scored action at
its window; (3) learner: planner PG term + planner KL guard; follow term
off; (4) inline certifier: the per-fork schedule directive over the wire
(Java, the ChoiceDirective idiom), Python-side arm enumeration + scoring
at the fork point (schedule_sweep/sched_mint code reused), the label +
arm spread written on the row, workers at 4g, the rate knob (`-points`
× the bridge's accept rate) with an off switch, the era-zero anchor rule
in the loader, the mint term moved into the RL pass on labeled rows; (5) the stratified paired read as a driver-callable
script (fixed baseline-generated v<0.45 population; two-policy paired
completions on the M7/M4 fork machinery; day-zero + terminal invocations
wired into the driver with the halt rule); (6) 4-game smoke: forced execution parity with the mint
executor's semantics (land-first, post-land binding), carry tripwire 0,
forced rows carry no logp; (7) day-zero banks + pre-flight pins + launch.

Hazards to pre-register:
- The cold-start poison wave (8 workers × 1 first request) now lands on
  a binding surface — per-iteration warm-up forward before generation.
- Forced casts bypass the cast head's veto penalty: attribution to the
  planner must be in place before launch or vetoes become free again.
- The certifier and generation contend for the box; the certifier
  yields. Anchor timelines on artifacts, not on the plan.
- Suite: `seedlabels`, `sched_serve`, loader parity, and the forced-row
  PG exclusion each need a regression test from the real probe6 rows.

## H. Build status (session one, 2026-09-03)

Items 1, 5 and 6 of §G are BUILT and smoked; the day-zero read is
staged, not launched (user pin: reboot first). Record of what the code
said differently from the draft, all resolved with the user this session:

- **No fork completion had ever carried a schedule.** `server.answer`
  gated the SchedServe on a store-indexed `g >= 0`; sched-rollout and
  mint completions are wire sessions (g = -1). The ceiling's natural arm
  and the mint's completions played mask-CLOSED, not advisory. The carry
  is now keyed by wid for wire sessions and the gate is open; "the same
  ckpt under advisory serve" = carry on, slot tokens fed.
- **Self-play census ⇒ target-seat scoping**: `--sched-binding forks`
  latches the seat that opens each wire session (the fork fires at the
  target seat's MAIN1 priority); the opponent is advisory on both sides.
- **Population = the ADR-0078 ceiling census, reused** (user decision;
  supersedes "generated at the baseline ckpt"): 4,084 eligible turns,
  1,742 at v<0.45 on `d4-critic-fullvis` (the pinned stratum critic),
  600 primary (mean v 0.198) + 200 context, `PAIRED_RNG_SEED` in
  `sched_pins.py`; 83 of the 600 sit in the ceiling's own sample.
- **Timing re-anchored** on the ceiling's stage-2 artifacts (2,720
  game-end completions ≈ 1.2 h on 4 lanes): the read is 2–3 h at 6
  lanes/side, not "≈ an hour". Accepted. **Resolution**: K=8 binomial
  floor 0.25 per window ⇒ ~1.0pp SE over 600 before CRN pairing; the
  2.2pp bar sits at ~2 SE — the day-zero read reports the empirical
  paired SE and pins K for the terminal read from it.
- **Serve-rule details adopted as built** (mirror the engine executor):
  land-first masked to lands at a quiescent main window (decline
  forbidden, the cast head picks which); NEXT present ⇒ single-candidate
  mask (logp 0 by construction); NEXT absent at a quiescent post-land
  main window ⇒ trigger 1 "absent" with the revision decoded FIRST and
  the answer taken under the revised plan (two-pass; never costs the
  phase); otherwise hold on spells (pass + non-spell options). Mask =
  `cand_allow` on the pointer logits; mu row carries `bind/allow/slot`
  + `sched.lp`; the loader reconstructs the mask (forced rows recompute
  to exactly 0 through the loader path — checked on the ingested smoke).
- **Found in passing, fixed**: `sched_slot_pick` raised on single-slot
  micro-batches (mulligan / attack / pass-only windows) ⇒ heuristic
  fallback — 1,266 per 480-game iteration in probe6 iter-5's own log,
  hidden by mixed 8-worker batches. The day-zero read serves both sides
  with the fix.
- Cold-start warm-up built (server default; `--no-warmup`). Natural-only
  sched points = a parser-only Java allowance (armId 0), jar rebuilt.
- Read pipeline: `scripts/sched_paired_read.py` (population / run /
  read); driver wiring (day-zero + terminal invocations, halt rule) is
  session two with the learner side.

**Day-zero read LANDED 2026-09-03 ([ADR-0095](../decisions/ADR-0095-m10-dayzero-read.md)): HALT** — −6.7pp ± 0.9 on 553 v<0.45 windows (z −7.6), context −12.6pp; 4.25 h measured (not "≈ an hour"); K=8/N=600 stands (read SE 0.9pp). Mechanism: trigger-2 mid-turn revisions re-decode empty at unlabeled states and bind as holds. Routes in the ADR; adjudication pending.

**Route 1 GATE PASSED 2026-09-03 (ADR-0095 addendum): the executor-strategy
planner (`m10-planner-distill-v2`, `scripts/sched_distill.py`) reads
FLAT (+0.9 ± 1.3pp) against advisory under the RELEASE rule; the pinned
"exhausted = hold" rule still −8pp because the emission basis is
pre-land (a plan is partial by construction). Fork 1 sub-pin amended: a
hold binds only where emitted; an empty re-decode at a revision trigger
releases the turn to the executor. probe7 init → the distilled graft.**


## I. The hand-basis planner (proposed 2026-09-04, user direction; not yet built)

**Finding (ADR-0095 route 1):** the planner's decode is a pointer over
the window's legal-now candidate list, so at the first MAIN1 window —
before the land drop, before rocks and rituals resolve — 28% of the
executor's realized casts have no slot the plan could name. Post-land
emission would only move the window; the user's examples (holding the
land to end of MAIN2 to keep a fuller hand; rocks and rituals changing
the mana mid-plan) say the plan must be able to name what is castable
*later in the turn*, with the land drop and mana development inside
the plan's order rather than ahead of it.

**Design lean: the plan's basis is the HAND (plus the board's activated
abilities), not the legal-now list; legality is the executor's job at
each window.**

1. *Key space.* The schedule decode's candidate set at a decode window
   = the legal-now candidates ∪ one virtual candidate per own hand card
   for its cast ability (entity row + the ability's `sa_vocab` id), and
   lands as candidates (the land drop is a slot — which land, when).
   The engine's ability labels are rules text (not constructible from
   card data, verified 09-04), so the virtual candidates come from a
   **mined cast-ability table**: card name → the cast-SA string(s) the
   engine emitted for that card from hand across the stores (primary =
   most frequent; alternates recorded), stored as a pool asset beside
   the sa_vocab. No engine change; a card never cast in any store is
   not plannable (nor was it ever cast).
2. *Sequential mana.* Not simulated. The plan's ORDER carries it (rock
   before the four-drop; ritual before the payoff); the per-slot
   afford bit already fed on the slot tokens (`slot_afford`, the census
   affordability heuristic under the now-source view) tells the planner
   which slots are affordable at this window; a planner that orders
   mana development first is what the labels teach (the executor's own
   lines do exactly this) and what reward can sharpen.
3. *Binding under a hand basis (serve).* At an own priority window:
   NEXT slot legal now ⇒ forced (as today). NEXT not legal but its card
   still in hand (or the ability still on the board) ⇒ **WAIT**: spells
   closed, lands/abilities open — the executor develops toward it (the
   plan may put the land later; a WAIT at a quiescent main window with
   a land in the plan ahead is the plan's own ordering). NEXT's card
   gone (countered, discarded, exiled) ⇒ trigger 1 (revision). End
   step ⇒ the turn is over (trigger 3, as today). A guard against a
   never-castable NEXT: WAIT is bounded by the executor's affordability
   read — if NEXT is unaffordable under the max-mana view for the turn
   (all sources + lands in hand), it is trigger 1 immediately.
4. *Targets.* The executor's realized casts matched against the hand
   basis: the unmatched rate falls from 28% to the cards drawn mid-turn.
   Lands re-enter the targets (the plan includes the drop).
5. *Loader / rows.* Slots stay (entity, sa_id) on the mu row; the
   featurizer's superset tensors (`sched_cand_*`) ride the example;
   `_sched_keys` reads them when present (fallback: the legal list).
   The learner's decode targets (session two) use the same superset.

**Cost:** the mining script (an afternoon, plus a full-corpus scan),
featurizer + model key space + serve WAIT semantics (a session), corpus
rebuild + distillation (an hour), the day-zero read (3.5 h). **Read
first:** the executor-agreement ceiling should rise (the 77% plateau is
partly the basis), and the day-zero number of a hand-basis planner is
the new baseline.

**§I named extensions (user, 2026-09-04; routed by name, none in the
hand-basis build):**
- *Abilities in the key space:* activations of board permanents (legal
  now — already plannable) AND of hand cards for after they resolve
  (cast the creature, then equip; cast the rock, then tap it) — mined
  activation strings per card; WAIT until the permanent exists. IN the
  hand-basis build.
- *Mana abilities in the plan:* deferred (Fork 6 / schedule-consistent
  payment); eventually in — the user's lean.
- *Multi-turn horizon + the explicit hold language:* "flash Maralen at
  the opponent's end step so next upkeep's tutor is live" is (1) an
  off-turn cast the hold-set must be able to NAME (hold X for window W),
  (2) a two-turn plan (this turn's setup, next turn's payoff — the
  certifier's h2 horizon already scores two turns), (3) a *reachable-
  cards* basis for the next-turn plan (hand ∪ tutorable library ∪ known
  top). Prerequisite found: **tutor/fetch target choices are not
  bridged** (`chooseSingleEntityForEffect` — the heuristic picks the
  card; ceiling measured 1.41pp/game vs the 2.2 bar and re-deferred at
  ADR-0080) — the model cannot "assume any card" until it chooses the
  card. Routing: the hold language after the hand basis; the horizon
  with the certifier's h2 labels; tutor targets when M11 re-opens (the
  reachable-cards basis is the argument that raises that ceiling — a
  tutor is worth more to a planner than to a window-by-window head).

## J. Decision-surface completeness — candidates surfaced 2026-09-04 (user question; UNROUTED until a scoping session)

Grounded in the callback census (DC pool: 1,136 callbacks/game, the
bridged tag set ≈ 52% of them) and the plan object as built:
1. **Slot TIMING, not just order.** A plan slot is executed at the first
   legal window (ASAP); the plan cannot say "after combat" (bluff-sized
   creature post-combat, pump pre-block, removal after blocks). Ordering
   ≠ timing; a per-slot phase anchor (MAIN1 / combat / MAIN2 / end
   step) makes the plan canonical over the turn's structure — the same
   class of gap as the land-timing point, and the executor's realized
   lines already contain the answer (distillation targets can carry the
   window's phase).
2. **One generic mid-resolution choice tag.** Tutor/fetch targets,
   `chooseCardsForEffect`, `confirmAction`, modes at resolution,
   `chooseColor`, counter types, replacement/static-effect choices are
   all SELECT-ONE/SELECT-K over an option list with obs — the pay_class
   mechanism (positional options, pointer head) already does that
   shape. M11 measured two genres separately; one mechanism would
   amortize the family (~40% of callbacks the heuristic answers today).
3. **Trigger ordering** (`orderAndPlaySimultaneousSa`, 12.6/game, every
   game): which ETB/upkeep trigger resolves first is the heuristic's; a
   planning-relevant choice never measured.
4. **Combat damage assignment** (`assignCombatDamage`, 6.5/game, 81% of
   games): which blocker dies is the heuristic's; attack/block are
   bridged, the third combat decision is not.
5. **Mulligan tuck at serve:** `TAG_TUCK` exists Java-side and the loader
   trains `mull_tuck`, but the server's TAG_TASK does not advertise it —
   verify; likely a free completion.
6. **Optional costs / modes inside the one-shot cast** (kicker 29/game
   in 35% of games): the census says fold them into the priority pick;
   verify what CastPlan carries today.
7. **Target intent on plan slots:** a slot names card + ability, the cast
   head picks targets at execution; certified arms are "soft-emission"
   the same way. A plan that sequences "removal on X, then attack"
   needs the target in the slot for the label to be faithful.
8. **Explicit hold language / off-turn plan** (named in §I).
9. **Reachable-cards basis + multi-turn horizon** (named in §I).
Routing rule: each item gets a name and a measured argument at the next
scoping session (the ADR-0077 no-silent-loss rule); 1 and 7 ride the
hand-basis plan object; 2–6 are bridge completions with their own
ceilings; none gate the current build.

**§J adopted by the user (2026-09-04) with one principle added, which
binds §I's key space and every reachable-cards extension:**
*the plan's basis is the seat's INFORMATION SET, never the engine's
truth.* Virtual candidates come only from what the player legitimately
knows: the hand (visible), the board, the seat's own decklist minus
known departures — and a library card is "reachable" only up to what
the player could know (an opponent's unrevealed exile or face-down
removal means the deck's true contents are NOT known; the model may
not assume a card is still there). Choices WITHIN abilities (tutor
targets, modes, cards-for-effect) are decided when the engine presents
the legal options, never assumed ahead; a plan slot naming a tutor's
target is an INTENT, and legality is the engine's at the window. This
is the seat-view invariant (obs perspective, the `full_vis` gate for
the critic only) applied to the planner's key space — the featurizer
builds virtual candidates from obs-visible zones and the decklist, and
nothing else. The hand-basis build (§I) starts 2026-09-04.

**§I status 2026-09-04 (user):** built and read (ADR-0095 addenda): the
hand-basis planner reads −1.8 ± 0.7pp at day zero (the same read as the
legal basis on shared windows); adopted as the plan object for session
two with the release rule and the distilled-hand graft as probe7's
init. **Two refinements ROUTED INTO SESSION TWO:** (a) WAIT closes
sorcery-speed spells only (instants/flash stay the executor's through
combat; speed from the card table's types/keywords); (b) the featurizer
excludes activations of tapped / summoning-sick / already-used board
hosts from the virtual candidates (13.4K fast-failing slots per read).

**Both refinements BUILT (session two, part 1, 2026-09-04 afternoon).**
(a) `SchedServe.bind`: under a WAIT the spell mask opens Instant-typed and
Flash-keyworded spells (card knowledge from the veto_knowability card
table; unknown names read as sorcery-speed = closed; effects that GRANT
flash are not card knowledge of the spell and stay closed) — telemetry
`sched_bind_wait_open(_spells)`; HOLD is unchanged. (b) the featurizer's
`board_activation_open`: a board host's activation enters the virtual
superset only with a road back this turn. The option scan does not filter
by payability (AnvilOptions PAYCHECK off), so an absent board activation is
absent for a NON-mana reason, and three such reasons never clear within
the turn, all readable from the seat's own visible state: tapped host
({T}/{Q} costs), summoning-sick host ({T}/{Q}; the engine's `sick` is
creature-only), and **spent** — a loyalty-cost or "activate only once each
turn" ability absent at a QUIESCENT MAIN window (sorcery-speed timing
holds there, so absence means used; mid-stack the absence is timing and
the candidate stays). "Used" is thus derived from visible state, not from
per-turn action tracking (the wire history carries no turn/sa; a Java obs
flag would be a serializer change needing the ADR-0025 forkcheck proof).
Key-space consequence: the distilled-hand graft was fitted on the wider
superset, so the corpus is REBUILT and the head refitted on the refined
featurizer (`m10-planner-distill-hand2`) before the day-zero re-read on
the same population — the standing day-zero-gated-binding rule.

**Found while validating (b) — a serve-rule defect that predates the
refinements: `quiescent_main` read the stack from entities only.** The obs
carries the stack two ways: cards on the stack are entities with
`z="stack"`, but triggered/activated ABILITIES on the stack never enter the
zone and appear only in the separate `obs["stack"]` list (the Java option
scan keys sorcery-speed legality on MagicStack for the same reason). In the
ceiling census 9.3K of 79K priority windows had an ability on the stack
and no stack entity — all read as quiescent. Consequences: binding rule 3
(NEXT absent at a quiescent main window ⇒ failed slot) fired at trigger-
on-stack MAIN windows and failed sorcery-speed slots for TIMING — the
hand-basis read's 13.4K "unactivatable" fails were partly this (Quintorius
+1 absent under its own token trigger, activated at MAIN2 as planned); rule
1 (land-first) misfired the same way on the legal basis; and the new
loyalty/once-per-turn "spent" rule misread 117 of 1,010 realized
activations in 150 census games (8 after the fix — untap lines and
no-target loyalty, accepted). Fixed in one place (`featurize.quiescent_main`
tests both representations; `SchedServe.quiescent_main` delegates), corpus
rebuilt on the fixed helper. The day-zero re-read measures the fixed rule
set as a whole; the earlier day-zero numbers (−1.1 legal, −1.8 hand) stand
as read but carried this misfire.

**Driver wiring (item 5) BUILT the same afternoon:** `selfplay.py` takes
`--sched-binding/--sched-basis/--sched-empty-rev/--sched-empty-emit/
--ability-table`; ONE derivation (`sched_flags(args)`) feeds every server
the driver starts (generation and arms — the candidate always plays under
the run's regime; the pre-reset driver never passed binding to any
server). `--paired-read PLAN_DIR` runs the stratified paired read on the
init ckpt at DAY ZERO (verdict HALT ⇒ `PAIRED-HALT`, notify, exit 5 — the
mid-point rule) and on the final ckpt at the TERMINAL (verdict + day-zero
baseline ride the COMPLETE notify); `--paired-every N` adds informational
mid-run reads. Records live in `loop_state.json` (`paired_*`), idempotent
on resume; the read's `read.json` is copied beside the loop as
`paired-<tag>.json`. The command mirrors the regime (basis / empty-rev /
empty-emit) and uses the harness's newest-jar rule.

