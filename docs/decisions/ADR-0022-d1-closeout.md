# ADR-0022: M3 D1 closeout — the veto cause is resolved; feature + penalty were one deliverable

- **Date:** 2026-07-19
- **Status:** accepted (closes M3 D1; resolves done-when #1)
- **Design-doc anchor:** §3d (reward), §6 (RL); ADR-0019 (veto-drift levers), ADR-0021 (M3 opening), d6-vtrace-loop §6c (the reward-shaping pin)

## Context

M3 D1 opened on the iter-013 forensics hypothesis: the observation lacked
commander tax, so RL walked into unpayable recasts. The work resolved into
four pieces, one of which was a mid-deliverable reframe:

1. **The "observation gap" was a featurization gap** — `cmdcast` had been
   in every dec record since M1 D1; transform v4 (`cmd_tax` on
   command-zone commander rows, `load_compat` zero-pad) exposed it with no
   fork change and no corpus regeneration (Anvil `5ae9a48`).
2. **First-attempt veto rate** (chain-independent basis) landed in census/
   monitor/arms; retroactive re-reads showed run-3's drift was real on this
   basis too. Baselines: D5 BC 0.1358 argmax (the done-when bar), iter-012
   0.2423 (Anvil `b9a10f3`).
3. **The controlled test (d6-run4, feature-only) falsified feature-alone**:
   ten iterations with the tax fully visible, drift 0.242 → 0.403 argmax,
   commander unpayables still growing. Mechanism identified: under re-ask,
   every attempt in a chain shares the window outcome, so there is **no
   advantage differential** for a zero-init feature to train from.
4. **The reframe:** the §3d veto penalty — filed as a D2 *reserve* lever in
   the plan — is not a fallback but the missing training signal. Feature
   and penalty are one deliverable pair (the feature supplies the *how*,
   the penalty the *why*). Pinned as d6-vtrace-loop §6c (user sign-off:
   vetoed casts + combat drops, λ = 0.02), implemented with reader-side
   derivation gated by census reconciliation (priority exact: 9,007 =
   9,007; combat diagnostic with all corner classes attributed — en route
   discovering the silent MinMaxBlocker illegal-block-discard class).

d6-run5 (feature + penalty, guard-kl 0.06 after a transition-KL halt at
0.05069) ran the full 20-iteration schedule — the project's first completed
schedule — and provides the closeout evidence.

## Decision: D1 is CLOSED — done-when #1 SATISFIED on both clauses

**Quantitative clause** (first-attempt veto ≤ D5 baseline, non-increasing):
sampled first-attempt veto fell 0.340 → ~0.10 within five iterations and
held; every argmax arms read (0.0806 / 0.0905 / 0.0966 / 0.0832) and the
2,000-game read (0.0987) sit **below the 0.1358 bar**. casts/game held at
baseline throughout (~51 vs floor 43) — veto reduction was not bought with
passivity. The penalty self-extinguished (rej 20.8 → ~8/trajectory).

**Forensic clause** (post-first-cast commander vetoes collapse on fresh RL
games): on the paired 2,000-game read (identical seeds/protocol vs
iter-012's record), **post-first-cast commander vetoes fell 1.567 →
0.438/game (−72%, 3.6×)**; pre-first-cast fell 0.657 → 0.258 (−61%). The
residual post/pre mix (63/37) tracks opportunity (post-cast windows
dominate late-game), not class-specific blindness — the two classes now
shrink and behave alike, which is what "cause resolved" looks like at the
mana edge.

## Consequences

- **The veto front closes as a structural leak.** The §6c penalty stays in
  permanently as a self-extinguishing constraint (per the standing
  keep-vs-anneal analysis: removing it restores the indifference the drift
  grows from; a Lagrangian λ is the documented upgrade if the equilibrium
  ever lands wrong).
- **Strength was untouched in both directions**: the 2,000-game corrected
  read on run-5's best checkpoint (iter-9) is a dead tie with iter-012
  (0.5171 ± 0.0110 vs 0.5213 ± 0.0110; paired −0.30pp ± 1.12, t=−0.27).
  The drift was wasted intent that re-ask was already absorbing — the D3
  lesson's RL-era echo, and priced honestly here.
- **Done-when #2 stays open and inherits the first ceiling datum**: paired
  arms declined late-run (0.540 → 0.475) and the flat 2,000-game read says
  this recipe (lr 2e-5, 480 games/iter, masked critic, terminal±penalty
  reward) does not push past iter-012. D2's scaling conversation starts
  from "a different lever, not more of the same": candidates = iteration/
  batch scale at lower lr, full-vis critic in the loop, rollout-labeled
  targets under micro-batching.
- `d6-run5/iter-009/train/last.pt` = run-5's checkpoint of interest
  (records: `data/runs/run5-best-arms-report.json`, run5-bestarm-* dirs,
  `data/training/d6-run5/`). The RL checkpoint of record REMAINS
  `d6-run3/iter-012/train/last.pt` (strength tie ⇒ no supersession; the
  veto-clean chain becomes the natural init for D2 runs).
- Watch items carried: run-5's late-run strength decline (unexplained —
  candidate causes: cumulative drift under a calibrated-critic regime,
  entropy glide 0.21→0.13); the elevated-but-attributed combat-declaration
  fallback counts; the two torn-frame crash games per ~500 (known class).
