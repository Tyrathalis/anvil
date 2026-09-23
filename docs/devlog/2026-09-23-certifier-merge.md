# 2026-09-23 — the certifier merge ([ADR-0117](../decisions/ADR-0117-certifier-merge.md)) beside the shakedown

<!-- Wrap-up: the session checklist lives in CLAUDE.md (devlog · plan-doc running record · Now block · commit). -->

## Done

- **The review (user: "the certifier merge on the fork while the shakedown runs — decisions?").** The
  recipe arm closed 04:30 at **0.5240 ± 0.0112** (30.6 h, 16 iterations, 7,680 games; day-zero 0.5185)
  → +0.55pp, inside noise; the alloc arm running since 04:30. Decisions taken (user): the forkcheck
  inside a shakedown pause window (`anvil.runs pause` at the iteration boundary; the wall budget carries),
  acceptance = the forkcheck + a native replay + the M9 witness pair (byte parity was never the bar —
  the two runners differ by construction), CensusRun's certify mode kept as the witness until the big
  run's launch, the merge before the documentation pass. The July `data/training/shakedown` /
  `shakedown2` dirs (M1 era, 155 MB, a naming collision with the arm dirs) deleted on sign-off.
- **The archaeology.** `CensusRun -certify` (PayDirective matched at the mainline's payment window,
  one full game per (job, arm, roll), census construction) vs the search copy (`runCopy`: GameCopier
  at the seat's quiescent priority window, the option forced, a SurfaceDirective per surface, the leaf
  family, `certSnap`) — everything downstream of reaching the window duplicated. AnvilRun's per-game
  construction: seed-derived AI profiles, the caps, `Anvil(N)-deck` / `Heur(N)-deck` names; the
  `-forceschedule` / `-forcechoice` job-file idiom; `-certify <horizon>` already taken (the M10 inline
  certifier) → the new front is `-replay`.
