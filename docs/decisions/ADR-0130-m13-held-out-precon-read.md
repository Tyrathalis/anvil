# ADR-0130: the held-out precon read: `iter-405` wins 0.2798 ± 0.0063 on Commander precons as served, and 0.4078 ± 0.0069 once unseen cards carry their text (+12.80 ± 0.72pp, no training)

- **Date:** 2026-11-19
- **Status:** accepted (a measurement; the one decision is how an unseen card is served in later precon reads)
- **Design-doc anchor:** §1 (the card encoder), §8 (the pool); [m13-plan.md](../design/m13-plan.md) Build 0, step 5

## Context

The benchmark M13 builds toward is Commander precons, two-player first. `iter-405` trained on a 1,701-card pool drawn from Duel Commander lists. Build 0's step 5 owed its strength on precon decks before any training on them, with each deck's share of unseen cards on file. The benchmark's pins (pin 6: era boundaries, rules and bans per track, reference opponents) wait on this read.

Preparing the read turned up how the model sees a card outside its pool. A checkpoint carries its own card table: frozen text rows, structured features and a learned id row per pool card. A name outside the table gets the "no card" row, the one hidden cards and tokens use. Nothing counts or logs it. So served as it stands the model sees four fifths of a precon deck as blanks.

## Decision

1. **The held-out figure of record is the text arm: 0.4078 ± 0.0069.** It is `iter-405`, network alone, against the plain heuristic on 500 random precon pairs, with every card's text and features in its table and no weight trained. The as-served figure, 0.2798 ± 0.0063, is filed as the cost of the blank rows.
2. **Later precon reads serve an extended card table.** `scripts/m13_precon_table.py` builds it: the base rows byte-identical and in the base order, the new cards' text rows from the same pinned model, and a checkpoint copy whose card buffers match.
3. **An unseen card's id row is the no-card row.** The mean of the trained id rows reads the same (−0.02 ± 0.57pp), so the simpler choice stands.

## Evidence

**The decks.** Forge's own Commander precon files on the merged engine: 184 decks from 2011 through Star Trek (2026), Secret Lair decks included. They hold 6,525 unique cards; 586 are in the pool. Five commanders are in the pool.

| Release years | Decks | Median share of a deck's non-basic cards outside the pool |
|---|---|---|
| 2011 to 2020 | 54 | 85.5% |
| 2021 to 2023 | 67 | 79.7% |
| 2024 to 2026 | 63 | 73.8% |
| All | 184 | 80.3% (range 56.4% to 92.6%) |

**The read** (`data/runs/m13-precon/read/read.md`; `scripts/m13_precon.sh`). Three arms on the same seeds (20261121) and the same 500 pairs of distinct decks, 2,500 games per seat, masked, raw, the Monte Carlo jar with the switch off, 24 workers. A win is a win over all games.

| Arm | Games | Model winrate | Seat 0 / seat 1 | Draws | Crashes |
|---|---|---|---|---|---|
| As served: unseen cards blank, the pool's ability table | 5,000 | **0.2798 ± 0.0063** | 0.2616 / 0.2980 | 25 | 7 |
| Text and features, the no-card id | 5,000 | **0.4078 ± 0.0069** | 0.3960 / 0.4196 | 20 | 3 |
| Text and features, the mean id | 5,000 | 0.4076 ± 0.0069 | 0.3828 / 0.4324 | 15 | 2 |

| Paired on seat and seed | Difference | Up / down |
|---|---|---|
| Text, no-card id − as served | **+12.80 ± 0.72pp** | 1,004 / 364 |
| Text, mean id − as served | +12.78 ± 0.72pp | 1,014 / 375 |
| Mean id − no-card id | −0.02 ± 0.57pp | 399 / 400 |

