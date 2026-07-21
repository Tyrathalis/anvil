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

**Status: ACCEPTED 2026-07-17 (user sign-off mid-run-4): scope = vetoed
casts + combat drops, λ = 0.02.** Amends design §3d's terminal-only reward.
First training use = run-5, gated on run-4's feature-only verdict and the
census-reconciliation gate below.

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
bounded-join machinery). **Gate (amended 2026-07-17 after the first live
reconciliation, run3-i000, 480 games): priority must reconcile EXACTLY
(certified: 9,007 = 9,007); combat census comparison is DIAGNOSTIC, not
ground truth — every n≥2 event must match (they all do: the 7-, 5-, 3- and
2-drop events reconcile to the event) and every residual single-event
mismatch must be attributable to one of the named corner classes below.**
The forensic dive on the 5 mismatch events found census and derivation
measure *different things* at the corners, and the derivation's
intent-vs-outcome accounting is the semantically correct penalty basis:

1. *Census over-counts internal repair* (g443 attack, `dropped=1 forced=1`):
   the realizer's tiered self-validation dropped a declared attacker and the
   forced-add tier restored it — realized combat equals the declared intent
   exactly. Derivation correctly reads 0; census counts the machinery's
   round trip.
2. *Census is blind to silent illegal-block discards* (g269: single block
   into an animated Hive of the Eye Tyrant, menace; g363: single block into
   Troll of Khazad-dûm, "except by three or more"): **min-blocker
   RESTRICTIONS pass the block realizer** (whose repair handles
   *requirements* via the `mustBlockAnAttacker` fixed point, not
   restrictions) **and the engine discards the illegal block silently
   downstream** — census records nothing, the model's block simply
   evaporates. This extends the D5 "the engine never validates AI blocks"
   finding: restrictions ARE enforced, silently, after the declaration.
   These are genuine rejected-intent events the derivation catches and the
   census misses — the penalty pricing them is a feature. (Serve-side
   follow-up queued in the worklist: teach the block realizer MinMaxBlocker
   restrictions, or re-ask on them.)
3. *Post-declaration invalidation by opponent triggers* (g383: Seasoned
   Dungeoneer's on-attack "target attacker gains protection from creatures"
   removed a block that was legal when declared): environment dynamics, not
   a declaration error — penalizing it is philosophically impure but the
   class is tiny, inseparable reader-side in v1, and the gradient it adds
   ("respect protection tricks") is not wrong play advice.

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

## 6d. M3 D2 amendment: mixed-opponent generation (2026-07-19, ACCEPTED)

