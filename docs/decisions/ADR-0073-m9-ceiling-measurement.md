# ADR-0073: M9 ceiling measurement — the 2-turn proxy CONVERTS where it holds (+12.5pp/window in-era) and the aggregate ceiling is SUB-GATE on every measured bound; payment routes to infrastructure, D6 takes the promotion slot

- **Date:** 2026-08-24
- **Status:** accepted
- **Design-doc anchor:** [m9-plan.md](../design/m9-plan.md) "The ceiling
  measurement" (pins, 2026-08-24, committed pre-read at `cec0150`);
  [ADR-0072](ADR-0072-d4-control-run-veto-collapse-falsified.md) (which
  specified the measurement and made it gate every remaining §3c decision);
  [ADR-0069](ADR-0069-d4-read-adjudication.md) (the capability negative this
  contextualizes); `data/runs/payment-evalset-v1` (the instrument under test)

## Question

ADR-0072 found that `payment_certify.py` certifies a `HORIZON = 2`
board/tempo proxy, not winrate — the single most important unmeasured
quantity in the §3c program. This measurement asks: **do the 69 certified
positives' 2-turn advantages convert to winning the game?**

## Instrument

Zero Java delta — `CensusRun -certify`'s `HorizonStop` already stops at
`t + horizon` OR natural game end, and rows carry `winner`/`ended`. Two job
sets over the evalset-of-record positives, identical except horizon (2 =
in-era re-certification; 999 = game end), **reusing the revalidation job ids
and seeds** so `rollSeed = f(seed, job, roll)` matches across sets: each
(job, arm, roll) is the SAME determinized trajectory truncated at two
points — the 2-turn proxy score and the game-end outcome are read off the
same game. k = 8, ALL arms (the non-best arms are the free
proxy-predictiveness scatter), bundle jar `2f87180cdf`, ~5,750 games, ~3.5h
on 8 lanes. Machinery: `scripts/payment_ceiling.py` (plan/read) +
`payment_certify.py lanes` + `scripts/launch_ceiling.sh`;
run dir `data/census/run-20260824-ceiling/`.

Reads were pre-registered in m9-plan.md and committed before any result
existed. Smoke (3 drills, k=1) validated the path end-to-end and reproduced
certification margins in-era (14.0 vs 11.5, 7.0 vs 5.9, 27.5 vs 24.2).

## Result

**Instrument health:** denominator 65/69 (4 thin-pairs, consistent with the
revalidation misses), zero unended rolls, zero draw-clock hits, refire
guard ok (≥55). Every game ended naturally.

**Primary (pin 2), paired per-drill win-diff Δ = win(best) − win(auto),
clustered by drill:**

| population | n | Δ (pp) | z | recert |
| --- | --- | --- | --- | --- |
| ALL | 65 | **+4.62 ± 2.15** | **+2.15** | 29/65 |
| recert in-era | 29 | **+12.50 ± 3.34** | **+3.74** | — |
| not recert | 36 | −1.74 ± 2.34 | −0.74 | — |
| blocker_pressure | 12 | +3.12 | +0.56 | 4/12 |
| color_hold | 25 | +6.00 | +1.49 | 13/25 |
| phyrexian | 13 | **+0.00** | 0.00 | 5/13 |
| wide_choice | 15 | +7.50 | +1.66 | 7/15 |

**Proxy predictiveness:** Spearman(in-era margin, win-diff) **+0.465** at
drill level (n=65), +0.408 across all 270 directed arms.

**The pinned branch adjudication:** SURVIVES (Δ ≥ +5pp AND z ≥ 2) missed on
magnitude by 0.4pp while passing on z — but the branch never fired, because
**in-era re-certification 44.6% < the 70% guard ⇒ INSTRUMENT DRIFTED,
qualified read, session adjudicates** (this ADR is that adjudication,
user-decided 2026-08-24).

**The guard's cause is winner's curse, not a broken era.** Certified margins
were selected on old-jar, old-determinization noise; regression on
re-measurement was expected even with a frozen engine, and the 70% pin
priced only drift. Evidence: median margin 3.88 → 2.50 but only 12/65
sign-flipped; 53/65 stayed positive, and the margin>0 set converts at
+6.6pp (z = +2.70). The recert/non-recert Δ split (+12.5 vs −1.7) is
exactly the signature of a *predictive proxy on a selection-noisy evalset*,
not of a proxy that stopped meaning anything.

