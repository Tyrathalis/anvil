# M9 D6 — the §3a turn-plan latent: design spec (the promotion-slot attempt)

**Pinned:** 2026-08-24 (D6 design session; user-approved forks: detached
carry + dense aux loss; probe-first aux-target selection; ADR-0053 accepted
as the ceiling evidence; window-rate sweep funded in parallel).
**Anchors:** [m9-plan.md](m9-plan.md) D6 (inherits the promotion slot via
the D4 negative branch, ADR-0069/ADR-0073 routing);
[anvil-design-v2.md §3a](anvil-design-v2.md) (the design surface: "at turn
start and on regaining priority, the network emits a plan embedding
conditioning all within-turn decoding");
[ADR-0049](../decisions/ADR-0049-flat-cycle-audit.md) (the bottleneck is
learning-signal density);
[ADR-0053](../decisions/ADR-0053-sequence-probe-resolution.md) ("dense
per-decision signal does not exist, dense per-PLAN signal does"; the
forced-branch machinery named the natural substrate for §3a plan-segment
credit); [ADR-0058](../decisions/ADR-0058-m7-closeout.md) (the chartered
natural-timing formulation — the considered alternative);
[ADR-0073](../decisions/ADR-0073-m9-ceiling-measurement.md) (decision 3:
this session must pin the escape argument + a pre-registered kill signal).

## The question

Can a turn-plan latent — the network's own scratchpad for within-turn
intent — move strength, where interface capability (§3c) measured out
sub-gate? The §15 bet on file: "turn-plan latent alone handles 3–4 action
tap/untap lines post-drilling — 65%."

## The escape argument (ADR-0073's mandatory pin)

The payment head died of marginal-vs-conditional collapse: its only
training signal was sparse trajectory returns routed through rare
deviation windows (~11–16 consequential windows/game, gate-relevant ones
far rarer), so straight RL learned the marginal statistic and pruned the
conditional one. The plan latent's signal structure is the opposite on
both axes, by construction:

1. **Consumption is dense.** The latent conditions EVERY decision in the
   turn, so the consumption path receives policy-gradient signal at every
   window — nothing depends on rare events.
2. **Emission is densely supervised.** The emitter is NOT trained by
   returns at all (the sparse channel that failed twice); it trains
   against a dense self-supervised plan-granularity target, every turn —
   the direct application of ADR-0049's density diagnosis and ADR-0053's
   "per-PLAN signal exists."

The residual failure mode is therefore different in kind: the policy can
learn to IGNORE the plan input (the marginal solution here — a constant
or unused latent). That is exactly what the pre-registered kill signal
instruments (§7). Frequency is also structurally opposite to §3c's:
plan windows fire every turn (~15–30 turn-groups/game/seat), not
0.11×/game — per-turn effects aggregate at gate scale (the ceiling
argument, §8).

## Design overview (v1, all pins reversible until the build session commits)

**Emit once per turn, carry detached, supervise densely, consume through
PG.** At the first own-seat decision window of each game turn, the
`[PLAN]` output (`out[:, 1]` — computed today, consumed by nothing) is the
emitted plan vector. It is cached per (game, seat), fed as an input to
every subsequent own-seat window of the same game turn, and reset when
the turn number increments. No gradient flows through the carry.

### §1 Emission & carry semantics

- **Emission point:** the first own-seat window of game turn `t`
  (whoever's turn it is — blocks and instants on the opponent's turn get
  a plan too; the grouping key is `(seat, obs.glob.turn)`, exactly the
  grouping the store reconstructs trivially and the reader precedents
  already use — the combat label window and the ADR-0054 re-ask
  detector).
- **Turn-first windows consume no plan** (`has_plan = 0`) — at serve time
  the plan does not exist yet at that window; training mirrors this
  exactly (serve/train consistency is the pinned skew boundary).
- **v2, recorded not built:** the design doc's fuller "re-emit on
  regaining priority" (a true within-turn recurrence, each window reading
  the previous window's emission). Held behind v1 reliance evidence — it
  multiplies the recompute surface and adds nothing until the policy
  demonstrably uses the v1 carry.
- **Explicitly out:** cross-turn persistence (the latent never survives a
  turn boundary in v1 — "within-turn" per the design doc).

### §2 Model surgery (small, graft-compatible)

- **Injection:** `StateAssembler` gains `plan_vec (B, d)` + `has_plan
  (B,)` batch keys; token 1 becomes `plan_tok + plan_proj(plan_vec) *
  has_plan` with `plan_proj` **zero-initialized** — day-zero behavior
  bit-identical (the `pay_kind_emb` precedent; `load_compat` zero-pad
  conventions apply). `collate()`'s fixed key allowlist extends
  (`cand_paykind` optional-key precedent); `Featurizer.example` mirrors
  field-for-field.
- **Emission head:** small MLP on `out[:, 1]` producing the aux-target
  prediction (target per §5). The plan vector itself is `out[:, 1]`
  (LayerNormed trunk output) — the aux head shapes it by gradient, no
  separate emission projection.
- **New params:** `plan_proj`, aux head. **Own optimizer group at lr
  1e-3, trunk stays 1e-5** — the ADR-0069 pin-2 arithmetic applies
  verbatim (~170–420 optimizer steps/iteration; at trunk lr new params
  never leave init).
- **No proto/wire change, no fork delta, no boundary event** — pure
  model-side, as chartered.

### §3 Serve path

- Carry lives exactly where `game_seed`/`header` live today: **the
  `Session` generator's locals** — one stream per worker, one live game
  per stream, requests arrive sequentially, so a session-local
  `{(g, seat): (turn, plan_vec)}` needs no cross-thread machinery. Evicted
  on `game_start`.
- The batcher constraint is satisfied by construction: `plan_vec` rides
  per-item in the example dict; the batcher's game-mixing never sees it
  as shared state.
- **Stores stay vector-free:** the plan is a deterministic function of
  the emission window's observation (which is stored), so training
  recomputes it — provenance and replay hold with zero schema change.
  `obs_schema` does not bump.

### §4 Training mechanics (fits the two-pass loop as-is)

The RL loop already iterates whole (game, seat) trajectories in temporal
order (`RlTrajectories`, contiguous segments), so turn grouping is a
loader-side `groupby((p, t))` — no sampler change.

- **Pass 0 (new, cheap, no-grad):** forward only the turn-first windows
  (`has_plan=0`), collect `out[:, 1]` per turn group (~1/3–1/10 of rows).
- **Pass A / Pass B:** unchanged shapes; non-first windows get their turn
  group's pass-0 vector as `plan_vec` (detached input, identical in both
  passes — the materialize-once answer to the two-pass constraint).
