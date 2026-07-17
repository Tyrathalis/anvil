# ADR-0018: Ruleset scope — Commander (40 life) is the target; Duel Commander is pool provenance

- **Date:** 2026-07-16
- **Status:** accepted
- **Design-doc anchor:** "Initial scope" (intro) + §8 (pool); amends the "1v1 Duel Commander" scope claim

## Context

While fact-checking a community post, we verified what ruleset our games
actually run: `AnvilRun` creates `GameType.Commander` games via
`RegisteredPlayer.forCommander`, which hardcodes **40 starting life** —
the (multiplayer) Commander ruleset, played 1v1. Corpus records confirm
40/40 openings. Forge ships no Duel Commander game type; the DC ruleset
(20 life, DC mulligan rule) would be config we add ourselves.

So the standing "initial scope: 1v1 Duel Commander" claim was half true:
Duel Commander gave us the **pool and banlist** (1,701 cards from 113 DC
meta decklists, duelcommander.com banlist), but every game, corpus, arm,
checkpoint, calibration, and certification to date is **1v1 Commander at
40 life**. Switching rulesets now would be a full dataset-boundary event:
20-life dynamics revalue aggro/tempo wholesale, obsoleting the 113K-game
corpus, the matchup priors, Ante's certification, and all arms baselines
mid-M2.

## Decision

**The target format is 1v1 Commander (40-life Commander ruleset). Duel
Commander is demoted from "the format" to "the pool's provenance."** The
DC meta remains a good curated-pool source — competitive, diverse,
Forge-scripted, banlist-clean — but the pool's function is card coverage,
not meta fidelity (a DC meta is anyway mis-calibrated to 40-life play).

Long-run scaling division, affirmed while we're here (this was already
the design-doc §"Initial scope" trajectory; now stated as the roadmap
rule):

1. **Features before breadth.** Features change interfaces (heads, obs
   fields, eval machinery); content changes volume through interfaces
   that already exist. Card/mode breadth mostly waits until the core
   feature set (RL, Tutor, Grindstone, Mentor surfaces) is in place.
2. **Content lands in chunks as dataset-boundary events** — the existing
   discipline (pinned pool version, fresh baselines, provenance) is the
   chunking mechanism. Steady state: set-by-set expansion on Magic's
   release cadence. First queued chunk: **precon-oriented Commander
   decks** (not DC-legal — Sol Ring et al.), which also repairs the DC
   pool's deck-style skew at 40 life and matches Forge's real user base.
   Priced honestly: new cards ⇒ new pool version + embedding-cache
   additions + an ID-embedding compat shim (the D2/D5 `load_compat`
   pattern — routine, not research).
3. **Zero-shot card entry is one lever away and unproven.** The text
   channel exists for exactly this, but the current model measurably
   ignores it (D5 null-text arm −0.19pp; ID crowds out text, ADR-0007).
   ID dropout remains the pre-Tutor lever; until it's demonstrated, "new
   cards generalize in" is a design bet, not a measurement.
4. **Modes scale via bridge-tag coverage** with heuristic-fallback +
   provenance as the graceful-degradation path (the M0→M1 arc, repeated
   per mode). **4-player Commander is classified as a feature, not a
   format** — it touches value semantics, Ante, combat targeting, and
   throughput (÷4 bridged seats) — and is not sequenced yet relative to
   cheap format extensions (e.g. Modern: same duel machinery, pool
   pipeline is format-parameterized).
5. **A Duel Commander mode (20 life) stays on the menu as a candidate
   Forge feature contribution** (good mobile fit, duel dailies) — a
   future dataset-boundary event if we ever train for it, never a silent
   config change.

## Consequences

- README, CLAUDE.md, and the project map scope lines updated to "1v1
  Commander over a pool derived from competitive Duel Commander
  decklists"; public communications use the same phrasing.
- Design doc's intro scope statement is amended by this ADR (bracket
  pointer added); §"Match is the episode"'s DC observation (commander
  public pre-game collapses the archetype posterior) survives unchanged —
  it's true of 1v1 Commander generally.
- No dataset, checkpoint, or eval invalidation — that is the point.
- Follow-up queued: precon pool-extension deliverable (post-core-features
  or as an early Tutor need); footnote check on whether the pool
  pipeline's banlist handling distinguishes DC's "banned as commander"
  entries (only matters if a DC mode ever lands).
