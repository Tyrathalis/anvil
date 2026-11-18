# The measurements before the M13 scoping — designs and results

**Doc status:** living · draft designs for the ladder of own checkpoints, the search-ranking gate and the search's wall cost ([ADR-0126](../decisions/ADR-0126-m12-closeout.md) decision 3); the ladder closed 11-17 (its result is in §1); the precon cost measurement is done (§4); the gate closed 11-18 (§2: the soft-target arm runs); the wall cost is not launched

Drafted 2026-11-16. The numbers marked *estimate* are arithmetic on measured prices, not measurements. Each design ends with what the user has to pin before launch.

## Summary

| Measurement | What it decides | Box time | Fork work |
|---|---|---|---|
| The ladder | M13's scoreboard; whether `iter-513` and `iter-405` separate head to head | 12.0 h (closed 11-17) | none |
| The search-ranking gate | whether the soft-target arm is run at all | 14.6 h (closed 11-18: the arm runs) | none expected |
| The search's wall cost | how many more games a search-off arm plays at equal box time | about 2 h, quiet box | none |

**One finding changes ADR-0126's wording.** The gate cannot be run offline on the big run's stored windows. A stored window of a model-served game cannot be reached again: seed, checkpoint and flags do not pin a search line across serving setups, and no tool forks from a stored coordinate of such a game. The stores hold the search's side in full (per-option, per-roll leaf values, the margin, the acted flag). The rollout truth has to be generated live. The gate is therefore a live read, and its name here is "the search-ranking gate".

## 1. The ladder of own checkpoints

**Question.** How do the run's checkpoints order against each other, and does that order match the order against the heuristic?

**Why it matters.** Strength has been measured only against the heuristic, and half of training is against it. Head to head, `iter-405` scores 0.5865 ± 0.0057 against its warm start on 5,000 games, which is a larger separation than the heuristic read gives for the same pair. The ladder is a more sensitive scoreboard for M13's arms if that holds across the run.

**Checkpoints.** The warm start (`shakedown-alloc/iter-019`), `big-run/iter-099`, `iter-301`, `iter-405`, `iter-513`. All five are on disk. `iter-301` is used as trained, not the `iter-301-rechead` transplant; the two play identically network-alone.

**Instrument.** [`scripts/h2h_read.py`](../../scripts/h2h_read.py), one call per pair, network-alone, masked, on `forge-tgtmask3.jar` at 24 workers and 2 servers. Each call plays both seat assignments on the same seeds and refuses an arm with an unrouted ask. Measured price: 1 h 50 m for 5,000 games.

**Design.**

- **Adjacent pairs at 5,000 games** (2,500 per seat assignment): start–099, 099–301, 301–405, 405–513. SE about 0.006 each.
- **The other five pairs at 2,000 games**: start–301, start–513, 099–405, 099–513, 301–513. SE about 0.009 each. The pair start–405 is already on file at 5,000 and is not replayed.
- **One seed base for all nine pairs**, fresh (not 20261115), so every pair plays the same decks and seeds.
- **A Bradley-Terry fit over the ten pairs**, with a bootstrap over game indices for its errors. This is a new script of about 100 lines; nothing in the repo fits one.

**Cost.** 4 × 1.84 h + 5 × 0.74 h ≈ 11 box-hours (*estimate*). One overnight launch through `anvil.runs`, as a chain of nine calls.

**Reads, all exploratory.** No bar is attached: this builds a scoreboard and tests no mechanism.

- The fitted ratings and their order, beside the order against the heuristic.
- Transitivity: whether the adjacent-pair margins add up to the long-pair margins within error. A failure means a one-dimensional ladder is the wrong scoreboard.
- `iter-405` against `iter-513`. The heuristic read put `iter-513` −0.78 ± 0.73pp under. A head-to-head read at SE 0.6pp is the first that could separate them.
- Seat effect per pair. The one read on file shows seat 0 winning 0.483 of decisive games.

**Pinned and launched 2026-11-16 (the user).** Seed base 20261116; 5,000 games on the adjacent pairs and 2,000 on the other five. The run is `ladder` ([`scripts/ladder_chain.sh`](../../scripts/ladder_chain.sh)); its reports are `data/runs/lad-<A>-<B>-h2h.json`. The Bradley-Terry fit is written while it runs.

