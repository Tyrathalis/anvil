# ADR-0102: M12 Build 0 pins — the mask's payability predicate is the executor's own; the boundary carries only game-path changes; deterministic caps; provenance in the game header under sv=3; the hidden-information axis (uniform determinization now, belief-sampled next); the banked value-label count corrected

- **Date:** 2026-09-06 (session 4)
- **Status:** accepted
- **Design-doc anchor:** m12-plan.md Build 0 (engine bundle) + fork J (new); anvil-design-v2 §3a
  (search), §3d (caps), §9 (store provenance); ADR-0101 findings 2–3; ADR-0068 (the boundary
  template); ADR-0025 (the behavior-identical exemption)

## Context

Build 0 opened with a review of the as-built state against the plan's text. Six things the
plan assumed turned out to be different from what the tree holds, and each changes the work:

| plan text | as built |
|---|---|
| "exact payability in the mask (the M9 enumerator as a filter)" | a payability filter already exists in `AnvilOptions.buildPriorityOptions` behind `-Danvil.scan.paycheck=on`, using Forge's own `ComputerUtilCost.canPayCost` before targets are set; it was turned OFF at M1 because costs price late (11 castable expert picks excluded in 320 games, the D3 validation) and it doubled the most expensive per-window engine work. The apply-time veto (`CastPlanRealizer.legality` + `canPayCost` after targets) uses the SAME Forge predicate. The M9 enumerator runs on the game path only inside payment windows. |
| "game-time and repetition caps with cap-aware reward" | a 300 s wall-clock draw clock exists (`AnvilRun.DRAW_CLOCK_S`) and the trainer already scores loss/draw/cap as 0 for both seats (the §3d rule, `rl.py`); there is no turn cap, no decision cap, no repetition detection. The 2,000-game rebaseline had zero draws. |
| "the budgeted search directive" | the schedule/certify machinery copies with paired seeds, reshuffles both libraries by default, and lets the network play the copy — but there is NO leaf-value callback in Java; the M11 read valued leaves offline. The directive is new surface. |
| "format id and pool id on every store/trajectory row" | `anvil/store/trajectories.py` states provenance lives in the manifest and never in records; the manifest already carries `format` (free text) and `pool_version`; the bridge hardcodes `format_tag = "mtg.commander"` regardless of `-f`, sends an empty `fork_commit` and never sets `engine_commit`. |
| "106K drill-fork games and thousands of K=8 composites" as value targets | 95,616 of the 106,189 are the cl2 store's completions. Rollout-mean labels on disk: **1,321 drill fork points, 806 harvest windows, 3,294 mint per-arm rows, ~6,000 cl2 per-arm leaves over 800 windows** — of order 10⁴ labeled post-action states, not 10⁵. |
| the p90 game-time tail as a cap target | the slowest decile of the rebaseline is 31% of wall time, runs 33 turns against a median of 21, and costs 1.75× more per turn — the tail is wide boards as much as long games; caps buy ≈10%, not a multiplier. |

A seventh item the plan did not name: every game copy keeps the opponent's TRUE hand, so the
path to every search leaf uses information the acting seat cannot have (the leaf value itself
is masked). The user raised the question of whether a thinner channel (values only, not
branches) would close the leak; it does not — the leak is what the number is conditioned on,
not the width of the channel.

## Decision

1. **The mask's payability predicate is the executor's own** — `canPayCost` before targets, the
   existing `PAYCHECK` path, ON by default on the research jar. Filter and apply-time
   adjudicator are the same predicate, so the veto rate falls to the late-pricing residual by
   construction (the ADR-0066 unit-of-exclusivity corollary applied to legality). The residual
   veto classes are named and counted, not absorbed: late-priced cost modifiers, and the
   model's own X / mode choice. **The M9 enumerator is NOT the filter**; it becomes an
   apply-time RESCUE (directed payment when `canPayCost` fails but a plan exists) only if the
   Build 0 smoke shows chain-payable casts dominating the residual. The mask cache
   (`-Danvil.scan.maskcache`, equivalence-proven 2026-08-11, default off) has its key extended
   for the new mask inputs (mana pool, life) and is re-gated by the obs-diff protocol; whether
   it ships ON is decided by the smoke's games/hour, not assumed (it read throughput-neutral at
   the serving-bound operating point).
