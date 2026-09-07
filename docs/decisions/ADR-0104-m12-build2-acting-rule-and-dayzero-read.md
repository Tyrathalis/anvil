# ADR-0104: M12 Build 2 — the search directive as the behavior policy (the acting rule), and the day-zero read moved to the 2,000-game instrument

- **Date:** 2026-09-06 (session 6)
- **Status:** accepted — day-zero read IN-BAND (addendum 09-07 11:01)
- **Design-doc anchor:** m12-plan.md Build 2 (the one gate) + canonical shape §2 (the acting
  rule) + fork C (sampled behavior); ADR-0101 §3 items 2/4/5 (four arms, band rules, the
  control-arm rule); ADR-0102 (the directive), ADR-0103 addendum (the margin distribution)

## Context

Build 1 read GO (one-ply 0.397 cross-fit) and the day-zero smoke on the sharpened head put the
margin bracket at 0.05 / 0.10 (margin ≥ 0.05 at 19.5% of searched windows, ≥ 0.10 at 11.5%).
Build 2 owed three things: the ACTING rule (the directive was telemetry-only — the controller
completed every searched row with the natural pick and played it), the pins the smoke could
not set (bar, temperature, rate, rolls), and the day-zero paired read.

What the tree held against the pinned read instrument (the ADR-0094 fork-window paired read,
K=8 completions from a fixed 800-window population, CRN across arms):

- The search monitor subscribes to the MAINLINE game only (`AnvilRun.SearchMonitor`, one per
  game); the read's completions are GameCopier copies served through the drill backend and
  the monitor never sees them. Searching inside a completion means a monitor per completion
  copy, search copies of completion copies, session ids routed to both the drill (".f") and
  search (".s") paths, value asks routed to the drill net, plus the census regeneration on the
  boundary jar (the mask changed the game path; the sv=2 census cannot replay) and a fresh
  replay-parity proof.
- The monitor searches every bridged seat holding priority on its own turn — in self-play
  completions both seats would search and the with-lookahead arm would read ≈ 0 by symmetry.
- The plan names the reference arm as "`iter-019` alone (the 0.5279 reference)" — a number on
  the 2,000-game-vs-heuristic scale — while pinning the fork-window instrument, whose
  completions are self-play from mid-game states. The bars and the instrument were on
  different scales.
- The heuristic + lookahead control arm is new Java surface either way: heuristic seats are
  not `PlayerControllerAnvil`, their priority pick is not an option-list index, and nothing
  forces a pick onto them.

## Decision

1. **The instrument is the standard 2,000-game read vs the heuristic** (`final_read.py`: the
   same pairs file + seed base per arm, seats 0/1 bridged in turn, argmax serve, `-reask`;
   arms diffed game-by-game, the `paired_arms.py` estimator). Seat scoping is free (heuristic
   seats are never searched), the day-zero checkpoint serves the mainline policy, the copies
   and the leaf values from one server, and the bars sit on the scale that defines them.
   User decision 09-06 s6 over the pinned fork-window read; the fork-window integration is
   routed by name as a Build 5 mid-run health instrument (per-window value-bin cuts), not a
   gate. The Ante pass is skipped on the arms (the diffs read raw wins; the corrected
   number is the closeout's, not the gate's).
2. **The acting rule** (`SearchDirective.Pending.decide`, applied by the controller AFTER its
   natural ask): margin = max V − V(natural) over the first ply's valued candidates; margin ≥
   bar → the option is SAMPLED from the softmax of the candidates' mean leaf values at
   temperature T (the natural line stays in the distribution — fork C, exploration + a
   behavior logp for PG); below the bar the natural pick stands. Unvalued candidates (every
   roll void / crash / unserved) are never sampled. A sampled pass returns pass; a sampled
   option is realized by a single-option forbid-decline re-ask (the search copy's W_FORCE
   shape, the network fills targets / X / modes / payment); a veto at apply, a pass despite
   the mask or an absent option falls back to the natural line, counted (`applied:act_void`).
   The natural pick absent from the candidate set (a mana ability, or beyond `-searchopts`)
   or unvalued = no act, counted (`by:nat_unsearched` / `nat_unvalued`). The sample draw is one
   splitmix64 step on (game seed, turn, window ordinal) — never the game's RNG stream, so a
   replay samples the same option and the flag-off path is untouched.
