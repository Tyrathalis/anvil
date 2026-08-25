"""M9 D6: the plan-latent carry surgery (m9-d6-plan-latent-spec §2).

Pins under test: the carried plan vector enters token 1 through a ZERO-init
projection gated by has_plan — day-zero outputs are bit-identical to the
static [PLAN] token whether the keys are absent, the gate is closed, or the
projection is untrained; the wire is actually connected (randomized proj +
open gate changes outputs); pre-D6 checkpoints load with plan_* / the
assembler projection at fresh init; act() exposes the emitted plan vector;
collate treats plan keys as optional (absent from BC-era examples).
Skips on a bare checkout (same local fixtures as test_pay_class)."""

from pathlib import Path

import pytest

STORE = Path("data/trajectories/pilotv2-20260821-155339")
EMBED = Path("data/embeddings/cf2ca6ba-qwen3.safetensors")
CKPT = Path("data/training/d5-combat/last.pt")

pytestmark = pytest.mark.skipif(
    not (STORE.exists() and EMBED.exists() and CKPT.exists()), reason="local pilot data not present"
)


@pytest.fixture(scope="module")
def net_and_batch():
    import torch

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import collate, default_methods
    from anvil.training.train import build_net
    from tests.test_sampling import _windows, _wire

    methods = default_methods()
    stem = str(EMBED).removesuffix(".safetensors")
    ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    net = build_net(
        stem,
        ckpt["config"]["pool_manifest"],
        len(methods),
        n_sa=ckpt["config"].get("sa_vocab_size", 0),
    )
    net.load_compat(ckpt["model"])  # plan_* absent from pre-D6 ckpt: must load
    net.eval()
    feat = Featurizer(stem, methods)
    exs = []
    for dec, header, prior in _windows({"chooseSpellAbilityToPlay"}, n=6):
        ex, _aux = feat.example(_wire(dec, prior), header, "priority")
        exs.append(ex)
    return net, collate(exs), [dict(e) for e in exs]


def test_day_zero_bit_identity(net_and_batch):
    import torch

    net, batch, _ = net_and_batch
    base = net(batch)
    # zero-init proj: an arbitrary carried vector with the gate OPEN changes nothing
    d = net.assemble.plan_tok.shape[-1]
    b = batch["entities"].shape[0]
    fed = {**batch, "plan_vec": torch.randn(b, d), "has_plan": torch.ones(b)}
    out = net(fed)
    assert torch.equal(base["policy_logits"], out["policy_logits"])
    assert torch.equal(base["value_logit"], out["value_logit"])
    # trained proj with the gate CLOSED also changes nothing
    with torch.no_grad():
        net.assemble.plan_proj.weight.normal_()
    gated = {**batch, "plan_vec": torch.randn(b, d), "has_plan": torch.zeros(b)}
    out2 = net(gated)
    assert torch.equal(base["policy_logits"], out2["policy_logits"])
    # trained proj + open gate: the wire is CONNECTED
    out3 = net(fed)
    assert not torch.equal(base["policy_logits"], out3["policy_logits"])
    with torch.no_grad():
        net.assemble.plan_proj.weight.zero_()


def test_act_exposes_plan(net_and_batch):
    import torch

    net, batch, _ = net_and_batch
    res = net.act(batch)
    d = net.assemble.plan_tok.shape[-1]
    assert res["plan"].shape == (batch["entities"].shape[0], d)
    fwd = net(batch)
    # no_grad act() may take the TransformerEncoder fused fast path — same
    # math, slightly different numerics than forward()'s grad path
    assert torch.allclose(res["plan"], fwd["plan"], atol=1e-4, rtol=1e-4)


def test_aux_head_shapes(net_and_batch):
    net, batch, _ = net_and_batch
    fwd = net(batch)
    act = net.plan_act_head(fwd["plan"])
    delta = net.plan_delta_head(fwd["plan"])
    n_sa = net.sa_emb.num_embeddings - 1 if net.sa_emb is not None else 0
    assert act.shape[-1] == (n_sa + 1 if n_sa else 1) + 3
    assert delta.shape[-1] == 6


MU_STORE = Path("data/trajectories/d6-run18-i000-20260821-205317")


