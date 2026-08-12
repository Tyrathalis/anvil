# M7 — the credit-assignment question: can dense per-decision signal reopen improvement?

**Opened:** 2026-08-10 (user-approved pins, this session).
**Anchors:** [ADR-0049](../decisions/ADR-0049-flat-cycle-audit.md) (the
bottleneck named: learning-signal density); [ADR-0050](../decisions/ADR-0050-m6-closeout.md)
(M6 closeout + carry-forward inventory); [ADR-0048](../decisions/ADR-0048-cycle3-resolution.md)
(the flat cycle that chartered the audit); design §4 (drill-regime value
targets), §6 (expert-iteration channel), d6-vtrace-loop §6c (the penalty
under re-tune); [m6-plan.md](m6-plan.md) (the pattern this doc follows).

## The question

ADR-0049 measured that the loop's only dense per-decision signal is the
§6c rejected-intent penalty (suppressive by construction) and that the
terminal outcome at 20+ turns cannot differentiate timing-quality among
behaviors the policy already explores (hold-then-cast abundant in
exploration, flat across training). M7 asks: **if we put a real dense
per-decision signal into the training path, does strength move?** The
program is probe-gated at each step; the headline close remains the
standing combined paired read (vs 0.5316, or its re-baselined successor
after the D3 boundary), honest in either direction.

**Mechanism-of-action statement (why value targets reach the policy):**
V-trace's policy-gradient advantage is ρ·(r + γV(s′) − V(s)). Today V is
trained from the same sparse terminal outcomes, so its per-decision
bootstrap differentials are noise (the measured ranking ceiling,
ADR-0036/0044). A V that is *locally accurate at drilled decisions*
converts the bootstrap differential into exactly the dense per-decision
signal the audit found missing. The critic enters the reward path through
the advantage — this is the difference from its variance-reduction-only
role ADR-0049 documented.

## D1 — P0, the deciding probe (existing data, zero box time)

**RESOLVED same session ([ADR-0051](../decisions/ADR-0051-p0-decision-delta-probe.md)):
gate NOT MET — split fraction 4.0%/6.5% (run13/old era) vs the 0.30 pin,
RMS true Δwr 0.082/0.000 vs the 0.10 pin, directional null. The sharper
finding: per-cell sampling noise puts the pinned threshold below the
estimator's resolution at any achievable split count — natural-variation
dense labeling fails as an instrument. Routing per the pin: D2 as
designed is NOT funded; the search-shaped form (forced-branch paired
rollouts, below) replaces it as the D2 candidate; D3's trigger
re-decided (rides with the forced-branch build).**

**Insight that makes it cheap:** within a single fork point, the K=8
sampled completions share an identical game state — the only difference
is the sampled action (and downstream sampling). Conditioning on the
first-window action *within* a fork point is therefore unconfounded.
No forced-action machinery is needed; run13's in-loop drill fork stores
(`data/trajectories/drillmix000..019-*-forks`, K=8, ~320 fork points ×
20 iterations, mu records intact) already contain everything.

**Method:** per fork point, classify each completion by the drilled
seat's first-window action (cast-now vs hold; sub-class hold-then-cast-
later from the completion's own decision sequence); compute the
within-point outcome differential Δwr; aggregate with binomial noise
subtracted (random-effects: var_signal = var_observed − mean binomial
var); read sign-consistency across iterations (same drills, evolving
policy) and per curation bin (winnable/coin/long_shot).

**Pre-registered gate (PINNED 2026-08-10, before any numbers were seen):**
the dense-signal path is FUNDED if RMS true Δwr ≥ 0.10 across ≥30% of
fork points with non-degenerate action splits, **plus** a directional
check: Δwr favors holding (hold-then-cast-later > cast-now) at the
positions where ADR-0049's holding metric fires. If the true signal
variance is ~0, per-decision rollout deltas at this horizon cannot
separate actions and the antidote must be search-shaped — tier-3 moves
up. Either answer is decisive.

**Rider:** the audit's scratch instruments (behavioral-delta /
cast-suppression read, interaction-holding metric) are productionized
into `scripts/` as standing per-run instruments — they are how a bundled
D2 run stays attributable.

## D2 — P1, the intervention build (gated on D1)

