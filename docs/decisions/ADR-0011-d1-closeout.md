# ADR-0011: M2 D1 closeout — fork rollout contract certified; fidelity fixes upstream as PR #1

- **Date:** 2026-07-10
- **Status:** accepted
- **Design-doc anchor:** m2-rl-plan D1 + done-when #1; ADR-0002 (gate this
  resolves); §9 (state forking); playercontroller-override-plan (landmine)

## Context

M2's rollout machinery needs a fork API whose contract is **state fidelity +
determinism, not trajectory reproduction** (m2-rl-plan). ADR-0002 left the
fork "broken-but-characterized": 12% static corruption in two seed-reproducible
bug classes, 50% deterministic trajectory divergence, plus the
`clonePlayer` controller-swap landmine and no certified path for a mid-game
fork to complete under the bridge. D1's done-when: forkcheck clean on the
contract, a mid-game fork completing reproducibly under the model, and the
static fixes submitted as upstream PR #1.

## Decision

**D1 is CLOSED.** All four scope items resolved, one evaporated:

- **Static corruption 12% → 0.** Both bug classes root-caused and fixed
  (fork `42e15f4822`): face-down exiled cards rebuilt face-up (information
  leak, 45/60 repro seeds); Player's seven field-managed effect cards copied
  by zone but never field-wired → compounding duplicates (15/60). 60/60 repro
  seeds + 500-game run clean.
- **Trajectory divergence 49.8% → 13.4% (heuristic) / 2.5% (BC policy).**
  Root cause: GameCopier renumbered card ids in zone-traversal order, and id
  order is AI-visible (`Card.compareTo`, id-keyed collections). Copies now
  keep original ids. Residual = the documented this-turn copy TODOs
  (deterministic, 67 repro seeds, not rollout-blocking).
- **Rollout determinism (twin gate): 99% heuristic (198/200), 100% under the
  BC policy (40/40).** The 1% heuristic tail is hash-ordered iteration in
  decision paths (2 repro seeds; ~40× amplified under the `-bridge`
  random-index stress instrument) — bounds bit-exact replay of single
  rollouts, does not bias averaged rollout labels. The BC policy is a
  fidelity amplifier in the good direction: greedy realistic lines consult
  neither the dropped this-turn fields nor the hash-order paths at
  random-policy rates.
- **Completion under the bridge: certified end-to-end** (fork `3aa1995658`,
  forkcheck `-grpc`): per-game Obs wire sessions give forks observations with
  the store off (store path verified byte-identical); history ring seeded
  from the parent at the fork point; mid-game forks complete under the model
  server with 0 statics / 0 transport failures / 0 fallbacks (50 games + 90
  fork replays).
- **The `clonePlayer` landmine evaporated:** `AnvilLobbyPlayer extends
  LobbyPlayerAi`, so the instanceof check reuses it — forked games keep Anvil
  controllers, verified in play. No code change needed.
- **Throughput priced (the D4 input):** copy 7 ms median; fork→completion
  rollout median 4.4 s / mean 6.3 s / p90 12.9 s at realistic lengths →
  ~70 positions/h/worker at K=8; server measured 59 rps at batch-1.
- **Upstream PR #1 SUBMITTED:
  [Card-Forge/forge#11203](https://github.com/Card-Forge/forge/pull/11203)**
  — the three fixes re-authored on clean upstream (`1eec01434e`,
  conflict-free cherry-pick), three differential regression tests in
  `GameSimulationTest` (each validated failing against the unfixed copier;
  the negative check also exposed a latent NPE: the unfixed copier crashes
  outright when a monarch/blessing effect card is in play), full
  forge-gui-desktop suite green (285 tests). Complies with Forge's
  CONTRIBUTING AI-agents policy (co-author trailer + body note).

Records: `data/forkcheck/run-20260710{,-twin,-grpc}/`. Fork commits
`42e15f4822` / `2e3c7e0c65` / `dc5b46e06e` / `3aa1995658`; PR branch
`gamecopier-fidelity-fixes` @ `2437820aee` (worktree `../forge-pr1`).

## Consequences

- **ADR-0002's interim workarounds retire** (fork-at-start, digest tripwire).
  `forkcheck -grpc` is the standing rollout-contract gate for engine bumps;
  `-twin` is the determinism leg; `-bridge` is the stress amplifier.
- **D4 economics are now priced, and the plan-doc risk is real:** naive K=8
  over 100K positions ≈ 400K game-equivalents ≈ weeks. The D4 pilot decides
  levers in this order: server micro-batching (GPU is batch-1-bound),
  smaller K, short-horizon rollouts, fork-during-generation.
- **Two residual classes stay bounded and documented, upstream-conversation
  material rather than blockers:** this-turn copy gaps (67 seeds; any fix
  must target upstream's new SpellAbility-typed `thisTurnCast` — see the
  worklist drift watch) and hash-ordered iteration in decision paths
  (Forge-wide ordered-collections conversation).
- **PR #11203 is monitored at the start of each session** (worklist standing
  entry; Forge stale-bots idle PRs at ~35 days). On merge, the fixes return
  via the next fork rebase — a separate dataset-boundary event whose anchor
  (#11161) is now concretely merged upstream.
- **D2 (SA-level schema + BC retrain) is unblocked** and next per the plan
  doc's order.
