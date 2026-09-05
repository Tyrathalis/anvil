# M11 plan — the OPTION SCORER (CHARTER DRAFT, 2026-09-05)

*Status: CHARTER DRAFTED at the M10 closeout ([ADR-0096](../decisions/ADR-0096-m10-closeout.md)),
direction agreed with the user in the 2026-09-05 session; the forks below carry recorded leans
and are adjudicated before anything builds (the project's design-round discipline). The name
reconciles with the "M11-routing" ceiling probes ([m11-routing-probes-spec.md](m11-routing-probes-spec.md),
ADR-0080): those measured two decision surfaces this milestone's mechanism serves (tutor targets
1.41pp/g, resolution payments 0.69pp/g).*

## Charter (agreed 2026-09-05)

**One head that scores the options the engine presents at ANY decision window, trained on
search-adjudicated per-option outcomes, acting where its margin clears a bar and deferring to
the executor elsewhere.** A schedule arm is an option whose content is a sequence; a tutor
target is an option whose content is a card; a payment class, a trigger order and a combat
damage assignment are options too. One search (the inline certifier, generalized by decision
tag) produces one label shape (a per-option Δ spread on the store row); one scorer consumes it;
its margin is the pivotality read-out that aims the search, picks drills, and gates any
deployment-time lookahead. Search is amortized at training time; deployment is the network.

## The facts it starts from (ADR-0096)

- The within-turn scheduling ceiling is real: +13.5pp/game under an oracle over 16 arms
  (ADR-0078); the certifier's labels are two-thirds signal at K=8 (split-half 0.50, retest
  27/40 re-certify) and improvements are CONTENT changes (47% disjoint card sets, 0% reorders).
- The wins are sparse (one window in five has an arm ≥ θ), state-specific (every arm family
  averages below natural; a family prior ranks at 0.06), and invisible to the executor's frozen
  representation (exact-arm head 0% at 4× data; frozen-trunk scorer Spearman 0.08 flat vs 0.66).
- **Pivotality is learnable from the frozen trunk: AUC 0.64 → 0.69 rising with data** (top-decile
  precision 0.60–0.67 vs base 0.37). The flywheel has a seed.
- A faithful generative planner bound at serve costs −2.3pp (commitment); the executor's
  per-window flexibility is worth keeping — hence margin-GATED acting, never blanket binding.
- Instruments proven and carried: paired strength read (SE 0.7pp at K=8/N=600), inline
  certifier (`-certify`, `anvil.certify`, finish → labels + spreads), harvest driver, retest,
  scorer/pivotality probes, jar-identity proof, driver heartbeat + HALT wiring.

## The canonical shape

1. **Option content encoding (pre-pinned, shared by every surface).** An option token =
   [host entity row ⊕ ability/sa embedding ⊕ kind ⊕ target refs ⊕ (for plans) pooled slot keys
   + length ⊕ (for plans) phase anchor]. The schedule head's `_sched_keys` and the pay-class
   positional-option mechanism are the two existing halves; this unifies them. Game-agnostic by
   shape (an option list with content vectors), Magic-specific only in the featurizer.
2. **The scorer head.** score(state, option) → predicted Δ vs the natural line, over the
   presented options plus the natural/pass option (score 0 by construction). Trained with a
   within-window pairwise ranking loss + a scale anchor on the spread; the trunk is TRAINABLE
   (Fork B). Its outputs give: the pick (argmax), the margin (top − natural), the spread
   (pivotality), and a ranking for drill/label selection.
