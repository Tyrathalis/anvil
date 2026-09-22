"""The target term's NaN guard (09-22, Kryptic's finding): cross-entropy with
ignore_index over a batch with NO labelled rows is NaN under reduction="mean";
the guard returns zero, and matches F.cross_entropy on the labelled subset."""

from __future__ import annotations

import torch
import torch.nn.functional as F

from anvil.policy.model import masked_cross_entropy


def test_all_ignored_batch_is_zero_not_nan():
    logits = torch.randn(6, 5, requires_grad=True)
    labels = torch.full((6,), -1, dtype=torch.long)
    raw = F.cross_entropy(logits, labels, ignore_index=-1)
    assert torch.isnan(raw)  # the failure Kryptic saw
    guarded = masked_cross_entropy(logits, labels)
    assert guarded.item() == 0.0 and torch.isfinite(guarded)


def test_matches_cross_entropy_on_the_labelled_subset():
    logits = torch.randn(6, 5)
    labels = torch.tensor([2, -1, 0, -1, 4, 1])
    expect = F.cross_entropy(logits[labels >= 0], labels[labels >= 0])
    assert torch.allclose(masked_cross_entropy(logits, labels), expect)
