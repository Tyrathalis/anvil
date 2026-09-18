# ADR-0112: M12 Build 4 — the allocation head served (fork D's gate as an `anvil.alloc` ask, fork L's first output), and the post-Build-4 read pre-registered

- **Date:** 2026-09-17
- **Status:** accepted
- **Design-doc anchor:** §3d′ (the search directive's gate) / §6 (the loop); m12-plan forks D and L; ADR-0109 item 2

## Context

ADR-0109 named the allocation head as the largest throughput lever we own: the search acts on
≈ 9% of windows at rate 1 and every window pays full price. Its first fit (09-16, the frozen e3
trunk on 52,697 pre-merge windows) read AUC 0.80 at margin ≥ 0.10 and captured 90% of the acts at
67% of the search's forward calls. Nothing was served: no head in the model, no wire, no rule in
the engine. The re-warm line closed 09-17 07:00 (ADR-0111) with `m12-build4-e1` as the day-zero
build, so the head lands on that build's trunk.

Three design questions were open at the session's start (user: proceed on the recommendations):

1. **Where the head's probability enters the engine.** ADR-0109 drafted it as an extra output on
   the priority response ("no extra calls"). The searched window's rate draw fires BEFORE the
   mainline's priority ask (`AnvilRun.SearchMonitor.onPriority`: the search runs, then the
   controller's own ask completes the row with the natural pick), so that route needs the search
   moved inside the controller's ask. The dedicated ask costs one forward call per candidate
   window against ≈ 3,700 copy calls per game (≈ 2%), needs no proto change, mirrors
   `anvil.value` and the M10 `anvil.certify` ask (a server-side allocation at a fork point is
   already an ask on this wire), and its answer can later carry a shape id (fork L).
2. **The allocation rule.** Threshold + floor (the probe's own arithmetic) vs a rate
   proportional to p.
3. **How the head is trained now.** A standalone frozen-trunk fit with a fit record (the
   pay-gate pattern) vs waiting for the loop-native term.

A fourth fact surfaced in the review: **the loop does not run the search yet.** The harness
accepts verbatim engine flags (`forge_args`) and the search row records the acting rule's
log-probability, but `selfplay.py` passes no search flags and `rl.py` has no term for search rows
or the search's behavior distribution. The shakedown assumes both (Build 4½ "the same loop
settings"). It is Build 4½ pre-work and is routed below by name.

## Decision

1. **The ask: `anvil.alloc` on the value wire** (fork `a37bc6a8b4` on `d734937c56`; `AnvilRun`
   only). After the `-searchrate` draw at a candidate window, with `-searchalloc <tau>` set, the
   monitor scans the options once (handed to `doSearch`, so a searched window scans no second
   time), builds the window's `Obs.peekPriority` record (the leaf value's own shape, with the
   session's history ring) under an RNG snapshot, and asks the head for P(the search would act
   here: margin ≥ the acting bar). The window is searched where **p ≥ tau**, or on a **seeded
   uniform-floor draw** at `-searchfloor` (default 0.1; a private stream keyed on the game seed
   and the window ordinal, so the labels keep coming from ungated windows — the §3d
   self-sealing hazard), or where the ask is **unserved** (NaN: the uniform rate, as before).
   Skipped windows leave an `ev: alloc` row (p, `by: skip`); searched rows carry
   `alloc: {p, by, ms}`; the census row `searchAlloc` counts by / n_opts; the game header pins
   `alloc` and `floor`. **Off (NaN) = byte-identical** — no ask, no scan; the forkcheck proves it
   (queued as the chain's first stage).
2. **The head: `alloc_head`, Linear(d_model, 1) on the `[STATE]` read-out** the value head uses
   (Anvil `6d12084`): zero weights, bias at the era's base rate (logit −2.29 ≈ 9.2%), the `alloc_`
   compat prefix (every older checkpoint loads; the head sits at the base rate). Outputs `alloc`
   (the logit in the training dict, the probability at serve). **The server serves the tag only
   from a checkpoint carrying an `alloc_fit` record** (the fit-record rule, ADR-0105); without
   one it declines and the worker searches at its uniform rate (`by: unserved`).
3. **The first fit = the frozen-trunk logistic folded into the head** (`scripts/alloc_fit.py
   fit`): the e1 trunk's `[STATE]` on the era's search rows — the target label pool
   `b4-tgtlab` (1,000 games under the recipe, e3 serving; **69,380 windows joined 100%**, 6,007
   positives at bar 0.10 = 8.7%) — five game-grouped folds for the honest numbers, the full fit
   written into `alloc_head` with standardization folded back into raw weights, the record in
   `config.alloc_fit`. **AUC 0.800 ± 0.012 out of fold (0.830 in sample)**, state alone (the
   probe's scalars added 0.02; the in-model head reads the state only). The tau table (in-sample
   recall → out-of-fold recall / cost share / windows share / games multiplier, floor 0.1):

   | recall pin | tau | OOF recall | cost share | windows searched | × games |
   |---|---|---|---|---|---|
   | 0.80 | 0.489 | 0.77 | 0.52 | 0.40 | 1.91 |
   | **0.90** | **0.369** | **0.87** | **0.62** | **0.51** | **1.60** |
   | 0.95 | 0.276 | 0.93 | 0.71 | 0.60 | 1.42 |

   **The pin: tau 0.369 (the 90% row), floor 0.1** — the first arm's setting; the shakedown's
   settings pass owns it. The served build = `data/training/m12-build4-e1a/last.pt` (e1 + the
   fitted head; every other parameter byte-identical, so the served set and policy are e1's).
   The labels are policy-conditional (the e3 policy's margins); the loop regenerates them per
   cycle — the loop-native BCE term lands with the loop wiring (below).
4. **The reads.** (a) The wire smoke on the unfitted build (2 games, `-searchalloc 0.5`): 224
   asks, 224 declined, every window `by: unserved` and searched, the ask 7 ms mean / 29 max, 0
   crashes — the path and the decline are clean. (b) The served smoke (4 games, tau 0.369) —
   the addendum below. (c) **The post-Build-4 read, pre-registered** (the Build 2 gate's second
   reading, ADR-0104): three arms on `m12-build4-e1a`, 2 × 1,000 games each vs the heuristic on
   the final_read pairs, 24 workers × 2 servers, the alloc-tip jar: `on` (the build alone,
   greedy), `act` (+ the recipe: rate 1, rolls 2, `-searchsurf 2`, acting at 0.10 / T 0.025 on
   options and entity + mode answers), `alloc` (the same recipe under `-searchalloc 0.369
   -searchfloor 0.1`). **Gate: act − on ≥ +1.5pp clears the big run's launch condition**
   (in-band or ≤ 0 = the Build 2 rules); **alloc − act is the head's strength-neutrality check**
   (within one SE at the lower call count = the head is free to allocate; a negative sign at
   t ≥ 2 = the floor or tau moves before the shakedown). The head's verdict proper is the
   shakedown's equal-box-time allocation arm (ADR-0109), not this read.
5. **Sequencing (user):** the head (this ADR) → the post-Build-4 read → **the loop wiring**
   (search flags on `selfplay.py`'s harness launch; `rl.py` gains the search-row terms —
   the distillation of the search's pick where it acted, PG under the search's behavior
   log-probability, the alloc head's BCE on the rows' margins — with the join and the anchor
   `search_distill` already built) → route (b) (ADR-0111: the target decoder co-distilled on
   the realized plans; needs the realized-plan recording on acted windows and copies, a fork
   change) → the documentation pass (Build order 4¾) → the shakedown with the allocation arm.

## Consequences

- The search's cost becomes a policy the model owns: at the pin the recipe searches half its
  windows for 87% of its acts, ≈ ×1.6 the games per box-hour in search cost (≈ ×1.3 whole-game
  at the recipe's copy share). The bench cell that prices it (24 × 2, the `alloc` arm's g/h
  beside the `act` arm's) is the read's own by-product (`ms_p50` per arm in `read.json`).
- Fork L's shape output is one enum away: the ask's INT answer carries a probability today and
  can carry a shape id when the deep round's labels exist per window.
- **Standing rule (born here):** an allocation gate's ask is a server ask on the value wire,
  declined without a fit record — never a default rate baked into the engine; the uniform floor
  is a private seeded stream so the rate draw and the arms still join per window.
- Routed by name: the loop wiring (Build 4½ pre-work, next after the read); the alloc head's
  loop-native term (with it); tau / floor as settings-pass axes; the peek-record vs dec-record
  featurization parity at serve (the value head's standing discrepancy, now shared by this head:
  a one-worker identity read if the served allocation ever disagrees with the offline fit).

## Addendum 09-17 15:15 — the served smoke clean; the chain launched

- **The served smoke** (4 games, `m12-build4-e1a`, tau 0.369 / floor 0.1, jar `a37bc6a8b4`):
  330 candidate windows — **head 189 (57%) / floor 18 (5.5%) / skip 123 (37%)**; searched 63% of
  windows (the offline table said 51%: four games, the head's p on searched windows mean 0.62,
  on skipped mean 0.18 — the separation is what the AUC promised); acts (by = search) **34 / 189
  on head windows (18%), 0 / 18 on floor windows** → the floor's act rate estimates the skipped
  windows' at 0 on this sample (the recall estimate 1.00 is four games of noise, not a number);
  copy forward calls 1,501 per game (the two-game unserved smoke: 2,817 — different games, not
  a read); the ask 19 ms mean / 39 max with the head served (7 ms declined); 4/4 games clean, 0
  copy crashes, the standing prefs-leak exception only; every ask answered (`model alloc: 330`).
- **Launched 15:14 through `anvil.runs`: `build4-alloc-chain`** (state
  `~/.local/state/anvil/runs/build4-alloc-chain.json`, running, pid 56516; log
  `data/runs/build4-alloc/run.log`; stall alarm 60 min on the run dir; sinks queue + desk) — the
  forkcheck `run-20260917-build4-alloc` (500 games vs the merge baseline; the flag-off path) →
  the post-Build-4 read `data/runs/build3-surface-read-b4post/` (on / act / alloc, 1,000 per seat,
  24 × 2) → `read.json` (on the reference) + `read-alloc.json` (act the reference) +
  `alloc-census.txt`. ETA ≈ 04:00–05:00 09-18 (forkcheck ≈ 1 h, on ≈ 1.5 h, act ≈ 6 h, alloc ≈ 4.5 h).

## Addendum 09-17 16:55 — the alloc tip proven → the fork pin `a37bc6a8b4`; the read's pace

- `run-20260917-build4-alloc`: **499 / 500 main-trace hashes identical**, 20260969 the standing
  launch-unstable seed (turns 29 vs 29), fork fidelity 451 / 48 / 1 = the merge baseline's →
  PASS 15:45. **The fork pin = `a37bc6a8b4`.**
- The `on` arm closed 16:27 (2,000 games, 0 crashes, 3 clock draws, veto rate 4.5%, model wins
  1,043 / 1,981 decisive); the `act` arm runs at ≈ 750 g/h — twice the self-play bench's 347
  because the read searches ONE bridged seat against the heuristic (the bench searched both).
  The ETA moves to ≈ 21:30 09-17.

## Addendum 09-17 22:35 — THE POST-BUILD-4 READ CLEARS THE LAUNCH CONDITION: act − on +2.29pp ± 1.02

- The `on` and `act` arms closed (2,000 games each, 0 crashes, the standing draw class only):
  **on 0.5265 ± 0.0112** (e1 alone, greedy, raw — the era's reference `iter-019` reads 0.5300 raw
  / 0.5348 corrected, so the day-zero build alone sits at the reference within noise; the
  Build 2 "dz − ref" question is closed neutral on this era's jar) / **act 0.5494 ± 0.0112**
  (+ the recipe). **Paired act − on = +2.29pp ± 1.02 (t 2.24, n 1,964; 225 up / 180 down) ≥ the
  +1.5pp bar → GO: the big run's launch condition (ADR-0104's "a post-Build-4 read ≥ +1.5pp")
  is CLEARED.** Acting telemetry on the act arm: 72,275 searched windows, act rate 8.96%
  (natural 89.7%, nat_unvalued 1.4%), ms p50 69 s vs 19.5 s alone (×3.5 wall on one searched
  seat vs the heuristic).
- The `alloc` arm runs (seat 0 at 22:20; ≈ 1,070 g/h vs the act arm's ≈ 750 at the same fleet:
  the head's saving in the read's own wall) — `read.json` + `read-alloc.json` land at its close.

## Addendum 09-18 09:30 — THE READ CLOSED: the head allocates freely (alloc − act +0.25 ± 0.61 at 51% of the windows); the chain done 00:39

- **Three arms, 2,000 games each, 24 × 2, jar `a37bc6a8b4`, build `m12-build4-e1a`, 0 crashes:**

  | arm | winrate ± se | vs on | vs act | ms p50 | wall × on |
  |---|---|---|---|---|---|
  | on (alone) | 0.5265 ± 0.0112 | — | — | 19.5 s | 1.00 |
  | act (the recipe) | 0.5494 ± 0.0112 | **+2.29 ± 1.02 (t 2.24)** | — | 69.1 s | 3.54 |
  | alloc (the recipe under the head) | 0.5528 ± 0.0112 | **+2.70 ± 1.00 (t 2.68)** | **+0.25 ± 0.61 (t 0.41; 76 up / 71 down, n 1,978)** | 49.3 s | 2.53 |

  **The neutrality check passes with room: alloc − act sits inside one SE at 51.3% of the
  candidate windows searched.** The search's wall overhead on the searched seat fell 40%
  (49.5 s → 29.8 s per game over the alone arm); the arm ran ≈ 1,070 g/h vs act's ≈ 750 on the
  same fleet.
- **The allocation census (`alloc-census.txt`; 73,266 candidate windows over the 2,000 games,
  keyed as 1,000 seed pairs):** head 46.0% / floor 5.3% / skip 48.7% → searched 51.3% (the
  offline table's 0.51 exactly); the head's p on searched windows mean 0.62 (p10 0.41), on
  skipped 0.16 (p90 0.32); **acts 5,600 / 33,692 on head windows (16.6%) vs 102 / 3,899 on
  floor windows (2.6%) → the floor's estimate of the skipped windows' act rate gives the head
  a recall of 0.86 (the fit's OOF 0.87)**; the act rate over searched windows 15.2% vs the
  uniform arm's 9.0%. Copy forward calls 477 per game on the alloc arm. The ask 44 ms mean /
  59 p90 / 1.3 s max under the fleet's batching (7–19 ms on the one-worker smokes).
- **Verdicts (pre-registered, item 4):** (1) **act − on +2.29 ≥ +1.5 → the big run's launch
  condition is cleared** on the day-zero build; (2) **alloc − act within one SE → the head is
  free to allocate** in the recipe from here (tau 0.369, floor 0.1; the shakedown's settings
  pass owns the pin and the equal-box-time allocation arm reads the games multiplier as
  strength). The served build of record moves to `m12-build4-e1a` (e1 + the head; the policy
  and the served set unchanged).
- Banked, not a verdict: both searched arms carry a mainline veto rate of 14% against the alone
  arm's 4.5% (the acting rule's forced picks re-asked by the executor) — a first look belongs to
  the loop-wiring session, where the search's behavior log-probability meets the mu record.
- Run hygiene: the launcher's stall tick watched the chain's own dir while the arms wrote
  elsewhere (two false STALLED alerts; a heartbeat file patched it live) → `anvil.runs launch
  --watch <dir>` routed; the GPU yield gate paused the act arm ≈ 3 h for a game on the GPU (by
  design, resumed clean); the read's pace on one searched seat vs the heuristic is ≈ 2× the
  self-play bench (both seats searched) — a sizing note for read ETAs.
