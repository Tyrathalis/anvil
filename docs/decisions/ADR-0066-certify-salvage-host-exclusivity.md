# ADR-0066: the certify-smoke salvage diagnosis — the payment DFS lacked host-card exclusivity; the forced family was 100% phantom; the paygoals2 telemetry read is invalidated for consequential/forced claims

- **Date:** 2026-08-20
- **Status:** accepted
- **Design-doc anchor:** [m9-payment-surface-spec.md](../design/m9-payment-surface-spec.md)
  §3 (the enumeration-feasibility = executor-feasibility invariant),
  §7 (salvage semantics + the >1% gate), §12c (the clean-forced
  channel); [m9-rung3-draft.md](../design/m9-rung3-draft.md) (the
  certification harness this fired inside); ADR-0065 (the capability
  audit whose invariant this restores)

## Question

The rung-3 certify smoke (8 jobs, 105 rows, 2026-08-20) measured
directed-execution salvage at **52% of certify arms and 100% of the
forced_chain family** — all six mined forced windows the same card
(Black Panther, Hope Enduring = the transformed face of King T'Challa;
the window is the `{4}{W}{U}` SetState activation). Spec §7's salvage
gate (>1%) fired on first contact, blocking the 126-job certification
run. Was this executor unfaithfulness, enumerator over-admission, or a
cost-shape peculiarity of the card?

## Verdict: enumerator over-admission — one structural defect, now fixed and regression-pinned

**The payment DFS tracked source availability per CLASS; feasibility is
per HOST CARD.** A dual land hosts two mana abilities (Forge scripts
duals as two basic-type intrinsics), which land in two *different*
source classes — and both classes list the same physical copies in id
order, so any plan needing both colors deterministically committed the
**lowest-id dual to two shards at once**. Count-feasible,
executor-infeasible: `executeDirected` taps the card for the first
atom, and the second atom fails `canPlay()` → `directed_salvage`. The
evidence was visible in the wire labels themselves (`spare:Badlands x2`
appearing twice as separate goals over the same two physical Badlands).

Salvage was deterministic per (job, arm) across all rolls — a plan
property, not flakiness — and clustered exactly on dual/multi-ability
boards. Minimal repro (2× Hallowed Fountain vs `{W}{U}`) failed with
the predicted duplicate-host commit pre-fix; passes post-fix.

## The fix (fork `37bde8051e`, branch `m9-payment-surface`)

1. **Host-card exclusivity in the DFS** (`PaymentEnumerator.DfsState`):
   a `usedHosts` set replaces the per-class `remaining[]` counters;
   the deterministic within-class pick becomes lowest-id atom whose
   host is uncommitted. Conservative for the rare no-tap repeatable
   producer (the atom model was already single-use per ability); the
   executor still adjudicates.
2. **Reason-coded salvage** (the diagnosis channel the smoke lacked):
   `executeDirected(p, pc, why)` reports `canplay:`/`costs:` +
   host#id@atomIdx; `PayDirective.execWhy` → certify row `exec_why`;
   `payment_certify.py read` prints the salvage gate + failure-point
   tally every read.
3. **Regression test** `testDualLandNotDoubleCommitted` (distinct
   hosts in every materialized plan + `directed_ok` + exact float on
   the dual board). Fork payment suite 15/15; Anvil suite green.

## Re-smoke (same 8 jobs, fixed jar): salvage 0.0000 on 64 directed rows — gate ok

- **blocker_pressure jobs 6/7: every directed arm now `directed_ok`
  (64/64 rows)** — the executor was faithful all along; every salvage
  in the original smoke was a phantom plan.
- **The forced family is GONE: jobs 0–5 enumerate ZERO options
  post-fix** (`avail_options=0`, all directed arms `no_such_option`).
  The auto-payer was *right* to refuse those boards — there is no
  legal payment for `{4}{W}{U}` at those states without
  double-committing a dual. All six "forced" windows were
  over-admission artifacts, **not** I+I+Signet-class auto-payer blind
  spots.

## Consequences

1. **The §12c clean-forced channel claim is falsified for this
   census.** `run-20260819-paygoals2`'s "forced 6 CLEAN" read: all six
   were phantoms. The forced channel remains real in principle (the
   ADR-0065 audit board still test-proves it) but is census-rare; D5's
   collapse read must not lean on forced-window traffic.
2. **The pinned pre-D4 baseline telemetry is contaminated on the
   affected margins.** Consequential 15.99/g, the class-count
   histogram, and option counts were measured with phantom
   compositions inflating multi-option windows (a window is
   consequential at ≥2 outcome-distinct options — phantom plans
   manufactured options). Direction of error: one-sided (fix only
   REMOVES plans). **Routing: re-run the 500-game paytelemetry census
   on the fixed jar, re-mine drill candidates, re-plan the
   certification set before the 126-job run** — the existing plan is
   doubly stale (6 dead forced jobs; option-index misalignment at any
   window whose option list shrank).
3. **The salvage gate earned its keep on first contact** — it caught a
   structural enumerator defect before any D4 read consumed a single
   certification. It stays pinned at >1% with `exec_why` now making
   fires diagnosable in-read.
4. Chain admissibility (`chainOrderFeasible`, count-based greedy) is
   NOT implicated — untouched, still executor-adjudicated.

## Standing rule born here

**An enumerator's unit of exclusivity must be the unit the executor
consumes** (here: the card, not the (card, ability) class). When an
enumeration layer and an execution layer disagree on the resource
model, the disagreement surfaces as deterministic salvage — read
per-arm × per-roll consistency before suspecting the executor.
