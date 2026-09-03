# M10 reset — DRAFT for adjudication (session 2026-09-02, the step-back round)

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
ckpt and probe7's init.** Fork 6 pending.

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
