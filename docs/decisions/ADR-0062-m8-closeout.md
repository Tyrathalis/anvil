# ADR-0062: M8 closeout — critic-ordered curation TIES at the gate (both candidates); the curriculum × curation family is measured out at this scale; routing = the M9 interface round (§3c mana head + §3a planning)

- **Date:** 2026-08-19
- **Status:** accepted (user-approved close 2026-08-19)
- **Design-doc anchor:** m8-plan (all four done-when clauses); ADR-0060
  (D1 fail + pivot), ADR-0061 (entry gate PASS), ADR-0035 (one-shot per
  method), ADR-0058 (the counting rule this close leaned on, again)

## The run (d6-run17) and its verdict

The D2′ run: critic-ordered curation (`drill-selection-m8-critic`, 320
entries from the 1,253-candidate 4× pool at 2.9× effective unique-g
selectivity, a2 quotas, critic-ordered within bands), run13's recipe
otherwise verbatim EXCEPT §6c at the standing corrected pricing
0.01/window (user decision: "verbatim" binds structure for
comparability, not superseded components), init `iter-019`, seed
20260821. **Ended at the iteration-11 veto-guard halt** (0.3032 >
1.5× iter-0 0.195; veto trajectory 0.230 → 0.255 → 0.303 — run16's
ending at higher tempo, consistent with 4×-selective curation
concentrating cast-heavy collapse windows harder). Iterations 0–10
accepted.

**Gate sweep (two-candidate, arms-selected, disclosed — the
run16/M6 precedent): both TIE.**

| candidate | corrected | paired vs baseline | verdict |
| --- | --- | --- | --- |
| iter-009 (peak arm 0.5575 ± 0.0248) | 0.5456 ± 0.0111 | **+0.75pp ± 0.99 (t=0.76, 1,994 games)** | TIE |
| iter-010 (last accepted) | 0.5325 ± 0.0110 | **−0.50pp ± 1.03 (t=−0.49, 1,997 games)** | TIE |

**No promotion. Ckpt of record stays `d6-run11/iter-019` at 0.5373 ±
0.0112.** The iter-009 arm read was the THIRD ~1.5σ small-N flattering
read caught by a full paired read (run8 0.5675, run16 0.575 — the
ADR-0058 one-observation rule, re-confirmed).

Pre-registered descriptive reads: realized composition vs cycle-3 —
320 vs 321 entries, ahead 18.75% vs 18.69%, all-band vs 303-band/18-
above; mean calibrated sel_v 0.5516 vs cycle-3's mean rollout sel_wr
0.4953 (ordering source differs; quota shape near-identical — the
attribution is clean to ordering-given-quotas). Behavioral record:
the iter-4 conversion-trade shape DISSOLVED by iter-9 (winnable
−4.1pp → −0.8pp, coin −1.2 → +0.3) while lost held +5.5pp — the
curriculum moved behavior in a healthier profile than run13's, and
strength still did not move. At argmax closing serve, veto sat at
0.181–0.185 despite the sampled-play climb to 0.303 (much of the
elevation is exploration-side probing).

## Family closure

Curriculum × curation is the only family that ever promoted (+1.98pp,
run11/ADR-0031) and is one-shot per method (ADR-0035). The method
ledger is now: a2 rebalance PROMOTED once; recomposed continuation
(run12) TIE; rank-critic-screened + D3 composition (run13) TIE;
**critic-ordered at 4× (run17) TIE — the last never-run method in the
family.** With credit-assignment recorded exhausted at ADR-0060 (every
angle substrate-absent or formulation-falsified), **both
training-signal families operating through the existing action
interface are measured out at this scale.** The recurring three-
milestone signature — trainable, behavior-moving, strength-neutral —
now has readings from representation (M6), credit (M7), and curation
(M8).

## The veto account (standing, for any future lever)

Recorded this milestone (devlog M9-seed section, user framing):
**under auto-payment, probing-via-veto IS optimal play** — the veto
channel is the model's only affordability oracle and re-ask makes
probes free. This explains veto strength-neutrality (×3), the §6c
pricing pincer (M6 suppression at 0.02/event vs M8 runaway at
0.01/window — no working uniform λ exists, it prices optimal behavior),
and drill amplification. **Deterrence approaches (auto-scaling λ,
harsher pricing) are CLOSED as an axis. Veto rate is re-typed as a
capability diagnostic:** prediction — a payment-aware model shows veto
collapse with no penalty; failure of that prediction falsifies the
interface theory. Entry instrument for any veto work: the knowability
decomposition (knowable-from-public vs hidden-info-plausible) over
logged vetoes.

## Routing

**M9 candidate (user-inclined, next design session): the interface
round — §3c conscious mana payment (payment-class sub-head) first,
§3a planning (plan-emit-and-condition, tier-2/3) second** (ADR-0042's
rising-priority queue, now with the measured case: the interface is
the one thing no run has touched). Constraint carried into that
round: tier-3 search scores leaves with the critic — ADR-0061
measured 0.42 ordering on fresh-era positions vs the 0.94 ceiling
(fine for curation; a real limit for search-leaf evaluation).
Next-boundary bundle unchanged (rebase + multi-format enablement +
2-arm trim + copy-state forensics) + the fork-index store-namespace
fix (the run17 iter-2 collision; era-scoped).

## Assets and corrections banked this milestone

- **Standing assets:** `rankcrit_audit.py` sample/read (the ordering
  audit, ~40 min/era) + the selectivity-curve pool rule;
  `critic_select.py` (critic-ordered selection, cross-store g-unique);
  parameterized `cycle_stock.py`; the OBSERVE probe (ADR-0060); 492
  banked K=8 audit labels in the calibration set; VRAM scale-to-zero +
  scale-back-up (branch `vram-scale-to-zero`, merged at this close).
- **Instrument corrections (the ADR-0059 genre):** `grindstone report`
  per-(game,turn) join (multi-fork drillfiles silently lost 124/500
  points); cross-store fork-index collisions made loud (`grindstone
  select` FATAL) + selection-side dedupe (run13 had carried 38 such
  pairs on rotation luck).
- **Amendment discipline exercised twice, both pre-data:** D1 K=32→64;
  the entry-gate threshold 0.45→0.35 re-referenced to the measured
  in-era benchmark 0.377.

## Stale-data pass (kill list presented at close; user executes)

Kill (~5.7G): `d6-run17-i0*` run dirs (2.2G) + trajectories (1.2G) +
`drillmix0*-m8stock*` campaign run dirs (128M) + fork trajectories
(821M) — tied-run training stores per the M7 precedent; `m8stock-s*` /
`m8stock2-s*` raw harness run dirs (1.3G) — ingested, trajectories
kept; `drillm8audit-*` raw label run dirs (12M) — aggregated into
`m8-audit/plan/drills.jsonl`; the three D1 K=2 smoke dirs (~200K);
launch-log dirs. **Keep:** `data/training/d6-run17` (+driver logs),
run17 finalarm stores + Ante ledgers, `m8stock*` trajectory stores
(267M — the selection's provenance chain), `early-doom-m8-rankcrit*`,
`m8-audit/` aggregates, `drill-selection-m8-critic`, `drillm8d1nat-*`
(ADR-0060), baseline-era stores. `data/forkcheck/m8d1-proof` jars
(183M) prune at the next boundary per ADR-0060.
