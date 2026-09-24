# Anvil

A neural agent for Magic: The Gathering built on the [Forge](https://github.com/Card-Forge/forge) rules engine: unified deckbuilding + piloting, a drill-driven data economy, luck-adjusted evaluation, coaching as a product surface, and mobile deployment as the upstream contribution.

Non-commercial, GPL-aligned, designed to be contributed back to Forge.

## Modules

| Module | Role |
|---|---|
| **Anvil** | the project and the pilot agent |
| **Tutor** | the deckbuilder |
| **Mentor** | the coaching product |
| **Grindstone** | the drill economy |
| **Ante** | the luck ledger (luck-adjusted evaluation) |

Initial scope is 1v1 Commander over a curated ~1–2K card pool drawn from
competitive Duel Commander decklists
([ADR-0018](docs/decisions/ADR-0018-ruleset-scope-clarification.md):
games run the 40-life Commander ruleset; the DC meta supplies the pool,
not the rules). The long-run plan is every card and mode Forge supports,
added in set-sized chunks once the core features are in place.

## Documentation

- [Design doc (v2)](docs/design/anvil-design-v2.md) — canonical, everything flows from here
- [Quickstart: your own card pool](docs/design/quickstart-custom-pool.md) — build the fork, make a pool from your decklists, BC → self-play → the paired read, with the defaults that worked externally
- [Project map](docs/project-map.html) — living overview: milestones, headline numbers, ADR index
- [Devlog](docs/devlog/) — session-by-session working notes
- [Decision records](docs/decisions/) — changes and resolutions to the design

## Building AI on Forge?

Read **[the field guide](docs/forge-ai-field-guide.md)** — every trap we hit
(and watched other projects rediscover), with measurements and fixes:
state-copy fidelity (fixed upstream in
[Card-Forge/forge#11203](https://github.com/Card-Forge/forge/pull/11203)),
determinism surfaces, silent-fallback corpus poisoning, winner-label
poisoning, eval statistics, information-set enforcement, and an RL
entropy-collapse post-mortem. Directly reusable pieces:
the [bridge protocol](docs/design/bridge-protocol-v0.md) (six game-agnostic
answer shapes over Forge's [109-method decision surface](docs/design/callback-census-results.md)),
the [observation schema](docs/design/observation-schema-v1.md) (~47KB/game),
the `forkcheck` fidelity-regression harness, and a
[survey of every AI-on-Forge project we know of](docs/design/discord-ai-plotting-survey.md).

## Status

Twelve milestones in: M0–M11 closed, M12 (search as the behavior policy)
open — its shakedown run is under way as of 2026-09-23. The RL checkpoint of
record plays at 53.5% ± 1.1pp against Forge's heuristic AI on the current
engine. The live state is the Status section of [CLAUDE.md](CLAUDE.md); the
[project map](docs/project-map.html) is the dashboard, the
[decision records](docs/decisions/) are the record, and
[docs/README.md](docs/README.md) indexes the rest.

### Milestones

One row per closed milestone; the closeout ADR is the record, and
[docs/status-archive.md](docs/status-archive.md) holds every Status bullet
verbatim. Every number is post-boundary unless its ADR says otherwise —
never compare winrates across eras.

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

## License

[GPL-3.0-or-later](LICENSE), matching Forge.
