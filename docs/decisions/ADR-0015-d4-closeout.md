# ADR-0015: D4 closeout — full-vis critic of record (mid-game +12pp AUC), Ante certified at the omniscient tier, rollout labels proven-and-priced with scale-up deferred behind efficiency

- **Date:** 2026-07-13
- **Status:** accepted
- **Design-doc anchor:** §4 (asymmetric critic), §7 (Ante); m2-rl-plan D4 +
  done-when #3; ADR-0013 (the label fix + gate re-base), ADR-0014 (mirror
  certification). Closes the deliverable those two re-shaped mid-flight.

## Context

D4 was chartered as "Ante certification, then rollout-labeled critic" with a
gate of "beat the ~0.60 matchup-prior BCE floor, final-turn AUC off 0.68."
Its own shakedowns rewrote that charter twice: ADR-0013 (the winner-label
poisoning — every prior value number was fiction; gate re-based to beating
`d4-valuefix` in the turns-from-end 5–16 band) and ADR-0014 (certification
passed with the apparatus catching its own re-deal modeling error). What
remained at close was the critic itself and the rollout-label question.

## What closed it

1. **`d4-critic-fullvis` is the critic of record** (§4's asymmetric critic:
   full-visibility input, trained from the d4-valuefix init, 100K steps /
   110 min, value loss only — the policy tower and its serve path are
   untouched; the critic ckpt's policy heads are garbage by construction and
   must never serve). On 600 val games / 354K windows: **BCE 0.4541 / AUC
   0.8658 overall; by turns-from-end AUC 0.991 / 0.975 / 0.985 / 0.965 /
   0.927 / 0.821 / 0.673 at 0/1/2/3–4/5–8/9–16/17+; calibration clean.**
   Versus the masked head: +6.6pp (5–8), +12.0pp (9–16), +12.2pp (17+) —
   hidden information was exactly the mid-game gap. The re-based gate
   (beat d4-valuefix's 0.70–0.86 band) is cleared by 12 points.
2. **The rollout-label machinery works, end to end, deterministically**
   (fork `80bd8ded76`, Anvil `818e666`/`c3674e6`): `-rollout K -points M`
   forks live model games at sampled quiescent MAIN1 windows under
   ForkFidelityCheck's discipline, completes K wire-session copies under
   the bridge with per-rollout library re-randomization (determinization),
   and keys each point to its training window via new Obs `mark` records.
   Smoke reproduced outcome vectors exactly across runs. Design choice of
   record: **labeler mainlines are on-policy model games**, not corpus
   replays — forks inherit Anvil controllers (D1-certified), positions
   match the distribution the RL-era critic must track, and the model
   mirror provides the held-out eval basis.
3. **The pilot (501 games, 1,951 labeled points, K=8, 4 points/game):
   rollout means out-rank the full-vis critic as outcome predictors in
   every band** — AUC 0.864 vs 0.842 overall; 0.970 vs 0.915 at 5–8
   turns-from-end (+5.5pp), 0.858 vs 0.849 at 9–16, 0.710 vs 0.690 at 17+
   (n=1,842 scored windows; record
   `data/runs/d4-pilot-signal-comparison.json`). Their raw BCE is worse —
   K=8 means are quantized and clipped — but ranking is what a distilled
   critic inherits. So: **the labels carry real signal above the
   outcome-label critic, concentrated in the 5–8 band and the tails.**
4. **Economics, measured honestly:** ~17 positions/h/worker at K=8 with
   turn-stratified points (~9/h with the early-turn-heavy mix) — each
   labeled game plays ~33 games in one index, through a batch-1 server at
   ~59 rps. 1,951 labels ≈ 14 active fleet-hours; a 50K-label run ≈ 15
   days as-is. **Server micro-batching is the mandatory first lever**
   (GPU sits mostly idle between single-request round-trips; 2–4×
   plausible).
5. **Ante re-certified at the omniscient tier** (the ADR-0014 queued step;
   record `data/runs/ante-cert-20260713-fullvis.json`): values under
   `d4-critic-fullvis` over the same 12,800-game mirror —
   **corr(raw, ledger) 0.08 → 0.22; β̂ ≈ 0.69–0.71 (up from 0.21,
   converging toward 1 exactly as §7 predicts); fitted var ratio 0.9516,
   CI90 [0.9454, 0.9577] — a ~4.8% variance cut, ~7.5× the interim head's
   0.64%; and pure AIVAT (β=1) now reduces variance too (0.9603)** — the
   critic crossed the quality threshold where unshrunk corrections help.
   Game-level zero-mean holds everywhere (ledger t=−0.32; opener t=−0.23;
   draw game-sum t=+1.08). **One new finding, recorded not buried: the
   draw class shows a node-level bias under the sharp critic (+5.0e-4 ±
   0.8e-4, t=+6.4) that the weak critic couldn't resolve (it read −0.3σ)**
   — some sub-class of "draws" isn't uniform over the multiset (candidate:
   tutor-to-hand entries whose search look didn't serialize library rows,
   so the seen-id guard missed them — chosen cards misread as uniform
   draws would bias exactly this direction). It largely cancels across
   seats in the mirror (game-level clean) but is Ante's next correctness
   item, alongside the coverage levers (draw-poison rule skips 69% of
   draws; re-deal opener re-anchoring). The self-audit catching a finer
   approximation each time the critic sharpens is §7's design working.

## Decision

**D4 is CLOSED.** M2 done-when #3 is satisfied on its re-based reading:
the critic clears the corrected gate by a wide margin and the Ante mirror
certification passed (ADR-0014) with the omniscient-tier re-measure above.
**Rollout-label scale-up is DEFERRED** — the machinery is certified, priced,
and parked, not abandoned: it returns behind server micro-batching, or when
D6 telemetry shows the critic limiting the loop, whichever comes first.

## Consequences

- **Next: D5 combat constructs** (hard prerequisite for D6 per ADR-0012 —
  expressiveness, not winrate; its BC arms will tie by construction).
- Critic usage lines: the Ante ledger auto-detects full-vis ckpts (§7
  omniscient tier); the D6 baseline/advantage questions get answered with
  the critic that exists — full-vis for targets/eval per §4, the masked
  policy-tower value head stays the only thing that serves.
- Standing per-critic upgrades: `certify --from-ledger` re-aggregates free;
  a values re-eval on the mirror is 96 min. Re-deal opener re-anchoring
  (tuck-dec windows) and shuffle-aware draw-poison relaxation remain the
  coverage levers for Ante's next tier.
- The labeling pilot's corpus (501 on-policy games + 1,951 labels,
  `data/trajectories/d4-rollout-pilot-20260712-131049`) stays ingested —
  it is the seed set for any future distillation and the eval set for
  micro-batching work.
- D6 pre-work flags carried: per-game memory accumulation under
  both-seats-bridged mode (the OOM class, ADR-worthy if profiling confirms
  a leak); the X ">16" clamp watch; census stays off in labeler runs.
