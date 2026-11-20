# ADR-0135: M13 Build 3 — the three arms' launch settings, the pre-registered reads, and the soft-target term

- **Date:** 2026-11-20
- **Status:** accepted (sections 1 to 5); section 6, the soft-target definition and its dose ladder, is proposed and waits on the user
- **Design-doc anchor:** [m13-plan.md](../design/m13-plan.md), Build 3 and pins 1, 2, 7 and 8; anvil-design-v2 §3e (search as the behavior policy), §6 (the loop); [ADR-0127](ADR-0127-m13-charter.md); [ADR-0134](ADR-0134-m13-build2-one-queue.md)

## Context

The plan pins what the three arms are, their length, their game count and their bar. It leaves the launch settings to this build: the flag strings, the seeds and ports, how the reads are run, and what the soft-target arm trains on. Two of the arms needed nothing built. The soft-target arm needed a training term that did not exist.

## Decision

### 1. One script holds the three arms

**`scripts/m13_arms.sh <arm> <hours>` is the arms' one definition.** It runs one self-play loop from `big-run/iter-405` on the pinned jar (`data/runs/m13-build2/forge-b2-mcguard.jar`, fork `68168fb214`) and stops it by the loop's wall budget. The arm and its hours are arguments, so `anvil.runs relaunch` repeats them.

**The arms differ in one block of that script and nowhere else.**

| Arm | Loop name | The block | Seed base | Port |
|---|---|---|---|---|
| Control | `m13-control` | `--search-recipe "$RECIPE" --search-alloc head --search-floor 0.1 --arms-lookahead on` | 20261201 | 50140 |
| Search off | `m13-nosearch` | empty: no recipe, so no `-search` on the workers, no search-row terms in the trainer, no with-lookahead read | 20261202 | 50144 |
| Soft targets | `m13-soft` | the control's block plus `--soft-frac <dose> --soft-temp <T> --soft-carry-w` | 20261203 | 50148 |

**Every other flag is the big run's segment-5 string** (`scripts/big_run_chain.sh`): 480 games per iteration, half against heuristic seats, 24 workers on 2 servers, the ADR-0119 rung-2 value recipe, the anchor at weight 0.1 drawn every 32 steps with its pause line at a gap of 0.15, the Spearman floor at 0.30, the run-distribution bank read with no floor.

### 2. What departs from the big run's string, in every arm

- **`--mc-frac 0.1`** (pin 7) and the one-queue generation (ADR-0134).
- **`--server-args "--abilities data/embeddings/abil-cf2ca6ba-m13-qwen3"`**, the merged jar's ability table.
- **`--rl-workers 12`**, where the big run ran 4. It changes the loader's parallelism and the interleave of one seeded schedule, not the recipe. The script halves it and reruns if the memory watchdog trips.
- **`--train-mem-floor-gb 24`**, where the big run had 40. The learner now peaks near 21 GB (ADR-0134, section 4), and a 40 GB floor would hold the step whenever the desktop is in use.
- **The distillation and allocation weights are calibrated at each arm's own first iteration and carried from there.** The big run carried weights calibrated at its iteration 0, and its policy-gradient magnitude had since fallen 18%. A fresh loop restores the shares the recipe names (0.05 and 0.02).
- **Each arm starts with an empty replay window.** It fills over the first four iterations, the same in every arm.

### 3. Order, and what shares the box

**The arms run one at a time, in the plan's order: control, search off, soft targets.** Equal box time is each loop's accumulated wall under `--wall-hours 168`. A second calibrated job beside an arm would tax that arm alone, so none runs. Reads that belong to no arm (the head-to-head reads, the dose ladder) run between arms.

**The control's first step is a day-zero read on the in-loop instrument:** `iter-405` on the in-loop read's seed base and pairs, 200 games per seat, network alone. It runs before the loop and is outside the wall budget. The "control falls" kill condition is read against it.

### 4. The pre-registered reads

**The verdict is the plan's and is not changed here.** Each arm's final checkpoint plays the control's final checkpoint head to head, network alone, decoder masked, on the pinned jar:

- `scripts/h2h_read.py --games 2500` (5,000 games over the two seat assignments), 24 workers, 2 servers, launched with `--quiet-box`.
- Seed bases: 20261211 for search off against the control, 20261212 for soft targets against the control. Neither has been used.
- **The bar is 2 standard errors, 1.1pp.** An arm inside the band is reported as level, with the power statement beside it.

**The continuity number** is each final checkpoint against the plain heuristic on the 11-07 confirm's seeds, 5,000 games, so it pairs game for game with day-zero's 0.6064 ± 0.0069.

**The in-loop reads** (every 5 iterations, 200 games per seat on fixed seeds) are trend instruments. A fixed-subset read is one observation. They feed two rules only: the "control falls" kill condition, and pin 1's watch on the search-off arm for an early, clear separation.

**"Control falls," made operational.** At the in-loop read nearest 84 hours of loop wall, the control's network-alone winrate is more than 2 standard errors below the day-zero read on the same seeds. The difference is paired game for game if the two reads' seeds match, which is checked at the first in-loop read; otherwise it is unpaired, and 2 standard errors is about 7pp.

### 5. The power statement

- **The read resolves 0.55pp** at 5,000 games head to head.
- **A week moved about 1.5pp** at the big run's slope, and the big run's last segment moved nothing (0.5019 ± 0.0055 between `iter-405` and `iter-513`). The control is expected to move little.
- **Games each arm produces** (*estimates*): the control about 110 to 120 iterations, 55,000 games, at the big run's 4,580 s of generation and 442 s of training per iteration, less the queue's saving and the learner's faster load, plus the Monte Carlo share. The search-off arm about 3.5 times that.
- **What the design cannot separate:** the search-off arm's result from its extra updates (pin 8; the equal-updates arm follows if it wins), and an arm's effect from one seed of training. Each arm is one run.

