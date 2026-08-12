# Visualization opportunities — where and why plots would pay

**Date:** 2026-08-12 (written during the documentation cleanup pause).
**Status:** thinking note, deliberately NOT an implementation plan. Nothing here is scheduled; M7's queue (ADR-0049 instruments → C-bundle build → run) is untouched.
**Prompt:** Talor is encouraging richer visualization — his stated workflow is "plot or generate a report of any data possible, as often as possible" (loss curves, game times/turns, which cards get/never get played), plus an embedding visualizer, and he suggests streamlit with "every data type should have a visualization and be linked to its inputs." He demonstrated with a pauper smoke report (10 games, HTML tables: deck records, turns distribution, priority-option widths, most/never-cast cards, decision-method census) and credits the workflow with finding real things — e.g. that stock Forge pulls sideboard cards into game 1s by default. Context: [discord-ai-plotting-survey.md](discord-ai-plotting-survey.md) records his Monte-Carlo rollout visualizer and the ecosystem's plotting habits.

## The honest assessment of where we stand

Anvil's decision discipline is gate-driven: pre-registered thresholds, paired reads, decompositions — numbers that resolve to verdicts without eyeballs. That discipline is why flat results close honestly, and no plot improves it. But several of our own findings were *shape* findings communicated as prose-wrapped numbers, and a few were found late precisely because nobody was looking at a shape:

- **d6-run2's entropy collapse** sat fully recorded in `monitor.jsonl` for ~5h before a human read it (the babysit-overnight-runs lesson). A per-iteration curve is the natural glance surface; guards mechanize known triplines, plots catch the unencoded ones.
- **ADR-0052's drill-map serving mismatch** is a scatter plot in essence: map winrate vs true winrate at corr 0.23 with a 0.374-vs-0.062 offset. On a scatter it screams; in a table it took a K-sizing read to trip over.
- **The probe path decisions** (ADR-0039/0041/0044/0046) all turned on curve *shape* — rising vs flat vs steepening learning curves. We re-derived those shapes from tables each time.
- **Calibration work** (ADR-0036) is reliability-diagram-shaped; ECE numbers summarize what one diagram shows.
- **ADR-0049's cast-suppression story** (16.9% of casts changed, 46% cast→pass) is a per-iteration behavioral drift that a timeline would have surfaced earlier than the audit did.

Talor's stronger point is the *report* habit, not dashboards: his 10-game HTML caught a real engine behavior (sideboard cards in game 1s) because the report surfaced "sideboard cards cast" as a category at all. **Checked 08-12: our pool carries zero sideboard sections (`grep -i sideboard data/pool/decks/*.dck` → 0 files), so that specific behavior cannot touch our corpus** — but the class ("a category you weren't looking at, made visible, reveals a bug") is exactly what our census machinery could render and doesn't.

## Where plots would pay, ranked

**Tier 1 — plot what a standing script already computes, emitted beside its artifact (cheap, rot-resistant):**

1. **Run telemetry PNG at run end (and per-iteration during):** entropy/KL/veto/gen_s/penalty-mass curves from `monitor.jsonl`. The babysitting glance surface; also the natural home for spotting the *next* run2-class anomaly no guard encodes.
2. **Reliability diagram from `scripts/critic_calibration.py`:** raw + isotonic-mapped, per era. The audit invariant already computes everything the diagram needs.
3. **Probe learning-curve PNG from the probe harnesses** (`frozen_probe.py`, `unfreeze_probe.py`): the path-decision shape, rendered once per sweep instead of re-derived.
4. **Drill-map scatter (map wr vs true wr) from the map tooling:** the ADR-0052 class made permanently visible; any future serving mismatch shows as a cloud off the diagonal.

**Tier 2 — a per-run HTML report for generation/eval runs (Talor's template, our census):** turns distribution, crash/wedge census, never-cast and never-seen cards vs the pool, priority-option widths, decision-method mix, veto/rejected-chain stats. We already log everything his report shows (census.jsonl + stores); this is a renderer, not new instrumentation. Its value is the sideboard-class find: categories made visible. Natural trigger points: after each boundary re-baseline, after each labeling campaign, on demand for forensics.

**Tier 3 — deliberately deferred:** streamlit/live dashboards, embedding visualizers, linked-trace explorers. These are *services* — they rot the way the project map rots (our own standing rule: a stale map is worse than none), and unlike the map they wouldn't be load-bearing for decisions. Revisit if/when Mentor exists (§11 — a coaching product wants exactly these surfaces) or if a collaborator workflow needs shared run inspection.

## Principles if/when this gets built

- **Generated-at-artifact-time, never a living service.** Every plot is a side effect of a script that already runs, written next to the artifact it describes (the map convention generalized: same commit batch, same provenance).
- **Plots are communication, not evidence.** Gates stay numeric and pre-registered; a plot never becomes the thing a verdict cites.
- **One renderer per artifact schema that already has a consumer** — no plotting a format nobody reads numerically first.
- **Matplotlib PNG + static HTML only** (Talor's own report is static HTML tables); no server dependencies in the loop.

## Disposition

Parked behind the M7 queue. Cheapest first candidates when a slot opens: Tier-1 #1 (monitor.jsonl curves — rides the invest-in-run-convenience standing preference) and Tier-2 riding the next re-baseline. Talor gets pointed at this note as the considered answer to his pitch.
