# ADR-0067: the Arena-of-Glory salvage family — chain admissibility was count-based and color-blind; a chained atom could be "paid" by mana that does not exist yet, including its own output

- **Date:** 2026-08-21
- **Status:** accepted
- **Design-doc anchor:** [m9-payment-surface-spec.md](../design/m9-payment-surface-spec.md)
  §3 (the enumeration-feasibility = executor-feasibility invariant),
  §7 (salvage semantics + the >1% gate), §12 (goal surface);
  ADR-0066 (the first salvage family, whose standing rule routed this
  one, and whose "chainOrderFeasible NOT implicated" consequence this
  falsifies)

## Question

The certify2 read (2026-08-21) recorded 32 non-blocking
`directed_salvage` rows (gate 0.0022, ok) — **every one of them
`costs:Arena of Glory#N@i`** (4 jobs: 227/358/382/470), deterministic
per arm across all rolls. certify3 added the same signature (job 202
arm 7, `costs:Arena of Glory#4@5`, 8/8; arms 1–6 all `directed_ok`).
Per the ADR-0066 standing rule (deterministic per-arm salvage ⇒
suspect the enumerator), why does enumeration-feasibility diverge from
executor-feasibility on exactly this card, and which side is wrong?

## Verdict: enumerator over-admission again — the second structural defect of the ADR-0066 genre, in the one place ADR-0066 declared clean

The failing atom is always Arena of Glory's second ability
(`{R}, {T}, Exert: Add {R}{R}` — the chained-activation class the
surface exists to expose). Exert is innocent: `Exert<1/CARDNAME>` pays
from source. The failure is the **{R} activation cost** at
`payComputerCosts`, and the defect is in `chainOrderFeasible` — three
admission gaps of one genre (the check's feasibility model was not the
executor's):

1. **Count-based and color-blind.** It summed unit counts against
   activation CMCs — a floating Plains `W` "covered" a `{R}`
   activation cost.
2. **No temporal self-exclusion.** The DFS appends a chained atom's
   activation shards to the work queue; a later float-payment branch
   (option a) could pay that `{R}` with **the atom's own second
   unit** — mana that does not exist until after the cost is paid.
3. **Feasibility solved over color MASKS, not the plan's materialized
   colors.** Found by the first re-adjudication pass: certify3 job 202
   arm 7 STILL salvaged after gaps 1–2 closed. The new plan-dump
   channel showed why in one row: floats `W,U,W,U,U` before Arena —
   the feasibility check re-solved the assignment over full unit masks
   and let Shivan Reef's `U|R` combo unit "be red" for the `{R}`
   activation cost, but the DFS had committed that unit to `U` (and
   `completePlan` defaults any uncommitted unit to `firstColor(mask)`,
   where `U` sorts before `R`); the executor expresses exactly those
   materialized colors. At execution time a combo unit has ONE color —
   the plan's — not a mask.

Both violations survive to the wire whenever the fungible pool at
execution time happens not to cover the activation cost:
`executeDirected` runs atoms in (activation CMC, host id) order,
pays each cost pool-first via the heuristic, and on a color-starved
board the only red source is Arena itself — whose mana payment taps
the host, so the subsequent `CostTap` fails → deterministic
`costs:Arena of Glory#N@i`. Why the card is a family of one in this
pool: the salvage needs a mana-costed mana ability with a **colored**
activation cost on boards where that color is scarce — Arena of Glory
is the census pool's only high-traffic instance.

Minimal repro: Plains + Arena of Glory vs `{1}{W}` (Kor Skyfisher).
The old enumerator admits `[Plains→W, Arena-costed→{1}]` with the
appended `{R}` shard paid by Arena's own float; execution salvages
with exactly the census signature. The earlier Mountain + Arena vs
`{R}{R}` board *passes* pre-fix — the Mountain's red float is
fungible and rescues the self-payment plan — which is why the defect
is intermittent at census scale (32/14k) yet deterministic per plan.

## The fix (fork branch `m9-payment-surface`): color-aware executor-order feasibility

`chainOrderFeasible` now **replays the executor's exact activation
order** (`EXEC_ORDER`, one shared comparator so the check and
`executeDirected` cannot drift) and requires an exact assignment:

- each chained atom's activation shards must be color-coverable by
  units that exist **strictly before it executes** — the initial pool
  plus earlier atoms' full yields, treated as fungible (earmarks do
  not survive the pool; this keeps the Mountain-board chain admitted);
- units carry their **materialized** colors (assigned plan color, else
  `firstColor(mask)` — the same rule `completePlan` and the executor's
  express-choice apply), never raw masks; a branch rejected for a
  wrong open-unit color is re-found by the DFS with the unit assigned
  (job 202's plan re-materializes with the Reef unit expressed red and
  executes);
