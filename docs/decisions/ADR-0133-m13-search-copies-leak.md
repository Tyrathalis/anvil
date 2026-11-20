# ADR-0133: a search copy can change the live game: refunded mana lands in the real player's pool, and a copy's prompt can be asked of the real controller

- **Date:** 2026-11-20
- **Status:** proposed (the finding is measured; the fix is built and proven on 500 heuristic seeds; landing it is the user's call, because it changes searched games)
- **Design-doc anchor:** §9 (state forking); invariant 1 (the engine adjudicates every claim); [m13-plan.md](../design/m13-plan.md) Build 1 ("a crash fix never qualifies"); [ADR-0131](ADR-0131-m13-copier-cause.md) (the copier's departed-player failures); [ADR-0132](ADR-0132-m13-build1-forced-decision-replay.md) (the replay that found this)

## Context

Forced-decision replay ([ADR-0132](ADR-0132-m13-build1-forced-decision-replay.md)) replays a stored game with no search copies. Two of the first four self-play games did not replay: the live game's state differed from the replay's at a window where nothing had been decided in between. One was the replay's own omission and is fixed there. The other was the live game.

## Decision

1. **The search's copies can change the game they were copied from.** Two paths are identified, both in the game copier, both present on upstream master and on the old engine pin (`5bd040351f`):
   - **Refunded mana.** The copier puts the original pool's mana objects into the copy's pool. Each mana object names the player it belongs to, and a refunded payment returns mana to that player's pool. When a copy spends floating mana and then rolls the payment back, the mana is added to the real player's pool. The real game gains mana that no land produced.
   - **A prompt asked of the real controller.** An effect card's abilities are copied as last-known information and keep the real game's activating player. An optional replacement reads its "you" from the ability before the handler sets it, so the copy asks the real game's controller. The answer acts on the copy, but the callback is recorded in the real game's frame and enters the history the server is shown.
2. **The first path needs floating mana at a searched window.** The heuristic never leaves mana floating across a priority pass. The network taps lands as separate actions, so its seat does.
3. **A guard now watches for it.** The search compares the game's observed state before and after each window's copies and reports a difference: a line in the worker's log, a `searchLeak` census row, a count in the worker's tally. It is in the inert commit and is on by default. It sees what the observation sees (zones, counters, life, mana pools); it does not see the second path, which leaves the state unchanged.
4. **The fix is built on fork branch `m13-build1-fixes2`** (`87d9411e7b`): the copy's mana names the copy's player, and a copied effect card's abilities name the copy's players. The same commit carries the two engine crash fixes and ADR-0131's two skips.
5. **Landing the fix is a boundary for searched games and is not decided here.** The heuristic forkcheck cannot see it: 500 of 500 seeds match with the fix. A searched game in which a copy would have leaked plays differently with it.

## Evidence

**The first sight** (`data/runs/m13-build1/rf-smoke`, self-play with the search at every window, seeds 20261122). Game 0, turn 16: the seat taps one Forest under Contamination and the stored frame shows three black mana at its next window. The replay shows one. The same game in a second run with the guard set to check every copy (`rf-smoke3`):

```
[search] LEAK g0.s61 (t16 MAIN1 seat 0): the game's state changed across its copies;
  before ..."mana":{"B":1}... after ..."mana":{"B":3}...
```

The guard names the copy: `g0.s61r0o1`, the forced option a modal removal spell. That run had 1 leaking window in 441 searched.

**The rate** (the fidelity read's searched cells, `data/runs/replay-fidelity/`, `iter-405`, seeds 20261123):

| Cell (inert jar, the leak present) | Games | Searched windows | Windows that leaked | Games with a leak |
|---|---|---|---|---|
| The search at every window, against the plain heuristic | 100 | 4,506 | 0 | 0 |
| Self-play, sampled, the search behind the allocation head | 100 | 881 | 5 | 3 |

- **It is rare, and in this sample it is self-play's.** Five windows in 881 is 0.57% (a small count: between about 0.2% and 1.3%). Against the heuristic none leaked in 4,506 windows, which puts that rate under about 0.07%.
- **The replay agrees with the guard game for game.** The three self-play games the guard flagged are the three that did not replay; no unflagged self-play game differed.
- The first sight above was self-play with every window searched: 1 window in 441.

**With the fix** (the same cells and seeds on `forge-b1-fixes2.jar`):

| Cell (fixes jar) | Games | Searched windows | Windows that leaked | Replayed identically | Same game | Differ |
|---|---|---|---|---|---|---|
| The search at every window, against the plain heuristic | 100 | 4,464 | 0 | 99 | 0 | 1 |
| Self-play, sampled, the search behind the allocation head | 100 | 915 | 0 | 96 | 4 | 0 |

- No window leaked in 5,379. Every self-play game replays.
- **The second path looks gone too, on a count.** The searched cells hold 18 "same game" games on the inert jar ([ADR-0132](ADR-0132-m13-build1-forced-decision-replay.md)) and 4 on the fixes jar, none of them in the cell against the heuristic. I traced one of the 18, a commander replacement prompt recorded from a copy's depth; the others are not sorted between this and record order.
- The one game that differs is the same seed that differs on the inert jar: the heuristic seat casts a different spell near the end. It is not the leak.

**The forkcheck** on the fixes jar: 500 of 500 main-trace hashes match the era's baseline; copy fidelity 467 clean, 33 divergent, the pin's. The first fixes jar (`508c0028b2`, the crash fixes and the two skips alone) also matched 500 of 500 at 467 clean.

**The code.** `GameCopier` copies the pool with `addManaNoEvent(m)` on the original's `Mana` objects; `Mana` is a record with a `player` field; `ManaRefundService.refundManaPaid` groups paying mana by `Mana::getPlayer` and adds it to that player's pool. `ReplacementHandler.executeReplacement` resolves `OptionalDecider` from the effect ability before it sets the ability's activating player. Both read the same on `5bd040351f`.

## What it touches

- **The old era is not sized.** `scripts/leak_scan.py` looks for a pool that grew between the search's option scan and the seat's ask. In 2,880 big-run games (iterations 400 to 405) it finds none in 46,848 windows it can see. But it sees only windows whose scan fired a recorded callback, about one in ten, and it finds none of the six leaks the guard caught in this session's games. Its zero says little. The code path is the same on the old pin, so the old era should be assumed to have leaked at a similar rate.
- **Where it can have acted:** generation under the recipe, the with-lookahead reads, the in-loop arms. Network-alone reads play no copy and are untouched.
- **The direction favours the searched seat,** which gains mana. At the rates above it is a few games in a hundred in self-play and fewer against the heuristic. That is small against the with-lookahead margin (about 3pp on the old era) but it is not zero, and it sits on the search-on side of M13's first comparison.
- **Monte Carlo rollouts use the same copier.** The guard is not on that path and no rate is measured. The 20 Monte Carlo games of the fidelity read all replayed identically.
- **Training data.** A game with leaked mana is a game the rules do not allow. About 3% of this sample's self-play games are such games.

## The options, for the user

1. **Land the fixes commit with the inert commit, as one boundary, before the arms.** The arms then start on an engine whose copies do not leak and whose two commonest crashes are gone. Day-zero's network-alone figures stand as they are for the leak (no copy is played); the crash fixes change only the games that crashed, about 0.3%. My recommendation: the arms are a month of box time, and the fix removes a bias from the one comparison they exist to make.
2. **Land the inert commit alone and keep the leak through the arms.** The control and soft-target arms would train with it, the search-off arm without it. At 3% of self-play games the bias is small, but it has a sign.
3. **Price it first:** a paired with-lookahead read of `iter-405` on the two jars, the same seeds (2,000 games is about 1.5 box hours a side). Against the heuristic the leak rate reads zero, so this read would mostly price the crash fixes; I do not think it is worth its time.

## Consequences

- Nothing is pinned by this ADR. The fixes jar and its commit are at `data/runs/m13-build1/forge-b1-fixes2.{jar,commit}`.
- **Upstream candidates**, for the worklist: the copier's mana copy (a clear bug in upstream's own simulation AI), the `OptionalDecider` ordering, the `SacrificeEffect` index, the charm null check. None is filed.
- **Standing rule born** (search, budgets and run sizing): a run that plays copies reports its leak count, and a nonzero count is read before the run's numbers are.
- **Routed:** the guard on the Monte Carlo path (with Build 2, where the Monte Carlo share enters the queue). A wider offline scan of old stores only if the user wants the old era sized further.
