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

### Now (2026-09-23)

- **Research — M12 Build 4½: the shakedown is running.** Plan: [m12-plan.md](docs/design/m12-plan.md) (charter [ADR-0101](docs/decisions/ADR-0101-architecture-review-m12-recharter.md), design [§3e](docs/design/anvil-design-v2.md)); session record: [m12-running-record.md](docs/design/m12-running-record.md).
  - **The run** ([ADR-0115](docs/decisions/ADR-0115-m12-shakedown-scoping.md)): four arms at equal box time, 30 h each, from day-zero `m12-build4-e1a-tgt` (0.5185 ± 0.0112); `anvil.runs` name `shakedown`, dir `data/runs/shakedown/`. Verdict: the best network-alone gain per box-hour; ties go to the cheaper arm.
  - **Arms:** recipe CLOSED 09-23 04:30 at 0.5240 ± 0.0112 (+0.55pp, noise). Alloc running, closes ≈ 09-24 13:00. Then shallow (≈ 09-25 20:30) and deep (≈ 09-27 03:30).
  - **Value-head drift ([ADR-0118](docs/decisions/ADR-0118-value-head-drift-under-the-loop.md)).** State-ranking Spearman fell 0.374 → 0.256 over 16 iterations, in both arms. Cause: V-trace targets with no anchor, feeding the search's leaf. Response: a per-iteration read (`value_pretrain eval`, CPU, 25 s), and the settings pass opens with a value-anchor arm (bar: within 1 SE of 0.374).
  - **Next, in order:** the arms' verdict (≈ 09-27) → one post-run worktree (`nan-guard`, `certifier-merge`, the `pause` STOP-scope fix, the Spearman battery row + guard, the value anchor) → the settings pass on the winner, anchor arm first → the launch ADR (`payment-evalset-v2` re-certified, `CensusRun -certify` + `PayDirective` deleted, the power statement) → **the big run** (4–6 weeks; bar ≥ +2.5pp network-alone over the reference; kill if with-lookahead climbs while network-alone is flat; kernel + driver + JDK pinned) → the 2,000-game read.
  - **Pins:** fork `05fea7938d`, engine `97535e047f` (see the table below); served build `m12-build4-e1a-tgt` with table `abil-cf2ca6ba-b4s-qwen3`; the recipe's full flag string is in the [quickstart](docs/design/quickstart-custom-pool.md) (§7 Self-play, with the flag table), at 24 workers × 2 servers (≈ 300–350 g/h); reference `iter-019` 0.5348 ± 0.0110.
- **Playable fork** ([worklist](docs/design/playable-fork-worklist.md)): release v26 `8b8d7f95d6` (`2.0.15-SNAPSHOT-09.19`) = the 09-19 upstream sync + the per-channel Android build stamp + a CardDb CI fix. The v25 boot on the phone (the first real mobile-delta run) is still unverified. Branch `playable`, worktree `../forge-play`; zero delta on the research fork. Release with `scripts/release-playable.sh` → the `daily-snapshots` prerelease; **publish MUST pin `-R Tyrathalis/forge`**. Open: T2 live-rescale; worklist item 10, the Cabal Coffers cancel-refund bug (upstream PR + test).
- **Chronicle side stream** ([ADR-0029](docs/decisions/ADR-0029-chronicle-scheduling.md), [mvp-plan](docs/design/chronicle-mvp-plan.md)): the 1993–94 collector-loop MVP, on the playable branch behind `CHRONICLE_MODE_ENABLED` (default OFF) until the two-week dogfood gate. D1–D4 + D6 done; **D5 dogfood open since 08-24.** Next: the dogfood proper, then the three-axis numbers pass (purse per difficulty, ante multiplier, `anteRivalFloorCards`). Invariants are in the mvp-plan.

### State of record