- **Aux loss:** attached in pass B at turn-first rows only:
  `L_plan = aux(head(out[:,1]), target(turn group))`, targets joined by
  the loader from the trajectory itself (no external labels, no
  campaign). All standing training rules from birth: **clips/hinge at
  birth** (ADR-0056), **auto-calibrated `w_plan` instrumented + guarded +
  recalibrated per iteration** (ADR-0057, `plan_share` telemetry mirrors
  `seq_share`), kl abort, share guard.

### §5 Aux target — probe rung R1 decides (pinned structure, pre-build)

**R1 RESOLVED same day
([ADR-0074](../decisions/ADR-0074-d6-r1-aux-target-probe.md), 20,191
turn-groups): both gates PASS wide — (a) macro-AUC 0.9235 vs arith
0.7528 (+0.171 vs the 0.03 pin), (c) mean Spearman 0.5665 vs 0.4462
(+0.120 vs 0.05). Selection = JOINT multi-task. Free finding: the
static [PLAN] readout already adds +0.016 AUC over [STATE] alone.
Next rung: build/graft (§8 step 2).**

Offline, on existing stores, before any model surgery — the D2a genre.
Candidate targets, both computable from the trajectory per turn group:

- **(a) own within-turn action summary:** multi-hot over the SA vocab of
  the seat's realized actions in the turn (what the turn-start state
  already commits to doing).
- **(c) end-of-turn delta:** own-perspective life/creatures/power/dev
  axes over the turn (the certify-axes genre — what the turn is worth).

**Probe:** predict each target from the frozen ckpt-of-record trunk's
turn-first `[STATE] ⊕ [PLAN]` outputs; baseline ladder per ADR-0043 —
base rate → obs-arithmetic (explicit features) → trunk probe; claiming
signal requires beating obs-arithmetic by the standing ≥0.03 margin
(AUC-equivalent per target type). **Selection rule:** prefer the target
that is predictable-above-baseline AND least obs-trivial; if both clear,
(a)+(c) jointly (multi-task aux). If NEITHER clears at turn-first
windows, the formulation's premise fails **before any build** — that
result routes to the forced-seq escalation or kills D6 at a session.
Exact thresholds pinned at the probe launch (base rates unknown until
measured; the structure and margin discipline are pinned here).

**R1 pins (PINNED 2026-08-24 at probe build, PRE-DATA — same session,
before any dump ran):**

