"""M12 Build 4½ — the loop wiring's driver side (selfplay.py): the recipe's
forge args, the acting bar, the allocation tau from the serving ckpt, the
search-term guards. ADR-0113."""

import types

import torch

from anvil.training.selfplay import (
    alloc_tau_of,
    ckpt_carries,
    guard_flags,
    sched_carry_flags,
    search_bar,
    search_forge_args,
)

RECIPE = "-search -searchrate 1 -searchrolls 2 -searchact 0.10 -searchtemp 0.025"


def _args(**kw):
    base = {"search_recipe": RECIPE, "search_alloc": "head", "search_floor": 0.1, "search_bar": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_search_bar_parses_the_recipe_and_honours_the_override():
    assert search_bar(_args()) == 0.10
    assert search_bar(_args(search_recipe="-search -searchact 0.05")) == 0.05
    assert search_bar(_args(search_recipe="-search")) == 0.10
    assert search_bar(_args(search_bar=0.2)) == 0.2


def test_search_forge_args_off_without_a_recipe():
    assert search_forge_args(_args(search_recipe=""), "x.pt") == []


def test_search_forge_args_appends_the_serving_ckpts_tau(tmp_path):
    fitted = tmp_path / "fitted.pt"
    torch.save({"model": {}, "config": {"alloc_fit": {"tau": 0.369}}}, fitted)
    bare = tmp_path / "bare.pt"
    torch.save({"model": {}, "config": {}}, bare)
    assert alloc_tau_of(str(fitted)) == 0.369
    assert alloc_tau_of(str(bare)) is None
    fa = search_forge_args(_args(), str(fitted))
    assert fa[: len(RECIPE.split())] == RECIPE.split()
    assert fa[-4:] == ["-searchalloc", "0.36900", "-searchfloor", "0.1"]
    # no record = the uniform rate; alloc off = the uniform rate
    assert search_forge_args(_args(), str(bare)) == RECIPE.split()
    assert search_forge_args(_args(search_alloc="off"), str(fitted)) == RECIPE.split()


def test_guard_flags_search_term_shares_read_the_median():
    rl = {"mean": {"kl_mu": 0.01, "distill_share": 0.5}, "med": {"distill_share": 0.1, "alloc_share": 0.2}}
    assert guard_flags({}, rl, None, distill_share_max=0.15, alloc_share_max=0.06) == [
        "guard: alloc_share 0.2 > 0.06"
    ]
    assert guard_flags({}, rl, None) == []


def test_sched_carry_flags_follow_the_serving_ckpt(tmp_path):
    with_sched = tmp_path / "s.pt"
    torch.save({"model": {"sched_query.weight": torch.zeros(1), "trunk.x": torch.zeros(1)}, "config": {}}, with_sched)
    bare = tmp_path / "b.pt"
    torch.save({"model": {"trunk.x": torch.zeros(1)}, "config": {}}, bare)
    assert ckpt_carries(str(with_sched)) == {"sched": True, "plan": False}
    a = types.SimpleNamespace(sched=False, sched_carry="auto")
    assert sched_carry_flags(a, str(with_sched)) == ["--sched", "--sched-frac", "0", "--sched-lr", "0", "--sched-proj-lr", "0"]
    assert sched_carry_flags(a, str(bare)) == []
    assert sched_carry_flags(types.SimpleNamespace(sched=True, sched_carry="auto"), str(with_sched)) == []
    assert sched_carry_flags(types.SimpleNamespace(sched=False, sched_carry="off"), str(with_sched)) == []
    assert sched_carry_flags(types.SimpleNamespace(sched=False, sched_carry="on"), str(bare))[:1] == ["--sched"]
