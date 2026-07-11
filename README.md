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

M0 (throughput harness) and M1 (behavior cloning) are complete: the batch
harness sustains ~1,700+ games/h with the Python bridge in the loop, and a
behavior-cloned agent trained on ~114K self-play games (held-out expert
agreement 0.976) plays full games at 46.8% ± 2.5pp against the heuristic AI
it imitates. Current milestone: M2 (RL) — the state-forking rollout contract
is certified (the `GameCopier` fidelity fixes are headed upstream), with the
SA-level action schema, rollout-labeled value targets, and first V-trace
self-play ahead. See the [devlog](docs/devlog/) and
[decision records](docs/decisions/) for the running narrative.

## License

[GPL-3.0-or-later](LICENSE), matching Forge.