**Gate-scale arithmetic (pin 4):** per-window value is real but thin at
gate resolution on every computable lower bound — pooled Δ × 0.112 mined
windows/game/seat = **+0.52pp/game**; recert-only (+12.5pp × ~0.058/g) ≈
**+0.73pp/game**; both below the ±1.1pp gate floor. The caveat cuts upward:
mining adjudicated only the top-ranked ~1,073 of ~8,000 consequential
windows, one seat, so the true certifiable-window rate could be 2–4× the
bound (which would put perfect play at +1.5–3pp, above the floor).

## Decision

1. **Verdict: the 2-turn proxy is PREDICTIVE and CONVERTS where it holds**
   (+12.5pp per window on in-era-certified drills, z = 3.74; Spearman
   ~+0.46). ADR-0072's branch (c) — "the value was never there /
   non-predictive proxy" — is **killed**. The drills were measuring
   something real.
2. **The aggregate ceiling is sub-gate on every measured bound.** The
   honest headline the closeout carries: *payment skill is worth +12.5pp in
   the windows where it fires, and those windows are rare enough that
   perfect play aggregates below the gate's noise floor on mined lower
   bounds.* Two training runs weren't chasing nothing; they were chasing
   something too small for the instrument that judged them.
3. **Routing (user-adjudicated): the payment surface is held as
   INFRASTRUCTURE — executor, enumerator, telemetry, evalset all stay —
   and D6 (the §3a turn-plan latent) takes M9's promotion slot.** The D6
   design session must pin: (a) the argument the latent escapes the
   marginal-vs-conditional failure mode that took the payment head (it
   trains on the same trajectory returns), and (b) a pre-registered early
   kill signal if it doesn't.
4. **The supervised-conditional-signal attack (ADR-0015 machinery) is a
   NAMED M10 candidate, contingent on the window-rate bound.** The one
   cheap follow-up this read points at: an exhaustive certification sweep
   over one 500-game census (~one night) to bound the true
   certifiable-window rate. **Scheduling decision deferred BY NAME to the
   D6 design session / M9 closeout** — the payment-completion-queue
   routing reads differently at +0.5pp than at +3pp (no-silent-loss rule).
5. **Evalset repair input (the owed ADR-0069 item, now empirical):**
   phyrexian converts at exactly 0.0pp at game end — the shape is dead as
   constructed at BOTH horizons (model-unreachable AND value-free), and
   its 13 positives should not survive repair unchanged. wide_choice
   (+7.5pp) carries real value despite being model-unreachable — its
   repair is about *reachability*, not existence.
6. **Anomaly (exploratory, battery discipline):** the
   positive-but-subthreshold margin stratum reads −4.9pp (z = −2.7, n=18)
   — small in-era board advantages converting slightly *against*.
   Multiple-comparisons territory; recorded, not interpreted.

## Standing rules born here

- **A re-certification threshold on a selected population must price
  winner's-curse regression, not only drift.** The 70% recert pin treated
  margin decay as evidence the era moved; a population selected on a noisy
  statistic regresses on re-measurement even under a frozen engine. Split
  the criterion (sign-flip rate vs threshold-clearance rate) or calibrate
  the pin on a held-out re-measurement before registering it.
- **Per-window value and gate-scale value are distinct claims; a ceiling
  statement must carry both.** "+12.5pp where it fires" and "+0.5pp/game
  aggregate" are the same measurement — citing either alone misroutes.
  (Companion to ADR-0072's certification-horizon rule.)

## Consequences

- **M9's §3c program is CLOSED as a strength lever at current window-rate
  bounds; the surface survives as infrastructure.** The closeout ADR
  upgrades "the winrate value has never been measured" to this ADR's
  verdict, and routes the payment-completion queue against it.
- **D6 design session is next** (the §3a second act, m9-plan D6, promotion
  slot inherited via the D4 negative branch).
- **Assets born:** `scripts/payment_ceiling.py` (the both-horizon paired
  replay + pinned read — reusable for any future evalset ceiling read);
  `data/census/run-20260824-ceiling/` (ceiling-read.json,
  ceiling-drills.jsonl = 65 payment windows with paired game-end labels —
  seed material for any future conditional-signal work);
  `scripts/launch_ceiling.sh` (the 8-lane detached driver pattern).
- **Still owed, unchanged:** pin-12 forced-family re-mine (re-deferral with
  recorded reason now the likely routing, per this verdict); evalset repair
  (now with decision 5's empirical shape verdicts).
