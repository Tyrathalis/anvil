# ADR-0033: M4 closeout — the drill loop went online and delivered the first outside-noise win

- **Date:** 2026-08-03
- **Status:** accepted (closure confirmed by user)
- **Design-doc anchor:** m4-plan (all deliverables); closes the milestone opened 2026-07-28 (ADR-0027)

## Summary

M4's four done-when clauses all resolved TRUE, each with its own record:

1. **The re-baseline question resolved** — ADR-0028 (D1): the `d6-run9`
   adaptation probe ran 10/10 under guards; +1.15pp ± 0.90 vs the old
   record = directionally-positive tie ⇒ the heuristic got stronger,
   baseline stayed 0.5121, and the probe re-confirmed ADR-0024's
   absent-signal diagnosis on the new engine. Its closing-read stores
   became D2's curation substrate — the deliverable was designed to
   feed its successor and did.
2. **Grindstone v0 online** — D2 opened and closed in a single day
   (07-29): curation regenerated on new-engine games (584 addressable
   losses, two-critic agreement 0.3pp), drill machinery smoke-gated
   (7/8 exact replay; the miss is an accounted statistic), the full
   584-drill ground-truth map (rollout 23.7% vs critic 0.584 — the
   calibration gap in one number), and the eval suite with the
   re-measurement pairing protocol that later caught selection-on-noise
   twice. The map alone paid for itself: two engine crash classes found
   (monarchy-transfer fixed same day + test-pinned; MayPlay diagnosed
   with deterministic repro).
3. **A drill-signal run beat the baseline outside noise** — ADR-0031
   (D3), via one falsified intermediate: experiment (a)'s all-behind
   mixture was strength-neutral with the mechanism visible in the
   held-out decomposition (ADR-0030), and the rebalanced (a2) converted
   it — **combined paired +1.98pp ± 0.71, t=2.77 over 3,994 games,
   replicated on independent seeds**. `d6-run11/iter-019` promoted to
   ckpt of record; **the M4 baseline closed at 0.5316 ± 0.0110**
   (opened at 0.5121).
4. **Serving path resolved** — ADR-0032 (D4): serve-path code was a
   documented negative (0.05 ms Python-active/request — the ceiling is
   waiting); the measured lever was generation shape (w=16 + per-batch
   ≥2-round chunking), mini-run-validated at **~+30% in-loop**. The
   standing recipe adopts w=16.

En route, unplanned but load-bearing: the chunk-tail retraction and its
standing lesson (cross-era throughput comparisons only at identical
chunking; a stable wrong number is stable because same seeds → same
slowest chunk); the fork-session ingest chain (`-forkobs` → stores →
sampled+μ parity) that makes drill completions first-class training
data; the mid-run drill-eval driver phase (the halfway kill/continue
read); the standing `anvil_watchd` watcher with self-registration (the
pgrep self-match class fully retired, then its test's notification leak
sealed with `ANVIL_NOTIFY_SILENT`); the three-layer wedged-completion
crash-cascade fix; and the D2.4 protocol pin (evals pair against the
pinned policy's own re-measurement, never selection-time labels) —
re-derived independently by the turn-offset sweep and the v2 evalset
cross-check.

## The honest headline

The milestone's thesis — **drills are the mechanical answer to the
absent-signal verdict** — is confirmed, with a mechanism sharper than
the plan predicted: behind-position drills generalize to held-out
positions of the same shape (+7.5/+7.4pp lost/long_shot, persisting at
full dose), but an all-behind curriculum *buys* that transfer with
conversion regression on ahead positions (−9.7pp), and mixture balance
— not more signal — was the difference between a tie and the win.
Curriculum composition is a first-class lever now, not an
implementation detail. The winnable −5.1pp residual at 18.8%
ahead-weight is the documented open edge of that lever.

## Decision

**M4 is CLOSED.** Checkpoint of record: `d6-run11/iter-019/train/last.pt`
at **0.5316 ± 0.0110 corrected** (standing seeds 20260710); BC
`d5-combat` remains the engine-bump certification policy. The M5
planning baseline is 0.5316.

**Next: M5 — Grindstone cycle 2 (the compounding question),** direction
agreed with the user this session: re-curate from iter-019's own
losses, run the loop again, and measure whether the second pass's
increment slopes up or down. The user's framing is the bet to test:
fixing bad decisions should move the collapse points to a higher level,
and training on the *new* collapse points should narrow toward a higher
level of play — the drill loop as a ratchet, not a one-shot correction.

## Consequences and carried-forward inventory

- **Hazard retired at close:** pool-manifest mtime selection (the M3
  rider) — `data/pool/CURRENT` pin, all four glob sites switched,
  loud failure on a missing/dangling pin.
- **Curation staleness is now a standing rule, not a one-off:** every
  drill cycle regenerates curation from the current ckpt-of-record's
  own losses; selection/evalset versions are ckpt-era-scoped
  (`drill-evalset-v2` is valid for run11-era ckpts only).
- **Recipe state:** w=16 generation + per-batch chunk clamp + §6d mix +
  §6c penalty + §6f critic @ lr 1e-5 + re-ask + drill phase at f≈20%
  with ahead-weight ≈ 19% (the (a2) shape).
- **Levers on file for M5:** critic calibration (the ~1,900 K-rollout
  ground-truth labels vs critic 0.58-on-0.24 miscalibration — improves
  curation, anchoring, and Ante at once); winnable-residual repair
  (per-bin slice stratification); escalation (b) K-rollout advantage
  baselines — opt-in, no longer ladder-required.
- **Small fork items carried:** MayPlay `.get(0)` fix (deferred to the
  copy-ordering/consolidation question), targeting-retry hang
  forensics, MinMaxBlocker realizer gap, the IndexOOB class (one more
  seed-pinned repro banked by `d4-w16val` iter-000).
- **Upstream watches unchanged:** #11285 (queued #11360 complementarity
  comment = the review nudge), consolidation follow-up if maintainers
  engage, connive-lines conflict expected at next rebase (drop ours).
- Playable-fork and Chronicle tracks are unaffected side streams
  (their own worklists; Chronicle next = D3 iteration + D4 SDK
  decision).
