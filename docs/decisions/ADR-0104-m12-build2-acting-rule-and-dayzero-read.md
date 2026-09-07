# ADR-0104: M12 Build 2 — the search directive as the behavior policy (the acting rule), and the day-zero read moved to the 2,000-game instrument

- **Date:** 2026-09-06 (session 6)
- **Status:** accepted (arms launched; the verdict lands in the addendum)
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
