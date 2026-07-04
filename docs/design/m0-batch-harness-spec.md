# M0 batch-harness spec

**Date:** 2026-07-03. **Anchors:** design §9 (disposable workers, pause/resume, throughput priorities); ADR-0002 (worker-count/JVM-flag defaults, measured scaling curve); [bridge-protocol-v0.md](bridge-protocol-v0.md) (Drain verb, worker-side trajectory logs, three-arm measurement plan); [playercontroller-override-plan.md](playercontroller-override-plan.md) (launcher precedent); `scripts/soak/run_scaling.sh` (conventions this formalizes).
**Question answered:** how the M0 harness launches, feeds, recycles, stops, resumes, and accounts for a fleet of Forge workers — the last design item before M0 goes to implementation. This is mostly transcription of decisions already measured and made; the one new mechanism is the **chunk**.

## Shape

A Python orchestrator (package `anvil/bridge/harness/`, §9 module) manages N JVM workers (the fork's headless launcher: `sim` for heuristic-only arms, the `anvil` command once `PlayerControllerAnvil` exists). The shell scripts in `scripts/` remain as thin precursors and get retired as the orchestrator absorbs their jobs.

## The chunk: one mechanism for recycling, resume, and pause

**A run is a list of globally-indexed games; workers consume them in chunks.** Game `i` has seed `seed(seed_base, i)` (deterministic, documented function; the i-th output of a SplitMix64 stream seeded at `seed_base`, i.e. `mix(seed_base + (i+1)·GOLDEN)` — a keyed stream, because both `base ^ i` and `base + i` collide structurally across nearby bases; implementation-pinned by a Java↔Python lockstep test). A worker invocation = one JVM given one chunk (a contiguous index range, default **200 games**); it plays them in order, appends one JSONL record per completed game, and **exits when the chunk is done**. The orchestrator launches a fresh worker with the next unclaimed chunk.

Everything the design asks for falls out of this one mechanism:

- **Recycling** (the ~26 MB/h RSS drift, soak finding): a chunk at w=16 throughput (≈239 g/h/worker) is ~50 min of life per JVM — drift never accumulates. JVM startup (~seconds) amortizes to <0.5% of chunk wall time.
- **Resume:** the per-game JSONL is the progress record. Resume = scan completed indices, re-issue every chunk minus its completed games. No checkpoint files, no separate progress protocol.
- **Pause:** stop issuing chunks; optionally `Drain` in-flight workers (finish current game, flush, exit). Nothing is lost either way — an undrained kill costs at most the in-flight games, which resume re-plays from their seeds.
- **Crash isolation:** a dead worker = an unfinished chunk = automatically re-issued. A game that kills or wedges its worker **twice** is recorded as `skipped` with its seed and flagged loudly (it's a free engine-bug repro), and the run moves on — one bad seed must never wedge a 90K-game night.

## Run anatomy & pinning

`data/runs/<run-id>/` contains:

- **`run.json` manifest** — the formal per-run pinning machinery CLAUDE.md has been promising: run id, purpose tag, timestamps; **fork commit + dirty flag + jar sha256**; anvil commit; bridge protocol version; deck files + hashes; format; `seed_base`; total games; worker count, heap, full JVM opts; `bridged_tags` and server identity (checkpoint id at M1, `"random-legal"` at M0); nice level. A worker refuses to start if the jar hash doesn't match the manifest.
- `workers/<n>/` — per-invocation stdout, optional GC log (flag, default off outside calibration runs).
- `games.jsonl` — merged per-game records: index, seed, chunk id, worker invocation id, outcome, turns, wall ms, per-tag decision counts, fallback count + reasons, exception census counters, draw-clock/cap flags.
- `trajectories/` — worker-side decision logs per bridge-protocol-v0 (every callback, `answeredBy`-tagged). M0 keeps them raw; the §9 store ingests later.
- `summary.json` — rolled-up throughput, latency histograms per tag, fallback rates; regenerated idempotently from `games.jsonl`.

**Deterministic single-game replay** is a first-class harness verb: `replay <run-id> <index>` reconstructs seed + decks + flags from the manifest and re-runs one game. This is the repro path for every anomaly the accounting spine flags.

## Worker contract (Java side)

- Args: deck pair, format, chunk range + `seed_base`, output paths, optional bridge endpoint + run id.
- Seeds `MyRandom` per game before match creation (forkcheck pattern); one game at a time; JSONL record appended (fsync'd) after each game.
- **Graceful stop:** SIGTERM or the presence of a stop-file (checked between games) → finish current game, flush, exit 0. The bridge `Drain` message is the same path. **No thread interrupts anywhere**; hung games are ended by watchdog draw-clocks (per-game 120 s draw clock as in the soak, plus a hard cap ~10 min → recorded as draw with reason). The 0.4%/~10%-of-wall slow-match tax is accepted at M0; cap-aware handling is a §3d model concern, not a harness one.
- Exit codes: 0 = chunk complete or gracefully stopped; nonzero = crash (orchestrator re-issues).

## Orchestrator contract (Python side)

- Launch profile defaults (all overridable, all recorded in the manifest):

| Knob | Default | Source |
|---|---|---|
| Workers, dedicated | **16** | ADR-0002 ceiling (3,818 g/h); never exceed physical cores |
| Workers, co-located (`--colocated`) | **12** | 94.5% of ceiling, 4 cores free for OS/inference server |
| Heap | `-Xms2g -Xmx2g` | scaling sweeps; ~230 MB live set |
| GC sizing | `-XX:ActiveProcessorCount=2` | ADR-0002 (null effect measured, kept as correct-by-construction) |
| Chunk size | 200 games | recycling quantum, see above |
| OS priority | `nice -n 19` | hard convention; `--calibrated` disables it, warns, and requires an explicitly quiet box |
| Bridge deadline | 5000 ms | bridge-protocol-v0 |

- Supervises workers, re-issues failed chunks, tails `games.jsonl` for a live games/h readout, and exposes exactly three run-level verbs: **`pause`** (stop issuing, drain), **`resume`** (re-scan, re-issue), **`status`**. No hot-reconfiguration — changing worker count or flags mid-run is a new run (manifests are immutable; throughput numbers stay interpretable).
- The M1 bridge era re-tunes worker count around GPU latency-hiding (ADR-0002 note); the co-located profile is the placeholder until then.

## What M0 acceptance looks like

1. The three-arm measurement from bridge-protocol-v0 (heuristic-only / priority-bridged / full-M0-tag-set) runs as three manifested runs with no manual bookkeeping, producing the bridge-tax number.
2. `replay` reproduces any flagged game bit-identically (same outcome digest) from manifest + index alone. *(Measured 2026-07-04: replay is **self-consistent** — two solo replays agree exactly — but can drift from the in-run instance (observed: 54 vs 55 turns, same winner) because the in-run game played mid-sequence in a warm JVM: identity-hash allocation order + the heuristic AI's wall-clock decision timeouts differ, the exact nondeterminism ADR-0002 characterized. A stable solo repro satisfies the debugging use-case; bit-identical in-run reproduction arrives when all decisions are bridged and replayed from the logged answer stream (protocol doc: replay = seed + answer log), or when the fork-API work lands identity-hash-free iteration.)*
3. A mid-run `pause` + machine reboot + `resume` completes the run with zero lost completed games and correct totals.
4. Overnight unattended run at w=16 sustains ≥90% of the 3,818 g/h baseline with recycling on (chunk boundaries invisible in the throughput curve).
