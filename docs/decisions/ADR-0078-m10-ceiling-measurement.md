# ADR-0078: M10 planning-ceiling measurement — FUNDED (+13.5pp/game central, 6× the threshold)

- **Status:** accepted (measurement complete 2026-08-26; verdict mechanical
  from the pre-registered thresholds)
- **Date:** 2026-08-26
- **Spec:** [m10-ceiling-spec.md](../design/m10-ceiling-spec.md)
  (ADJUDICATED 2026-08-25, all five knobs; launch pins in
  `scripts/sched_pins.py`, committed pre-data)

## Question

What is optimal within-turn resource scheduling worth — sequencing +
schedule-consistent payment, JOINTLY per the unified-competency charter —
relative to `d6-run11/iter-019`'s natural play?

## How it was measured (all pinned before data)

Two-stage ADR-0075 mirror on a fresh 500-game census (seed base
20520825, paygoals2 pairs, obs sv=2 + paytelemetry + census, jar parity
vs the `2f87180cdf` bundle commit proven empirically 19/20
byte-identical): (1) h2 certification over a pinned uniform sample of
600 eligible turn-groups (≤16 directed arms + natural, K=8 paired
rollSeeds keyed on target turn, select rolls 0–3 / score rolls 4–7,
θ=2.0 on the pinned certify-descended composite, 0.75 consistency);
(2) game-end conversion on the positives (selected arm + natural,
horizon 0, same rollSeeds), paired Δwr over scoring rolls with the
unended-roll guard, game-clustered bootstrap CI. Reads pre-registered
before their data existed (`schedule_read.py`, commits `0a0595a` /
`b8f11f3`).

## Results

- **Stage 1:** 583/600 planned turns read (16 = fork never fired,
  mainline ended pre-target; zero drift/skip rows). **170 certified —
  rate 29.16% [25.62, 32.98]** ⇒ **2.38 certified turns/game** at the
  census's 8.17 eligible/game (payment precedent: 0.321/game).
- **Stage 1b (h4 side-sample, 94 shared turns read):** h2 30 vs h4 33
  certified — ratio 1.10 < the pinned 1.25 ⇒ **flag does NOT fire**;
  the h2 rate carries uncorrected (the ADR-0053 hold-bias concern was
  armed and did not materialize at threshold; hold-shaped selections
  1→3, small-n).
- **Stage 2:** 170/170 turns read (2 unended pairs dropped).
  **Conversion Δwr = +5.69pp per certified turn [+2.05, +9.56]**.
- **Gate-scale bracket (pp/game):** lower **4.28** / central **13.54**
  / upper **25.75**; floor row (rate-CI-lower × conversion) **11.90**.
- **Pinned thresholds:** point ≥ 2.2 AND floor row ≥ 1.1 ⇒ **FUNDED.**
  The central is ~6× the funded threshold; the bracket's lower row
  alone is ~2× it. **The charter's promotion run is funded as measured.**

## Caveats (recorded, none gate)

- **h2-proxy validity is WEAK: Spearman(h2 margin, Δwr) = 0.109**
  (payment precedent 0.36–0.47). The certification gate finds turns
  whose best schedule converts (+5.7pp measured directly at game end),
  but the h2 MARGIN barely rank-orders game-end value within positives —
  the instrument is a good detector and a poor ranker. Selection/label
  work in the M10 build should not treat h2 margins as fine-grained
  value; the certified/not bit plus game-end outcomes are the trustable
  signal.
- **Divergence is pervasive:** ~50% of selected-arm rolls degraded
  mid-schedule (2,311/4,664 — the fork-5 instrument). The measured
  ceiling therefore already INCLUDES degrade-to-natural behavior on
  half the executions — if anything a downward bias on perfect-play
  value, and direct evidence that schedule×payment entanglement is the
  real terrain (the unified-competency framing's own premise).
- Frame loss 2.7% (16 fork-never-fired turns); a missed-point row is a
  cheap instrument improvement for the next sweep genre.
- Mainline draw-clock winners are fabricated (both-win wart, watch
  list); sched rows extract unique winners and the read guards on
  `ended` — the verdict path is clean.

## Consequences

- **The M10 build proceeds on the funded candidate**: v2
  schedule-bearing plan target + re-advertised payment actuation +
  supervised conditional labels, trained and read as one competency.
  The §3b learnable-stops alternative stays shelved on ceiling grounds.
- The 170 positives + 5,076-window payment universe are the seed
  supervision material; best-arm schedule shapes ride in the sweep rows
  (fork-9 dividend, unread — exploratory reads owed at the design
  session, never gating).
- Engine assets born and proven trace-invisible en route: the
  `-forceschedule` soft-emission executor + schedule-consistent payment
  scorer, the sched-rollout mode with target-turn-keyed rollSeeds, the
  watchdog remove-on-cancel fix, and **the AiCache leak fix** (see the
  standing rule below).

## Standing rule born

**Bridged JVMs leak one game graph per game unless AiCache is cleared
between games — chunk recycling is load-bearing; never run a bridged
JVM unbounded without one or the other.** (Upstream `AiCache.dataMap`
is cleared only in `AiController.chooseSpellAbilityToPlay`, a path
bridged seats never take; heap-dump BFS proof 144/146 retained Games.
Fork fix `7716bbe44d` clears between completions/games — within-game
behavior untouched for census parity; a within-game clear at bridged
windows is a BOUNDARY-EVENT candidate for the next bundle, and the
identity-keyed staleness it would fix is a recorded era property.
Upstream candidate queued: game-scoped/bounded AiCache.)
