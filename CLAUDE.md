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

### Now (as of 2026-11-11)

What is running, what is next, and what waits on the user. Closed work is in the state table below, [ADR-0123](docs/decisions/ADR-0123-big-run-launch.md) and the [running record](docs/design/m12-running-record.md). The block as it stood before the 11-09 rewrite is in [status-archive.md](docs/status-archive.md), verbatim. Writing rules: [docs/style-guide.md](docs/style-guide.md).

- **Research — M12: the big run is in segment 5, running since 11-10 21:30.** `anvil.runs` name `big-run`, dir `data/runs/big-run/`, loop `data/training/big-run/`. It resumed at iteration 444 from `iter-443` with 728.4 of the 840 wall hours used, so the wall lands about 11-15 plus yields and the segment reads. The chain `scripts/big_run_chain.sh` is the recipe's single source. Plan: [m12-plan.md](docs/design/m12-plan.md). Charter: [ADR-0101](docs/decisions/ADR-0101-architecture-review-m12-recharter.md). Launch, bars and kill rule: ADR-0123. Per-segment reads: `data/runs/big-run/read.md`.
- **The recipe of record.** The alloc search recipe plus the ADR-0119 rung-2 value recipe: a head-only anchor at weight 0.1, `--value-stopgrad-trunk`, `--trunk-lr 3e-6`, `--value-head-lr 1e-4`. Drills are off and the target decoder serves masked. It runs on `forge-tgtmask3.jar` at 24 workers × 2 servers with `RL_WORKERS` 4. The full flag string is in the [quickstart](docs/design/quickstart-custom-pool.md), §7a.
- **Segment 5's settings.** `--anchor-every 32` (from 16; the user, 11-07), the Spearman floor 0.30, the anchor-gap pause line 0.15, the run-distribution rows exploratory at floor 0, ParallelGC on the workers, the memory watchdog active. Pre-registered: the memorization gap's slope halves and the holdout Spearman holds within one SE of 0.452. A slide toward 0.35 reads as the hold too weak at 32. The casts guard floor is 0.7× day-zero (`GUARD_CASTS_FLOOR` overrides). Its basis is 85% search-copy rows (running record, 11-11).
- **At the wall.** The 2,000-game read and the paired close read (`CLOSE=1`), on seed base 20261006. The promotion bar is ≥ 0.563 network-alone, confirmed by a fresh-seed paired read against the era reference `d6-run11/iter-019`. On the user's go: the head-to-head read of `iter-405` against the warm start (≈ 3 box-hours). The next segment is the user's go: `echo N > data/runs/big-run/segment`, then `anvil.runs relaunch --name big-run`.
- **Run supervision.** The finding-4 fix is merged (11-10) and the big run runs under it. The supervisor and the chain share the scope `anvil-big-run-<supervisor pid>.scope`. A run whose supervisor died reads `orphaned`, and nothing starts beside it. The loop holds `<out>/loop.lock`. The stall tick sees the run (`anvil.runs tick --name big-run`), the check-in is on and the memory watchdog is armed by the launcher. `"resume": false` is still in the state file and is the user's to flip while the run is down. At the next stop: merge branch `live-casts-guard` (the casts guard on live rows; the user's call, 11-11) and make the launcher's nice absolute (the loop runs at 15, not 19).
- **Routed to the closeout scoping.** [ADR-0125](docs/decisions/ADR-0125-value-head-track.md), value truth as a stream, is proposed and is the candidate center of the next milestone; the amortized advantage head folds into it. The mid-run design review's candidate ADR (a search-off arm at equal box time) is in the running record, 11-09. The oversize game's source is in the running record, 11-10. The `CensusRun -certify` and `PayDirective` deletion and the `payment-evalset-v2` re-certification go to the next boundary together. The dated history that remains in code comments goes to the closeout documentation pass. At the run's close, unpin the kernel, driver and JDK.
- **Upstream stream** ([upstream-worklist.md](docs/design/upstream-worklist.md), first section). One engine PR and one GUI PR are open at a time, each from the clean `../forge-upstream` worktree. Engine slot: the AI decision log, [#12180](https://github.com/Card-Forge/forge/pull/12180). tool4ever called its direction ok on 11-10; it was re-ported onto master the same day and is mergeable. Tier 0.2 (the station tap crash) queues behind it, re-checked on master 11-10 and ready on branch `station-tap-guard`. GUI slot: Tier 3.2 is next, after a stock reproduction. [#11285](https://github.com/Card-Forge/forge/pull/11285) (the determinism hooks) was APPROVED by tool4ever 11-10 and waits on a merge. Queued: the `canRegenerate` recursion fix (Tier 0.6), a small forge-ai PR.
- **Playable fork** ([worklist](docs/design/playable-fork-worklist.md)): release v27 is published (`2187b0d3b4`, `2.0.16-SNAPSHOT-11.01`, desktop and Android), with MostCromulent's Forge Web GUI in the desktop jar. Branch `playable`, worktree `../forge-play`; zero delta on the research fork. Release with `scripts/release-playable.sh`; **the publish must pin `-R Tyrathalis/forge`**. Open: T2 live-rescale. Owed: the mobile visual pass and the phone's first boot. The fork's CI has not run since 10-14.
- **Chronicle side stream** ([ADR-0029](docs/decisions/ADR-0029-chronicle-scheduling.md), [mvp-plan](docs/design/chronicle-mvp-plan.md)): the 1993–94 collector-loop MVP, on the playable branch behind `CHRONICLE_MODE_ENABLED` (default off) until the two-week dogfood gate. D1–D4 and D6 are done; the D5 dogfood has been open since 08-24. Next: the dogfood proper, then the three-axis numbers pass (purse per difficulty, ante multiplier, `anteRivalFloorCards`). Invariants are in the mvp-plan.
- **Pins.** The fork pin, the served build and the checkpoints are in the table below. The kernel, the NVIDIA driver and the JDK are pinned for the run's length (`IgnorePkg`).

### State of record

| Thing | Value |
|---|---|
| RL ckpt of record | **`big-run/iter-405`** — **0.6210 ± 0.0108** raw, masked, on the launch jar (the standard 2,000-game read at segment 4's close, 11-07; [ADR-0123](docs/decisions/ADR-0123-big-run-launch.md) §5; with-lookahead 0.6530 ± 0.0151); confirmed **0.6214 ± 0.0069** on 5,000 fresh-seed games with **+9.46 ± 0.77pp paired over `d6-run11/iter-019`** (0.5280 ± 0.0071 on the same seeds; t 12.29, 963 up / 500 down) — promoted 11-07 at the big run's fourth segment under the standing default; the previous ckpts of record `big-run/iter-301` (0.5930 ± 0.0110; confirmed 0.5972 ± 0.0069, +6.32 ± 0.79pp paired, promoted 10-29) and `big-run/iter-099` (0.5640 ± 0.0111; confirmed 0.5776 ± 0.0070, +4.22 ± 0.79pp paired, promoted 10-13) are the segment-3 and segment-1 marks; `d6-run11/iter-019` (0.5348 ± 0.0110 corrected, the 09-16 era) stays the era reference for the run's remaining segments |
| Served surface build (Build 4) | **`data/training/m12-build4-e1a-tgt/last.pt`** — served with the DECODER MASKED since 10-04 ([ADR-0122](docs/decisions/ADR-0122-union-target-mask.md); the server's default; `--no-target-mask` is the control) — the target decoder refit under the corrected player-position convention ([ADR-0116](docs/decisions/ADR-0116-player-target-positions.md); self-target rate 37.5% → 15.3%, strength within noise); the shakedown's day-zero. Seven surfaces (entity one + set, mode, order, damage, target) + tuck; table `abil-cf2ca6ba-b4s-qwen3`. Its lineage (e1 → e1a with the allocation head, [ADR-0112](docs/decisions/ADR-0112-m12-build4-allocation-head-served.md)) is in the running record |
| Eval / Ante critic | `d4-critic-fullvis` (full-vis; never serves) |
| BC certification ckpt | `d5-combat/last.pt` (`forkcheck` at every engine bump) |
| Card pool | `cf2ca6ba` — 1,701 cards from 113/120 DC decks (`anvil.pool`; pinned by `data/pool/CURRENT`) |
| Research fork pin | **`5bd040351f`** — the union target mask ([ADR-0122](docs/decisions/ADR-0122-union-target-mask.md); each priority option's legal-target union on the opts entry, modes walked, engine-refused labels marked, the unfit flag's bound-mode fix; recording / serve; forkcheck `run-20261004-tgtmask3` 499/500, PASS 10-05 00:15; **the agreement check CLEARED on `e412dbb24d`: 0 / 23,647 targets outside; the paired read CLEARED: the decoder serves MASKED**; snapshot jar `data/runs/tgtmask/forge-tgtmask3.jar` serves the next run), on `e412dbb24d` (PASS 22:03) on `5b54fbe6ef` (the first mask tip, PASS 20:22) on `9c589c1ced` — the option scan's cast-restrictions clause (the Spider-Man 2099 fix; forkcheck 499/500, PASS 10-03 17:29; the paired read vs the shuffle-mark jar 10-04: +0.15 ± 0.30pp, `restrictions` vetoes → 0 — serves), on the shuffle mark `8d82dfa546` ([ADR-0121](docs/decisions/ADR-0121-shuffle-mark.md); PASS 10-03 15:35), the certifier merge `05fea7938d` ([ADR-0117](docs/decisions/ADR-0117-certifier-merge.md)) and engine `97535e047f` (upstream 09-16, [ADR-0110](docs/decisions/ADR-0110-m12-upstream-merge-20260916.md)). The pin is the fork tip (`master`, pushed). Snapshot jars `data/runs/castmask/forge-castmask.jar`, `data/runs/shufflemark/forge-shufflemark.jar`. Every tip and its ADR-0025 proof: [fork-lineage.md](docs/design/fork-lineage.md) |
| Fork checkout | `../forge` (blobless; `origin` Tyrathalis/forge, `upstream` Card-Forge/forge; `~/.local/opt/maven/bin/mvn -P windows-linux`, Java 17 on JDK 26) |
| Playable release | v27 `2187b0d3b4` (`2.0.16-SNAPSHOT-11.01`; carries the Web GUI) |

### Milestones

M0–M11 closed; the one-row-per-milestone table (verdicts, closeout ADRs, carried assets) is in the root [README.md](README.md#milestones). Every number is post-boundary unless its ADR says otherwise — **never compare winrates across eras.**

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
- **On a run close:** its row in the map's run ledger (verdict-colored) · the battery `analysis.md` read · **for the big run: unpin the kernel, driver and JDK** (`IgnorePkg` in `/etc/pacman.conf`, pinned on launch day — kernel + `linux-cachyos-nvidia-open` + `nvidia-utils` + JDK move together) and update.
- **On a milestone open or close:** the milestone table row in the root [README.md](README.md#milestones) + the verbatim move of the old Now paragraph to [status-archive.md](docs/status-archive.md) · the new plan doc + its `mNN-running-record.md` (the record stays out of the plan so the plan reads cheaply) · `**Doc status:**` lines (the closed plan → historical) and `uv run python scripts/docs_index.py` · the map's milestone block, Now panel and state-of-record table · design doc §13 row · the root README's Status paragraph · the **stale-data deletion pass** (inventory `data/` scratch dirs → reference-grep `docs/decisions/`, `scripts/`, `anvil/` → kill list with sizes → delete on user sign-off; unconditional keeps: ckpts of record, drills.jsonl dirs, selection/evalset assets, baseline-era arm stores, Ante certs).
- **On a state-of-record change** (ckpt, baseline, pool, fork pin, release): the table above and the map's copy · a fork commit that reaches the pin also gets its row in [fork-lineage.md](docs/design/fork-lineage.md); the table cell holds only the current pin.
- **On a user-facing change** (a launcher, a harness or driver flag, pool tooling, a prerequisite): [quickstart-custom-pool.md](docs/design/quickstart-custom-pool.md) — external users run from it; it is maintained, not generated.
- **At documentation passes only** (the last one 2026-09-23, Build order 4¾; the next at the big run's closeout): the field guide, standing-rules prune, design doc ledger §3d′ + §13, the canonical register, the quickstart, `docs/ops/`, the map, and the Now block trimmed to what is running / what is next / the pins. Items already routed to it: the open plan's "Out of scope / routed by name" section.

Deferrals are routed by name at the next scoping session or closeout ADR — scheduled or re-deferred with a reason, never silently dropped.
