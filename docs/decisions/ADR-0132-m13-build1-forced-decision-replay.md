# ADR-0132: forced-decision replay is an answer tape recorded at the bridge, and Build 1's inert commit is not a boundary

- **Date:** 2026-11-20
- **Status:** accepted
- **Design-doc anchor:** §9 (seeded replay, state forking); [m13-plan.md](../design/m13-plan.md) Build 1, pin 9, done-when 2; [ADR-0025](ADR-0025-d4-rebase-closeout.md) (the exemption); [ADR-0117](ADR-0117-certifier-merge.md) (the certifier deletion)

## Context

A served game did not reproduce from its seed and checkpoint. The server's batch numerics move an answer now and then, so no stored window could be reached again without luck. Build 1 was to add a replay mode that feeds a stored game's recorded answers back in place of a server, read its fidelity on about 20 games, and land it with ADR-0126's next-boundary items in one commit proven by trace hashes.

The plan assumed the store already held the answers. It holds each callback's result (the card chosen, the spell cast), not what the server sent. A cast plan's target references, a vetoed attempt, an attack map and the search's verdicts cannot be rebuilt from results without guessing.

## Decision

1. **The answers are recorded where they enter the game.** A served run with obs writes an answer tape into each game's frame (`{"k":"ans"}` records): every answer the mainline game took from the bridge, in order, and every search verdict that changed the game (a forced option, a forced pass, an armed surface answer). The allocation head's answer is taped too. A search copy's asks are not: the tape belongs to the game, and the session id tells the two apart.
2. **A replay runs the same worker command with `-b tape:<file>` and no server.** The replay bridge answers each ask from the tape. It first makes the draw from the game's random stream that the gRPC bridge makes before every round trip, so the stream stays where the served game had it. An ask the tape does not hold next ends that game as diverged and names the entry.
3. **A replay keeps the run's search flags.** The search monitor does on the replayed game what it did on the live one: the state-based check at the window, the allocation ask, the option scan, the cache clear. It plays no copy, and the seat applies the taped verdict. The first form dropped the search flags, and one self-play game in four then replayed differently, because the monitor's state-based check moves when a creature dies or a trigger goes on the stack.
4. **Recording is on by default** for a served run with obs (`--no-tape` turns it off). An older jar ignores the flag. Frames written before this commit carry no tape and cannot be replayed.
5. **The inert commit is not a boundary.** Fork branch `m13-build1` (tip `39827cb3b5`, five commits on the pin) carries the replay, the first player in every results row, the `CensusRun -certify` and `PayDirective` deletion, the frame cap fix and the search's copy-leak guard. Its forkcheck matches the era's baseline on all 500 seeds.
6. **`payment-evalset-v2` is retired as a certified set on this engine.** The replay runner reaches 25 of its 280 windows on the merged jar (5 of 56 positives, 20 of 224 auto-correct). A payment drill set for this era is mined afresh on the replay runner's own games.
7. **The oversize game has two sources, and one is fixed.** The recorder's cap was tested after the write, so a capped frame ran one record past the reader's 1 GiB bound and the reader refused it. The frame now ends under the bound. The size itself is not an engine loop. The seat's commander was Elminster, whose scry trigger makes a cost-reduction effect each time; 46 of them stood that turn. Every cost check of every option scan asks the controller to choose among them one at a time (`chooseSingleStaticAbility`, one candidate each), and each ask is recorded with a full observation: 38,701 asks in turn 31. Dropping the record of a one-candidate ask changes what the server is shown as history, so it is a boundary item and is routed, not done here.
8. **Crash fixes and copier changes are a separate commit and are not offered under the exemption.** They are in [ADR-0133](ADR-0133-m13-search-copies-leak.md).

## Evidence

**The fidelity read** (`scripts/m13_replay_fidelity.sh`, `data/runs/replay-fidelity/`; `iter-405`, seeds 20261123). Every game of four cells was replayed from its tape on the same jar and compared with the stored frame record by record. A game is identical when every record is equal apart from wall times: the state observed at each decision, the options, the answer, the result.

| Cell | Games | Identical | Same game | Differ |
|---|---|---|---|---|
| Network alone against the plain heuristic | 200 | 192 | 8 | 0 |
| The search recipe acting, against the plain heuristic | 100 | 89 | 9 | 2 |
| Self-play, sampled, the search behind the allocation head | 100 | 88 | 9 | 3 |
| Network alone against the Monte Carlo heuristic (8 rounds) | 20 | 20 | 0 | 0 |
| **All** | **420** | **389** | **26** | **5** |

