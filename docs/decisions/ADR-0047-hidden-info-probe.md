# ADR-0047: Full-vis-vs-masked unfreeze probe — hidden information is NOT the residual; belief head deprioritized for ranking

- **Date:** 2026-08-08
- **Status:** accepted
- **Design-doc anchor:** §4 (belief head, omniscient-critic tier)
- **Inputs:** [ADR-0046](ADR-0046-label-campaign-resolution.md) (queued
  this probe as the last unpriced axis), [ADR-0044](ADR-0044-b2-unfreeze-probe-verdict.md)
  (masked numbers of record), `data/runs/unfreeze-probe-fullvis/`
  (numbers of record), ADR-0039 (the d4 full-vis trunk's frozen-probe
  under-ranking — the prior data point this replicates).

## Question

The rollout labels are generated from the TRUE game state (forks carry
the opponent's actual hand), while our critic evaluates masked windows —
so an unknown slice of the 0.48→0.9 residual could be information a
masked observer simply cannot have. Price it: identical N=4/N=0
fine-tunes on `labelset-c2-v3`, identical split and frozen holdout, with
windows assembled full-vis (ValueEvaluator caller override — a value
instrument only, never a policy input).

## Findings (3 seeds each, vs the masked numbers of record)

| cell | masked | full-vis |
|---|---|---|
| N=0 (head only) | 0.4693 ± 0.0018 | 0.4664 ± 0.0041 |
| N=4 | **0.4829 ± 0.0010** | 0.4790 ± 0.0022 |

1. **Zero gain from omniscience, at either capacity.** If anything a
   hair lower (off-distribution inputs for a masked-trained trunk: the
   un-tuned head reads 0.280 full-vis vs 0.335 masked; the fine-tune
   recovers the gap and then finds nothing extra in the revealed hand).
2. Consistent with ADR-0039's independent observation (the d4 critic —
   full-vis-trained at scale — under-ranks the masked policy trunk).
   Caveat recorded honestly: a masked-trained trunk given full-vis
   windows is not the same as a trunk trained full-vis from scratch at
   this objective; but the d4 data point covers that flank.
3. **The elimination chain is now:** not state arithmetic (ADR-0043),
   not card function (ADR-0045), not hidden information (this), not
   label count at current slope (ADR-0046: ~+0.006/doubling), partially
   gradient-reachable (ADR-0044/0046: 0.4829 and rising slowly). What
   remains for the 0.48→0.9 gap: deeper capacity / the B-3 encoder
   swap, or the possibility that loss-adjacent Commander positions are
   not rankable to 0.9 by ANY static evaluation — the tier-3 search
   argument (rollouts SEARCH; a static head cannot).

## Decisions

1. **The belief head earns no priority from ranking** — its §4
   motivations (bluff modeling, information-value plays) stand on their
   own timeline, but "the critic is blind because it can't see hands"
   is now measured false.
2. **The graduated build proceeds on the MASKED path at N=4**
   (full-vis buys nothing and masked keeps serve parity trivial).
3. **The static-evaluation-ceiling hypothesis is promoted to a named
   question** for the M6 closeout: if the graduated build's paired read
   lands, the next representation conversation should weigh tier-3
   search (critic-scored leaves — planning as the ranking mechanism)
   against B-3 encoder work, with this ADR as evidence that more input
   information is not the constraint.
