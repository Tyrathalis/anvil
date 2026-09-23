# ADR-0117: The certifier merge — one fork-and-adjudicate primitive, AnvilRun `-replay` as the certifier's front

- **Date:** 2026-09-23
- **Status:** accepted (the fork tip `05fea7938d`; forkcheck `run-20260923-certmerge` PASS 12:33 (499/500, 20260969 the standing seed; fidelity 451/48/1 = the baseline's)); the Python side on the branch `certifier-merge` (worktree `../anvil-wt-certmerge`), merged into main with `nan-guard` when the shakedown closes
- **Design-doc anchor:** §6 (Grindstone: drill provenance and certification), §9 (engine & infrastructure); m12-plan "the certifier merge" (routed 09-09 s2 → Build 4½ / ADR-0108 → ADR-0115: during the shakedown week, for the big run's jar)

## Context

Two runners adjudicated a stored decision by replaying to it and forking: the M9 certifier
(`CensusRun -certify`, [ADR-0077](ADR-0077-m9-closeout.md): a `PayDirective` matched on the mainline's
payment window by (player, turn, sa substring, ordinal); one FULL GAME per (job, arm, roll) under census
construction — default AI profiles, no caps; roll 0 the true continuation, rolls ≥ 1 libraries reshuffled
at the window; a horizon stop; one `ev:"certify"` row per game with the end snapshot) and the search copy
(`AnvilRun.SearchMonitor.runCopy`, [ADR-0102](ADR-0102-m12-build0-pins.md) fork J onward: a `GameCopier`
copy at the seat's quiescent priority window, the option forced, any surface answered by a
`SurfaceDirective`, the leaf family `next | eot | h<N> | end`, the same snapshot). Everything downstream
of reaching the window was duplicated, and the two runners were not trajectory-identical (the 09-09
finding: AnvilRun draws seed-derived AI profiles and applies the caps), so no certify job could line up
with a search window. The big run's drill-finding IS the search ([ADR-0101](ADR-0101-architecture-review-m12-recharter.md)
item 3), and its two triggers — the re-certification of the existing payment drills on the new pin and
the first drill mined from network-played games — both fire at its launch. The plan's sketch: consult
`PayDirective` inside the Anvil controller's copy path, the certifier a thin front, CensusRun's certify
mode retired, drill mining moved to AnvilRun census rows.

## Decision

1. **The front: `AnvilRun -replay <jobs.jsonl> -labels <out.jsonl>`.** One job per line in the M9 jobs
   contract (`job, seed, deck1, deck2, p | seat, t, sa, ord, arms, k, horizon, mode`) plus the
   coordinate's own `profile1 / profile2` (else AnvilRun's seed-derived pair; recorded on every row)
   and `ph` (the window's phase). The mainline plays the job's game (idx = job) under AnvilRun's own
   construction and flags; **the fork point is the window where the seat's NATURAL PICK is the stored
   option** — a `PlayerControllerAnvil.PickHook` told the pick before the play, on the job's turn (and
   phase), the active player's priority on an empty stack (the fork-fidelity rule), the ord-th such
   pick. There every (arm, roll) forks a search copy through the SearchMonitor's copy runner with the
   option forced and a PAY `SurfaceDirective` answering `arm` at the option's own payment window
   (0 = auto, the paired baseline), played to the horizon leaf (`t + horizon`; `< 0` = the outcome),
   one certify row per copy in CensusRun's row contract (+ `kind, calls, i, seat, t, ph, label,
   profiles`; observe rows carry the window's `frame` and the game `header`). **Roll 0 is the true
   continuation** (the mainline's RNG stream restored, no determinization — `runCopy(..., trueLine)`);
   rolls ≥ 1 are fork J's determinized copies. The mainline ends at the fork point (the completions are
   the product); a window that never comes writes one `never_fired` row per arm.
2. **No `PayDirective` on the copy path.** The pay `SurfaceDirective` already IS the directed payment
   on a search copy (`copyPay`, evening 4); it gained the execution record the certify row needs
   (`exec / goals / kinds / turn`). The plan's sketch consulted `PayDirective` there; the landing is
   smaller and one idiom.
3. **The phase is part of the coordinate; the natural pick is the window.** The first landing forked
   at the first quiescent priority window holding the option: on the 09-23 native smoke a main-2 cast
   forked at main 1 was a window the AI declines (`heur_refuse`, 11 of 52 jobs), so the fork point
   moved to the mainline's own pick. A payment made on the opponent's turn or in response (the stack
   non-empty) has no faithful fork point — `GameCopier` resumes at the active player's priority — and
   reads `never_fired` by design (13 of 52 native jobs, every one an opponent-turn cast: counterspells,
   flash creatures, instant-speed abilities). The same limit the search has.
4. **`CensusRun -certify` stays as the parity witness** until the big run's launch, then deletes with
   `PayDirective`; `payment_certify.py lanes --runner census|anvil` (default `anvil`), `read`
   unchanged (the rows are the same contract), `plan --results <results.jsonl>` takes an AnvilRun run's
   provenance (decks, seed, profiles by game index) in place of the census lane scripts, the phase rides
   from the miner's candidate; `payment_drill_score.py score --rows` reads observe frames off the rows.
   `payment_drill_mine.py` needs no change — AnvilRun's `-paytelemetry` census carries the same fields.
5. **Acceptance = the forkcheck + the native replay + the M9 witness pair** (the two runners are not
   trajectory-identical by construction, so byte parity was never the bar): the native replay (4 heuristic games under `-paytelemetry -bridgeseats 2`,
   112 consequential windows off the census, the first 60 as jobs with profiles + phase, arms ≤ 4, k 2,
   horizon 2) — **35 fired / 6 diverged / 19 never_fired**, the copy's option count equal to the census
   row's `goals` on every fired job (35/35), arm 0 auto on both rolls and every arm > 0 `directed_ok`
   (200/200 copies); the 19 never_fired = 16 opponent-turn casts + 3 own-turn casts in response (no
   fork point by design), the 6 diverged = the copier's own divergence class (the AI's memory is not
   copied). The M9 witness pair (30 `ceilh2` jobs of 08-24, k 1): CensusRun -certify on today's jar
   **22/30** (8 = the jar drift since August), AnvilRun -replay on the same phase-less, profile-less
   coordinates **4/30** — the two runners' play agrees on that few M9 windows, so the M9 evalset's
   re-certification goes through the witness, and every new drill is mined and certified on AnvilRun's
   construction. Observe mode: 5 native observe jobs → 5 rows with `frame` + `header`, `payment_drill_score.py score --rows` featurized and ran the b4e1a-tgt build off the rows alone (5/5 scored, every pick auto — the withheld pay head's day-zero signature). Forkcheck: PASS 12:33 (499/500, 20260969 the standing seed; fidelity 451/48/1 = the baseline's).

## Consequences

- The certifier's front of record is `-replay`; every future certification and re-certification runs
  on AnvilRun's construction — a coordinate mined from an AnvilRun game replays exactly under the same
  flags (the seed-derived profiles are recorded on the coordinate). The M9 evalset of record
  (`payment-evalset-v2`) was certified under census construction; its re-certification on the big run's
  pin runs through the witness pair first (how many of its windows the AnvilRun prefix reaches).
- Standing rule (born here → standing-rules.md, curation / drills): **a replay coordinate names the
  seat's natural pick, its turn, its phase and the seat profiles; the fork point is that pick's window,
  never the first window holding the option** (the AI declines many of those).
- Routed by name: a `-search` front over a stored window (re-search a high-margin window at higher
  budget, ADR-0101 item 3 — the coordinate is the window, not a cast; the pick hook is its hook point);
  the deletion of `CensusRun -certify` + `PayDirective` at the big run's launch ADR; `nan-guard` +
  `certifier-merge` merge into main when the shakedown closes.
