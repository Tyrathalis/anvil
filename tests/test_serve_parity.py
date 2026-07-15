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


def _wire_hist(prior, now_pos, k=8):
    """Promoted to featurize.store_wire_hist (the D6 RL loader shares it);
    kept as an alias for the tests that import it."""
    from anvil.bridge.featurize import store_wire_hist
    return store_wire_hist(prior, now_pos, k)


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
        net = build_net(stem, ckpt["config"]["pool_manifest"], len(methods),
                        n_sa=ckpt["config"].get("sa_vocab_size", 0))
        net.load_compat(ckpt["model"])  # task_emb grew at D5 (attack/block)
        net.eval()

    checked = 0
    for dec, header, prior in _priority_windows():
        wire = dict(dec)
        wire["hist"] = _wire_hist(prior, dec["_pos"])
        ex_serve, aux = feat.example(wire, header, "priority")

        from anvil.encoder.transform import assemble, history_tokens
        out_train = assemble(dec, header, perspective=dec["p"],
                             history=history_tokens(prior, dec["p"],
                                                    now_pos=dec["_pos"]))
        import numpy as np
        assert np.array_equal(out_train["entities"], ex_serve["entities"].numpy())
        assert np.array_equal(out_train["globals"], ex_serve["globals"].numpy())
        assert np.array_equal(out_train["players"], ex_serve["players"].numpy())
        # history token equality: same (m, self, host-row) triples
        row_of = out_train["entity_row_of"]
        hist_train = [(h["m"], h["self"], row_of.get(h["e"], -1))
                      for h in history_tokens(prior, dec["p"], now_pos=dec["_pos"])]
        hist_serve = ex_serve["history"].numpy()
        for i, (m, s, r) in enumerate(hist_train):
            assert hist_serve[i][1] == s and hist_serve[i][2] == r
        # candidates: loader construction on the same opts (M2 D2 SA level)
        from anvil.training.dataset import KINDS, norm_sa
        key_of, cand_train, sa_train, kind_train = {}, [-1], [-1], [-1]
        for o in dec.get("opts") or []:
            r = row_of.get(o.get("e"))
            if r is None:
                continue
            key = (r, norm_sa(o.get("sa", "")))
            if key in key_of:
                continue
            key_of[key] = len(cand_train)
            cand_train.append(r)
            sa_train.append(ds.sa_vocab.id(key[1]))
            kind_train.append(KINDS.get(o.get("kind"), KINDS["other"]))
        assert cand_train == ex_serve["cand_rows"].tolist()
        assert sa_train == ex_serve["cand_sa"].tolist()
        assert kind_train == ex_serve["cand_kind"].tolist()

        if net is not None:
            batch = collate([ex_serve])
            fwd = net(batch)["policy_logits"].argmax(1)
            act = net.act(batch, pass_delta=0.0)
            assert int(fwd[0]) == int(act["choice"][0])
        checked += 1
    assert checked >= 20


def _combat_windows(n=40):
    from anvil.store.trajectories import open_store
    store = open_store(str(STORE))
    got = []
    for g in store.game_indices()[:60]:
        traj = store.game(g)
        prior = []
        for i, dec in enumerate(traj.decisions):
            if dec.get("m") in ("declareAttackers", "declareBlockers") \
                    and dec.get("obs") is not None:
                got.append((dict(dec), traj.header, list(prior),
                            list(traj.decisions), i))
                if len(got) >= n:
                    return got
            prior.append(dec)
    return got


def test_combat_featurizer_matches_loader():
    """D5: combat windows through the featurizer produce the loader's state
    tensors and candidate fields; act() emits well-formed combat picks."""
    import torch

    from anvil.bridge.featurize import Featurizer
    from anvil.encoder.transform import assemble, history_tokens
    from anvil.training.dataset import (attack_fields, block_fields, collate,
                                        default_methods)
    import numpy as np

    methods = default_methods()
    stem = str(EMBED).removesuffix(".safetensors")
    feat = Featurizer(stem, methods)

    net = None
    if CKPT.exists():
        from anvil.training.train import build_net
        ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
        net = build_net(stem, ckpt["config"]["pool_manifest"], len(methods),
                        n_sa=ckpt["config"].get("sa_vocab_size", 0))
        net.load_compat(ckpt["model"])
        net.eval()

    checked_a = checked_b = 0
    for dec, header, prior, decs, i in _combat_windows():
        task = "attack" if dec["m"] == "declareAttackers" else "block"
        wire = dict(dec)
        wire["hist"] = _wire_hist(prior, dec["_pos"])
        ex, aux = feat.example(wire, header, task)

        out_train = assemble(dec, header, perspective=dec["p"],
                             history=history_tokens(prior, dec["p"],
                                                    now_pos=dec["_pos"]))
        assert np.array_equal(out_train["entities"], ex["entities"].numpy())
        assert np.array_equal(out_train["globals"], ex["globals"].numpy())
        assert np.array_equal(out_train["players"], ex["players"].numpy())

        # candidate fields vs the LOADER's label extractor on the same dec
        row_of = out_train["entity_row_of"]
        f = (attack_fields(decs, i, dec, row_of, len(header["players"]), -1)
             if task == "attack" else block_fields(decs, i, dec, row_of, -1))
        if f is None:
            # forced-empty window: featurizer must agree there's nothing to ask
            assert ex["cmb_rows"].shape[0] == 0 or task == "block"
            continue
        assert f["cmb_rows"] == ex["cmb_rows"].tolist()
        assert f["cmb_count"] == ex["cmb_count"].tolist()
        if task == "block":
            assert f["blk_atk_rows"] == ex["blk_atk_rows"].tolist()
            assert f["blk_atk_rows"] == aux["blk_atk_rows"]
        # aux member expansion covers every candidate row
        for r in f["cmb_rows"]:
            assert aux["cmb_members"][r]

        if net is not None and ex["cmb_rows"].shape[0]:
            batch = collate([ex])
            act = net.act(batch)
            A = batch["cmb_rows"].shape[1]
            n_ent = batch["entities"].shape[1]
            n_p = batch["players"].shape[1]
            assert act["atk_yes"].shape == (1, A)
            assert (act["cmb_count"] >= 1).all()
            assert (act["atk_tgt"] < n_ent + n_p).all()
            M = batch["blk_atk_rows"].shape[1]
            assert (act["blk_pick"] <= M).all()
        if task == "attack":
            checked_a += 1
        else:
            checked_b += 1
    assert checked_a >= 10 and checked_b >= 5