**Diagnosis this answers (ADR-0022's ceiling datum):** mirror self-play with
a calibrated critic yields ~zero per-decision advantages (pg ±0.002 in every
healthy run), so winrate learning crawls — while the §6c penalty episode
proved the loop learns FAST when a real differential signal exists. Run-5's
late paired-arms decline (0.540 → 0.475, entropy gliding down) carries the
mirror-overfit signature: generation shows the policy only itself, eval
measures it against the heuristic. Both problems point the same direction:
put the eval distribution INTO generation.

**Design.** Per iteration, a fraction `heur_frac` (v0: 0.5) of games are
model-vs-heuristic instead of mirror: the harness's existing single-seat
bridged mode (`--bridge-seats`), split evenly between seat 0 and seat 1 for
symmetry. Consequences, all falling out of existing machinery:

- **Trajectories**: heuristic-opponent games contribute ONE mu-covered
  trajectory (the model seat); mirror games two. `game_trajectories`
  already excludes non-mu seats. At heur_frac 0.5 the trajectory mix is
  2:1 mirror:heuristic — recorded, not corrected, in v0.
- **Reward** unchanged (§3d terminal + §6c penalty); against the heuristic
  E[win] ≈ 0.52, so genuinely asymmetric advantages exist on exactly the
  distribution the arms measure.
- **μ/ratios/tripwire** unchanged (μ only ever covered model decisions).
- **Driver**: an iteration's generation becomes three harness launches
  (mirror both-seats; heur s0; heur s1), three run dirs, three stores.
  `loop_state.stores` becomes a list of per-iteration GROUPS so the replay
  window (R=4) stays "last 4 iterations", not "last 4 stores"; old flat
  loop_state entries load as singleton groups. Fresh weight applies to the
  newest group's stores, replay weight to older groups' — the flat
  store/weight lists rl.py already accepts.
- **Guards/census**: per-run baselines as always (census now spans both
  game types; the veto/casts metrics are model-seat-only by the `by=bridge`
  filter, so their semantics are unchanged).
- **Arms comparability**: untouched (arms were always vs-heuristic argmax).

**What this is not:** a league (no opponent pool, no past-checkpoint
opponents — documented upgrade if heuristic-anchoring plateaus); not a
teacher-forcing return (the heuristic never labels anything — it just plays
the other seat, exactly as in every eval arm since M1).

## 6e. M3 D2 amendment: generation temperature (2026-07-21, RESOLVED NEGATIVE — lever falsified by the curve)

**Resolution (same day): the τ-strength curve on run-6 iter-19
(`data/runs/tau-curve-run6i19-report.json`, 400 paired games/point) is FLAT
in τ ∈ [0.3, 1.0].** Winrates 0.5200/0.5025/0.5200/0.5075 at τ =
0.3/0.5/0.8/1.0 vs argmax 0.5400; paired-vs-argmax −2.0 to −3.75pp (all
±~2.1); the sharpest read — τ-vs-τ paired with shared seeds AND shared
sampling noise (CRN) — puts τ=0.3 only +1.25pp ± 2.0 over τ=1.0 (t=0.63).
No temperature recovers the tax. Mechanics confirmed live (first-attempt
veto rises monotonically 0.105→0.128 with τ), so the flat winrate is
behavior, not instrumentation. **Interpretation: with a peaked policy
(entropy ~0.17), τ<1 already plays argmax on confident windows; the
surviving deviations sit in near-tie windows whose probabilities barely
move with τ. The tax is the price of exploration itself — not a removable
inefficiency — and the actionable defect is that exploration variance
never gets credited back to the near-tie decisions that caused it: a
credit-assignment (critic) problem, not a temperature problem.** Run-7
therefore keeps τ=1.0 (single-variable discipline) and takes the critic
lever (§6f). The tempered-μ plumbing below stays landed (any future τ≠1
run trains correctly).

Original design notes (kept for the record):

**Diagnosis this answers (run-6's reward-split measurement):** the §6d
heuristic-half games — τ=1 sampled play against the eval opponent — read
0.5064 ± 0.0081 pooled (3,837 games) where the same checkpoints' argmax
arms read 0.53–0.54. The ~2pp sampling tax lands exactly on the learning
signal: the heur-half mean advantage was ~+0.006, not the ~+0.025 the
argmax arms implied, so §6d was mispriced by the temperature gap. τ-noise
is a compute multiplier (outcome variance uncorrelated with credited
decisions), and at desktop scale signal efficiency IS the strength budget.

**Design.** Generation serves at τ < 1 (value from the τ-strength curve on
run-6 iter-19: arms at τ ∈ {0.3, 0.5, 0.8, 1.0}, `scripts/tau_curve.py`;
expectation ≈ 0.5–0.8). Everything else keeps §6b/§6c/§6d. Serve plumbing
existed since D6 day one: `make_noise` scales the Gumbel noise (argmax(l/τ
+ g) == argmax(l + τ·g)), `act()` reports logp under the TEMPERED
distribution — the recorded μ is the true behavior policy at any τ.

- **Learner (LANDED 2026-07-21):** the μ-recompute tripwire reads the
  generation temperature from mu meta per store (`composite_logp(...,
  temperature=mu_tau)`); replay mixtures may span runs at different τ.
  Negative-control test: a τ=0.5 record recomputed at τ=1 trips the 0.2
  tolerance (sparse — ~2/160 windows on a peaked policy — but real runs
  sample 10^5 decisions/iteration).
- **V-trace needs NO change:** ratios are π(a)/μ(a) with π the τ=1 policy
  being optimized and μ the recorded tempered logp — exactly the
  off-policy correction V-trace exists for. Note the asymmetry to watch:
  τ<1 sharpens μ, so ρ < 1 on modal actions and >1-clipped (ρ̄=1) on rare
  sampled ones; monitor mean ρ (run-1..6 baseline 0.94–0.99 at τ=1).
- **Exploration:** τ↓ trades exploration for signal; the entropy hinge
  floor (§ADR-0017) still guards collapse, and τ is generation-only —
  arms/eval stay argmax, Ante unchanged.
- **Finer dials if the curve is interesting:** per-head temperature (the
  choice head carries the pass/cast decision; combat heads may want more
  noise than X), per-game mixed τ (a τ≈1 slice preserves exploration
  coverage while most games generate signal).

## 6f. M3 D2 amendment: full-vis critic in the loop (2026-07-21, DRAFT — run-7's lever)

**Diagnosis this answers (two lines of evidence converging):** (a) the
ADR-0022 ceiling datum — mirror parity + the calibrated masked critic give
pg terms ±0.002, so winrate learning crawls; §6d put real signal into
generation but the heur-half advantage is only ~+1–2pp. (b) The §6e curve —
the sampling tax is exploration cost concentrated in near-tie windows, and
its variance is never credited back to the decisions that caused it. Both
point at credit precision. The full-vis critic is measured far sharper than
the masked head the loop currently bootstraps from: AUC 0.8658 vs 0.788
overall, +6.6/+12.0/+12.2pp at 5–8/9–16/17+ turns-from-end (ADR-0015).
Sharper V ⇒ smaller noise floor under |vs − V| ⇒ the small real advantages
stop drowning.

**Design: asymmetric V-trace (AlphaStar precedent).** Pass-A values —
baseline AND bootstrap — come from a separate full-vis critic net; π, μ,
ratios, tripwire, reward, guards all unchanged.

- **rl.py**: `--critic-ckpt` loads the critic net (`load_compat`). The
  loader emits a parallel full-vis example stream for the same windows
  (`Featurizer.example(full_vis=)` → `assemble(full_vis=)` — reader-side
  un-masking of the full-state store records the wire always carried; the
  ~3-line passthrough is the only encoder change). Pass A runs the frozen
  critic on the fv segments for `values`; **pass B never sees fv tensors —
  the policy gradient's leak boundary, test-pinned.**
- **The policy's own masked value head keeps training** on the same vs
  targets (serve-artifact consistency + §6 monitor continuity). The monitor
  logs BOTH critics' v0-vs-realized — a live masked-vs-full-vis A/B every
  iteration for free.
- **Critic lifecycle**: init `d4-critic-fullvis`; per iteration the driver
  runs generate → ingest → **critic phase** (`finetune_value --full-vis
  --trainable all`, low lr ~1e-5, ~1 pass over the fresh+replay window,
  init = previous iteration's critic) → **policy phase** (rl.py with the
  fresh critic) → arms. Iteration 0's critic phase adapts the D4 critic to
  the self-play distribution before the first policy gradient consumes it —
  no separate warm-start run needed. Critic ckpt saved per iteration
  (provenance; `loop_state` gains the critic path).
- **Costs**: loader featurization ~×1.7 (second example per window), pass A
  +1 forward per segment, one extra resident net during the policy phase
  (`--rl-seg` absorbs VRAM pressure); critic phase = minutes on the freed
  GPU between generation and training.
- **Monitoring/guards**: the §6 anomaly rule reads the LOOP critic
  (full-vis) vs realized reward; masked-head read kept alongside; critic
  phase logs BCE on fresh vs replay stores (overfit watch — 480-game
  iterations are small for `--trainable all`).
- **Bias note**: bootstrapping from full-vis V injects hidden info into vs
  targets (the standard asymmetric-critic caveat; the §4 v0 decision
  deferred exactly this). The policy only receives it through advantage
  magnitudes, never as an input feature; ρ/KL/entropy monitors watch for
  pathology. Ante keeps its own copy of the critic question independent —
  certify still runs d4-critic-fullvis until a mid-run critic proves
  sharper there too.

**Run-7 config pin: identical to run-6 except the critic** (heur_frac 0.5,
λ=0.02, guard-kl 0.06, lr 2e-5, 480 g/iter, τ=1.0, re-ask, init run-6
iter-19) — single-variable attribution, same paired arms.

**What this is not:** rollout labels (D4's machinery stays parked behind
its economics), not a critic ensemble, not a change to what the policy
observes.

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
