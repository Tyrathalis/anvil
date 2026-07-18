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
  (keeps the head's p(win) calibration semantics). ~~Small entropy bonus per
  head from day one (collapse guard, monitored).~~ **Amended by ADR-0017
  (run-2 collapse): the always-on bonus has no equilibrium — with mirror
  self-play advantages ≈0 it is the only persistent policy gradient and
  compounds with lr into runaway (run-2 @ lr 3e-5: entropy 0.18→4.4 by iter
  5, arms 8.5%). Replaced by a hinge floor: the bonus applies only below an
  entropy target (~iter-0 mean), zero gradient above. Exploration is τ=1
  sampling's job.**
- Critic = the policy net's own (info-set-masked) value head. The full-vis
  asymmetric critic as V-trace baseline is a documented upgrade, not v0 —
  it doubles target-pass cost and mixes conventions; d4-critic-fullvis
  remains the Ante/eval critic.
- ~~No KL-to-BC anchor v0; KL(π‖μ) and entropy are monitored, and the anchor
  is the named contingency if entropy collapses or KL runs away.~~ **The
  contingency fired (run-2, ADR-0017). Guards are v0 now: the driver rejects
  a checkpoint and halts when the iteration crossed a tripline — per-iter
  mean KL(π‖μ) > 0.05, entropy > 2× iter-0 mean, or veto rate > 1.5×
  iter-0. Every needed signal was already in monitor.jsonl.**

## 5. Replay mixing

Uniform over the last R=4 iterations' stores (MultiStore already reads
disjoint stores as one corpus), fresh iteration weighted to ~50% of samples.
V-trace ratios price the staleness; AWR is the documented fallback if replay
ever goes deeper (plan §6 phase 2).

## 6. Monitoring: anomaly monitor + arms

Per-iteration `monitor.jsonl` row, written before the checkpoint is accepted:

- **Anomaly rule (§6): realized winrate exceeding the critic's predicted
  winrate is a bug report until proven otherwise.** Compare mean first-window
  V vs realized outcome per iteration (both seats). **Two-sided per ADR-0017:
  critic ≫ reward flags too (run-2 iter 5 read v0 0.65 vs reward 0.50
  unflagged — the value head chasing vs-targets that had reverted to V under
  clipped ρ).**
- Entropy per head; KL(π_{k+1}‖μ); mean/max ρ pre-clip; fraction clipped.
- Census-derived: veto rate, block/attack drop, fallback count (must stay 0),
  X ">16" clamp rate (watch item, was 0.4%→0.7%), transport failures.
- Game health: length distribution (stall watch), cap/draw rate, crash count,
  g/h.
- Arms (δ=0, 400 games, paired seeds, argmax serve) every K≈5 iterations via
  the standing `arms_report.py` path — progress meter, not gate. Ante ledger
  available for sharper reads when deltas are small.

## 6b. Run-2 amendment: serve-time re-ask-on-veto (2026-07-15)

