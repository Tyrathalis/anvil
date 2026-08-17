# ADR-0060: M8 D1 resolved — the natural-timing probe FAILS its gate; within-natural timing variation does not exist at plan granularity; the pre-registered pivot (D2′ curriculum × rank-critic curation) is taken

- **Date:** 2026-08-17
- **Status:** accepted
- **Design-doc anchor:** m8-plan D1 (gate pinned at the design session,
  before generation) → D2′; ADR-0051 (natural variation falsified at
  single decisions), ADR-0053 (plan-granularity signal under FORCED
  directives), ADR-0058 (the chartered follow-up this probe gates),
  ADR-0059 (the boundary-exemption proof + instrument corrections)

## Context

M7 closed on a split verdict: dense plan-granularity credit is
trainable and behavior-moving, but the act−hold target taught greedy
timing — below the natural optimum ADR-0053 measured. The chartered
follow-up was a natural-timing-target formulation, gated on the one
substrate never measured: does *within-natural* timing variation at
plan granularity carry per-point label-grade signal? ADR-0051 killed
natural-variation labels at single decisions; ADR-0053 measured
plan signal only under forced directives. D1 closed that gap before
anything was built.

**Instrument:** single NATURAL arm under the new OBSERVE directive
(fork `b2d7ca2ec2` + jstr fix `fe11f57a28`; records, never forces),
K=64 completions per point on `drill-selection-v5-active` (99
model-active in-band points, the exact campaign substrate a D2 target
would train on), fork-instrument sampled serving by the ckpt of record
(`d6-run11/iter-019`), argmax mainline replay — the M7 campaign
invocation verbatim. Labels: per-completion first realized SPELL cast
(`isSpell()`; lands and activated abilities excluded as mana
development — the smoke caught a fetchland crack registering as "first
cast") + absolute turn, first land turn, outcome. Boundary-exemption
proof and the two instrument corrections found en route: ADR-0059.
Reader: `scripts/natural_timing_read.py`.

**Gate (PINNED 2026-08-17 at the design session, before any
generation; K=32→K=64 + two-bin amendments recorded in m8-plan with
the ADR-0051 resolvability arithmetic):**

1. split abundance ≥30% of probed points (minority bin ≥12.5% of
   counted completions, two-bin: in-window vs deferred);
2. RMS true Δwr ≥ 0.10 on the two-bin contrast over split points;
3. mismatch × mean |Δwr| × play-weight ≥ ~1pp. Play-weight derivation
   (fixed before the read): active in-band drilled windows per source
   game = 99/2,000 = 0.0495.

## What was measured

Coverage pristine: 99/99 points fired (zero seat-skips — the screening
held), 6,335/6,336 completions (1 crash), zero directive anomalies,
zero unparseable rows (the jstr fix at K=64 scale).

| clause | pin | measured | verdict |
| --- | --- | --- | --- |
| 1 — split abundance | ≥30% | **3/99 = 3.0%** | **FAIL** |
| 2 — RMS true Δwr (split points) | ≥0.10 | 0.348 (on 3 points: mean +0.174, 2 pos / 1 neg) | nominal pass, no weight at n=3 |
| 3 — implied whole-game headroom | ≥~1pp | **0.55pp** (naive) / 0.57pp (rms-true) | **FAIL** |

Descriptive (never gating): pooled first-spell timing is heavily
in-window — 71.8% in-window, 6.2% +1 (opponent turn), 13.6% +2, 8.4%
≥+3-or-never. Pooled winrates decline with deferral (0.586 / 0.605 /
0.520 / 0.417) — direction consistent with ADR-0053's hold costs, but
confounded (late first casts correlate with losing positions) and
unusable as a training substrate at this abundance. Modal first casts
are frequently *deterministic across all 64 sampled completions* of a
point (several spells appear exactly 64×#points times). 96% of
completions played a land (70% in-window) — the isSpell exclusion was
load-bearing.

## Decision

1. **The gate FAILS on clause 1, decisively (3.0% vs 30%), with
   clause 3 also failing.** The pre-registered reading of a clause-1
   failure stands as written in m8-plan: the policy barely varies its
   spell timing at drilled points — **there is nothing for a
   natural-timing target to grade.** The natural-timing formulation is
   NOT funded; no D2 design round.
2. **Failure mode recorded:** within-natural timing variation is
   absent at plan granularity under sampled serving — this extends
   ADR-0051's natural-variation falsification from single decisions to
   N-turn plans. The full picture across the family: natural variation
   carries no signal at any granularity (0051, this ADR); forced
   contrasts carry label-grade plan signal (0053) but the one forced
   formulation tried taught the wrong timing and was strength-neutral
   at the gate (0058).
3. **The pre-registered pivot is taken: D2′ — curriculum ×
   rank-critic curation** (the only lever family that ever promoted,
   +1.98pp ADR-0031; one-shot per method ADR-0035; critic-ordered is a
   never-run method). Entry gate per m8-plan: a rollout audit of
   `rank-critic-c2v3` ordering on the target curation population,
   threshold pinned at its own design session (ADR-0036 extrapolation
   caution); fallback = corrected-map-anchored composition against the
   winnable residual. Audit labels bank into the standing calibration
   set (the M5 invariant).
4. The m8-plan family-closure pre-commitment (a timing-branch TIE at
   the strength gate closes the credit-assignment family) does not
   fire — no timing run happened. The M8 closeout ADR should weigh
   this probe's result when the family's status is recorded: every
   angle measured to date is now either substrate-absent (natural, any
   granularity) or formulation-falsified (act−hold), with forced-plan
   signal (0053) the one live measurement a future formulation would
   have to build on.

## Consequences

- M8 proceeds on D2′: next session = the audit design round (pin the
  Spearman-vs-rollout-truth threshold before generating audit labels),
  then critic-ordered (or fallback) curation → one run vs
  **0.5373 ± 0.0112**.
- The probe instrument (OBSERVE mode + per-completion timing labels) is
  a standing asset: it is the cheap "does the policy vary here at all"
  screen for any future behavioral-variation question, and the
  single-arm flag halves campaign cost wherever forced arms aren't
  needed.
- Probe stores: labels-only run dirs
  (`drillm8d1nat-*-130633`/`-140654`, ~9M total) keep with the run
  dirs of record; the three K=2 smoke dirs (~200K) are stale-data
  candidates at M8 close, and `data/forkcheck/m8d1-proof` (183M — mostly
  the three preserved jars) prunes to results+meta after the next
  boundary's forkcheck supersedes it.
- Cost postscript: the probe ran ~2h box time as priced (6,336
  completions at K=64) plus one aborted launch (jstr bug, ~30 min) —
  the design-session resolvability check that forced K=64 is what made
  the clause-1 verdict this clean (8/64 minority floor instead of
  4/32).