2. **The boundary carries only game-path changes**: the mask filter, the caps, and the provenance
   header (item 4). The search directive, the value RPC, and the Build 3 enumerators are inert
   with their flags off and land AFTER the boundary as ADR-0025-exempt commits, each with its
   500-game forkcheck proof — Build 2 does not wait on nine enumerators. The boundary forkcheck
   runs against the 08-21 seed set (`run-20260821-m9boundary`) and discharges the recording
   jar's owed proof (`f4824f3d6`, one recording-only commit) by transitivity on the same seeds.
   The day-zero fixed population (ADR-0094) regenerates on the boundary jar — era-closed.
3. **Caps are deterministic and replay-stable**: a per-game decision-window cap and a turn cap,
   both in game units the model could in principle see, pinned from the rebaseline's own
   distribution at the 99.5th percentile so ≤ 0.5% of games truncate (obs records per game:
   p50 1,915 / p99 6,733 / p99.5 9,477 / max 72,134; turns p99 46 / max 107 — the exact
   priority-window quantile is read at implementation). The wall-clock clock stays as a crash
   guard only. Reward: unchanged — win 1, loss/draw/cap 0 for both seats (already in `rl.py`).
   **Repetition detection is deferred** with a tripline: draw-clock or cap hits above 0.5% of
   games in any run reopen it. The design's canonicalization-hash detector stays the named
   mechanism.
4. **Provenance shape**: "on every row" is satisfied by the per-game obs header plus the store
   manifest — registry ids for format (the `formats` vocab registry keys) and pool (the pool
   manifest hash, passed to `AnvilRun` as `-pool <id>`), the bridge `GameStart.format_tag`
   derived from `-f`, `WorkerHello.fork_commit`/`engine_commit` populated. Records stay
   provenance-free (the store invariant holds). **`OBS_SCHEMA_VERSION` → 3** as the era gate,
   with the reader taking the version per store manifest so Build 1 opens sv=2 stores
   explicitly; sv=2 and sv=3 never join. `launch --pool` additionally refuses to extend a store
   whose manifest `pool_version` differs from `CURRENT`. Pauper has no pool to pin; the
   per-directory `CURRENT` convention is documented in the onboarding recipe, nothing written.
