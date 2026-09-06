# ADR-0099: M11 Build 1 — the option scorer on certifier spreads is KILLED by the pre-registered curve (0.158 at N=607, 0.204 at full N, rising but under the 0.30 bar); the trunk's gradient buys +0.02 over frozen; a length prior explains most of it

- **Date:** 2026-09-06
- **Status:** ACCEPTED (addendum below: routes R1 and R2 read negative the same day; R3 / R5 remain, the user adjudicates)
  (options below)
- **Design-doc anchor:** m11-plan.md Build 1 + done-when 2; ADR-0097 (single network, spread
  loss on certified windows); ADR-0096 (the frozen probe at 0.08); ADR-0098 (the one-turn
  critic at 0.30)

## Context

Build 1 asked whether the option scorer — the charter's single head, q([STATE]) · pool(arm keys),
on a TRAINABLE trunk — can rank the certifier's schedule arms the way the search ranks them, fitted
on every spread the project owns (harvest h1 + the mint recomputed from its lane rows: 3,655
windows, 37,257 (window, arm) pairs, 789 game-hash holdout windows). Bands pre-registered
2026-09-06 (m11-plan Build 1): at the frozen probe's N=607, ≤ 0.15 KILL / > 0.30 PASS / between →
the 25/50/100% curve decides (rising AND > 0.30 at full N passes, else KILL); pivotality AUC ≥ 0.70
alongside. Recipe as adjudicated: init `m10-sched-init` with option keys and query copied from
the executor's pointer; full fine-tune (trunk 1e-5, heads 1e-3) vs a frozen-trunk twin; pairwise
ranking hinge + 0.05 MSE anchor on the 8-roll composite; early stop on holdout Spearman; 3 seeds.

## The read (`data/training/m11-scorer-b1`, holdout 780 windows with ≥ 3 arms)

| n_train | mode | Spearman (3 seeds) | top-1 | piv. AUC | harvest / mint | certified / natural |
|---|---|---|---|---|---|---|
| 607 | full | **0.158** (0.14, 0.18, 0.16) | 0.16 | 0.53 | 0.09 / 0.16 | 0.20 / 0.13 |
| 607 | frozen | 0.150 | 0.16 | 0.55 | 0.14 / 0.16 | 0.16 / 0.15 |
| 716 (25%) | full | 0.149 | 0.15 | 0.54 | 0.14 / 0.15 | 0.24 / 0.13 |
| 1433 (50%) | full | 0.188 | 0.16 | 0.53 | 0.17 / 0.20 | 0.21 / 0.19 |
| 2866 (100%) | full | **0.204** (0.20, 0.21, 0.21) | 0.18 | 0.57 | 0.12 / 0.22 | 0.20 / 0.20 |
| 2866 (100%) | frozen | 0.183 | 0.16 | 0.53 | 0.15 / 0.20 | 0.20 / 0.18 |

References on the same holdout: the untrained init (the executor's own preference pooled over the
arm) −0.06; **arm LENGTH alone 0.148**; the frozen probe 0.08 (harvest-only, N=607); the one-turn
critic lookahead 0.30 zero-shot (ADR-0098); the label's own split-half 0.53; chance top-1 ≈ 0.10.
Fits peak at epochs 0–6 and overfit within 5–11 epochs (train loss 1.2–1.5 at the peak); SE per
point ≈ 0.016.

**Verdict: KILL by the curve** (607: 0.158 — between the bands; full N: 0.204, rising, under 0.30).
The trunk's gradient buys +0.02 over frozen at every N. The slope is ≈ +0.03 per doubling of
windows: the 0.30 bar extrapolates to ~16× the data (~50K spread-labeled windows ≈ 400+ lane-hours
at today's yield) — not fundable, and even then a tenth of the way to the 0.66 ceiling. The
pivotality read-out from the fitted scores (0.53–0.57) is BELOW the frozen-trunk state-level
classifier (0.69, ADR-0096): the head's max-arm score is not the pivotality read-out the charter
assumed.

## What the KILL says (and does not say)

- It closes **"learn the certifier's arm ranking from spread labels at harvest scale"** — the
  third negative on the same target after the exact-arm head (0% at 4×) and the frozen probe
  (0.08): now with the trunk trainable, with 4.5× the windows, and with the executor's own keys
  as the start. Most of what any fit recovers is a length prior; the rest is +0.05.
- It does NOT close the charter's mechanism at single-option surfaces (a payment class, a cast,
  a target): every negative so far is on COMPOSITE options (schedule arms) whose content is a
  sequence the executor plays out. ADR-0075's payment labels (5,076 windows, a measured +2.96pp
  ceiling as a supervised conditional competency) are the untested single-option case.
- It does NOT close one-step lookahead as a SIGNAL: the critic at one ply ranks the spread at
  0.30 with no fitting (ADR-0098) — better than anything learned here — and is dense (every
  window, ~14 copies of one turn) where spreads are sparse (one in five windows, 8 rolls × 2
  turns × 14 arms).

## Routes (the user's adjudication; lean marked)

