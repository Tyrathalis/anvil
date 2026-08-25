# M10 planning/scheduling ceiling measurement — pre-registration spec

*Status: DRAFT FOR ADJUDICATION (2026-08-25 design session). Structure
follows the fork map ([m10-plan.md](m10-plan.md)) with user leanings
applied; the named knobs (§Adjudication) need user sign-off, and exact
thresholds marked "at launch" are pinned in the launch commit PRE-DATA
(the R1/ratesweep discipline). Anchors:
[ADR-0073](../decisions/ADR-0073-m9-ceiling-measurement.md) (the genre),
[ADR-0075](../decisions/ADR-0075-window-rate-sweep.md) (the two-stage
pattern this mirrors), [ADR-0053](../decisions/ADR-0053-sequence-probe-resolution.md)
(forced-directive machinery + the existing headroom evidence),
`data/runs/schedule-census-m10` (terrain, 2026-08-25).*

## Question

What is optimal within-turn resource scheduling worth — sequencing +
directed payment, measured JOINTLY per the charter — relative to the
ckpt-of-record's natural play? Both claims per the standing rule:
per-window (per consequential turn) and gate-scale (per game).

## Why two-stage (the power argument, recorded)

Direct uniform best-vs-natural: eligible turns fire ~7.1/game, so
gate-scale = per-turn mean × 7.1 — at feasible N (≤1,000 turns) the
per-turn SE (~0.5–1.1pp even with paired rollSeeds) amplifies to
±4–8pp/game. Rejected. The ADR-0075 shape instead: (1) a horizon-2
certification sweep prices the RATE of schedule-consequential turns on
a uniform sample; (2) game-end conversion runs only on certified
positives, where per-window effects are large (payment: +9.2pp at
n=19, z=2.16). Gate-scale = rate × conversion, three-row bracket.

## Instrument

### Population & sampling

- **Fresh 500-game census** from `d6-run11/iter-019` on the bundle jar
  `2f87180cdf` (engine `23c3d2a85d`), NEW seed base (pinned at launch,
  2052xxxx block), paygoals2 deck-pair convention, obs sv=2 +
  paytelemetry + census on. Not gate-seeded (fresh seeds; the ADR-0068
  rule checked). The veto-elevated run18/19/20 stores are not touched.
- `schedule_census.py` tags every own-turn turn-group; **eligible** =
  own-turn AND afford_now ≥ 2 (census conventions as committed).
  Rate denominator: eligible-turns/game measured on THIS census
  (rebaselinearm reference: 7.08/g).
- **Uniform sample of 600 eligible turn-groups** (rng pinned at
  launch). Marginal-stratum subset: 200 of the 600 (same rng).

### Arms (per sampled turn)

- **NATURAL**: no directive, K rolls (the policy as deployed — its K
  sampled rolls double as the free best-of-K policy-slack read).
- **Directed schedule arms, cap 16**: ordered subsets of the eligible
  affordable-action set (the emitted-schedule vocabulary — pointer over
  the emission window's candidates; co-design pin, fork 9).
  - n ≤ 3: full enumeration (≤16 ordered subsets incl. the empty
    hold-all schedule).
  - n ≥ 4: 6 canonical + seeded-random ordered subsets to the cap.
    Canonical set (knob b): hold-all; greedy-max-spend (largest total
    cmc, cost-desc order); ramp-first (mana-producers first, then
    greedy); curve-ascending; curve-descending; hold-interaction
    (exclude instant-speed candidates, greedy over the rest).
- **Payment mode — JOINT primary (fork-2 user leaning):** each
  directed arm executes **schedule-consistent directed payment** —
  at each payment window the executor picks the enumerated plan that
  maximizes feasibility of the arm's REMAINING scheduled actions,
  tie-broken most-flexible-spare. Deterministic given the schedule ⇒
  no arm blowup. **Marginal stratum:** the same directed arms re-run
  under auto-pay on the 200-turn subset (attribution vs the measured
  payment leg + the super-additivity read).
- **Rolls:** K = 8 per arm, rollSeeds paired across arms per
  (turn, roll) — the ADR-0073 same-determinization pattern.

### Divergence policy (fork-5 pin)

Forced action illegal at its window ⇒ **degrade to auto for the
remainder, count** (`degraded_steps`, `degraded_at`). Arm VOID if zero
scheduled actions execute. Divergence rate is a first-class free
instrument (schedule × payment entanglement). Refire/thin-pair/
unended-roll guards per the certify standard.

### Stage 1 — certification (horizon 2)

`HorizonStop` at t+2. **Select/score split at birth (winner's-curse
rule, ADR-0073): directed-best selected on rolls 0–3, scored on rolls
4–7.** A turn is POSITIVE if the selected arm's scored h2 composite
(payment_certify axes, reused) beats NATURAL's by margin ≥ θ (θ pinned
at launch after the instrument smoke; structure pinned here). The
certification horizon is part of the claim's type (ADR-0072).

