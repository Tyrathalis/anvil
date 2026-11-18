# M13 running record — what in the recipe produces the gain

**Doc status:** living · M13's session-by-session record (opened 2026-11-18, ADR-0127)

*Appended per session, newest last: what moved, what broke, what the next session picks up. The charter, build order, pins and kill conditions live in [m13-plan.md](m13-plan.md); the CLAUDE.md Now block is a summary of this file. Read the newest entries first.*

- **2026-11-18 — the milestone opens** ([ADR-0127](../decisions/ADR-0127-m13-charter.md)). The three pre-scoping measurements closed between 11-17 and 11-18 ([m13-prescoping-measurements.md](m13-prescoping-measurements.md)); the days' narrative is in the [11-17](../devlog/2026-11-17.md) and [11-18](../devlog/2026-11-18.md) devlogs. The user re-read ADR-0126's routing against them, agreed the order (the merge, throughput that changes no game, the three arms, the value-head track beside them) and pinned nine points, listed in the plan. Nothing is running. Build 0 has not started: `../forge` is at the pin `5bd040351f` and upstream is 1,340 commits ahead as of the 11-16 fetch. The count-budget patch is on branch `flat-mc-count-budget` in `../forge-upstream`, unpushed. **Next:** Build 0 step 1, the merge as one commit after a tag, then the forkcheck on the merged jar.
