"""ADR-0124: the anchor's draw budget, the memorization meter's split and its pause line."""

import numpy as np

from anvil.training.selfplay import anchor_gap_pause
from anvil.training.value_pretrain import eval_split_rows

META = [{"holdout": i % 5 == 0} for i in range(50)]


def test_eval_splits_partition_the_bank_and_the_train_sample_is_fixed():
    ho, tr, al = (eval_split_rows(META, s, 0) for s in ("holdout", "train", "all"))
    assert len(ho) == 10 and len(tr) == 40 and len(al) == 50
    assert not set(ho) & set(tr) and set(ho) | set(tr) == set(al)
    a = eval_split_rows(META, "train", 8, seed=3)
    b = eval_split_rows(META, "train", 8, seed=3)
    assert len(a) == 8 and a.tolist() == b.tolist() and not set(a) & set(ho)
    assert eval_split_rows(META, "train", 8, seed=4).tolist() != a.tolist()
    assert np.all(np.diff(a) > 0)  # sorted, a stable row order


def test_eval_split_is_loud_on_an_unknown_name():
    import pytest

    with pytest.raises(ValueError):
        eval_split_rows(META, "test")


def test_pause_line_fires_above_the_line_and_only_once_per_level():
    assert anchor_gap_pause(None, 0.15, None) is None  # no meter
    assert anchor_gap_pause(0.3, 0, None) is None  # off
    assert anchor_gap_pause(0.14, 0.15, None) is None
    assert anchor_gap_pause(0.16, 0.15, None).startswith("pause line: anchor memorization gap 0.16 > 0.15")
    # paused at 0.16: the line sits at 0.21 until the gap grows past it
    assert anchor_gap_pause(0.20, 0.15, 0.16) is None
    r = anchor_gap_pause(0.22, 0.15, 0.16)
    assert r and "re-based to 0.21" in r
