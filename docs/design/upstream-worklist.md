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

Notes (replay triage, 2026-07-06):
- **6 of 7 do NOT reproduce solo** (all CME + ArrayIndexOOB + NoSuchElement
  replay decisive on the pinned jar) — load/timing-dependent thread races,
  not seed-determined engine bugs. **Upstream `1f0a3e0815` (#11161, merged
  2026-07-06) fixes exactly this class**: parallel mustAttack Combat mutation
  (unsynchronized `addAttacker` → CME + silently dropped attackers) and the
  non-volatile `timeoutReached` cancellation flag (on JDK 20+ the ONLY
  cancellation signal — a wedged-eval-thread mechanism relevant to our
  runaway-frame class and timeout-pass tail). **Do not file these upstream;
  verify statistically instead**: pilot baseline ~1.4 CME/10K games under
  w=16 load; the post-bump crash census should read ~0.
- **38257 StackOverflowError reproduces deterministically** — solo, both on
  the pinned jar and on a #11161-patched build (same turn 17, ~36 s), so
  #11161 does not cover it. **This is the one genuine filing candidate.**
  Breadcrumbs: "Spider-Man 2099 … [Couldn't add to stack, failed to target]"
  immediately precedes the crash; Lumra, Bellow of the Woods also in play.
  The runner's catch doesn't print the stack — capture it with an
  instrumented build when filing.
- **#11161 is the anchor for the next dataset-boundary fork bump** (after
  d6ext completes or its stopping rule fires — never mid-run). It should
  also shrink ADR-0002's nondeterminism floor (the races are a same-seed
  divergence source) and adds a stack-dump-per-AI-timeout that turns the
  slow-tail seeds into log-diagnosable profiler samples. Cherry-pick applies
  cleanly to our fork: branch `test-11161` (verified building + playing).

## Already-known (from M0, ADR-0002)

- Fork static-corruption bug classes (two, seed-reproducible) — upstream PR #1
  material, characterized in the forkcheck harness (fork `8907112`).
- `GameCopier.clonePlayer` swaps non-AI controllers to heuristic AI on fork —
  fix before M2 forking (playercontroller-override-plan.md landmine).
