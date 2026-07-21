"""Full-vis critic loop plumbing (M3 §6f): the RL loader's fv stream must
align 1:1 with the masked stream, actually reveal hidden information, and —
the serve-parity-critical regression — leave the masked (policy) stream
byte-identical to the full_vis=False path. Runs against a run-6 sampled-actor
store + the D5 checkpoint; skips when local data isn't present."""

from pathlib import Path

import numpy as np
import pytest

STORE = Path("data/trajectories/d6-run6-i019-20260721-095939")
EMBED = Path("data/embeddings/cf2ca6ba-qwen3.safetensors")
CKPT = Path("data/training/d5-combat/last.pt")

pytestmark = pytest.mark.skipif(
    not (STORE.exists() and EMBED.exists() and CKPT.exists()),
    reason="local run-6 store not present")


def _arrays_equal(a, b) -> bool:
    import torch
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and a.shape == b.shape and bool(torch.equal(a, b))
    if isinstance(a, np.ndarray):
        return isinstance(b, np.ndarray) and a.shape == b.shape and bool((a == b).all())
    return a == b


@pytest.fixture(scope="module")
def feat_and_game():
    from anvil.bridge.featurize import Featurizer
    from anvil.store.trajectories import open_store
    from anvil.training.dataset import default_methods
    from anvil.training.rl import game_trajectories

    store = open_store(str(STORE))
    stem = str(EMBED).removesuffix(".safetensors")
    feat = Featurizer(stem, default_methods())
    for g in store.game_indices():
        trajs, skip = game_trajectories(store, feat, g, full_vis=True)
        if skip is None and trajs and len(trajs[0][1]) >= 10:
            return store, feat, g, trajs
    pytest.fail("no usable mu-covered game in the store")


def test_fv_stream_alignment(feat_and_game):
    _, _, _, trajs = feat_and_game
    for seat, exs, reward, rej, exs_fv in trajs:
        assert len(exs_fv) == len(exs), (seat, len(exs_fv), len(exs))
        assert all(fv is not None for fv in exs_fv)


def test_fv_off_is_v0_shape(feat_and_game):
    from anvil.training.rl import game_trajectories
    store, feat, g, _ = feat_and_game
    trajs, skip = game_trajectories(store, feat, g)  # default off
    assert skip is None
    for seat, exs, reward, rej, exs_fv in trajs:
        assert exs_fv == []


def test_fv_reveals_hidden(feat_and_game):
    """Somewhere in a real game the opponent holds hidden cards — the fv
    window must differ from the masked one (entity identities un-nulled)."""
    _, _, _, trajs = feat_and_game
    differs = 0
    for seat, exs, reward, rej, exs_fv in trajs:
        for (ex, _), fv in zip(exs, exs_fv):
            if not _arrays_equal(ex["ent_emb"], fv["ent_emb"]) \
                    or ex["entities"].shape != fv["entities"].shape:
                differs += 1
    assert differs > 0, "full_vis windows identical to masked everywhere"


def test_masked_stream_unperturbed(feat_and_game):
    """The policy stream with full_vis=True must be byte-identical to the
    full_vis=False path — §6f must not touch what the policy trains on."""
    from anvil.training.rl import game_trajectories
    store, feat, g, trajs_fv = feat_and_game
    trajs_off, skip = game_trajectories(store, feat, g)
    assert skip is None
    assert len(trajs_off) == len(trajs_fv)
    for (s1, exs1, r1, rej1, _), (s2, exs2, r2, rej2, _) in zip(trajs_off, trajs_fv):
        assert (s1, r1, rej1) == (s2, r2, rej2)
        assert len(exs1) == len(exs2)
        for (ex1, rec1), (ex2, rec2) in zip(exs1, exs2):
            assert rec1 is rec2 or rec1 == rec2
            assert set(ex1) == set(ex2)
            for key in ex1:
                assert _arrays_equal(ex1[key], ex2[key]), key


def test_fv_labels_stay_padded(feat_and_game):
    """mu labels are applied to the masked stream ONLY — a labeled fv window
    would mean the policy-gradient term could silently consume full-vis
    input (the §6f leak boundary)."""
    import torch
    _, _, _, trajs = feat_and_game
    checked = 0
    for seat, exs, reward, rej, exs_fv in trajs:
        for (ex, rec), fv in zip(exs, exs_fv):
            if rec["task"] == "priority" and rec.get("c", 0) > 0:
                assert int(ex["label"]) == rec["c"]
                assert int(fv["label"]) <= 0, "fv window carries a mu label"
                checked += 1
    assert checked > 0


def test_critic_value_forward_on_fv(feat_and_game):
    """End-to-end pass-A shape check: collate fv windows, run the net, get
    finite value logits — the critic consumes fv batches unchanged."""
    import torch

    from anvil.training.dataset import collate, default_methods
    from anvil.training.train import build_net

    _, _, _, trajs = feat_and_game
    exs_fv = trajs[0][4][:8]
    ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    net = build_net(str(EMBED).removesuffix(".safetensors"),
                    ckpt["config"]["pool_manifest"], len(default_methods()),
                    n_sa=ckpt["config"].get("sa_vocab_size", 0))
    net.load_compat(ckpt["model"])
    net.eval()
    with torch.no_grad():
        out = net(collate(exs_fv))
    v = out["value_logit"]
    assert v.shape[0] == len(exs_fv) and torch.isfinite(v).all()
