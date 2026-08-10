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
