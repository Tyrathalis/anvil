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

### Now (2026-09-06)

- **Research — M12 SCOPED 09-06 ([ADR-0101](docs/decisions/ADR-0101-architecture-review-m12-recharter.md) ACCEPTED + addendum, [m12-plan.md](docs/design/m12-plan.md)): SEARCH AS THE BEHAVIOR POLICY, built through to ONE BIG RUN. Build 0 boundary LANDED 09-06 s4 — forkcheck PASS (497/500, residual seeds replay to baseline), unpayable vetoes −97%, search directive smoked (≈2.6× forward calls at rate 1), scans RNG-neutral, cache OFF. **Build 1 GO 09-06 s5 ([ADR-0103](docs/decisions/ADR-0103-m12-build1-value-head-and-build3-enumerators.md)): one-ply 0.277 → 0.390 ± 0.019 cross-fit (n 647), h2/K=8 0.44 → 0.69, state ranking 0.39 (below its 0.50 bar), policy drift nil — day-zero ckpt `data/training/m12-build1-stopstate/last.pt` (the state-stop variant, 0.397; both variants GO); the Build 3 enumerators (Surfaces + SurfaceDirective + `-searchsurf`, seven answer shapes, 20 callbacks named in obs) landed in the fork `6eb64b6c538`, smoked (116 sub-rows, 0 crashes), forkcheck PASS 498/500 → fork pin `6eb64b6c538`. **Build 2 OPEN 09-06 s6 ([ADR-0104](docs/decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)): the acting rule landed (fork `103747691cc`: margin ≥ bar → sample from the leaf-value softmax at T, the natural line below it, a veto falls back; `-searchact/-searchtemp/-searchseats`, `search` pins on every game header; smokes act rate 24%, act_void 0.5%, 0 crashes, ~3× wall); **the day-zero read moved to the standard 2,000-game read vs the heuristic** (the pinned fork-window read could not search inside its own completions and sat on a different scale from the 0.5279 reference; standing rule) — arms ref / dz / dzla (bar 0.05) / dzla10, T 0.025, rate 1, rolls 1, surfaces off; **the chain LAUNCHED 23:16 09-06** (`data/runs/build2-dayzero/`, chain pid 1872752, watchd-registered, notifies; read lands ~07:00 09-07 in `read.json`); forkcheck PASS 498/500 → fork pin `103747691cc`. **READ 09-07 11:01: IN-BAND** — ref 0.538 / dz 0.522 / dzla(0.05) 0.530 / dzla10 0.538; dzla − dz **+0.92pp ± 1.10** (gate arm) → Build 3 proceeds, the big run needs a post-Build-4 read ≥ +1.5pp; dzla10 − dz +1.58 ± 1.04 (second arm; the shakedown's bar starts at 0.10); **dz − ref −1.63 ± 1.15** (the pretrain cost policy strength; lookahead recovers only to ref); multiplier 1.75× calls / 2.1× wall. The loop game → the loop guard (fork `b4825285529`: bounded engine re-ask + `Census.loopCheck` + clock allowance 900 s). Loop-guard tip PROVEN 498/500 → fork pin `b4825285529`; **control chain LAUNCHED 11:20 09-07** (`data/runs/build2-control/`, heur → heurla, ETA ~14:40); then Build 3.** ([ADR-0102](docs/decisions/ADR-0102-m12-build0-pins.md): executor's own predicate as the mask filter, boundary = mask + caps + provenance header under sv=3, deterministic caps at p99.5, fork J search copies determinized to the acting seat's info set — uniform now, belief-sampled next; Build 1 label count corrected to ~10⁴).** Build order: (0) the engine bundle, one boundary — exact payability in the mask, game-time/repetition caps, the budgeted anytime search directive (budget unit = network forward calls; leaf = the acting seat's next quiescent window, greedy intermediates), the surface enumerators, format id + pool id on every row → (1) the value head inside the shared trunk on rollout composites + full-vis targets (**GO one-ply Spearman ≥ 0.35 and/or state-ranking ≥ 0.50; KILL if neither clears 0.32**) → (2) search + **the ONE gate: the four-arm day-zero paired read** (`iter-019` alone / Build 1 ckpt alone / + lookahead / heuristic + lookahead; **≥ +1.5pp GO, ≤ 0 kill-candidate, in-band proceeds but blocks the launch until a post-Build-4 read clears +1.5pp**; control arm within 1.0pp = "the value head carries it") → (3) every §3d′ surface (three answer shapes, natural line always in the option set, smoke reads) → (4) stack-entry tokens + text-hash-keyed embedded ability text + **format-as-features** (full multi-format readiness; second-format training decided later) + the post-Build-4 re-warm → (4½) **the shakedown run** (~20–30K games, settings + the power-statement slope) → (5) **the big run in a four-to-six-week envelope** (≥ +2.5pp target; kill: with-lookahead climbs, network-alone flat; the Android ship of `iter-019` runs alongside on `playable`) → (6) the 2,000-game read. No Pauper in M12 (routed to the closeout). Running record: the plan doc.
- **Playable fork ([worklist](docs/design/playable-fork-worklist.md)): release v24 `fe86deded9` (`2.0.15-SNAPSHOT-09.05`).** Founding worklist items 1–8 built, published, user-verified; v23 = the upstream sync onto `89806371a4d`; v24 fixed the Android res refresh (first real mobile-delta run pending on device). Branch `playable`, worktree `../forge-play`; zero delta on the research fork. Release: `scripts/release-playable.sh` → `daily-snapshots` prerelease, **publish MUST pin `-R Tyrathalis/forge`**. Residue: T2 live-rescale; **worklist item 10** (09-06): the Cabal Coffers cancel-refund engine bug (`ManaRefundService` ignores `undo()`'s result), upstream PR + test. Multiplayer hardening CLOSED 07-30 ([record](docs/design/multiplayer-hardening.md)).
- **Chronicle side stream ACTIVE ([ADR-0029](docs/decisions/ADR-0029-chronicle-scheduling.md) + [mvp-plan](docs/design/chronicle-mvp-plan.md)): the 1993–94 collector-loop MVP on the playable branch behind `CHRONICLE_MODE_ENABLED` (default OFF) until the 2-week dogfood gate.** D1–D4 + D6 DONE (D6 verified in play on device 08-24); **D5 dogfood OPEN, clock running since 08-24.** Invariants: seed integrity, monotone day tick, prestige-proof saves, pack EV negative by construction, runtime cosmetics, an effort→reward channel ([ADR-0070](docs/decisions/ADR-0070-chronicle-effort-reward-sink.md)), rival pools derived never stored ([ADR-0071](docs/decisions/ADR-0071-d6-design-round.md)). Next: D5 dogfood proper, then the three-axis numbers pass (purse-per-difficulty, ante multiplier, `anteRivalFloorCards`).

### State of record

| Thing | Value |
|---|---|
| RL ckpt of record | `d6-run11/iter-019` — **0.5279 ± 0.0110** corrected ([ADR-0068](docs/decisions/ADR-0068-m9-boundary-bundle.md) era); promoted at M4, held through M5–M11 |
| Eval / Ante critic | `d4-critic-fullvis` (full-vis; never serves) |
| Day-zero ckpt (M12 Build 1) | `data/training/m12-build1-stopstate/last.pt` — one-ply 0.397 ± 0.019 / h2-K8 0.71 / state 0.375 (ADR-0103; selected by the declared inner-val rule over `m12-build1/last.pt` at 0.390 / 0.69 / 0.392); never promoted, the Build 2 arm |
| BC certification ckpt | `d5-combat/last.pt` (`forkcheck` at every engine bump) |
| Card pool | `cf2ca6ba` — 1,701 cards from 113/120 DC decks (`anvil.pool`; pinned by `data/pool/CURRENT`) |
| Research fork pin | engine `23c3d2a85d`; **Build 0 boundary tip `aac9f808bcf`**; **Build 2 tip `b4825285529`** (the acting rule `103747691cc` → the control arm `1d4b2d817c3` → the loop guard; each ADR-0025-exempt: forkcheck 498/500 vs the 08-21 seeds on `103747691cc` (09-06) and on `b4825285529` (09-07), the standing two misses, 20260739 replays to the baseline hash twice each time — PASS; the day-zero read ran on the `103747691cc` snapshot, the control arms on `b4825285529`); **Build 3 enumerators `6eb64b6c538`** (ADR-0025-exempt: forkcheck 498/500 vs the 08-21 seeds, both misses = the identity-hash residual, 20260739 replays to the baseline hash twice — PASS 09-06 s5) (ADR-0102; obs sv=3; forkcheck 497/500 vs the 08-21 seeds on the final jar, the 3 misses = the identity-hash residual — PASS 09-06); the recording jar's ADR-0025 proof discharged by transitivity |
| Fork checkout | `../forge` (blobless; `origin` Tyrathalis/forge, `upstream` Card-Forge/forge; `~/.local/opt/maven/bin/mvn -P windows-linux`, Java 17 on JDK 26) |
| Playable release | v24 `fe86deded9` |

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
- **Long-running jobs launch at low priority** (`nice -n 19`); harnesses stop gracefully and resume at seeded game granularity (design §9). Calibrated measurements run on a quiet box instead.
- **Every run emits and we read its analysis battery** ([run-analysis-protocol.md](docs/design/run-analysis-protocol.md)): session pickup after any run starts by opening its `analysis.md`; battery findings are exploratory only — verdicts stay pre-registered.
- Python ~60% / Java ~40% overall; Java work is archaeology in the Forge fork, not here.

## Repo layout

- `anvil/` — Python package; subpackages map to design-doc sections (`encoder` §1, `state` §2, `policy` §3, `heads` §4, `tutor` §5, `training`+`grindstone` §6, `ante` §7, `bridge`+`store` §9, `pool` §8, `evals` §7, `mentor` §11).
- `scripts/` — standing instruments and drivers (`final_read.py`, `migration_read.py`, `docs_index.py`, …); each names its ADR in its docstring.
- `docs/` — [README.md](docs/README.md) is the index. `design/` (canonical doc, plans, specs), `decisions/` (ADRs), `devlog/` (one file per session), `standing-rules.md`, `status-archive.md`, `project-map.html`, `forge-ai-field-guide.md`.
- `tests/` — pytest.

## Session wrap-up checklist

Each line names its trigger; most sessions touch only the first group. Nothing else is maintained by hand.

- **Every session:** `docs/devlog/YYYY-MM-DD[-sessionN].md` from the template (what was done, what broke, what the next session picks up) · the **Running record** section of the open plan doc (append; this is where the narrative accumulates) · the **Now** block above if state changed · commit with a plain descriptive message.
- **On an ADR:** the file (copy `docs/decisions/TEMPLATE.md`, `ls` for max+1) · a line in [standing-rules.md](docs/standing-rules.md) if it births a rule (same commit) · its row in the map's ADR index · the affected plan doc's status line. ADR numbers collide across parallel sessions — check `git log` before building queued work.
- **On a run close:** its row in the map's run ledger (verdict-colored) · the battery `analysis.md` read.
- **On a milestone open or close:** the milestone table row + the verbatim move of the old Now paragraph to [status-archive.md](docs/status-archive.md) · the new plan doc with a Running record section · `**Doc status:**` lines (the closed plan → historical) and `uv run python scripts/docs_index.py` · the map's milestone block, Now panel and state-of-record table · design doc §13 row · the root README status line · the **stale-data deletion pass** (inventory `data/` scratch dirs → reference-grep `docs/decisions/`, `scripts/`, `anvil/` → kill list with sizes → delete on user sign-off; unconditional keeps: ckpts of record, drills.jsonl dirs, selection/evalset assets, baseline-era arm stores, Ante certs).
- **On a state-of-record change** (ckpt, baseline, pool, fork pin, release): the table above and the map's copy.
- **At documentation passes only:** the field guide, standing-rules prune, design doc ledger §3d′, the canonical register.

Deferrals are routed by name at the next scoping session or closeout ADR — scheduled or re-deferred with a reason, never silently dropped.
