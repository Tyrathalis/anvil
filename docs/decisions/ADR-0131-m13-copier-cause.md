# ADR-0131: the copier's four-player failures come from a player who has left the game: 94% of failed rollouts map an object that player owned

- **Date:** 2026-11-19
- **Status:** accepted (a diagnosis; the fix is routed, not built)
- **Design-doc anchor:** §9 (state forking); [m13-plan.md](../design/m13-plan.md) Build 0, step 6; [m13-prescoping-measurements.md](../design/m13-prescoping-measurements.md), the copier check

## Context

In four-player games 15 to 25% of Flat Monte Carlo rollouts failed in the game copier, against 1% in two-player. The 11-18 check showed the failures persist on upstream master and run through the copier's player step. The cause was not identified; the guess on file was a player who has left the game. Our own search copies games through the same class, so no four-player search or Monte Carlo read runs before the cause is known.

## Decision

1. **The cause is a player who has left the game.** Survivors' state still refers to objects that player owned. The copier copies only the remaining players and their zones, so those references have no counterpart and the copy throws.
2. **It takes two forms**, both measured:
   - **A commander-damage entry.** A survivor's commander-damage table keeps the lost player's commander. `Player.copyCommandersToSnapshot` has a skip for a commander that maps to nothing, but the copier's mapper throws instead of returning nothing, so the skip never runs.
   - **An effect card in a survivor's command zone.** An effect the lost player owned and controlled stays in another player's command zone (Gonti, Canny Acquisitor's "you may cast that card" effect is the common one). The copier finds no player for it and fails placing it.
3. **Once it happens, every later copy for that survivor fails,** which is why the rate is high and why two-player games are spared: there the game ends when a player leaves.
4. **The fix is routed to Build 1 and is not built here.** No four-player search or Monte Carlo read runs before it lands.

## Evidence

Two cells of the 11-18 check's eight four-player pods, three games each, desktop Monte Carlo in every seat, on diagnostic jars built from the pin (`e40ba17c9c`) in a separate worktree (`../forge-copierdiag`, branch `copier-diag`; outputs in `data/runs/m13-copier/`). The jars print the state of each object the copier cannot map. They are not the pin and serve nothing else. The mode's budget is a clock and the box was carrying another run, so the two cells are not the same games.

| Cell | Games | Rollouts | Failed |
|---|---|---|---|
| First diagnostic (unmapped cards) | 20 of 24 | 10,542 | 1,423 (13.5%) |
| Second diagnostic (adds unplaceable cards) | 24 | 12,972 | 3,122 (24.1%) |

In the second cell, by cause:

| Cause | Failed rollouts | Share |
|---|---|---|
| A commander of a player who has left, in a survivor's commander-damage table | 2,434 | 78% |
| An effect card of a player who has left, in a survivor's command zone | 490 | 16% |
| A remembered token whose zone has no player (owner still in the game) | 44 | 1.4% |
| Other | about 150 | 5% |

- **Every one of the 2,434 unmapped commanders had an owner who had lost** and was no longer among the game's players, with three or two of four players remaining. The first cell agrees: 486 of 486 lines read at its status check.
- **Every one of the 490 unplaceable cards was owned and controlled by a lost player** and sat in a surviving player's command zone. Gonti's effect is 406 of them; the rest are Praetor's Counsel, Mosswort Bridge, Worf, Merchant Raiders and Ezuri effects.
- **The token class is the two-player one.** It is the "Couldn't map" on a token already routed to Build 1 ([ADR-0129](ADR-0129-m13-monte-carlo-opponent.md)): 84 of 24,486 rollouts in the two-player clock cell.
- One pod of the first cell failed at startup on a profile-directory race between JVMs (`scripts/precon_cost.py` shares one `user.home` across pods). It is the script's, not the copier's.

## The fix, as routed

- **In the copier:** skip a commander-damage entry and an effect card whose owner is not among the copied players. Both are a few lines. The copy loses nothing a rollout can use: the lost player's commander can deal no more damage.
- **In the engine, the better upstream fix:** a player who leaves should take their effect cards out of other players' command zones (rule 800.4a). That changes mainline play in multiplayer and is upstream's call.
- **The boundary question.** A two-player game has no departed player while it runs, so the copier change should leave every two-player game identical. ADR-0025 asks for that as a forkcheck, not an argument; it is owed when the change is built.

## Consequences

- **Build 0's step 6 is closed.** The four-player track's blocker is named and is small.
- **Routed to Build 1:** the two copier skips with their forkcheck, beside the token-mapping failure already there. **Routed to the upstream worklist** as a candidate with the three copier fixes (Tier 0.12): the commander-damage skip is a clear bug in upstream's own guard.
- **`scripts/precon_cost.py`'s shared home** is routed to Build 2 with the other driver fixes.
- The diagnostic worktree and branch stay until the fix is built; they are the reproduction.
- No standing rule is born.
