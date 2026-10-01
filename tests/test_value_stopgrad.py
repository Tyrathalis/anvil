"""ADR-0119 ladder rung 2 (10-01): `AnvilNet.value_stopgrad` — the value head
reads a DETACHED [STATE] read-out, so no value-side gradient reaches the trunk
while the head itself still trains and the policy gradient still reaches the
trunk. The trainer's --value-stopgrad-trunk sets the switch; it is not an
architecture parameter (checkpoints carry no trace; default off is the
pre-rung-2 model exactly). The gradient-norm row's read (trunk_grad_norm) of
the value term is zero under the switch. Skips on a bare checkout (the same
local fixtures as test_plan_latent)."""

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
    net.load_compat(ckpt["model"])
    net.eval()
    feat = Featurizer(stem, methods)
    exs = []
    for dec, header, prior in _windows({"chooseSpellAbilityToPlay"}, n=4):
        ex, _aux = feat.example(_wire(dec, prior), header, "priority")
        exs.append(ex)
    return net, collate(exs)


def _norm(gs) -> float:
    import torch

    tot = sum((g.float() ** 2).sum() for g in gs if g is not None)
    return float(torch.sqrt(tot)) if isinstance(tot, torch.Tensor) else 0.0


def _value_and_policy_grads(net, batch, flag: bool):
    import torch

    net.value_stopgrad = flag
    try:
        trunk = [p for p in net.trunk.parameters() if p.requires_grad]
        head = [p for p in net.value_head.parameters() if p.requires_grad]
        out = net(batch)
        v_term = out["value_logit"].float().sum()
        pg_term = out["policy_logits"].float().clamp(min=-1e8).logsumexp(-1).sum()
        v_trunk = _norm(torch.autograd.grad(v_term, trunk, retain_graph=True, allow_unused=True))
        v_head = _norm(torch.autograd.grad(v_term, head, retain_graph=True, allow_unused=True))
        pg_trunk = _norm(torch.autograd.grad(pg_term, trunk, retain_graph=True, allow_unused=True))
        return v_trunk, v_head, pg_trunk, out
    finally:
        net.value_stopgrad = False


def test_default_off_value_reaches_trunk(net_and_batch):
    net, batch = net_and_batch
    assert net.value_stopgrad is False  # a fresh / loaded net is the pre-rung-2 model
    v_trunk, v_head, pg_trunk, _ = _value_and_policy_grads(net, batch, False)
    assert v_trunk > 0 and v_head > 0 and pg_trunk > 0


def test_stopgrad_cuts_value_to_trunk_only(net_and_batch):
    import torch

    net, batch = net_and_batch
    v_trunk, v_head, pg_trunk, out_on = _value_and_policy_grads(net, batch, True)
    assert v_trunk == 0.0, "a value gradient reached the trunk under value_stopgrad"
    assert v_head > 0, "the head itself must still train"
    assert pg_trunk > 0, "the policy gradient must still reach the trunk"
    # the forward VALUES are unchanged: detach is a gradient-only switch
    # (both passes in grad mode — nn.TransformerEncoder's no_grad fast path
    # has its own numerics, which is a kernel choice, not the switch)
    out_off = net(batch)
    assert torch.equal(out_on["value_logit"].detach(), out_off["value_logit"].detach())
    assert torch.equal(out_on["policy_logits"].detach(), out_off["policy_logits"].detach())


def test_grad_norm_row_reads_zero_under_stopgrad(net_and_batch):
    """The rl.py gn_v row (ADR-0118 addendum) is the loop's own check that the
    switch is in force: trunk_grad_norm of a value term reads 0."""
    import torch.nn.functional as F

    from anvil.training.value_pretrain import trunk_grad_norm

    net, batch = net_and_batch
    trunk = [p for p in net.trunk.parameters() if p.requires_grad]
    net.value_stopgrad = True
    try:
        out = net(batch)
        v_loss = F.binary_cross_entropy_with_logits(
            out["value_logit"].float(), (out["value_logit"] > 0).float()
        )
        assert trunk_grad_norm(v_loss, trunk) == 0.0
    finally:
        net.value_stopgrad = False
    out = net(batch)
    v_loss = F.binary_cross_entropy_with_logits(
        out["value_logit"].float(), (out["value_logit"] > 0).float()
    )
    assert trunk_grad_norm(v_loss, trunk) > 0.0


def test_anchor_path_honors_stopgrad(net_and_batch):
    """The anchor (ValueAnchor.loss) reads the head through value_pretrain.
    value_logits, not AnvilNet.forward — the 10-01 smoke caught gn_anchor
    still on the trunk; the switch must cover that path too."""
    import torch

    from anvil.training.value_pretrain import value_logits

    net, batch = net_and_batch
    trunk = [p for p in net.trunk.parameters() if p.requires_grad]
    head = [p for p in net.value_head.parameters() if p.requires_grad]
    net.value_stopgrad = True
    try:
        v = value_logits(net, batch).float().sum()
        assert _norm(torch.autograd.grad(v, trunk, retain_graph=True, allow_unused=True)) == 0.0
        assert _norm(torch.autograd.grad(v, head, allow_unused=True)) > 0.0
    finally:
        net.value_stopgrad = False
    v = value_logits(net, batch).float().sum()
    assert _norm(torch.autograd.grad(v, trunk, allow_unused=True)) > 0.0

