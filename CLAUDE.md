# Anvil

A neural agent for Magic: The Gathering built on the Forge rules engine. Non-commercial, GPL-aligned, designed to be contributed back to Forge. Solo nights-and-weekends project.

**Canonical design doc: [docs/design/anvil-design-v2.md](docs/design/anvil-design-v2.md).** Read it before substantive work. Design changes go into that doc or into an ADR in `docs/decisions/` — never live only in chat history.

## Module naming (Magic vocabulary under the smithy umbrella)

- **Anvil** — the project and the pilot agent (plays the game)
- **Tutor** — the deckbuilder (searches the pool for what the deck needs)
- **Mentor** — the coaching product
- **Grindstone** — the drill economy (grinds scenarios, sharpens the model)
- **Ante** — the luck ledger (accounts what chance took and gave)

Initial scope: 1v1 Duel Commander, curated ~1–2K card pool (union of DC meta decklists + flex slots).

## Status

- **M0 CLOSED (2026-07-04): [ADR-0003](docs/decisions/ADR-0003-m0-closeout.md).** All deliverables landed and measured; §14/§15 recalibrated (throughput row resolved true 6× pre-optimization; calendar risk shifts to M1 representation quality and M2 RL machinery). **Current milestone: M1 (BC)** — main line is encoder/featurization, real observations over the bridge, `CastPlan` one-shot (also fixes the 65% veto rate); parallel tracks: upstream PR #1 (static fork-bug fixes, per ADR-0002), DC card pool/decklist pipeline, census re-run on the pool. First M1 artifact: the M1 plan doc.
- **DC pool pipeline landed (2026-07-04): [dc-pool-pipeline.md](docs/design/dc-pool-pipeline.md).** `uv run python -m anvil.pool fetch|banlist|build|install|status`; acquisition (mtgtop8 `f=EDH` + duelcommander.com banlist, incremental, ≥2s politeness) is split from deterministic derivation (manifest content hash = pool version; `data/` stays outside git, flex/overrides force-tracked as config). **First real pool built: version `f568b187` — 1,679 cards from 111/120 decks** (20 events since 2025-07, banlist 2026-07-04, 112 cards); exclusions all legitimate (6 banned, 1 malformed source, 2 carrying `Greymond, Avacyn's Stalwart` — a genuine Forge card-script gap, the report's first upstream-gap entry). Partner commanders supported; smoke-load gate passed in the fork (single + partner decks, seeded games). Fetcher lessons: mtgtop8 serves iso-8859-1 (decode by header, not assumption) and spells split cards `Fire/Ice`. **Unblocks the census re-run.** Real-DC-deck games run long vs precons (161 turns/72s in one heuristic smoke game) — recalibrate g/h expectations when the census reruns.
- Pre-M0 prior-work survey **done** (2026-07-02): [docs/design/prior-work-survey.md](docs/design/prior-work-survey.md). Key upshots: memory/allocation pressure is the recurring Java-engine killer (M0 must include an RSS/GC soak test); Forge's `GameCopier`/simulation layer is reportedly unstable, raising risk on state forking (§9); Forge design conversations go in PRs/Discord, never issues (stale bot, ~35 days).
- **[ADR-0001](docs/decisions/ADR-0001-prior-work-responses.md)** (2026-07-02) records the survey responses: engine stays Forge; M0 gains soak + fork-fidelity tests; bridge protocol invariants (legal-actions-only materialization; one-shot-or-micro-step decision answering); standing gated bet — stable single-step fork API as flagship upstream contribution, resolved after M0.
- Forge fork: **created** (2026-07-02). Lives at `../forge` (sibling repo, blobless clone); `origin` = Tyrathalis/forge, `upstream` = Card-Forge/forge. Cloned/pinned at upstream commit `0bfdaa572f30c03e105bd5573b5d851a7c5b7a44` (2026-07-02, "Refactor CountersPutAi #11141"). Build: user-local Maven at `~/.local/opt/maven/bin/mvn`, profile `-P windows-linux`, Java release 17 on system JDK 26. Formal per-run pinning machinery arrives with the M0 harness.
- **First measurements (2026-07-03 soak, 6K games/8.2h single JVM):** forward-play is leak-free (heap-after-GC flat; LearnForge's killer confirmed dead); ~2.3 GB allocations/game; ~26 MB/h native RSS drift (recycle workers routinely); 0.4% of games hit the 120s draw clock.
- **M0 measurement set complete (2026-07-03): [ADR-0002](docs/decisions/ADR-0002-fork-api-gate-resolution.md)** resolves the fork-API gate. Headlines: **64 games/min total at 16 workers** (process-per-worker scales monotonically; §15 target beaten 6× pre-optimization; 32-core purchase declined); **fork fidelity is broken-but-characterized** (50% deterministic trajectory divergence, 12% static corruption in two seed-reproducible bug classes, zero crashes in 2,000 forks; copying *canonicalizes* — 2.4% fresh drift per additional fork). Fork API promoted to flagship upstream contribution, sequenced before M2; static-bug fixes are upstream PR #1 post-M0; interim workarounds: fork-at-start + digest tripwire. The `forge forkcheck` harness (fork commit `8907112`) is the permanent fidelity regression gate for engine bumps.
- **`PlayerController` override plan done (2026-07-03): [playercontroller-override-plan.md](docs/design/playercontroller-override-plan.md).** Headlines: injection is zero-engine-change (`LobbyPlayerAnvil` via `IGameEntitiesFactory`); decision surface is 109 methods (~88 real decisions); `PlayerControllerAnvil extends PlayerControllerAi` with per-decision `answeredBy: bridge|heuristic-fallback` provenance tagging; one-shot casting proven feasible via the AI play path (pre-set targets + `AiCostDecision`), mid-resolution choices irreducibly micro-step — ADR-0001's one-shot-or-micro-step invariant maps 1:1 onto engine structure. Landmine logged: `GameCopier.clonePlayer` swaps non-AI controllers to heuristic AI on fork (fix before M2 forking). First implementation step: instrumented callback-frequency census.
- **Bridge protocol v0 drafted (2026-07-03): [bridge-protocol-v0.md](docs/design/bridge-protocol-v0.md).** Wire schema is six game-agnostic *answer shapes* (SELECT_ONE/K, INT_IN_RANGE, BOOL, ORDER_N, CONSTRUCT); Magic semantics are namespaced string tags + opaque context (data, not schema — §1 hygiene at the wire). One bidirectional gRPC stream per worker; server-side `bridged_tags` config drives coverage; one-shot cast = composite `CastPlan` answer behind a config flag; fallback is a first-class response with provenance telemetry; trajectories stay worker-side (bridge carries decisions only). M0 measurement plan: three-arm throughput delta vs the 3,818 g/h baseline.
- **Batch-harness spec done (2026-07-03): [m0-batch-harness-spec.md](docs/design/m0-batch-harness-spec.md).** Python orchestrator in `anvil/bridge/harness/`; the **chunk** (200-game worker invocation, exit when done) is the single mechanism behind recycling, resume, pause, and crash isolation; `run.json` manifest is the formal per-run pinning machinery (fork commit + jar sha256, worker refuses on mismatch); `replay <run> <index>` is a first-class verb; defaults table transcribed from ADR-0002 (w=16/12, 2g heaps, ActiveProcessorCount=2, nice 19).
- **M0 implementation and measurement COMPLETE (2026-07-04).** Calibrated three-arm run (w=16, 320 games/arm, orchestrator-managed): heuristic 3,016 g/h / local-random 1,772 g/h / gRPC-echo 1,727 g/h → **bridge tax 2.6% at w=16; zero transport failures; 314/320 games bit-identical across transport** (6 divergences = the known heuristic-fallback nondeterminism floor, same winners). **The M0 calibrating number: ~1,700+ games/h with the bridge in the loop** (~41K games/day). Measured table in [bridge-protocol-v0.md](docs/design/bridge-protocol-v0.md). Closed out by [ADR-0003](docs/decisions/ADR-0003-m0-closeout.md).
- **Batch orchestrator landed (2026-07-04, Anvil `8b5037c`, fork `80b66aa262`):** `uv run python -m anvil.bridge.harness launch|pause|resume|status|replay|summarize`. Chunk mechanism verified end-to-end (pause mid-run → resume → 24/24 unique games, no dups/gaps); seeds are a SplitMix64 keyed stream with a Java↔Python lockstep test (`tests/test_seeds.py` — `base^i` collided across nearby bases, caught by test, fixed both sides); jar-hash verified per launch; zero-progress abort guard distinguishes systemic failures from per-game skips. **Replay caveat measured:** solo replays are self-consistent but can drift from in-run instances (warm-JVM identity-hash order + AI wall-clock timeouts — ADR-0002's nondeterminism, now at harness level); spec amended.
- **gRPC bridge live end-to-end (2026-07-04, fork `4d6f929057`, Anvil `b9ea529`).** Canonical proto at `anvil/bridge/proto/anvil_bridge.proto` (synced copy compiled into forge-gui-desktop via protobuf-maven-plugin); Python decision server `uv run python -m anvil.bridge.server` (echo + random modes, server-driven `bridged_tags`); Java `GrpcBridge` (one bidi stream, blocking round-trips, deadline→local-answer fallback). **Echo instrument verified: gRPC-arm games bit-identical to local-arm across 20 seeds. First bridge-tax number: ~2.3% single-worker** (132s vs 129s / 20 games, ~full M0 tag set) — in the census-projected band; the calibrated multi-worker number comes with the orchestrator.
- **`PlayerControllerAnvil` landed (2026-07-04, fork commit `56c96c6c40`, `forge anvil` command).** Extends `CensusPlayerController` (census log doubles as the provenance log: `by=bridge` vs implicit heuristic-fallback); M0 tag set routed through the `AnvilBridge` seam; `LocalRandomBridge` answers from `MyRandom` (deterministic per seed, transport-free control arm). Priority materializes engine-legal options; picked spells go through `canPlaySa` (targets/X pre-set AI-path style) with veto→pass. Smoke (5 games): all decisive, 5.8 s/game, ~656 bridged priority windows/game, **65% veto rate** — `canPlaySa` applies heuristic judgment, not just legality, so M0 plays "random proposal, heuristic-gated"; acceptable for bridge-tax measurement (round-trips unaffected), revisit with M1 CastPlan targeting.
- **Callback census done (2026-07-03): [callback-census-results.md](docs/design/callback-census-results.md)** (500 games, 388K callbacks, fork commit `9c4a7cd4cf`, rerunnable via `forge census` + `scripts/census/`). Headlines: `chooseSpellAbilityToPlay` is 56% of traffic (top 5 = 84%); only 45/109 methods ever fire on the precon pair; cast path confirmed — targets and X are pre-set on the SA (never callbacks on the AI path), optional costs fold into the priority answer, modes answer at two interception points; mid-resolution is 100% outside cast windows. Bridge tax projected ~1–2% for priority-only. Re-run census when the DC pool lands.

Update this section as milestones land.

## Design invariants (re-read these every session)

- The engine adjudicates every claim any learned component makes.
- Every LLM judgment is downstream-verified (LLMs filter and narrate; they never generate training truth).
- Every drill is provenance-traced to a real game.
- The value function is continuously audited against rollouts.
- Detection is the engine's job; response is the model's.
- The error-accounting queue is the spine everything reports to.
- The model never sees the engine version — formats are rules to play to; versions are bugs not to learn.

## Hard conventions

- **Game-agnostic schema:** keep Magic-specific assumptions (zone lists, feature names) out of the Python-side schema (design §1, cross-game hygiene). Costs a naming convention now, preserves multi-game optionality forever.
- **Seed everything; deterministic replay.** State forking with seed control is load-bearing for four systems.
- **Provenance on all trajectories:** source, engine hash, checkpoint, drill-template ID.
- **Fork discipline:** pinned Forge versions per run; engine upgrades are dataset boundary events. Upstream PRs stay small, tested, human-reviewed.
- **Long-running jobs launch at low priority** (`nice -n 19`) so the desktop preempts them; harnesses are designed for graceful stop + seeded game-granularity resume (design §9, "disposable workers"). Calibrated measurements are the exception: schedule them on a quiet box instead.
- Python ~60% / Java ~40% overall; Java work is archaeology in the Forge fork, not here.

## Repo layout

- `anvil/` — Python package; subpackages map to design-doc sections (`encoder` §1, `state` §2, `policy` §3, `heads` §4, `tutor` §5, `training`+`grindstone` §6, `ante` §7, `bridge`+`store` §9, `pool` §8, `evals` §7, `mentor` §11). Skeleton only until M1; M0 work concentrated in `bridge/`.
- `docs/design/` — canonical design docs.
- `docs/devlog/` — one dated file per working session (see workflow below).
- `docs/decisions/` — ADRs for anything that changes or resolves a design-doc question.
- `tests/` — pytest.

## Working session workflow

- **End of every session:** write `docs/devlog/YYYY-MM-DD.md` (copy `docs/devlog/TEMPLATE.md`): what was done, what broke, what the next session picks up. Claude writes this as part of wrapping up.
- **When a design question is resolved or a design-doc claim changes** (e.g., a probability from §15 gets measured, a bet flips): write an ADR in `docs/decisions/` (copy the template, next sequence number) and update the Status section above.
- Commit at natural checkpoints with plain descriptive messages; the devlog carries the narrative, not the commit log.
