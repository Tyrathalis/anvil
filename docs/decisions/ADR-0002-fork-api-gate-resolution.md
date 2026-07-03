# ADR-0002: M0 measurements resolve the fork-API gate — promoted, sequenced before M2

- **Date:** 2026-07-03
- **Status:** accepted
- **Design-doc anchor:** §9 (state forking, throughput), §15; resolves the gated bet from [ADR-0001](ADR-0001-prior-work-responses.md) §2

## Context

ADR-0001 queued a gated bet: *if the M0 soak and fork-fidelity numbers come back ugly, a stable copy/enumerate/apply single-step API for Forge is promoted from risk-mitigation to flagship upstream contribution.* Both measurements are now in, plus the multi-worker scaling curve (M0's games/hour deliverable). All data from fork commit `8907112` (Forge upstream pin `0bfdaa5`), Commander precons (Abzan Armor TDC / Arcane Maelstrom C20), heuristic-vs-heuristic, seeded; harness is `forge forkcheck` (see [fork-fidelity-test.md](../design/fork-fidelity-test.md)); raw data in `data/forkcheck/` and `data/soak/scaling-20260703/`.

### Measurements

**Soak (2026-07-03 overnight, 6K games/8.2h):** leak-free; prior devlog. Gate input #1: clean.

**Fork fidelity (4 × 500-game runs):** fork a live game at a quiescent active-player MAIN1 priority point, replay with byte-cloned `MyRandom` state, diff per-turn state digests vs mainline.

| Run | Variant | clean | trajectory divergence | static mismatch |
|---|---|---|---|---|
| 1 | v1 semantics | 38% | 50% | 12% |
| 2 | v2 (AP-priority-only forks) | 38% | 50% | 12% |
| 3 | v2 + fresh RNG in fork | 14% | 74% | 12% |
| chain | v2 + F2=copy(F1), replay both | 37% | 51% | 12% |

- **Zero crashes in 2,000 forks.** `GameCopier`'s instability is entirely *silent state drift* — worse than crashing for training purposes (silent data poison), and invisible to upstream's existing single-point score check.
- **Divergence is deterministic:** a divergent seed reproduces its exact divergence (turn, first-diff, both outcomes) across fresh JVM invocations (3/3 repeats + original). This exonerates wall-clock effects and identity-hash iteration order for the bulk of divergence, implicating **copy-construction insertion order** (deterministic per-structure). Every divergent seed is a bisectable repro.
- **Mainline forward-play is seed-deterministic across JVMs** — validates "seed everything; deterministic replay" on the Forge side.
- **RNG cloning is necessary but not binding** (run 3): removing it costs 24 points of fidelity (38→14% clean), but with a perfect clone half of games still diverge. A fork API therefore needs *both* RNG state capture/restore (upstream has no such concept — `MyRandom` is a bare singleton) *and* deterministic construction ordering.
- **Copying canonicalizes (chain run):** 94.6% of second forks reproduce the first fork exactly; among F1-divergent games, 96%. **Fresh drift per additional fork: 2.4%** — the compounding noise floor for repeated forking.
- **Two static bug classes, no long tail** (12% of copies, stable across runs, seed-reproducible): (a) face-down/hidden exiled cards come back face-up in the copy (~75% of cases; information leak — a search rollout could "see" hidden cards); (b) duplicated "Keyword Effects" object in the Command zone (~25%; **compounds per copy** — 25% of static-mismatch games re-corrupt on recopy).
- Copy cost: median 6 ms, p99 9 ms per fork. Cost is a non-issue.
- Divergence manifests a median of 6 turns post-fork, typically first visible as library order (an earlier decision delta desyncing the shared RNG stream at the next shuffle); 57% of divergent games still reach the identical final outcome — equivalent-but-not-identical play.

**Scaling curve (1/2/4/8/16 JVM processes, 2 GB fixed heaps, 300 games/worker):**

| workers | games/h/worker | total games/h | per-worker efficiency |
|---|---|---|---|
| 1 | 922 | 922 | 100% |
| 2 | 677 | 1,354 | 73% |
| 4 | 688 | 2,750 | 75% |
| 8 | 375 | 2,998 | 41% |
| 16 | 242 | **3,866 (64 games/min)** | 26% |

Monotonic total throughput — **MageZero's shared-heap collapse does not occur with process-per-worker.** Efficiency staircase is consistent with boost clocks + split-L3 (7950X: 2 CCDs × 32 MB) under ~2.3 GB/game allocation traffic; GC-thread oversubscription (each JVM sizing for 32 CPUs) is a suspected co-factor under test in the extension sweep (w=16/20/24 with `-XX:ActiveProcessorCount=2`), results to be appended to the devlog.

## Decision

1. **The gated bet fires: the stable fork API is promoted to flagship upstream contribution**, sequenced as a prerequisite for M2 (Grindstone/ddmin/pivotal-turn search) — *not* as an immediate detour. Nothing before M2 forks; M0/M1 are unblocked (forward-play is leak-free, deterministic, and fast). Evidence package for the upstream conversation: this ADR + ~250 deterministic divergence repros per 500 games + the forkcheck differential harness. The API's now-evidenced requirements: deterministic copy-construction ordering, RNG state capture/restore, and the two bug-class fixes.
2. **The two static bug classes get root-caused and fixed immediately post-M0 as upstream PR #1** (small, surgical, differential-tested — the credibility-builder ADR-0001 wants before the larger fork-API PR). The ~60-seed repro set is the test suite; the fork carries the patches locally if upstream review lags. The compounding duplication bug is priority within the pair.
3. **Interim workarounds, effective now:** (a) *fork-at-start* — copying canonicalizes, so systems that will compare forked branches should play reference games in copy-space from turn 0/1, where the static bug classes also mostly cannot occur (to be verified empirically when M2 work starts); (b) *digest tripwire* — any workflow that forks digest-checks the copy (~6 ms) and flags corrupted forks; (c) repeated-fork designs budget for the 2.4%/fork drift floor.
4. **Throughput target met pre-optimization; hardware purchase declined.** 64 games/min ≈ 92K games/day on the existing box vs §15's "10+ games/min on 32 cores post-optimization." Phase-1's ~500K-game corpus ≈ 6 days wall clock. The "buy a 32-core box" budget line (deferred at the 2026-07-03 planning checkpoint pending this curve) is **closed: not needed.** Allocation profiling remains the top throughput lever (per-worker efficiency 26% at w=16).

## Consequences

- M0's measurement set (games/sec, soak, fork fidelity) is **complete**. Remaining M0 scope: bridge protocol draft (ADR-0001 invariants) + `PlayerController` override plan; the harness spec inherits the disposable-workers/pause-resume conventions (design §9) and the scaling sweep's worker-count/JVM-flag defaults (pending extension sweep).
- M2 planning gains a hard dependency: fork API (or at minimum the local ordering+RNG+bug fixes) lands before search/ddmin/drills. Mentor counterfactuals additionally get the fork-at-start pattern for branch-vs-branch comparisons.
- §15 recalibrations: throughput risk revised sharply down (target beaten 6× pre-optimization); "GameCopier fragility" converts from open risk to *characterized, bounded, deterministic* — with a measured 2.4%/fork noise floor and a fix path. The Rust-subset phase-two bet loses urgency on throughput grounds (its other motivations stand).
- The forkcheck harness is a permanent asset: fidelity regression gate for every future Forge version bump (fork discipline: engine upgrades are dataset boundary events — now with a fidelity check attached).