- the main cost must be coverable by what remains;
- snow/phyrexian honored (float units carry host snow-ness; life
  budget from the DFS's phyrexian count);
- exact small backtracking with symmetric-unit pruning,
  `FEAS_NODE_BUDGET` 20k per plan — on exhaustion the plan is
  **admitted** (pre-tightening behavior, executor adjudicates; a
  budget miss degrades loud-at-census, never silently censors).

**Diagnosis channel extended** (the ADR-0066 `exec_why` lesson,
second application): salvage rows now also carry `plan` — the
executor-order atom dump (`host#id[activation]->materialized colors` +
pool spend) via `PaymentEnumerator.describePlan` /
`PayDirective.planDesc`. Gap 3 was found from one such row; without it
the residual would have been another blind family.

Regression tests (fork payment suite, now 20/20 across the four
classes): `testColorStarvedChainNotAdmitted` (the census signature —
every surfaced option must execute `directed_ok`; failed pre-fix with
`costs:Arena of Glory#2@1`) and
`testExertCostedManaAbilityChainExecutes` (the fungibility guard —
the legitimate exert chain must STAY admitted and execute; passed
pre- and post-fix).

## Re-adjudication (all five affected jobs, fixed jar): salvage 0.0000

Verbatim job replays (same seeds/decks/windows, arms × k=8 rolls) on
the fixed jar — **zero salvage on all 176 rows**, formerly-salvaging
arms split exactly as the diagnosis predicts:

| job | old (salvaging arm) | new |
| --- | --- | --- |
| certify2 227 | arm 1 salvage 8/8, opts 3 | **all 3 arms `directed_ok`**, opts 3 (goal re-argmaxed to a feasible plan) |
| certify2 358 | arm 1 salvage 8/8, opts 2 | arm 1 `directed_ok`, **opts 2→1** (phantom option gone; arm 2 `no_such_option`) |
| certify2 382 | arm 3 salvage 8/8, opts 3 | arms 1–2 `directed_ok`, **opts 3→2** (arm 3 `no_such_option`) |
| certify2 470 | arm 1 salvage 8/8, opts 2 | arm 1 `directed_ok`, **opts 2→1** (arm 2 `no_such_option`) |
| certify3 202 | arm 7 salvage 8/8, opts 7 | **all 7 arms `directed_ok`**, opts 7 (the gap-3 plan re-materialized with the Reef unit expressed red — arm 7 is now EXECUTABLE, not phantom) |

Certify3 job 202 therefore goes back to the evalset session for
single-job re-adjudication + evalset re-merge (its drill was held in
`data/runs/payment-evalset-v1/held-drills.jsonl` pending this
finding, and its arm 7 is real).

## Consequences

1. **ADR-0066 consequence 4 is falsified** — chain admissibility WAS
   implicated, by the same resource-model-mismatch genre (there:
   exclusivity unit; here: temporal/color availability). The standing
   rule performed as designed: the family was flagged at read time and
   diagnosed off the reason codes.
2. **The paygoals3 baseline telemetry is again one-sidedly stale on
   option-count margins** (the fix only REMOVES plans; consequential
   15.28/g is an upper bound on the fixed-jar rate). Salvage traffic
   was 0.22% of directed rows, so the perturbation is small, but any
   window whose option list shrank has option-index misalignment vs
   the certify2/3 arm numbering. **Routing: re-pin decision (paygoals4
   verbatim re-census vs accept-the-bound) goes to the D4 gate
   session by name — not silently absorbed.**
3. Certified drills are unaffected (certification requires
   `directed_ok` arms; no certified drill rode a salvaged arm), and
   the 193 auto-correct drills are auto-arm-only. The one held drill
   (certify3 job 202) goes back to the evalset session with its
   re-adjudicated arms.
4. The executor keeps its static `EXEC_ORDER`; residual
   greedy-color-mismatch cases (the heuristic spending the wrong
   fungible unit on a generic shard) remain possible in principle,
   remain reason-coded salvage, and remain covered by the standing
   rule below.

## Standing rule extended (ADR-0066 rule, second confirmation)

An enumerator's feasibility model must match the executor's actual
algorithm — resource exclusivity (0066), and now **temporal and color
availability under the executor's execution order**. When the two
layers disagree, the disagreement surfaces as deterministic per-arm
salvage; suspect the enumerator first, and keep the shared invariant
in ONE code artifact (here `EXEC_ORDER`) so the layers cannot drift
apart silently.
