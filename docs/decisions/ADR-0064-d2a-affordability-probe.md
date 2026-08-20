# ADR-0064: M9 D2a — the frozen-trunk affordability probe: gate PASS on the high branch (AUC 0.8809 ≥ 0.75); the veto gap is behavioral/interface; D2b SKIPPED per the pinned routing

- **Date:** 2026-08-19
- **Status:** accepted
- **Design-doc anchor:** [m9-plan.md](../design/m9-plan.md) D2a (all pins
  set pre-data at the 2026-08-19 D2a session); ADR-0063 + addendum (the
  v2 label substrate); ADR-0043 (the reconstruction discipline the
  arithmetic-margin pin implements)

## Question

Can affordability — will the engine veto this cast? — be predicted from
the current representation? High ⇒ the trunk already carries the
ingredients and the veto gap is behavioral/interface (the §3c surface
supplies expression + incentive); low ⇒ a genuine representation gap the
§3c surface must expose.

## Instrument

`scripts/affordability_probe.py` (labels → features → probe; 7 unit
tests, suite 205 green). Labels per the pin: positives = first-attempt
`unpayable` vetoes (D1 v2 verdict strata riding as labels-only),
negatives = engine-accepted first-attempt casts/activations (land/pass
excluded); trunk = frozen `d6-run11/iter-019` probed on its own masked
view; substrate `[STATE] ⊕ candidate-entity token` (the pointer head's
input pair; candidate row recovered via `entity_row_of`); ridge +
game-grouped CV-by-AUC, deterministic 80/20 game holdout (frozen-probe
convention). **Leakage guard:** the obs-arithmetic arm runs
`classify_window(corroborated=False)` on every example — the
corroborated path branches on the engine verdict, which IS the label;
guard is itself tested (verdict fields on the record must not move
features). Transfer negatives seeded-capped at 40k/pop (raw counts
logged: argmax 62,466, elevated 207,149). Data:
`data/runs/affordability-probe-d2a` (249M).

Fit population: sampled trio (15,056 examples / 2,244 pos; holdout
3,221 / prevalence 0.155). Drops all named — dominant classes
land_excluded (by design) and dec_missing (the D1 torn-tail class);
zero entity_row_missing.

## Result — the ladder (holdout AUC, sampled fit)

| arm | AUC | knowable | artifact (not_knowable) | uncertain |
| --- | --- | --- | --- | --- |
| base rate | 0.5 | — | — | — |
| cost_pips | 0.7163 | 0.7083 | 0.7538 | 0.6639 |
| obs_arith | 0.8431 | 0.9827 | **0.5385** | 0.9732 |
| state | 0.7671 | 0.7761 | 0.7423 | 0.7869 |
| **state ⊕ cand** | **0.8809** | 0.9000 | **0.8422** | 0.8922 |

**Gate: PASS, high branch** — 0.8809 ≥ 0.75 ⇒ behavioral/interface.
Margin over explicit arithmetic **+0.0378 ≥ 0.03** ⇒ the trunk adds
beyond the arithmetic it re-encodes (the ADR-0043 bar). **D2b: SKIPPED**
per the pinned routing (aux affordability would teach what the trunk
already knows; the forfeited secondary falsification was priced in
pre-data).

**Transfer (no refit):** state⊕cand 0.8967 argmax / 0.8917 elevated —
the representation carries across serve modes and into the
veto-elevated era.

## The finding inside the finding

**The trunk partially predicts the auto-payer's ARTIFACT refusals —
exactly where arithmetic is blind by construction.** On the
not_knowable stratum (obs says payable, engine refused —
`ComputerUtilCost` willingness families), obs_arith reads **0.5385 ≈
chance** while state⊕cand reads **0.8422** (0.8831 argmax / 0.7834
elevated transfer). The model's representation carries signal about
when the engine's own payer will refuse an arithmetically-payable
board — flash-timing shapes, X/phyrexian willingness patterns. This is
the entire arithmetic margin and change: the trunk isn't merely
re-encoding pips-vs-sources; it has learned something about the
auto-payer's behavior itself.

Corollary for D3: the model already "knows" enough to stop paying the
veto tax the moment the interface lets it act on that knowledge — the
cleanest possible setup for the §3c falsifiable prediction. If vetoes
do NOT collapse once payment is expressible, the failure is in the
surface or the incentive, not the representation, and the closeout can
say so with this probe as evidence.

Secondary readings: `[STATE]` alone = 0.7671 — much of the signal
lives in the candidate token (state alone doesn't know WHICH cast is
being priced); cost_pips alone = 0.7163 (cost identity is informative
but far from sufficient).

## Consequences

- **D3 is next** (engine capability audit first, per the plan ladder) —
  probe-funded on the pinned high branch; D2b is skipped and its
  "minimal payment-awareness" mechanism check migrates to D5's
  attribution set, as the pins anticipated.
- The D5 mechanism read inherits a sharpened premise chain: vetoes are
  knowable (D1) ∧ affordability is represented (D2a) ⇒ collapse should
  follow expression. Falsification now indicts the surface/incentive,
  never the representation.
- The artifact-stratum result (0.8422) is banked as a D3 design input:
  payment classes should not assume the engine's payer is the oracle —
  the model out-predicts arithmetic on the payer's own refusals.
- Standing asset: `scripts/affordability_probe.py`; the feature dump
  doubles as a labeled affordability dataset (95,937 examples across
  three populations) for any future aux-target work.
- `data/runs/affordability-probe-d2a` (249M) priced at the M9-close
  stale-data pass.
