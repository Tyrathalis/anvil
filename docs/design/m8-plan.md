# M8 — one lever to a promotion attempt: natural-timing credit, probe-gated, with a pre-registered pivot

**Opened:** 2026-08-17 (user-approved shape, this session).
**Anchors:** [ADR-0058](../decisions/ADR-0058-m7-closeout.md) (M7 closeout
+ the chartered follow-up); [ADR-0053](../decisions/ADR-0053-sequence-probe-resolution.md)
(the funding probe: plan-granularity signal, timing ordering natural >
greedy ≫ hold); [ADR-0051](../decisions/ADR-0051-p0-decision-delta-probe.md)/[ADR-0052](../decisions/ADR-0052-ksizing-read-map-serving-mismatch.md)
(the falsified single-decision instruments + the variance decomposition
every probe reads through); [ADR-0031](../decisions/ADR-0031-a2-resolution.md)/[ADR-0035](../decisions/ADR-0035-d2-compounding-read-resolution.md)
(the curriculum lever and its one-shot-per-method verdict);
[ADR-0036](../decisions/ADR-0036-d3-critic-calibration.md) (critic
ranking blindness + the extrapolation caution); [m7-plan.md](m7-plan.md)
(the pattern this doc follows).

## The question

M7 ended in a split verdict: dense plan-granularity credit is trainable
and behavior-moving, but the act−hold target taught greedy timing —
which ADR-0053 had already measured below natural. M8 asks: **does
plan-granularity credit aimed at the measured timing optimum move
strength — and if a cheap probe says the trainable signal isn't there,
which strength lever gets the run instead?** The pivot is
pre-registered (below), so M8 ends with a promotion attempt against the
standing gate either way — not a fourth consecutive diagnosis
milestone.

**Strategic pre-commitment (user-approved 2026-08-17):** if the
timing-target branch runs and TIES at the gate, the M8 closeout ADR
records the credit-assignment lever family CLOSED at this scale — no
further formulation rounds; the next milestone starts from a different
family (curriculum/curation, planning §3a, or content growth at the
next boundary).

