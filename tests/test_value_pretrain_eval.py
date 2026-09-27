"""The state-ranking eval path (value_pretrain eval; ADR-0118): the bank's
iter-019-era examples widen to a Build 4 net's globals with the vocab's
format scalars, loud on any other width; Spearman is rank-only."""

import numpy as np
import pytest
import torch

from anvil.encoder.transform import (
    FORMAT_SCALARS,
    GLOBAL_FEATURES,
    N_FORMAT_ONEHOT,
    N_GLOBAL_BASE,
    Vocab,
)
from anvil.training.value_pretrain import spearman, widen_globals


def _ex(width: int) -> dict:
    return {"globals": torch.arange(width, dtype=torch.float32), "label": torch.tensor(0)}


def test_widen_globals_from_the_iter019_era():
    """base + the Commander one-hot -> today's layout: newer one-hot columns
    zero, the format scalars filled from the vocab's row."""
    b = N_GLOBAL_BASE
    old = b + 1
    exs = [_ex(old), _ex(old)]
    out = widen_globals(exs, len(GLOBAL_FEATURES), "Commander")
    assert len(out) == 2 and out[0]["globals"].shape[0] == len(GLOBAL_FEATURES)
    g = out[0]["globals"]
    assert g[:old].tolist() == exs[0]["globals"].tolist()
    assert g[old:b + N_FORMAT_ONEHOT].tolist() == [0.0] * (N_FORMAT_ONEHOT - 1)
    assert g[b + N_FORMAT_ONEHOT:].tolist() == Vocab().format_scalars("Commander")
    assert exs[0]["globals"].shape[0] == old  # the bank is not mutated


def test_widen_globals_from_a_build4_bank_keeps_its_scalars():
    b = N_GLOBAL_BASE
    old = b + 1 + len(FORMAT_SCALARS)
    g = widen_globals([_ex(old)], len(GLOBAL_FEATURES), "Commander")[0]["globals"]
    assert g[:b + 1].tolist() == list(range(b + 1))
    assert g[b + 1:b + N_FORMAT_ONEHOT].tolist() == [0.0] * (N_FORMAT_ONEHOT - 1)
    assert g[-len(FORMAT_SCALARS):].tolist() == list(range(b + 1, old))  # the saved scalars, moved


def test_widen_globals_is_identity_at_width_and_loud_otherwise():
    n = len(GLOBAL_FEATURES)
    exs = [_ex(n)]
    assert widen_globals(exs, n, "Commander") is exs
    with pytest.raises(ValueError):
        widen_globals([_ex(n + 1)], n, "Commander")
    with pytest.raises(ValueError):
        widen_globals([_ex(N_GLOBAL_BASE + len(FORMAT_SCALARS))], n, "Commander")  # no such era


def test_spearman_is_rank_only():
    y = np.array([0.1, 0.4, 0.2, 0.9])
    assert spearman(y, y) == pytest.approx(1.0)
    assert spearman(y * 100 + 3, y) == pytest.approx(1.0)
    assert spearman(-y, y) == pytest.approx(-1.0)