- **R1 — LEAN: distill one-step lookahead (expert iteration at one ply).** The label source for
  the scorer's spread loss becomes the full-vis critic's one-step Δ (dense, cheap); rollout
  spreads stay the certification and ceiling instrument. First read on existing data (~1 h):
  fit the same head on the 800 harvest windows' critic-eot targets (`critic-lookahead-cl2`) and
  read holdout Spearman vs the critic targets (learnability) AND vs the spreads (does a critic-
  distilled scorer inherit the critic's 0.30). Pre-register: learnability ≥ 0.5 vs critic targets
  and ≥ 0.25 vs spreads at N≈600 to fund a lookahead-labeling lane at scale.
- **R2 — test the mechanism on the single-option surface: payment classes** (ADR-0075's
  labeled universe as per-option spreads, `payment_certify.py` as the certifier). Same head,
  same fit script, the 2b surface pulled forward. Cheap (data exists; format to verify). If the
  scorer ranks payment options well above chance, the KILL is surface-specific (composite
  options) and the charter narrows to single-option surfaces.
- **R3 — server-side lookahead as the acting rule, no learning**: at serve, plan-type options
  scored by copy + evaluate with the masked head (0.28), margin-gated; read = paired strength
  at day zero. Abandons amortization; what ADR-0097 routed to the end.
- **R4 — more spread data** (void pre-filter + K=1 spreads at 1/8 cost): the slope says 16×;
  rejected unless the economics change by an order of magnitude.
- **R5 — close M11 negative on the mechanism** and re-scope at a scoping session.

R1 and R2 are both ≤ 1 day and answer different halves of the question (is a dense cheap label
learnable; is the head fine on single options); the lean is to run BOTH before any re-charter.

## Consequences (on acceptance)

- m11-plan done-when 2 → KILLED; Builds 2–4 as chartered are suspended pending the route.
- Standing-rule candidate: composite-option quality (schedule arms) is not learnable from
  spread labels at harvest scale under any of three head shapes; any future plan-type surface
  must show a within-window Spearman above a length prior before a training run funds it.
- Assets: `option_scorer_fit.py` (build/fit/report), `AnvilNet.score_options`, the 3,655-window
  spread corpus (`m11-scorer-b1/windows.pt`, 44 MB), best-full / best-frozen ckpts (instrument
  only; 276 MB each — kill-list candidates at the route decision).

## Addendum (2026-09-06, same day): routes R1 and R2 READ — both negative; status → ACCEPTED as the mechanism's kill

**R1 — distill one-step lookahead.** The same head fitted on the 655 harvest windows that carry
cl2's critic targets (502 train / 153 holdout; targets = the full-vis critic's eot Δ, K=1 and K=8):

| target | n_train | full | frozen | vs spread (full) |
|---|---|---|---|---|
| critic eot K=1 | 251 | 0.199 | 0.181 | 0.11 |
| critic eot K=1 | 502 | 0.160 (0.25 / 0.15 / 0.08) | 0.147 | 0.06 |
| critic eot K=8 | 251 | 0.221 | 0.229 | 0.08 |
| critic eot K=8 | 502 | 0.165 (0.17 / 0.25 / 0.08) | 0.193 | 0.03 |

Pre-registered: learnability ≥ 0.5 vs the critic targets AND ≥ 0.25 vs spreads → fund a lane.
**KILL**: the critic's one-ply ranking is no more learnable from (state, option) than the
rollout spread is — seed variance ±0.08, no rise with N. The critic's 0.30 lives in the
post-action state, which the head never sees.

**R2 — the single-option surface (payment classes).** 276 observed drill windows (evalset v2 +
the 13 retired phyrexian positives; 1,258 options; 64 positive), the pointer logits as scores
(option 0 = auto = 0), three game-hash splits × 2 seeds, N ≈ 205 train / 70 holdout:

| split | full (2 seeds) | frozen (2 seeds) | top-1 | full: auto-correct stratum | full: POSITIVE stratum |
|---|---|---|---|---|---|
| 0 | 0.360, 0.368 | 0.360, 0.384 | 0.58–0.65 | 0.53, 0.51 | −0.35, −0.23 |
| 1 | 0.290, 0.242 | 0.271, 0.257 | 0.47–0.51 | 0.33, 0.36 | 0.18, −0.06 |
| 2 | 0.230, 0.231 | 0.180, 0.237 | 0.46–0.50 | 0.37, 0.40 | −0.04, −0.10 |
| mean | **0.287** | 0.282 | | 0.42 | **−0.10** |

Pre-registered (same bands as arms, N ≈ 200): PASS > 0.30 / KILL ≤ 0.15 / between → fund a
ratesweep-observe lane. The mean lands BETWEEN — but the stratum split says what the 0.29 is:
on auto-correct windows (81% of the corpus) the head learns that every option is worse than
auto (the sign of the margin, a base rate); on the POSITIVE windows — the only ones where a
choice carries the +2.96pp ceiling — it ranks at −0.10 (12 seed×split reads, 10 ≤ 0, at ~16
holdout positives each). The trunk's gradient adds nothing (0.287 vs 0.282). **Funding more N on
the strength of the between-band mean would be funding the base rate; the positive stratum is
the read, and it is null.** (Caveat recorded: 64 positives is a small universe; the ADR-0075
class-CE competency was measured as memorization of these same windows, ADR-0088.)

**Status → ACCEPTED as the mechanism's kill.** Three surfaces of the option scorer read at or
below a prior: schedule arms (length prior +0.05), critic-distilled arms (no learnability), and
single-option payment classes (sign prior on auto-correct; null on positives). The
representation does not expose within-window option quality from the pre-action state at the
data scales any certifier of ours produces.

Remaining routes: **R3** (serve-side one-ply lookahead with the masked head as the acting rule,
margin-gated; a bounded day-zero paired read, ~1 day; abandons amortization) and **R5** (close
M11 negative; scoping session). Lean: R5, with R3 as the only bounded read left in the family.

Assets from the route reads (instrument only; kill-list candidates at the closeout pass):
`m11-scorer-r1-k1/`, `m11-scorer-r1-k8/`, `m11-scorer-r2-pay/` (~2.2 GB of best-*.pt ckpts;
the corpora are small). `option_scorer_fit.py` gains `--targets`, `build-pay`, `--hold-salt`.
