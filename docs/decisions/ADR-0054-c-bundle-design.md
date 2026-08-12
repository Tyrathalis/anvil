# ADR-0054: C-bundle design — sequence-contrastive timing targets, critic-phase value targets, §6c re-priced

- **Date:** 2026-08-11
- **Status:** accepted
- **Design-doc anchor:** §4 (drill-regime value targets), §6 (contrastive
  pairs), d6-vtrace-loop §6c (pricing amended), m7-plan D2

## Context

ADR-0053 funded the C bundle and carried four design inputs: target shape
(per-point advantage vs binary preference), channel (policy-gradient vs
auxiliary head), mixing weight vs the sparse terminal signal, and the
N/K campaign budget. The C3 re-tune additionally needed the m7-plan
pre-work read (re-ask chains vs independent events) and ADR-0053's
calibration bound: the penalty for trying must stay below the measured
cost of not trying (−1.5pp ≈ 0.015 reward units per held turn).

Three facts established this session ground the pins:

1. **Chain read (new standing script `scripts/rejected_chain_read.py`,
   all 20 run13 main stores: 49,902 veto events / 9,596 trajectories,
   5.2 per trajectory — ADR-0049's band reproduced).** Chains are
   positionally inferred (consecutive vetoed priority attempts, same
   seat, same turn — §6b re-asks immediately, nothing intervenes).
   **57.8% of veto events are singletons; chains are short** (83% of
   chains are length 2; 12 events in 49,902 hit the 8-cap), so
   first-attempt-only pricing alone removes only 23.5% of exposure —
   the hypothesized chain pile-up is NOT the main story. The real
   over-pricing is λ itself: λ = 0.02 per event exceeds 0.015, the
   measured cost of a full held turn. Sharpening facts: **76% of veto
   windows end abandoned** (the model attempted, was vetoed, ultimately
   passed — paying the penalty AND the tempo loss the penalty was meant
   to prevent), and chain length is realizer walk-down machinery, not
   graded intent — a length-4 chain is one wrong timing pick priced
   four times. Per-iteration means wander 2.5–11.0 with no downtrend:
   twenty iterations of penalty never trained vetoes away (consistent
   with ADR-0049 — the gradient went into cast suppression instead).
2. **The loop retrains the full-vis critic every iteration**
   (`finetune_value --full-vis` on the fresh mixture; pass-A values —
   the V in the V-trace advantage — come from that critic). m7-plan's
   C2a wording ("aux value loss" on the trained net) would put drilled
   accuracy only into the policy's masked head, which the advantage
   never reads while a critic serves pass A. The critic phase is the
   channel that realizes the mechanism-of-action statement.
3. **Campaign economics:** the N=4/K=32 probe rung sustained ~3,200
   completions/hour, pricing a 2-arm act−hold label at ~1.2 min/point
   at K=32 (~0.6 at K=16). The probe's labels rows do not record the
   act arm's realized first cast — a small harness extension needed for
   cast-specific targets.

## Decision (user-approved pins, 2026-08-11)

**C-seq — sequence-contrastive timing targets (the new component):**

1. **Target = advantage × specific-cast contrast** at the marked
   mainline fork window: L_seq = −Â(fp) · [log p(cast*) − log p(pass)],
   with Â(fp) = wr_act − wr_hold clipped to ±0.25 (engineered
   aggregates get clips at birth) and cast* = the act arm's modal first
   cast. Fallback to cast-mass-vs-pass when modal agreement < 50%.
   Rewards the cast the rollouts actually evaluated, not aggression per
   se (ADR-0053's act−nat caution); per-point sign handles
   hold-favoring states.
2. **Harness extension:** labels rows record each act-arm completion's
   first-cast SA + the modal agreement fraction (labels-only stays —
   pin 3 of the forced-branch design unchanged). Rides the D3 window.
3. **Campaign: P ≈ 100 points/iteration at K = 16, two arms
   (act-4/hold-4), labels regenerated fresh every iteration** — the act
   arm is the *current* policy's preferred cast, so labels are
   policy-conditional and staleness bites; freshness beats the √2
   per-point SE of K=16 vs 32. Selection: model-seat-active in-band
   points (~3× overshoot per the ADR-0052 coverage rule), riding the
   drill phase's rotating slice. Cost ≈ +1h/iteration (~2× current).
   N = 4 is a campaign hyperparameter, not a law.
4. **Mixing:** w_seq calibrated empirically at run start so the seq
   term carries ~10% of policy-gradient mass; its own metrics
   accumulator (per-lever attribution).

**C2a — drilled-point rollout value targets: critic phase + policy
aux.** Aux BCE toward wr_K(fp) at fork first-windows added to the
per-iteration critic phase, capped ~10% of critic batches — drilled
accuracy enters pass-A values and therefore the advantage (the M7
mechanism, realized with zero new generation: the drill phase already
produces the K=8 completions). The same aux also lands on the policy's
masked head in rl.py (trunk shaping; keeps the masked/full-vis A/B
honest). No drill-regime task token in v1: under the re-tuned λ the
shaped/unshaped value-target gap is ≤ ~0.04/trajectory — noted, revisit
if the aux and main value losses visibly fight.

**C3 — §6c re-priced: first-attempt-only, λ = 0.01** (from per-event
λ = 0.02, chain cap 8). One penalty per veto *window* regardless of
chain length. Per-window exposure ≤ 0.01 — strictly below one held
turn's measured cost, which is the exact calibration statement: trying
is never priced worse than a turn of not trying. Total exposure falls
to ~38% of current. Combat-drop events (no chains) simply take the new
λ. Anti-passivity guards stay armed (casts/game, first-attempt veto
rate). A λ change is an RL-chain boundary — rides the D3 era boundary
that was already scheduled.

## Consequences

- d6-vtrace-loop §6c's accepted pricing (λ = 0.02, per-event) is
  superseded by this ADR; amendment note added there.
- The bundle run's build list: forced-seq labels-row extension +
  in-loop forced-seq phase (harness), L_seq + masked-head aux in rl.py,
  critic-phase aux in finetune_value, first-attempt-only veto grouping
  in `rejected_events` (the chain-grouping logic now exists in
  `scripts/rejected_chain_read.py` to be shared/ported), w_seq
  calibration at run start.
- Still owed before the run (m7-plan D1 rider, unlanded): the ADR-0049
  cast-suppression + interaction-holding reads productionized into
  `scripts/` — they are the gate's attribution instruments.
- Sequencing unchanged: D3 stability pass + era boundary + re-baseline
  → one training run vs the standing gate (m7-plan done-when 2/3).
- Standing lesson (chain read): when a penalty's structural dichotomy
  is pinned in advance (chains vs singletons), run the cheap
  decomposition before designing the fix — the measured answer (λ
  magnitude, not chain structure) differed from both pinned branches.
