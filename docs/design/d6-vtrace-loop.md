# D6: first V-trace self-play loop — build plan

2026-07-14. Implements m2-rl-plan §D6. Deliverable (plan's words): **a loop
that runs, doesn't collapse, and improves the arms.** First runs are
tens-to-hundreds of K games; Grindstone position economy is the M3-era scale
lever, not this.

Init: `d5-combat/last.pt`, δ=0. Concession disabled (§3d gate). Reward
cap-aware. Anomaly monitor from day one.

## 1. Loop shape: synchronous iterations, not async IMPALA

One 4090 serves actors AND trains. The arithmetic makes strict alternation
nearly free: an iteration's generation batch (~500–1,000 games ≈ 30–60 min at
fleet rate) yields ~300–600K decision windows; one training pass at batch 256
runs ~14 steps/s ≈ 3–8 min. Alternation costs <15% wall-clock and buys: zero
GPU contention, no hot-swap machinery (server restarts on the new checkpoint
in seconds), per-iteration provenance-clean stores, and bounded off-policy
staleness (≤1 checkpoint for fresh data) that V-trace's clipped corrections
are designed for. Async actors + weight push is the documented upgrade if
generation/training overlap ever matters; it does not at this scale.

**Iteration k:** serve `ckpt_k` (sampling on) → generate B games both-seats
bridged → ingest to `data/trajectories/<run>/iter-k/` (manifest pins ckpt
step) → compute V-trace targets under `ckpt_k` → SGD on replay mixture →
save `ckpt_{k+1}` → monitor report → restart server. Arms every K iterations.

## 2. Action definition: the model's sampled pick; realizer = environment

The executor modifies model intent at known rates (veto ~10–14% of cast
attempts, block drop ~3.7%). If "the action" were the *executed* action, μ
would be the marginal over realizer behavior — uncomputable, and the IS
ratios biased exactly on the decisions where realization diverges. So:

- **Action = the model's sampled composite pick** (candidate index incl.
  PASS, target slots, X class, one-field answers, combat row assignments).
- **Realizer + engine = environment.** Vetoes/drops/forced-adds are
  environment stochasticity; the reward already prices them. π/μ ratios are
  exact by construction.
- Consequence: RL training labels come from the μ record (what was sampled),
  NOT from obs `oi`/`ret` (what was executed). The BC loader's label path is
  untouched; the RL loader swaps in sampled actions where they exist.

## 3. Behavior policy recording: server-side `mu.jsonl`, zero Java changes

The server already parses the full wire dec record (`s` = per-game decision
seq, joined by dec/ret in the store) and the game header (`g` = game index).
Per answered decision it appends one record to a per-run sidecar:

```
{"g": ..., "s": ..., "task": ..., "acts": {per-head sampled components},
 "logp": total composite logprob, "ent": per-head entropies, "step": ckpt step}
```

Ingest merges `mu.jsonl` exactly like rollout `labels.jsonl` (existing
pattern), keyed `(g, s)` — an exact join, no positional fragility. The
learner recomputes π (and can recompute μ as a cross-check: serve/loader
parity is byte-identical, so a recomputed `logp` under `ckpt_k` must match
the recorded one — this is the standing drift tripwire for the RL loader).

Sampling: temperature τ=1 v0, seeded per `(game_seed, s)` — deterministic
replay convention holds. Sampling happens in the per-item batcher view (CPU,
per-item generator) from the logits `act()` already computes; arms/eval runs
keep argmax (`--sample` off).

## 4. V-trace specifics

- Trajectory = one seat's decision sequence within a game (both seats of a
  mirror game are two trajectories; the info-set transform already gives
  per-seat perspectives).
- Reward: terminal only. **Win = 1; loss = 0; draw/cap/crash = 0 for both
  seats** (§3d: a stalling leader must not profit — capping out forfeits the
  +1). Crash games keep `has_outcome` gating as in BC. γ=1.
- Targets: standard V-trace `vs` with ρ̄ = c̄ = 1, computed per game in one
  forward pass under `ckpt_k` frozen at iteration start (the target net).
  Composite logprob = sum of the active heads' factor logprobs for that
  decision (same masks the BC losses already use).
- Policy loss: −ρ_s · (r_s + γ·vs_{s+1} − V(x_s)) · log π(a_s|x_s), applied
  to every sampled head factor. Value loss: BCE with soft target `vs`
  (keeps the head's p(win) calibration semantics). Small entropy bonus per
  head from day one (collapse guard, monitored).
- Critic = the policy net's own (info-set-masked) value head. The full-vis
  asymmetric critic as V-trace baseline is a documented upgrade, not v0 —
  it doubles target-pass cost and mixes conventions; d4-critic-fullvis
  remains the Ante/eval critic.
- No KL-to-BC anchor v0; KL(π‖μ) and entropy are monitored, and the anchor
  is the named contingency if entropy collapses or KL runs away.

## 5. Replay mixing

Uniform over the last R=4 iterations' stores (MultiStore already reads
disjoint stores as one corpus), fresh iteration weighted to ~50% of samples.
V-trace ratios price the staleness; AWR is the documented fallback if replay
ever goes deeper (plan §6 phase 2).

## 6. Monitoring: anomaly monitor + arms

Per-iteration `monitor.jsonl` row, written before the checkpoint is accepted:

- **Anomaly rule (§6): realized winrate exceeding the critic's predicted
  winrate is a bug report until proven otherwise.** Compare mean first-window
  V vs realized outcome per iteration (both seats).
- Entropy per head; KL(π_{k+1}‖μ); mean/max ρ pre-clip; fraction clipped.
- Census-derived: veto rate, block/attack drop, fallback count (must stay 0),
  X ">16" clamp rate (watch item, was 0.4%→0.7%), transport failures.
- Game health: length distribution (stall watch), cap/draw rate, crash count,
  g/h.
- Arms (δ=0, 400 games, paired seeds, argmax serve) every K≈5 iterations via
  the standing `arms_report.py` path — progress meter, not gate. Ante ledger
  available for sharper reads when deltas are small.

## 7. What v0 deliberately is not

Async IMPALA / weight push; server hot-swap; concession; AWR; mode heads;
Grindstone economy; full-vis critic in the loop; upstream rebase. Each is
documented above where it would slot in.

## 8. Build order

1. `act()` sampling mode + per-item seeded sampling in the batcher view +
   `mu.jsonl` writer + `--sample` flag. Parity test: recomputed logp ==
   recorded logp on a smoke run.
2. Ingest merge for `mu.jsonl` (mirror labels.jsonl path).
3. RL loader: windows + sampled-action labels + per-game trajectory grouping.
4. V-trace target computation + losses in `anvil/training/rl.py` (reuse
   build_net/collate/load_compat).
5. Loop driver `anvil/training/selfplay.py`: iteration orchestration atop the
   existing harness launch/ingest, monitor report, arms cadence.
6. Smoke: 2 iterations × 60 games end-to-end, all tripwires green, then the
   first real run (~10–20 iterations overnight).
