# ADR-0044: B-2 partial-unfreeze probe CLEARS the gate — first lever past the frozen ceiling; label-starved, rising

- **Date:** 2026-08-07
- **Status:** accepted (next-step resource decision flagged for the user, see Decision 3)
- **Design-doc anchor:** §4 (value heads), §2 (state representation)
- **Inputs:** [ADR-0042](ADR-0042-d2b-design-session.md) (the pre-registered
  B-2 recipe: top-N trunk layers + value head, ranking loss, game-grouped
  holdout), [ADR-0043](ADR-0043-b1-feature-probe-verdict.md) (B-1 negative —
  the deficit is not at the input), [ADR-0041](ADR-0041-extended-curve-path-verdict.md)
  (the frozen benchmark + 0.46 standing gate),
  [ADR-0040](ADR-0040-d2a-labeling-reprice.md) (drill-mode label pricing),
  `scripts/unfreeze_probe.py` + `data/runs/unfreeze-probe-v1/` (harness and
  numbers of record).

## Context

With B-1 resolved negative (the trunk already linearly encodes state
arithmetic), B-2 was the last live lever before the parked encoder swap:
can gradient pressure on the trunk's own top layers learn ranking the
frozen `[STATE]` cannot linearly express? Harness: the exact frozen-probe
positions as masked-path value windows (`prep` banks 6,117 examples once),
RankNet pairwise logistic loss (|Δwr|-weighted, pairs gated at ≥ 2/8 — one
K=8 step is noise) on the c2 train split, early-stopped on a game-grouped
inner split (515 rows), final read on the SAME frozen holdout (1,197 rows)
as every other candidate. Era-scoped by construction (c2 labels on the
iter-019 ckpt of record). Cells cost ~0.3 min — ADR-0042's "a few
GPU-hours per cell" was off by ~100×, which is what made same-day seed
replication and a label curve free.

## Findings (5 seeds per N at lr=3e-5, shared holdout — paired comparison)

1. **N=0 control (head-only, ranking loss): 0.4528 ± 0.0017.** A fresh
   ranking-trained head recovers the linear-probe plateau exactly (vs
   0.3349 for the shipped BCE head — ADR-0039's head-blindness corollary
   re-confirmed) and no more: **0.455 is genuinely the frozen-representation
   ceiling, now measured a third independent way.**
2. **N=2 (top-2 trunk layers + head, 6.6M params): 0.4769 ± 0.0015 —
   every seed above every N=0/N=1/N=4 cell.** +0.024 over the plateau,
   ~14 seed-sds, paired on the shared holdout. N=4 lands between
   (0.4672 ± 0.0023 — more capacity, worse: overfit at this n); N=1 barely
   moves (0.459). **First lever to clear the ADR-0041 standing gate.**
3. **The label-scaling curve is RISING and STEEPENING at the boundary**
   (N=2, 3 seeds/point): 1K → 0.4428, 2K → 0.4500, 3.6K → 0.4769. Below
   ~2K train labels the fine-tune cannot beat the ridge; the whole gain
   arrives in the last 1.6K labels. **The lever is label-starved, not
   saturated** — opposite of the ADR-0041 frozen-feature curve, which was
   flat over the same range.

## Decisions

1. **B-2 clears; the graduated build proceeds per ADR-0042 done-when 2**
   with bundle = B-2 alone (B-1 failed its gate). The real build carries
   the pre-registered discipline: value-tower split or partial-layer
   protection for the shared policy trunk, era-scoping of every derived
   asset (isotonic maps, selection/evalset versions), and the standing
   2,000-game combined paired read vs **0.5316** as the only promotion
   gate.
2. **The probe result prices the build at N=2** (top-2 layers + value
   head); N=4's regression says deeper unfreezing needs more labels, not
   more capacity.
3. **Label expansion is re-priced from parked to recommended-first**
   (user decision — box time): the rising curve is the exact pre-registered
   trigger ADR-0039/0041 established for buying labels, and ADR-0040
   already measured the cheap path (drill mode, 27.3 pos/h/worker;
   5–10K/era ≈ 1–2 days). Recommended sequence: drill-mode tranche →
   re-run this probe at the expanded n (cells are ~minutes; the curve
   extends for free) → build at whatever N the expanded sweep picks. The
   fork stability pass (ADR-0033 carried items) rides as pre-campaign
   gate per the m6-plan.
4. **B-3 encoder swap stays parked** — the gate cleared, so the ADR-0042
   unpark condition (both probes fail) never fired.

## Consequences

- `data/runs/unfreeze-probe-v1/`: banked examples (`examples.pt`), grid
  report, seed-replication report, curve reports.
- `scripts/unfreeze_probe.py` gains `--seeds`, `--train-size`, `--report`
  (replication and curves are one-liners — the probe layer stays the cheap
  attribution instrument ADR-0042 wanted).
- Any ckpt the graduated build produces is a NEW ERA for era-scoped
  assets (standing rule, restated because this is the first time since
  ADR-0036 that a trunk-touching value ckpt is actually in prospect).
- The 0.4769-at-3.6K point becomes the number the expanded-label re-probe
  must beat for the tranche to have paid for itself.
