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

M0 (throughput harness) and M1 (behavior cloning) are complete: the batch
harness sustains ~1,700+ games/h with the Python bridge in the loop, and a
behavior-cloned agent trained on ~114K self-play games (held-out expert
agreement 0.976) plays full games at parity-minus-a-few-points against the
heuristic AI it imitates. M2 (RL) is in flight: the state-forking rollout
contract is certified and the `GameCopier` fidelity fixes are **merged
upstream** ([#11203](https://github.com/Card-Forge/forge/pull/11203)); the
SA-level action schema, luck-adjusted evaluation ledger (Ante), asymmetric
critic, and combat constructs have landed; V-trace self-play is running —
the current checkpoint reads 50.8% ± 2.5pp (luck-corrected) against the
teacher, and the first guarded run following an instructive entropy-collapse
post-mortem ([ADR-0017](docs/decisions/ADR-0017-run2-entropy-collapse.md)) is
underway. See the [project map](docs/project-map.html) and
[decision records](docs/decisions/) for the running narrative.

## License

[GPL-3.0-or-later](LICENSE), matching Forge.
