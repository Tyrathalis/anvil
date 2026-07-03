# ADR-0001: Responses to the pre-M0 prior-work survey

- **Date:** 2026-07-02
- **Status:** accepted
- **Design-doc anchor:** §9 (engine choice, bridge, throughput priorities), §3 (policy head), §13 (sequencing); informed by [prior-work-survey.md](../design/prior-work-survey.md)

## Context

The pre-M0 survey (ygo-agent, MageZero, LearnForge, Forge-readiness scan) surfaced four questions the design doc should answer explicitly:

1. MageZero is actively developed and its author collaboration-friendly — build from it, or reconsider XMage as the engine?
2. Forge has documented problems (LearnForge's 2016 memory leak under headless self-play; a contributor's 2023 assessment that the `GameCopier`/simulation layer is "effectively a reimplementation of a good chunk of the engine, and isn't very stable") — should polishing Forge come before other work?
3. Has a decade of Forge development since LearnForge improved that situation?
4. ygo-agent made different design calls (env-side serialization of multi-part decisions, flat legal-action scoring, LSTM memory, JAX, turn-speed reward shaping) — which should Anvil adopt?

## Decision

**1. Engine choice stands: Forge.** MageZero's architecture (per-matchup specialist heads, hashed sparse features, determinized PUCT with information leakage) is contrary to Anvil's core bets at every layer; only its harness *pattern* is reusable, and patterns are copied, not inherited. XMage demonstrates rather than avoids the JVM heap problem (heap-bound MCTS threading, `-Xmx24g` mitigations), and — decisively — has no Android surface, which would delete Anvil's deployment thesis (§11). MageZero remains what §12 says: baseline, cross-engine differential-testing counterparty, and now a confirmed willing collaborator. Early friendly contact via their Discord.

**2. Sequencing stands; two tests join M0; one new gated bet is queued.** Measure before fixing:

- The 2016 leak afflicted forward-play; M0's job is to characterize exactly that path. **M0 gains two explicit deliverables:** (a) a multi-hour RSS/GC soak test of headless self-play; (b) a fork-fidelity differential test of `GameCopier` (fork + no-op replay must reproduce the mainline trajectory).
- `GameCopier` fragility is real but not a *now* risk: M0's random-legal forward-play never copies state. Forking becomes load-bearing at Grindstone/ddmin/search time (M2+).
- **New gated bet (mirrors the Rust-subset gate):** if the M0 soak and fork-fidelity numbers come back ugly, a stable copy/enumerate/apply single-step API for Forge is promoted from risk-mitigation to **flagship upstream contribution** — it is exactly what a Forge contributor named as the blocker for serious tree-search AI, PR #3669 laid the foothold, and Forge merges external PRs at ~190/month. Greenlight only after M0 measurement, same discipline as the Rust bet.

**3. Expectation set: leak probably healed, allocation pressure probably not.** Leaks are ordinary bugs; the codebase has had a decade of active maintenance, Java 17+, modern GC, and maintainers who run headless AI-vs-AI sims themselves. Allocation pressure from copying deep game states is architectural, uncorrected by routine maintenance (nobody upstream has needed 32-thread self-play), and independently evidenced on XMage in 2026. The design doc's throughput priorities (canonicalization patch, allocation profiling) are reaffirmed and expected to carry more of the load, not less.

**4. ygo-agent adoptions and rejections:**

- **Adopt — materialize-only-legal-actions as a bridge-protocol invariant.** The engine side only ever presents legal actions; masking is construction, not filtering. Day-one protocol rule.
- **Adopt — protocol-level fallback for the pointer decoder.** Keep the autoregressive pointer decoder (§3): MTG's target/mode/payment structure is deeper than YGO's and the turn-plan latent wants a within-turn scratchpad. But the bridge protocol must allow a decision request to be answered either in one round-trip (full decoded action) or as a sequence of single picks (ygo-agent-style micro-steps), so retreating at M1 is a config change, not a protocol rewrite.
- **Note for M2 — UPGO** alongside V-trace: nearly free in implementation, AlphaStar-lineage evidence in long-horizon games. A flag to try, not a commitment.
- **Reject — JAX migration.** Their motive was actor-learner throughput at 32-GPU scale; Anvil is one 4090 with CPU-bound game generation. PyTorch stands per §9 ("GPU sophistication deferred until demonstrably saturated").
- **Reject — turn-speed reward shaping.** Suits YGO tempo; in MTG it would bias against control lines. The per-decision time cost on concession (§3d) captures the compute rebate without distorting play. (Their undiscounted `gamma=1.0` matches our win-prob-as-sole-target design — confirmation, no change.)
- **Free lessons absorbed:** featurize-once-in-Java (§9) already prevents their duplicated-featurizer wart; their under-featurized negation state causing nonsense plays is a concrete argument that §2's derived characteristics must come from the engine, never be re-derived bridge-side.

## Consequences

- M0's definition of done now includes the soak test and fork-fidelity test alongside the games/sec number; M0 remains the next milestone with no reordering.
- The M0 bridge-protocol spec must encode two invariants before code: legal-actions-only materialization, and one-shot-or-micro-step decision answering.
- A new standing bet joins the ledger: *stable single-step fork API as flagship upstream contribution, gated on M0 measurements* — to be resolved by a future ADR once sized.
- Community actions unlocked: contact MageZero's author (cross-engine eval interest) and the Forge Discord (citing the wiki's open invitation); never park design conversations in Forge issues (stale bot, ~35 days).
- §15 probability estimates untouched for now; the M0 measurements, not this survey, should move them.
