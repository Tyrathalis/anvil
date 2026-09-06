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

Twelve milestones in: M0–M11 closed, M12 (search as the behavior policy) in
scoping as of 2026-09-06. The RL checkpoint of record plays at 52.8% ± 1.1pp
against Forge's heuristic AI on the current engine, +6.7pp over behavior
cloning. The live state — one paragraph per open track and one row per
milestone — is the Status section of [CLAUDE.md](CLAUDE.md); the
[project map](docs/project-map.html) is the dashboard, the
[decision records](docs/decisions/) are the record, and
[docs/README.md](docs/README.md) indexes the rest.

## License

[GPL-3.0-or-later](LICENSE), matching Forge.
