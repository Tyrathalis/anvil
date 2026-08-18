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

## D1 — the natural-timing probe (the decision gate) — RESOLVED 2026-08-17: gate FAILED ([ADR-0060](../decisions/ADR-0060-d1-natural-timing-probe.md)), pivot taken

**Question:** does *within-natural* timing variation at plan
granularity carry per-point label-grade signal — and is the implied
whole-game headroom above what the gate can resolve? This is the exact
substrate a natural-timing target would train on, and it is NOT yet
measured: ADR-0051 falsified natural-variation labels at single
decisions; ADR-0053 measured plan-granularity signal only under
*forced* directives. D1 closes that gap for a fraction of a campaign's
cost before anything is built.

**Method (amended at the D1 design session, 2026-08-17,
user-approved):** a fresh single-arm campaign at the current era — the
model-active in-band selection (`drill-selection-v5-active`, 99
points), **K=64** NATURAL completions per point (no directive). One
small harness extension rides in-era (labels-only, store formats
untouched; ADR-0025 empirical proof — forkcheck same-hash on the
normal game path — is the boundary-exemption obligation): per NATURAL
completion, record the drilled seat's **first realized spell cast**
(`isSpell()`) SA + absolute game turn — the binning field; lands AND
activated abilities (fetch cracks, equips) are excluded as mana
development, not the spell-timing axis (the smoke caught a fetchland
activation registering as "first cast"), and in-hand lands would
otherwise pull completions into the in-window bin — plus the first
land-play turn (confound check) and the per-completion outcome (the
aggregate `w_nat` can't join bins to wins). An arms-selection
flag runs the NATURAL arm alone (partially retires the queued 2-arm
trim; the act/hold arms were already measured in ADR-0053).
Classification per completion: **primary two-bin contrast = in-window
vs deferred** (first spell on the fork turn vs any later/never); the
fine 4-bin classification (in-window / +1 / +2 / ≥+3-or-never, global
turns — +1 is an opponent-turn instant-speed window) is recorded and
read descriptively to shape D2, but does not gate. Read: within-point
Δwr between the two bins through the standing ADR-0051/0052 variance
decomposition, split abundance measured first. Cost: ~6,300
completions ≈ 2h box time at w=16.

**Why K=64 / two-bin (the ADR-0051 design-time resolvability check,
run at pin time):** within-natural bins are different completions —
no common-random-numbers pairing exists, so the binomial floor is the
full independent one. At the originally proposed K=32 with ≥4/32
bins, the floor variance (~0.06–0.125/point) puts the RMS-0.10 target
(var_signal = 0.01) below 1σ of the variance-estimator's own sampling
noise across ~30 split points — the gate would measure noise in both
directions (false-fail and false-fund). K=64 with the coarse two-bin
contrast (floor ~0.017 at a 24/40 split) resolves the pin at
~1.7–1.9σ on 40–50 split points.

**Pre-registered gate (PINNED 2026-08-17, before any generation):**

1. **Split abundance:** ≥30% of probed points show a non-degenerate
   two-bin split (minority bin ≥12.5% of counted completions, i.e.
   ≥8/64). Degenerate splits ⇒ the policy barely varies its spell
   timing at drilled points — nothing for a natural-timing target to
   grade.
2. **Signal:** RMS true Δwr ≥ 0.10 on the primary two-bin contrast
   over the split-bearing points (the standing label pin), via the
   standing variance decomposition.
3. **Headroom arithmetic:** mismatch fraction (modal natural bin ≠
   argmax-Δwr bin among split-bearing points) × mean |Δwr| ×
   drilled-window play-weight ⇒ implied whole-game effect ≥ ~1pp (the
   gate's resolution). The play-weight derivation (occurrences of
   in-band model-active fork windows per game, from the standing
   selection/screening funnel) is fixed in the D1 ADR before the read.

All three pass ⇒ the formulation is FUNDED (D2). Any fail ⇒ the pivot
branch (D2′), with the failure mode recorded — each clause failing
says something different about where timing credit dies.

## D2 — funded branch: the natural-timing formulation + one run — NOT FUNDED (ADR-0060)

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

## D2′ — pivot branch (TAKEN 2026-08-17, ADR-0060): curriculum × rank-critic curation

The best-evidenced *untried* strength combination on file: curriculum
composition is the only lever that ever produced a promotion (+1.98pp
± 0.71, ADR-0031), one-shot **per curation method** (ADR-0035) — and a
rank-critic-ordered curation is a method that has never run.
(**Premise verified 2026-08-17** against the cycle-3 session record:
run13's ordering/banding came entirely from the K=8 rollout map — the
critic only screened candidacy (calibrated `peak_v ≥ 0.5`) and placed
anchors; its list order was uncorrelated with critic ranking, Spearman
−0.08. Critic-*ordered* is genuinely never-run.)

### Pinned design (audit design session, 2026-08-17, user-approved — pinned before any stock generation or audit labels)

**Method under test:** `rank-critic-c2v3`'s calibrated (era-scoped
isotonic) score replaces the K=8 rollout map's `sel_wr` as the
ordering/band-membership source for selection and quota filling.
Everything the critic already did in cycle-3 — addressability
screening and anchor placement — carries verbatim, so the run
attributes to **ordering, given quotas**. The audit unit is the
**anchor point** (the unit banding actually ranks), through the
standing cycle-3 anchor machinery.

