# ADR-0037: M5 closeout — the compounding question answered: one-shot, with the mechanism measured and the successor direction instrumented

- **Date:** 2026-08-05
- **Status:** accepted (user-confirmed close, 2026-08-05)
- **Design-doc anchor:** §6 (Grindstone), §7 (value-audit invariant)
- **Inputs:** [ADR-0034](ADR-0034-m5-opening-sequence.md) (opening),
  the m5-plan D1 migration-read section (pre-registered, 2026-08-04),
  [ADR-0035](ADR-0035-d2-compounding-read-resolution.md) (D2),
  [ADR-0036](ADR-0036-d3-critic-calibration.md) (D3).

## The milestone question and its answer

**Question (ADR-0034):** does the drill loop compound — fixed decisions
moving collapse points up-level, each cycle narrowing toward stronger
play — or was cycle 1 a one-time correction?

**Answer: one-shot.** Δ2 = −0.58pp ± 0.73 (t=−0.79, 3,995 paired games
on matched standing+fresh seeds) against Δ1 = +1.98pp ± 0.71. A
near-verbatim second cycle from the promoted checkpoint's own losses
produced no measurable gain. Both directions were pre-approved as
honest closes; this one closes with the mechanism understood at three
levels rather than just the number recorded.

## Done-when resolution (all three TRUE)

1. **Cycle-2 curation/selection/evalset v3 online + migration read
   recorded** (2026-08-04, m5-plan D1 section): read recorded BEFORE
   the run against pre-registered signatures — verdict
   one-shot-consistent (stock stable 576 vs 584; distributions
   unmoved; 63.5% of cycle-1 addressable losses re-surfacing on the
   same seeds with crash turns unmoved; drilled = undrilled conversion
   28.9%/29.1% ⇒ cycle-1's gain was diffuse, not window-specific).
   Assets: selection v3 = 410 pts, evalset v3 = 116 w/ pinned baseline
   0.3488, eras chained via iter-019 measured on v2 and v3.
2. **Compounding read resolved** (ADR-0035): the one-shot verdict
   above; gate not cleared, NO promotion — ckpt of record stays
   `d6-run11/iter-019`, baseline 0.5316 ± 0.0110. Decomposition
   unanimous: stock undiminished / held-out transfer flat (drill-eval
   −0.2pp vs run11's +3.9pp) / conversion trade returned.
3. **Critic calibration measured** (ADR-0036): split verdict on 3,750
   banked K=8 labels — isotonic remap fixes absolute calibration
   (held-out ECE 0.30–0.36 → 0.025–0.048 ≈ repeat-noise floor;
   ADOPTED era-scoped for cycle-3 curation/doom labels) while ranking
   is representation-blind (Spearman 0.26–0.29 vs 0.94–0.97 achievable)
   and no calibration can fix it.

## The honest headline

**The drill loop is a one-shot corrector per curation method, not a
ratchet — and the reason is now measured: the training signal's value
model cannot distinguish live from dead positions in exactly the
population the drills mine.** Cycle 1 paid because it changed
curriculum composition (ADR-0030/0031); cycle 2 re-ran the method and
bought nothing; the critic that selects and scores the windows ranks
them at Spearman 0.27 against a 0.94 ceiling. More of the same signal
does not help; changing what the gradient can see does. That is the
M3→M5 falsification record compressed into one sentence, and it points
at representation as the binding constraint.

## Standing rules and tools born in M5

- **The migration read** (`scripts/migration_read.py`): run before
  pricing any cycle; a one-shot profile is a strong prior against an
  unmodified re-run. It predicted run12's outcome from curation-stage
  data at ~1/40th the compute.
- **Ranking-from-rollouts:** within loss-adjacent populations, the
  critic's ordering is not evidence; K-rollout labels are.
- **The value-audit invariant is mechanized:**
  `scripts/critic_calibration.py` ingests every future map/sweep run's
  drills.jsonl; the calibration set (3,750 labels) grows for free.
- **Isotonic calibration maps are era-scoped assets** like
  selection/evalset versions.
- **Instrument-limitation note:** critic-classified quantities in the
  record ("61% addressable", "18–39% luck-locked") are aggregate-level
  estimates from a ranking-blind instrument; the K=8 rollout maps are
  authoritative where they exist (rollout truth: ~59% of
  critic-addressable games are dead at the crash window).
- **Seed-set sensitivity:** run12's two gate halves disagreed by 3.5pp
  (~2.4σ); single-set reads at ~1pp effect sizes are not conclusive in
  either direction — the combined paired read is the standard.

## M6 scoping inputs (recorded, not decided)

- **The deciding first probe:** train a fresh head on the 3,750
  rollout labels against frozen trunk features — if anything can learn
  to rank from them, the cheap path (rollout-label value targets,
  ADR-0015 machinery, critic replacement) is open; if nothing can,
  encoder enrichment/unfreezing is the measured direction.
- Curriculum composition (winnable residual −5.1pp) = the proven cheap
  lever, available alongside.
- Ante correctness riders (draw-poison coverage, re-deal re-anchoring,
  node-level draw bias) + isotonic wiring ride wherever the critic
  work lands.
- Carried fork items unchanged (ADR-0033 inventory); upstream watches
  unchanged (#11285 etc.).

## Consequences

- Status bullet archived verbatim to
  [status archive M5 section](../status-archive.md); compact summary in
  CLAUDE.md; map swept (M5 collapsed, Now → M6 scoping).
- State of record unchanged by M5: ckpt `d6-run11/iter-019`, baseline
  0.5316 ± 0.0110, pool `cf2ca6ba`, selection/evalset v3 valid for
  iter-019-era candidates.
- Next session: M6 planning with the evidence chain above.
