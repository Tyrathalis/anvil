# ADR-0118: The value head drifts off rollout truth under the loop — the state-ranking audit wired, a value anchor as the settings pass's first arm

- **Date:** 2026-09-23
- **Status:** accepted
- **Design-doc anchor:** §4 (value head), §6 (training pipeline), the fourth design invariant ("the value function is continuously audited against rollouts"); m12-plan Build order 4½ / 5

## Context

ADR-0115 item 3(c) named the state-ranking Spearman as each shakedown arm's third closing number
"where a checkpoint-eval path exists (else routed to the big run's mid-run health)", and routed the
path by name for when the first arm closed. The recipe arm closed 09-23 04:30. The path was built
today as `anvil.training.value_pretrain eval`: the checkpoint's value head scores the frozen 1,197-row
holdout of the state benchmark (`labelset-c2-v3`, K=8 rollout winrate at pre-action states — ADR-0103's
cell, reference 0.27–0.48, the Build 1 build 0.392), CPU by default so an eval beside a running fleet
never trips the GPU yield and eats an arm's box time; the bank's iter-019-era examples are widened to a
Build 4 net's globals with the vocab's own format scalars. Validation: the two Build 1 checkpoints on
record reproduce (0.3921 vs 0.3919; 0.374 vs 0.375). About 25 s per checkpoint.

**The read** (`data/runs/shakedown/state_ranking.jsonl`; bootstrap SE ≈ 0.025–0.030 per row):

