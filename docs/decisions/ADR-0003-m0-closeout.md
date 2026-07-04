# ADR-0003: M0 close-out — harness measured, schedules recalibrated, M1 sequenced

- **Date:** 2026-07-04
- **Status:** accepted
- **Design-doc anchor:** §13 (sequencing), §14 (budget), §15 (standing probabilities); completes the measurement program of [ADR-0002](ADR-0002-fork-api-gate-resolution.md)

## Context

M0 existed to answer one question: **games/sec with the bridge in the loop** — the number that calibrates every schedule after it (§13). All M0 deliverables have now landed and the measurement set is complete:

- **Batch orchestrator** (Anvil `8b5037c`, fork `80b66aa262`): chunked worker invocations, `run.json` pinning manifests (jar sha256 verified per launch), pause/resume/replay/status/summarize; pause→resume verified with no duplicate or missing games; SplitMix64 keyed seed stream with a Java↔Python lockstep test.
- **gRPC bridge** (fork `4d6f929057`, Anvil `b9ea529`): one bidi stream per worker, six game-agnostic answer shapes, server-driven `bridged_tags`, deadline→heuristic-fallback with provenance.
- **Random-legal agent** (`PlayerControllerAnvil`, fork `56c96c6c40`): M0 tag set bridged, census log doubling as the provenance log.

### Measurements (calibrated three-arm run, 2026-07-04)

w=16, 320 games/arm, chunk 20, quiet box, same seed base across arms; full table in [bridge-protocol-v0.md](../design/bridge-protocol-v0.md):

| arm | total g/h | note |
|---|---|---|
| heuristic-only | 3,016 | 20-game chunks amortize JVM startup poorly; `sim`-based ceiling 3,818 |
| local-random (control) | 1,772 | random-legal games are longer (median 35 turns vs 19) |
| gRPC echo | 1,727 | **bridge tax +2.6% at w=16** |

- **The calibrating number: ~1,700+ games/h with the bridge in the loop** (≈29 games/min, ≈41K games/day dedicated) for random-legal play with the full M0 tag set. This is the *protocol floor* — the echo server answers instantly; M1+ adds model inference latency on top, amortized by server-side batching across 16 workers.
- Zero transport failures in ~200K+ round-trips; one Python server handled all 16 workers.
- Echo-instrument fidelity at scale: 314/320 games bit-identical across transport; all 6 divergences are the known heuristic-fallback nondeterminism floor (identical seeds and winners), consistent with ADR-0002 — not answer mismatches.
- Prior measurements folded in from ADR-0002 and the 2026-07-03 soak: 64 games/min heuristic total at w=16 (monotonic process-per-worker scaling); forward-play leak-free over 6K games/8.2h; fork fidelity broken-but-characterized (2.4%/fork drift floor, two seed-reproducible static bug classes); callback census (priority = 56% of traffic, 45/109 methods live).

## Decision

1. **M0 is done.** Every deliverable in §13's M0 line (batch harness + bridge + random-legal agent) is landed, exercised in anger (960-game calibrated run, zero skips), and measured. No remaining M0 scope.
2. **§15/§14 recalibrations are folded into the design doc** (this ADR is the record; the doc rows now cite it):
   - The throughput row — "Post-optimization Forge: 10+ games/min on 32 cores, P=60%, least certain" — is **resolved true with 6× margin, pre-optimization, on the existing 16-core box**: 64 games/min heuristic, 29 games/min bridged. The §14 sentence "risk concentrated almost entirely in the M0 games/hour number" is retired.
   - Schedule arithmetic at measured rates: the ~500K-game BC corpus (§14) ≈ 5.5–7 days wall-clock heuristic-only; 1–3M self-play games ≈ 25–75 days at the bridged protocol floor (an upper bound on cost — real inference adds latency but batches, and allocation profiling remains an untouched throughput lever at 26% per-worker efficiency).
   - The bridge-tax question is closed at 2.6% (census projected 1–2%; measured with the full M0 tag set, in band). The 5x-stretch contingency in §13 (games taking minutes → Rust bet moves to phase one) is dead; the Rust-subset bet stays phase-two on its remaining motivations.
3. **Sequencing out of M0** (per the commitments in ADR-0001/0002, now unblocked):
   - **Main line: M1 (BC)** — encoder/featurization (§1–2), real observations over the bridge (entity-token payloads replacing the empty M0 observation field), `CastPlan` one-shot casting behind the config flag (also the fix path for the 65% `canPlaySa` veto rate), yield macros.
   - **Parallel Java track: upstream PR #1** — root-cause and fix the two static fork-bug classes (ADR-0002 decision 2: small, surgical, differential-tested; the ~60-seed repro set is the test suite). Runs alongside M1, not blocking it; nothing before M2 forks. The full fork API remains sequenced before M2.
   - **Parallel data track:** DC card pool / decklist pipeline; census re-run when the pool lands (the precon-pair census is the provisional basis for M1 tag coverage until then).
4. **Known caveats carried into M1 planning** (logged, accepted for M0, not to be silently forgotten): 65% veto rate means M0 plays "random proposal, heuristic-gated" (revisit with CastPlan targeting); solo replays can drift from in-run instances until all decisions are bridged and replayed from the logged answer stream (spec amended); workers recycle routinely against ~26 MB/h native RSS drift; production chunk size is 200 (the calibrated run's chunk-20 startup amortization explains the 3,016 vs 3,818 heuristic gap); harness runs launch detached (`setsid nohup`), never through session-scoped background paths.

## Consequences

- Every downstream schedule now rests on a measured number instead of §15's least-certain estimate. §14's overall calendar risk shifts from throughput to the two remaining unmeasured fronts: representation quality (M1's BC-agreement row, P=80%) and RL machinery (M2).
- M1 planning starts from a known floor: ~41K games/day bridged on existing hardware, no new hardware purchase (ADR-0002 decision 4 stands).
- The orchestrator, bridge, and `forkcheck` harnesses graduate from deliverables to permanent instruments: every future engine bump replays the fidelity gate; every future throughput claim re-runs the three-arm protocol.
- First M1 artifacts to produce: M1 plan doc (encoder/featurization scope, CastPlan design, observation schema) and the DC pool pipeline kickoff.
