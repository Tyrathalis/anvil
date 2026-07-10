# ADR-0008: M1 D7 gate resolution — §15 high-80s row resolves TRUE; 3-epoch recipe

- **Date:** 2026-07-10
- **Status:** accepted
- **Design-doc anchor:** §15 of anvil-design-v2.md (BC agreement prediction row); m1-bc-plan D7

## Context

D7 is "train to the gate": held-out action agreement excluding
single-legal-option decisions (ADR-0005 timing-legal candidate basis), per-tag,
on the final corpus. §15 predicted high-80s. The epoch sweep (1/2/3 full
epochs over the 113,592-game corpus, from-scratch runs at 258K/516K/774K steps
with matched cosine schedules, merged D4 architecture, pw=0.1, batch 256,
600-batch finals) doubled as the ADR-0006 residual experiment: does repeating
the frozen corpus keep paying, or was diversity the binding constraint?

Pre-launch fix that the sweep depended on: the loader's game shuffle was
seeded once, so epoch 2+ would have replayed epoch 1's order exactly
(`f150afc` reseeds per epoch; verified distinct + deterministic).

## Decision

**The §15 high-80s row resolves TRUE, conservatively.** Final 600-batch evals
(val split, n_honest ≈ 148.9K per run):

| run | steps | honest | raw | nonpass | target | X (n=173) | value BCE | wall |
|-----|-------|--------|-----|---------|--------|-----------|-----------|------|
| d7-ep1 | 258K | 0.9647 | 0.9655 | 0.9043 | 0.9719 | 0.786 | 0.573 | 4.6h |
| d7-ep2 | 516K | 0.9719 | 0.9726 | 0.9229 | 0.9749 | 0.804 | 0.571 | 9.2h |
| d7-ep3 | 774K | **0.9758** | 0.9764 | **0.9339** | 0.9754 | 0.856 | 0.574 | 13.9h |

Honest agreement lands ~8pp above the predicted band at one epoch and ~9pp at
three — and this at pass-weight 0.1, which *sacrifices* honest-metric points
for nonpass coverage. Per-tag (ep3 val): mulligan 0.9969 (n=639), tuck 0.868
(n=250), binary 1.0 (n=39), number 1.0 (n=50), trigger 1.0 (n=4). Tails
reported as tiny-n coverage, not strong claims. Valpair reads +0.0–0.4pp above
val throughout (the standing denominator quirk); zero held-out-matchup gap.

**The standard recipe is 3 epochs.** Each added epoch kept paying outside
noise (nonpass +1.86pp then +1.10pp, SE ~0.33pp) with no val regression on any
head. Returns are halving per epoch; a 4th (~18.5h) is not scheduled — D8
winrate evidence outranks another half-point of agreement.

**ADR-0006 residual resolved: repetition works; diversity was not binding.**
Second and third passes over the *same* frozen corpus bought what doubled
diversity at matched compute could not (the 100K checkpoint's 50K→100K arm
went -0.61pp). The stop decision is retroactively vindicated: more passes are
free, more games cost ~42h per doubling.

**The X head was never corpus-limited — it was compute-limited.** On the
identical 672-window pilot-val basis where the ADR-0006 curve read
0.573/0.637/0.674/0.647 (climb stopped, "headroom = drills/architecture"),
the sweep checkpoints read **0.795/0.839/0.874** — +20pp over the best curve
arm, still climbing at 3 epochs, and the combined-val basis (n=1,518, SE
~1.3pp) agrees to the third digit. The curve arms were all 113K-step trains;
the rare-label heads simply hadn't converged at that depth on any corpus
size. Amends ADR-0006's X interpretation: the §6 drills premise is *not*
"showing up early" — it stands on its own merits, but rung-1 X accuracy was
recoverable with epochs alone.

## Consequences

- **M1 done-when #1 is satisfied** (the honest number exists and beat the
  target). Remaining: D8 (BC agent plays over the bridge, winrate recorded).
- `d7-ep3/last.pt` is the D7 checkpoint of record and the D8 agent, behind
  PASS-logit calibration (`anvil/training/calibrate_pass.py`, offset stored
  beside the checkpoint). Measured: the model under-passes by 1.7pp raw
  (0.8861 vs expert 0.9029 on 149.7K multi windows); offset **δ=+2.169**
  matches the rate and lifts honest to **0.9841** — the D5 premise (pw=0.1's
  honest cost is recoverable post-hoc) confirmed exactly. Nonpass at the
  calibrated point reads 0.8932 by construction (marginal action windows flip
  to pass); both operating points are recorded, D8 play decides between them.
- Value head unchanged (~0.57 BCE) across all recipes, as the diagnosis
  predicted — measured, not data- or recipe-limited. M2 rollout labels remain
  the fix; nothing new to do here.
- §15's calendar risk shifts entirely to D8/M2 machinery (executor, RL); no
  representation-quality reserve is needed.