**AMENDED post-D1 (ADR-0051): the natural-variation C2b v1 is dead; D2's
candidate is now the forced-branch paired-rollout generator** — the
forced-action harness feature (scripted first decision post-fork), branch
A/B completions with paired seeds, K as a resolution dial. It is at once
tier-3's first rung (1-ply search targets), §6's contrastive-pair
generator, and the instrument P0 lacked. C2a and C3 below stand as
originally scoped (C2a bundles with any run; C3's evidence is ADR-0049
telemetry, untouched by P0). A sizing read (paired-variance measurement
at small K on a handful of decisions) prices the K dial before any
campaign. Next session picks this up as a design+build decision with
the user.

**Forced-branch design PINNED (user-approved 2026-08-10, second
session):**

1. **Act = the current policy's preferred cast, pass masked** (the
   on-policy option; rejected alternative: replaying the source game's
   recorded action — era-fragile at the measured 7/8 exact-replay rate
   and off-policy the moment the policy moves). Mechanism: the normal
   bridge ask with a new **no-pass constraint flag** (bridge protocol
   addition; served as a mask on the pass logit before sampling); on
   veto, the standing §6b re-ask machinery walks down to the next-best
   realizable cast with pass still masked. Δwr therefore prices *the
   cast the policy would make now* vs holding — exactly the contrastive
   signal C2b consumes.
2. **Hold = forced pass exactly once** — the drilled seat's first
   `chooseSpellAbilityToPlay` post-fork — then free play (end-of-turn /
   second-main / later-turn casts all permitted). Matches ADR-0049's
   hold-then-cast metric; the question is cast-*now* vs not-now.
3. **No forced-branch obs stores in v1.** The branch label IS the
   action (no μ-record classification needed — the P0 requirement that
   forced branches obsolete), and Δwr joins onto the *mainline* fork
   window that `Obs.mark` already keys. v1 output = labels-JSONL only:
   no `-forkobs` on forced completions, no synthetic-id branch
   encoding, no ingest-hygiene machinery. Revisit only when something
   (tier-3) needs the completions' internals.
4. **Pairing = shared rollSeed per (fp, r) across branches** (identical
   determinized library order, downstream MyRandom stream, and
   announced server noise seed; divergence comes only from the forced
   decision — common random numbers, paired variance shrinks with K by
   construction). A pair with a crashed member is **dropped whole**
   (the ~12% crash tax must not unbalance branches); crash/skip counts
   recorded per row.
5. **Feasibility guards, loud not silent:** (i) no realizable cast at
   the fork window ⇒ `branch_skip` recorded, point dropped — the skip
   *rate* is itself a finding (high ⇒ drilled decisions are hold-only
   states and instrument coverage shrinks); (ii) force only when the
   fork window's priority player is the bridge seat.
6. **Output shape:** one labels row per fork point carrying both
   branches (`w_act[]`, `w_hold[]`, per-branch draws/crashes/skips,
   pairs actually used) — pairing explicit in the data, Δwr a
   one-liner join.
7. **Sizing read before any campaign:** 20–30 drilled fork points at
   K ∈ {4, 8, 16} per branch; measure paired SE of Δwr vs K
   empirically against ADR-0051's noise-floor arithmetic. Cost note:
   forced-branch mode is 2×K completions per fork point.

**Pin 7 RESOLVED (2026-08-11, [ADR-0052](../decisions/ADR-0052-ksizing-read-map-serving-mismatch.md)):
NULL at every K ≤ 16, on a corrected population — no Δwr-label campaign.**
The read validated the instrument (hold ≈ natural continuation corr 0.885,
100% pairs, 0 crashes, pairing beats the independent floor) and en route
found the standing drill-map serving mismatch: `gs generate` replayed
mainlines argmax over sampled sources, so map winrates priced divergent
states (map 0.374 vs true 0.062, corr 0.23; true crash states 78%
0-for-16). After the fix (`--sample-mainline`, corrected three-anchor maps
in `drill-map-cycle3-true/`: crash−2 true wr 0.491 with 52% band mass),
the re-read on 59 in-band forced points still measured pure 1/√K noise
scaling, RMS true Δwr ≤ ~0.08 at K=16 vs the 0.10 pin. Single-decision
cast-vs-hold deltas are small in truth even at contested states — the
credit signal lives in decision sequences (composes with ADR-0049).
**C2b as per-decision Δwr targets is falsified at affordable K.** D2's
candidate list re-forms (routing = user decision): tier-3 search targets
(values aggregate over sequences) / corrected-population mixtures + C2a
(maps now trustworthy; case-drilling has never actually been tried —
ADR-0052 blast radius) / sequence-level contrastive design round. C3
untouched. Coverage rule for any forced campaign: ~96% fire × ~33–40%
model-seat-active ⇒ ~3× overshoot or model-active drill selection.

