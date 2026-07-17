# Run-3 iter-013 veto forensics — what a 41%-veto policy tries to cast

2026-07-17. M3-plan input (ADR-0019 named veto drift the open front). Data:
census of `d6-run3-i013` (the guard-rejected iteration, 480 games) vs
`d6-run3-i000` (baseline, same run).

## Profile

| | iter-000 | iter-013 |
|---|---|---|
| vetoes / casts | 9,007 / 26,889 (25.1%) | 18,528 / 26,368 (41.3%) |
| `unpayable` | 6,164 (68% of vetoes) | 14,113 (**76%**) |
| `no_shape_fit` | 2,051 | 3,250 |
| others (dangling/restrictions/timing) | ~790 | ~1,165 |
| re-ask chains ≥4 | 30 | 227 (cap 8 held) |

The drift is overwhelmingly **`unpayable`** (+129%); every other class grew
sub-linearly with it. The policy increasingly wants things it cannot afford.

## The commander-tax finding

Top vetoed cards are dominated by **commanders** (Spider-Man 2099, Ertai
Resurrected, Phelia, Light-Paws, Black Panther, Tifa Lockhart, Yoshimaru)
plus a counterspell-hold cluster. Discriminator: splitting each commander's
vetoed casts by whether that card had already resolved a cast earlier in the
same game (i.e. commander tax active):

- **73% of commander vetoes occur post-first-cast** (1,942 vs 710), and the
  per-card ratios are stark where tax bites hardest: Ertai 352 post / 64
  pre, Phelia 293/37, Light-Paws 286/28, Tifa 184/21.

**Hypothesis (strong): the observation does not carry commander tax**, so
the model prices recasts at printed cost. BC never exposed this — the
heuristic teacher checks payability before proposing, so the corpus contains
no counterexamples — and RL exploration walks straight into the gap. The
drift is then partly *rational* under the model's beliefs: it wants its
commander back and cannot see why that fails, and V-trace only prices the
opportunity cost of the wasted window (a re-ask pass), a weak gradient.

## Implications for the M3 lever choice

1. **Feature fix first**: surface tax-adjusted commander cost (or cast
   count) in the observation. Verify obs coverage: cast count is derivable
   from history for the reader — if so, no regeneration; loader/featurizer
   + serve change only. This attacks the *cause*; reward penalties attack
   the symptom.
2. **Reward veto penalty** remains the general lever for the non-commander
   remainder (~⅓ of the drift: counterspell holds, generic unpayables) —
   needs its §3d pin; size it small (the wasted-window cost is already
   implicitly priced, the penalty is a sharpener).
3. The counterspell-hold cluster deserves its own look before penalizing:
   holding up counter mana and being wrong is arguably *strategy learning in
   progress*, not pathology — a penalty could suppress instinct formation.
4. First-attempt veto rate (excluding re-ask chains) should become the
   monitored quantity either way — chains inflate the current metric.
