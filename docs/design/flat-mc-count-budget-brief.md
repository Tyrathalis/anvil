# Brief — the Flat Monte Carlo rollout-count budget patch

**Doc status:** historical · the brief for the separate session that builds upstream-worklist Tier 0.10; written 11-17 and carried out the same day by a background agent; the result is in upstream-worklist.md, Tier 0.10

Paste everything under the line into a new session opened on this project. The design it implements is in [upstream-worklist.md](upstream-worklist.md) (Tier 0.10) and [m13-upstream-merge-scoping.md](m13-upstream-merge-scoping.md).

---

## Background

Upstream Forge added a "Flat Monte Carlo" mode to its heuristic AI in PR #12308 (10-24): `FlatMonteCarloPicker.java` in `forge-ai`, with `HiddenInfoShuffler`. Its budget is wall-clock:

- profile properties `FLAT_MC_DECISION_BUDGET_MS` and `FLAT_MC_TURN_BUDGET_MS`;
- a desktop "max" mode behind the game flag `AI_FLAT_MONTE_CARLO_MAX` (1,500 ms per decision, 6,000 ms per turn);
- a slow-streak back-off (`flatMcSlowTrips`);
- a base seed drawn from `MyRandom.getRandom().nextLong()`.

Rollouts stop at a deadline, so the mode's strength depends on box load and the same seed can give a different game. The user decided on 2026-11-16 that a rollout-count budget is built before the project's upstream merge, on upstream master, and later offered upstream as a small `forge-ai` PR. The user also decided that the announcement read uses the desktop mode's allowance, so that allowance has to be expressed in counts.

Constraints:

- Upstream work happens only in the clean worktree `/home/tyrathalis/Everything/Projects/forge-upstream`. Never in `../forge` (the research fork) and never on the `playable` branch.
- The engine PR slot is held by #12180. **No pull request is opened and nothing is pushed to any remote.**
- Build with `~/.local/opt/maven/bin/mvn -P windows-linux`. A single-module build needs `-am`. Forge tests need an isolated `user.home`.
- Run every maven build and test under `nice -n 19`; another session may be timing games on the box.
- The launching session owns the Anvil checkout's documents. Do not edit or commit anything under `/home/tyrathalis/Everything/Projects/Anvil`; report instead.
- Git deletions (branch or worktree removal) are handed to the user as commands.

## Task

Build the rollout-count budget on upstream Forge master, locally, and report back.

1. In `../forge-upstream`: check that `git status` is clean, `git fetch upstream`, and create a local branch `flat-mc-count-budget` from `upstream/master`. Record the commit it starts from. The worktree currently sits on `ai-decision-log`.
2. Read `FlatMonteCarloPicker.java`, `HiddenInfoShuffler`, the picker's call sites in `AiController` (and `PlayerControllerAi` if it has any), the `FLAT_MC_*` properties in `AiProps` and the `.ai` profiles, and how `AI_FLAT_MONTE_CARLO` and `AI_FLAT_MONTE_CARLO_MAX` are set (`HostedMatch`; `SimulateMatch`'s `-mc on|max|off`). List every place the mode's behaviour depends on the wall clock: deadlines, the per-turn budget, the slow-streak back-off, any timeout tracker, any adaptive candidate or rollout count. List every source of randomness it draws, and from which stream.
3. Design the smallest change that makes a game with the mode on a pure function of its seed: one default-off profile property under which every clock read above is bypassed and the work is bounded by counts alone. With the property unset, behaviour must be exactly upstream's. Keep it in upstream's style and as small as an upstream reviewer would want.
4. Implement it, with one test in upstream's existing test layout: the same seed and decks played twice with the mode on and the count budget set give the same game (the same winner and turn count at least). Run that test and the existing Flat Monte Carlo tests. If determinism fails for a reason other than the clock (the base seed draw, thread timing, a hash-ordered collection), find the cause and say whether the fix belongs in this patch.
5. Work out the desktop "max" allowance in counts: the candidate count, rollouts per candidate and rollout depth the desktop mode permits when the clock never binds, per profile (Default, Hard, Hardest).
6. Commit on the local branch with a plain message. Do not push and do not open a PR.

**Done looks like:** the branch `flat-mc-count-budget` in `../forge-upstream` with the change and its passing test committed, and a final report giving the starting commit, the clock dependencies and randomness sources, the property's name and semantics, the diff size, the test's result, the desktop allowance in counts, and anything the Anvil merge should know (for example whether `AITimeoutTracker` acts in a harness-built game).