- **Population:** `d6-run18-i000` + `i001` mirror stores (post-boundary,
  generation from the grafted init — nearest to ckpt-of-record
  behavior), both seats, every (seat, turn ≥ 1) group whose first
  own-seat window carries an obs. Trunk = `d6-run11/iter-019` frozen.
- **Split:** deterministic game-grouped 80/20 (standing).
- **Arm ladder:** base rate → obs-arithmetic (pinned explicit set: turn,
  per-seat life/hand/lib/commander-cast, per-controller battlefield
  total/creature/power/untapped counts, command-zone count) → `[STATE]`
  → `[STATE] ⊕ [PLAN]`.
- **(a) action summary:** multi-hot over a probe-local vocab (top-256 sa
  strings, ≥50 train support) + 3 summary bits (land_played,
  any_ability, attacked). Metric: macro-AUC over qualifying classes.
  **Gate: `[STATE] ⊕ [PLAN]` ≥ obs-arithmetic + 0.03 AND ≥ 0.60
  absolute.**
- **(c) end-of-turn delta:** own/opp life, own hand, own battlefield
  count, own creatures, own power — same-seat next-turn-group first obs
  minus emission obs. Metric: mean held-out Spearman over the six axes.
  **Gate: ≥ obs-arithmetic + 0.05 AND ≥ 0.15 absolute.**
- **Selection:** both clear ⇒ joint multi-task aux; one ⇒ that one;
  **neither ⇒ NO build** — escalation session (forced-seq target) or D6
  closes negative. Read counted once; any exploratory slicing reported,
  never gating.

- **Escalation (recorded, not v1):** ADR-0053's act−hold plan-segment
  advantages via the carried forced-seq campaign machinery — the
  value-aligned target, at campaign cost. The chartered natural-timing
  formulation (ADR-0058) lives HERE as an aux-target variant if the
  self-supervised targets prove insufficient — recorded so the charter
  is routed, not lost.

### §6 Telemetry from birth (priced by nothing)

- **Plan-reliance:** mean |Δ policy logits| with `plan_vec` zeroed vs
  fed, on a fixed offline probe set, per accepted iteration — THE
  consumption readout.
- **Latent informativeness:** across-turn variance of emitted vectors +
  aux holdout metric per iteration.
- `plan_share` (aux share of gradient mass) + its guard; head-movement
  series (`plan_proj` RMS — the ADR-0069 "moved vs never moved"
  separator).

### §7 Pre-registered kill signal (ADR-0073's mandatory pin)

At the probe run (§8), **if after 4 accepted iterations plan-reliance
remains at its day-zero noise floor while the aux holdout metric has
plateaued, the formulation is dead** — the policy is ignoring a latent
that has nothing left to learn to say. Halt, record the negative, route
at a session (v2 recurrence, forced-seq target, or D6 closes negative
and M9 closes on the D4/D6 double negative).

**Numerics (PINNED at the recipe session 2026-08-25, pre-launch;
day-zero banked on `d6-plan-init` over the pinned fixed population
`d6-run18-i000`, 40 traj / 10,629 carried windows: reliance_l1 and
argmax_flip EXACTLY 0.0 — live bit-identity — aux_act_bce 0.7105 ≈ ln 2,
aux_delta_l1 0.638):**

- **Instrument:** `scripts/plan_reliance.py`, run by the driver per
  accepted iteration on the fixed store (comparable series; readout in
  monitor.jsonl `plan_reliance`).
- **KILL (driver-automatic, exit 4, `PLAN-KILL` marker):** from the 4th
  accepted iteration — max argmax_flip over all accepted iterations
  **< 0.005** (the carry never flips 1-in-200 greedy decisions) AND
  aux_act_bce plateaued (**< 2% relative improvement vs two accepted
  iterations back**). Both conditions, conservatively conjunctive.
- **FUND (⇒ the D5-slot full run; human-adjudicated at the read,
  nothing auto-promotes):** argmax_flip **≥ 0.02** at any accepted
  iteration with guards clean AND aux_act_bce **≤ 0.8 × day-zero**
  (≤ 0.568) — the latent is behaviorally live and the emission
  informative. Grounding for 0.02: the D4 payment head at its
  most-moved shifted ~3–4% of drill-window argmax; a consumed latent
  should reach half that on ~10k carried windows (binomial SE ≈ 0.001 —
  20σ from the floor).
- **Between = discuss-zone**, session adjudicates (the D4 pattern).
  Behavioral axes (hold-then-cast, within-turn dithering) exploratory,
  never gating.

### §8 Sequencing & the strength read

1. **R1 aux-target probe** (offline, ~a session) → pins the target.
2. **Build + graft + day-zero verification** (bit-identity with plan
   zeroed; banked day-zero reliance/aux baselines).