**D2 ROUTING PINNED (user-approved 2026-08-11): C-probe → B-vehicle →
A-parked.**

1. **Sequence-contrastive probe FIRST** (highest information per cost;
   tests M7's hypothesis at the granularity ADR-0052's evidence favors):
   extend the forced-branch harness with a PERSISTENT directive over an
   N-turn horizon — three arms per fork point sharing rollSeeds per
   (fp, r): NATURAL (no directive), HOLD-N (force-pass every bridged
   priority cast window for N turns post-fork, then free), ACT-N
   (forbid_decline every priority window for N turns; mid-sequence
   exhaustion degrades to pass, counted loudly). N = 2 default (matches
   ADR-0049's hold-then-cast horizon and the crash−2 anchor distance),
   CLI-parameterized. Population: the corrected in-band points
   (arm-o2 band, both stores). K = 16, sampled instrument serving,
   labels-only (pin 3 unchanged). Read: pairwise Δwr (hold−nat, act−nat,
   act−hold) through the ADR-0051/0052 variance decomposition. Resolvable
   sequence-level signal ⇒ it defines the training target (sequence
   advantages / plan-segment credit — connects to ADR-0042's §3a
   planning priority). Null on winnable states ⇒ drilled mid-game states
   are outcome-insensitive to short policy variation — M7 moves toward
   its "dense signal cannot reopen improvement" branch with the full
   measurement chain.
2. **One training run as the bundle vehicle (road B):** corrected-
   population drill mixture (band on TRUE winrates, informed anchor) +
   C2a aux value targets from corrected maps + C3 §6c re-tune — plus
   sequence-contrastive targets if the probe funds them. Closes
   case-drilling honestly either way (the one-shot verdict never bound
   it — run11 was distributional supplementation, ADR-0052).
3. **Tier-3 search (road A) parked behind a corrected-label critic:**
   naive rollout-backed 1-ply inherits the same noise arithmetic that
   killed C2b; revisit once a critic retrained on corrected-map labels
   exists to back the search.
4. **Sequencing:** probe (labels-only, pre-boundary) → D3 stability pass
   + era boundary + re-baseline → the run. Standing gate unchanged.

**Sequence probe RESOLVED at N=2/K=16 (2026-08-11, same day): the first
outside-noise contrastive signal in M7 — directional, at sequence
granularity, in ADR-0049's predicted direction.** 61 pooled points
(27 s0 + 34 s1), 976/976 triples, 0 crashes, sign-replicated across
stores:

| contrast | mean Δwr | t | var ratio | RMS true |
| --- | --- | --- | --- | --- |
| hold-2 − natural | **−2.6pp ± 1.3** | **−2.02** | **1.33** | **0.049** |
| act − natural | −0.9pp | −0.82 | 0.94 | 0 |
| act − hold | +1.6pp | +1.62 | 0.83 | 0 |

Readings: (1) forced 2-turn deferral measurably costs winrate while
forced-greedy ≈ natural — the policy's cast timing is already near its
greedy frontier and the loss channel is deferral: causal,
engine-adjudicated evidence for the cast-suppression story ⇒ **C3
re-priced from "probably necessary" to "directly evidenced"**;
(2) hold−nat is the only cell in all of M7 with positive var_signal —
sequence granularity carries per-point signal where single decisions
carried none — but RMS 0.049 < the 0.10 label pin and ratio 1.33 on 61
points is suggestive, not decisive; (3) instrument clean at scale.
Probe artifacts: fork `6d2f44c9d3`
(`-forceseq`), `scripts/seq_probe_read.py`, runs `seqprobe-s0/s1`.

**K=32 / N ∈ {2,4} rung RESOLVED same day
([ADR-0053](../decisions/ADR-0053-sequence-probe-resolution.md)): the C
bundle is FUNDED.** Deferral cost compounds (−2.6pp @ N=2 → **−6.1pp @
N=4, t = −4.49**, ≈ −1.5pp per held turn, 27/28 nonzero points
negative); per-point RMS true Δwr grows with horizon to **0.090
(hold−nat) / 0.085 (act−hold) ≈ the 0.10 pin**, var ratios 3.7+; timing
ordering natural > greedy ≫ hold (act−nat −1.7pp at N=4 — pure
aggression is NOT the target). Trainable contrast = act−hold (2 forced
arms, no natural): 64 completions/point at N=4/K=32. No further rungs —
horizon is a campaign hyperparameter. **Next: the C-bundle design round
(sequence-contrastive targets at N≈4 + C2a + C3, with C3's re-tune
calibrated against the measured −1.5pp/turn passivity cost) → D3
boundary → the run vs the standing gate.**

Three attribution-separable components; bundle shape decided on D1's
numbers (aggressive-inclusion posture per ADR-0042, with per-lever
instruments):

- **C2a — rollout value targets at drilled decisions** (design §4
  verbatim). The loop already computes per-fork-point K-rollout winrates
  every iteration (drill accounting); C2a joins them onto the fork
  decision's windows as an auxiliary task-token-flagged value loss,
  capped as a fraction of value batches. Zero new generation cost;
  ~a day in rl.py + tests.
- **C2b — contrastive per-action advantages** (design §6's dormant
  expert-iteration channel: fork, roll out, engine adjudicates →
  contrastive pairs). D1's within-fork-point Δwr becomes a per-action
  policy-gradient target at drill decisions, natural-variation v1 (no
  forced actions). Inclusion depends on D1's split abundance.
- **C3 — §6c economy re-tune.** Pre-work read (cheap, run13 stores):
  decompose the 3.8–8.3 rejected-intents/trajectory into re-ask chains
  (paying up to 8λ) vs independent events — chains ⇒ first-attempt-only
  pricing; independents ⇒ λ decay (0.02 → ~0.005 floor). A λ change is
  an RL-chain boundary; the next cycle's fresh mixture absorbs it.
  Anti-passivity guards (casts/game, first-attempt veto) stay armed —
  the audit's cast-suppression finding makes them MORE important, not
  less.

**Gate:** the standing 2,000-game combined paired read + evalset
decomposition + the productionized D1 instruments (did cast-suppression
reverse? did credit reach hold-then-cast timing?).

## D3 — the era boundary (PINNED: after D1 clears, before D2's run)

**AMENDED post-D1 (ADR-0051): the "after D1 clears" trigger fired on a
gate that did not clear. New trigger: the pass rides with the
forced-branch generator build (same justification — fork-rollout-heavy
work — and the forced-action feature touches the same harness surface).**

The carried fork stability pass (IndexOOB, targeting-retry, MayPlay
`.get(0)`, MinMaxBlocker realizer gap) lands once D1 gates through and
before D2's first training run: engine boundary ⇒ `forge forkcheck` +
re-baseline final_read (~2,000 games, overnight). Rationale: D2 leans on
fork throughput every iteration (~12% crash tax today), the MinMaxBlocker
fix corrects a §6c mis-pricing corner (silent illegal-block discards),
and the λ re-tune is an RL-chain boundary anyway — one clean era for the
whole program. The fork-index namespace fix (fork `a73ee9d4e4`,
FORK_G_BASE = 1e12) is already landed and smoke-proven; it is
store-format-only and rides the same era.

## Done-when

1. D1 resolved against the pre-registered gate (either direction).
2. If funded: D2 built with per-lever instruments; one training run
   consuming the dense signal, closed by the standing paired read.
3. D3 boundary executed (if D1 funds D2): stability pass + forkcheck +
   re-baseline, all D2 numbers on the new baseline.
4. An ADR records the credit-assignment verdict: did dense signal move
   strength, and which component carried it?

## Carried / explicitly deferred

- Tier-3 search: the mature form of C2a/C2b; unparks immediately if D1
  fails the gate (search-derived targets are then the remaining path).
- Pool expansion, iteration pipelining, eval thinning: unchanged from
  m6-plan.
- Rank-critic ΔV as potential-based advantage shaping: considered,
  deliberately NOT in the v1 bundle — the rank-critic was trained on
  loss-adjacent c2 labels; its ΔV elsewhere is extrapolation
  (ADR-0036's population lesson). Revisit only with rollout audit.
- Encoder/B-3 work: parked (M6 verdict — representation not the binding
  constraint).