Run-1 measured veto drift 14.1%→19.2% sampled across 12 iterations (argmax
16.6% vs D5's 13.9%): RL drifts toward cast attempts the executor silently
converts to passes — a reward leak the policy cannot observe. ADR-0012
pre-blessed the lever ("serve-time re-ask on veto is protocol-legal"); it
promotes to a run-2 prerequisite, ahead of lr/iteration scaling.

**Semantics — §2's action pin is unchanged; re-ask is an environment change.**
On an M1 CastPlan veto (`CastPlanRealizer.Result.sa == null`), instead of
converting the window to a pass, the environment re-issues the priority
decision with the vetoed candidate row removed. Each re-ask is a first-class
decision: fresh Obs seq (own dec/ret pair), own μ record, own sampling noise
(keyed `(game_seed, s)` as always), and an independent V-trace timestep. The
history ring carries the vetoed attempt into the re-ask window — serve-faithful
by construction, so loader parity holds.

**Mechanics (Java, per attempt):** realize → veto census line (gains
`reask=<attempt idx>`) → `Obs.ret(seq, null)` closes the vetoed dec →
remove the vetoed candidate from the options list → `Obs.decPriority`
(fresh seq, reduced options; also resets the single-slot `prioSeq`/
`prioOptions` `oi` bookkeeping — the ret-before-next-dec ordering is
load-bearing) → bridge round-trip with `retry_of` = the vetoed request's
wire `decision_seq` (proto field 9, reserved for exactly this, previously
unread). Loop exits: realized cast / model picks PASS / options exhausted /
cap `REASK_CAP=8` → pass. Removal granularity = the whole candidate row;
coarse for X-dependent unpayability (a different X might have been payable),
accepted v0.

**Flag:** harness `--reask` → run.json manifest → worker `-reask` →
`PlayerControllerAnvil`; off = pre-amendment behavior, M0 selectOne path
never re-asks. The server needs no flag (stateless per request); it counts
`retry_of > 0` into its stats.

**The two μ-parity invariants** (violations fire the §3 recompute tripwire):
1. every re-ask gets a **fresh `s`** — `decode_frame`'s `by_seq` and the
   `(g,s)` μ join both collide silently on reuse;
2. the re-asked dec's logged `opts` are the **reduced** list — the loader
   rebuilds candidate rows from stored opts, and μ was recorded against the
   served (reduced) set.

**Costs, accepted:** ~1 extra GPU round-trip per veto (~5/game at current
rates, ≈ +1% requests); re-asks add near-duplicate timesteps to the seat
trajectory (`1/t_len` PG normalization absorbs them).

**Eval comparability:** re-ask changes the environment for *every*
checkpoint. The standing arms recipe becomes `-reask` + `--obs` (obs enables
Ante-ledger corrected reads, adopted same day); the D5 arm is re-baselined
once under the new environment; cross-environment paired comparisons
(run-1 arms vs run-2 arms) are not valid.

**Follow-ups, not v0:** block-drop re-ask (same lever, combat surface);
X-class-specific removal instead of whole-row.

## 6c. M3 amendment: rejected-intent penalty — the §3d reward-shaping pin (2026-07-17, DRAFT)

**Status: drafted during d6-run4; needs user sign-off on scope + coefficient
before any run trains with it.** Amends design §3d's terminal-only reward.

**Motivation.** Re-ask (§6b) removed the reward *leak* but also the last
vestige of *cost* for doomed attempts: every attempt in a re-ask chain
shares the window's eventual outcome, so the advantage differential between
"attempted an unpayable cast, got vetoed" and "passed" is structurally zero.
Consequence measured in run-4 (2026-07-17): the cmd_tax observation fix
reaches the model (serve path verified end-to-end) yet commander unpayables
kept *growing* (iter-4 arms: Spider-Man 2099 vetoes 178→207/400g vs init,
first-attempt veto 0.242→0.329 argmax) — the feature has no gradient to
train from because the reward never distinguishes doomed attempts. The
observation fix and this penalty are one deliverable pair: the feature
supplies the *how*, the penalty supplies the *why*.

**Design.** A small negative per-event reward on **engine-rejected intent**
— every event where the engine had to refuse or repair the model's declared
action:

1. **Vetoed cast attempts** (every attempt in a chain, first or re-ask):
   r += −λ at that timestep. The counterspell-hold examination (M3-plan
   prerequisite, run on iter-4 arms) clears this: the cluster is 664
   `no_shape_fit` + 407 `unpayable` *attempts* — firing blanks / firing
   without mana. Holding counter mana = choosing PASS, which is never
   penalized.
2. **Dropped/repaired combat declarations** (attack drops, block drops,
   forced-add corrections): same λ per rejected declaration row. Same
   no-differential structure (engine silently repairs; the model never
   learns the declaration was illegal). Block-drop telemetry: 3.7%.

Unified principle: *the engine detects; the penalty is how detection reaches
the policy.* This is not heuristic shaping — no judgment enters, only
rules-legality events the engine already adjudicates.

**Coefficient: λ = 0.02 proposed; bracket [0.01, 0.05].** Scale logic: the
local differential vs PASS needs only to dominate gradient noise (mirror
advantages are O(0.01) mid-game); terminal stays 1.0, a 20-veto game loses
0.4 max at the cap — visible, not dominant. Chain cap 8 bounds per-window
exposure at 8λ.

**Mechanics.** Penalty enters as r_t at the rejected timestep in the V-trace
targets (terminal reward unchanged; §3d cap/draw rule unchanged). Reward is
no longer strictly zero-sum — irrelevant to V-trace (not a zero-sum solver).
The policy's masked value head learns the *shaped* return (win prob minus
expected future penalties) — acceptable for its critic role; note the
**Ante/eval critic (`d4-critic-fullvis`) trains on unshaped outcomes and is
untouched**, and winrate arms remain terminal-based, so the eval yardsticks
don't move. Loss-curve comparisons across the reward boundary are invalid
(new environment for the learner); arms comparisons remain valid.

**Reader-side derivation + validation gate.** Rejected-intent flags are
derived at label construction from the store: vetoed attempts from the
`retry_of` chain / ret-null pattern; combat drops by diffing the answered
AttackMap/BlockMap against realized combat in the following obs (the D5
bounded-join machinery). **Gate before first training use: derived counts
must reconcile exactly with census veto/drop counts on the same run** (the
loader-vs-measure reconciliation pattern that caught the D5 same-ids class).

**Anti-passivity guards.** The known failure mode: the cheapest way to zero
vetoes is to stop casting. Guards: (a) casts/game joins the driver guard set
— flag/halt if it falls >20% below iter-0; (b) first-attempt veto rate is
expected to FALL — if it falls while casts/game holds and arms hold, the
penalty is working; (c) winrate arms stay the true gate (a λ that buys veto
reduction at winrate cost is wrong, exactly like the D8 calibration finding).

**Rejected alternatives** (considered 2026-07-17, kept out deliberately):
- *Potential-based/board shaping (life, tempo, card advantage):* injects
  heuristic value judgment — violates the learned-value principle and §1
  hygiene; the value head's whole job is to learn this.
- *Per-turn time cost:* biases play style toward haste; the §3d cap/draw
  rule already removes the stall exploit.
- *Rescue bonus (reward re-ask recoveries):* asymmetric double-count; the
  recovered cast already earns whatever the game gives it.
- *Fallback penalty:* the combat-declaration fallback class (~0.1%) is an
  environment edge, not model intent — penalizing it teaches nothing.
- *X-clamp penalty (X>16 clamp, 0.4% of casts):* same rejected-intent
  family but realizes-as-clamped rather than refused; deferred — fold in
  only if ent_x/clamp telemetry grows.

**Provenance.** λ recorded in loop_config + monitor rows; a reward change is
an RL-chain boundary (runs with different λ never share a replay mixture —
the mixture's older stores carry returns priced under a different reward).

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