3. **Probe run** (D4-shape: ~8×480, no arms, no campaign, guards
   unchanged) against §7's kill signal + a funding gate pinned at the
   recipe session — the gate is posed on the reliance/aux/behavioral
   channel (hold-then-cast, within-turn dithering — the ADR-0053
   behavioral axes), NEVER on a small-N accuracy count (the ADR-0069
   lesson).
4. **Full run** (the promotion attempt) only if funded: standing
   2,000-game combined paired read vs **0.5279 ± 0.0110**, own
   attribution, arms counted once, fresh-seed tiebreaker — m9-plan D5
   protocol under the D6 flag.

**Ceiling evidence (user-accepted 2026-08-24, in lieu of a fresh
measurement):** ADR-0053 measured plan-granularity headroom directly —
−1.5pp per held turn, natural > greedy ≫ hold ordering, dithering
abundant in exploration (ADR-0049) — and plan windows fire every turn,
so per-turn effects aggregate ~15–25× per game. The frequency structure
that sank §3c does not apply. Recorded honestly: this is an existence
argument for headroom, not a quantified per-game ceiling; if D6 reads
strength-neutral WITH high reliance and healthy aux, a quantified
ceiling measurement becomes the next question, not another run.

## Build/graft rung — BUILT 2026-08-25 (spec §8 step 2)

Full suite 242 green (236 standing + 6 new in `test_plan_latent.py`);
`rl.py --plan` integration smoke on `d6-run18-i000` clean (w_plan
calibrated 0.00125 at plan_frac 0.1, tripwire 0 violations, pass-0 9.7%
of wall). Landed:

- **Model:** `StateAssembler.plan_proj` (zero-init, gated by `has_plan`) +
  `plan_act_head`/`plan_delta_head`; `act()` exposes the emitted plan;
  `load_compat` allows plan params missing. Day-zero bit-identity
  test-pinned three ways (keys absent / gate closed / proj untrained);
  the wire-connected and gradient-reaches-proj cases test-pinned too.
- **Collate:** `plan_vec`/`has_plan` optional keys (absent ⇒ omitted ⇒
  static-token path).
- **Serve:** `ModelBackend` carry `{(g, seat): (turn, vec)}`, gated on the
  ckpt carrying plan params (`carry_plan`, the has_pay convention);
  emission = first answered request of the (g, seat, turn) group; g<0
  fork headers never carry; capped FIFO eviction. *(Owed: a carry test
  against a plan-bearing ckpt — trivial now `d6-plan-init` exists.)*
- **Loop:** `game_trajectories(plan=True)` marks + JOINT targets
  (sa-vocab ids + 3 bits; delta axes clamped ±20 at birth, lockstep with
  `plan_probe.py`); loader side tensors (dim-0 aligned, OOM-slice-safe);
  `plan_pass0` (materialize-once, both passes); aux term in pass B at
  emission rows; w_plan calibration + `plan_share` + `plan_rms`
  telemetry (the w_seq/ADR-0057 pattern, `--plan-w` carries iteration-0's
  value forward); **tripwire recomputes the head's carry under the REF
  net** — otherwise it would measure pass-0 net drift, not serve/loader
  drift. `--plan` off = byte-identical to pre-D6.
- **Graft:** `scripts/graft_plan_init.py` →
  `data/training/d6-plan-init/last.pt` — plan params at design init
  (proj rms 0.0 verified), **pay params STRIPPED** (ADR-0073 routing:
  the D6 runs never advertise the pay tag; attribution stays
  pure-latent).

**Next: the recipe session** — probe-run funding gate + kill-signal
numerics (§7) pinned pre-launch; driver flag threading + guard wiring;
day-zero reliance/aux baselines banked on `d6-plan-init`; the serve
carry test.

## Explicitly out of D6 v1

- In-graph BPTT through the carry (recorded fallback; GPU-hostile,
  two-pass-hostile, serve-parity risk).
- Re-emission on regaining priority (v2, behind reliance evidence).
- Cross-turn latent persistence.
- Any §3c coupling (payment surface is infrastructure per ADR-0073; the
  latent conditions the payment head only in the trivial sense that it
  conditions everything downstream of token 1).
- Tier-3 search (critic-leaf constraint stands, ADR-0061).

## Open items owed at later sessions

- R1 probe thresholds (at probe launch, pre-data).
- Probe-run funding gate + kill-signal numerics (at the recipe session).
- The M9 closeout ADR still owes: strength verdict (this track), the
  payment-completion queue routed by name (rate-sweep result in hand),
  pin-12 re-mine disposition, evalset repair routing.
