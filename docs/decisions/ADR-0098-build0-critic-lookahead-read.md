# ADR-0098: M11 Build 0 — the critic-lookahead read lands in the HYBRID band (0.301 ± 0.022): rollouts stay the label of record, K is the cheap-label dial, the learned pivotality head aims, critic lookahead survives only as the deployment-gate candidate

- **Date:** 2026-09-06
- **Status:** accepted (the pre-registered bars adjudicate; refinement of the HYBRID text on one
  measured comparison, recorded below)
- **Design-doc anchor:** m11-plan.md Build 0 + Fork C; anvil-design-v2 §4 (asymmetric critic),
  §3a (pivotal-turn search), §6 (ε-pivotality); ADR-0097 (the two critics named)

## Context

Fork C asked whether "copy the game, apply one option, evaluate with the critic" — ~1/16 the cost
of a K=8 two-turn rollout label — ranks the certifier's options the way the rollouts do. If it did,
it would become the training-time labeler for most windows and the only search a deployment ever
runs. The read was pre-registered 2026-09-05 (m11-plan Build 0): headline cell = the full-vis
critic at the first priority window of turn t+1 (**eot**), one copy (K=1), score = V(arm) −
V(natural) paired by roll seed, vs the pinned 8-roll h2 composite; mean within-window Spearman over
windows with ≥ 3 scored arms; **≥ 0.40 ADOPT / 0.20–0.40 HYBRID / < 0.20 RETIRE**. Instrument:
the harvest's 806 rolled-out windows replayed through `-forceschedule -forkobs` (fork
`f4824f3d6`, recording only), every completion window stored, both critics read
(`scripts/critic_lookahead_read.py`; runs `critic-lookahead-cl1` = 200-window subset,
`critic-lookahead-cl2` = all 806).

## The read (cl2, 800/806 windows; 6 lost at replay; 650 with ≥ 3 scored arms after voids)

| predictor → target (within-window Spearman) | mean ± se | median | top-1 | piv. AUC |
|---|---|---|---|---|
| **full-vis / eot / K=1 vs comp8 — HEADLINE** | **0.301 ± 0.022** | 0.46 | 0.29 | 0.65 |
| full-vis / eot / K=8 vs comp8 | 0.325 ± 0.022 | 0.47 | 0.33 | 0.65 |
| full-vis / h2 / K=1 vs comp8 | 0.307 ± 0.022 | 0.46 | 0.32 | 0.65 |
| full-vis / h2 / K=8 vs comp8 | 0.463 ± 0.022 | 0.67 | 0.44 | 0.71 |
| masked head / eot / K=1 vs comp8 | 0.277 ± 0.022 | 0.41 | 0.28 | 0.62 |
| masked head / h2 / K=8 vs comp8 | 0.439 ± 0.021 | 0.62 | 0.44 | 0.70 |
| ONE rollout's composite (roll 0) vs rolls 1–7 — cost-matched | 0.471 ± 0.019 | 0.63 | 0.38 | 0.71 |
| label split-half sel(0–3) vs sco(4–7), this sample | 0.531 ± 0.019 | 0.71 | 0.41 | 0.79 |

The subset (cl1, 157 windows) read 0.279 ± 0.044 — the same band; the full read replicates it.
Strata on the headline: certified windows 0.368 (n=150), natural 0.262 (n=500). Chance top-1 at
7.4 scored arms ≈ 0.14. Per-window yield: 6.5 of ~14 arms void (the 32% void-time finding again);
133 windows fall under 3 scored arms.

## Decision

1. **Fork C — HYBRID, adjudicated by the bars.** The label target stays **the pinned h2 composite
   spread from K=8 rollouts** (the label of record for the scorer's spread loss). Critic
   lookahead is **NOT the labeler**: at one turn it carries a third of the ranking (0.30; ≈ 0.37
   after correcting for the label's 0.66 reliability), and the cost-matched alternative — ONE
   two-turn rollout's composite — beats it (0.47) at ~2× the copy cost. Cheap labels, where
   wanted, come from **fewer rollouts, not from the critic: K is the dial** (K=1 → 0.47, K=4 →
   0.53 split-half, K=8 → 0.66 implied), a stratum decision for Build 2's launch pins (Fork D).
2. **The aiming role goes to the learned pivotality read-out, not to critic lookahead.** The
   pre-registered HYBRID text said "critic aims and pre-filters"; measured, the critic's max-arm
   Δ predicts "this window has an arm ≥ θ" at AUC 0.65 zero-shot, while the frozen-trunk
   pivotality probe already reads 0.69 from the state alone (ADR-0096) at zero search cost — and
   under the charter the scorer's own margin IS that read-out. Certifying by critic lookahead
   would spend ~14 copies per window to aim no better than a forward pass. This refines the
   band's text on one measured comparison; the rollouts-as-label half of the band is untouched.
3. **Critic lookahead survives as the deployment-gate candidate only**, and its deployment
   reliability is now measured rather than owed: the policy's **masked value head tracks the
   full-vis critic within 0.02–0.03 at every horizon** (eot K=1 0.28 vs 0.30; h2 K=8 0.44 vs
   0.46), so a server-side one-step lookahead on the masked head buys a ~0.28-ranking, top-1
   0.28 vs 0.14 chance — a weak but real gate. Whether that is worth a copy at serve is the
   ADR-0097-routed question (funded by the network-alone vs lookahead gap at M11's close).
4. **Horizon is the mechanism, not blindness.** At the composite's own horizon averaged over
   rolls the same critic reads 0.46 (ADOPT band) — it agrees with what the composite measures
   once the two turns have played out; after one turn the future is not yet in the state. The
   eot state is near-deterministic across rolls (K=1 ≈ K=8: 0.30 vs 0.33), so a one-step
   lookahead's cost is one copy by construction and cannot be bought down further.

## Consequences

- m11-plan: Fork C marked ADJUDICATED; Build 0 done-when item 1 satisfied; Build 1 proceeds
  unchanged (the spread loss trains on rollout spreads). Fork D's launch pins gain a K-stratum
  question (uniform floor + pivotality-aimed sampling, with K per window as a budget dial).
- The void-arm legality pre-filter (routed to Build 2) is now priced twice: 46% of arms void per
  window and 17% of windows lost below 3 scored arms — it raises label yield AND read power.
- Standing rules born here → standing-rules.md: (a) critic lookahead is not a one-turn labeler,
  K is the cheap-label dial; (b) readers over fork stores stream per window under a memory cap
  (the cl2 read held 96K decoded completions, hit 51.6 GB RSS, and the kernel OOM-killed it and
  the desktop session at 00:03 — recorded in the 2026-09-06 devlog).
- Assets carried: `critic_lookahead_read.py` (lane + streaming read + watchd registration), the
  recording jar `f4824f3d6` (ADR-0025 proof deferred until a jar generates a training store),
  instrument stores `critic-lookahead-cl1-forks` (223 MB) / `cl2-forks` (893 MB) — keep through
  M11, list at the closeout stale-data pass.
- Not changed: ckpt of record, the baseline, the label pins (θ = 2.0, K = 8, h2 composite).
