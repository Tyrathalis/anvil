# Bridge protocol v0 — draft

**Date:** 2026-07-03. **Anchors:** ADR-0001 (day-one invariants), design §9 (inference-server bridge), §1 (cross-game schema hygiene), §2 (entity tokens, dedup), §3 (pointer decoder, learnable stops, payment default); [playercontroller-override-plan.md](playercontroller-override-plan.md) (decision surface, envelope shape, provenance rule).
**Question answered:** what crosses the JVM↔Python boundary, in what shapes, for the M0 harness — such that M1 (real observations, one-shot cast, yield macros) is additive, not a rewrite.

## Scope & principles

M0 traffic: many JVM workers play games with `PlayerControllerAnvil`; a subset of decisions is answered by one Python server (random-legal at M0); everything else falls back to the inherited heuristic, tagged. The number M0 wants is games/sec **with bridge round-trips in the loop**.

Day-one invariants, restated as protocol law:

1. **Legal-actions-only materialization** (ADR-0001): every request carries its engine-enumerated legal options (or legal-candidate sets for construction answers). The server selects; it never proposes and never filters. Masking is construction.
2. **One-shot-or-micro-step** (ADR-0001): micro-step (one request per engine callback) is the base case; one-shot cast is a *composite answer* to the priority request, enabled per-session by config. Retreat is a config change.
3. **Game-agnostic wire schema** (§1): the protobuf schema defines *answer shapes*, not Magic concepts. Magic semantics travel as string tags and opaque context — data, not schema.
4. **Seed everything; provenance on everything** (conventions): seed in `GameStart`; engine hash in the handshake (never in any observation — the model must not see engine versions); every logged decision tagged `answeredBy: bridge | heuristic-fallback`.
5. **Featurize once, in Java** (§9, ADR-0001): observation payloads are Java-built feature structures; Python does embedding lookup and inference only. At M0 the observation field is empty — random-legal needs only option counts.

**Transport:** gRPC over loopback, protobuf, **one long-lived bidirectional stream per worker**. The server batches across streams for GPU passes (M1); at M0 it answers immediately (uniform random), which measures the protocol floor. Blocking synchronous request→response on the worker's game thread is correct and intended (override plan: single game thread, no reentrancy, stack frozen during setup).

## The central schema decision: answer shapes, not Magic decisions

Every bridgeable `PlayerController` callback reduces to one of six **answer shapes**:

| Shape | Answer payload | Example callbacks |
|---|---|---|
| `SELECT_ONE` | option index | `chooseSpellAbilityToPlay` (M0 form), `chooseColor`, `chooseSingleEntityForEffect` |
| `SELECT_K` | option indices, min≤k≤max | `chooseCardsForEffect`, discard/sacrifice piles, `chooseModeForAbility` |
| `INT_IN_RANGE` | integer | `chooseNumber`, `announceRequirements` (X) |
| `BOOL` | boolean | `confirmTrigger`, `mulliganKeepHand`, `chooseBinary` |
| `ORDER_N` | permutation of option indices | `orderMoveToZoneList`, scry/surveil splits (two ordered lists), `orderCosts` |
| `CONSTRUCT` | structured message (per construction kind) | combat maps, targeting, one-shot `CastPlan` |

The request additionally carries `decision_tag` — a namespaced string (`"mtg.priority"`, `"mtg.declare_attackers"`, `"mtg.scry"`, one per bridged callback) — plus an opaque `context` (deciding player, phase, prompt params, equivalence-class counts per §2 dedup). Python code that must be game-aware keys on the tag; the M0 random-legal server ignores tags entirely and answers by shape. This is the §1 hygiene convention realized at the wire: adding a second game adds tags and feature vocabularies, zero schema changes.

`CONSTRUCT` kinds are the two families the override plan identified as construction-not-selection, plus the composite cast:

- **`AttackMap`** / **`BlockMap`**: lists of (attacker-class → defender) / (blocker-class → attacker) pairs over engine-enumerated legal candidates; the engine's own validate-and-retry loops (`validateAttackers`) backstop illegal maps — worker re-asks with a `retry_of` field set.
- **`TargetPlan`**: per targeting requirement, indices into the legal-candidate list.
- **`CastPlan`** (M1, one-shot): spell option index + mode indices + X + `TargetPlan` + payment-class picks. Worker realizes it via the AI play path (pre-set targets on the SA, `AiCostDecision`-style payment). Per §3c, payment picks are only present when the engine flags the payment as consequential; otherwise engine auto-payment is the default.

## Message catalogue

Stream is worker-initiated; all messages carry `game_id` and a strictly increasing `decision_seq` where applicable.

**Handshake** — `WorkerHello` (protocol version, worker id, engine commit hash, fork commit hash, capabilities) ⇄ `ServerHello` (accepted version; **`bridged_tags`: the set of decision tags this session answers over the wire** — everything else the worker resolves locally without a round-trip; `one_shot_cast: bool`; deadline defaults). Coverage expansion is thus a server-config change; the worker is dumb about policy.

**Per game** —
- `GameStart` (worker→server): seed, format tag, per-player deck ids + hashes, provenance blob (harness run id, drill-template id when Grindstone arrives).
- `DecisionRequest` (worker→server): `decision_seq`, `decision_tag`, `answer_shape`, `options[]` (id + human-readable label + optional Java-built feature bytes), `constraints` (min/max/k), `context`, `observation` (bytes; empty at M0), `retry_of` (set when re-asking after engine validation rejected a construct), `deadline_ms`.
- `DecisionResponse` (server→worker): `decision_seq`, oneof answer per shape, **or `fallback: true`** (server declines; worker answers heuristically and tags it), and optionally (M1, §3b) `yield_directive` — a macro-stop ("don't bridge `mtg.priority` again until <phase/event>"), the protocol hook for learnable stops; the worker's inherited heuristic auto-passes in between, and the directive is itself logged as a decision.
- `GameEnd` (worker→server): outcome, turns, wall ms, per-tag decision counts, fallback count + reasons, draw-clock/cap hits.

