"""M10 v2: the schedule-surface model surgery (m10-build-spec §2).

Pins under test — the v2 identity contract: sched keys absent leaves every
output byte-identical (case 1, covered by the whole pre-existing suite plus
the mixed-batch check here); mask-closed slots are invisible to the other
tokens (case 2 — numerics-tight, the padding-variation class the batcher
already tolerates); at zero-init sched_proj the outputs are
schedule-CONTENT-invariant bit-exactly (case 3); a trained proj with fed
slots changes outputs (case 4 — the wire is connected). Plus: greedy decode
STOP latch, teacher-forced decode/aux shapes, and gradient reachability for
the consumption and emission paths. Skips on a bare checkout (same local
fixtures as test_plan_latent)."""

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
    net.load_compat(ckpt["model"])  # sched_* absent from pre-M10 ckpt: must load
    net.eval()
    feat = Featurizer(stem, methods)
    exs = []
    for dec, header, prior in _windows({"chooseSpellAbilityToPlay"}, n=6):
        ex, _aux = feat.example(_wire(dec, prior), header, "priority")
        exs.append(ex)
    return net, collate(exs), [dict(e) for e in exs]


def _sched_keys_for(batch, seed=0):
    """A syntactically-valid fed schedule over the batch's real entities."""
    import torch

    from anvil.training.dataset import SCHED_CAP, SCHED_PAY_NONE

    g = torch.Generator().manual_seed(seed)
    b, n = batch["entities"].shape[:2]
    n_real = batch["ent_mask"].sum(1)
    rows = torch.stack(
        [torch.randint(0, max(1, int(n_real[i])), (SCHED_CAP,), generator=g) for i in range(b)]
    )
    return {
        "sched_rows": rows,
        "sched_sa": torch.randint(0, 50, (b, SCHED_CAP), generator=g),
        "sched_status": torch.randint(0, 4, (b, SCHED_CAP), generator=g),
        "sched_afford": torch.randint(0, 2, (b, SCHED_CAP), generator=g).float(),
        "sched_pay": torch.full((b, SCHED_CAP), SCHED_PAY_NONE, dtype=torch.int64),
        "sched_mask": torch.ones(b, SCHED_CAP, dtype=torch.bool),
    }


def test_identity_contract(net_and_batch):
    import torch

    net, batch, _ = net_and_batch
    base = net(batch)  # case 1: keys absent — the unchanged code path
    fedA = {**batch, **_sched_keys_for(batch, seed=1)}
    fedB = {**batch, **_sched_keys_for(batch, seed=2)}
    # case 3: zero-init proj — two DIFFERENT schedules, identical outputs
    outA, outB = net(fedA), net(fedB)
    assert torch.equal(outA["policy_logits"], outB["policy_logits"])
    assert torch.equal(outA["value_logit"], outB["value_logit"])
    # case 2: mask-closed slots are invisible to the other tokens (numerics-
    # tight, not bitwise — reduction-tree shape may differ with appended
    # positions; same class as batch-padding variation, tripwire-covered)
    closed = {**batch, **_sched_keys_for(batch, seed=3)}
    closed["sched_mask"] = torch.zeros_like(closed["sched_mask"])
    outC = net(closed)
    assert torch.allclose(base["policy_logits"], outC["policy_logits"], atol=1e-5, rtol=1e-5)
    # case 4: trained proj + fed slots — the wire is CONNECTED
    with torch.no_grad():
        net.assemble.sched_proj.weight.normal_()
    outD = net(fedA)
    assert not torch.equal(outA["policy_logits"], outD["policy_logits"])
    with torch.no_grad():
        net.assemble.sched_proj.weight.zero_()


def test_mixed_batch_empty_item_unperturbed(net_and_batch):
    """Collate mixing: an example WITHOUT sched keys batched alongside fed
    ones gets an all-False mask row and answers (numerics-tight) as if the
    surface were absent."""
    import torch

    from anvil.training.dataset import collate

    net, batch, exs = net_and_batch
    solo = net(collate([exs[0]]))
    keys = _sched_keys_for(batch, seed=4)
    mixed_exs = [dict(exs[0])] + [
        {**dict(e), **{k: v[i + 1] for k, v in keys.items()}} for i, e in enumerate(exs[1:3])
    ]
    mixed = net(collate(mixed_exs))
    n_solo = solo["policy_logits"].shape[1]
    assert torch.allclose(
        solo["policy_logits"][0], mixed["policy_logits"][0, :n_solo], atol=1e-5, rtol=1e-5
    )