The first cell is its second run (`data/runs/replay-fidelity-na/`). In the first, two servers shared the port by my error and six games crashed on a broken stream; that run is not counted.

- **"Same game"** means the replay agrees with the stored game at every served decision (the state it was asked in, its options, its answer) and at the end, while some record differs. The differences are ones two launches of the engine show anyway: an effect card's name carries a JVM-wide counter, equivalent options or the engine's own callbacks inside one step come in a different order, or a search copy's prompt was recorded in the live frame ([ADR-0133](ADR-0133-m13-search-copies-leak.md)).
- **The five that differ are not the replay's.** Three are the self-play games in which a search copy leaked mana into the live game; the leak guard names the same three, and no other game. One game ended live on the wall-clock draw limit, which a replay does not hit. In one the heuristic seat cast a different spell three decisions from the end; the cause is not read, and the same game differs the same way on the fixes jar.
- **One more kind was seen in the discarded run:** the seat held two copies of a card that lets it play a land, the two options came in the other order, and the taped index took the other copy. An option index is only as stable as the engine's option order.
- **So the engine itself is the limit.** About 1% of games (5 of 420, three of them the leak) do not reproduce from identical answers, and about 6% reproduce with records in a different order. Replay measures that rate; before it there was no instrument for it on served games.

**The exemption proof** (`scripts/forkcheck/run_forkcheck.sh`, the standing 500 seeds, baseline `run-20261118-mergefix-baseline`):

| Jar | Fork commit | Main-trace hashes | Copy fidelity |
|---|---|---|---|
| `forge-b1-inert.jar` | `6c934cafd2` (replay, deletion, cap) | 500 of 500 | 467 clean, 33 divergent |
| `forge-b1-inert2.jar` | `39827cb3b5` (adds replay under search flags and the leak guard) | 500 of 500 | 467 clean, 33 divergent |

The forkcheck plays heuristic seats and does not pass through the gRPC bridge, whose echo draws moved into a shared class. The replay itself covers that: a replayed game is identical only if the replay bridge's draws match the gRPC bridge's.

**The certifier deletion.** `PayDirective` was consulted only under `-paytelemetry` and matched nothing unarmed. `payment_certify.py` keeps one runner. The witness: the evalset's 280 jobs through `AnvilRun -replay` on the inert jar, one roll each (`data/runs/m13-build1/evalset-recert/`): 25 fired, 253 never fired, 2 diverged.

**The cap.** With the bound set to 3 MB, two games' frames end at 2,999,723 and 2,998,493 bytes with the cap's end record and decode at the bound.

## Consequences

- **Done-when 2 is met:** the fidelity read is on file.
- **A stored window is a tape position.** Reaching one is a replay to that entry. The fork point for a consumer (the gate on stored games, ADR-0125's truth stream, a re-search of a stored window) is not built: it is a stop at a tape entry plus the existing copy runners, and is routed to the first consumer, Build 4's truth stream.
- **A replay is also a detector.** A stored game that does not replay had something act on it that its tape does not hold. That is how the copy leak of ADR-0133 was found.
- **Not done here, routed by name:** the token "Couldn't map" class (0.3% of two-player rollouts; the fixes commit prints the asking site once per JVM, so the next Monte Carlo run names it) stays with Build 1's fixes commit. The three single-occurrence crashes (`getDividedValue`, `AttachAi.affectsAttached`, `checkRemoveCounterCost`) and the `StackOverflowError` go to the upstream worklist as candidates.
- **The fork pin does not move in this ADR.** The inert tip can become the pin under the exemption as it stands. Whether the fixes commit rides with it is ADR-0133's question.
- **Standing rule born** (engine, fork and data hygiene): a served run records its answer tape, and a claim about a stored game's state is checked by replaying it.

## Addendum, 2026-11-20: the pin moved

The user chose to land the fixes commit with this one ([ADR-0133](ADR-0133-m13-search-copies-leak.md), addendum). The fork pin is `cf78d3f046`; this ADR's inert tip `39827cb3b5` is in its history and has its own row in [fork-lineage.md](../design/fork-lineage.md).