**Stock:** fresh seed base per the `cycle_stock` freshness principle
(honest stock = games the critic has never seen labels from; the
re-baseline stores stay untouched as the gate instrument).
`cycle_stock.py` gets parameterized for M8 (it is hardcoded to
cycle-3: seed base, output paths). Initial pool = **2× cycle-3**:
~3,200 games (~2h at w=16) → ~840 calibrated-addressable candidates
by the measured funnel (cycle-3: 1,600 → 576 raw → 422 calibrated,
~26%). Curriculum size stays ~320 entries — pool scale IS the
selectivity ratio, which is the method's payoff (ranking-for-free
over more candidates than K=8 labeling affords).

**Entry gate (PINNED): Spearman ≥ 0.45** between the critic's
calibrated score and K=8 rollout `sel_wr`, over **N=500
uniformly-random anchor points** from the candidate pool — NOT
band-filtered (the audit measures ordering on the population the
critic would rank; banding on `sel_wr` first would condition on the
labels under test). Reference frame: home-holdout 0.4833 measured
against the same K=8 instrument (attenuation apples-to-apples), blind
floor 0.27, K=8 repeat ceiling 0.94 — the semantics are "fund only if
new-era ordering roughly matches the critic's own holdout; material
degradation ⇒ fallback." Labels bank into the standing calibration
set either way (M5 invariant). Cost: 4,000 rollouts ≈ 1.5h box.

*Resolvability (run at pin time, the ADR-0051 obligation):* Fisher-z
SE = 1/√497 ≈ 0.045 → ±0.036 in ρ near the pin. A materially degraded
ordering (0.35) sits ~2.7σ below the pin; a true-holdout-level
ordering (0.4833) reads below 0.45 ~17% of the time — **accepted**,
because both branches are pre-registered, respectable methods (a
knife-edge read routes to a good branch either way). Distinguishing
0.4833 from 0.45 itself would need N≈2,800 and is not the decision at
stake.

**AMENDMENT (2026-08-17, same session, user-approved — BEFORE any
audit labels existed; the D1 K=32→K=64 precedent): threshold
re-pinned 0.45 → 0.35.** The pipeline smoke ran the audit reader over
cycle-3's own K=8 labels (1,193 anchor points, the full old-era
curation population — effectively the audit with ZERO era transfer)
and measured **Spearman 0.377**. The 0.4833 reference was the
critic's holdout on its *training-label population*; on the
*curation-anchor population* the critic reads 0.377 even in-era — so
the 0.45 pin conflated two degradations: population-type (now
measured, 0.483→0.377 in-era) and era transfer (unknown, the
chartered question). Under 0.45 the gate's outcome was nearly
foregone and carried no transfer information. Re-referenced
semantics: **fund if ordering survives the era boundary within noise
of its measured in-era, same-population benchmark (0.377)**; fail =
genuine era degradation ⇒ fallback. Recorded caveat: 0.377 vs 0.35
is ~0.6σ at N=500 — a transfer-intact ordering still reads below the
pin ~25% of the time; accepted on the same both-branches-respectable
argument. The cycle-3 validation read (0.3772, curve 1× 0.623 → 4×
0.646, no winner's-curse signature) is the amendment's evidence and
lives in the 7f9f5ca smoke artifacts.

*Descriptive reads (never gating):* per-bin ordering quality
(winnable/coin/long_shot/lost Spearman + top-slice enrichment — the
ADR-0036 winnable-blindness check, recorded for future composition
work); realized band/bin distribution of the selected ~320 vs
cycle-3's (ordering shifts content even under fixed quotas — the
attribution caveat, logged for the closeout ADR).

