"""Train/serve parity (M1 D8): the bridge featurizer must produce the exact
tensors the training loader produces for the same decision, and AnvilNet.act
must pick what forward's argmax picks. Runs against the pilot store + D7
checkpoint; skips when the local data isn't present (repo tests stay green on
a bare checkout)."""

from pathlib import Path

import pytest

STORE = Path("data/trajectories/d3pilot-20260704-175219")
EMBED = Path("data/embeddings/cf2ca6ba-qwen3.safetensors")
CKPT = Path("data/training/d7-ep3/last.pt")

pytestmark = pytest.mark.skipif(
    not (STORE.exists() and EMBED.exists()), reason="local pilot data not present")


def _wire_hist(prior, k=8):
    """What the Java ring ships: raw (m, p, ret-host) for the last K prior
    decs — the info-set rule is applied server-side in wire_history."""
    out = []
    for d in prior[-k:]:
        ret = d.get("ret")
        host = -1
        if isinstance(ret, list) and ret and isinstance(ret[0], dict):
            host = ret[0].get("e", -1)
        out.append({"m": d.get("m", "?"), "p": d.get("p", -1), "e": host})
    return out


def _priority_windows(n=40):
    from anvil.store.trajectories import open_store
    store = open_store(str(STORE))
    got = []
    for g in store.game_indices()[:30]:
        traj = store.game(g)
        prior = []
        for dec in traj.decisions:
            if (dec.get("m") == "chooseSpellAbilityToPlay" and dec.get("obs") is not None
                    and dec.get("ret") is not None):
                got.append((dict(dec), traj.header, list(prior)))
                if len(got) >= n:
                    return got
            prior.append(dec)
    return got


def test_featurizer_matches_loader_and_act_matches_forward():
    import torch

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import PriorityWindows, collate, default_methods

    methods = default_methods()
    stem = str(EMBED).removesuffix(".safetensors")
    feat = Featurizer(stem, methods)
    ds = PriorityWindows(str(STORE), stem, methods)

    from anvil.store.trajectories import open_store
    store = open_store(str(STORE))

    net = None
    if CKPT.exists():
        from anvil.training.train import build_net
        ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
        net = build_net(stem, ckpt["config"]["pool_manifest"], len(methods))
        net.load_state_dict(ckpt["model"])
        net.eval()

    checked = 0
    for dec, header, prior in _priority_windows():
        # training-path example: run _examples on a stub store view
        g = None  # _examples reads via store.game; emulate by index lookup
        # find the example by regenerating from the real generator per game is
        # costly; instead compare against the loader's own featurization calls
        wire = dict(dec)
        wire["hist"] = _wire_hist(prior)
        ex_serve, aux = feat.example(wire, header, "priority")

        from anvil.encoder.transform import assemble, history_tokens
        out_train = assemble(dec, header, perspective=dec["p"],
                             history=history_tokens(prior, dec["p"]))
        import numpy as np
        assert np.array_equal(out_train["entities"], ex_serve["entities"].numpy())
        assert np.array_equal(out_train["globals"], ex_serve["globals"].numpy())
        assert np.array_equal(out_train["players"], ex_serve["players"].numpy())
        # history token equality: same (m, self, host-row) triples
        row_of = out_train["entity_row_of"]
        hist_train = [(h["m"], h["self"], row_of.get(h["e"], -1))
                      for h in history_tokens(prior, dec["p"])]
        hist_serve = ex_serve["history"].numpy()
        for i, (m, s, r) in enumerate(hist_train):
            assert hist_serve[i][1] == s and hist_serve[i][2] == r
        # candidate rows: loader construction on the same opts
        seen, cand_train = set(), [-1]
        for o in dec.get("opts") or []:
            r = row_of.get(o.get("e"))
            if r is not None and r not in seen:
                seen.add(r)
                cand_train.append(r)
        assert cand_train == ex_serve["cand_rows"].tolist()

        if net is not None:
            batch = collate([ex_serve])
            fwd = net(batch)["policy_logits"].argmax(1)
            act = net.act(batch, pass_delta=0.0)
            assert int(fwd[0]) == int(act["choice"][0])
        checked += 1
    assert checked >= 20