| Thing | Value |
|---|---|
| RL ckpt of record | `d6-run11/iter-019` — **0.5348 ± 0.0110** corrected on the merged jar (the 09-16 era, [ADR-0110](docs/decisions/ADR-0110-m12-upstream-merge-20260916.md); the pre-merge era's 0.5279 ± 0.0110 of [ADR-0068](docs/decisions/ADR-0068-m9-boundary-bundle.md) is not comparable); promoted at M4, held through M5–M12 Build 3 |
| Served surface build (Build 4) | **`data/training/m12-build4-e1a-tgt/last.pt`** — the target decoder refit under the corrected player-position convention ([ADR-0116](docs/decisions/ADR-0116-player-target-positions.md); self-target rate 37.5% → 15.3%, strength within noise); the shakedown's day-zero. Seven surfaces (entity one + set, mode, order, damage, target) + tuck; table `abil-cf2ca6ba-b4s-qwen3`. Its lineage (e1 → e1a with the allocation head, [ADR-0112](docs/decisions/ADR-0112-m12-build4-allocation-head-served.md)) is in the running record |
| Eval / Ante critic | `d4-critic-fullvis` (full-vis; never serves) |
| Day-zero ckpt (M12 Build 1) | `data/training/m12-build1-stopstate/last.pt` — one-ply 0.397 ± 0.019 / h2-K8 0.71 / state 0.375 (ADR-0103; selected by the declared inner-val rule over `m12-build1/last.pt` at 0.390 / 0.69 / 0.392); never promoted, the Build 2 arm |
| BC certification ckpt | `d5-combat/last.pt` (`forkcheck` at every engine bump) |
| Card pool | `cf2ca6ba` — 1,701 cards from 113/120 DC decks (`anvil.pool`; pinned by `data/pool/CURRENT`) |
| Research fork pin | **`05fea7938d`** — the certifier merge ([ADR-0117](docs/decisions/ADR-0117-certifier-merge.md); forkcheck 499/500, PASS 09-23), on engine `97535e047f` (upstream 09-16, [ADR-0110](docs/decisions/ADR-0110-m12-upstream-merge-20260916.md)). The fork tip `cd4b9d9951` = the pin + a test-only commit. Every tip and its ADR-0025 proof: [fork-lineage.md](docs/design/fork-lineage.md) |
| Fork checkout | `../forge` (blobless; `origin` Tyrathalis/forge, `upstream` Card-Forge/forge; `~/.local/opt/maven/bin/mvn -P windows-linux`, Java 17 on JDK 26) |
| Playable release | v26 `8b8d7f95d6` |

### Milestones

One row per milestone; the closeout ADR is the record, [docs/status-archive.md](docs/status-archive.md) holds every Status bullet verbatim. Every number is post-boundary unless its ADR says otherwise — never compare winrates across eras.

| M | Closed | ADR | Verdict | Carried assets / hazards |
|---|---|---|---|---|
| M0 | 07-04 | [0003](docs/decisions/ADR-0003-m0-closeout.md) | harness + bridge v0 ([spec](docs/design/bridge-protocol-v0.md)); bridge tax 2.6% at w=16 | `PlayerControllerAnvil`, harness launch/pause/resume/status/replay/summarize, pool pipeline |
| M1 | 07-10 | [0009](docs/decisions/ADR-0009-m1-closeout.md) | BC agent 46.8% vs teacher, held-out agreement 0.9758 | obs schema v1 + zstd store, CastPlan executor, 113,592-game corpus, Qwen3 embeddings pinned (0007) |
| M2 | 07-17 | [0020](docs/decisions/ADR-0020-m2-closeout.md) | V-trace self-play loop end-to-end; first RL ckpt superseded BC | fork rollout contract ([#11203](https://github.com/Card-Forge/forge/pull/11203)), Ante AIVAT certified (0014), entropy guards (0017), `d4-critic-fullvis` |
| M3 | 07-28 | [0026](docs/decisions/ADR-0026-m3-closeout.md) | RL 0.5121 ± 0.0110, +6.69pp over BC; parity with the heuristic | `final_read.py` 2,000-game protocol, the boundary-event template (0025), [#11285](https://github.com/Card-Forge/forge/pull/11285) |
| M4 | 08-03 | [0033](docs/decisions/ADR-0033-m4-closeout.md) | Grindstone online; first drill win +1.98pp; **`iter-019` PROMOTED** | `anvil_watchd`, mid-run drill-eval, w=16 + chunk clamp (0032) |
| M5 | 08-05 | [0037](docs/decisions/ADR-0037-m5-closeout.md) | drill loop one-shot per curation method (Δ2 −0.58pp) | `migration_read.py`, era-scoped isotonic maps (0036) |
| M6 | 08-10 | [0050](docs/decisions/ADR-0050-m6-closeout.md) | representation not the bottleneck; signal density is (0049) | `rank-critic-c2v3`, `labelset-c2-v3`, frozen-probe benchmark |
| M7 | 08-16 | [0058](docs/decisions/ADR-0058-m7-closeout.md) | dense per-decision signal trainable and behavior-moving, strength-neutral | seqlabels join, share guard, evalset v4 |
| M8 | 08-19 | [0062](docs/decisions/ADR-0062-m8-closeout.md) | critic-ordered curation TIED; natural-timing probe failed (0060) | `rankcrit_audit.py`, `critic_select.py`, 492 K=8 labels |
| M9 | 08-25 | [0077](docs/decisions/ADR-0077-m9-closeout.md) | veto-collapse FALSIFIED (0072); perfect-payment headroom real, +2.96pp/g (0075); no promotion | payment surface as infrastructure, D6 plan machinery, boundary bundle (0068); run14–20 stores banned from mixtures |
| M10 | 09-05 | [0096](docs/decisions/ADR-0096-m10-closeout.md) | generative planner route NEGATIVE; pivotality learnable (AUC 0.69) | inline certifier, paired strength read + fixed population, harvest pool + mint |
| M11 | 09-06 | [0100](docs/decisions/ADR-0100-m11-closeout.md) | option scorer NEGATIVE as a mechanism (0098/0099); the engine + value head one step ahead is the asset | `score_options` head (inert), `option_scorer_fit.py`, `critic_lookahead_read.py`, 3,655-window spread corpus |

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
- **Long-running jobs launch through `uv run python -m anvil.runs launch --name <run> --dir <dir> -- <cmd>`** ([ADR-0107](docs/decisions/ADR-0107-run-launcher-and-checkin.md): detach, nice 19, a recorded done/failed state, its own stall tick, the alert queue; quote its coverage line, claim nothing else; **09-18: the supervisor runs its own event-driven `claude -p` check-in on failed / stalled / gone / long done, the coverage line names the consumer after a self-test, `--watch` for chains whose arms write elsewhere, `anvil.runs sweep` for dead supervisors** — and the launching session arms a background wait on the run's state; **09-21: `pause --name N --wait` / `relaunch --name N` for a maintenance reboot, `--resume-on-gone` for the sweep's own relaunch, `--wall-hours` on the loop for equal-box-time arms**); harnesses stop gracefully and resume at seeded game granularity (design §9). Calibrated measurements run on a quiet box instead.
- **Every run emits and we read its analysis battery** ([run-analysis-protocol.md](docs/design/run-analysis-protocol.md)): session pickup after any run starts by opening its `analysis.md`; battery findings are exploratory only — verdicts stay pre-registered.
- **Writing style for docs** (Now bullets, ADR summaries, running-record entries, standing rules): lead with the verdict; one claim per sentence; say what changed and why it matters before the evidence; commit hashes and run ids only where they are the pin or the proof; no chains of `→` with nested parentheses; history goes to the archive, the running record, or [fork-lineage.md](docs/design/fork-lineage.md), not to CLAUDE.md. ADRs and archives are not rewritten to match.
- Python ~60% / Java ~40% overall; Java work is archaeology in the Forge fork, not here.

## Repo layout

- `anvil/` — Python package; subpackages map to design-doc sections (`encoder` §1, `state` §2, `policy` §3, `heads` §4, `tutor` §5, `training`+`grindstone` §6, `ante` §7, `bridge`+`store` §9, `pool` §8, `evals` §7, `mentor` §11).
- `scripts/` — standing instruments and drivers (`final_read.py`, `migration_read.py`, `docs_index.py`, …); each names its ADR in its docstring.
- `docs/` — [README.md](docs/README.md) is the index. `design/` (canonical doc, plans, specs), `decisions/` (ADRs), `devlog/` (one file per session), `standing-rules.md`, `status-archive.md`, `project-map.html`, `forge-ai-field-guide.md`.
- `tests/` — pytest.

## Session wrap-up checklist

Each line names its trigger; most sessions touch only the first group. Nothing else is maintained by hand.

- **Every session:** `docs/devlog/YYYY-MM-DD[-sessionN].md` from the template (what was done, what broke, what the next session picks up) · the open milestone's running record, `docs/design/mNN-running-record.md` (append, newest last; this is where the narrative accumulates) · the **Now** block above if state changed · commit with a plain descriptive message.
- **On an ADR:** the file (copy `docs/decisions/TEMPLATE.md`, `ls` for max+1) · a line in [standing-rules.md](docs/standing-rules.md) if it births a rule (same commit) · its row in the map's ADR index · the affected plan doc's status line. ADR numbers collide across parallel sessions — check `git log` before building queued work.
- **On a run close:** its row in the map's run ledger (verdict-colored) · the battery `analysis.md` read · **for the big run: unpin the kernel, driver and JDK** (`IgnorePkg` in `/etc/pacman.conf`, pinned on launch day — kernel + `linux-cachyos-nvidia-open` + `nvidia-utils` + JDK move together) and update.
- **On a milestone open or close:** the milestone table row + the verbatim move of the old Now paragraph to [status-archive.md](docs/status-archive.md) · the new plan doc + its `mNN-running-record.md` (the record stays out of the plan so the plan reads cheaply) · `**Doc status:**` lines (the closed plan → historical) and `uv run python scripts/docs_index.py` · the map's milestone block, Now panel and state-of-record table · design doc §13 row · the root README status line · the **stale-data deletion pass** (inventory `data/` scratch dirs → reference-grep `docs/decisions/`, `scripts/`, `anvil/` → kill list with sizes → delete on user sign-off; unconditional keeps: ckpts of record, drills.jsonl dirs, selection/evalset assets, baseline-era arm stores, Ante certs).
- **On a state-of-record change** (ckpt, baseline, pool, fork pin, release): the table above and the map's copy · a fork commit that reaches the pin also gets its row in [fork-lineage.md](docs/design/fork-lineage.md); the table cell holds only the current pin.
- **On a user-facing change** (a launcher, a harness or driver flag, pool tooling, a prerequisite): [quickstart-custom-pool.md](docs/design/quickstart-custom-pool.md) — external users run from it; it is maintained, not generated.
- **At documentation passes only** (the last one 2026-09-23, Build order 4¾; the next at the big run's closeout): the field guide, standing-rules prune, design doc ledger §3d′ + §13, the canonical register, the quickstart, `docs/ops/`, the map, and the Now block trimmed to what is running / what is next / the pins. **Routed to the next pass (the 2026-09-23 fluency review):** cap each standing rule at about two lines, detail left in its ADR (37K → ≈ 25K); cut the design doc's §3d′ ledger to the current coverage table, the history to the ADRs; `/consolidate-memory` over the entries that repeat this file (the three launch entries into one; ADR-collision and check-git-log are already in this checklist).

Deferrals are routed by name at the next scoping session or closeout ADR — scheduled or re-deferred with a reason, never silently dropped.
