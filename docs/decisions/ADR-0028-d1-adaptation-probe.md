# ADR-0028: M4 D1 closeout — the adaptation probe resolves the re-baseline question: the heuristic got stronger

- **Date:** 2026-07-29
- **Status:** accepted
- **Design-doc anchor:** m4-plan D1; resolves the mechanism question ADR-0025
  deliberately left open and ADR-0027 pre-registered the test for
- **Records:** `data/training/d6-run9/` (run), `data/runs/run9-final-arms-report.json`
  + `data/runs/ante-run9-finalarm-s{0,1}-*.json` (closing read),
  `data/runs/run9-finalarm-s{0,1}-*` (stores, obs on — the D2 curation substrate)

## Context

The rebase dropped the RL checkpoint of record from 0.5530 to 0.5121
corrected, and the two candidate mechanisms — the heuristic got stronger
(26 forge-ai commits) vs opponent-specific-fit loss (§6d family) — were
indistinguishable by static reads (ADR-0025's diff-in-diff: −2.45pp ± 2.19,
underpowered). ADR-0027 pre-registered the discriminating experiment:
`d6-run9`, the standing recipe **verbatim** (run-7b config: §6d mix 0.5 +
§6c penalty 0.02 + §6f critic, lr 1e-5, re-ask, guards), init
`run7b/iter-014/{train,critic}`, first-ever training contact with the
rebased fork (`master` @ `5fbc2ac98d`), 10 guarded iterations, fresh seeds
20260830. Pre-registered interpretation: fast recovery toward ~0.55 ⇒
opponent-fit (recoverable); flat ⇒ heuristic stronger; partial ⇒ both.

## What happened

- **Run health: 10/10 iterations, zero guard halts, zero tripwire
  violations.** KL/iter 0.004–0.009, entropy pinned 0.12–0.13, ρ ~0.99.
  Post-collate cadence confirmed in production: train ~3 min vs generation
  ~25–32 min (~32 min/iteration total; the 16.6h-train era is over).
  Crashes: 3 in 4,800 generation games (timeout, NPE, and one of the
  carried `IndexOutOfBoundsException` class), all skipped cleanly.
- **The clearest adaptation signal was veto, and it was strength-neutral:**
  generation veto rate fell 0.149→0.113 (first-attempt 0.118→0.094) across
  the run; the closing read reads first-attempt 0.0817 at argmax. The
  policy visibly re-fit its action distribution to the new opponent — and
  bought nothing, echoing the D1/§6c lesson a third time (veto is wasted
  intent, not lost winrate).
- **Arms:** i4 0.4950 ± 0.0250 → i9 0.5100 ± 0.0250 (400-game reads) — no
  snap-back; the i4 dip matches run-7b's own early-consolidation shape.
- **The decision read (2,000 games, `final_read` protocol, seeds 20260710 =
  fully paired with the baseline read):** iter-009 **raw 0.5230 ± 0.0112 /
  corrected 0.5233 ± 0.0110**; paired vs `run7b-i14` on the same seeds:
  **+1.15pp ± 0.90 (t=1.28, 174 up / 151 down)** — a directionally-positive
  tie, not outside noise. Ante ledger zero-mean on both arms (opener
  game-sum t=1.19, draw t=1.06).

## Decision

- **Verdict: the heuristic got stronger — that is the dominant mechanism of
  the −4.09pp re-baseline.** Opponent-specific fit was the *recoverable*
  hypothesis and it predicted fast recovery (the §6c precedent: behavioral
  re-fit lands in ~5 iterations, and indeed veto re-fit did). Ten
  iterations bought +1.15 ± 0.90 — a crawl consistent with ADR-0024's
  ceiling-grind regime, not a snap-back. Any residual opponent-fit
  component is ≲1pp and not cheaply separable.
- **The M4 baseline stands at 0.5121; checkpoint of record UNCHANGED
  (`d6-run7b/iter-014`).** Iter-009 does not meet the promotion bar
  (outside-noise paired supersession). D3's gate remains: beat the
  checkpoint of record outside noise on the standing paired 2,000-game
  corrected read.
- **`d6-run9/iter-009` = the designated init candidate for D3 runs** — new-
  engine-adapted, veto-clean (first-attempt 0.0817, the lowest read to
  date), directionally positive; the run-5→run-6 init pattern repeated.
- **The probe doubles as a fresh confirmation of the M4 premise on the new
  engine:** the standing recipe, given 10 healthy iterations against the
  new opponent, moved ~1pp inside noise. The absent-signal diagnosis
  (ADR-0024) carries over to the rebased platform unchanged — the next
  capability comes from a different signal source, which is exactly what
  D2/D3 build.
- **M4 done-when #1 is SATISFIED** (probe run under guards + paired read +
  this ADR). Next: D2.1 — regenerate early-doom/curation on the closing-
  read stores (`run9-finalarm-s{0,1}`, obs on, 2,000 games; use the probe's
  own critic `d6-run9/iter-009/critic` for traces — new-engine-trained).

## Price and caveats

~5.5h GPU overnight (10 iterations ≈ 5.3h) + ~2h read. Caveat recorded
honestly: 10 iterations cannot exclude a slow-grind recovery that a
30-iteration run might compound — but that is the ceiling-grind ADR-0024
already priced at ~flat-to-negative, and the fast-recovery hypothesis is
what the probe was designed to test. It resolved negative. The draw-poison
skip count in the Ante ledger (17,705 nodes) restates the known 69%
coverage item — queued with the next critic retrain, unchanged.