- **The fork (tip `05fea7938d` on `cbe386d2c6`): `AnvilRun -replay <jobs.jsonl> -labels <out>`.** The M9
  jobs contract + `seat` / `profile1` / `profile2` / `ph`; the mainline plays the job's game to the
  window where the seat's NATURAL PICK is the stored option (`PlayerControllerAnvil.PickHook`, the
  pick before the play; the job's turn + phase, the active player's priority on an empty stack, the
  ord-th such pick); per (arm, roll) one search copy through the SearchMonitor's copy runner (never
  subscribed: rate 0) with the option forced and a PAY `SurfaceDirective` answering the arm at the
  option's own payment window (0 = auto), to the horizon leaf; **every copy continues the mainline's
  decision** (`SearchDirective.replayNatural`: the seat's own chooser under the mainline's pre-decision
  RNG state, the pick verified, else `diverged:<pick>`); roll 0 on the true line (no determinization),
  rolls ≥ 1 determinized per fork J; one `ev:"certify"` row per copy in CensusRun's contract (+ `kind,
  calls, i, seat, t, ph, label, profiles`; observe rows carry `frame` + `header`); the mainline ends at
  the fork point; a window that never comes → one `never_fired` row per arm. `SurfaceDirective` gained
  the fired PAY answer's `exec / goals / kinds / turn` (copyPay records them); `CensusRun.flatJson`
  shared; `runCopy(..., trueLine, playRng)`; `CopyResult` gained winner / snapInts / the surface exec
  record; `certSnap` refactored over `certSnapInts`. Test `ReplayJobTest` (4). No `PayDirective` on the
  copy path — the pay SurfaceDirective already is the directed payment.
- **The three landings the smokes forced** (each a miss class read off the rows, not a guess):
  (1) under `-b local-random` every seat is bridged to the random bridge, which has no cast plan →
  every copy voided; the heuristic mirror is `-bridgeseats 2` (the harness's idiom). (2) The first
  quiescent window holding the option is often one the AI declines (`heur_refuse` 11/52: a main-2
  cast forked at main 1) → the phase on the coordinate, then the fork point = the natural pick.
  (3) A matched natural pick re-approved through `heuristicRealize` → `canPlaySa` still refused on a
  Reckless seat (its chance checks re-roll) → `replayNatural`: the copy runs the seat's own chooser
  under the pre-decision RNG and verifies the pick — CensusRun's semantic (the same trajectory
  continued), now on a copy.
- **The Python side on the branch `certifier-merge`** (worktree `../anvil-wt-certmerge`; merges into
  main with `nan-guard` when the shakedown closes): `payment_certify.py lanes --runner anvil|census`
  (default anvil) + `--forge-flags`, `plan --results <results.jsonl>` (AnvilRun provenance: decks,
  seed, profiles by game index; the phase from the miner's candidate), `REPLAY_JOB_FIELDS`,
  `lane_command`; `payment_drill_score.py score --rows` (frames off the observe rows), `lanes
  --runner`. `payment_drill_mine.py` unchanged (AnvilRun's `-paytelemetry` census carries the same
  fields). Lint clean.
- **Docs:** ADR-0117, the standing rule (curation / drills), `scripts/certmerge_forkcheck_chain.sh`.

## Results

- **The native replay** (4 heuristic games under `-paytelemetry -bridgeseats 2`, 112 consequential
  windows mined off the census, the first 60 as jobs with profiles + phase, arms ≤ 4, k 2, horizon 2):
  **35 fired / 6 diverged / 19 never_fired**; on every fired job the copy's option count equals the
  census row's `goals` (35/35); arm 0 auto on both rolls, every arm > 0 `directed_ok` (200/200 copies).
  The 19 never_fired: 16 opponent-turn casts (counterspells, flash creatures, instant-speed abilities —
  no faithful fork point, by design) + 3 own-turn casts in response / at declare-attackers (the stack
  non-empty). The 6 diverged = the copier's own divergence class (the AI's memory is not copied; the
  fork-fidelity check's 48/500). The pick-hook-only jar read 29 fired / 11 heur_refuse on the same jobs.
- **The M9 witness pair** (30 `ceilh2` jobs of 08-24, k 1): CensusRun -certify on today's jar fires
  **22/30** (8 never_fired = the jar drift since August; 94 directed_ok arms); AnvilRun -replay on the
  same coordinates (no phase, no profiles, the AnvilRun prefix): **4/30** (26 never_fired) — the two runners' play
  agrees on that few of the M9 windows, which is what the re-certification of `payment-evalset-v2` on
  the big run's pin will meet.
- **Observe mode + the scorer's row path:** 5 native observe jobs → 5 rows with `frame` + `header`, `payment_drill_score.py score --rows` featurized and ran the b4e1a-tgt build off the rows alone (5/5 scored, every pick auto — the withheld pay head's day-zero signature)
- **Forkcheck `run-20260923-certmerge`:** PASS 12:33 (499/500, 20260969 the standing seed; fidelity 451/48/1 = the baseline's)

## Broke / surprised me

- `-b local-random` bridges every seat (the default tag set) — a "heuristic" smoke under it is random
  play with voided forced options; the idiom for all-heuristic is `-bridgeseats 2`.
- The AI's decision is stochastic per profile: re-approving a matched pick through `canPlaySa` on a
  copy is not the same decision. Trajectory continuation needs the pre-decision RNG state (snapshotted
  at the seat's priority event) and the seat's own chooser.
- zsh: `rm -f dir/prefix.*` with no match aborts the whole `&&` chain (nomatch).

## Next session picks up

- The forkcheck's verdict → the fork pin; the shakedown relaunched (`anvil.runs relaunch --name
  shakedown`) the moment the chain's DONE lands.
- The documentation pass (Build order 4¾) beside the alloc / shallow / deep arms.
- At the big run's launch ADR: delete `CensusRun -certify` + `PayDirective`; re-certify
  `payment-evalset-v2` through the witness pair first.
- Routed: a `-search` front over a stored WINDOW (re-search at higher budget; the pick hook is its hook
  point); the diverged class's attribution (RNG vs AI memory) if a re-certification needs it.