### 6. The soft-target term (built; its definition and dose are proposed)

**What is built.** `rl.py --soft-frac` adds one loss term, off by default. With it off the loader builds nothing and the learner's replay of a stored iteration matches the earlier run to GPU noise.

- **Which windows.** A searched priority window where the natural line was played, the acting rule did not fire, and the search's margin is under the bar. This is the population of the gate's un-acted slope (+0.351 ± 0.073). It needs two or more options with a value; voided and skipped options are left out.
- **The target.** The policy's own distribution over the valued options, detached, tilted by the search's values: t ∝ π · exp(q / T). The loss is KL(t ‖ π), capped at 2 nats per window.
- **Why a tilt and not a softmax of the values.** A softmax of the values was built first. On a stored iteration its KL sat at the cap (2.9 per trajectory against the tilt's 0.05). Most of it was a sharp policy being pulled toward uniform on options the search values alike. An auxiliary target's shape is a behavioral prior (ADR-0076), and that one says "be less sure". The tilt leaves the policy alone where the values are equal and moves it only along the search's ranking.
- **The weight** is set as a share of policy-gradient mass, calibrated at the arm's first iteration and carried, with a share guard at three times the target. This is the distillation term's mechanism.
- **Its first numbers,** from a learner replay of a 96-game iteration under `iter-405` at a 0.05 share: about 17 soft windows per trajectory against less than 1 acted window; trunk gradient norm 0.05 against the policy gradient's 0.32.

**Proposed, for the user:**

- **Temperature 0.1,** the acting bar: one bar of value difference is one nat of tilt. The gate's slope says about a third of a shallow difference is realized, so the tilt overstates the evidence threefold at this setting and the weight is what prices it.
- **The dose ladder** (the plan: "its target weight is pinned from a short dose ladder before the arm launches"). Three shares, 0.02, 0.05 and 0.15, each a 24-hour loop from `iter-405` on the arm's own settings, read network alone against the heuristic at 2,000 games on one seed set, with the control's checkpoint at the same wall hour as the reference. The arm takes the highest dose that is not below the reference by 2 standard errors. If every dose is, the plan's kill condition applies and the arm is not run. It costs about three box-days and runs after the search-off arm.

### 7. The smokes

**Each arm's loop ran two iterations of 96 games from `iter-405` on the arm script,** with the Monte Carlo share and an in-loop read every iteration (`m13s-nosearch`, `m13s-soft`; the control's path is the soft arm's with the term off, and Build 2's `b2loop` ran it).

- **Soft targets: complete, no battery anomaly, no guard.** The loader joined about 16 soft windows per trajectory (`soft_n` 16.2, `soft_raw` 0.040). The search join matched 3,130 of 3,130 rows. A 96-game iteration has fewer optimizer steps than the 50-step calibration, so the smoke never applied the term; section 6's replay, calibrated over 10 steps, is the evidence that it applies.
- **Search off: iteration 0 complete, halted at iteration 1 by the veto guard.** 124 vetoes against iteration 0's 76 (a rate of 0.029 against 0.018; the line is 1.5 times). Generation took 250 s and training 88 s. This is open item 4.
- **The leak guards found nothing:** 0 of 7,767 comparisons across both smokes.
- **Generation servers log "nothing to decide" on the target and order surfaces.** 93 and 33 asks in the search-off smoke's two iterations, 66 and 22 in the soft smoke's, 12 and 26 in `b2loop`. Each falls back to the heuristic. None appears in a read's servers or on the old jar. It is open item 5.

## Consequences

- **Build 3's first arm launches on these settings.** The search-off arm follows at the control's wall stop, on the same script.
- **Open for the user, none of which blocks the control** (item 4 is wanted before the search-off arm, item 1 before the ladder):
  1. Section 6's definition, temperature and ladder.
  2. **The search-off arm and the anchor's pause line.** The anchor draws once per 32 optimizer steps, so an arm with 3.5 times the steps draws 3.5 times the bank in a week. `iter-405` starts at a train-minus-holdout gap of 0.096, the big run's fifth segment took it to 0.119, and the pause line is 0.15. The arm will probably pause on it. A pause spends no box time; it needs a relaunch. The alternative is `--anchor-every 112` for that arm, which holds the bank's draws per box-hour equal and changes the value recipe per step. The recommendation is to leave 32 and take the pauses: the arm is already pinned as "no search, more updates", and the anchor per step is part of an update.
  3. **Build 4 beside the arms.** Its desk work is free. Its box jobs (the truth stream's rollouts, a critic's training) would tax whichever arm is running. The recommendation is to run them between arms.
  4. **The veto guard on the search-off arm.** With no search a 96-game iteration has about 100 vetoes, a fifth of the searched arms' count, and they cluster by game. The smoke's 1.6-fold step between two iterations is probably that noise; at 480 games the count is five times larger and the line may still be met by chance over 400 iterations. A false halt costs a relaunch and no box time. The recommendation is `--guard-veto-mult 2.5` for that arm alone, decided before it launches; the guard is not part of the recipe.
  5. **The "nothing to decide" asks.** They are about 0.2% of a generation server's asks and the same in every arm, so they do not bias the comparison. They are not attributed: no played game's census records a fallback, which points at game copies (the Monte Carlo opponent's or the sampled seats'). The recommendation is to attribute them on the control's first iteration's logs, at the desk, and route a fix to the next boundary.
- **No standing rule is born.** The tilt's reason is ADR-0076's rule applied.
- **Routed:** the quickstart gains the soft-target flags when the arm's dose is pinned; until then the term is this ADR's.
