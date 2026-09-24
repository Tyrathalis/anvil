"""The state-ranking eval path (value_pretrain eval; ADR-0118): the bank's
iter-019-era examples widen to a Build 4 net's globals with the vocab's
format scalars, loud on any other width; Spearman is rank-only."""

import numpy as np
import pytest
import torch

from anvil.encoder.transform import FORMAT_SCALARS, GLOBAL_FEATURES, Vocab
from anvil.training.value_pretrain import spearman, widen_globals


def _ex(width: int) -> dict:
    return {"globals": torch.arange(width, dtype=torch.float32), "label": torch.tensor(0)}


def test_widen_globals_appends_the_format_scalars():
    old = len(GLOBAL_FEATURES) - len(FORMAT_SCALARS)
    exs = [_ex(old), _ex(old)]
    out = widen_globals(exs, len(GLOBAL_FEATURES), "Commander")
    assert len(out) == 2 and out[0]["globals"].shape[0] == len(GLOBAL_FEATURES)
    assert out[0]["globals"][:old].tolist() == exs[0]["globals"].tolist()
    assert out[0]["globals"][old:].tolist() == Vocab().format_scalars("Commander")
    assert exs[0]["globals"].shape[0] == old  # the bank is not mutated


def test_widen_globals_is_identity_at_width_and_loud_otherwise():
    n = len(GLOBAL_FEATURES)
    exs = [_ex(n)]
    assert widen_globals(exs, n, "Commander") is exs
    with pytest.raises(ValueError):
        widen_globals([_ex(n + 1)], n, "Commander")
    with pytest.raises(ValueError):
        widen_globals([_ex(n - 1)], n, "Commander")


def test_spearman_is_rank_only():
    y = np.array([0.1, 0.4, 0.2, 0.9])
    assert spearman(y, y) == pytest.approx(1.0)
    assert spearman(y * 100 + 3, y) == pytest.approx(1.0)
    assert spearman(-y, y) == pytest.approx(-1.0)
