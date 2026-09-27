"""ADR-0120: the Constructed model row. A new format column inserts at the
one-hot's END, before the Build 4 scalars; every older globals layout maps
through one column map (transform.widen_globals_columns) shared by the
checkpoint pad (model.pad_state_proj) and the bank widening
(value_pretrain.widen_globals), so pre-change checkpoints project the same
outputs on the same states — the identity proof the onboarding checklist
asks for — and a Constructed header featurizes to its own row."""

import pytest
import torch

from anvil.encoder.transform import (
    FORMAT_SCALARS,
    GLOBAL_FEATURES,
    GLOBAL_SCALE,
    N_FORMAT_ONEHOT,
    N_GLOBAL_BASE,
    PLAYER_FEATURES,
    Vocab,
    assemble,
    globals_layout,
    widen_globals_columns,
)
from anvil.policy.model import pad_state_proj
from tests.test_transform import _dec, _header

N_SC = len(FORMAT_SCALARS)
N_PL = 2 * len(PLAYER_FEATURES)


def test_layout_constants():
    assert GLOBAL_FEATURES[N_GLOBAL_BASE:N_GLOBAL_BASE + N_FORMAT_ONEHOT] == ["fmt_commander", "fmt_constructed"]
    assert GLOBAL_FEATURES[-N_SC:] == ["format_" + k for k in FORMAT_SCALARS]
    assert len(GLOBAL_SCALE) == len(GLOBAL_FEATURES)
    assert Vocab().formats == {"Commander": 0, "Constructed": 1}


def test_globals_layout_reads_every_era_and_is_loud_otherwise():
    b = N_GLOBAL_BASE
    assert globals_layout(b) == (b, 0, False)  # M1–M8
    assert globals_layout(b + 1) == (b, 1, False)  # M9: the Commander one-hot
    assert globals_layout(b + 1 + N_SC) == (b, 1, True)  # Build 4: + the scalars
    assert globals_layout(len(GLOBAL_FEATURES)) == (b, N_FORMAT_ONEHOT, True)  # today
    with pytest.raises(ValueError):
        globals_layout(b - 1)
    with pytest.raises(ValueError):
        globals_layout(b + N_FORMAT_ONEHOT + N_SC + 1)  # wider than today
    with pytest.raises(ValueError):
        globals_layout(b + N_SC)  # five one-hots and no scalars: no era produced it


@pytest.mark.parametrize("saved_g", [N_GLOBAL_BASE, N_GLOBAL_BASE + 1, N_GLOBAL_BASE + 1 + N_SC])
def test_pad_state_proj_is_an_identity_on_saved_inputs(saved_g):
    """A pre-change checkpoint's state projection, re-laid onto today's
    columns, projects a saved-layout input mapped through the same column
    map to the SAME output; the new format column's weights are zero."""
    g = torch.Generator().manual_seed(saved_g)
    n_cur = len(GLOBAL_FEATURES)
    saved_w = torch.randn(6, saved_g + N_PL, generator=g)
    cur_w = torch.randn(6, n_cur + N_PL, generator=g)
    padded = pad_state_proj(cur_w, saved_w, n_cur)
    cols = widen_globals_columns(saved_g)
    x = torch.randn(saved_g + N_PL, generator=g)
    x_new = torch.zeros(n_cur + N_PL)
    x_new[cols] = x[:saved_g]
    x_new[n_cur:] = x[saved_g:]
    assert torch.allclose(saved_w @ x, padded @ x_new, atol=1e-6)
    new_cols = sorted(set(range(n_cur)) - set(cols))
    assert (padded[:, new_cols] == 0).all()
    assert GLOBAL_FEATURES.index("fmt_constructed") in new_cols
    # the Build 4 scalars' saved weights moved past the new column
    if saved_g == N_GLOBAL_BASE + 1 + N_SC:
        assert torch.equal(padded[:, n_cur - N_SC:n_cur], saved_w[:, saved_g - N_SC:saved_g])


def test_constructed_header_featurizes_to_its_own_row():
    h = _header()
    h["fmt"] = "Constructed"
    g = assemble(_dec([]), h)["globals"]
    b = N_GLOBAL_BASE
    assert g[b:b + N_FORMAT_ONEHOT].tolist() == [0.0, 1.0]
    sc = g[-N_SC:].tolist()
    assert sc == pytest.approx([20 / 40, 60 / 100, 0.0, 0.0, 1.0])
    gc = assemble(_dec([]), _header())["globals"]
    assert gc[b:b + N_FORMAT_ONEHOT].tolist() == [1.0, 0.0]
    assert gc[-N_SC:].tolist() == pytest.approx([40 / 40, 100 / 100, 1.0, 1.0, 1.0])
    assert gc[:b].tolist() == g[:b].tolist()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA")
def test_pad_state_proj_takes_a_cpu_state_onto_a_cuda_net():
    n_cur = len(GLOBAL_FEATURES)
    saved_w = torch.randn(3, n_cur - 1 + N_PL)
    cur_w = torch.randn(3, n_cur + N_PL, device="cuda")
    out = pad_state_proj(cur_w, saved_w, n_cur)
    assert out.device.type == "cuda" and out.shape == cur_w.shape
