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

- **Current milestone: pre-M0.** Next deliverable is the M0 harness (batch harness + JVM↔Python bridge + random-legal agent) whose purpose is to measure **games/sec — the number that calibrates every schedule after it**.
- Pre-M0 prior-work survey **done** (2026-07-02): [docs/design/prior-work-survey.md](docs/design/prior-work-survey.md). Key upshots: memory/allocation pressure is the recurring Java-engine killer (M0 must include an RSS/GC soak test); Forge's `GameCopier`/simulation layer is reportedly unstable, raising risk on state forking (§9); Forge design conversations go in PRs/Discord, never issues (stale bot, ~35 days).
- **[ADR-0001](docs/decisions/ADR-0001-prior-work-responses.md)** (2026-07-02) records the survey responses: engine stays Forge; M0 gains soak + fork-fidelity tests; bridge protocol invariants (legal-actions-only materialization; one-shot-or-micro-step decision answering); standing gated bet — stable single-step fork API as flagship upstream contribution, resolved after M0.
- Forge fork: **created** (2026-07-02). Lives at `../forge` (sibling repo, blobless clone); `origin` = Tyrathalis/forge, `upstream` = Card-Forge/forge. Cloned/pinned at upstream commit `0bfdaa572f30c03e105bd5573b5d851a7c5b7a44` (2026-07-02, "Refactor CountersPutAi #11141"). Build: user-local Maven at `~/.local/opt/maven/bin/mvn`, profile `-P windows-linux`, Java release 17 on system JDK 26. Formal per-run pinning machinery arrives with the M0 harness.
- **First measurements (2026-07-03 soak, 6K games/8.2h single JVM):** forward-play is leak-free (heap-after-GC flat; LearnForge's killer confirmed dead); ~2.3 GB allocations/game; ~26 MB/h native RSS drift (recycle workers routinely); 0.4% of games hit the 120s draw clock.
- **M0 measurement set complete (2026-07-03): [ADR-0002](docs/decisions/ADR-0002-fork-api-gate-resolution.md)** resolves the fork-API gate. Headlines: **64 games/min total at 16 workers** (process-per-worker scales monotonically; §15 target beaten 6× pre-optimization; 32-core purchase declined); **fork fidelity is broken-but-characterized** (50% deterministic trajectory divergence, 12% static corruption in two seed-reproducible bug classes, zero crashes in 2,000 forks; copying *canonicalizes* — 2.4% fresh drift per additional fork). Fork API promoted to flagship upstream contribution, sequenced before M2; static-bug fixes are upstream PR #1 post-M0; interim workarounds: fork-at-start + digest tripwire. The `forge forkcheck` harness (fork commit `8907112`) is the permanent fidelity regression gate for engine bumps.
- **`PlayerController` override plan done (2026-07-03): [playercontroller-override-plan.md](docs/design/playercontroller-override-plan.md).** Headlines: injection is zero-engine-change (`LobbyPlayerAnvil` via `IGameEntitiesFactory`); decision surface is 110 methods (~88 real decisions); `PlayerControllerAnvil extends PlayerControllerAi` with per-decision `answeredBy: bridge|heuristic-fallback` provenance tagging; one-shot casting proven feasible via the AI play path (pre-set targets + `AiCostDecision`), mid-resolution choices irreducibly micro-step — ADR-0001's one-shot-or-micro-step invariant maps 1:1 onto engine structure. Landmine logged: `GameCopier.clonePlayer` swaps non-AI controllers to heuristic AI on fork (fix before M2 forking). First implementation step: instrumented callback-frequency census.
- **Remaining M0 scope:** bridge protocol draft (ADR-0001 invariants; envelope shape pre-resolved by the override plan) + batch-harness spec (disposable workers, pause/resume, worker-count/JVM-flag defaults from the scaling sweeps).

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

- `anvil/` — Python package; subpackages map to design-doc sections (`encoder` §1, `state` §2, `policy` §3, `heads` §4, `tutor` §5, `training`+`grindstone` §6, `ante` §7, `bridge`+`store` §9, `evals` §7, `mentor` §11). Skeleton only until M1; M0 work concentrates in `bridge/`.
- `docs/design/` — canonical design docs.
- `docs/devlog/` — one dated file per working session (see workflow below).
- `docs/decisions/` — ADRs for anything that changes or resolves a design-doc question.
- `tests/` — pytest.

## Working session workflow

- **End of every session:** write `docs/devlog/YYYY-MM-DD.md` (copy `docs/devlog/TEMPLATE.md`): what was done, what broke, what the next session picks up. Claude writes this as part of wrapping up.
- **When a design question is resolved or a design-doc claim changes** (e.g., a probability from §15 gets measured, a bet flips): write an ADR in `docs/decisions/` (copy the template, next sequence number) and update the Status section above.
- Commit at natural checkpoints with plain descriptive messages; the devlog carries the narrative, not the commit log.
