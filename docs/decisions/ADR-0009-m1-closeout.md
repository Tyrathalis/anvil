# ADR-0009: M1 closeout — BC agent plays; winrate 46.8% vs the expert it imitates

- **Date:** 2026-07-10
- **Status:** accepted
- **Design-doc anchor:** m1-bc-plan "M1 is done when"; §15 rows; ADR-0008 (gate)

## Context

M1's three completion criteria: (1) the honest held-out agreement number
exists and is compared to the high-80s target; (2) the BC agent completes
real games over the bridge with provenance-clean fallback and a recorded
winrate vs the heuristic; (3) the corpus + store are provenance-complete for
M2. (1) resolved TRUE in ADR-0008 (honest 0.9758, ~9pp above target); (3)
closed with D6 (113,592 games, zero-error validated). This ADR records (2)
and closes the milestone.

## Decision

**M1 is CLOSED.** The D8 eval path ran same-day from executor first-light to
measured arms:

- **Executor:** CastPlanRealizer adjudicates legality only (the M0 65% veto
  rate was canPlaySa's *judgment*, never consulted now). Host-level
  disambiguation ladder: shape-fit → payability → kind prior → scan order;
  modal spells cast mode-less (modes+targets heuristic at the census-mapped
  interception points — the M1 scope line realized); divided-as-you-choose
  gets a deterministic even split. Two smoke-crash classes fixed en route
  (fallback-flag misread → infinite London mulligan; divided-allocation NPE).
- **Serve path:** wire observations = the obs-log dec record + last-K history
  ring (back-filled at ret to match the training loader's joined view);
  featurization is loader-parity-tested (byte-identical tensors, act()==
  forward argmax — tests/test_serve_parity.py). Information-set rule stays in
  the one leak-tested Python transform.
- **Arms** (200 held-out valpair pairs, mirrored seats, same seeds, w=8
  nice-19, 1,000 games total):

  | arm | winrate vs heuristic | veto rate | casts | notes |
  |-----|---------------------|-----------|-------|-------|
  | heuristic self-play | (seat0 47.5%) | — | — | median 21 turns |
  | model δ=0 | **46.8% ± 2.5pp** (187/400) | 7.8% | 13,387 | 398/400 decisive |
  | model δ=+2.169 | **45.5% ± 2.5pp** (182/400) | 3.1% | 13,746 | 398/400 decisive |

  The δ arms are a statistical tie; calibration halves the veto rate
  (574→219 unpayable) at no winrate cost. Zero draw clocks; 4 crashes/800
  model games (0.5%, the known engine class). **Throughput 927–1,068 g/h vs
  959 heuristic at matched settings — bridge + GPU inference in the loop is
  operationally free at w=8** (M0's 2.6% echo tax remains the protocol
  floor; the batch-1 server never bottlenecked).
- **Provenance:** fallback confined to unbridged tags (modes, tuck,
  mid-resolution family) + ~0 server fallbacks; every cast carries rung/veto
  telemetry; runs pin fork commit + jar hash as always.

**The number to carry: a pure BC agent, one epoch of D7's 3-epoch recipe
behind it and a same-day executor, plays within ~1σ of parity against the
heuristic that generated its training data, on matchups it never saw.**
Winrate was recorded-not-gated; parity was not required to close M1.

## Consequences

- **M2 begins.** Entry points, in the order the evidence suggests: fork-API
  hardening for state forking (ADR-0002's flagship contribution, prerequisite
  for rollouts); rollout-labeled value targets (the measured fix for the
  matchup-entropy-floor value head); RL fine-tuning from `d7-ep3` (V-trace,
  §6 phase 2).
- **Rung-1 output-channel gaps are now measured, not speculative** (D8
  census): order-rung 30% of multi-SA casts, modal 1.2%, divided 0.03%. The
  M2 action schema gets SA-level candidates (labels exact via the `oi` field
  logged from now on), mode heads, and allocation heads, in that order of
  measured mass.
- Winrate arms are cheap (~12 min each): re-measure per M2 checkpoint as the
  standing strength eval; δ choice stays open (tie) — RL init should probably
  start action-rich (δ=0) and let the reward decide the pass boundary.
- The census/obs instrumentation carried the whole diagnosis arc (mulligan
  loop, modal cluster, divided NPE) — keep both on for all eval runs; the
  cost is noise at these scales.
