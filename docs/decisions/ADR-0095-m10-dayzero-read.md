# ADR-0095: M10 reset day-zero read — binding execution of the distilled planner is WORTH −6.7pp on the behind stratum (HALT for adjudication)

- **Date:** 2026-09-03
- **Status:** accepted — measurement complete (verdict mechanical from
  the ADR-0094 Fork 4/5 rules); **ADJUDICATED 2026-09-03 (user): route 1
  — train the planner on the existing model's strategy before any
  binding regime.** Session two (the learner side) waits on a planner
  that matches the executor as written at the windows it binds, gated
  by a re-run of this read on the same population.
- **Design-doc anchor:** m10-reset-draft.md §D4 (the read), §D5 (the
  staged budget + mid-point rule), §H (build status); ADR-0094

## Question

Before any training, does BINDING execution of the distilled planner
(probe6 iter-5's emitter, mint CE 1.24 on the 08-30 full-support
labels) make the policy stronger than the same checkpoint played
ADVISORY (slot tokens fed, the cast head free), on the funded v<0.45
stratum where the ADR-0078 ceiling said the value lives?

## How it was measured (pinned pre-data; m10-reset-draft §H)

Population: 600 own-turn MAIN1 windows at v<0.45 (`d4-critic-fullvis`)
+ 200 context windows at v≥0.45, drawn once (`PAIRED_RNG_SEED`) from
the ADR-0078 ceiling census (4,084 eligible turn-groups; user decision
to reuse the census). Instrument: the sched-rollout mode with
natural-only fork points, K=8 completions per window per side, rollSeeds
keyed on the target turn (common random numbers across sides); side A =
the candidate under `--sched-binding forks` (the fork's opening seat
binds, opponent advisory), side B = the candidate advisory; both sides
replay the mainline from the census's generating ckpt (`d6-run11/
iter-019`) and serve completions from probe6 iter-5 (the M4 D2.4
dual-policy path). Estimator: per-window paired Δwr over valid rolls,
mean over windows, SE = SD/√N. Bar (`PAIRED_BAR`): ±0.022 — the
ADR-0078 threshold scale read per window. Run:
`data/runs/sched-paired-dayzero-probe6i5-20260903-122840`, 4.25 h on
12 lanes, zero lane failures, zero server fallbacks on either side.

## Results

| stratum | windows | Δwr (A − B) | SE | 95% CI | z | wr A | wr B |
|---|---|---|---|---|---|---|---|
| **primary v<0.45** | **553** | **−0.0672** | 0.0089 | [−0.0845, −0.0498] | **−7.59** | 0.165 | 0.232 |
| context v≥0.45 | 183 | −0.1257 | 0.0166 | [−0.158, −0.093] | −7.57 | 0.648 | 0.773 |

- **Verdict: HALT** (mean ≤ −bar by 3×). Monotone in the critic's
  value: −4.0pp at v<0.1, −6.1 at 0.1–0.2, −7.7 at 0.2–0.3, −9.4 at
  0.3–0.45, −12.6 on the context stratum — the more winnable the state,
  the more binding costs. 186 primary windows worse, 68 better, 299
  tied (46% moved); 33 windows at Δwr ≤ −0.5 vs 7 at ≥ +0.5. Game
  length unchanged (t_end 23.0 vs 22.8).
- **The instrument works as designed.** Empirical per-window paired SE
  0.094 vs the K=8 binomial floor 0.200 — CRN pairing halves the noise;
  read SE 0.9pp at N=553, so the 2.2pp bar sits at ~2.5 SE for the
  terminal read at this K (pin for probe7: **K=8, N=600 stands**; the
  reset's "≈ an hour" is 4.25 h at 6 lanes/side, balanced lanes now).
  Residue: 47 primary + 17 context windows never fired (mainline ended
  before the target turn — the ceiling's 2.7% class, here 8%: the
  population is deep-behind states that end early), 5 skip rows per
  side (three games' mainline replays diverged from the census before
  the target turn: `seat_mismatch`, symmetric, dropped), crash rows
  0.6% (the copy+resume class, pairs dropped).
- **Serve telemetry on the bound seat (5,949 completions, 443,491
  bound windows): HOLD 71.2% / forced CAST 24.5% / LAND 4.3%.** Of
  426,566 emissions, 53.3% were EMPTY; 59% of emissions were trigger-2
  (opponent action) revisions, 12.7% exhaust, 11.8% end-step, 1.9%
  absent-slot; 51% of revisions were no-ops. Emitted lengths 0/1/2/3/4+
  = 53/24/14/6/3%.

## The mechanism (read on the smoke store + probe6's own generation)

Trigger 2 fires ~3.4× per own turn (any opponent action during our
turn — blocks, triggers, responses), and the planner's re-decode from
those mid-turn states comes back EMPTY 59% of the time (73% in probe6's
advisory generation — the same planner). Under advisory an empty
revision cost nothing; **under binding an empty revision is a HOLD on
every castable spell for the rest of the turn.** In the 4-game binding
smoke, 549 of 784 hold windows sat under an empty plan with a castable
spell in hand. This is exactly the cost Fork 1 recorded and priced as a
label-extension item ("revision windows are the least-supervised
decodes") — the day-zero read says it is not a cost item but the
dominant term: the mint labels the MAIN1 emission window only, so at
every mid-turn state the emitter has never seen, empty is its min-CE
hedge, and binding turns the hedge into purposeful passing the planner
never chose.

## Routes for the adjudication (user's call; none taken yet)

1. **An empty REVISION binds nothing.** Built behind
   `--sched-empty-rev noop` (an empty re-decode with slots still pending
   keeps the remaining plan; the first-window emission and the end-step
   stay as pinned). Keeps binding for what the planner DID decide;
   removes the hedge-to-hold conversion. Measurable in ~45 min on 100
   windows with the bind trace (`run --limit 100 --empty-rev noop
   --bind-trace`).
2. **Label revision windows before binding them** (the Fork 3 named
   certifier extension) — the principled fix, but it is session-two work
   plus a mint, and the day-zero read cannot be re-run until then.
3. **Narrow trigger 2** to state-changing opponent actions (a counter
   or removal resolving; not blocks/triggers) — fewer unlabeled
   re-decodes; the missed-trigger residual grows.
4. Keep the pin and read (1) as telemetry only — the reset's "a hold IS
   a decision" applied to revisions the planner was never taught.

The day-zero decomposition did its job: the number is a distillation +
execution-rule finding, not a training finding — session two's planner
PG would train on top of a −6.7pp execution regime.

## Consequences

- Session two does NOT start on the pinned recipe; the adjudication
  picks a route, and a re-run of the day-zero read on that route is the
  gate for building the learner side.
- Standing (candidate, pending adjudication): **a binding execution
  rule may only bind decodes the labels cover** — a decode at an
  unlabeled state binds nothing until labeled.
- Instruments born: `sched_paired_read.py` (the primary read, proven at
  N=553 with CRN halving the noise), the server bind trace, the
  empty-revision flag.

## Addendum — route 1 measured (2026-09-03 17:35): FALSIFIED

`--sched-empty-rev noop` vs the day-zero binding side on the same 56
primary windows and rolls: **Δwr +0.0000 ± 0.0096** (context −0.021 ±
0.020); control null across runs +0.011 ± 0.014. The bind trace on the
candidate seat: 90% of holds have NO slots left — the post-exhaustion
re-decode replaces a finished 1–2-slot plan with empty, and that empty
binds as "exhausted = pass" while spells remain castable (77% of holds
mask one). Mid-plan empty revisions (the no-op's target) are ~9% of
holds. Route 1 is closed; the dominant term is **short plans +
exhausted-binds-closed**. Route 1' = "release": an empty re-decode at
any revision trigger hands the rest of the turn to the executor
(built; measured next on the same windows).

## Addendum — route 1' (release) measured (2026-09-03 18:10)

Same 56 primary windows and rolls: **release vs day-zero binding +0.022
± 0.013** (context +0.056 ± 0.034); **release vs advisory −0.078 ±
0.030, z −2.59** (context −0.052 ± 0.048). Bound windows under release:
forced cast 69% / land 12% / hold 19%. On one subset vs advisory: HOLD
−9.6 / NO-OP −9.6 / RELEASE −7.8. **The first-window plan executed as
written is the residual cost**: the distilled planner's plans are a
lossy imitation of the executor's own line (75% of its labels are the
natural line; mint CE 1.24) and forcing them replaces the cast head's
choices with the imitation's errors. Binding cannot pay until the
planner is better than the executor at the windows it binds — the
question the adjudication now poses is planner quality first (more /
certified-heavier labels, or head-only distillation that fits) versus
reward training under binding from −8pp.

## Addendum — isolation passes (2026-09-03 19:40): the damage is monotone in the amount bound

Same 56 primary windows and rolls, Δwr vs advisory (control null ≈ 0
± 0.008): pinned HOLD −0.096 · NO-OP −0.096 · RELEASE −0.078 ·
RELEASE + no land-first −0.089 (land forcing is not the cost) · RELEASE
+ **first slot only −0.045 ± 0.026** (vs pinned +0.054 ± 0.023, z +2.3;
context −0.010, was −0.118). Every reduction in what binds moves the
number toward advisory and none reaches it: **the planner's plan is
worse than the executor's own choice at every slot, including the
first.** A distilled planner whose labels are 75% the executor's own
line cannot beat the executor when executed as written unless the copy
is faithful; at mint CE 1.24 it is not, and its errors are pure loss.
Consequence for the adjudication: binding pays only where the planner
is better than the executor — planner quality (or a serve-time
confidence gate on WHERE to bind) precedes any binding regime; reward
training from −4.5pp on slot-0 binding is the alternative bet.

## Adjudication (user, 2026-09-03 evening): ROUTE 1

"It definitely sounds like we need to train the planner on the existing
model's strategy before proceeding." The planner is distilled on the
executor's own realized turn plans (the natural line at scale, from
stores where no planner influenced play), fit to convergence with a
holdout, with the mint's certified labels as overrides where present;
the gate is this read re-run on the same population (first-slot-only
and the full rule): a faithful planner reads ≈ 0 against advisory, and
the certified quarter is what remains to add. Standing rule born (→
standing-rules.md): **a binding execution regime is gated by a day-zero
read of the planner against the executor it replaces — binding pays only
where the planner is at least the executor's equal at the bound
windows.**

## Addendum — route 1 build note (2026-09-03 20:20): the emission basis is PRE-LAND

Building the executor-strategy corpus (`scripts/sched_distill.py`)
surfaced a structural fact behind the mechanism: the emission window is
the first own MAIN1 priority window, which is BEFORE the land drop, so
its candidate basis lacks every cast that only becomes affordable after
the drop — **25% of the executor's realized casts are not in the
emission basis** (83 of 339 on the 20-game smoke; probe6's own loader
counted 18% unmatched). A planner labeled only at emission windows can
never plan those casts, and under binding they can only re-enter through
a revision decode the mint never labeled — the exhaustion re-decode that
came back empty. The sweep's arms had the same pre-land basis (the
ceiling was measured with that handicap and still cleared). Route 1's
corpus therefore labels EVERY own-turn priority window with the
executor's remaining in-basis casts from that window on (revision
decodes get their supervision; post-land casts become plannable where
they become castable); lands are excluded from targets (the plan is
casts; the executor keeps the land drop).

## Addendum — route 1 GATE READ (2026-09-03 21:40): FLAT under release; the pinned hold rule superseded

The executor-strategy planner (`m10-planner-distill-v2`: the graft with
its planner pointer fitted on 1,900 argmax games of the ckpt of record —
holdout first-cast agreement 77%, exact plan 64% at emission windows,
vs probe6's 25% / 12%), served on the same 100 windows as the
diagnostics, vs its own advisory play (= iter-019 exactly, zero-init slot
tokens):

| serve rule | Δwr vs advisory (56 primary) | context (36) | bound mix |
|---|---|---|---|
| pinned (empty = hold) | −0.080 ± 0.022, z −3.6 | −0.111 ± 0.033 | hold 82% (98% under an exhausted plan) |
| **release** (empty re-decode → executor) | **+0.009 ± 0.013, z +0.7 — FLAT** | −0.035 ± 0.021 | cast 49% / land 17% / hold 34% |

A faithful planner reads ≈ 0 against the executor it copies — the gate
the adjudication set. The pinned rule cannot pass it for a structural
reason found in the build: **the emission basis is pre-land, so a plan is
partial by construction** (28% of the executor's casts are unplannable
at MAIN1); "exhausted ⇒ hold" then closes the spells the plan could not
name. Fork 1's "hold is binding" sub-pin is amended: **a hold binds only
where the planner EMITS it (an empty first-window plan, an explicit
non-empty revision); an empty re-decode at a revision trigger releases
the rest of the turn to the executor** (`--sched-empty-rev release`).
Both instruments and the estimator behaved: within-run CRN pairs at
1.3pp SE on 56 windows.

Consequences: (1) the ADR-0094 mid-point rule reads FLAT as "training is
the open question; proceed"; (2) probe7's init becomes the distilled
graft (its planner matches its executor) rather than probe6 iter-5;
(3) the full 600-window read of this ckpt under release is the terminal
read's own baseline; (4) session two builds on the release rule.

## Addendum — FULL-SCALE gate read of the distilled planner (2026-09-04 02:00): FLAT by rule, −1.1 ± 0.6

`sched-paired-dayzero-distill-release-20260903-221758` (800 windows,
K=8, release rule, 3.57 h, zero lane failures / fallbacks): **primary
v<0.45 (568 windows) Δwr −0.0108 ± 0.0057, z −1.9, CI [−0.022, +0.0004]
— FLAT by the pre-registered rule** (mean above −bar, CI touching 0);
context (185) −0.0405 ± 0.0109. The structure by value: flat where the
game is lost (+0.1 / +0.3 / −0.3pp at v<0.3), **−3.5 ± 1.3pp at v
0.3–0.45 and −4.1 on context** — binding a 77%-faithful planner costs
nothing where nothing is winnable and ~3.5–4pp where the executor's
choices matter. Instrument at full scale: within-run paired SE 0.077 per
window (floor 0.20), read SE 0.57pp; 120 windows worse / 93 better / 355
tied. Bound windows 102K: cast 52% / land 18% / hold 30%; 329K windows
released; **73% of the remaining holds sit under an EMPTY first-window
emission** (23% of turns; 74% of those turns later held a castable
spell) — the planner's false empties (empty-recall 76% on the holdout;
the executor holds at 33% of emission windows) are the residual. A last
variant is built and measured on the diagnostic windows: an empty
first-window emission binds nothing (`--sched-empty-emit release`) —
binding then only ever forces the planner's NON-EMPTY plans, at the cost
of the "hold is a decision" degree of freedom at day zero.

## Addendum — empty-emission release on the diagnostic windows (2026-09-04 03:10): +3.1 ± 1.3

`--sched-empty-rev release --sched-empty-emit release` (binding forces
only the planner's NON-EMPTY plans; every empty decode leaves the turn to
the executor), distilled planner, same 56 primary windows: **Δwr +0.031 ±
0.013, z +2.4** (context −0.038 ± 0.026); release-only on the same
windows +0.009, pinned −0.096. Bound windows 9.5K: cast 73% / land 20% /
hold 7%. The series on one subset: HOLD −9.6 → NO-OP −9.6 → RELEASE
−7.8 → (distilled) RELEASE +0.9 → RELEASE + EMPTY-EMIT RELEASE +3.1.
The subset reads ~2pp hotter than the population (release-only: +0.9 on
the subset, −1.1 at full scale), so the full 800-window read of this
variant was launched overnight (landing ~06:30) as the number for the
morning's adjudication of the rule.

## Addendum — FULL-SCALE empty-emission variant (2026-09-04 06:30): the two release rules are the same read

`sched-paired-dayzero-distill-emptyemit-20260904-025704` (800 windows,
3.54 h, clean): **primary −0.0099 ± 0.0055 (z −1.8), FLAT by rule**;
context −0.027 ± 0.010; by value +0.1 / −0.3 / −0.7 / −2.7pp. Against the
release-only read on the SAME 568 windows: **+0.0009 ± 0.0034** — no
difference. The subset's +3.1 was a fluctuation (the 56-window subset
runs ~2pp hot on every variant). Bound windows 73K: cast 73% / land 20% /
hold 7%; 15.6K empty first-window emissions released.

**The day-zero number for a 77%-faithful executor-strategy planner is
−1.0 ± 0.55pp on the behind stratum under any non-degenerate binding
rule, −3 to −4pp on winnable states, and the residual is the forced
NON-EMPTY plans (the price of committing at MAIN1 to a sequence the
executor decides window by window), not the empties.** By the ADR-0094
mid-point rule this is FLAT: binding + distillation are worth about
nothing at day zero and training is the open question. Session two's
recipe: the distilled graft as init, `--sched-empty-rev release`
(keeps the emitted hold as a planner decision — the empty-emit variant
buys nothing measurable and removes that degree of freedom), the
terminal read against advisory from a −1.1 ± 0.6 start. Named, not
taken: moving the emission window POST-land (the pre-land basis leaves
28% of casts unplannable; a design change to the emission point).