### Stage 1b — horizon-sensitivity side-sample (added 2026-08-25, the
h2-bias mitigation)

ADR-0053 measured deferral value COMPOUNDING with horizon (−2.6pp at
N=2 → −6.1pp at N=4), so an h2 certifier is structurally biased
against hold-shaped schedules — the interaction-mana class. Mitigation:
**100 of the 600 sampled turns (same rng) are additionally certified at
horizon 4.** Read: certification-rate and margin deltas h2→h4, split
by arm shape (hold-bearing vs not). If h4 certifies materially more
(threshold pinned at launch), the rate carries an h4-informed
correction band and the conversion population is revisited at the read
session before the verdict closes. ~7% budget add.

### Stage 2 — conversion (game end)

Positives re-run to natural game end, same job ids and seeds — the
rollSeed-identity both-horizon trick (stage-1 rows ARE the h2 arm at
half cost). **Primary read: paired Δwr = win(selected arm, scoring
rolls) − win(natural), clustered by game.** h2-proxy validity re-read
(Spearman margin vs win-diff — the payment precedent numbers: +0.36
to +0.47).

### Gate-scale arithmetic

rate (Wilson CI, stage 1) × conversion (stage 2) — three-row bracket
(lower/central/direct), both-claims statement, vs the ±1.1pp floor.

### Secondary / exploratory reads (never gating)

- Best-of-natural-K vs mean-of-natural-K: the reachable-ceiling /
  policy-distribution-slack indicator (fork-1 secondary, free).
- Strata: resource-bound vs not; chained-present; n-bucket;
  joint vs auto-pay marginal (super-additivity).
- Binned-gain curve by pre-turn critic score (the LordOfThePigs
  instrument prototype).
- Best-arm schedule shapes (ramp-first? holds?) — seed supervision
  material for the v2 decoder (fork 9 dividend).

## Funding thresholds (knob d — drafted for adjudication, pinned pre-data)

- **Joint ceiling point ≥ 2.2pp/game (2× floor) AND rate-CI-lower ×
  conversion ≥ 1.1pp ⇒ the charter's promotion run is FUNDED** as
  measured.
- Point in [1.1, 2.2) or CI straddling the floor ⇒ **session
  adjudicates** (mechanism-speed evidence, ADR-0076, may still fund).
- Point < 1.1pp/game ⇒ **charter re-opens**: the §3b ranking and the
  substrate corollary get re-argued on mechanism grounds, not ceiling
  grounds, at a named session.
- The super-additivity and marginal-attribution reads inform routing
  but never gate (small-n strata).

## Budget (knob e — user overbudget direction on record)

~(600 + 200) × 17 arms × 8 rolls ≈ 109k horizon-2 rollouts (short:
~2–3 turns each) + stage-2 game-end re-runs on positives + 600×8
natural rolls. Reference: the payment h2 sweep ran 600 windows × ~4
arms × 8 in one evening on 4 lanes; this is ~5–6× that ⇒ **2–3 nights
on 8 lanes, nice'd; quiet-box rule for stage 2** (the calibrated
read). Early-cancel per the user pin: clear null + suspected
implementation error only.

## Engine build owed (the one Java delta)

`-forceschedule` directive on the instrumented jar: ordered SA list +
schedule-consistent payment selection + degrade-and-count semantics +
directive trace validation. Smoke gate before the sweep: 3 turns
replayed end-to-end, directive traces validated, margins reproduced
across a re-run (the ADR-0073 smoke precedent). Census/instrument
code only — not the game path, no boundary implications; the research
fork proper carries zero delta.

## Explicitly out

- Off-turn schedule arms (reactive holds): their value is captured in
  game-end outcomes of own-turn hold arms; directive design for
  forced reactions is its own genre. Recorded, not lost — re-enters
  with the resolution-effect-payment probe if that family funds.
- Policy-resample serving arms beyond the free best-of-K read.
- Horizons beyond the turn for the directive (N-turn persistent
  schedules — v2 recurrence territory).

## Adjudication knobs (user sign-off before the launch commit)

a. Two-stage shape (h2 certification → game-end conversion) vs
   direct single-stage — the power argument above.
b. The canonical arm list (six named above).
c. Schedule-consistent directed payment as the joint executor rule
   (deterministic, no arm blowup).
d. Funding threshold numbers (2×-floor structure above).
e. Budget scale (~109k h2 rollouts; 2–3 nights).
