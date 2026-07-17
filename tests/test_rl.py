"""V-trace target math + ADR-0017 guard/hinge units (M2 D6) — pure unit
tests, no local data needed."""

import torch

from anvil.training.rl import entropy_hinge, vtrace_targets
from anvil.training.selfplay import guard_flags


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


def test_entropy_hinge_zero_gradient_above_floor():
    """ADR-0017: entropy above the floor must contribute exactly zero loss
    AND zero gradient — the always-on bonus's constant upward pressure was
    run-2's root cause. A sign error here recreates the runaway."""
    ent = torch.tensor([0.15, 0.20, 0.25], requires_grad=True)
    pen = entropy_hinge(ent, floor=0.08, b=3, t_len=3)
    assert pen.item() == 0.0
    pen.backward()
    assert torch.all(ent.grad == 0)


def test_entropy_hinge_pushes_up_below_floor():
    """Below the floor the penalty is positive and its gradient DECREASES
    with entropy (d pen / d ent < 0), i.e. gradient DESCENT on the loss
    raises entropy — the collapse-guard direction."""
    ent = torch.tensor([0.01, 0.02], requires_grad=True)
    pen = entropy_hinge(ent, floor=0.08, b=2, t_len=2)
    assert pen.item() > 0
    pen.backward()
    assert torch.all(ent.grad < 0)


def _rl_of(kl, ent):
    return {"mean": {"kl_mu": kl, "ent": ent}}


BASE = {"ent": 0.18, "veto_rate": 0.237}  # run-2's actual iter-0 point


def test_guards_quiet_on_healthy_iterations():
    """run-2 iters 0-2 shaped inputs: no guard fires (kl <= 0.019,
    ent/veto within multiples)."""
    assert guard_flags({"veto_rate": 0.31}, _rl_of(0.019, 0.218), BASE) == []
    assert guard_flags({"veto_rate": 0.237}, _rl_of(0.009, 0.183), None) == []


def test_guards_would_have_halted_run2():
    """run-2's actual iter-3 and iter-4 monitor numbers: iter 3 almost trips
    kl (0.047 < 0.05 — the drift was one iteration from the line); iter 4
    trips all three."""
    assert guard_flags({"veto_rate": 0.345}, _rl_of(0.047, 0.254), BASE) == []
    flags = guard_flags({"veto_rate": 0.613}, _rl_of(1.067, 0.86), BASE)
    assert len(flags) == 3, flags


def test_guard_kl_is_absolute_no_baseline_needed():
    flags = guard_flags({}, _rl_of(0.06, None), None)
    assert len(flags) == 1 and "kl_mu" in flags[0]


def test_draw_scores_zero_for_both_seats():
    """§3d cap-aware rule as used by the loader: draw/cap reward is 0 — the
    stalling leader's vs targets sink toward 0, same as a loss."""
    v = torch.tensor([0.9, 0.9])  # a 'winning' board that stalls out
    lp = torch.zeros(2)
    vs, adv, _ = vtrace_targets(v, lp, lp, reward=0.0)
    assert torch.allclose(vs, torch.zeros(2))
    assert (adv < 0).all()


def test_census_first_attempt_veto_basis(tmp_path):
    """M3 D1: first_veto_rate counts one attempt per window (no reask field),
    so re-ask chains inflate veto_rate but not the first-attempt basis."""
    import json as _json

    from anvil.training.selfplay import _census_tallies

    wd = tmp_path / "workers" / "inv-000"
    wd.mkdir(parents=True)
    m = "chooseSpellAbilityToPlay"
    lines = [
        # window A: clean first-attempt cast
        {"by": "bridge", "m": m, "pick": "Bolt"},
        # window B: first attempt vetoed, rescued on attempt 2 (chain of 3)
        {"by": "bridge", "m": m, "pick": "Ertai", "veto": "unpayable"},
        {"by": "bridge", "m": m, "pick": "Ertai", "veto": "unpayable", "reask": 1},
        {"by": "bridge", "m": m, "pick": "Ring", "reask": 2},
        # window C: model-chosen pass on first attempt
        {"by": "bridge", "m": m, "pick": "pass"},
    ]
    (wd / "census.jsonl").write_text("\n".join(_json.dumps(r) for r in lines) + "\n")

    c = _census_tallies(tmp_path)
    assert c["veto"] == 2 and c["cast"] == 2 and c["reask_rescued"] == 1
    assert c["veto_rate"] == 0.5           # chain-inflated: 2/(2+2)
    assert c["first_veto"] == 1 and c["first_cast"] == 1
    assert c["first_veto_rate"] == 0.5     # here equal by construction...

    # ...but a longer re-veto chain moves ONLY the chain-inflated rate
    lines += [{"by": "bridge", "m": m, "pick": "X", "veto": "no-fit", "reask": k}
              for k in range(1, 5)]
    (wd / "census.jsonl").write_text("\n".join(_json.dumps(r) for r in lines) + "\n")
    c2 = _census_tallies(tmp_path)
    assert c2["veto_rate"] == 0.75         # 6/(6+2)
    assert c2["first_veto_rate"] == 0.5    # unchanged
