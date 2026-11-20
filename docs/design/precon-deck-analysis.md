# Precon deck analysis: the heuristic mirror on the 178 benchmark decks

**Doc status:** survey · the precon heuristic mirror of 2026-11-19 (ADR-0130, third and fourth addenda)

**Every figure here is a deck's strength in the hands of Forge's plain heuristic, in two-player Commander at 40 life.** It is not a deck's strength in human hands or in a pod. The heuristic plays creature decks well and plays political, reactive, spell-based and alternate-win decks badly, and the tables show it. All of it is exploratory.

The data: 20,024 games with the heuristic in both seats, 45 rounds in which every deck plays one opponent, about 225 games a deck (`data/runs/pcmirror-20261119-200332`). A rating is a Bradley-Terry fit on all games, on the Elo scale, with 0 the average deck. The starting player comes from a one-turn replay of the same seeds. Regenerate with `scripts/precon_strength_report.py` and `scripts/precon_deck_analysis.py`; the per-deck file is `data/benchmark/precons-178/deck-analysis.json`.

## What it says

- **Decks differ enormously.** Winrates run from 0.151 (Nature of the Beast) to 0.893 (Calling All Angels).
- **Strength rises about 2 points of winrate per release year,** unevenly: 2017 stands above its neighbours, 2018 and 2019 dip, and 2024 is a step down between two strong years.
- **No color is clearly best.** Decks of one or two colors do better than decks of three or four, probably because the heuristic's mana is simpler.
- **The outliers are the pilot's.** The decks furthest above their year's trend are angels, dinosaurs, dragons, counters and poison. The decks furthest below are group-hug, goad, spellslinger, storm and alternate-win decks.
- **Known disagreements with players' opinion** (the user, 11-19): Peace Offering and Counter Intelligence are regarded as strong and read near the bottom here; Goblin Storm is regarded as weak and reads weak. Peace Offering's politics have no object in a two-player game.
- **Going first is worth about 2 points,** and more between strong decks: +5.1pp when both decks are in the strongest third, +0.7pp when both are in the weakest. This fits the user's guess that the decks the heuristic plays well are the proactive ones, which gain most from the first turn. Single decks are not resolved: each has about 112 games on either side.

A color here is a color in the mana cost of any card in the deck.

## Going first

The first player wins 0.5225 ± 0.0035 of 19927 decided games; the decks alone predict 0.5004.

| The first player's deck, by rating | Games | First player wins | Decks alone | Edge |
|---|---|---|---|---|
| weakest third | 6573 | 0.3527 ± 0.0059 | 0.3419 | +1.1pp |
| middle third | 6624 | 0.5296 ± 0.0061 | 0.5042 | +2.5pp |
| strongest third | 6730 | 0.6813 ± 0.0057 | 0.6515 | +3.0pp |

| Both decks, by rating | Games | First player wins | Decks alone | Edge |
|---|---|---|---|---|
| both in the weakest third | 2207 | 0.5070 ± 0.0106 | 0.4998 | +0.7pp |
| both in the strongest third | 2166 | 0.5540 ± 0.0107 | 0.5033 | +5.1pp |

Per deck, winrate on the play minus on the draw: mean +0.045; standard deviation across decks 0.068, where sampling alone gives 0.064. Its slope on the deck's rating is +0.13 ± 0.04pp per 10 rating points.

## The trend by release year

+16.2 ± 1.8 rating points a year (R² 0.31); winrate +1.97 ± 0.23pp a year.

| Year | Decks | Mean winrate | Mean rating | Best | Worst |
|---|---|---|---|---|---|
| 2011 | 5 | 0.297 | -174 | Heavenly Inferno [COM] [2011] (0.41) | Political Puppets [COM] [2011] (0.19) |
| 2013 | 5 | 0.292 | -165 | Eternal Bargain [C13] [2013] (0.42) | Nature of the Beast [C13] [2013] (0.15) |
| 2014 | 5 | 0.313 | -153 | Guided by Nature [C14] [2014] (0.39) | Built from Scratch [C14] [2014] (0.23) |
| 2015 | 5 | 0.420 | -75 | Wade into Battle [C15] [2015] (0.64) | Seize Control [C15] [2015] (0.20) |
| 2016 | 5 | 0.416 | -65 | Breed Lethality [C16] [2016] (0.64) | Stalwart Unity [C16] [2016] (0.28) |
| 2017 | 4 | 0.497 | -5 | Draconic Domination [C17] [2017] (0.61) | Arcane Wizardry [C17] [2017] (0.32) |
| 2018 | 4 | 0.403 | -76 | Exquisite Invention [C18] [2018] (0.53) | Subjective Reality [C18] [2018] (0.36) |
| 2019 | 4 | 0.363 | -110 | Primal Genesis [C19] [2019] (0.43) | Faceless Menace [C19] [2019] (0.35) |
| 2020 | 9 | 0.433 | -47 | Ruthless Regiment [C20] [2020] (0.59) | Arcane Maelstrom [C20] [2020] (0.28) |
| 2021 | 16 | 0.491 | -8 | Draconic Rage [AFC] [2021] (0.64) | Prismari Performance [C21] [2021] (0.31) |
| 2022 | 24 | 0.525 | +21 | Urza's Iron Alliance [BRC] [2022] (0.69) | Maestros Massacre [NCC] [2022] (0.30) |
| 2023 | 27 | 0.566 | +53 | Angels They're Just Like Us, but Cooler and with Wings [SLD] [2023] (0.78) | Timey-Wimey [WHO] [2023] (0.33) |
| 2024 | 26 | 0.484 | -8 | Animated Army [BLC] [2024] (0.72) | Peace Offering [BLC] [2024] (0.29) |
| 2025 | 14 | 0.560 | +47 | Eternal Might [DRC] [2025] (0.72) | Counter Intelligence [EOC] [2025] (0.22) |
| 2026 | 25 | 0.606 | +85 | Calling All Angels [FDC] [2026] (0.89) | Goblin Storm [SLD] [2026] (0.42) |