**Control** — `Drain` (server→worker: finish current game, flush, exit — the disposable-worker/recycling verb), heartbeat pings both ways.

**Not on the wire:** trajectories. The worker writes the full decision log (every callback, bridged or not, with `answeredBy`, options digest, chosen answer, seed, seq) to local JSONL/binary for the store (§9) to ingest. The bridge carries only what the server needs to answer *now*; replay = seed + recorded answers, no server required.

## Failure, timeout, ordering semantics

- Worker blocks on the game thread awaiting each response, bounded by `deadline_ms` (M0 default: generous, 5000 — we are measuring, not tuning). On deadline or stream error: answer via heuristic fallback, tag it, count it; after N consecutive bridge failures (default 3) the worker self-drains after the current game. **No thread interrupts anywhere** (forkcheck lesson: an interrupted worker leaks a thread that keeps consuming the shared `MyRandom` singleton) — draw-clock watchdogs only.
- Responses must arrive in request order per game (one outstanding request per game by construction — the game thread is blocked). `decision_seq` exists for logging and desync detection, not reordering: a mismatched seq is a protocol bug → worker drains, game discarded, loud log.
- A `fallback` response is always legal for the server, per tag or per request. Fallback rate is first-class telemetry: trajectory metadata carries it (provenance rule), `GameEnd` reports it, and the harness alarms if it grows — for bridged tags at M0 it should be ~0.

## Determinism & provenance

Per game: seed set via `MyRandom.setRandom(new Random(seed))` before match creation (forkcheck pattern). The bridged answers are part of the trajectory record, so deterministic replay = same engine hash + seed + answer log, with fallback decisions reproduced by the (deterministic-given-RNG) heuristic. Engine/fork hashes live in `WorkerHello` and trajectory metadata only; no observation or option payload may embed them.

## M0 measurement plan (what this protocol is for)

- **Throughput delta:** same workload as the scaling sweeps (Commander precons, w=16, 2 GB heaps, `ActiveProcessorCount=2`), three arms: heuristic-only (baseline 3,818 g/h), bridged with `bridged_tags = {mtg.priority}`, bridged with the full M0 tag set (priority, mulligan, triggers, binary, number). The delta is the bridge tax; §9's napkin math says loopback gRPC + protobuf at O(10²–10³) round-trips/game should cost single-digit percent — measure, don't assume.
- **Latency histograms** per tag (worker-side, request→response) and decisions/game per tag — the latter cross-checks the instrumented callback census from the override plan.
- **Soak riders:** fallback rate ≈ 0 on bridged tags; no new RSS drift attributable to stream buffers; worker recycling under `Drain` loses zero games.

## Open for M1 (deliberately not drafted now)

- Observation payload schema (§1/§2: entity-token feature structure, dedup counts, global tokens) — waits on encoder work; the `observation: bytes` field is the socket it plugs into.
- `CastPlan` details beyond the sketch (mode/X/target interleaving on the AI play path) — waits on the override plan's instrumented census confirming the callback order empirically.
- `yield_directive` grammar (§3b macro-stops) and payment-consequential flagging (§3c) — protocol hooks reserved above, semantics deferred.
- Batch-formation instrumentation on the Python side (§9: actor and GPU starvation share a timeout-tuning fix) — server-internal, invisible to the wire.

## Proto sketch

```proto
syntax = "proto3";
package anvil.bridge.v0;

service DecisionBridge {
  rpc Session (stream WorkerMsg) returns (stream ServerMsg);
}

message WorkerMsg { oneof msg {
  WorkerHello hello = 1; GameStart game_start = 2;
  DecisionRequest request = 3; GameEnd game_end = 4; Ping ping = 5; } }
message ServerMsg { oneof msg {
  ServerHello hello = 1; DecisionResponse response = 2;
  Drain drain = 3; Ping ping = 4; } }

enum AnswerShape { SELECT_ONE = 0; SELECT_K = 1; INT_IN_RANGE = 2;
                   BOOL = 3; ORDER_N = 4; CONSTRUCT = 5; }

message Option   { uint32 id = 1; string label = 2; bytes features = 3; }
message DecisionRequest {
  string game_id = 1; uint64 decision_seq = 2;
  string decision_tag = 3;            // "mtg.priority", ... — data, not schema
  AnswerShape shape = 4;
  repeated Option options = 5;
  Constraints constraints = 6;        // min, max, k
  bytes context = 7;                  // game-namespaced context message
  bytes observation = 8;              // empty at M0; entity-token features at M1
  uint64 retry_of = 9;                // set when engine validation re-asks
  uint32 deadline_ms = 10;
}
message DecisionResponse {
  uint64 decision_seq = 1;
  oneof answer { uint32 index = 2; IndexList indices = 3; int64 value = 4;
                 bool flag = 5; IndexList ordering = 6; Construct construct = 7; }
  bool fallback = 8;                  // server declines; worker answers locally, tags it
  bytes yield_directive = 9;          // reserved, M1 (§3b)
}
message Construct { oneof kind {
  AttackMap attack_map = 1; BlockMap block_map = 2;
  TargetPlan target_plan = 3; CastPlan cast_plan = 4; } }  // CastPlan: M1
```

(Full messages — `WorkerHello`, `GameStart`, `GameEnd`, `Constraints`, the `Construct` kinds — spelled out at implementation time in `anvil/bridge/proto/`; the sketch pins the shapes the design commits to.)
