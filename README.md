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

Initial scope is 1v1 Duel Commander over a curated ~1–2K card pool.

## Documentation

- [Design doc (v2)](docs/design/anvil-design-v2.md) — canonical, everything flows from here
- [Devlog](docs/devlog/) — session-by-session working notes
- [Decision records](docs/decisions/) — changes and resolutions to the design

## Status

Pre-M0. The first milestone is a throughput harness (Forge ↔ Python bridge + random-legal agent) to measure games/sec, the number that calibrates the entire schedule.
