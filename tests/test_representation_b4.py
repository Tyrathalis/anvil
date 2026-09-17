"""M12 Build 4 (ADR-0111): the representation completions — format scalars in
the globals, the stack entries as additive fields, the ability text beside
the candidate's string id. Pins under test: (1) the format scalars ride the
globals after the one-hot with their scales; (2) stack_fields maps the
recorded stack onto entity rows / seats; (3) the identity contract — with the
fields absent, present, or filled with arbitrary content the outputs are
byte-identical at zero init (the wire is connected once a projection is
non-zero). The net cases skip on a bare checkout (the sched-surface fixtures)."""
from pathlib import Path

import numpy as np
import pytest

from tests.test_transform import _dec, _header

STORE = Path("data/trajectories/pilotv2-20260821-155339")
EMBED = Path("data/embeddings/cf2ca6ba-qwen3.safetensors")
CKPT = Path("data/training/d5-combat/last.pt")
have_local = STORE.exists() and EMBED.exists() and CKPT.exists()


def _ents():
    return [
        {"e": 10, "n": "Llanowar Elves", "z": "battlefield", "c": 0, "o": 0},
        {"e": 11, "n": "Sol Ring", "z": "battlefield", "c": 1, "o": 1},
        {"e": 12, "n": "Counterspell", "z": "stack", "c": 1, "o": 1},
    ]


def test_format_scalars_ride_the_globals():
    from anvil.encoder.transform import FORMAT_SCALARS, GLOBAL_FEATURES, GLOBAL_SCALE, assemble

    assert len(GLOBAL_FEATURES) == len(GLOBAL_SCALE)
    assert GLOBAL_FEATURES[-5:] == ["format_" + k for k in FORMAT_SCALARS]
    out = assemble(_dec(_ents()), _header())
    g = out["globals"]
    assert g.shape[0] == len(GLOBAL_FEATURES)
    # Commander: 40 life / 100 cards / singleton / command zone / london -> scaled
    assert np.allclose(g[-5:], [40 / 40, 100 / 100, 1.0, 1.0, 1.0])
    assert out["stack"] == []
    assert out["seats"] == [0, 1]


def test_unknown_format_is_loud():
    from anvil.encoder.transform import VocabError, assemble

    h = _header()
    h["fmt"] = "Nonesuch"
    with pytest.raises(VocabError):
        assemble(_dec(_ents()), h)


def test_stack_fields_map_entries():
    from anvil.encoder.stack_fields import STACK_K, stack_fields
    from anvil.encoder.transform import assemble

    stack = [
        {"e": 12, "c": 1, "lbl": "Counterspell", "ak": "deadbeef00000001", "tgt": [{"e": 10}]},
        {"e": 999, "c": 0, "lbl": "an emblem", "tgt": [{"pi": 1}]},
    ]
    out = assemble(_dec(_ents(), stack=stack), _header())
    assert out["stack"] == stack

    class Abil:
        def index(self, k):
            return 7 if k == "deadbeef00000001" else -1

    f = stack_fields(out, Abil(), 0)
    row_of = out["entity_row_of"]
    assert f["stack_mask"].tolist() == [True, True] + [False] * (STACK_K - 2)
    assert f["stack_rows"][0] == row_of[12] and f["stack_rows"][1] == -1  # hostless entry
    assert f["stack_ak"].tolist()[:2] == [7, -1]
    assert f["stack_ctrl"].tolist()[:2] == [0, 1]  # entry 0 the opponent's, entry 1 mine
    assert f["stack_tgt_rows"][0] == row_of[10] and f["stack_tgt_rows"][1] == -1
    assert f["stack_tgt_pi"].tolist()[:2] == [-1, 1]  # player 1 = seat position 1 from perspective 0
    # no cache: keys -1, the rest unchanged
    g = stack_fields(assemble(_dec(_ents(), stack=stack), _header(), perspective=1), None, 1)
    assert g["stack_ak"].tolist()[:2] == [-1, -1] and g["stack_ctrl"].tolist()[:2] == [1, 0]
    assert g["stack_tgt_pi"].tolist()[:2] == [-1, 0]  # from perspective 1 the target player is self