| checkpoint | state-ranking ρ |
|---|---|
| `iter-019` (the era reference; the RL critic in the trunk) | 0.335 |
| the day-zero build `m12-build4-e1a-tgt` (the Build 1 head, untouched since) | 0.374 |
| recipe iter 0 / 1 / 2 | 0.321 / 0.343 / 0.344 |
| recipe iter 4 / 9 / 12 / 15 (the arm's final) | 0.275 / 0.302 / 0.299 / **0.256** |
| alloc iter 0 / 4 / 8 | 0.333 / 0.275 / **0.256** |

The head's ranking of states against rollout truth falls from the first training cycle and keeps
falling — ≈ 0.12, about four SE over the recipe arm's 16 iterations — and the alloc arm reproduces the
shape independently. Over the same iterations the recipe arm's network-alone strength stayed flat
within noise (0.5185 → 0.5240 ± 0.0112) and its mid-run lookahead gap drifted upward (+0.3pp at
iteration 4, +1.8 at 9, +3.3 at 14; each 400 games, ± 2.5pp).

**The mechanism is the loop's configuration, not a bug.** The Build 1 head was fit on K=8 rollout
composites plus the full-vis critic's dense leaf values (ADR-0103). Inside the loop the same head trains
on V-trace targets — terminal outcomes under the current sampled policy, BCE at `--value-weight 0.5`
(`rl.py`, the D6 loop) — with no critic on the shakedown chain and nothing anchoring it to rollout truth.
Under the recipe the head is also the search's leaf, so as it drifts the search's acted labels drift with
it, and the behavior policy's quality is the leaf's. The fourth design invariant names exactly this
audit; it existed as a Build 1 read and was never wired into the loop.

Under the pre-registered rules this is neither the Build 5 kill (with-lookahead climbs while
network-alone stays flat) nor the Build 5 tripline (both curves plateau while the Spearman is flat). It is
a third shape — the Spearman falling from cycle one while strength is flat — and it is the landmine the
shakedown exists to catch (ADR-0115: "the run stays the last landmine catcher").

Also recorded for the alloc arm's read: the allocation head's admission rose from 51% of windows at
day-zero (the b4post read's 51.3%) to 66% at iteration 8 as its per-cycle tau fell 0.369 → ≈ 0.02 under
the trained head (in-loop AUC 0.65–0.76 vs 0.80 at the fit) — the population drift ADR-0113 said to watch;
its searched windows cost 34 copy calls each vs the recipe's 27–29 (the head picks the bigger windows);
per-game wall −14% vs the recipe, so the arm lands ≈ 20 iterations in its 30 h against the recipe's 16.

## Decision

1. **The shakedown's arms run to their verdict as designed.** All four share the drift; the equal-box-time
   comparison stays valid; a mid-flight change would confound the verdict (ADR-0115 item 4 stands).
2. **The state-ranking Spearman becomes a per-iteration read of the loop** — a battery row on every
   iteration's checkpoint and a guard (a drop of more than two bootstrap SE below the day-zero value
   flags the iteration; the driver's anomaly channel, not a halt, until the settings pass calibrates it).
   Built in a worktree; lands with `nan-guard` and `certifier-merge` after the shakedown (the tree rule).
3. **The settings pass on the winning arm opens with a value-anchor arm**: a replay term on the Build 1
   state and leaf banks (`data/runs/m12-build1/bank-state.pt`, `bank-leaf.pt` — rollout composites and the
   full-vis critic's leaf values, already on disk) beside the V-trace value loss, the KL-anchor pattern
   applied to the value head. **Pre-registered bar: the Spearman stays within one bootstrap SE of the
   day-zero 0.374 across the pass's iterations** while the network-alone read is not worse than the
   un-anchored winner's. Freezing the head is the weaker alternative (the trunk under it moves anyway) and
   is the second arm only if the anchor fails. A periodic re-fit on fresh rollouts is routed, not scheduled
   (rollout labels are the expensive part).
4. **The eval merges into main now** (`8099b8d`; the loop does not import `value_pretrain`; the running
   chain script is untouched). Each remaining arm's read gains the Spearman column by hand from the JSONL
   until the battery row lands.

## Consequences

- The big run does not launch with a value head that trains unanchored: the anchor's read is a
  launch condition beside the post-Build-4 +1.5pp (ADR-0104) — the value function is the central asset
  (ADR-0101) and the leaf of the behavior policy; its audit is part of the loop from here.
- Standing rule born → [standing-rules.md](../standing-rules.md) (training-loop design): **a value head
  that trains inside the loop is audited against rollout truth every iteration (the state-ranking
  Spearman on the frozen holdout), and a head that also serves as the search's leaf is anchored to that
  truth — outcome targets alone pull it off it.**
- The Build 5 tripline text gains this third shape by name at the docs pass (the plan's kill list).
- Routed: the anchor's implementation (a `--value-anchor` term in `rl.py` reading the Build 1 banks;
  worktree, after the shakedown); the battery row + guard (`anvil/evals/battery.py`, `selfplay.py`);
  whether the one-ply cell (the cross-fit read, GPU) joins the per-iteration audit (priced first); the
  periodic rollout re-fit (only if the anchor fails).

## Addendum 2026-09-24 — the drift lives in the trunk, not the head's weights (the head-swap read)

**Verdict: swapping the value head's four tensors between day-zero and a drifted checkpoint moves the
Spearman not at all; the trunk's representation under the head is what drifted.** A freeze of the head
would therefore do nothing (the ADR's guess, now measured); the anchor arm stays first because its
replay loss reaches the trunk through the head. Read on CPU beside the running alloc arm (no pause;
the eval is deterministic given the checkpoint), rows in `data/runs/shakedown/state_ranking_headswap.jsonl`.

| trunk from | head from | state-ranking ρ |
|---|---|---|
| day-zero | day-zero | 0.374 |
| alloc iter-016 | alloc iter-016 | 0.213 |
| **alloc iter-016** | **day-zero** | **0.214** |
| **day-zero** | **alloc iter-016** | **0.379** |
| recipe iter-015 | recipe iter-015 | 0.256 |
| recipe iter-015 | day-zero | 0.259 |
| day-zero | recipe iter-015 | 0.377 |

Boot SE ≈ 0.026–0.030. The head did move (relative L2 change 1.8% in both arms, vs 0.4% for the
67M-parameter trunk and 1.7% for the decoders), but its movement is orthogonal to the ranking; the
0.4% trunk change carries the whole loss. Also read: alloc iter-012 / iter-016 = 0.277 / **0.213**,
the lowest in either arm, ≈ five SE below day-zero; the loop's own value loss fell 0.418 → 0.371
over the same iterations (the head fits the V-trace targets better while matching rollout truth worse).

**What this does not tell:** which loss moves the trunk — the value loss at weight 0.5 (the largest
term by magnitude; then the anchor counteracts it directly) or the policy / distill / alloc terms (then
the anchor competes with them and may cost strength, which the arm's pre-registered strength bar
catches). Routed: a per-term trunk gradient-norm row in `rl.py` (worktree, post-run); a `--swap-head`
option on `value_pretrain eval` so this read is one flag, not a scratch script.
