# ADR-0055: D3 era boundary closed — new standing gate 0.5373 ± 0.0112 on the rebased + hardened engine

- **Date:** 2026-08-12 (overnight close of the 2026-08-11 boundary work)
- **Status:** accepted
- **Design-doc anchor:** fork discipline (engine upgrades are dataset
  boundary events); m7-plan D3; ADR-0025 (the rebase-as-boundary
  precedent); ADR-0054 (the λ change riding this era)

## Context

m7-plan D3 scheduled one consolidated era boundary before the C-bundle
run: the carried fork stability pass, the ADR-0054 λ re-tune (a reward
change = RL-chain boundary), the forced-seq harness extension, and — per
the user's call — an upstream rebase to collect ~2.5 weeks of drift.
Late in the window, Talor-A/anvil#9 (grpc off-by-one after >5s
responses) was confirmed and fixed, and the user chose to restart the
re-baseline so the fix rides inside the pinned era (free: the session
crash had killed the v1 handoff before the read started).

## The era

**Fork pin: `d798917ae5`** (research master, pushed). Contents over the
prior era: upstream rebase (210 commits, 45 fork-local replayed, zero
conflict stops; #11436 gives the heuristic depth-zero simulation
validation — GameCopier now hot in normal games), the stability pass
(GameCopier effect-source links `b361dfcb8f`; STATION tap-guard
`9f0a2c0886`; MinMaxBlocker already fixed 07-25; targeting-retry closed
as bounded), monarch set-code NPE (`46c0c0893e`), forced-seq labels-row
extension (`b3b33f153a`), and the #9 protocol fix (`d798917ae5`:
decision_seq verification + poisoned-stream drain on all three decision
paths; GrpcBridgeSeqTest pins the invariant incl. the cross-game
clause). Anvil side: #4 format sweep (mu-determinism-gated, 1,408 mu
records byte-identical) + #8 multi-format pool scaffold.

## The read

**New standing gate: 0.5373 ± 0.0112** (`d3-rebaseline`, 1,999 games,
iter-019 vs the current heuristic, standing final_read protocol).
Supersedes 0.5316 ± 0.0110 per m7-plan's "subject to the D3
re-baseline" clause. Statistically indistinguishable from the old
number — iter-019 holds through the rebase despite the stronger
heuristic path, unlike the two prior boundaries (both of which the
heuristic moved). Run hygiene: **0 crashes in 1,999 games** (prior-era
reads carried 2–3 — the stability pass visible in production), 0
bridge-poison events, 0 deadline events (the #9 validity condition
holds trivially; with the fix it would have self-healed anyway).

## Fork fidelity

Post-rebase forkcheck (500 games, default mode): **442 clean / 58
divergence = 11.6%**, statics still 0, vs the 7.0% prior-era reference.
Prime suspect for the rise: #11436's simulation validation puts
AI_TIMEOUT-sensitive evaluation on the heuristic path — the documented
twin-nondeterminism residual, now exercised more often. The
`FIXED_HASH=1` discriminator pair is running (results annexed below
when complete); the 11.6% stands as the era's fidelity characterization
either way. Fork-rollout instruments (drill maps, forced-branch,
forced-seq) inherit this rate; the ADR-0052-era corrected-population
machinery is unaffected in kind.

## The #9 blast-radius sweep (owed from the fix)

Per-invocation sweep of all 22 affected worker logs: **suspect label
rows ≤ 181 total** (whole-invocation upper bounds). 84 sit in the
parked July `d4-rollout-pilot` (never consumed); the remainder scatter
≤15 rows per invocation across the drill/labeling era. The 140-event
drillo1 worker produced only 2 label rows — post-desync answers were
garbage, so games crashed rather than yielding labels (the bug
self-limited). Verdict: **no standing conclusion is threatened** —
affected rows are ≤~2% of any label population and inject noise, not
bias. Training-trajectory stores: zero events all-time. No re-runs; the
c2 labelset annotation stands in this ADR in lieu of per-row exclusion
unless a future re-fit motivates it.

## Decision

1. The standing headline gate for M7's C-bundle run is **0.5373 ±
   0.0112** on fork era `d798917ae5`. All bundle-run numbers compare
   against it via the standing combined paired read.
2. The λ re-tune (first-attempt-only + λ=0.01, ADR-0054) is licensed:
   its RL-chain boundary is this era; the next mixture starts fresh.
3. Store-format era notes carry forward: FORK_G_BASE namespace
   (`a73ee9d4e4`) and the labels-row extension are in-era; never mix
   pre/post-base stores in one MultiStore join.

## Consequences

- The C-bundle build (rl.py L_seq + masked-head aux, finetune_value
  C2a aux, first-attempt-only port, selfplay forced-seq phase) targets
  this era. Per the user-pinned sequencing, the DOCUMENTATION CLEANUP
  PAUSE precedes it, and the ADR-0049 instruments are owed before the
  run (their baseline read = the d3-rebaseline stores).
- Upstream filing queue off the fresh base: STATION tap guard,
  GameCopier effect-source, monarch NPE; #9's unary-Decide RPC and
  control-message dispatch split are noted for a protocol v1 rev.
- Watch-list items armed: targeting-retry re-open trigger (wedge row in
  a corrected-era campaign); mask-cache re-enable still gated on the
  obs-diff protocol if ever wanted.

## Annex: FIXED_HASH discriminator — RESOLVED (2026-08-12): the
divergence is DETERMINISTIC copy-state divergence, not nondeterminism

The FIXED_HASH=1 pair returned **the identical tally AND the identical
game set: 442/58, all 58 seeds shared with the default-mode run** — and
the killed v1 forkcheck (pre-#9 jar, `46c0c0893e`, 437-game prefix)
agrees 49/49 on its shared seeds. Three runs, two jars, two
identity-hash modes, one divergent set: the 11.6% is a fully
deterministic, seed-stable copy-vs-mainline divergence class — NOT the
hash-iteration class and NOT wall-clock (either would vary across
launches). Divergence samples show generic downstream symptoms
(library-order/zone/life diffs at the first divergent state), so the
root mechanic needs trace-diff forensics: prime suspect remains
rebase-introduced state that GameCopier does not carry (e.g. #11436's
simulation bookkeeping or another new upstream mechanic), in the same
family as the effect-source gap this era fixed.

Disposition: **queued on the upstream-worklist as a diagnosed-class
entry; does not reopen the boundary.** The era is characterized
(statics 0, the set is stable and enumerable — the 58 seeds ARE the
repro list), fork instruments inherit a known rate, and the
corrected-population machinery re-prices drill labels from true
rollouts regardless. Forensics slot: with/after the GameCopier→
GameSnapshot consolidation work, using the recorded first-divergence
snapshots.
