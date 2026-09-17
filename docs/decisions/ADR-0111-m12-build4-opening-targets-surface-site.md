# ADR-0111: M12 Build 4 opens — the ability table extended across an engine boundary, the representation scope pinned, and the target surface's real site (the AI's own trigger preparation, not the controller callbacks)

- **Date:** 2026-09-16
- **Status:** accepted (user, 09-16 session 3: the order and the full representation scope; the
  mask-cache re-read)
- **Design-doc anchor:** §3d′ (the coverage ledger), §1–§2 (representation), §6 (search as the
  behavior policy); [m12-plan.md](../design/m12-plan.md) Build order 4; amends
  [ADR-0109](ADR-0109-prelaunch-completeness-audit.md) item 1 (the site) and
  [ADR-0110](ADR-0110-m12-upstream-merge-20260916.md) (the table's extension, the mask-cache gate)

## Context

Build 3 closed with six surfaces served; the upstream merge landed with the fork pin `8137d0c41c`,
the reference `iter-019` 0.5348 ± 0.0110 and 16 ability keys the merge added outside the served
table. Build 4 = the last representation and coverage work before the post-Build-4 read and the
shakedown ([ADR-0109](ADR-0109-prelaunch-completeness-audit.md): targets as a surface first, then
the allocation head). Three questions were open at the session: the order of Build 4's parts, how
much of the representation item to carry (the user: format readiness is nice for the external
projects but not essential), and whether the mask cache's routed re-read is worth a box slot.

## Decisions

1. **The order:** the ability table → the targets evening on the current trunk → the three
   representation items under ONE re-warm → the allocation head fit on the re-warmed trunk → the
   post-Build-4 read. The re-warm is the shared expensive step and is paid once; the allocation head
   fits last so it is not refit twice.
2. **The representation scope = all three items, no trim.** The finding that decided it: the obs
   already records every stack instance (host, controller, label, targets) but the encoder consumes
   one scalar of it, `stack_size` — so stack-entry tokens are a STRENGTH item for the network-alone
   windows (instant speed, the opponent's turn: no lookahead there), not readiness. The string-id
   `sa_emb` is still the trunk's candidate embedding (Build 3's hash-keyed table is the surfaces'
   key only). Format-as-features is a Python-side lookup from the format id already on every row
   plus a small learned embedding: zero fork delta, inert for a single-format run, rides the same
   re-warm; what helps a one-format external project is the onboarding doc (the documentation
   pass), not the feature.
3. **The ability table across an engine boundary is EXTENDED, never rebuilt:** the served table's
   rows are copied byte-identical (row indices kept), only the keys the new dump adds are embedded
   (the model revision checked by re-embedding a sample of base rows, cosine 1.00000), keys the new
   engine dropped stay (the banked stores carry them; the re-warm reads those stores). `abil-cf2ca6ba-b4-qwen3`
   (15,489). `anvil.bridge.server --abilities <stem>` serves a superset table to an older build, so a
   paired read's reference arm carries no OOV confound (`scripts/extend_ability_table.py`; the same
   script folds a pool's side-table keys with `--stores`).
4. **The mask cache stays OFF, closed for the era:** the ADR-0102 re-read on the merged jar at one
   worker, 108/120 identical, 9 mask-class first divergences on the same four callbacks. Not chased
   before the run (the memo already took most of the mask's cost).
5. **The target surface's real site is the AI's own trigger preparation.** ADR-0109 named the
   controller callbacks (`chooseTargetsFor` / `chooseNewTargetsFor` / `chooseTarget`); the 4-game
   smoke on that tip recorded 47 `playTrigger` rows and 3 `chooseTargetsFor` — the AI targets its
   triggers inside `doTrigger` (`PlayerControllerAi.prepareSingleSa`, the effect logic), and the
   engine's `setupTargets` loop that calls the callback is the human / copy path. The hook:
   `PlayerControllerAi.preparedTrigger(sa)`, a protected no-op between a trigger's preparation
   (modes chosen, targets picked, every other decision made) and its play, at both sites
   (`playTrigger`, `orderAndPlaySimultaneousSa`) — the first fork delta in that file, two call
   lines and an empty method. The census controller overrides it: one TARGET window per targeting
   ability in the prepared chain (`playTriggerTargets`; the legal-target set = the engine's own
   `TargetRestrictions.getAllCandidates` with the targets cleared as `setupTargets` does, then
   restored; min/max from the restrictions; no window for divided-amount targeting), the
   heuristic's picks = the natural line, a directed / bridged answer re-targets the ability pick by
   pick under `canTarget` + `isTargetNumberValid` (else the picks stand, directive miss `legal`).
   Everything else the trigger logic decided is kept — the joint mode + target choice ADR-0109 wants
   without re-implementing the effect AI. The callback hooks stay for the paths they own. The smoke on
   the hook: 89 windows / 4 games (≈ 22 per game — the largest deferral, as sized), copies force
   them, 0 crashes. The answer shape = the entity set (`surf_target`, a new task on the shared
   option-set decoder; the wire tag `mtg.surface.target`).
6. **The third arm's switch:** `AnvilRun -modegate off` lifts the mode playability gate
   (serve-only, default on). The evening's read = off (the new build with the target tag withheld =
   today's served set) / on (+ targets, gated mode) / nogate (+ targets, gate off), 300 games per
   seat, network alone, one jar. Pre-registered as in ADR-0109: nogate within one SE of on → the gate
   retires; a clear negative → the gate stays and the mode head's loss is attributed on the ladder.
7. **The mode option feature:** each mode option now carries `nt`, its legal-target count (−1 = no
   targets), on MODE windows (the feature routed at evening 2; consumed at the mode head's refit).

## Consequences

- Standing rules born here → [standing-rules.md](../standing-rules.md): (a) **a surface's hook site
  is verified by the census counts before the hook lands** — the engine's controller callback API is
  where a HUMAN decides; the AI decides inside its own logic, and a hook on the wrong site records
  nothing while looking complete; (b) **an ability table crosses an engine boundary by extension**
  (base rows byte-identical, new keys embedded, dropped keys kept), and an older build serves the
  superset through the server's stem override.
- Fork tips: `23b8e36c03` (the callback hooks) → `9438db1146` (test) → `5dd8ab3ede` (the
  preparedTrigger site) → `a36975497b` (`-modegate`); the forkchecks queued (`run-20260916-build4-targets`,
  `run-20260916-build4-gate`). The label pool `b4-tgtlab` (1,000 games, the recipe with surface
  acting, the e3 build serving its six on the b4 table) launched 14:52; the overnight chain
  (`scripts/build4_targets_chain.sh`: ingest → the b4s table → the six-plus-target fit → the build
  `m12-build4-e1` → the served-head smoke → the three-arm read) waits on it.
- Routed: the representation items + the one re-warm (next), the allocation head's served output,
  the mode head's refit on a pool whose copies play model-chosen targets (if the gate retires), the
  upstream note for `preparedTrigger` (a two-line hook; the same shape as `orderSimultaneousSa`).

## Addendum 09-16 15:50 — the retarget tip proven

- `run-20260916-build4-targets` (jar `5dd8ab3ede`, 500 seeds vs the merge baseline): **499 / 500
  main-trace hashes identical, 20260969 the standing seed; fork fidelity 451 / 48 / 1 on both →
  PASS.** The `preparedTrigger` hook + the three callback hooks are behavior-identical with no
  directive and no bridged target tag (ADR-0025-exempt). The gate tip `a36975497b` (the read's jar)
  and the stack-key tip `7343c40d84` follow in the queue; the pin moves when the read's jar is proven.

## Addendum 09-16 16:27 — the gate tip proven → the fork pin `a36975497b`

- `run-20260916-build4-gate` (jar `a36975497b` = the evening's read jar `forge-targets-gate.jar`):
  **499 / 500 identical, 20260969 the standing seed; fidelity 451 / 48 / 1 = the baseline's → PASS.**
  The fork pin moves to `a36975497b` (the target surface + `-modegate`). The stack-key tip
  `7343c40d84` follows (`run-20260916-build4-stackak`).

## Addendum 09-16 17:20 — the stack-key tip proven → the fork pin `7343c40d84`

- `run-20260916-build4-stackak` (jar `7343c40d84`): 499 / 500 identical, 20260969 the standing
  seed; fork fidelity 450 / 49 / 1 vs 451 / 48 / 1 — the one status flip is 20260853, the
  identity-hash residual seed (its main trace identical; its fork replay flips between runs of one
  jar), and **its replay on the same jar is clean and hash-identical to the baseline
  (`run-20260916-build4-stackak-replay853`, 1/1) → PASS** (the standing replay rule). The fork pin
  = `7343c40d84`; every Build 4 fork tip is proven. The evening's read runs on `a36975497b` (the
  stack key is recording-only; the two jars are behavior-identical on the game path).

## Addendum 09-16 17:40 — a Build 3 latent bug: the surface heads trained on a mismatched ability table

- Found when the evening's fit crashed on a separate bug (the surface method embedding lacked the
  OOV row the first never-seen method name needed): `surface_fit.load_net` set the network's ability
  table from the checkpoint config or the module default, while the loaders keyed the options on the
  `--abilities` stem. The Build 3 fits started from the day-zero checkpoint (no stem in its config),
  so e1–e3 trained with the 5,148-row pool table under loaders keyed on the 15,473-row folded table:
  **every store-only key — two thirds of the table, the in-play abilities — trained on the clamped
  last row and served on its real vector.** Fixed (the net's table = the loaders'); tonight's refit of
  all six surfaces + target runs on the corrected path. The evening's three arms share the build, so
  the fix is common-mode in the read; how much of Build 3's served quality it cost is a separate read
  (the ladder vs e3), routed to the post-Build-4 read.