5. **The hidden-information axis (fork J, new).** Every search copy is **determinized to the
   acting seat's information set**: libraries reshuffled (already default) AND the opponent's
   hand resampled uniformly from their unknown set (decklist minus visible zones; the commander
   pins the list in this pool), one sample per leaf roll, the same zone-swap shape as the
   library reshuffle. Revealed-from-hand cards are approximated as unknown unless the engine
   tracks the reveal. Named as the first teacher setting in the directive's provenance, so a
   later change is a labeled teacher boundary rather than a silent one. Routed by name: (L2)
   **belief-sampled determinization** — the belief head's first consumer; its labels are free
   and dense (the true opponent hand at every self-play window) and its quality is read as
   log-likelihood of the true hand vs uniform on held-out games, no strength read needed;
   consistency rejection (hands the opponent's own policy would not have played that way) as a
   later refinement. (L3) information-set search proper — out of scope; the residual flaw of
   all determinized search (each copy assumes the seat can respond differently in worlds it
   cannot distinguish, so committed lines are under-valued) is a named suspect if the Build 5
   network-alone gap holds while with-lookahead climbs.
6. **The Build 1 record is corrected** to the label counts above. The pre-registered bars
   (GO one-ply ≥ 0.35 and/or state-ranking ≥ 0.50; KILL < 0.32) stand; the read is interpreted
   at ~10⁴ rollout-mean labels plus the dense full-vis h2 targets and terminal outcomes, and the
   ADR-0099 slope (+0.03 per doubling from 10³) is the prior for what that scale can buy.

## Consequences

- m12-plan Build 0 rewritten to this shape; fork J added; the label-count line corrected; the
  Build 1 read carries the scale note.
- Build 0 order inside the fork: (a) mask filter ON + cache key extension + obs-diff gate;
  (b) caps; (c) provenance header + sv=3 + bridge fields + Python reader/harness; (d) the
  boundary jar: forkcheck vs the 08-21 seeds, then a bridged smoke on `iter-019` reading the
  residual veto classes, the cap-hit rate, games/hour cache off/on, and the priority-window
  quantile; (e) AFTER the boundary, as exempt commits: the value RPC + the budgeted directive
  with uniform determinization + forward-call/leaf telemetry, then the enumerators.
- Standing rules born here → standing-rules.md: **the mask's legality predicate is the
  executor's apply-time predicate** (filter and adjudicator agree by construction; residual
  classes are counted, never absorbed by a penalty); **a search copy is determinized to the
  acting seat's information set** (hidden zones resampled, never carried true; the sampler is a
  named teacher setting in provenance; values from true-hand copies leak regardless of channel
  width).
- The belief head moves from "deferred, unnamed consumer" to "deferred, first consumer = the
  determinization sampler, labels free"; routed by name at the closeout or earlier if fork J's
  L1 reads as the binding suspect.
- Not changed: the ckpt of record, the baseline, every other ADR-0101 pin.

## Addendum (2026-09-06, session 4, evening): the boundary landed and read

**Boundary jar:** fork `master` at the Build 0 tip (the search directive, the RNG-neutral scan
and the search fixes ride on `5d5283eb233`); Anvil `de3d23a`+. **Forkcheck
(`run-20260906-build0-boundary`, 500 heuristic games, seed 20260703 = the 08-21 seed set):
499/500 main-trace hashes identical to `run-20260821-m9boundary`**, the one miss = seed 20260969,
already named on 09-05 as launch-to-launch unstable on a single jar (the identity-hash residual);
fork fidelity 450 clean / 50 divergence = the baseline's 450/50. The recording jar's owed
ADR-0025 proof (`f4824f3d6`) is discharged by transitivity on the same seeds. No capped seeds
among the 500.

**The smoke (arms A/B/C, `iter-019` argmax vs heuristic, seat 0, 3 workers):**

| per game | reference (pre-boundary arm s0, 1,000 g) | A filter ON (600 g) | C payshadow (200 g) |
|---|---|---|---|
| first-attempt veto rate | 0.1217 | **0.0458** | 0.0415 |
| unpayable first vetoes | 2.99 | **0.10** | 0.02 |
| no_shape_fit | 0.90 | 1.03 | 1.10 |
| restrictions / after_stack / timing | 0.19 / 0.00 / 0.03 | 0.09 / 0.06 / 0.04 | 0.05 / 0 / 0.02 |
| realized casts | 30.8 | 27.8 | 27.4 |
| re-ask rescues | 0.84 | 0.23 | 0.19 |
| games capped (turn / windows) | 0 | 2 of 600 (1 / 1) | 1 of 200 |
| median game ms | 8,248 (16 workers) | 7,919 | 9,403 |

