# The three measurements before the M13 scoping — design draft

**Doc status:** living · draft designs for the ladder of own checkpoints, the search-ranking gate and the search's wall cost ([ADR-0126](../decisions/ADR-0126-m12-closeout.md) decision 3); the ladder is pinned and launched; the gate and the wall cost are not launched

Drafted 2026-11-16. The numbers marked *estimate* are arithmetic on measured prices, not measurements. Each design ends with what the user has to pin before launch.

## Summary

| Measurement | What it decides | Box time | Fork work |
|---|---|---|---|
| The ladder | M13's scoreboard; whether `iter-513` and `iter-405` separate head to head | about 11 h (*estimate*) | none |
| The search-ranking gate | whether the soft-target arm is run at all | about 10 h (*estimate*), after a 4-game pricing smoke | none expected |
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

**The bar (the user agreed 11-16 to skip the soft-target arm if the read is not promising; the numbers are the draft's).** The soft-target arm is not run if the un-acted Spearman is under 0.15, which is about a third of the prior read's all-window figure. Between 0.15 and 0.30 the arm runs with a note that its dose is the risk. At 0.30 or more it runs without the note. The acted figure carries no bar; it is the reference.

**What the gate does not show.** Ranking is not teaching. A positive read says the targets carry signal; only the arm says whether the policy can use it (ADR-0100's rule: a ceiling is not learnability).

**To pin.** The bar and its bands. K=4 or K=8 for the truth (K=8 doubles the cost). Whether step 0 runs first and can cancel step 1.

## 3. The search's wall cost on the current recipe

**Question.** How many games per box-hour does generation produce with the search off, against the recipe of record?

**Why it matters.** It sets the search-off arm's size at equal box time. The only figure on file is Build 2's 2.1× wall per game, from a different search shape and a different jar.

**Design.** Two short generation cells from `iter-405` on a quiet box, same seeds, same fleet (24 workers, 2 servers, sampled serving): the recipe of record's search flags, and no search flags. About 240 games each. Read games per hour, game-hours per game, and forward calls per game from the stores' own telemetry. Nothing is trained and nothing is promoted.

**Cost.** About 2 box-hours (*estimate*: one generation phase of the big run took about 70 minutes for 480 games with search). It is a calibrated timing: nothing else runs on the box, ComfyUI unloaded.

**Also read from the same cells, at no cost.** The training step's share of an iteration is already on file (422 s of about 4,600 s). With the search-off games-per-hour beside it, the two numbers size the "more learning per game" arm as well.

**To pin.** Nothing but the go; this one has no judgement in it.

## Order

1. Step 0 of the gate (desk).
2. The ladder, overnight.
3. The gate's 4-game smoke, then its read, overnight.
4. The wall cost, on a quiet box, when nothing else is queued.

The ladder and the gate both use the full fleet, so they run one after the other, not side by side.
