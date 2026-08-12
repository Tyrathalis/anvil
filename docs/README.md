# docs/ — index and reading order

Written 2026-08-12 (documentation cleanup pause). Files never move out of their
directories — everything here is a link target from CLAUDE.md, ADRs, and the
project map — so this index is the navigation layer.

## Start here

1. [design/anvil-design-v2.md](design/anvil-design-v2.md) — **the canonical design doc.** Why and what; section numbers (§1–§15) are referenced everywhere.
2. [project-map.html](project-map.html) — the living dashboard: Now panel, state-of-record table, run ledger, ADR index. Swept every milestone/deliverable change.
3. [design/m7-plan.md](design/m7-plan.md) — the open milestone plan (M7, the credit-assignment question).
4. [forge-ai-field-guide.md](forge-ai-field-guide.md) — every trap we measured, with detection and fix. The doc written for other Forge-AI builders.
5. [status-archive.md](status-archive.md) — verbatim full-history bullets for closed tracks (and snapshots of open bullets that outgrew CLAUDE.md). CLAUDE.md's Status section holds the compact live summaries.

## Directories

- **`decisions/`** — ADRs, numbered sequentially (0001–0055 so far; `TEMPLATE.md` at the root). Authoritative for every resolved design question. The project map carries a one-line-per-ADR index table. Numbering hazard: parallel sessions collide — `ls` for max+1 at write time.
- **`design/`** — design docs, plans, specs, and surveys (breakdown below).
- **`devlog/`** — one dated file per working session (`YYYY-MM-DD[-sessionN].md`, from `TEMPLATE.md`). The session-by-session narrative; the map footer and commit log deliberately don't duplicate it.

## design/ breakdown

**Living (updated as work lands):**

- [m7-plan.md](design/m7-plan.md) — open milestone plan
- [upstream-worklist.md](design/upstream-worklist.md) — queued upstream contributions + diagnosed engine classes (incl. the ADR-0055 copy-state divergence class)
- [playable-fork-worklist.md](design/playable-fork-worklist.md) — playable-track doc of record
- [chronicle-mvp-plan.md](design/chronicle-mvp-plan.md) — Chronicle side-stream plan (active; D3 iteration next)

**Reference (stable, still load-bearing):**

- [bridge-protocol-v0.md](design/bridge-protocol-v0.md) — wire schema: six game-agnostic answer shapes
- [observation-schema-v1.md](design/observation-schema-v1.md) — trajectory/obs format
- [playercontroller-override-plan.md](design/playercontroller-override-plan.md) — the 109-method decision surface
- [callback-census-results.md](design/callback-census-results.md) — measured callback traffic on the pool
- [dc-pool-pipeline.md](design/dc-pool-pipeline.md) — pool fetch/build/install pipeline
- [m0-batch-harness-spec.md](design/m0-batch-harness-spec.md) — chunk mechanism, run.json pinning
- [d6-vtrace-loop.md](design/d6-vtrace-loop.md) — the self-play loop design
- [fork-fidelity-test.md](design/fork-fidelity-test.md) — forkcheck, the standing engine-bump gate
- [multiplayer-hardening.md](design/multiplayer-hardening.md) — public record of the security track (9 findings, 3 merged upstream)
- [collection-mode-sketch.md](design/collection-mode-sketch.md) — Chronicle's founding design record (the MVP plan cites it)

**Surveys (ecosystem intelligence, dated snapshots):**

- [prior-work-survey.md](design/prior-work-survey.md) + [discord-ai-plotting-survey.md](design/discord-ai-plotting-survey.md) — who is doing AI-on-Forge and what they hit
- [survey-dive-austinio-rl-branch.md](design/survey-dive-austinio-rl-branch.md) · [survey-dive-manabrew-harness.md](design/survey-dive-manabrew-harness.md) · [survey-dive-pricepredictor-magezero.md](design/survey-dive-pricepredictor-magezero.md) — deep dives
- [manabrew-protocol-445-review.md](design/manabrew-protocol-445-review.md) — delivered protocol review
- [visualization-opportunities.md](design/visualization-opportunities.md) — where/why visualization would pay for Anvil (2026-08-12; deliberately not yet an implementation plan)

**Historical (closed-milestone plans and forensics — kept for provenance, superseded by their closeout ADRs):**

- Milestone plans: [m1-bc-plan.md](design/m1-bc-plan.md) · [m2-rl-plan.md](design/m2-rl-plan.md) · [m3-plan.md](design/m3-plan.md) (+ [m3-candidates.md](design/m3-candidates.md)) · [m4-plan.md](design/m4-plan.md) · [m5-plan.md](design/m5-plan.md) · [m6-plan.md](design/m6-plan.md)
- Forensics/notes: [d5-combat-executor-notes.md](design/d5-combat-executor-notes.md) · [run3-veto-forensics.md](design/run3-veto-forensics.md) · [card-addition-pipeline-sketch.md](design/card-addition-pipeline-sketch.md)
