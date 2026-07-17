# ADR-0020: M2 closeout — the RL machinery milestone is complete

- **Date:** 2026-07-17
- **Status:** accepted
- **Design-doc anchor:** m2-rl-plan (all deliverables); closes the milestone opened 2026-07-10

## Summary

M2's four done-when clauses all resolved TRUE, each with its own record:

1. **Fork contract gated + PR submitted** — ADR-0011 (D1): rollout contract
   certified under the BC policy; PR #11203 submitted, then merged upstream
   2026-07-12 with the consolidation follow-up maintainer-blessed.
2. **SA checkpoint on both bases + repriced arms** — ADR-0012 (D2/D3):
   agreement parity at exact labels, order rung retired at zero cost, arms
   tie; the pre-RL scope rule adopted.
3. **Critic beats the floor + Ante certified** — ADR-0015 (D4), after
   ADR-0013's winner-label poisoning fix and ADR-0014's certification:
   full-vis critic +12pp mid-game AUC; Ante zero-mean, variance-reducing.
4. **V-trace improves the arms outside noise** — ADR-0019: run-3's guarded
   chain reads 0.5213 ± 0.0110 corrected on 2,000 games, **+6.75pp ± 2.31
   paired vs the BC arm (t=2.92)** — the agent surpasses the heuristic it
   imitated.

En route, unplanned but load-bearing: D5 combat constructs (ADR-0016),
re-ask-on-veto + Ante-in-arms (d6-vtrace-loop §6b), the run-2 collapse and
the guard/hinge regime it bought (ADR-0017), ruleset-scope clarification
(ADR-0018), and the community archaeology + field-guide publication that
opened the manabrew/maintainer collaboration thread.

## Closing hygiene (this ADR's own measurements)

**forkcheck `-grpc` re-cert under micro-batching** (record
`data/forkcheck/run-20260717-grpc-mb/`): twin determinism matrix —

| serve config | d7-ep3 (BC) | run3 iter-012 (RL) |
|---|---|---|
| batch-1 server (D1 record) | 40/40 | — |
| micro-batch server, solo | **40/40** (main-vs-fork 39/40 — D1 bit-for-bit) | 36/40 |
| micro-batch server, + concurrent pollution worker | — | 32/40 |

- **The micro-batcher is exonerated**: at fixed BC checkpoint it reproduces
  the D1 certification exactly. The serve-path rewrite cost nothing.
- **Twin determinism is a policy property**: the RL checkpoint loses 4/40
  solo (argmax near-ties — its entropy grew 0.13→0.21 across the RL chain)
  and a further 4/40 under mixed batch composition (bf16 reduction-order
  sensitivity, which only matters at near-ties). Zero static corruption in
  any cell.
- **Gate protocol amendment: engine-bump certification runs with the BC
  checkpoint** (isolates engine changes from policy properties); the
  current-policy row is informational. Practical impact of RL-ckpt
  nondeterminism was already priced by design: ingest's μ-conflict guard
  absorbs re-issue divergence, rollout labels are MC estimates, arms are
  one-shot measurements.

**Fallback class closed:** all 78 fallbacks across runs 1–3 are combat
declarations (71 block / 7 attack ≈ 0.1% of combat windows) — the known
answer-edge class, bounded, documented; "run-1 had 0" was a misread of the
per-iteration monitor (it had 2–10/iter all along, labeled combat-terminal).

**Veto forensics** ([run3-veto-forensics.md](../design/run3-veto-forensics.md)):
iter-013's drift is 76% `unpayable`, and **73% of commander vetoes occur
with commander tax active** — a strong observation-feature-gap hypothesis
(the model prices recasts at printed cost) that reorders the M3 lever list:
feature fix before reward shaping.

**Fork-local item filed:** `ForkFidelityCheck` lacks the headless
crash-handler (`67e55ba1c1` covered the worker path only) — a startup
failure parks Forge's modal bug-report dialog (bit an operator 2026-07-17);
queued in the worklist for the next fork touch.

## Decision

**M2 is CLOSED.** The milestone's thesis — that the RL machinery could be
built end-to-end on the M1 foundations and produce measurable strength — is
proven with margin. Checkpoint of record: `d6-run3/iter-012/train/last.pt`
(RL); `d5-combat/last.pt` remains the BC checkpoint of record and the
engine-bump certification policy.

**Next: the dedicated M3 planning session** (fresh context), seeded by
[m3-candidates.md](../design/m3-candidates.md) — tracks: RL science
(veto/commander-tax first), the upstream community moment
(manabrew/Hanmac/endstep + #11161 rebase), expressiveness, infra QoL. The
plan doc, opening-sequence ADR, and milestone done-whens come out of that
session per the M1/M2 pattern.