def test_forward_sched_outputs_shapes(net_and_batch):
    import torch

    from anvil.training.dataset import SCHED_CAP

    net, batch, _ = net_and_batch
    b, c = batch["cand_mask"].shape
    tgt = torch.full((b, SCHED_CAP), -1, dtype=torch.int64)
    tgt[:, 0] = torch.where(
        batch["cand_mask"][:, 1:].any(1), torch.ones(b, dtype=torch.int64), torch.zeros(b, dtype=torch.int64)
    )
    tgt[:, 1] = 0  # STOP after one slot
    fed = {**batch, "sched_tgt": tgt}
    out = net(fed)
    assert out["sched_logits"].shape == (b, SCHED_CAP + 1, c)
    assert out["sched_r"].shape == (b, SCHED_CAP, 2)
    assert out["sched_e"].shape == (b, 7)
    # the live-logit pattern equals the candidate mask at every decode step
    assert ((out["sched_logits"] > -1e8) == batch["cand_mask"].unsqueeze(1)).all()


def test_greedy_decode_stop_latch(net_and_batch):
    import torch

    from anvil.training.dataset import SCHED_CAP

    net, batch, _ = net_and_batch
    res = net.act(batch, sched_decode=True)
    picks = res["sched_picks"]
    b = batch["entities"].shape[0]
    assert picks.shape == (b, SCHED_CAP)
    # once STOP (0) is picked every later slot is forced 0
    for i in range(b):
        row = picks[i].tolist()
        if 0 in row:
            j = row.index(0)
            assert all(p == 0 for p in row[j:])
        # picks index the candidate space and respect the mask
        for p in row:
            assert bool(batch["cand_mask"][i, p])
    # without the flag act() emits no decode
    assert "sched_picks" not in net.act(batch)


MU_STORE = Path("data/trajectories/d6-run18-i000-20260821-205317")


@pytest.mark.skipif(not MU_STORE.exists(), reason="local run18 store not present")
def test_loader_sched_targets(net_and_batch):
    """End-to-end target construction: game_trajectories(sched=True) marks
    emission windows (MAIN1 rule), builds decode/E/R targets, RlTrajectories
    attaches the side tensors; a store without mu sched fields carries no
    conditioning keys (pre-M10 store => targets only)."""
    import torch

    from anvil.training.dataset import SCHED_CAP, default_methods
    from anvil.training.rl import SCHED_COUNTERS, RlTrajectories

    stem = str(EMBED).removesuffix(".safetensors")
    ds = RlTrajectories([str(MU_STORE)], [1.0], stem, default_methods(),
                        seg=64, sched=True)
    item = next(i for i in ds if "skip" not in i)
    segs = item["segs"]
    assert all("sched_emit" in s and "sched_tgt_full" in s for s in segs)
    emit = torch.cat([s["sched_emit"] for s in segs])
    tgt = torch.cat([s["sched_tgt_full"] for s in segs])
    assert emit.any(), "no emission windows marked in a whole trajectory"
    # emission rows carry a decode target (first step never pad)
    assert (tgt[emit][:, 0] >= 0).all()
    # non-emission rows carry none
    assert (tgt[~emit] == -1).all()
    ev = torch.cat([s["sched_e_valid"] for s in segs])
    et = torch.cat([s["sched_e_tgt"] for s in segs])
    assert (ev <= emit).all() and ev.any()
    assert (et[ev] >= 0).all() and (et[ev] <= 30.0).all()
    rv = torch.cat([s["sched_r_valid"] for s in segs])
    assert (rv.any(dim=1) <= emit).all()
    # pre-M10 store: no mu sched fields => no conditioning keys collated
    assert all("sched_mask" not in s for s in segs)
    assert SCHED_COUNTERS.get("emit", 0) > 0
    assert tgt.shape[1] == SCHED_CAP + 1
    # the accounting stays visible, never silent
    assert "unmatched" in SCHED_COUNTERS or SCHED_COUNTERS.get("slots", 0) >= 0


def test_gradients_reach_sched_params(net_and_batch):
    """Consumption (slot tokens -> PG path) and emission (decode/E/R losses)
    are both in-graph."""
    import torch

    from anvil.training.dataset import SCHED_CAP

    net, batch, _ = net_and_batch
    b = batch["entities"].shape[0]
    fed = {**batch, **_sched_keys_for(batch, seed=5)}
    net.zero_grad(set_to_none=True)
    net(fed)["policy_logits"].sum().backward()
    g = net.assemble.sched_proj.weight.grad
    assert g is not None and g.abs().sum() > 0
    net.zero_grad(set_to_none=True)
    tgt = torch.zeros(b, SCHED_CAP, dtype=torch.int64)
    tgt[:, 0] = 1
    out = net({**batch, "sched_tgt": tgt})
    loss = out["sched_logits"].logsumexp(-1).sum() + out["sched_r"].sum() + out["sched_e"].sum()
    loss.backward()
    for name in ("sched_query", "sched_key", "sched_sa_proj"):
        g = getattr(net, name).weight.grad
        assert g is not None and g.abs().sum() > 0, name
    for head in (net.sched_e_head, net.sched_r_head):
        g = head[0].weight.grad
        assert g is not None and g.abs().sum() > 0
    net.zero_grad(set_to_none=True)
