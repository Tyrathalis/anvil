"""V-trace target math (M2 D6) — pure unit tests, no local data needed."""

import torch

from anvil.training.rl import vtrace_targets


def test_on_policy_reduces_to_monte_carlo():
    """rho == c == 1, gamma 1, terminal-only reward: vs telescopes to the
    return at every step; advantage sign follows (return - V)."""
    v = torch.tensor([0.5, 0.6, 0.7])
    lp = torch.zeros(3)
    vs, adv, rho = vtrace_targets(v, lp, lp, reward=1.0)
    assert torch.allclose(vs, torch.ones(3))
    assert torch.allclose(rho, torch.ones(3))
    assert (adv > 0).all()
    vs0, adv0, _ = vtrace_targets(v, lp, lp, reward=0.0)
    assert torch.allclose(vs0, torch.zeros(3))
    assert (adv0 < 0).all()


def test_calibrated_values_zero_advantage():
    lp = torch.zeros(3)
    _, adv, _ = vtrace_targets(torch.ones(3), lp, lp, reward=1.0)
    assert adv.abs().max() < 1e-6
    _, adv0, _ = vtrace_targets(torch.zeros(3), lp, lp, reward=0.0)
    assert adv0.abs().max() < 1e-6


def test_off_policy_clipping_shrinks_corrections():
    """pi far below mu: rho ~ 0 — targets stay near V (no correction is
    trusted), never explode."""
    v = torch.tensor([0.5, 0.6, 0.7])
    lp = torch.zeros(3)
    vs, _, rho = vtrace_targets(v, lp - 3.0, lp, reward=1.0)
    assert (rho < 0.06).all()
    assert (vs - v).abs().max() < 0.2


def test_rho_clipped_at_rho_bar():
    v = torch.full((4,), 0.5)
    lp = torch.zeros(4)
    _, _, rho = vtrace_targets(v, lp + 2.0, lp, reward=1.0, rho_bar=1.0)
    assert torch.allclose(rho, torch.ones(4))


def test_draw_scores_zero_for_both_seats():
    """§3d cap-aware rule as used by the loader: draw/cap reward is 0 — the
    stalling leader's vs targets sink toward 0, same as a loss."""
    v = torch.tensor([0.9, 0.9])  # a 'winning' board that stalls out
    lp = torch.zeros(2)
    vs, adv, _ = vtrace_targets(v, lp, lp, reward=0.0)
    assert torch.allclose(vs, torch.zeros(2))
    assert (adv < 0).all()
