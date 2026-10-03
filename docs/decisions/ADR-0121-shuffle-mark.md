# ADR-0121: The shuffle mark — draw coverage for the Ante ledger

- **Date:** 2026-09-27
- **Status:** accepted (the ADR-0025 proof pending: the forkcheck runs on the quiet box after the settings pass closes; the jar becomes the pin of record only on PASS)
- **Design-doc anchor:** §7 (Ante) and §9 (bridge / store)

## Context

The Ante ledger corrects a draw only while the drawing player's library order is provably unknown. An order-revealing decision (scry, surveil, put-on-top, an ordered move to the library) poisoned that player for the rest of the game, because the shuffle that voids the knowledge was not observable in the record stream. The 09-16 reference read (seat 1 of the merged jar's arm, 990 games) shows the price: 9,930 draw nodes corrected against 10,735 skipped as poisoned and 771 skipped for every other reason. [ADR-0119](ADR-0119-value-function-first-before-the-big-run.md) step 2 routed the fix as a fork commit with its own boundary pricing.

The seam exists on both sides. Every shuffle goes through one engine method, `Player.shuffle`, which fires a `GameEventShuffle` on the game's synchronous event bus after the library is set. The store frame already has a `mark` record kind: written on store sessions only, never on the wire sessions search and fidelity copies use, ordered by stream position, and read by nobody today. The fidelity check hashes the monitor's per-turn digests, not the record stream.

## Decision

1. **The fork records every shuffle as a mark, either seat.** `Obs.startGame` subscribes a listener on the store session's game; on the event it writes `{"k":"mark","m":"shuffle","s":seq,"t":turn,"p":seat}` through `Obs.mark`, which is gated on the store session and the current game. Search and fidelity copies get a fresh event bus per `Game` and never a store session, so they write nothing. The game path is untouched. Fork test `ShuffleMarkTest` (2): both seats' shuffles land in stream order in a real frame; a game without a session writes nothing.

2. **Not a boundary.** The mark is additive: no schema-version bump, every existing reader ignores marks it does not name, a store without marks reads exactly as before, and the number of record (the raw winrate) does not move. The [ADR-0025](ADR-0025-d4-rebase-closeout.md) proof is still run: the 500-seed forkcheck against the 09-16 baseline, held until the settings pass closes because its cells are compared at equal box time against the shakedown's arms. The fork commit `8d82dfa546` (on the tip `cd4b9d9951`) is written, built and tested now; it reaches the pin and [fork-lineage.md](../design/fork-lineage.md) on PASS.

3. **The ledger's cleanse.** A shuffle mark for seat p between two records voids every piece of library knowledge the ledger holds for p: the poison flag, the London known-bottom list, and the seen status of every p-owned entity not serialized in a non-library zone at the next record. A looked-at library card is a uniform draw again once shuffled; a card in hand, in play or in the yard stays seen. The cleanse applies after that record's own draw detection: events inside one gap have no order, so a draw in the shuffle's gap is judged under the pre-shuffle state. Skipping a draw because the card was once seen would be a selection on the outcome, which is why the seen set is cleansed and not merely the flag. `ledger.extract` reads `traj.marks` by position; six tests in `tests/test_ante_shuffle.py`; the skip census gains a `shuffle_cleanse` row.

4. **Sequencing.** The forkcheck and the Ante re-measure (ADR-0119 step 2's first half) both need the quiet box, and the re-measure needs the anchored head, so one read after the pass closes serves both: the re-measure's games generate on the new jar with the anchored checkpoint, and its census reports `shuffle_cleanse` beside `draw_poisoned`.

## Consequences

- Draw coverage is bounded by the census above: at most the poisoned half returns, minus the draws inside a shuffle's own gap. The re-measure's effective-sample ratio decides whether corrected reads become the number of record (the ADR-0119 step 3 bar, 1.5×).
- One standing rule: a chance event that voids knowledge the ledger tracks is a stream record, not an inference.
- Routed by name: the heuristic seat's order-revealing decisions are never recorded, so that seat is never poisoned (a pre-existing gap, now visible against the mark's census); the same-gap conservatism is measurable from the re-measure and stays unless it costs coverage; the fork-lineage row and the pin move on the forkcheck's PASS.