### Result (closed 2026-11-17)

**One rating per checkpoint describes all ten pairs, and the order matches the order against the heuristic.** The run closed with exit 0 after 12.0 box-hours. The fit is [`scripts/ladder_fit.py`](../../scripts/ladder_fit.py) over the nine reports and the 11-15 pair; its output is `data/runs/ladder/fit.md`.

| Checkpoint | Elo over the warm start | ± | Paired over the era reference against the heuristic (5,000 games) |
|---|---|---|---|
| `shakedown-alloc/iter-019` (warm start) | 0 | | not read at 5,000 |
| `big-run/iter-099` | +31.0 | 2.9 | +4.22 ± 0.79pp |
| `big-run/iter-301` | +49.4 | 3.0 | +6.32 ± 0.79pp |
| `big-run/iter-405` | +60.5 | 2.8 | +9.46 ± 0.77pp |
| `big-run/iter-513` | +62.3 | 3.2 | +8.61 ± 0.79pp |

| Pair (A against B) | Games | A's score | ± | Fitted | Residual (SE) |
|---|---|---|---|---|---|
| 099 – start | 5,000 | 0.5385 | 0.0056 | 0.5444 | −1.05 |
| 301 – 099 | 5,000 | 0.5241 | 0.0055 | 0.5265 | −0.44 |
| 405 – 301 | 5,000 | 0.5133 | 0.0054 | 0.5159 | −0.48 |
| 513 – 405 | 5,000 | 0.5019 | 0.0055 | 0.5027 | −0.14 |
| 301 – start | 2,000 | 0.5787 | 0.0085 | 0.5706 | +0.96 |
| 405 – start (11-15) | 5,000 | 0.5865 | 0.0057 | 0.5861 | +0.07 |
| 513 – start | 2,000 | 0.5940 | 0.0090 | 0.5887 | +0.59 |
| 405 – 099 | 2,000 | 0.5463 | 0.0087 | 0.5423 | +0.45 |
| 513 – 099 | 2,000 | 0.5335 | 0.0085 | 0.5450 | −1.35 |
| 513 – 301 | 2,000 | 0.5270 | 0.0084 | 0.5186 | +1.00 |

The four reads, all exploratory:

- **Order.** The ratings rise in training order, as the heuristic reads do. The two scoreboards disagree only on `iter-405` against `iter-513`, where neither separates them.
- **Transitivity holds.** No residual passes 1.35 SE, and the squared residuals sum to 5.8 on 6 degrees of freedom. A one-dimensional ladder is a fair scoreboard for this lineage.
- **`iter-513` and `iter-405` are level.** 0.5019 ± 0.0055 head to head, +1.8 Elo in the fit against a combined error of about 4. The heuristic read was −0.78 ± 0.73pp. Segment 5 moved the network by nothing either scoreboard can see.
- **Seat.** Seat 0 won between 0.468 and 0.495 of decisive games in all nine pairs. This is not a seat effect: seat 0 always holds the first deck of the pairing, and the nine pairs share pairings. Over the 200 pairings the first deck wins 0.490 ± 0.018.

**What it says about the scoreboard.** A head-to-head read is somewhat tighter than a heuristic read at the same size: 0.55pp against 0.73pp on 5,000 games. Its margins are not uniformly larger. From `iter-301` to `iter-405` the heuristic reads moved 3.1pp and the head-to-head score 1.3pp; from the warm start to `iter-099` it is the other way round. So the ladder is a second scoreboard that agrees with the first, not a sharper replacement for it.