**Rebase assessed and declined at open (2026-08-17):** upstream delta
since era `d798917ae5` = 80 commits over 6 days; 45 changed card
scripts with ZERO pool intersection; 7 engine-path commits, none on our
game path (the AI X-sizing fix targets two cards not in the pool; the
LandMana LKI cache is a perf refactor we don't need). A boundary would
cost forkcheck + a 2,000-game re-baseline for nothing, and would break
direct comparability between M7's verdict and M8's first read. The
**next-boundary bundle** is recorded on the map watch list: upstream
rebase + multi-format learning enablement (model-side — the pool
scaffold landed as fork #8 at the ADR-0055 boundary) + the 2-arm
campaign trim + copy-state divergence forensics (ADR-0055 annex).

**Carried-items audit (2026-08-17):** the M4-era "carried fork items"
are ALL resolved — they landed in the ADR-0055 D3 boundary: MayPlay
`.get(0)` = GameCopier effect-source restore (`b361dfcb8f`), IndexOOB
class = STATION tap-guard (`9f0a2c0886`), MinMaxBlocker fixed 07-25,
targeting-retry closed-as-bounded with its reopen trigger armed.
Nothing carries into M8 from M3/M4.

## D1 — the natural-timing probe (the decision gate)

**Question:** does *within-natural* timing variation at plan
granularity carry per-point label-grade signal — and is the implied
whole-game headroom above what the gate can resolve? This is the exact
substrate a natural-timing target would train on, and it is NOT yet
measured: ADR-0051 falsified natural-variation labels at single
decisions; ADR-0053 measured plan-granularity signal only under
*forced* directives. D1 closes that gap for a fraction of a campaign's
cost before anything is built.

**Method:** a fresh single-arm campaign at the current era — the
model-active in-band selection (`drill-selection-v5-active`, 99
points), K=32 NATURAL completions per point (no directive), N=4
horizon. One small harness extension rides in-era (labels-only, store
formats untouched): record the drilled seat's first realized cast SA +
turn offset per NATURAL completion — the natural-arm sibling of the
act-arm field `6a63ec2997` already records. Classification per
completion: first-cast timing bin (in-window / +1 turn / +2 / ≥+3 or
never). Read: within-point Δwr between populated timing bins through
the standing ADR-0051/0052 variance decomposition, split abundance
measured first. Cost: ~3,200 completions ≈ half a forced-seq campaign
phase (~1h box time at w=16) + the extension.

**Pre-registered gate (numbers PROPOSED here; PIN at the D1 design
session, before any generation runs):**

1. **Split abundance:** ≥30% of points show a non-degenerate timing
   split (≥2 bins with ≥4/32 completions each). Degenerate splits ⇒
   the policy barely varies its timing at drilled points — nothing for
   a natural-timing target to grade.
2. **Signal:** RMS true Δwr ≥ 0.10 between leading bins on the
   split-bearing points (the standing label pin).
3. **Headroom arithmetic** (the ADR-0051 standing rule — check the
   threshold against estimator resolvability at design time): mismatch
   fraction (modal natural timing ≠ argmax-Δwr bin) × mean |Δwr| ×
   drilled-window play-weight ⇒ implied whole-game effect ≥ ~1pp (the
   gate's resolution).

All three pass ⇒ the formulation is FUNDED (D2). Any fail ⇒ the pivot
branch (D2′), with the failure mode recorded — each clause failing
says something different about where timing credit dies.

## D2 — funded branch: the natural-timing formulation + one run

A design round pins the loss form: a timing-bin advantage at the marked
mainline fork window that rewards the argmax bin — **including holding
where holding wins** (the anti-greedy correction ADR-0058's verdict
demands; act−hold rewarded casting unconditionally). Every standing
rule applies from birth: clips/hinge at birth (ADR-0056),
auto-calibrated weights instrumented + guarded + recalibrated at the
drift cadence (ADR-0057), share guard + kl abort armed, fixed-subset
arms reads counted once (ADR-0058). Machinery carries verbatim from
M7: seqlabels join, campaign phase, battery seq curves, screened
selection + evalset v4. Close = one training run vs the standing gate
**0.5373 ± 0.0112** (2,000-game combined paired read + evalset
decomposition + battery attribution: did per-point timing agreement
with the argmax bin rise, and did hold-then-cast move toward the
natural optimum rather than away?).

## D2′ — pivot branch (pre-registered): curriculum × rank-critic curation

The best-evidenced *untried* strength combination on file: curriculum
composition is the only lever that ever produced a promotion (+1.98pp
± 0.71, ADR-0031), one-shot **per curation method** (ADR-0035) — and a
rank-critic-ordered curation is a method that has never run.

**Entry gate (pinned at its own design session):** a rollout audit of
`rank-critic-c2v3` ordering on the target curation population — the
ADR-0036 caution stands (trained on loss-adjacent c2 labels; its
ordering elsewhere is extrapolation until audited). Spearman vs
K-rollout truth above a pinned threshold funds critic-ordered
curation; below it, fall back to corrected-map-anchored composition
against the winnable residual (still a new method — the corrected maps
postdate run11's curation entirely). Audit labels bank into the
standing calibration set either way (the M5 invariant). Close = the
same standing gate, same read.

## D3 — riders (conditional, never blocking)

- **Throughput items** unpark only if D1/D2 campaign economics demand
  (single-arm K=32 is cheaper than M7's two-arm campaigns, so likely
  not).
- **Battery `--compare <run>` overlay** (~30 lines, convenience list):
  ride at first natural opportunity — M7 hand-rolled cross-run curve
  comparison three times.
- Trackio stays on watch (not started).

## Explicitly out of M8

- Rebase (assessed at open, above); pool/content growth; multi-format
  enablement — all next-boundary bundle.
- Act−hold dose escalation (ADR-0058: not recommended).
- Encoder/representation work (M6 verdict stands).
- Planning §3a / conscious mana payment: still the rising-priority
  queue (ADR-0042), untouched by this milestone's outcome unless the
  closeout ADR routes there.

## Done-when

1. D1 resolved against the pre-registered gate, either direction, with
   an ADR.
2. One training run on the selected branch (D2 or D2′), closed by the
   standing 2,000-game combined paired read vs 0.5373 ± 0.0112.
3. The M8 closeout ADR records the verdict — including, on a
   timing-branch tie, the pre-committed credit-assignment-family
   closure.
4. The next-boundary bundle is recorded on the map watch list (done at
   open).
