# M11 plan — the OPTION SCORER (CHARTER DRAFT, 2026-09-05)

*Status: CHARTER ADJUDICATED 2026-09-05 ([ADR-0097](../decisions/ADR-0097-m11-charter-adjudication.md))
at the M11 scoping session, the same day it was drafted at the M10 closeout
([ADR-0096](../decisions/ADR-0096-m10-closeout.md)). Forks A, B, E, F adjudicated (single network;
payment classes as the second surface; the standard read closes); C and D keep their leans and are
pinned at Build 0's read and Build 2's launch respectively. The name reconciles with the
"M11-routing" ceiling probes ([m11-routing-probes-spec.md](m11-routing-probes-spec.md), ADR-0080):
those measured two decision surfaces this milestone's mechanism serves (tutor targets 1.41pp/g,
resolution payments 0.69pp/g).*

## Charter (agreed 2026-09-05; adjudicated the same day, ADR-0097)

**Every decision the engine presents is a list of options; the network scores each option as an
advantage over the natural line; one label format (a per-option Δ spread on the store row, from
the certifier at any decision tag) feeds that score at every surface.** The scorer IS the
policy's action head (single network): acting is softmax over scores, the margin gates composite
plan-type options, PG trains every window and spreads train the certified ones, on the same
logits. A schedule arm is an option whose content is a sequence; a tutor
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
2. **The scorer head = the action head (Fork B, ADJUDICATED single network).** score(state,
   option) → predicted Δ vs the natural line, over the presented options plus the natural/pass
   option (score 0 by construction). The same logits carry two losses: PG on realized outcomes
   at every window (dense, as today) and a within-window pairwise ranking loss + scale anchor on
   the certifier's spread where one exists (the grounded-driver machinery of ADR-0088 drives
   the label term). The trunk is trainable; the executor is not a separate frozen network. Its
   outputs give: the pick (argmax / sampled), the margin (top − natural), the spread (pivotality
   — Grindstone's ε-pivotality criterion, §6, made a read-out), and a ranking for drill/label
   selection. Under this shape the certifier's per-tag spreads ARE the ceiling measurement
   (rate × best-option Δ), so a new tag's ceiling and its labels come from one run.
3. **The certifier by tag.** `anvil.certify` answers arms for any tagged window: SELECT-ONE
   windows enumerate each presented option as an arm; priority windows enumerate schedule arms
   (today's `build_arms`) AND single casts; K rolls to a horizon; the spread rides the store row
   as the label. Sampling weight = a uniform floor + the scorer's predicted pivotality (Fork D).
4. **Acting at serve.** Single-option windows (casts, payment classes, targets): the scorer's
   scores are the action logits — no gate, the head acts as the policy does today. Composite
   plan-type options (a schedule arm): played only where the margin ≥ bar, arming the executor
   for the turn (plans survive as ONE option type); below the bar the per-window head plays.
   Replaces binding rules 1–4 and WAIT. Day-zero paired read against the ckpt of record before
   the scorer's training touches acting logits (the ADR-0095 rule).
5. **Critic lookahead (Fork C).** Copy the game, apply one option, evaluate with the critic — a
   ~100× cheaper arm score than 2-turn × K=8 rollouts. Its reliability against rollout spreads is
   the milestone's first read; if adequate it becomes the training-time labeler for most
   windows and the only search a deployment ever does (server-side, gated by pivotality). Two
   critics, named: training-time lookahead uses the FULL-VISIBILITY critic (ADR-0015,
   instrument-only by §7); deployment lookahead can only use the policy's masked value head,
   whose reliability is a SEPARATE read, not implied by Build 0's.
6. **Deployment.** The network alone on a phone; lookahead only where the pivotality read-out
   fires and only where compute exists. The scorer's amortization IS the deployment story.

## Forks (ADJUDICATED 2026-09-05 where marked; leans in bold elsewhere)

- **A. First surfaces — ADJUDICATED.** Priority casts + schedule arms (the funded ceiling), then
  **PAYMENT CLASSES as the second surface of the same head** (ADR-0075 labels as per-option
  spreads; ceiling +2.96pp/game measured; certifier exists). Tutor targets (1.41pp/g, ChoiceDirective
  exists) are routed by name to the next scoping session, after payment has measured the
  per-surface cost of the scorer. Mid-resolution surfaces wait on §J item 10 (stack-entry tokens),
  which lands before any such surface's harvest.
- **B. Representation — ADJUDICATED: SINGLE NETWORK.** The scorer is the policy's action head with
  advantage semantics; one trunk, trainable; PG + spread losses on the same logits. The two-network
  form (frozen executor acting below the bar, a separate trainable-trunk scorer gating it) is
  recorded and rejected: two trunks at serve, and the scorer's trunk would train on the sparse
  spreads alone. Build 1's read is identical under both forms (a scorer fitted on a trainable copy
  of the trunk). Guard: the paired read at day zero when the scorer's training first touches
  acting logits; the executor's strength under the scorer must not move.
- **C. Label target.** **The pinned h2 composite spread for training (reliability measured), the
  critic-lookahead read FIRST as the cheap substitute**; horizon-0 win as the strength truth.
  Adjudicated by Build 0's read.
- **D. Certification weighting.** **Uniform floor (30%) + pivotality-proportional**; the floor
  keeps the head learning about dull windows and keeps a comparable stratum with era zero.
  Pinned at Build 2's launch.
- **E. Reads — ADJUDICATED.** **The STANDARD 2,000-game combined paired read closes the milestone**
  (`scripts/final_read.py` vs 0.5279 ± 0.0110; promote on cleared gate). The fixed-population
  paired read (SE 0.7pp at K=8/N=600) is the mechanism and mid-run instrument, never the closer.
  Surfaces attribute through per-tag reads: the certifier's per-tag spreads + the paired read
  with the mask closed per tag (the amended one-mechanism rule, ADR-0097). Mechanism reads =
  scorer within-window Spearman vs search (bar: > 0.3 at the frozen probe's N, i.e. clearly
  above 0.08 toward the 0.66 ceiling), pivotality AUC (bar ≥ 0.70), certified-label yield per
  rollout. KILL: scorer Spearman not above the frozen probe at equal N after the first
  trainable fit.
- **F. Payment cash-in — ADJUDICATED: folded into Fork A** (the second surface, same head, same
  label format); not a parallel track and not its own head.

## Build order (staged around the cheapest decisive read)

0. **Critic-lookahead reliability read** — Java: apply one presented option on a GameCopier copy
   and snapshot (a one-step `ScheduleDirective` with horizon "after this action"); Python: the
   critic on the resulting state vs the rollout spread, Spearman within window on the harvest's
   806 points. One session; decides Fork C.
   **As built (2026-09-05, user-adjudicated):** the harvest's rolled-out windows replay through the
   `-forceschedule` lane with their own arms at K=8/h2 **and `-forkobs`** (the exclusion lifted;
   `doSchedRollouts` opens fork-store sessions with arm-aware synthetic ids and `"a"` in the fork
   header — recording only, no game-path change; the ADR-0025 jar proof is DEFERRED to the first
   jar that generates a training store, Build 2). Every completion's decision windows are stored,
   so one lane reads several cells: the critic at the first window of turn t+1 (**eot** — the
   cheap labeler's horizon) and at the last window before the h2 stop, from roll 0 alone (K=1)
   and averaged over the 8 rolls, for the full-vis critic of record AND the policy's masked value
   head (the deployment critic; a separate read, ADR-0097); plus the cost-matched comparators
   (one rollout's composite vs the other seven; the label's own split-half on the same sample).
   Score per arm = mean over rolls of V(arm) − V(natural), paired by roll seed. Script:
   `scripts/critic_lookahead_read.py`.
   **PRE-REGISTERED bars** on the headline cell (full-vis / eot / K=1 vs the 8-roll composite;
   mean within-window Spearman, windows with ≥ 3 scored arms): **≥ 0.40 ADOPT** (critic
   lookahead labels most windows; rollouts certify the pivotality-aimed stratum only);
   **0.20–0.40 HYBRID** (critic aims and pre-filters; rollouts stay the label of record);
   **< 0.20 RETIRE** (rollouts only; lookahead survives as a deployment-gate question). Reference
   points: label reliability 0.66 at K=8 (observable ceiling ≈ 0.8), the label's split-half 0.50,
   the frozen-trunk scorer probe 0.08. Scale: a 200-window uniform subset (seed 20260905) read hot,
   the full 806 overnight decides.
1. **Option-content encoding + scorer head on a trainable trunk**, fitted on mint + harvest
   spreads (3,475 windows, ~45K option scores); read = Spearman/AUC vs the frozen probe at equal
   N and the learning curve. The first build read; the KILL lives here.
2. **Certifier by tag + pivotality-aimed sampling** (server: weight function; Java: SELECT-ONE
   arms for tagged windows; the void-arm legality pre-filter); harvest 2 under advisory
   generation with the scorer aiming. **2b. The payment surface**: `mtg.pay_mana_class` options
   scored by the same head, ADR-0075 labels joined as spreads (`payment_certify.py` as the
   certifier for that tag); read = per-tag Spearman + the payment evalset (repaired first,
   ADR-0082).
3. **Scorer acting at serve** (scores as action logits; margin gate for plan-type options — the
   mask machinery exists) + the day-zero paired read against the ckpt of record.
4. **The long run**: labels accrue inside generation; PG + spread losses on one network per
   era, the mint as the era-zero anchor; paired read at day zero, mid-point, terminal; closed
   by the standard 2,000-game read.

## Done-when

1. Build 0 read recorded (critic-lookahead Spearman vs rollout spreads on the harvest's 806
   points); Fork C adjudicated on it.
2. Build 1 clears the KILL: trainable-trunk scorer Spearman > 0.3 at the frozen probe's N, with a
   rising learning curve; pivotality AUC ≥ 0.70.
3. The certifier by tag runs inline with pivotality-aimed sampling; per-option spreads ride the
   store row for BOTH surfaces (schedule/cast, payment class).
4. The scorer acts (argmax/sampled on single-option windows, margin-gated on plan options) with
   the day-zero paired read passed against the ckpt of record.
5. One promotion-scale run closed by the standard 2,000-game read vs 0.5279 ± 0.0110 — or early
   by its pre-registered kill with an ADR; per-tag attribution reads alongside.
6. The closeout ADR routes the queue by name (tutor targets, stack-entry tokens, trigger order /
   combat damage, §3b stops, mull tuck, deployment lookahead on the masked value head).

## Inherited obligations and hazards

- Information-set principle (§J): choices within abilities are decided when the engine presents
  the legal options; the scorer only ever sees presented options.
- §J item 10 (stack-entry tokens) before any mid-resolution or trigger-response surface's
  HARVEST: abilities on the stack reach the model only as a count today. Routed by name at
  ADR-0097 — neither M11 surface needs it.
- Sampled-mainline replay parity is bounded by serving jitter (~20% of games): reads pair
  within-run (CRN) and budget cross-run divergence.
- Void arms (step-0 veto) are 32% of certifier rollout time: a Java legality pre-filter before
  harvest 2.
- Engine changes = boundary events unless ADR-0025-proven (forkcheck vs the 08-21 run: 498/500).

## Out of scope / retired / routed by name

Retired (ADR-0096): the generative pointer-decoder planner, blanket binding and the WAIT
machinery, planner PG/KL, the follow term. Deployment-time tree search on device. Routed by name
(ADR-0097): tutor targets (next scoping, vs 1.41pp/g); stack-entry tokens (§J-10, before the
first mid-resolution surface); trigger ordering / combat damage (certifier-by-tag measures and
labels them when bridged); §3b learnable stops; mulligan tuck at serve (first `TAG_TASK` touch);
deployment lookahead on the masked value head (funded by the network-alone vs server-lookahead
gap at close). Closed: the payment cousins / costmod / pool-tie (ADR-0083).
