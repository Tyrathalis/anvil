# M11-routing ceiling probes — tutor/fetch targets + resolution-effect payments (RESOLVED 2026-08-27: BOTH RE-DEFER — [ADR-0080](../decisions/ADR-0080-m11-routing-probes.md); T 1.41pp/g, P 0.69pp/g vs the 2.2 bar; P's decline-cost 2.5pp/window already captured by the heuristic)

*Design-round obligation 6 ([m10-plan.md](m10-plan.md)), funded by name
at the 2026-08-25 scoping discussion: two session-scale ceiling
measurements riding the M10 design round, ROUTING M11, never gating
M10's build. The ADR-0073 measure-the-ceiling genre on the ADR-0053
forced-branch machinery; both claims per the standing rule (per-window
value AND gate-scale = rate × per-window). The effect-payment probe IS
the measured argument ADR-0077 requires before that item can be
re-deferred a second time.*

## Shared discipline (both probes)

- **Population: uniform over mined windows** (the ADR-0075 lesson —
  mining defines the surface, never value-filters it; any
  value-selected stratum is exploratory and winner's-curse-priced).
- **Store: `m10-ceiling-census-20260825-212414`** (era iter-019,
  boundary bundle) for the mining census; rollout populations
  re-derived at the same seeds. Rebaselinearm stores as the fallback
  volume source if window rates are too thin (recorded either way).
- **Rolls: K=8 with the structural select/score split** (select on
  rolls 0–3, score on 4–7 — the sched_pins precedent; best-arm
  ceilings inflate without it).
- **Read: per-window paired Δwr at game end** (forced-best vs natural
  reference), clustered by game; gate-scale = measured window rate ×
  per-window delta. Divergence/void caps pre-registered per arm
  (exhaustion precedent).
- **Routing rule (pinned pre-data at each probe's launch):** gate-scale
  ceiling ≥ the M10 funding threshold (the ADR-0078 pinned ~2.25pp/game
  scale) ⇒ the item schedules into M11 scoping by name; below ⇒
  re-deferred WITH the number attached (ADR-0077's condition
  satisfied either way).
- **Mining rung first, forcing rung second:** each probe opens with a
  CPU-only store census (window rate, candidate-set sizes, seat/turn
  distribution) — the rate half of the gate-scale claim and the
  arm-budget input — before any engine work runs.

## Probe T — tutor/fetch-target ceiling (§3d′ family 2)

- **Window definition:** own-seat `chooseSingleEntityForEffect` AND
  `chooseSingleCardForZoneChange` decisions (SELECT_ONE shape) whose
  candidate set is a library/multi-zone search (tutor/fetch class),
  candidate count ≥ 2. Multi-entity search variants
  (`chooseEntitiesForEffect` 0.70/g, `chooseCardsForEffect` 0.43/g)
  counted in the census, forced only if their rate is material
  (recorded fork).
- **Measured raw rates (census.jsonl sweep, 500 games, 2026-08-26):**
  `chooseSingleEntityForEffect` 5.87/g, `chooseSingleCardForZoneChange`
  5.79/g — before the library-search/candidate-count filter, which the
  mining rung applies. The class is 20–50× the M9 payment window rate
  pre-filter; the surface is live at census resolution.
- **Arms:** force each distinct candidate target, capped at the top-k
  by a cheap static order (k pinned at launch from the census
  candidate-size distribution; full enumeration when ≤ k) + the
  natural arm (the AI's unforced pick) as the paired reference.
- **Read:** best-forced vs natural Δwr per window (select/score
  split); heuristic-regret = natural vs best among forced arms.
- **Engine delta owed:** `-forcechoice` — force a designated
  SELECT_ONE outcome at a (seed, turn, window-ordinal) key; the third
  member of the `-forcebranch`/`-forceschedule` family, same
  labels-JSONL output contract.

## Probe P — resolution-effect payments ceiling

- **Window definition:** `payManaCost` windows with `effect=true`
  (resolution-time pay-or-suffer; the census stream carries the flag).
  **Measured: 50.12/g raw (25,061 events / 500 games, census.jsonl
  sweep 2026-08-26)** — the plan's ~54/g confirmed in the fresh era.
  The mining rung splits this into the pay-or-suffer subset (decline
  legal) vs mandatory payments; only the former is forced.
- **Arms:** force-PAY vs force-DECLINE at each mined window (binary in
  the pay-or-suffer class; windows with a payment-choice interior are
  counted in the census and routed to the directed-payment machinery
  only if their rate is material — recorded fork). Natural choice
  recorded ⇒ regret read (value lost by the AI's actual pay/decline
  policy) rides free.
- **Read:** pay−decline Δwr per window + natural-choice regret;
  gate-scale by the re-measured rate.
- **Engine delta owed:** force pay/decline at effect-payment windows —
  a knob on the existing payment executor path (float-then-apply
  machinery already brackets the window; the force is a decision
  override, not a new payment path). **Plus (mining-rung finding): the
  census payManaCost emission must first gain isCancellable + source
  name + effect class — without it the forcing universe is
  undefined.**

## Explicitly out

- Any training wiring for either surface (routing probes only).
- Value-model-guided target selection for tutors (that is the M11
  build question these numbers fund or kill).
- Effect payments with nontrivial payment interiors beyond the
  census count (recorded, not forced, this round).

## Mining-rung results (RUN 2026-08-26, `scripts/m11_mining.py` committed
## pre-run at `9a1e2de` → `data/runs/m11-mining/`)

Rate convention: per SEAT-game (/1000 — the gate-scale denominator at
eval); the census is 500 self-play games, both seats the model.

- **Probe T — the surface is live and the probe is genuinely open:**
  `tutor_fetch` (Search-your-library class, ZoneChange only) 0.784
  /seat-game, 744 forceable (ncand ≥ 2), 92.3% isOptional
  (fetchland-dominated; candidate counts spread to 10+ — the k pin
  should consider name-dedup compression for fetches). `dig`
  (Look-at-the-top class, SingleEntity only) 0.336/seat-game, ~all
  forceable, candidates mostly 2–5. **In-family forceable traffic
  ≈ 1.08/seat-game — 3.4× the M9 payment window rate**; clearing the
  pinned 2.25pp/game routing bar therefore needs ≈ +2pp per window,
  which is exactly the forcing rung's question. The `other` stratum
  (targeting/untap/equip, 4.7/seat-game) is out of family and stays
  out. Multi-entity variants stay counted-only (566 events total).
- **Probe P — the decline-legal split is TELEMETRY-BLOCKED:** of
  25.06 effect-true windows/seat-game, only `text_optional` 0.36
  /seat-game is knowably decline-legal from the current fields;
  `empty_sa` 18.64 (clustered MAIN1 7,481 / CLEANUP 4,420) and
  `phase_sa` 4.41 (`[Phase: player]` marker rows) cannot be
  classified — `prompt` is always null and there is no
  isCancellable/source field. **The engine-delta session therefore
  gains a THIRD item: extend the census payManaCost emission with
  isCancellable + source name + effect class** — the P forcing
  universe cannot be defined before that lands, and the true
  decline-legal rate sits anywhere in [0.36, 25.1]/seat-game. The
  plan's ~54/g raw figure was never the pay-or-suffer rate.

## Engine deltas — BUILT 2026-08-26 (fork `07c28fcf8a`), one touch, three deltas

- **`-forcechoice <tsv>`** — `ChoiceDirective` (the ScheduleDirective
  WeakHashMap idiom) + an AnvilRun choice-rollout mode (NATURAL + arms
  × K, target-turn-keyed paired rollSeeds, `ev:choice` labels rows
  with directive trace + certify snapshot). Choicefile TSV:
  `g \t turn \t seat \t horizon \t armId \t tutor|prevent \t action`.
  **First-match semantics** at the target seat's first family window
  of the target turn (family regex = the mining classifier VERBATIM —
  the forced universe equals the mined universe by construction);
  multi-window turns counted by `windowsSeen`. Forcing is BY INDEX
  into the live candidate list (candidate identities recorded in the
  row via `chosen`); index-out-of-bounds = fired-with-miss `idx_oob`,
  natural continue.
- **Pay/decline override** — `forcePrevent` at `payCostToPreventEffect`
  bypasses `willPayUnlessCost` (force-pay = `canPayCost` +
  `CostPayment.payComputerCosts`, the PlayerControllerAi path
  verbatim; unaffordable = fired-with-miss `pay_unaffordable`);
  decline returns false unpaid.
- **Census telemetry extension** — `src` (host card) + `api` on
  `payManaCost` thin rows and `payCostToPreventEffect` records (the
  attribution gap closed); generated controller regenerated via a new
  `FORCE_OVERRIDES` emission (only the three methods changed).
- **Fork point / coverage (recorded cap):** the existing quiescent
  own-MAIN1 fork trigger — windows on turns where the seat never
  holds a MAIN1 window (~11–16% by phase distribution) are OUT of
  coverage, loudly counted by skip rows + `fired:false`. Window
  recurrence post-fork is stochastic per roll; `fired:false` rows are
  the coverage instrument, void caps priced at launch.
- **ADR-0025 proof (behavior-identical on the game path):** sched
  mechanical smoke rerun on the new jar = mined schedfile IDENTICAL +
  72/72 labels rows identical modulo ms vs the banked era-jar smoke;
  census stream identical for all shared games except the declared
  classes (1,200 src/api enrichments incl. 9 `d` stack-frame bumps
  from the helper frame, 8 end-row ms fields). Zero unexpected diffs.
- **`-forcechoice` mechanical smoke PASSED** (`scripts/choice_smoke.py`,
  the schedule_smoke genre): index forcing picks distinct candidates
  at the same window (arm 1 → Agatha's Soul Cauldron, arm 2 → Arcane
  Signet), idx_oob miss, pay/decline both fire, rollSeed pairing,
  natural-arm purity, re-run byte-determinism.

## Launch pins (drafted 2026-08-26 for adjudication; executable single
## source = `scripts/choice_pins.py`, this section is the prose mirror)

- **Universes (measured, active-player-forkable):** probe T = 928
  events / **796 distinct (g, t, seat) points** (86% of the 1,078
  mined events — the active-player proxy: the seat holding the FIRST
  MAIN1 cast window of the turn); probe P = 1,415 events / **1,333
  points** (85% of 1,656). Uncovered ~15% (off-turn / pre-MAIN1
  windows) is the recorded coverage cap.
- **Arms:** T = natural + candidate indices 0..min(ncand, 6)−1 (mean
  5.0 forced arms; index order = the engine's deterministic candidate
  list; the DC pool is singleton, so duplicate-name arms are a
  non-issue — recorded). P = natural + force-pay + force-decline.
- **Rolls: K = 8**, target-turn-keyed paired rollSeeds (built-in).
  **Select/score split** (rolls 0–3 select, 4–7 score) for every
  best-of claim (T best-arm; P best-of-pay/decline); each-arm-vs-
  natural pooled over all 8 rolls = the unbiased secondary.
- **Fired-pairing rule:** a forced arm's roll pairs against the
  natural arm's same-roll outcome ONLY when the directive fired that
  roll; a point enters the per-window read at ≥2 fired scoring rolls,
  else it moves to the coverage denominator. Fired rates are
  first-class coverage numbers.
- **Reads (pre-registered, `scripts/choice_read.py` committed
  pre-data):** primary per probe = paired best-forced vs natural Δwr,
  clustered by game; P secondary = pay−decline delta distribution +
  natural-agreement rate; T secondary = heuristic-regret (natural vs
  best) and per-index deltas. Gate-scale = FULL mined per-seat-game
  rate (T 1.08, P 1.66) × per-window Δ — the covered-stratum
  measurement extrapolated to the uncovered ~15% is a recorded
  assumption, reported alongside a coverage-discounted row.
- **Routing arithmetic (the ADR-0078 scale, adjudicated):**
  gate-scale point ≥ **2.2pp/game** ⇒ SCHEDULE into M11 (CI-lower ≥
  1.1 strengthens the routing); below ⇒ re-defer with the number.
- **Horizon: game end (h = 0)** — the routing read is win-rate-based;
  no proxy stage.
- **Population/replay:** the m10-ceiling-census configuration
  verbatim (pairs paygoals2, gpp 5, seed base 20520825, obs/census/
  paytelemetry flags, grpc bridge + model server) — the mined windows
  replay deterministically to the fork point; lanes split by game,
  quiet-box, 12 lanes (stage-2 precedent). Enriched-jar census output
  = the src catalog, free.
- **Power note (recorded pre-data):** with the split, per-window SE ≈
  0.354/√N_used; T exhaustive at ~60% fired-usable ⇒ SE ≈ 1.6pp on a
  ~2.0pp decision threshold — a wide-CI verdict is possible and
  acceptable for a routing read (the number gets attached either
  way); the pooled secondary is ~√2 tighter.
- **Budget — ADJUDICATED (user, 2026-08-26): EXHAUSTIVE, pause/resume
  first-class.** One combined plan (T + P arms share a point's natural
  rolls on (g, t, seat) collisions); ~70k game-end completions total.
  A 34h unbroken quiet-box stretch is NOT assumed: lanes run
  `nice -19` and are killable at any moment —
  `choice_plan.py resume` drops COMPLETE points from the lane TSVs,
  rotates the out files (the reader globs `out*.jsonl` generations),
  and a rerun reproduces identical rolls because rollSeeds are
  point-keyed (`seed ^ turn ^ roll`), never sequence-dependent.
  Nights-and-idle scheduling covers the bill in chunks.
- **Load/health guard (the quiet-box concern, pinned):** the wr read's
  load exposure is timeout-bias (a loaded box trips rollout watchdogs
  ⇒ forced draws). The paired design absorbs symmetric losses; the
  read reports crash + unended (timeout/draw-clock class) rates per
  arm side and FLAGS natural-vs-forced asymmetry >2× — a flagged read
  is discuss-zone, not silently routed.
- **Adjudication (user, 2026-08-26):** exhaustive scale confirmed;
  LAUNCH approved (server up, lane smoke, 12 lanes armed under the
  detached-run checklist + babysit wakeups).

## Adjudication record (user, 2026-08-26 — all four on the recorded leans)

1. **Probe T windows: both SELECT_ONE classes**
   (`chooseSingleEntityForEffect` + `chooseSingleCardForZoneChange`),
   library/multi-zone-search filtered, ≥2 candidates; multi-entity
   variants census-counted, forced only if material.
2. **Probe P forcing scope: decline-legal windows only** (pay-or-suffer
   proper); mandatory payments census-counted for context.
3. **Routing threshold PINNED: gate-scale ceiling ≥ the ADR-0078
   funding-threshold scale (≈2.25pp/game)** ⇒ schedule into M11;
   below ⇒ re-defer with the number (ADR-0077's condition satisfied
   either way). Restated numerically in each probe's pins module at
   launch.
4. **Engine-delta sequencing: after the v2 target probe read** — one
   Java session builds `-forcechoice` + the pay/decline override
   together (one fork touch); the CPU mining rungs run in between.