## Colors

| Color | Decks with it | Mean winrate | Rating against decks without it, year trend removed |
|---|---|---|---|
| White | 101 | 0.509 | +8 ± 14 |
| Blue | 99 | 0.489 | -23 ± 14 |
| Black | 88 | 0.507 | +17 ± 14 |
| Red | 97 | 0.486 | -29 ± 14 |
| Green | 86 | 0.485 | -22 ± 14 |

| Colors in the deck | Decks | Mean winrate | Mean rating |
|---|---|---|---|
| 1 | 14 | 0.543 | +40 |
| 2 | 59 | 0.519 | +15 |
| 3 | 89 | 0.479 | -16 |
| 4 | 7 | 0.464 | -31 |
| 5 | 9 | 0.535 | +25 |

| Combination | Decks | Mean winrate | Mean rating | Years |
|---|---|---|---|---|
| W | 3 | 0.669 | +165 | 2014 to 2026 |
| G | 2 | 0.600 | +92 | 2014 to 2026 |
| WUBG | 1 | 0.640 | +88 | 2016 to 2016 |
| RG | 5 | 0.602 | +81 | 2021 to 2024 |
| UB | 6 | 0.577 | +60 | 2020 to 2024 |
| WU | 4 | 0.538 | +48 | 2021 to 2022 |
| C | 1 | 0.587 | +46 | 2023 to 2023 |
| WG | 6 | 0.576 | +43 | 2017 to 2026 |
| WUB | 12 | 0.556 | +39 | 2013 to 2026 |
| WB | 6 | 0.540 | +39 | 2015 to 2026 |
| WUBRG | 9 | 0.535 | +25 | 2017 to 2026 |
| WR | 6 | 0.532 | +23 | 2015 to 2026 |
| WUBR | 2 | 0.506 | +19 | 2016 to 2026 |
| WBR | 9 | 0.517 | +14 | 2011 to 2026 |
| U | 2 | 0.495 | +12 | 2014 to 2026 |
| WBG | 6 | 0.503 | +4 | 2011 to 2025 |
| BR | 5 | 0.498 | -3 | 2019 to 2024 |
| UG | 8 | 0.477 | -13 | 2015 to 2026 |
| WUR | 14 | 0.487 | -15 | 2011 to 2026 |
| URG | 7 | 0.486 | -20 | 2011 to 2025 |
| BG | 6 | 0.477 | -24 | 2015 to 2026 |
| UBR | 9 | 0.463 | -24 | 2013 to 2026 |
| B | 3 | 0.462 | -27 | 2014 to 2026 |
| BRG | 6 | 0.457 | -28 | 2013 to 2026 |
| UBG | 6 | 0.460 | -34 | 2011 to 2025 |
| R | 3 | 0.480 | -37 | 2014 to 2026 |
| WRG | 11 | 0.443 | -44 | 2013 to 2025 |
| WBRG | 1 | 0.431 | -49 | 2016 to 2016 |
| UR | 7 | 0.422 | -59 | 2015 to 2026 |
| WURG | 2 | 0.430 | -69 | 2016 to 2026 |
| WUG | 9 | 0.396 | -75 | 2013 to 2026 |
| UBRG | 1 | 0.307 | -160 | 2016 to 2016 |

## Furthest above their year's trend

| Deck | Colors | Winrate | Rating | Against the trend |
|---|---|---|---|---|
| Calling All Angels [FDC] [2026] | W | 0.893 | +379 | +308 |
| Wade into Battle [C15] [2015] | WR | 0.644 | +116 | +224 |
| Angels They're Just Like Us, but Cooler and with Wings [SLD] [2023] | W | 0.782 | +236 | +214 |
| Tramplesaurus Rex [FDC] [2026] | G | 0.809 | +263 | +192 |
| Reign of Dragons [FDC] [2026] | R | 0.791 | +251 | +180 |
| Breed Lethality [C16] [2016] | WUBG | 0.640 | +88 | +180 |
| Corrupting Influence [ONC] [2023] | WBG | 0.742 | +198 | +176 |
| Draconic Domination [C17] [2017] | WUBRG | 0.613 | +97 | +172 |
| Vampiric Bloodlust [C17] [2017] | WBR | 0.621 | +75 | +150 |
| Urza's Iron Alliance [BRC] [2022] | WUB | 0.692 | +147 | +141 |

## Furthest below

| Deck | Colors | Winrate | Rating | Against the trend |
|---|---|---|---|---|
| Counter Intelligence [EOC] [2025] | WUR | 0.222 | -216 | -271 |
| Peace Offering [BLC] [2024] | WUG | 0.291 | -152 | -191 |
| Tricky Terrain [M3C] [2024] | UG | 0.288 | -139 | -177 |
| 20 Ways to Win [SLD] [2024] | WUBRG | 0.344 | -137 | -175 |
| Blame Game [MKC] [2024] | WR | 0.324 | -137 | -175 |
| Goblin Storm [SLD] [2026] | R | 0.416 | -100 | -171 |
| Arcane Maelstrom [C20] [2020] | URG | 0.276 | -196 | -169 |
| Quick Draw [OTC] [2024] | UR | 0.356 | -128 | -166 |
| Timey-Wimey [WHO] [2023] | WUR | 0.335 | -143 | -165 |
| Paradox Power [WHO] [2023] | URG | 0.324 | -141 | -163 |