**What it says about the run.** The gain per segment shrank on this scale too: 31 Elo over the first 100 iterations, 18 over the next 202, 11 over the next 104, 2 over the last 108. Segment 5 is labelled as having failed to improve the network (the user, 11-17; ADR-0123's addendum of that date). Crashes were 3 to 17 games per pair.

## 2. The search-ranking gate

**Question.** At windows where the search did not act, do the search's option values rank the options better than chance against rollout truth? At windows where it acted, how much better?

**Why it matters.** The loop searches about 19,000 windows per iteration and teaches the policy from the roughly 1,400 that clear the bar. The soft-target arm would teach from all of them. If the values at the un-acted windows carry no ranking signal, that arm teaches noise, and ADR-0111's offline re-warm lost up to 47pp doing something close to that. The gate decides whether the arm is run.

**The closest prior read** is ADR-0106's priority-slot calibration ([read](../../data/runs/build3-priocal/read.md)). It used a Build 3 checkpoint's head on heuristic-played games, with K=4 end rollouts as truth, over 814 windows. The `next`-leaf values ranked options at Spearman 0.438 ± 0.028 against the end rollouts, 0.462 ± 0.027 against salted ones. Acting on a 0.10 margin converted at +0.035 ± 0.024 over 78 windows. It did not split acted from un-acted windows, and neither the head nor the states are the big run's.

**Step 0, no box time.** Re-read the calibration's stored rows split at the 0.10 margin. It costs an hour at the desk and says whether the split is visible at all on the old head. Its data is on disk at `data/runs/build3-priocal` and `data/runs/build3-priocal-salt`.

**Step 1, the live read.** `iter-405` plays the recipe of record's games with the search's partial-expansion slot turned to an end leaf on every searched window:

- the recipe's own search flags (`next` leaf, 2 rolls, bar 0.10, temperature 0.025), so the shallow values are exactly what the loop would have recorded;
- `-searchdeep 3 -searchdeepleaf end -searchdeeprolls 4 -searchdeepfloor 1.0`, with `-searchdeeplo` set to the bar so the floor alone selects windows;
- each searched window then carries the shallow values for every option and K=4 end-of-game outcomes for the natural pick plus the top three options.

**The statistic.** Per window, the Spearman correlation between the shallow value and the end-rollout mean over the deep set (up to four options), averaged over windows, with a bootstrap over games. Reported for un-acted windows (shallow margin under 0.10) and acted windows separately. Also reported: the truth's own split-half ceiling (2 rolls against 2), and top-1 agreement.

**Sizing.** In `big-run-i405`, 240 games gave 6,376 searched windows, of which 386 acted: about 26 windows and 1.6 acted windows per game. At 110 games that is about 2,900 un-acted and 175 acted windows (*estimate*). Scaling the prior read's error, the un-acted Spearman would carry about ± 0.015 and the acted one about ± 0.06.

**Cost.** Four options × four rolls × about 19 worker-seconds per rollout is about 300 worker-seconds per window, so 110 games is about 10 box-hours at 24 workers (*estimate*). No model-served price for per-option end copies is on file. A 4-game smoke prices it before the launch.

**Three things to check at the smoke.**

- **What the mainline does when the deep round runs.** The flag's comment says the option stage decides on the deep values. If so, these games act on end-leaf values and are not the recipe's games, though each window is still a state the model reached. The split uses the recorded `shallow_margin`, so the statistic is unaffected. If a record-only deep round is wanted instead, that is a fork change with its forkcheck.
- **That the floor at 1.0 covers acted windows.** The deep round is documented as running in a margin band plus a floor draw on every other window.
- **The deep set is the top three, not all options.** The ranking is over at most four options per window. Windows with two options contribute little.

**The bar (the user agreed 11-16 to skip the soft-target arm if the read is not promising; the numbers are the draft's). Withdrawn 11-17 for the slope bar under the step 0 result below.** The soft-target arm is not run if the un-acted Spearman is under 0.15, which is about a third of the prior read's all-window figure. Between 0.15 and 0.30 the arm runs with a note that its dose is the risk. At 0.30 or more it runs without the note. The acted figure carries no bar; it is the reference.

**What the gate does not show.** Ranking is not teaching. A positive read says the targets carry signal; only the arm says whether the policy can use it (ADR-0100's rule: a ceiling is not learnability).

**To pin.** The bar and its bands. K=4 or K=8 for the truth (K=8 doubles the cost). Whether step 0 runs first and can cancel step 1.

### Step 0 result (2026-11-17): the per-window Spearman is not a usable statistic, and the prior figure was an artifact

`scripts/search_rank_split.py` on the stored rows; outputs in `data/runs/search-rank-gate/step0-*.txt`.

- **ADR-0106's 0.438 is a tie artifact.** Its Spearman ranks tied values by their position in the option list. End-rollout means at K=4 are flat across the options in 57% of windows, and tied in most others, so both sides were ranked by position and read as agreeing. With ties averaged, the same rows give 0.052 ± 0.052 over the 206 windows where a rank correlation is defined. The script reproduces 0.4378 with the old ranking, so the difference is the tie rule alone.
- **The truth cannot rank itself at K=4.** Its split-half ceiling (two rolls against two) is 0.09 ± 0.08. A perfect ranker would fail a bar of 0.15. The Spearman bar above is withdrawn.
- **The replacement statistic is a pooled slope.** Centre the shallow means and the end means within each window, then regress one on the other over all windows. The slope is the share of a shallow value difference that the outcome realizes. Rollout noise widens its error and does not bias it.
- **On the old head it does not separate the two groups.** Slope at acted windows 0.24 ± 0.11 (81 windows); at un-acted windows 0.10 ± 0.07 (737 windows), and 0.21 ± 0.07 against the salted truth. The values carry some signal away from the bar, at a third to a half of face value. The read is too small to say more, and it is Build 3's head on heuristic games.
- **The top-pick gain agrees with ADR-0106.** Where the search would act, its pick beats the natural one by +0.061 ± 0.030 in end outcome; elsewhere by +0.004 ± 0.005.

**Step 1 is unchanged as a data collection.** The same flags and the same games serve the slope. At about 2,900 un-acted windows its error would be about ± 0.035 (*estimate*, scaled from step 0).

**The bar, on the slope (pinned by the user 11-17, before any live row was read).** The soft-target arm is not run if the un-acted slope is within two standard errors of zero. It runs with a note on its dose if the slope is under 0.10. Otherwise it runs. The acted slope is the reference beside it.

### The pricing smoke (2026-11-17, `rank-gate-smoke`) and the live read's launch

- **Price.** Four games took 3.1 game-hours and gave 114 searched windows, 107 of them with a deep round: about 100 game-seconds per window on an unloaded box, a third of the estimate above. One game ran 2.5 hours (43 turns); the other three ran 10 to 17 minutes. The read's wall time is set by its longest games.
- **The three checks.** The floor at 1.0 ran the deep round on every window with two or more valued options, the 14 over the bar included. The natural pick was in every deep set, which held two to four options. The recorded shallow margin equals the margin of the plain option values in all 114 rows.
- **Record-only, a departure from the draft.** `-searchdeepbar 9` keeps the deep round from acting; otherwise the games would act on four-rollout end values. No window acted in the smoke. The states are therefore the network's own play, not the search-acted games' states.
- **Two more departures, from the harness.** `final_read.py` serves greedy and plays every game against the heuristic; the loop samples and plays half mirrors. The allocation threshold is `iter-405`'s own fit, 0.01855.
- **The live read** (`rank-gate`, launched 11-17 16:40): 160 games, 80 per seat on 80 pairings, seed base 20261119, 24 workers and 2 servers, `forge-tgtmask3.jar`. Read with `scripts/search_rank_split.py --live`. About 4,500 windows (*estimate*).

### Result (closed 2026-11-18): the soft-target arm runs, with no dose note

`rank-gate` exited 0 at 07:10 on 11-18 after 14.6 hours. Output: `data/runs/search-rank-gate/live/split.{json,txt}`. The slope is of four-rollout end means on shallow means, centred per window; errors are a bootstrap over games.

| Group | Windows | Slope | Top-pick gain over the natural pick |
|---|---|---|---|
| un-acted (shallow margin under 0.10) | 2,264 | **+0.351 ± 0.073** | +0.005 ± 0.004 |
| un-acted, margin 0 | 1,077 | +0.364 ± 0.090 | −0.001 ± 0.001 |
| un-acted, margin 0 to the bar | 1,187 | +0.314 ± 0.135 | +0.010 ± 0.007 |
| acted (margin 0.10 or more; the reference) | 163 | −0.061 ± 0.110 | −0.017 ± 0.018 |
| all | 2,427 | +0.225 ± 0.066 | +0.003 ± 0.004 |

- **Against the pinned bar.** The un-acted slope is 4.8 standard errors from zero and over 0.10. The soft-target arm runs and carries no dose note. The two seat arms agree: 0.359 ± 0.091 and 0.344 ± 0.109.
- **What the slope says.** Where the search does not act, about a third of a shallow value difference between two options shows up in the end outcome. The shallow values order the options the search leaves alone; that is the information soft targets would train on.
- **Flagged, exploratory: the acted windows show no slope.** At the windows the search would act on, the shallow preference is not realized (−0.06 ± 0.11), and the option it would switch to does no better than the natural pick. The 09-15 rows read 0.24 ± 0.11 and +0.061 ± 0.030 at such windows. The two seat arms agree (−0.09 and −0.04) and the figure holds without the five heaviest games (−0.11). The gap to the old rows is 1.9 standard errors, so this is a flag and not a finding. Two things could produce it without the search being wrong: a margin over the bar selects windows where the two-rollout shallow values are noisiest, which pulls a slope toward zero; and these are record-only states from greedy play against the heuristic. It bears on M13's search-off arm and is routed to the scoping.
- **Power came in under the plan.** 159 games and 2,427 usable windows against an estimate of 4,500. Rows per game were about 18. The truth is flat in 51% of windows, as in the old rows.
- **Run notes.** One game was skipped after exhausting a 2 GB heap twice (seat 0, game 43; `skips.json`). One game ran 8.0 hours and held the first arm's other 23 slots idle for about four of them. The games read 0.579 ± 0.039 against the heuristic, which is not a strength read: the sample is 159 games.

## 3. The search's wall cost on the current recipe

**Question.** How many games per box-hour does generation produce with the search off, against the recipe of record?

**Why it matters.** It sets the search-off arm's size at equal box time. The only figure on file is Build 2's 2.1× wall per game, from a different search shape and a different jar.

**Design.** Two short generation cells from `iter-405` on a quiet box, same seeds, same fleet (24 workers, 2 servers, sampled serving): the recipe of record's search flags, and no search flags. About 240 games each. Read games per hour, game-hours per game, and forward calls per game from the stores' own telemetry. Nothing is trained and nothing is promoted.

**Cost.** About 2 box-hours (*estimate*: one generation phase of the big run took about 70 minutes for 480 games with search). It is a calibrated timing: nothing else runs on the box, ComfyUI unloaded.

**Also read from the same cells, at no cost.** The training step's share of an iteration is already on file (422 s of about 4,600 s). With the search-off games-per-hour beside it, the two numbers size the "more learning per game" arm as well.

**To pin.** Nothing but the go; this one has no judgement in it.

## 4. The cost of a precon game, two-player and four-player (measured 2026-11-17)

**A four-player precon game costs about 13 times a two-player one on the stock heuristic, and Flat Monte Carlo at the desktop setting multiplies either by 4 to 12.** This is the cost side of the benchmark's two tracks (ADR-0126, the benchmark addendum). Every seat is the stock AI; no model, no bridge, no GPU.

**Instrument.** [`scripts/precon_cost.py`](../../scripts/precon_cost.py) on the jar in `../forge-upstream` (upstream as of 11-10 plus the decision-log PR), Forge's own `sim` mode, pods drawn at random from the 184 precons under `res/quest/commanderprecons`, seed 20261117. A two-player cell plays the first two decks of each four-player pod. Six JVMs at once on an otherwise idle box. Times exclude each JVM's first game; counts are over all games. Reports: `data/runs/precon-cost/<cell>/report.json`.

| | 2 players, plain | 4 players, plain | 2 players, Monte Carlo max | 4 players, Monte Carlo max |
|---|---|---|---|---|
| Games | 120 | 120 | 24 | 24 |
| Seconds per game, mean | 2.9 | 37.9 | 35.8 | 131 |
| Seconds per game, median | 1.9 | 17.6 | 24.3 | 141 |
| Seconds per game, 90th percentile | 4.2 | 60.6 | 37.6 | 173 |
| Longest game, seconds | 18.5 | 609 | 204 | 227 |
| Player-turns per game, median | 20 | 48.5 | 17 | 46 |
| Plays put on the stack, median | 46.5 | 158 | 38.5 | 171 |
| Seconds per player-turn, median | 0.10 | 0.35 | 1.29 | 2.65 |
| Draws | 0 | 1 | 0 | 0 |
| AI decision timeouts | 0 | 14 | 0 | 4 |

The Monte Carlo mode's own statistics, summed over each cell:

| | 2 players | 4 players |
|---|---|---|
| Decisions it took up | 1,129 | 3,613 |
| Rollouts per decision | 7.95 | 5.46 |
| Rollouts that failed | 98 of 8,977 | 4,939 of 19,718 |
| Decisions left to the heuristic because the play could not be simulated | 28 | 1,189 |
| Decisions where it overrode the heuristic | 355 | 786 |
| 95th-percentile decision time per pod, ms | 1,440 to 2,147 | 1,553 to 2,458 |

What the cells say:

- **The four-player game is 2.4 times longer in turns and 3.2 times larger in plays.** The rest of the plain cost is per turn: each turn takes about 3.5 times as long.
- **The plain four-player tail is heavy.** The mean is twice the median, one game ran ten minutes, and the stock AI hit its own decision timeout 14 times.
- **Monte Carlo at the desktop setting costs about 1.3 s per player-turn in two-player and 2.7 s in four-player.** That is 12 times the plain two-player game and about 4 times the plain four-player game by the mean.
- **The mode is half-working in four-player.** A quarter of its rollouts failed there, mostly in the game copier ("Couldn't map" a card), and a third of its decisions fell back to the heuristic as unsimulatable. In two-player 1% failed. A four-player Monte Carlo opponent on this jar is weaker than its setting says, and our own search copies games through the same copier.
- **The 95th-percentile decision ran past the 1,500 ms budget in every pod.** Six JVMs on 32 cores is a light load, so the clock binds even on a quiet box.

What they do not say: anything about a model-served seat. The 27 s median game of the recipe of record is a different measurement (model-served, the Duel Commander pool, the bridge in the loop). The small Monte Carlo cells (24 games) carry wide errors on every figure.

### The copier check (2026-11-18): the four-player rollout failures are not fixed on upstream master

The same eight four-player pods, three games each, Flat Monte Carlo at the desktop setting in every seat, on a jar built from the patch branch (`d0e50c61c7`, upstream master of 11-17 plus the count budget, the budget left off). Outputs: `data/runs/precon-cost/p4-max-patch/`; both jars are kept in `data/runs/precon-cost/jars/`.

| Jar | Rollouts | Failed | Decisions that fell back as unsimulatable |
|---|---|---|---|
| upstream 11-10 | 19,718 | 4,939 (25.0%) | 1,189 of 3,613 (32.9%) |
| patch branch (master 11-17) | 18,731 | 2,862 (15.3%) | 711 of 3,349 (21.2%) |

- **A deck effect it is not.** The decks and seeds are the same and the failures persist, on fewer distinct cards (11 against 20). Upstream's fixes of the week reduced them by about four tenths. The two cells are not the same games: the mode's budget is a wall clock, so play diverges.
- **Where it fails.** The unmapped objects are commanders and the Monarch's effect card, and the trace runs through `Player.copyCommandersToSnapshot` in the copier's player step. The cause is not identified. One untested guess is a player who has left the game, which would explain why two-player games fail at 1%.
- **What it means for us.** Our search copies through the same class. The first forty two-player search games of `rank-gate` printed the copier's "Couldn't map" line 8 times, so the two-player track is not affected. The four-player track is, on any jar up to 11-17 master, for upstream's Monte Carlo opponent and for our own search alike.
- **Routed to the M13 scoping (four-player):** find the cause on the merged engine before any four-player search or Monte Carlo read; it is a candidate upstream fix.

## Order

1. Step 0 of the gate (desk).
2. The ladder, overnight.
3. The gate's 4-game smoke, then its read, overnight.
4. The wall cost, on a quiet box, when nothing else is queued.

The ladder and the gate both use the full fleet, so they run one after the other, not side by side.