**Pool-scale rule (PINNED — responsive by pre-registered rule, no
auto-scaling machinery):** on the audit labels, simulate
quota-filling selection at effective pool scales {1×, 2×, 4×, 8×}
(selection fractions ≈76/38/19/9.5% of candidates; ~379/190/95/47
labeled points per slice). Primary metric: **true-in-band precision**
— fraction of critic-selected entries whose rollout wr ∈ [0.25, 0.85]
(K=8 binomial spillover hits all scales equally; the relative read is
unbiased). Rule: final pool scale = the largest simulated scale whose
precision is within 5pp of the 1× read, **capped at 4×** (the 8×
slice is ~47 points — indicative only, recorded to shape future
cycles, never funding this one; the 4× read resolves at ~1σ against
the 5pp margin — the cap bounds the damage). If the rule says >2×,
ONE pre-authorized top-up generation before curation; top-up
candidates are critic-ranked **without additional labels** — that is
the method. The rule keys only on rollout-labeled quantities, never
critic scores (no self-grading — the winner's-curse check cannot be
run on the instrument being audited).

**Composition (PINNED):** the promoted a2 quotas verbatim (ADR-0031:
18.8% ahead rebalance, band 0.25–0.85), critic-ordered within bands.
Cycle-3's D3-composition winnable-20% quota is NOT reused: it never
promoted, and ADR-0036's winnable −0.56 residual says the critic is
most blind exactly there — winnable-weighting × critic-ordering would
concentrate curriculum mass where the ordering instrument is least
trustworthy. Winnable-weighting remains the fallback branch's method
and a recorded future lever if this cycle's decomposition reopens it.

**Fallback branch (audit < 0.45):** corrected-map-anchored
composition against the winnable residual — the N=500 audit labels
ARE a uniform rollout map of the pool; compose from the labeled
points (still a never-run method: the corrected maps postdate run11's
curation entirely). Same run, same gate.

**Order of operations:** (1) **pipeline smoke** — the critic-ordering
path end-to-end (trace → rank → calibrated band membership → compose)
on existing cycle-3 candidates, wiring check only, BEFORE any
generation (the jstr lesson: instrument bugs surface on first
contact); (2) `cycle_stock`-M8 generation at 2×; (3) audit labels
(N=500, K=8); (4) gate read + selectivity curve → pool-scale decision
(top-up iff the pinned rule says so); (5) curation, funded or
fallback method; (6) **migration read** (standing gatekeeper) before
pricing; (7) the run — run11 recipe verbatim, init `iter-019`,
in-loop critic unchanged, M7's recipe-neutral machinery riding (loud
seqlabels drops, guard set). Close = the standing 2,000-game combined
paired read vs **0.5373 ± 0.0112** + evalset-v4 decomposition +
battery.

**Recipe interpretation recorded at launch (2026-08-18,
user-decided): "verbatim" binds the recipe's STRUCTURE for
comparability, not superseded components** — the §6c penalty runs at
the standing corrected pricing (0.01 / per-window grouping, ADR-0054),
not run13's 0.02/per-event, which the driver retains for era
reproduction only and whose veto-elevation cost (0.215) ADR-0048
documented. Delta vs run13 is therefore curation + pricing; the gate
of record (vs the baseline) is unaffected. Launch command of record:
`scripts/launch_d6_run17.sh` (run13 `loop_config` otherwise verbatim;
fresh seed base 20260821; evalset-v4 drill-eval every 5 riding as
recipe-neutral instrumentation).

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