- **The payability class is gone (−97%) at no wall-time cost.** The residual veto is the
  **shape-fit class** (the CastPlan's target refs do not fit the named spell) at ~1 per game,
  unchanged — it belongs to Build 3's targets surface, not to payability; it is now the
  dominant veto and is named as such. `after_stack` (0.06/g) is ONE card: "Play land by Glarb,
  Calamity's Augur" (33 of 38) — `canPlay` admits the top-of-library land play, the post-stack
  check rejects it. **The heuristic seat's expert pick was outside the filtered mask 0 times in
  15,558 casts** — the M1 D3 late-pricing exclusion class did not reproduce.
- **Casts per game −10% vs the reference** (rescues −73%); the two runs play different pair
  schedules, so a smoke cannot separate behavior from matchup mix — flagged for the Build 2
  day-zero paired read; the loop's anti-passivity floor (0.8× baseline) is the guard.
- **Caps pinned as built: turn 52 / windows 1,650** (0.33% of games truncate; windows p99.5 in
  A = 1,477, max = the cap).
- **The enumerator-rescue class (C):** of 895,532 options scanned over 115,656 windows, 209,048
  (23%) were rejected by the executor's predicate and **19,717 of those (9.4% of rejected, ~0.17
  per window) are payable by the M9 enumerator** — the chained-activation blind spot
  (Signet-class). They are NOT admitted to the mask: admitting them without routing their
  payment through `executeDirected` would only recreate vetoes at apply. **Routed by name to
  Build 3's payment-classes surface** (where the pay head and the directed executor go live):
  admit `payable || enumeratorPlan` and pay directed when auto cannot. Shadow costs +19% engine
  time per game at 3 workers.
- **The mask cache:** the obs-diff gate on A vs B FAILED on the first jar — 68 of 600 games
  first-diverged on the MASK class with identical prior records, and in the worst cases the
  boards differed wholesale. **Root cause: the payability test walks
  `ComputerUtilMana.isManaSourceReserved`, whose `MyRandom.percentTrue` draws from the game RNG
  on every shard × source it examines (every profile sets RESERVE_MANA_FOR_MAIN2_CHANCE=100),
  so each scan perturbed the seed's stream and every cache hit shifted it.** This is also the
  D2 "`-obs` perturbs which trajectory a seed plays" finding, now explained. **Fix (in the
  boundary): the scan and the predicate run on a throwaway RNG** (`AnvilOptions.withScratchRng`)
  — obs logging, the cache, the realizer's apply-time check and the search copies' scans are
  RNG-neutral by construction. The cache gate re-read on the fixed jar: CACHE_GATE_RESULT.
  B's timing (+31% vs A) was contaminated by the session's own compiles and is not a read; the
  cache stays OFF (default) until the search multiplier says the engine binds.
- **The search smoke (12 games, rate 0.05, 1 roll, 45 windows):** the directive runs end to end —
  leaves 86%, void 14% (the forced option vetoed at apply on the copy: mana-ability activations
  13%, spells 21% — the shape-fit class again), crashes 0 after two fixes (the sched-only
  `sc.onCast` dereference; an immutable single-option ask list). **Forward calls per leaf p50 2
  / p90 4 / max 16** (= 1 intermediate decision at p50 — the leaf is one resolution away),
  **ms per window p50 496 / p90 1,454** at ~7 candidates, ms per option p50 61, copy share 11%;
  **multiplier 1.13× forward calls at rate 0.05 → ≈3.6× at rate 1**, wall ≈ +0.5 s per searched
  window over a ~10 s game (~80 eligible windows/game → ~5× wall at rate 1 before any gating).
  **58% of candidates were pure mana abilities** ("{T}: Add {B}"), whose leaf is the pass leaf
  with the seat tapped down → **excluded from the candidate set by default** (`-searchmana`
  restores; they stay in the mask) — expected to cut per-window cost ~2.4×. Margins on the
  unsharpened head: p50 0.017 / p90 0.071 / max 0.13; argmax ≠ natural at 67% of windows;
  margin ≥ 0.02 at 42%, ≥ 0.05 at 20% — the bar/temperature are pinned at Build 2 on the
  sharpened head, not from this. Value asks: 43/43 served, 0 fallbacks.
- **Build 0 done-when 1:** landed. Remaining inside Build 0: the Build 3 enumerators (Java only,
  exempt commits) — next session; **Build 1 opens in parallel.**
