# ADR-0048: Cycle 3 (d6-run13) resolved — strength TIE on the best curation yet; the layer question is now the question; audit chartered

- **Date:** 2026-08-09
- **Status:** accepted (audit charter user-approved 2026-08-09)
- **Design-doc anchor:** §6 (training/Grindstone), §4 (value)
- **Inputs:** [ADR-0046](ADR-0046-label-campaign-resolution.md)/[ADR-0047](ADR-0047-hidden-info-probe.md)
  (the graduated critic + elimination chain), the cycle-3 pipeline
  (migration read → `cycle_stock` → `drill-map-cycle3-k8` → selection v4
  w/ D3 composition), `data/runs/run13-final-arms-report.json` +
  `data/runs/drill-evalset-v3/eval-20260809-*.json` (numbers of record).

## The run

`d6-run13`: run11 recipe verbatim, init `iter-019`, in-loop critic
unchanged (attribution isolated to curation method + composition), 20/20
iterations, zero guard halts. One launch crash (fork-store index
encoding collides for source g=0 — the single such row dropped from
selection v4; proper encoding fix filed for the next store era). Arm
trend 0.4775 → 0.5025 → 0.4975 → 0.5100 (400-game reads).

## Verdict

1. **Strength: TIE.** Combined paired ante-corrected **0.5199 ± 0.0110**
   (2,000 games, 1,996 decisive) vs the standing **0.5316 ± 0.0110**:
   Δ = −1.2pp ± 1.6, t ≈ −0.75. **No promotion**; `d6-run11/iter-019`
   remains the ckpt of record; the 0.5316 baseline stands.
2. **Decomposition (evalset-v3, D2.4 pairing):** winnable **−2.4pp**
   (D3's chartered question: the residual did NOT close), coin
   **−9.1pp** (~3.5σ — the curriculum's most-trained bin got WORSE at
   held-out instances), long_shot −3.2pp, lost **+5.6pp**. The
   run12 conversion-trade signature, inverted: better at grinding
   near-hopeless positions, worse at converting contested ones.
3. **Mechanism notes:** veto rate elevated at close (0.215 vs ~0.10
   historical; spiked 0.20 mid-run, recovered, re-rose) — the §6c
   penalty (λ=0.02) at this veto rate is a persistent negative term on
   attempted casts. Crash tax 4/2,000 nominal.

## What this cycle establishes (with the two-week arc)

Every measured sub-quantity improved — critic ranking 0.27→0.48,
calibration ECE 0.33→0.004, curation honesty (31% of the old curriculum
exposed as luck-locked noise), crash anchors ~2.5 turns closer to the
error — **and strength did not move.** The static-critic axis is
measured out (ADR-0043/45/46/47). The coin-bin regression proves the
policy DID change behaviorally under training — it moved in the wrong
direction on exactly the trained material. Suspicion therefore shifts
one layer up: exploration/objective/credit-assignment, not
representation and not "the policy won't move."

## Decision: AUDIT before any further training spend (user-approved)

Three reads, all cheap (a day, mostly existing data), each producing a
named bottleneck layer:

1. **Behavioral delta** run13-final vs iter-019: serve-distribution KL,
   action agreement, where they diverge (the coin regression says they
   diverge somewhere — find it).
2. **Interaction-holding corpus probe** (the bait-them-out question,
   user 2026-08-09): from logged games, how often does the model hold
   castable interaction across turns with mana available, vs the
   heuristic's cast-immediately? Never-explored ⇒ exploration/objective
   layer; explored-but-not-reinforced across RL iterations ⇒ credit
   assignment (⇒ rollout-value targets / search); explored-and-grown ⇒
   recipe/eval layers.
3. **Veto/penalty telemetry pass:** whether §6c's penalty at a 0.2 veto
   rate is suppressing attempted aggression (one of the few quantities
   that measurably moved).

Context for the audit's stakes: the user's exploitability argument (the
heuristic spends interaction immediately; baiting is learnable in
principle) argues the true ceiling vs this opponent is well above 0.55
— the flat cycles are NOT eval saturation until proven otherwise.
Tier-3 search remains the strategic direction but is NOT built on an
unexplained flat substrate; the audit locates the layer first.