3. **The certifier by tag.** `anvil.certify` answers arms for any tagged window: SELECT-ONE
   windows enumerate each presented option as an arm; priority windows enumerate schedule arms
   (today's `build_arms`) AND single casts; K rolls to a horizon; the spread rides the store row
   as the label. Sampling weight = a uniform floor + the scorer's predicted pivotality (Fork D).
4. **Margin-gated acting at serve.** At a window: if the scorer's margin ≥ bar → play the top
   option (a plan-type option arms the executor for the turn: plans survive as ONE option type);
   else the executor plays. Replaces binding rules 1–4 and WAIT.
5. **Critic lookahead (Fork C).** Copy the game, apply one option, evaluate with the critic — a
   ~100× cheaper arm score than 2-turn × K=8 rollouts. Its reliability against rollout spreads is
   the milestone's first read; if adequate it becomes the training-time labeler for most
   windows and the only search a deployment ever does (server-side, gated by pivotality).
6. **Deployment.** The network alone on a phone; lookahead only where the pivotality read-out
   fires and only where compute exists. The scorer's amortization IS the deployment story.

## Forks (leans in bold; adjudicate before build)

- **A. First surfaces.** **Priority casts + schedule arms (the funded ceiling), then tutor
  targets (1.41pp/g measured, ChoiceDirective exists)**; mid-resolution surfaces wait on §J
  item 10 (stack abilities visible to the model).
- **B. Representation.** **Trainable trunk for the scorer, initialized from the ckpt of record,
  with the executor's cast head frozen as the acting policy below the bar**; alternative =
  frozen trunk + deep head (the probe says no). Guard: the executor's strength under advisory
  must not move (paired read, advisory vs advisory across ckpts).
- **C. Label target.** **The pinned h2 composite spread for training (reliability measured), the
  critic-lookahead read FIRST as the cheap substitute**; horizon-0 win as the strength truth.
- **D. Certification weighting.** **Uniform floor (30%) + pivotality-proportional**; the floor
  keeps the head learning about dull windows and keeps a comparable stratum with era zero.
- **E. Reads.** **Primary strength = the paired read (candidate under margin-gated acting vs
  the same ckpt advisory, fixed population, ADR-0078 bar scale); mechanism reads = scorer
  within-window Spearman vs search (bar: > 0.3 at the frozen probe's N, i.e. clearly above 0.08
  toward the 0.66 ceiling), pivotality AUC (bar ≥ 0.70), certified-label yield per rollout.**
  KILL: scorer Spearman not above the frozen probe at equal N after the first trainable fit.
- **F. Payment cash-in.** **Parallel track**: re-advertise the M9 payment capability (ADR-0075,
  +2.96pp as a supervised conditional competency) as an option surface of the same scorer, or
  as its own head if faster — the shortest path to a strength number that moves.

## Build order (staged around the cheapest decisive read)

0. **Critic-lookahead reliability read** — Java: apply one presented option on a GameCopier copy
   and snapshot (a one-step `ScheduleDirective` with horizon "after this action"); Python: the
   critic on the resulting state vs the rollout spread, Spearman within window on the harvest's
   806 points. One session; decides Fork C.
1. **Option-content encoding + scorer head on a trainable trunk**, fitted on mint + harvest
   spreads (3,475 windows, ~45K option scores); read = Spearman/AUC vs the frozen probe at equal
   N and the learning curve. The first build read; the KILL lives here.
2. **Certifier by tag + pivotality-aimed sampling** (server: weight function; Java: SELECT-ONE
   arms for tagged windows); harvest 2 under advisory generation with the scorer aiming.
3. **Margin-gated acting at serve** (the mask machinery exists) + the paired read.
4. **The long run**: labels accrue inside generation; scorer retrained per era on the growing
   pool with the mint as the era-zero anchor; paired read at day zero, mid-point, terminal.

## Inherited obligations and hazards

- Information-set principle (§J): choices within abilities are decided when the engine presents
  the legal options; the scorer only ever sees presented options.
- §J item 10 before any mid-resolution surface: abilities on the stack reach the model only as a
  count today.
- Sampled-mainline replay parity is bounded by serving jitter (~20% of games): reads pair
  within-run (CRN) and budget cross-run divergence.
- Void arms (step-0 veto) are 32% of certifier rollout time: a Java legality pre-filter before
  harvest 2.
- Engine changes = boundary events unless ADR-0025-proven (forkcheck vs the 08-21 run: 498/500).

## Out of scope / retired

The generative pointer-decoder planner, blanket binding and the WAIT machinery, planner PG/KL,
the follow term (ADR-0096). Deployment-time tree search on device.
