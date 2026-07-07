# Upstream worklist

Seed-pinned, deterministically reproducible engine bugs harvested from Anvil
runs, queued for upstream PRs to Card-Forge/forge (per ADR-0002: static-bug
fixes are upstream PR #1; fork API is the flagship contribution, sequenced
before M2). Forge design conversations go in PRs/Discord, never issues
(prior-work survey: stale bot, ~35 days).

Repro: `uv run python -m anvil.bridge.harness replay d3pilot-20260704-175219 <game>`
(replay caveat from the batch-harness spec applies: solo replays are
self-consistent but can drift from in-run instances via AI wall-clock
timeouts; crash repros here are engine-path crashes and expected to
reproduce — verify before filing).

## Engine crashes — 50K pilot `d3pilot-20260704-175219` (fork `ca76c842a8`, 2026-07-06)

7 crashes in 50,000 games. All games' obs frames are readable; policy labels
usable (40.9K across the 21 readable crash+hardcap games), value-excluded via
`status`.

| game | seed | exception | turn | decks | profiles |
|---|---|---|---|---|---|
| 9204 | 5945958510859883103 | ConcurrentModificationException | 21 | dc-864165 vs dc-864162 | Experimental/Experimental |
| 9321 | 9091511573053637269 | ConcurrentModificationException | 31 | dc-864378 vs dc-863782 | Cautious/Reckless |
| 23533 | 1237691297111091176 | ConcurrentModificationException | 20 | dc-864206 vs dc-864589 | Cautious/Experimental |
| 39429 | 4871274615174445432 | ConcurrentModificationException | 25 | dc-864589 vs dc-864793 | Reckless/Cautious |
| 38257 | -3478740822025787825 | StackOverflowError | 17 | dc-863788 vs dc-864788 | Reckless/Default |
| 24846 | 7953943506196291359 | ArrayIndexOutOfBoundsException | 28 | dc-863786 vs dc-864922 | Default/Reckless |
| 7122 | 3723828607195549218 | NoSuchElementException | 41 | dc-864377 vs dc-864561 | Reckless/Default |

Notes:
- 4/7 are ConcurrentModificationException — likely one underlying iteration-
  during-mutation bug class; triage together (get stack traces via replay
  before assuming).
- StackOverflowError on `dc-863788` — one of the two grind-cluster decks from
  the D3 slow-tail census; possibly recursion in a loop the hard-cap games
  also exercise.

## Already-known (from M0, ADR-0002)

- Fork static-corruption bug classes (two, seed-reproducible) — upstream PR #1
  material, characterized in the forkcheck harness (fork `8907112`).
- `GameCopier.clonePlayer` swaps non-AI controllers to heuristic AI on fork —
  fix before M2 forking (playercontroller-override-plan.md landmine).