**The splits** (exploratory; the thirds are cut on the decks' unseen shares).

| | As served | Text, no-card id | Games per arm |
|---|---|---|---|
| Model's deck under 77% unseen | 0.3294 ± 0.0113 | 0.4606 ± 0.0120 | 1,715 |
| 77% to 84% | 0.2841 ± 0.0113 | 0.4280 ± 0.0124 | 1,605 |
| 84% and over | 0.2250 ± 0.0102 | 0.3345 ± 0.0115 | 1,680 |
| Opponent's deck under 77% unseen | 0.2420 ± 0.0103 | 0.3819 ± 0.0117 | 1,715 |
| 77% to 84% | 0.2561 ± 0.0109 | 0.3639 ± 0.0120 | 1,605 |
| 84% and over | 0.3411 ± 0.0116 | 0.4762 ± 0.0122 | 1,680 |
| Model's deck from 2011 to 2020 | 0.1905 ± 0.0102 | 0.3020 ± 0.0119 | 1,480 |
| 2021 to 2023 | 0.3003 ± 0.0109 | 0.4355 ± 0.0118 | 1,775 |
| 2024 to 2026 | 0.3347 ± 0.0113 | 0.4693 ± 0.0119 | 1,745 |

- **The text is worth about 13 points at every level of the split.** The gain does not shrink where more of the deck is unseen.
- **The model does worse holding an older deck and better facing one.** Unseen share and release year move together, and older precons are also weaker decks, so the splits do not separate the model's unfamiliarity from the deck's strength. The heuristic mirror on these pairs would; it was not run.
- **The model loses to the heuristic on precons in every cell.** On its own pool it reads 0.6064 against the same opponent. The two figures are on different decks and are not a difference in pp.

## What is not clean

- **The ability table is incomplete for precon cards.** It was extended from 17,798 to 36,190 keys by a dump of the precon cards' printed abilities. Keys that only arise in play (tokens, granted abilities) are missing and are served as zeros in all three arms. The text arm's figure is a floor on this account.
- **The as-served arm differs from the text arms in two things:** the card table and the ability table. The 12.8 points are for both together.
- **A new crash:** `ArrayIndexOutOfBoundsException`, 8 games in 15,000. Four `NullPointerException` games in the as-served arm. No worker ran out of memory. The battery reports no anomaly in any arm.
- **Name handling.** Deck files mark foils with a trailing "+"; a split card is listed as "A // B" and indexed by "A"; two cards go by flavor names (Mind Flayer, the Shadow; E. Honda, Sumo Champion). The table script handles the first two and the names file carries the real names for the third. `anvil/encoder/cardtext.py` now resolves a split card's full name by its first face; the first extended server crashed without it.
- **The decks sit in Forge's user deck store** at `~/.forge/decks/commander/anvil-precons/` as `pc-NNN.dck`. The store is shared with the playable build; the subfolder keeps them apart from the pool's decks. `data/runs/m13-precon/deck-map.json` names each file.
- **Precons here are played under the project's two-player Commander rules.** Secret Lair decks are in the 184; pin 6 says whether they stay.

## Consequences

- **Pin 6 is ready for the user.** The eras as cut here are a starting point, not the pin: 2011 to 2020, 2021 to 2023, 2024 to 2026 hold 54, 67 and 63 decks.
- **The blank row is a silent failure.** A server that meets a card name outside its table should count it and say so. Routed to Build 1.
- **Pool growth by precon era starts from 0.41, not 0.28,** and the first era's training is measured against the text arm on that era's decks.
- **Routed to Build 1:** the `ArrayIndexOutOfBoundsException` crash; the unknown-card counter. **Routed to the pool-growth scoping:** ability keys that arise in play; the heuristic mirror on precon pairs as the deck-strength control.
- No standing rule is born.

## Addendum, 2026-11-19: the benchmark's deck list is 178 decks

**The precon benchmark's list is every paper Commander precon, 178 decks** (the user, 11-19). It is Forge's 184 files, less the eight Commander Anthology reprints, plus two Secret Lair decks Forge does not package. `scripts/precon_benchmark_decks.py` builds it to `data/benchmark/precons-178/` and installs it at `~/.forge/decks/commander/anvil-precons-178/`.

- **The list was checked against EDHREC's precon page:** 178 paper decks through Star Trek, the same 178. It is one outside source; both wikis refused the fetch.
- **The eight anthology decks are card-for-card copies** (set codes CMA and CM2). Two of them list their basic lands split by art, which reads as a difference in the files and is none.
- **The two added decks are "20 Ways to Win" (2024) and "Everyone's Invited!" (2025).** Every card in both has a Forge script. Their lists are from EDHREC and sit in `scripts/precon_extra/`. A 30-game heuristic smoke on them ran clean.
- **Secret Lair decks are in** (the user: they are not balanced differently from the other precons). **The two Magic Online theme decks are out.** **Foundations Commander is a 2026 release** (the user); its edition file's 2024 date is the set's.
- **The list's figures:** 6,583 unique non-basic cards, 585 in the pool; the median deck is 79.8% unseen (56.4% to 92.6%). By year: 5 each for 2011 and 2013 to 2016, 4 each for 2017 to 2019, then 9, 16, 24, 27, 26, 14 and 25 for 2020 to 2026.
- **The read above stands as filed.** Its 500 pairs were drawn over the 184 files, so the eight copied decks carried double weight (about 4% of deck slots). The next precon read uses the 178.
- **Still open in pin 6:** the era boundaries, the rules and bans per track, the reference opponents.

## Second addendum, 2026-11-19: the eras are three, and the pool grows oldest-first

**The benchmark reports by three eras: 2011 to 2020, 2021 to 2023, 2024 to 2026** (the user, 11-19). Pool growth takes them oldest-first. If the first era trains badly, it is split into sub-eras.

| Era | Decks | Unique non-basic cards | In the pool today | New cards, oldest-first |
|---|---|---|---|---|
| 2011 to 2020 | 46 | 2,158 | 175 | 1,983 |
| 2021 to 2023 | 67 | 3,218 | 327 | 2,198 |
| 2024 to 2026 | 65 | 3,186 | 421 | 1,815 |
| All | 178 | 6,583 | 585 | 5,996 |

- Each era more than doubles today's 1,701-card pool; the full list ends near 7,700 cards.
- Later precons reprint earlier ones: 802 of the middle era's cards and 1,177 of the last era's appear in an earlier era. Oldest-first gives three even steps.
- **Coverage of Forge's card scripts** (exploratory; 35,340 scripts, digital-only and un-cards included). A card counts as covered when every keyword, ability API, trigger mode, static mode and replacement event in its script appears on some card in the pool. Today's pool covers 90.2% of cards; the three eras bring that to 94.8%, 96.0% and 96.8%. Counting parameter names as well, the figures are 76.4%, then 84.9%, 89.1% and 91.5%. This counts script vocabulary, not how well a card is played.
- **Still open in pin 6:** the rules and bans per track, the reference opponents.

## Third addendum, 2026-11-19: deck strength, and the read adjusted for it

**Precon decks differ widely in strength, and once that is accounted for the model's deficit is flat: about 9 points below a heuristic holding the same decks, in every era and at every unseen share.** The era gradient in the read above is the decks, not the model's unfamiliarity.

**The mirror** (`pc-mirror`; `data/runs/pcmirror-20261119-200332`, `data/benchmark/precons-178/strength.json`; `scripts/precon_strength_report.py`). The plain heuristic in both seats on the 178 decks: 45 rounds in which every deck plays one opponent, five games a pair, 20,024 games, seeds 20261122. Each deck has about 225 games. 59 games were drawn and 38 crashed.

- **Deck winrates run from 0.151 to 0.893,** with a standard deviation of 0.140 across decks. Sampling alone would give 0.032.
- **A Bradley-Terry rating per deck** is fitted on all games, so a deck's opponents are accounted for. The spread is 112 on the Elo scale.
- **The seat does not matter:** seat 0 wins 0.4996 ± 0.0035.
- **Older decks are weaker.** Mean winrate 0.383 for 2011 to 2020 (46 decks), 0.533 for 2021 to 2023 (67), 0.547 for 2024 to 2026 (65).
- **Strongest:** Calling All Angels (0.893), Tramplesaurus Rex (0.809), Reign of Dragons (0.791), the Secret Lair Angels deck (0.782). Four of the five Foundations Commander decks are in the top seven. **Weakest:** Nature of the Beast (0.151), Political Puppets (0.191), Seize Control (0.200).
- A deck's rating correlates −0.19 with its share of unseen cards.
- These are strengths in the plain heuristic's hands, two-player. A deck the heuristic pilots badly reads as weak.

**The step 5 read, adjusted.** For each game of the read, the ratings give the winrate a plain heuristic would expect holding the model's deck against the opponent's. The eight anthology copies take their originals' ratings.

| Text arm (no-card id) | Games | Model winrate | A heuristic's expected winrate, same decks | Difference |
|---|---|---|---|---|
| All | 5,000 | 0.4078 ± 0.0069 | 0.5000 | −9.2pp |
| Model's deck from 2011 to 2020 | 1,480 | 0.3020 ± 0.0119 | 0.3945 | −9.3pp |
| 2021 to 2023 | 1,775 | 0.4355 ± 0.0118 | 0.5387 | −10.3pp |
| 2024 to 2026 | 1,745 | 0.4693 ± 0.0119 | 0.5501 | −8.1pp |
| Model's deck under 77% unseen | 1,715 | 0.4606 ± 0.0120 | 0.5329 | −7.2pp |
| 77% to 84% | 1,670 | 0.4305 ± 0.0121 | 0.5298 | −9.9pp |
| 84% and over | 1,615 | 0.3282 ± 0.0117 | 0.4342 | −10.6pp |
| Opponent's deck under 77% unseen | 1,715 | 0.3819 ± 0.0117 | 0.4671 | −8.5pp |
| 77% to 84% | 1,670 | 0.3617 ± 0.0118 | 0.4702 | −10.8pp |
| 84% and over | 1,615 | 0.4830 ± 0.0124 | 0.5658 | −8.3pp |

- **As served the same adjustment gives −22.0pp overall,** between −20.3 and −24.2pp in every cell.
- **What remains of the unseen-share effect is small:** −7.2pp for the most familiar third of decks against −10.6pp for the least. The cells' errors are about 1.2pp before the ratings' own error, which is not propagated here.
- **Exploratory.** The expected figure comes from ratings fitted on about 225 games a deck. The thirds are cut at the read's fixed 77% and 84%, so the middle and upper cells differ a little from the table above.

**What it changes.** Later precon reads report the model's winrate beside the heuristic's expectation for the same decks, from `strength.json`. The benchmark's pairs can also be balanced on rating. Neither is pinned here.

**A crash to route:** `ArrayIndexOutOfBoundsException` in 37 of 20,024 heuristic-only games, so it is the engine's and not the bridge's. It is already Build 1's (eight games in the read above).

## Fourth addendum, 2026-11-19: going first is worth about 2 points, and the decks do not differ in it

**The first player wins 0.5225 ± 0.0035 of decided games in the heuristic mirror,** against 0.5004 expected from the decks alone. A deck's winrate on the play is about 4.5pp above its winrate on the draw.

- **How it was read.** The mirror's records do not name the starting player. The same 20,025 seeds were replayed with `-turncap 1` and the census log (`pc-firstcap`, eleven minutes; the user's suggestion). The log names the coin-flip winner, and the heuristic always chooses to play. A 96-game check gave the same starter as full-length games in 96 of 96.
- **By the first player's era:** +1.5pp over the decks' expectation for 2011 to 2020, +2.7pp for 2021 to 2023, +2.1pp for 2024 to 2026.
- **No deck-level difference is resolved.** The play-minus-draw gap varies across decks with a standard deviation of 0.068; sampling alone gives 0.064. Each deck has about 112 games on each side.
- **The seat is not the starter:** seat 0 started 49.4% of games.
- Exploratory figures from the same mirror, not filed in detail: strength rises about 16 rating points (2pp of winrate) per release year; no color is clearly best; decks of one or two colors do better than three or four; the decks furthest above their year's trend are creature decks and those furthest below are group-hug, goad, spell and alternate-win decks. All of it is strength in the plain heuristic's hands.
- This bounds what the play-or-draw surface can be worth on these decks against this opponent: the whole choice is worth about 4.5pp to the side that makes it, if playing first is always right.
