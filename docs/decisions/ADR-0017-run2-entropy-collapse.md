# ADR-0017: d6-run2 entropy-bonus collapse — the §4 no-anchor bet resolves false; guards promote to v0

- **Date:** 2026-07-16
- **Status:** accepted
- **Design-doc anchor:** d6-vtrace-loop §4 (losses/anchor), §6 (monitoring); m2-rl-plan D6

## Context

d6-run2 (lr 3e-5 × 16 iterations, re-ask on, init = d6-run1 final) was the
lr/iteration-scaling arm agreed after run-1's verdict (cumulative KL from
init only ~0.05 at lr 1e-5 — "the policy barely moved"). d6-vtrace-loop §4
deliberately shipped v0 without a KL-to-BC anchor: *"KL(π‖μ) and entropy are
monitored, and the anchor is the named contingency if entropy collapses or
KL runs away."*

KL ran away. The run collapsed at iterations 4–5 and was stopped at
iteration 6 of 16 (~9.5 h spent): entropy 0.18→4.40, per-iteration KL(π‖μ)
0.009→4.40, ρ_mean 0.99→0.27, veto rate 23.7%→86.6%, iter-004 arms **0.085 ±
0.014** vs the heuristic. The monitor recorded every stage; nothing acted.

## Diagnosis (evidence in `data/training/d6-run2/`)

1. **Root cause: entropy-bonus runaway under near-zero advantages.** In
   mirror self-play with a calibrated critic, PG advantages average ≈0 — the
   `pg` loss term sat at ±0.002 for the entire run (per-step metrics.jsonl,
   all iterations). The entropy bonus (ent_weight 3e-3) is therefore the only
   persistent gradient on the policy, and lr sets its compounding rate:
   +0.003 entropy/iter at lr 1e-5 (run-1) vs +0.02 → +0.05 → +0.10 → runaway
   at 3e-5. Entropy climbs monotonically *within* iterations (train-time
   driven, not a data shift).
2. **Positive feedback closes the loop:** entropy↑ → KL(π‖μ)↑ → ρ clipped
   toward 0 → V-trace advantages shrink further → even less opposition to
   the bonus. Iteration 4's within-epoch traces show ρ 0.98→0.33 while
   entropy triples.
3. **Head attribution:** the priority *choice* head led (μ-record entropy
   0.081→0.118→0.257→1.14 across iters 0/3/4/5), targets followed; the X
   head — the pre-registered suspect — was high-but-flat (0.82→0.80 through
   iter 4): exonerated. Value head exonerated too: v-loss flat 0.32–0.43
   throughout; the v0 drift (0.51→0.69) is downstream (vs targets revert to
   V under clipped ρ).
4. **Re-ask amplified volume, not cause:** once the policy sprayed, veto
   chains multiplied priority windows — iter 5: 1.06M priority decisions
   (~4× normal) for the same 480 games, 66% of them veto events, 103K chains
   ≥4 deep (cap 8 held). Gen+train wall time tripled. Turns stayed flat
   (median 21) through iter 4 — the early explosion was pure re-ask chains.
5. **Run-1 re-read:** its entropy 0.131→0.165 was not "mild healthy
   exploration" — it was the same force at ⅓ speed. **The v0 loss has no
   entropy equilibrium**: nothing opposes the bonus when advantages are ≈0,
   and exploration already comes from τ=1 sampling, so the always-on bonus
   buys nothing and destabilizes.

## Decision

1. **The §4 contingency fired → guards promote to v0.** The loop driver must
   not accept a checkpoint whose iteration crossed triplines; it halts (or
   rolls back to the prior ckpt) on: per-iteration mean KL(π‖μ) > 0.05,
   entropy > 2× the run's iter-0 mean, or veto rate > 1.5× the run's iter-0
   rate. All three signals were in monitor.jsonl by iteration 4 — a guard
   would have saved ~5 h and the garbage chain.
2. **The §6 anomaly rule becomes two-sided.** Critic ≫ reward (iter 5: v0
   0.65 vs reward 0.50) is as much a bug report as reward ≫ critic; it went
   unflagged.
3. **The always-on entropy bonus is retired.** Replacement: a hinge floor —
   the bonus applies only below an entropy target (~the run's iter-0 mean),
   contributing zero gradient above it. Exploration remains τ=1 sampling's
   job; the floor only guards against genuine collapse (the failure the
   bonus was there for).
4. **lr ceiling bracketed:** stable at 1e-5, runaway at 3e-5 *with* the
   always-on bonus. With the bonus retired the ceiling is untested — run-3
   probes lr under the new guards (guards make the probe cheap: worst case
   is a halted iteration, not a burned night).
5. d6-run2 is discarded as a training chain (iter-000..003 ckpts are
   drifted-hot with unknown arms); `data/training/d6-run2/` is kept as the
   negative-result record. **The run-3 init remains d6-run1's final ckpt**
   (0.5083 ± 0.0246 corrected under re-ask — the standing baseline).

## Consequences

- d6-vtrace-loop §4/§6 amended (same commit): hinge entropy floor, guard
  triplines, two-sided anomaly rule.
- Run-3 = the first guarded run: ent hinge + lr probe (1–2e-5), init
  d6-run1 final, `-reask`, fresh seed stream; done-when #4 still open, read
  at 2,000 games with Ante-corrected paired stats when a run survives its
  guards.
- Watch items carried: server fallbacks 3–9/iteration (flat across load —
  a small constant-rate class, unrelated to the collapse, still nonzero
  where run-1 had 0); veto chain-depth ≥4 count is a cheap secondary
  collapse indicator (25× jump at iter 4).
- Priced honestly: the 3e-5 arm cost ~9.5 h GPU and falsified "run-1 left
  free speed on the table" — the drift rate was the stability margin.
