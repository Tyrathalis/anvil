"""ADR-0088 fixed-batch application mechanics.

The m10-probe2 read (ADR-0087) named a loop-wide defect: ADR-0057
calibrate-then-freeze is unsound for a fixed small batch applied every
optimizer step — the batch is memorized in ~10 applied steps, the full
frac-scale mass lands on the shared trunk as an impulse, and the share
guard is structurally blind (share decays WITH the fit). Both fixed-batch
terms show the signature in the banked probe data (seedlab raw 2.73 ->
0.42 in ~10 steps at frac 0.1; paylab raw 0.99 -> 0.23 in the same
window), and per-invocation recalibration amplifies it across iterations
(probe1 w_seedlab grew 12x over three iterations as raw fell on the
partially-fitted batch).

The fix set (all mechanics here are generic to any fixed label batch):
- ChunkSampler: apply ONE k-window chunk per optimizer step, chunk order
  reshuffled per epoch (without replacement) — no step sees a fittable
  batch, and memorization is slower than the iteration by construction.
- warmup_scale: linear ramp on the applied weight over the first N
  applied steps — spreads whatever impulse survives subsampling.
- Cross-iteration: the loop's carry-w convention (calibrate once at
  iteration 0 against the honest day-zero raw, carry via loop_state) —
  recalibrating against a partially-fitted batch is the amplifier.
- The memorization tripline itself lives in selfplay.guard_flags
  (first-window raw vs raw-at-calibration).
"""

from __future__ import annotations

import random


class ChunkSampler:
    """Per-step subsampling of a fixed label batch: yields one collated
    chunk per call, cycling all chunks without replacement, reshuffling
    each epoch. Deterministic from the seed (the run's seed convention)."""

    def __init__(self, segs: list, seed: int):
        if not segs:
            raise ValueError("ChunkSampler needs a non-empty seg list")
        self.segs = segs
        self._rng = random.Random(seed)
        self._order: list[int] = []
        self._i = 0

    def next(self) -> list:
        """One chunk, as a single-element seg list (the *_pass contract)."""
        if self._i >= len(self._order):
            self._order = list(range(len(self.segs)))
            self._rng.shuffle(self._order)
            self._i = 0
        seg = self.segs[self._order[self._i]]
        self._i += 1
        return [seg]


def warmup_scale(applied_steps: int, warmup: int) -> float:
    """Linear 0->1 ramp over the first `warmup` applied steps; 1.0 when
    warmup is 0/disabled. `applied_steps` counts steps the term has been
    APPLIED (post-calibration), not optimizer steps since run start."""
    if warmup <= 0:
        return 1.0
    return min(1.0, (applied_steps + 1) / warmup)
