# ADR-0114: M12 Build 4½ pre-work — route (b) re-scoped: the search's copies realize the model's plan, the void class is the coverage bound (the void-rescue instrument)

- **Date:** 2026-09-19
- **Status:** accepted
- **Design-doc anchor:** §3d′ (the search directive as the behavior policy); m12-plan Build order 4½; ADR-0111 addenda 04:40 / 07:00; ADR-0112 (the banked veto item); ADR-0113 decision 2

## Context

Route (b) was routed at ADR-0111's close as the training-side completion of the re-warm's
finding: "record the realized plan on acted windows and copies, co-distill the target decoder
on them". Its premise, written at 04:40 on 09-17 and carried into the Now block, the standing
rules (the line under ADR-0111) and ADR-0113's routing, was that **a search copy realizes its
forced option through the heuristic's planner** (`heuristicRealize`: the engine's AI plans the
targets and X) while **the mainline realizes the model's pick through its own CastPlan** — so
every leaf value was the option's value under a plan the model never produced, and part of the
with-lookahead advantage was the heuristic's planning of the search's picks, a component the
network alone could not reproduce by learning WHICH option (the Build 5 risk named there).

This session's review (user: "review the state, any decisions before route (b)?") read the fork
and the pools before building, and the premise does not hold on a network arm:

1. **The fork.** A copy's seats get their controllers from the lobby player
   (`AnvilLobbyPlayer.createIngamePlayer`), which carries the same bridged tag set as the
   mainline seat. On a bridged seat the copy's forced window is a single-option
   forbid-decline ask to the MODEL (`PlayerControllerAnvil.chooseSpellAbilityToPlayInner`,
   the `W_FORCE` branch: `options = w.ask; schedForce = true` → `bridge.priorityCastPlan` →
   `CastPlanRealizer.realize`). `heuristicRealize` fires only on an unbridged seat (the
   heuristic-plus-lookahead control arm of ADR-0104 item 5, the `!bridged(TAG_PRIORITY)`
   branch and `searchForcedAsk`'s control path) and behind the flag-gated `-vetofallback
   heuristic` (off). The 09-14 throughput note already said it in passing: "the first launch
   saturated the single model server on network-played copies".
2. **The pool.** On `b4-tgtlab` (69,380 search rows, 1,000 games, the e1 build under the
   recipe) 90,955 of 254,232 first-ply candidate copies voided; **88,395 of the void copies
   made exactly one forward call before ending** — the forced ask, vetoed by the realizer or
   passed despite the mask (a heuristic-realized void makes none). 2,560 made zero (the copy
   ended before the window).
3. **The banked "14% mainline veto rate" (ADR-0112) is the copies'.** The act arm's
   `final_read` census counts 622,084 single-rung one-shot asks against the on arm's 57,729
   — the copies' forced asks are in it — so its 14% vs 4.5% is the void class diluted over
   every copy ask, not a mainline number. The item closes here.

So on every network arm the search values each option under the model's own plan, the
mainline plays that plan (ADR-0113's acted-window label is the plan the value was measured
under — its decision 2 already relies on this), and there is no train/serve plan gap to
distill across. The re-warm's harm mechanism stands on its own evidence (the fallback read:
the heuristic refused 95% of the distilled policy's vetoed picks; the harm scaled with the
dose) and the day-zero decision is unaffected. **What flips is the sign of the Build 5 risk:**
the search does not borrow planning it cannot teach; it is bounded by the decoder it already
has. The void class is the search's coverage bound on a network arm — on `b4-tgtlab` 35.8%
of first-ply candidate copies, **43.8% of spell options, 33.7% of abilities, 1.1% of lands**
— and an option that voids is never valued, so the acting rule can never pick it, whatever it
would be worth. (ADR-0110's void re-roll skip priced this as a copy-fidelity artifact; it is
the decoder's.)

## Decision

1. **Route (b) as written is closed.** On acted windows the plan is already the model's own;
   there is no heuristic plan to distill toward. The record is corrected in this ADR, in the
   standing rule under ADR-0111 (rewritten to the finding above), in the Now block and in
   ADR-0112's banked item.
2. **Its replacement is measured before it is built: the void-rescue instrument, read-only.**
   Fork tip `57337a7e38` on the pin `a37bc6a8b4`: `-searchvoidrescue` — a first-ply candidate
   whose roll-0 copy voided gets ONE more copy on the same roll seed (CRN with every other
   candidate's roll 0) with the forced option realized by the heuristic's planner on the
   bridged seat (`SearchDirective.heuristicForce` → `PlayerControllerAnvil.heuristicForce`:
   `canPlaySa`, the realized plan serialized by `Obs.planJson` in the ret-record idiom, or the
   `AiPlayDecision` refusal); the seat's later windows stay the network's, as on every copy.
   Recorded on the row's option as `vr` (why the forced ask voided: the realizer's veto code
   `no_shape_fit` / `dangling_ref` / `illegal` / `unpayable`, or `pass_masked`, `veto_cap`,
   `no_oneshot`; `heur_refuse` on the control arm) and `h {kind, v, calls, ms, plan, refuse}`,
   **outside the value arrays the acting rule reads** — the arm's behavior is the recipe's;
   census `searchRescue`; header pin `voidrescue`. Search-copy / recording only; off =
   byte-identical (the forkcheck `run-20260919-build4-voidrescue` proves it).
3. **The read (`scripts/void_rescue_read.py`, pre-registered):** the arm = the served build
   `m12-build4-e1a` under the recipe WITHOUT the allocation head (every candidate window
   searched: the most void samples per game) + the instrument, 150 games per seat vs the
   heuristic on the `final_read` pairs, 24 × 2 (`scripts/void_rescue_chain.sh`, launched
   through `anvil.runs`). It answers, in order: (a) the void class by reason and by option
   group, and the rescue rate (what fraction the heuristic realizes to a leaf vs refuses, with
   the refusal census); (b) for the rescued leaves, the value against the window's best valued
   candidate and against the natural line on the same roll seed — the margin distribution, the
   share clearing the acting bar 0.10, and per window whether a rescue would have changed the
   acting decision; (c) the price (rescue forward calls vs the first ply's); (d) the plan census
   (targets / X / plain — where a decoder label would be non-trivial).
   **Decision rule:** the acting extension is built if rescued options clear the bar over the
   best valued candidate on **≥ 2% of searched windows** (≈ a fifth of the recipe's act rate)
   at a price ≤ +30% of the first ply's calls; below that, route (b) closes on the number and
   the void class is banked as the decoder's coverage bound for the loop to close by PG.
4. **If it is built (the original route (b) machinery on the correct subset):** the rescued
   copies' values enter the acting rule as candidates in their own right; an acted rescue pick
   is played on the mainline through the heuristic's plan (the built `-vetofallback heuristic`
   path restricted to acted rescue windows), the acted window's plan label is that plan with
   behavior probability one on the plan factors, and the pick-distillation CE (ADR-0113
   decision 2) extends from the choice to the target and X factors on those windows. Its read
   is a 600-game paired read against the recipe; a rescue copy costs ≈ five calls where a void
   copy cost one.

## Consequences

- The Build 5 kill criterion's named risk is re-signed: not "the with-lookahead advantage is
  the heuristic's planning" but "the search's ceiling is the decoder's coverage" — the
  shakedown's arms are read knowing it, and the void rate by reason is a standing census on
  every recipe arm from here.
- Standing rules (this commit): the ADR-0111 line rewritten; a new line — the search values
  only what the decoder can plan (the void class is a coverage bound, read by reason before
  an arm is sized).
- The documentation pass (Build order 4¾) follows the read; the shakedown after it.
- Routed by name: the act_void reason on the mainline's forced ask (the same `vr` code on the
  `act_void` row — recording only; rides the next fork commit); the mainline veto rate on
  searched arms read from the mainline decs alone (the census field `by` distinguishes them)
  at the post-shakedown read.
