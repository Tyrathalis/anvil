# Anvil

A neural agent for Magic: The Gathering built on the Forge rules engine. Non-commercial, GPL-aligned, designed to be contributed back to Forge. Solo nights-and-weekends project.

**Canonical design doc: [docs/design/anvil-design-v2.md](docs/design/anvil-design-v2.md).** Read it before substantive work. Design changes go into that doc or into an ADR in `docs/decisions/` — never live only in chat history. **[docs/README.md](docs/README.md)** indexes everything else (generated from per-file status lines by `scripts/docs_index.py`).

## Module naming (Magic vocabulary under the smithy umbrella)

- **Anvil** — the project and the pilot agent (plays the game)
- **Tutor** — the deckbuilder (searches the pool for what the deck needs)
- **Mentor** — the coaching product
- **Grindstone** — the drill economy (grinds scenarios, sharpens the model)
- **Ante** — the luck ledger (accounts what chance took and gave)

Initial scope: 1v1 Commander (40-life Commander ruleset), curated ~1–2K card pool derived from Duel Commander meta decklists + flex slots ([ADR-0018](docs/decisions/ADR-0018-ruleset-scope-clarification.md): DC is the pool's provenance, not the ruleset; content breadth scales in set-sized dataset-boundary chunks after core features).

## Status

### Now (as of 2026-11-18)

What is running, what is next, and what waits on the user. Closed work is in the state table below, [ADR-0126](docs/decisions/ADR-0126-m12-closeout.md) and the [M12 running record](docs/design/m12-running-record.md). Earlier Now blocks are in [status-archive.md](docs/status-archive.md), verbatim. Writing rules: [docs/style-guide.md](docs/style-guide.md).

- **Research — M12 is closed (11-16, [ADR-0126](docs/decisions/ADR-0126-m12-closeout.md)); M13 is not chartered yet.** The ladder of own checkpoints closed 11-17: one rating per checkpoint fits all ten pairs, and `iter-405` and `iter-513` are level head to head (0.5019 ± 0.0055). The verdict: training scale works. `big-run/iter-405` reads 0.6214 ± 0.0069 on 5,000 fresh-seed games, +9.46 ± 0.77pp paired over the era reference, network alone. Not known: whether search teaches, whether the ratio of data to training is right, and whether the recipe has stopped: segment 5 failed to improve the network. The run's record: [ADR-0123](docs/decisions/ADR-0123-big-run-launch.md), `data/runs/big-run/read.md`.
- **The recipe of record.** The alloc search recipe plus the ADR-0119 rung-2 value recipe: a head-only anchor at weight 0.1, `--value-stopgrad-trunk`, `--trunk-lr 3e-6`, `--value-head-lr 1e-4`. Drills are off and the target decoder serves masked. It runs on `forge-tgtmask3.jar` at 24 workers × 2 servers with `RL_WORKERS` 4. The full flag string is in the [quickstart](docs/design/quickstart-custom-pool.md), §7a. It is the control arm of whatever M13 runs first.
- **Next, in the order agreed 11-16.** The designs are in [m13-prescoping-measurements.md](docs/design/m13-prescoping-measurements.md). (1) Done: the Monte Carlo count-budget patch is built (`flat-mc-count-budget` in `../forge-upstream`, unpushed), and the precon cost is measured: four-player costs 13 times two-player, plain heuristic; 15% of its Monte Carlo rollouts still fail (the copier). (2) Done: the search-ranking gate cleared (un-acted slope +0.351 ± 0.073), so the soft-target arm runs; the acted windows showed no slope, flagged. (3) The search's wall cost, on a quiet box. (4) The user re-reads ADR-0126's routing against the results. (5) The M13 charter is drafted, then opened. The documentation pass lacks only the quickstart's reorganization.
- **What M13 has to decide.** What in the recipe produces the gain. The benchmark is chosen: Commander precons, two-player and four-player tracks, by release era (ADR-0126). The candidates are in ADR-0126's routing table: three arms at equal box time (the recipe of record, search off, soft targets), more learning per game, [ADR-0125](docs/decisions/ADR-0125-value-head-track.md)'s value-head track, throughput, the short format. The arms are sized before they are ordered: a week-long arm moves about 1.5pp at the run's slope and a 5,000-game paired read resolves 0.7pp. M13 opens with an upstream merge (1,340 commits; upstream's heuristic now has a Monte Carlo mode on a wall-clock budget): [scoping draft](docs/design/m13-upstream-merge-scoping.md).
- **Waits on the user.** The rest of the [stale-data kill list](docs/ops/stale-data-pass-2026-11-16.md). A read of the pruned [standing rules](docs/standing-rules.md). Whether forced-decision replay becomes an M13 item ([devlog](docs/devlog/2026-11-16-session2.md), last section).
- **Run supervision.** Launched runs sit under the finding-4 supervisor, which shares one scope with its command. A run whose supervisor died reads `orphaned`, and nothing starts beside it. The stall tick is on, the launcher arms the memory watchdog, and the check-in passes its self-test. The big run's state and 33 iterations' weights are at `data/training/big-run/` (thinned 11-16); its state file still holds `"resume": true` and the run reads `done`, so the sweep leaves it.
- **Routed to the next boundary** (ADR-0126): the `CensusRun -certify` and `PayDirective` deletion with the `payment-evalset-v2` re-certification; the learner's memory work; the loop config prune; the NullPointerException crash; the oversize game's source.
- **Upstream stream** ([upstream-worklist.md](docs/design/upstream-worklist.md), first section). One engine PR and one GUI PR are open at a time, each from the clean `../forge-upstream` worktree. Engine slot: the AI decision log, [#12180](https://github.com/Card-Forge/forge/pull/12180), APPROVED by tool4ever 11-11 and waiting on a merge. Tier 0.2 (the station tap crash) queues behind it, ready on branch `station-tap-guard`. GUI slot: Tier 3.2 is next, after a stock reproduction. [#11285](https://github.com/Card-Forge/forge/pull/11285) (the determinism hooks) merged 11-11. Queued: the `canRegenerate` recursion fix (Tier 0.6), a small forge-ai PR.
- **Playable fork** ([worklist](docs/design/playable-fork-worklist.md)): release v27 is published (`2187b0d3b4`, `2.0.16-SNAPSHOT-11.01`, desktop and Android), with MostCromulent's Forge Web GUI in the desktop jar. Branch `playable`, worktree `../forge-play`; zero delta on the research fork. Release with `scripts/release-playable.sh`; **the publish must pin `-R Tyrathalis/forge`**. Open: T2 live-rescale. Owed: the mobile visual pass and the phone's first boot. The fork's CI has not run since 10-14.
- **Chronicle side stream** ([ADR-0029](docs/decisions/ADR-0029-chronicle-scheduling.md), [mvp-plan](docs/design/chronicle-mvp-plan.md)): the 1993–94 collector-loop MVP, on the playable branch behind `CHRONICLE_MODE_ENABLED` (default off) until the two-week dogfood gate. D1–D4 and D6 are done; the D5 dogfood has been open since 08-24. Next: the dogfood proper, then the three-axis numbers pass (purse per difficulty, ante multiplier, `anteRivalFloorCards`). Invariants are in the mvp-plan.
- **Pins.** The fork pin, the served build and the checkpoints are in the table below. The kernel, the NVIDIA driver and the JDK are no longer pinned: the `IgnorePkg` line was lifted and the box updated and rebooted on 11-16 (kernel 7.3.4). The system Python is not pinned.

### State of record

| Thing | Value |
|---|---|
| RL ckpt of record | **`big-run/iter-405`** — **0.6214 ± 0.0069** network alone against the heuristic on 5,000 fresh-seed games, masked, on the launch jar; **+9.46 ± 0.77pp paired** over the era reference `d6-run11/iter-019` on the same seeds. The standard 2,000-game read is 0.6210 ± 0.0108, and 0.6530 ± 0.0151 with lookahead. Head to head it scores 0.5865 ± 0.0057 against the big run's warm start. Promoted 11-07; the earlier promotions and every read are in [ADR-0123](docs/decisions/ADR-0123-big-run-launch.md) |
| Served surface build (Build 4) | **`data/training/m12-build4-e1a-tgt/last.pt`** — served with the DECODER MASKED since 10-04 ([ADR-0122](docs/decisions/ADR-0122-union-target-mask.md); the server's default; `--no-target-mask` is the control) — the target decoder refit under the corrected player-position convention ([ADR-0116](docs/decisions/ADR-0116-player-target-positions.md); self-target rate 37.5% → 15.3%, strength within noise); the shakedown's day-zero. Seven surfaces (entity one + set, mode, order, damage, target) + tuck; table `abil-cf2ca6ba-b4s-qwen3`. Its lineage (e1 → e1a with the allocation head, [ADR-0112](docs/decisions/ADR-0112-m12-build4-allocation-head-served.md)) is in the running record |
| Eval / Ante critic | `d4-critic-fullvis` (full-vis; never serves) |
| BC certification ckpt | `d5-combat/last.pt` (`forkcheck` at every engine bump) |
| Card pool | `cf2ca6ba` — 1,701 cards from 113/120 DC decks (`anvil.pool`; pinned by `data/pool/CURRENT`) |
| Research fork pin | **`5bd040351f`** — the fork tip (`master`, pushed), carrying the union target mask ([ADR-0122](docs/decisions/ADR-0122-union-target-mask.md)) on engine `97535e047f` (upstream 09-16, [ADR-0110](docs/decisions/ADR-0110-m12-upstream-merge-20260916.md)). Its forkcheck passed 499/500. The snapshot jar that serves runs is `data/runs/tgtmask/forge-tgtmask3.jar`; the two before it are `data/runs/castmask/forge-castmask.jar` and `data/runs/shufflemark/forge-shufflemark.jar`. Every tip and its ADR-0025 proof: [fork-lineage.md](docs/design/fork-lineage.md) |
| Fork checkout | `../forge` (blobless; `origin` Tyrathalis/forge, `upstream` Card-Forge/forge; `~/.local/opt/maven/bin/mvn -P windows-linux`, Java 17 on JDK 26) |
| Playable release | v27 `2187b0d3b4` (`2.0.16-SNAPSHOT-11.01`; carries the Web GUI) |

### Milestones

M0–M12 closed; M13 is not chartered yet. The one-row-per-milestone table (verdicts, closeout ADRs, carried assets) is in the root [README.md](README.md#milestones). Every number is post-boundary unless its ADR says otherwise — **never compare winrates across eras.**

## Design invariants (re-read these every session)

- The engine adjudicates every claim any learned component makes.
- Every LLM judgment is downstream-verified (LLMs filter and narrate; they never generate training truth).
- Every drill is provenance-traced to a real game.
- The value function is continuously audited against rollouts.
- Detection is the engine's job; response is the model's.
- The error-accounting queue is the spine everything reports to.
- The model never sees the engine version — formats are rules to play to; versions are bugs not to learn.

These seven are the constitution; the operational layer under them is **[docs/standing-rules.md](docs/standing-rules.md)** — every measured rule the milestones have birthed (gating/reads, training-loop design, curation, engine/data hygiene, routing), one line each with its ADR. Read the relevant section before designing any run, gate, instrument, or curation cycle.

## Hard conventions

- **Game-agnostic schema:** keep Magic-specific assumptions (zone lists, feature names) out of the Python-side schema (design §1, cross-game hygiene).
- **Seed everything; deterministic replay.** State forking with seed control is load-bearing for four systems.
- **Provenance on all trajectories:** source, engine hash, checkpoint, drill-template ID.
- **Fork discipline:** pinned Forge versions per run; engine upgrades are dataset boundary events. **Exemption ([ADR-0025](docs/decisions/ADR-0025-d4-rebase-closeout.md)):** a change that is behavior-identical on the game path is not a boundary — but the proof is *empirical, not argued* (same seed set on both jars → identical `forkcheck` trace hashes; any mismatch ⇒ boundary). A crash fix never qualifies. Upstream PRs stay small, tested, human-reviewed.
- **Hazards:** the playable build shares Forge's user deck store with research (`launch --pool` hash-gates it); never check out `playable` in the research worktree.
- **Long-running jobs launch through `uv run python -m anvil.runs launch --name <run> --dir <dir> --launched-by '<your ListAgents name> [<ref>]' -- <cmd>`** ([ADR-0107](docs/decisions/ADR-0107-run-launcher-and-checkin.md)). Quote its coverage line and claim nothing beyond it. **The launching session owns the run's close** (ADR-0107 addendum 10-03): the check-in relays the run's events to the session whose ListAgents row carries the bracketed ref in `--launched-by` (read yours from ListAgents: "This session is <name> [<ref>]" — peers see a titled session by its title, so the ref is the handle); a run event you receive for a run you did not launch is informational — read the state file's `launched_by` and `git log -3` on main before writing anything, and never write a second close.
  - The launcher detaches at nice 19, records a done/failed state, runs its own stall tick and feeds the alert queue.
  - Its supervisor runs a `claude -p` check-in on failed / stalled / gone / long done; the coverage line names that consumer after a self-test. `--watch` covers chains whose arms write elsewhere; `anvil.runs sweep` finds dead supervisors.
  - The launching session also arms a background wait on the run's state (the launcher notifies the user, not the session).
  - Maintenance reboot: `pause --name N --wait`, then `relaunch --name N`. `--resume-on-gone` lets the sweep relaunch; `--wall-hours` on the loop gives equal-box-time arms.
  - Harnesses stop gracefully and resume at seeded game granularity (design §9). Calibrated measurements run on a quiet box instead.
- **Every run emits and we read its analysis battery** ([run-analysis-protocol.md](docs/design/run-analysis-protocol.md)): session pickup after any run starts by opening its `analysis.md`; battery findings are exploratory only — verdicts stay pre-registered.
- **Writing style: [docs/style-guide.md](docs/style-guide.md)** (adopted 2026-11-09). Every document is one of three kinds. State documents (the Now block, the state table, the README's Status, the map's panels) are rewritten in place and stay inside their caps: the Now block at most 800 words, a bullet at most 120. Records (ADRs, the running record, devlogs, the archive) are appended to and never rewritten. Reference documents, code comments and `--help` text describe the present and link a record for history. In every kind: lead with the verdict; one claim per sentence; say what changed and why it matters before the evidence; commit hashes and run ids only where they are the pin or the proof.
- Python ~60% / Java ~40% overall; Java work is archaeology in the Forge fork, not here.

## Repo layout

- `anvil/` — Python package; subpackages map to design-doc sections (`encoder` §1, `state` §2, `policy` §3, `heads` §4, `tutor` §5, `training`+`grindstone` §6, `ante` §7, `bridge`+`store` §9, `pool` §8, `evals` §7, `mentor` §11).
- `scripts/` — standing instruments and drivers (`final_read.py`, `migration_read.py`, `docs_index.py`, …); each names its ADR in its docstring.
- `docs/` — [README.md](docs/README.md) is the index. `design/` (canonical doc, plans, specs), `decisions/` (ADRs), `devlog/` (one file per session), `standing-rules.md`, `status-archive.md`, `project-map.html`, `forge-ai-field-guide.md`.
- `tests/` — pytest.

## Session wrap-up checklist

Each line names its trigger; most sessions touch only the first group. Nothing else is maintained by hand.

- **Every session:** `docs/devlog/YYYY-MM-DD[-sessionN].md` from the template (what was done, what broke, what the next session picks up) · the open milestone's running record, `docs/design/mNN-running-record.md` (append, newest last; this is where the narrative accumulates) · the **Now** block above if state changed (rewrite the affected bullet, do not append to it; text that leaves goes to the running record or the archive) · commit with a plain descriptive message.
- **On an ADR:** the file (copy `docs/decisions/TEMPLATE.md`, `ls` for max+1) · a line in [standing-rules.md](docs/standing-rules.md) if it births a rule (same commit) · its row in the map's ADR index · the affected plan doc's status line. ADR numbers collide across parallel sessions — check `git log` before building queued work.
- **On a run close:** its row in the map's run ledger (verdict-colored) · the battery `analysis.md` read · for a run launched under `IgnorePkg` pins (kernel + `linux-cachyos-nvidia-open` + `nvidia-utils` + JDK move together), lifting them and updating.
- **On a milestone open or close:** the milestone table row in the root [README.md](README.md#milestones) + the verbatim move of the old Now paragraph to [status-archive.md](docs/status-archive.md) · the new plan doc + its `mNN-running-record.md` (the record stays out of the plan so the plan reads cheaply) · `**Doc status:**` lines (the closed plan → historical) and `uv run python scripts/docs_index.py` · the map's milestone block, Now panel and state-of-record table · design doc §13 row · the root README's Status paragraph · the **stale-data deletion pass** (inventory `data/` scratch dirs → reference-grep `docs/decisions/`, `scripts/`, `anvil/` → kill list with sizes → delete on user sign-off; unconditional keeps: ckpts of record, drills.jsonl dirs, selection/evalset assets, baseline-era arm stores, Ante certs).
- **On a state-of-record change** (ckpt, baseline, pool, fork pin, release): the table above and the map's copy · a fork commit that reaches the pin also gets its row in [fork-lineage.md](docs/design/fork-lineage.md); the table cell holds only the current pin.
- **On a user-facing change** (a launcher, a harness or driver flag, pool tooling, a prerequisite): [quickstart-custom-pool.md](docs/design/quickstart-custom-pool.md) — external users run from it; it is maintained, not generated.
- **At documentation passes only** (the last one 2026-09-23, Build order 4¾; the M12 closeout's pass opened 2026-11-16): the field guide, standing-rules prune, design doc ledger §3d′ + §13, the canonical register, the quickstart, `docs/ops/`, the map, and the Now block trimmed to what is running / what is next / the pins. Items already routed to it: the open plan's "Out of scope / routed by name" section.

Deferrals are routed by name at the next scoping session or closeout ADR — scheduled or re-deferred with a reason, never silently dropped.
