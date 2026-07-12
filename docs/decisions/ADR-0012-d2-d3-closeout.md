# ADR-0012: M2 D2/D3 closeout — SA-level schema at agreement parity, arms tied, order rung retired; the "winrate leak" resolves as an action-identity gain, not a winrate gain

- **Date:** 2026-07-11
- **Status:** accepted
- **Design-doc anchor:** m2-rl-plan D2/D3 + done-when #2; ADR-0010 (the
  sequencing bet this resolves); ADR-0009 (the 46.8% baseline and the
  31–36% order-rung measurement)

## Context

ADR-0010 moved the SA-level action schema ahead of RL on two arguments: the
executor's order rung decided 31–36% of play-time casts by scan order ("the
largest known winrate leak"), and RL needs SA-level action identity
regardless. The plan priced the label side pessimistically: sa-string join
recovers ~69% of multi-SA cases, ~31% masked.

## Decision

**D2 and D3 are CLOSED.** Results, in the order the plan asked for them:

- **Labels (full-corpus sweep, 113,592 games / 6.11M casts):** candidates =
  (host row, normalized SA) pairs with identical keys collapsed; labels
  resolve oi → exact string → prefix-min. **99.92% exact + 0.08% prefix;
  masked = 228 casts (0.004%)** — the plan's ~31% "ambiguous" mass was a
  measurement artifact (option-vs-option matching on 60-char truncated
  strings, no candidate collapse). The ambiguity class is identical-string
  duplicates (permission routes, same-rendering cost variants), which
  collapse into one candidate: the model cannot distinguish identical
  descriptors, so nothing is lost; the executor keeps first-fit for the
  engine-side tie. Record: `data/training/d2-sa-label-measure-full.json`;
  pinned vocab `anvil/training/sa_vocab_v1.json` (33,691 strings, held-out
  OOV 0.03–0.05%, never regenerate in place).
- **Retrain (d2-sa, 774K steps / 15.1h, D7 recipe verbatim): agreement
  parity.** Honest 0.9748 SA-basis / **0.9751 host-basis vs 0.9758** (run
  noise); nonpass 0.9247 on the strictly harder name-the-SA basis; targets
  0.9769; mulligan 0.9969; value at its floor (0.573); valpair ≥ val
  throughout; n_masked = 1 per 600 eval batches. X head 0.852 vs 0.874
  full-val basis (−2.2pp, ~1.7σ — watch). Fresh calibration: δ=+2.180
  rate-matches (D7's +2.169 structure reproduced almost exactly — the pass
  boundary is a corpus+recipe property, not an architecture property).
- **Arms (same 200 valpair pairs, same seeds as D8 — paired comparison;
  400 games/arm):**

  | arm | winrate | veto rate | order rung |
  |---|---|---|---|
  | D8 δ=0 (host-level) | 0.4675 ± 0.0249 | 7.8% | 4,141 casts (31%) |
  | **D3 δ=0 (SA-level)** | **0.4625 ± 0.0249** | 10.0% | **0** |
  | D8 δ=+2.169 | 0.4550 ± 0.0249 | 3.1% | 5,004 (36%) |
  | **D3 δ=+2.180** | **0.4400 ± 0.0248** | 5.3% | **0** |

  800/800 decisive, **0 crashes** (D8: 0.5%), 0 transport failures, 0 server
  fallbacks (117K requests, 67 rps). Rungs read `single` + `modal` only —
  the order and kind rungs retired from live play exactly as designed.
  δ=0 ≥ calibrated again: the RL init stays action-rich.

## The headline resolution

**The order-rung mass did not cash out as winrate: δ=0 is a statistical tie
with D8 (−0.5pp at SE 2.5pp).** Two mechanisms, both now measured: the
ladder's kind-prior first-fit was evidently a good proxy for the model's
intent on most multi-SA hosts; and the SA-level answer forfeits the ladder's
rescue (a host-level pick with an unpayable SA used to get rescue-cast as a
payable sibling; an exact SA pick vetoes to pass instead — veto rate
7.8%→10.0%, casts/game 33.5→26.8). What D2/D3 actually bought, per
ADR-0010's second argument: **the model now owns action identity** — the RL
prerequisite — with exact labels, meaningful per-SA veto decomposition, and
zero agreement cost. The "largest known winrate leak" framing is retired;
recoverable-winrate attention moves to the veto class (model payability
errors, ~10% of cast attempts, no rescue) and the still-heuristic
modal/combat surfaces.

## Consequences

- m2-rl-plan done-when #2 is satisfied (SA checkpoint on both bases, arms
  repriced, order rung retired). **Next: D4** (rollout-labeled critic +
  Ante certification) from `d2-sa/last.pt`.
- `d2-sa/last.pt` = checkpoint of record; RL init = d2-sa at δ=0.
- The +2.2pp veto increase is the new named leak candidate; it is smaller
  than the retired rung's mass and queues behind D4/D6 unless RL telemetry
  elevates it. Candidate lever if elevated: payability-aware masking at
  serve (the engine knows unpayable; the candidate mask stays timing-legal
  per ADR-0005 for training, but serve-time re-ask on veto is protocol-legal).
- X overflow clamp fired on 0.4% of calibrated-arm casts (40/11,136) vs the
  3-per-100K corpus estimate — the model over-predicts the ">16" bucket in
  play; watch during D6, revisit the 2026-07-10 clamp decision if it shows
  up in blunders.
- `scripts/arms_report.py` formalizes the arms aggregation (validated by
  reproducing the D8 report exactly); the standing per-checkpoint eval is
  now: server on ckpt → 2 mirrored arms → arms_report vs the D8/D3 rows.

## Addendum (same day): the pre-RL scope rule

Discussion after the close-out generalized the result into three plan
amendments (m2-rl-plan decisions #8/#11/#12 + reordered D4/D5 text):

1. **The BC stage is finished as a strength program.** Imitation is at its
   teacher-clone ceiling with clean execution; the mass-implies-leak
   inference is retired. From here to D6, pre-RL work is justified only by
   (a) expressiveness RL needs, (b) label/observation correctness, or
   (c) eval sharpness — never by projected BC winrate. Arms demote from
   goal to instrument (regression tripwire before RL, progress meter during).
2. **D5 combat constructs become a hard prerequisite for D6** (RL cannot
   learn combat it cannot express; its BC arms will predictably tie and
   that is not a failure signal).
3. **Ante certification moves to the front of D4** (eval resolution is now
   the binding constraint on all subsequent decisions; the certified arm is
   an afternoon and sharpens everything after it).

Instrumental caveats recorded so "don't worry about BC competence" is not
over-read: the BC checkpoint remains the RL init (what matters: agreement,
coverage, action identity, calibrated pass boundary — not winrate) and the
D4 label generator (what matters: sanity + determinism, both certified in
D1). The arms keep running per checkpoint as the tripwire for pathological
regressions at unchanged winrate.