3. **Pins:** bar **0.05** for the gate arm (acts at ~20–24% of searched windows) with **0.10**
   as the bracket's second arm; **T = 0.025** (an option one 0.05-bar below the best keeps
   ~13% weight, 0.10 below ~2%; T = 0 is argmax); **rate 1** (every quiescent own-turn
   MAIN1/MAIN2 window — no pivotality gating until a run's margins exist to train it on);
   **rolls 1** (one determinization per candidate, the smoke's basis); the surface expansion
   OFF (Build 3 attributes its surfaces through per-tag reads, ADR-0097); mana abilities
   excluded from candidates (ADR-0102). Flags: `-searchact <bar> [-searchtemp <T>]
   [-searchseats <csv>]`.
4. **Provenance:** every game header carries a `search` object (rate, rolls, opts, mana, surf,
   surfcap, bar, temp, seats); every searched row carries the verdict (`by`, `margin`,
   `act`, `act_o`, `logp`, `p`, `applied`); the harness records the verbatim AnvilRun flags
   (`forge_args`) in `run.json` — arms under different flags are different behavior policies.
   The store consequence, deferred by name to the shakedown's loader work: an ACTED window
   carries two priority decs (the natural ask over the full option list, `by=bridge`, then
   the forced re-ask over one option, `by=search`); the search row is the label and the
   first dec is the state.
5. **Arms:** `ref` = `iter-019` alone re-read on the Build 2 jar (the boundary changed the
   game path; never compare across eras), `dz` = the day-zero ckpt alone (policy drift ≈ 0
   expected), `dzla` = the day-zero ckpt + lookahead at bar 0.05, `dzla10` at bar 0.10. The
   heuristic control arms (`heur` = the heuristic mirror, `heurla` = heuristic + lookahead)
   follow on their own exempt fork commit; the control rule (ADR-0101 §3 item 5) interprets
   the gate, never gates it, so it trails. **Mechanism:** both seats already carry
   `PlayerControllerAnvil` (a heuristic seat = empty tag set), so an explicit `-searchseats`
   overrides the bridged requirement and names the heuristic seat; on copies the
   heuristic honours the directive with its own realization (`canPlaySa`), every
   intermediate decision is the heuristic's, the masked head values the leaf; on the
   mainline the sampled option is played through the same realization (no network plan).
   `final_read.py --heuristic-control` = no seat bridged + `-searchseats <seat>` per seat
   run; the reader keys the win on that seat (`scripts/build2_control_read.sh`).
6. **Bars unchanged:** dzla − dz ≥ +1.5pp GO / ≤ 0 KILL-CANDIDATE / in-band proceeds and blocks
   the Build 5 launch until a post-Build-4 read clears +1.5pp. **Power statement:** 2,000
   paired games per arm; the per-game paired diff has SD ≤ 0.71 (independent wins) so SE ≤
   1.1pp, ~0.9pp with the seed pairing the M3/M4 reads showed — the +1.5pp bar sits at ~1.5
   SE, the kill line at ~1.5 SE below it. This read resolves GO from KILL-CANDIDATE; it does
   not resolve GO from in-band at two SE, which the band rule already tolerates (in-band
   proceeds). Read cost: ~80 min per plain arm at eight workers, ×~3 wall with search (the
   smoke: 33 s/game vs ~11).
7. **The jar is snapshotted** into the read directory and pinned by sha in every arm's
   manifest, so the control-arm Java lands in the fork while the arms are in flight; the
   forkcheck of the control commit waits for the read to finish (CPU contention changes the
   server's micro-batch composition — the near-tied-pick drift class).

## Consequences

- Fork: `SearchDirective.Pending` (the acting rule + the row completion),
  `PlayerControllerAnvil.chooseSpellAbilityToPlay` (the verdict applied; `searchForcedAsk`),
  `AnvilRun` (`-searchact/-searchtemp/-searchseats`, `Obs.searchPins`, the seat check, the
  labels sink null-safe), `Obs` (the header's `search` object); `SearchActTest` (7 cases: the
  classes, argmax at T = 0, the seeded softmax's sampling rate, unvalued never sampled, the
  row). ADR-0025-exempt with the flag off: forkcheck vs the 08-21 seeds in the addendum.
- Anvil: harness `--forge-args` / `--labels` / `--jar` (manifest `forge_args`, `labels`);
  `final_read.py --forge-args/--labels/--jar/--skip-ante`; `scripts/build2_act_smoke.sh`,
  `scripts/build2_read.py` (smoke + arms: acting telemetry, paired diffs, the gate verdict),
  `scripts/build2_dayzero_read.sh` (the detached chain: jar snapshot → ref → dz → dzla →
  dzla10 → read → notify; resumable per arm).
- Standing rule born here → standing-rules.md: **a gate's bars and its instrument share one
  scale — name the instrument beside the bar, and check it can run every arm before the
  bar is set** (the day-zero read was pinned at K=8/N=600 on the fork-window read while its
  reference number lived on the 2,000-game read, and the instrument could not search inside
  its own completions).
- Routed by name: the heuristic control arms (the next fork commit); the fork-window search
  integration as a Build 5 mid-run health read; the acted-window store rule (two decs per
  window) to the shakedown's loader; the pivotality head's first fit on the arms' margins
  (labels free at every searched window) to Build 4½; the temperature as a budget knob on
  the scaling curve (fork F).

## Addendum (2026-09-06, session 6, 23:16): the exemption proof and the launch

- **Forkcheck (flag off):** 498/500 main-trace hashes identical to the 08-21 baseline (`run-20260906-build2-act`; fork fidelity 448/52 vs 450/50); the two misses are the standing pair — 20260969 (launch-unstable) and 20260739, which replayed twice on the same jar to the baseline hash `9e0365815606ddf6` (the identity-hash residual) — **PASS at the ADR-0025 standard; the research fork pin moves to `103747691cc`**. Fork commit `103747691cc` (the jar built from that tree; the smoke on it: 353 windows, act rate 24%, applied act 70 / pass 9 / act_void 2, 0 crashes).
- **Launched** 23:16 09-06, `scripts/build2_dayzero_read.sh` detached (chain pid 1872752, watchd `build2-dayzero` stall 60 min + each arm's own `b2-<arm>-read` registration, notify on completion / failure), jar snapshot `data/runs/build2-dayzero/forge-build2.jar` (sha `812ea09e…`, pinned in every arm's manifest); arms ref → dz → dzla (bar 0.05) → dzla10, 2 × 1,000 games each at eight workers; ETA ~80 min per plain arm, ~2.5 h per search arm → the read lands ~07:00 09-07 in `data/runs/build2-dayzero/read.json`. The heuristic control-arm code (item 5's mechanism) is committed in the fork as `1d4b2d817c3` (compiles; unproven); its forkcheck and `build2_control_read.sh` run after the read finishes.

## Addendum (2026-09-07, 10:50): the loop game and the loop guard

- **The loop game (09-07, 09:51–10:56):** the dzla10 arm's game 989 spent 65 min in one MAIN1 window — the bridged seat activated Dark Sphere's prevention ability with an empty stack, `ChooseSourceEffect`'s unbounded `do … while (o == null)` re-asked the AI's `NeedsPrevention` chooser (which only answers from the stack or unblocked attackers) 150K+ times, no priority pass so no cap could count it, and the wall-clock guard under search sat at 300 + 3,600 s. The heuristic never enters that state (its `canPlayAI` gates the activation); a learned policy picking from the legality mask does — the same shape as the Cabal Coffers refund bug (engine code assuming the AI's own gating). **Fixed in the fork (`b4825285529`, user-approved 09-07):** the engine re-ask bounded (two attempts, then the first real source — upstream PR candidate, `upstream-worklist.md`); `Census.loopCheck` — consecutive identical controller callbacks per game past 256 cap the game as a Draw with reason `loop:<method>` and the Surfaces force hooks answer the first option so any such loop exits (counted like a cap; the 0.5% tripline reopens repetition detection); the search allowance on the wall-clock guards 3,600 → 900 s. Replay of the loop game on the fixed jar: 20 turns, 36 s, exactly two source asks per activation. Routed by name to the shakedown: a state-hash repetition detector at priority grants for model-driven no-progress cycles (bounded today by the window cap); a per-turn discount as the training-side answer to progress-without-winning (token doubling), not a guard. One clock hit in ~8,000 games — under the tripline.

## Addendum (2026-09-07, 11:01): the day-zero read — IN-BAND

`data/runs/build2-dayzero/read.json` (chain 23:16 → 11:01; 8,000 games on the snapshot jar of `103747691cc`):

| arm | games | winrate vs the heuristic | vs `ref` (paired) | vs `dz` (paired) |
|---|---|---|---|---|
| `ref` — `iter-019` alone (Build 2 jar) | 1,984 | 0.538 ± 0.011 | — | — |
| `dz` — day-zero ckpt alone | 1,972 | 0.522 ± 0.011 | −1.63pp ± 1.15 (t −1.4) | — |
| `dzla` — day-zero + lookahead, bar 0.05 (**the gate arm**) | 1,974 | 0.530 ± 0.011 | −0.77 ± 1.20 | **+0.92 ± 1.10 (t 0.8)** |
| `dzla10` — bar 0.10 (the bracket's second arm) | 1,978 | 0.538 ± 0.011 | −0.10 ± 1.21 | +1.58 ± 1.04 (t 1.5) |

Acting telemetry (75K / 72K searched windows): bar 0.05 acts at 15.4% of windows (applied act 12.0%,
pass 2.9%, `act_void` 0.11%), bar 0.10 at 9.0% (act 7.4%, pass 1.5%, void 0.06%); sampled ≠ argmax
19% / 14%; margins p90 0.086 / 0.092, ≥ 0.05 at 15.6% / 16.5%, ≥ 0.10 at 8.5% / 9.1% (lower than
the 40-game smoke's 19.5% / 11.5%: the heuristic opponent's boards are narrower than self-play's);
`nat_unvalued` 1.4–1.5%; leaves 70% / void 29%; forward-call multiplier **1.76× / 1.74×**, wall
**2.09× / 2.07×** at eight workers; ms per window p50 260 / p90 1,050. Drops: 16 / 21 / 10 / 9
draws (caps), 7–16 crash-or-hang games per arm (gRPC deadline under search load, the copy NPE
class, one StackOverflow) — pairs drop, n stays ≥ 1,956.

**Verdict: IN-BAND on the pre-registered gate arm** (dzla − dz = +0.92pp, inside (0, 1.5)): Build 3
proceeds; **the big run cannot launch without a post-Build-4 read ≥ +1.5pp**; the value-head pass
for that re-read (ADR-0101 §3 item 4) = one more banked-label fit + this run's own composites.
Read honestly: the bar-0.10 arm sits at +1.58pp on the point estimate, but it is the bracket's
second arm, not the gate arm, and a post-hoc bar pick is exactly what the pre-registration forbids;
what it says is that the acts between margins 0.05 and 0.10 are net negative (≈ −0.7pp ± 1.0 for
~6% more acted windows) — the bar for the shakedown starts at 0.10, pinned before that read.
Two facts beside the gate: (1) **the day-zero checkpoint alone reads 1.6pp below `iter-019`** (t −1.4)
despite 99% argmax agreement on held-out windows — the value-head pretrain cost policy strength
at the ~1% of windows that differ, and the with-lookahead arms only recover to `ref`'s level
(dzla10 − ref = −0.1pp); network-alone for Build 5 therefore starts from `dz`, below the reference,
and the post-Build-4 re-warm is read against `ref`, not `dz`. (2) The search multiplier at eight
workers is 1.75× forward calls and 2.1× wall against the heuristic — lower than the self-play
smoke's 2.4× (one seat searches; half the windows) — the Build 5 sizing number for a
vs-heuristic population; self-play doubles it.

## Addendum (2026-09-07, 11:20): the combined tip proven; the control chain launched

- forkcheck `run-20260907-build2-control-loop` 498/500 vs the 08-21 seeds (fork fidelity 449/51), the standing two misses, 20260739 replays to the baseline hash `9e0365815606ddf6` twice on the same jar — **PASS; the research fork pin moves to `b4825285529`** (the control arm `1d4b2d817c3` + the loop guard).
- **Control chain launched 11:20 09-07** (`scripts/build2_control_read.sh`, chain pid 519465, watchd `build2-control` + per-arm registrations, notify on completion; jar snapshot `data/runs/build2-control/forge-control.jar` sha `8a5aab9c…`): `heur` (no seat bridged, `-searchseats` names the read seat, no search) then `heurla` (bar 0.05 / T 0.025 / rate 1), read against the day-zero arms; ETA ~14:40.