@pytest.mark.skipif(not MU_STORE.exists(), reason="local run18 store not present")
def test_loader_plan_marks_and_pass0(net_and_batch):
    """End-to-end loader path: game_trajectories(plan=True) marks + targets,
    RlTrajectories side tensors, plan_pass0 attachment semantics."""
    import torch

    from anvil.training.dataset import default_methods
    from anvil.training.rl import RlTrajectories, plan_pass0

    net, _, _ = net_and_batch
    stem = str(EMBED).removesuffix(".safetensors")
    ds = RlTrajectories([str(MU_STORE)], [1.0], stem, default_methods(),
                        seg=64, plan=True)
    item = next(i for i in ds if "skip" not in i)
    segs = item["segs"]
    assert all("plan_turn" in s and "plan_first" in s for s in segs)
    # turn-first structure: first row of the trajectory is an emission; turns
    # are monotonic; every turn has exactly one first row
    turns = torch.cat([s["plan_turn"] for s in segs])
    firsts = torch.cat([s["plan_first"] for s in segs])
    assert bool(firsts[0])
    assert (turns[1:] >= turns[:-1]).all()
    for t in turns.unique().tolist():
        assert int(firsts[turns == t].sum()) == 1
    # emission targets live only on first rows
    act = torch.cat([s["plan_act_tgt"] for s in segs])
    assert act[~firsts].abs().sum() == 0
    assert act.shape[1] == net.plan_act_head.out_features
    dv = torch.cat([s["plan_delta_valid"] for s in segs])
    assert (dv.bool() <= firsts).all()  # valid deltas only at emissions

    plan_pass0(net, segs, "cpu")
    pv = torch.cat([s["plan_vec"] for s in segs])
    hp = torch.cat([s["has_plan"] for s in segs])
    assert (hp[firsts] == 0).all()  # serve parity: emissions consume nothing
    carried = ~firsts.bool()
    assert (hp[carried] == 1).all()  # every non-first row is carried
    # all carried rows of one turn share their emission vector
    for t in turns.unique().tolist():
        rows = (turns == t) & carried
        if rows.any():
            vecs = pv[rows]
            assert (vecs == vecs[0]).all()
            assert vecs[0].abs().sum() > 0


def test_plan_proj_receives_gradient(net_and_batch):
    """The consumption wire is in-graph: PG loss reaches plan_proj."""
    import torch

    net, batch, _ = net_and_batch
    d = net.assemble.plan_tok.shape[-1]
    b = batch["entities"].shape[0]
    fed = {**batch, "plan_vec": torch.randn(b, d), "has_plan": torch.ones(b)}
    net.zero_grad(set_to_none=True)
    out = net(fed)
    out["policy_logits"].sum().backward()
    g = net.assemble.plan_proj.weight.grad
    assert g is not None and g.abs().sum() > 0
    net.zero_grad(set_to_none=True)


def test_serve_carry_semantics():
    """The stub-driven carry contract (m9-d6-plan-latent-spec §3): emission
    on first sight of a (g, seat, turn), feed-back within the turn, reset
    on turn advance, no carry for fork headers or ungated backends."""
    import threading
    import types

    import torch

    from anvil.bridge.server import ModelBackend

    stub = types.SimpleNamespace(
        carry_plan=True,
        plan_carry={},
        plan_lock=threading.Lock(),
        _plan_cap=4,
        torch=torch,
        net=types.SimpleNamespace(
            assemble=types.SimpleNamespace(plan_tok=torch.zeros(1, 8))
        ),
    )
    inject = lambda ex, g, p, t: ModelBackend._plan_inject(  # noqa: E731
        stub, ex, {"g": g}, {"p": p, "t": t}
    )
    ex = {}
    key, emit = inject(ex, 5, 0, 3)
    assert emit and key == (5, 0) and ex["has_plan"] == 0.0
    ModelBackend._plan_store(stub, key, 3, torch.ones(8))
    ex2 = {}
    key2, emit2 = inject(ex2, 5, 0, 3)
    assert not emit2 and ex2["has_plan"] == 1.0 and ex2["plan_vec"].sum() == 8
    ex3 = {}
    _, emit3 = inject(ex3, 5, 0, 4)  # turn advanced -> fresh emission
    assert emit3 and ex3["has_plan"] == 0.0
    _, emit4 = inject({}, 5, 1, 3)  # other seat -> own emission
    assert emit4
    key5, emit5 = inject({}, -1, 0, 3)  # fork header -> never carries
    assert key5 is None and not emit5
    stub.carry_plan = False
    key6, _ = inject({}, 5, 0, 3)  # ungated backend -> no-op
    assert key6 is None
    # cap eviction is FIFO and bounded
    stub.carry_plan = True
    for g in range(6):
        ModelBackend._plan_store(stub, (g, 0), 1, torch.zeros(8))
    assert len(stub.plan_carry) == 4


def test_carry_gating_on_ckpt_params():
    """carry_plan mirrors has_pay: on iff the ckpt saves plan params.
    d6-plan-init must gate ON and also carry NO pay params (ADR-0073
    infrastructure routing — the D6 runs never advertise the pay tag)."""
    import torch

    grafted = Path("data/training/d6-plan-init/last.pt")
    if not grafted.exists():
        pytest.skip("d6-plan-init not present")
    keys = torch.load(grafted, map_location="cpu", weights_only=False)["model"].keys()
    assert any(k.startswith(("plan_", "assemble.plan_proj")) for k in keys)
    assert not any(k.startswith("pay_") for k in keys)
    src = torch.load(CKPT, map_location="cpu", weights_only=False)["model"].keys()
    assert not any(k.startswith(("plan_", "assemble.plan_proj")) for k in src)


def test_collate_plan_keys_optional(net_and_batch):
    import torch

    from anvil.training.dataset import collate

    _, _, exs = net_and_batch
    plain = collate(exs)
    assert "plan_vec" not in plain
    d = 512
    exs2 = [dict(e) for e in exs]
    exs2[0]["plan_vec"] = torch.ones(d)
    exs2[0]["has_plan"] = 1.0
    mixed = collate(exs2)
    assert mixed["plan_vec"].shape == (len(exs2), d)
    assert mixed["has_plan"][0] == 1.0 and mixed["has_plan"][1:].sum() == 0
    assert mixed["plan_vec"][1:].abs().sum() == 0