@pytest.fixture(scope="module")
def net_and_batch():
    if not have_local:
        pytest.skip("local pilot data not present")
    import torch

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import collate, default_methods
    from anvil.training.train import build_net
    from tests.test_sampling import _windows, _wire

    methods = default_methods()
    stem = str(EMBED).removesuffix(".safetensors")
    ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    net = build_net(stem, ckpt["config"]["pool_manifest"], len(methods), n_sa=ckpt["config"].get("sa_vocab_size", 0))
    net.load_compat(ckpt["model"])  # cand_abil_proj / assemble.stack_* absent: must load (zero-init)
    net.eval()
    feat = Featurizer(stem, methods)
    exs = []
    for dec, header, prior in _windows({"chooseSpellAbilityToPlay"}, n=6):
        ex, _aux = feat.example(_wire(dec, prior), header, "priority")
        exs.append(ex)
    return net, collate(exs)


def _filled(batch, seed):
    """Arbitrary stack + candidate-key content over a random ability table."""
    import torch

    from anvil.encoder.stack_fields import STACK_K

    g = torch.Generator().manual_seed(seed)
    b = batch["entities"].shape[0]
    n = batch["entities"].shape[1]
    c = batch["cand_rows"].shape[1]
    fed = dict(batch)
    fed["stack_mask"] = torch.rand(b, STACK_K, generator=g) < 0.6
    fed["stack_rows"] = torch.randint(-1, max(n, 1), (b, STACK_K), generator=g)
    fed["stack_ak"] = torch.randint(-1, 5, (b, STACK_K), generator=g)
    fed["stack_ctrl"] = torch.randint(0, 2, (b, STACK_K), generator=g)
    fed["stack_tgt_rows"] = torch.randint(-1, max(n, 1), (b, STACK_K), generator=g)
    fed["stack_tgt_pi"] = torch.randint(-1, 2, (b, STACK_K), generator=g)
    fed["cand_ak"] = torch.randint(-1, 5, (b, c), generator=g)
    return fed


def test_identity_contract(net_and_batch):
    import torch

    net, batch = net_and_batch
    base_batch = {k: v for k, v in batch.items() if not k.startswith("stack_") and k != "cand_ak"}
    base = net(base_batch)  # the fields absent — the pre-Build-4 code path
    asis = net(dict(batch))  # the loader's own fields (keys -1 without a table; the stack as recorded)
    assert torch.equal(base["policy_logits"], asis["policy_logits"])
    assert torch.equal(base["value_logit"], asis["value_logit"])
    # a random ability table + arbitrary content: still identical at zero init
    net.set_ability_table(torch.randn(5, net.abil_vec.shape[1]))
    outA, outB = net(_filled(batch, 1)), net(_filled(batch, 2))
    assert torch.equal(base["policy_logits"], outA["policy_logits"])
    assert torch.equal(outA["policy_logits"], outB["policy_logits"])
    assert torch.equal(base["value_logit"], outA["value_logit"])
    # the wire is connected: a non-zero projection moves the outputs
    for name in ("stack_host_proj", "stack_tgt_proj", "stack_state_proj"):
        lin = getattr(net.assemble, name)
        with torch.no_grad():
            lin.weight.normal_()
        outD = net(_filled(batch, 1))
        assert not torch.equal(base["policy_logits"], outD["policy_logits"]), name
        with torch.no_grad():
            lin.weight.zero_()
    with torch.no_grad():
        net.cand_abil_proj.weight.normal_()
    outE = net(_filled(batch, 1))
    assert not torch.equal(base["policy_logits"], outE["policy_logits"])
    with torch.no_grad():
        net.cand_abil_proj.weight.zero_()
    assert torch.equal(base["policy_logits"], net(_filled(batch, 1))["policy_logits"])
