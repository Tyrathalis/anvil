"""Serve-time sampling (M2 D6): Gumbel-max picks must be deterministic per
(game_seed, dec seq) and independent of GPU batch composition; the recorded
behavior logp must reproduce through the RL recompute path (mu_record ->
apply_mu_labels -> forward -> composite_logp) — the standing drift tripwire
the V-trace learner relies on. Runs against the pilot store + D5 checkpoint;
skips when local data isn't present."""

from pathlib import Path

import pytest

STORE = Path("data/trajectories/d3pilot-20260704-175219")
EMBED = Path("data/embeddings/cf2ca6ba-qwen3.safetensors")
CKPT = Path("data/training/d5-combat/last.pt")

pytestmark = pytest.mark.skipif(
    not (STORE.exists() and EMBED.exists() and CKPT.exists()),
    reason="local pilot data not present")


def _windows(methods_filter, n=25, games=60):
    from anvil.store.trajectories import open_store
    store = open_store(str(STORE))
    got = []
    for g in store.game_indices()[:games]:
        traj = store.game(g)
        prior = []
        for dec in traj.decisions:
            if dec.get("m") in methods_filter and dec.get("obs") is not None:
                got.append((dict(dec), traj.header, list(prior)))
                if len(got) >= n:
                    return got
            prior.append(dec)
    return got


def _wire(dec, prior, k=8):
    from tests.test_serve_parity import _wire_hist
    w = dict(dec)
    w["hist"] = _wire_hist(prior, dec["_pos"])
    return w


@pytest.fixture(scope="module")
def net_and_feat():
    import torch

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net

    methods = default_methods()
    stem = str(EMBED).removesuffix(".safetensors")
    ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    net = build_net(stem, ckpt["config"]["pool_manifest"], len(methods),
                    n_sa=ckpt["config"].get("sa_vocab_size", 0))
    net.load_compat(ckpt["model"])
    net.eval()
    return net, Featurizer(stem, methods)


def test_noise_determinism():
    import torch

    from anvil.bridge.featurize import Featurizer
    from anvil.policy.sampling import make_noise, noise_seed
    from anvil.training.dataset import default_methods

    stem = str(EMBED).removesuffix(".safetensors")
    feat = Featurizer(stem, default_methods())
    dec, header, prior = _windows({"chooseSpellAbilityToPlay"}, n=1)[0]
    ex, _ = feat.example(_wire(dec, prior), header, "priority")
    a = make_noise(ex, "priority", seed=noise_seed(123, 7))
    b = make_noise(ex, "priority", seed=noise_seed(123, 7))
    c = make_noise(ex, "priority", seed=noise_seed(123, 8))
    for k in a:
        assert torch.equal(a[k], b[k])
    assert not torch.equal(a["choice"], c["choice"])


def test_batch_composition_invariance(net_and_feat):
    """Item 0's sampled picks and logps must not depend on what else is in
    the micro-batch (pad_noise scatter must respect the players/STOP/none
    column layout at padded offsets)."""
    import torch

    from anvil.policy.sampling import make_noise, noise_seed, pad_noise
    from anvil.training.dataset import collate

    net, feat = net_and_feat
    wins = _windows({"chooseSpellAbilityToPlay"}, n=8)
    exs = [feat.example(_wire(d, pr), h, "priority")[0] for d, h, pr in wins]
    # deliberately mix in a window with a different entity count for padding
    sizes = {e["entities"].shape[0] for e in exs}
    assert len(sizes) > 1, "test needs entity-count diversity to exercise padding"

    checked = 0
    for i, ex in enumerate(exs):
        nz = make_noise(ex, "priority", seed=noise_seed(42, i))
        solo = collate([ex])
        out1 = net.act(solo, noise=pad_noise([nz], solo, "cpu"))
        other = exs[(i + 1) % len(exs)]
        nz2 = make_noise(other, "priority", seed=noise_seed(42, i + 100))
        duo = collate([ex, other])
        out2 = net.act(duo, noise=pad_noise([nz, nz2], duo, "cpu"))
        assert int(out1["choice"][0]) == int(out2["choice"][0])
        # canonical target picks must agree (padded index spaces differ)
        n1, s1 = int(out1["n_ent"]), int(out1["stop_idx"])
        n2, s2 = int(out2["n_ent"]), int(out2["stop_idx"])
        ni = ex["entities"].shape[0]

        def canon(picks, n, s):
            outp = []
            for t in range(picks.shape[1]):
                p = int(picks[0, t])
                if p == s:
                    break
                outp.append(p if p < n else ni + (p - n))
            return outp
        assert canon(out1["tgt_picks"], n1, s1) == canon(out2["tgt_picks"], n2, s2)
        assert int(out1["x_cls"][0]) == int(out2["x_cls"][0])
        assert torch.allclose(out1["logp_choice"][0], out2["logp_choice"][0], atol=1e-4)
        assert torch.allclose(out1["logp_tgt"][0], out2["logp_tgt"][0], atol=1e-4)
        checked += 1
    assert checked >= 8


def _roundtrip(net, feat, dec, header, prior, task, seed, tau=1.0):
    """act(sample) -> mu_record -> apply_mu_labels -> forward -> composite_logp;
    returns (record, recomputed per-head dict). tau follows the serve path:
    make_noise scales the noise, act reports tempered logp, and the recompute
    must be told the same temperature (rl.py reads it from mu meta)."""
    from anvil.policy.sampling import make_noise, mu_record, noise_seed, pad_noise
    from anvil.training.dataset import collate
    from anvil.training.rl import apply_mu_labels, composite_logp

    ex, aux = feat.example(_wire(dec, prior), header, task)
    nz = make_noise(ex, task, tau, seed=noise_seed(seed, dec["s"]))
    batch = collate([ex])
    out = net.act(batch, noise=pad_noise([nz], batch, "cpu"), temperature=tau)
    rec = mu_record(header["g"], dec["s"], task, ex, aux, out)

    import torch
    ex2, _ = feat.example(_wire(dec, prior), header, task)
    apply_mu_labels(ex2, rec)
    b2 = collate([ex2])
    with torch.no_grad():
        lp = composite_logp(net(b2), b2, temperature=tau)
    return rec, {k: float(v[0]) for k, v in lp.items()}


def test_mu_roundtrip_priority(net_and_feat):
    net, feat = net_and_feat
    casts = passes = 0
    for dec, header, prior in _windows({"chooseSpellAbilityToPlay"}, n=160):
        rec, lp = _roundtrip(net, feat, dec, header, prior, "priority", 314)
        assert abs(lp["logp"] - rec["logp"]) < 5e-3, (rec, lp)
        assert abs(lp["choice"] - rec["lp"]["choice"]) < 5e-3
        if rec["c"] > 0:
            assert abs(lp["tgt"] - rec["lp"]["tgt"]) < 5e-3
            assert abs(lp["x"] - rec["lp"]["x"]) < 5e-3
            casts += 1
        else:
            assert lp["tgt"] == 0.0 and lp["x"] == 0.0
            passes += 1
        if casts >= 5 and passes >= 5:
            return
    assert passes >= 5 and casts >= 5, (passes, casts)


def test_mu_roundtrip_reduced_options(net_and_feat):
    """Re-ask-on-veto (d6-vtrace-loop §6b) mu-parity invariant #2: a re-asked
    dec carries a REDUCED candidate list; mu recorded against it must
    reproduce through the recompute path when the loader rebuilds the same
    reduced list from the stored opts."""
    net, feat = net_and_feat
    checked = 0
    for dec, header, prior in _windows({"chooseSpellAbilityToPlay"}, n=60):
        if len(dec.get("opts") or []) < 2:
            continue
        reduced = dict(dec)
        reduced["opts"] = list(dec["opts"][:-1])  # the "vetoed" candidate removed
        rec, lp = _roundtrip(net, feat, reduced, header, prior, "priority", 991)
        assert abs(lp["logp"] - rec["logp"]) < 5e-3, (rec, lp)
        assert abs(lp["choice"] - rec["lp"]["choice"]) < 5e-3
        checked += 1
        if checked >= 8:
            return
    assert checked >= 8, checked


def test_mu_roundtrip_temperature(net_and_feat):
    """τ≠1 mu-parity (run-7 prerequisite): serve records TEMPERED logp, so the
    recompute matches only at the generation temperature — recomputing a
    τ=0.5 record at τ=1 must trip the 0.2 tolerance on at least some casts
    (the failure mode the rl.py mu-meta fix exists to prevent)."""
    from anvil.training.rl import apply_mu_labels, composite_logp

    net, feat = net_and_feat
    checked = mismatched = 0
    for dec, header, prior in _windows({"chooseSpellAbilityToPlay"}, n=160):
        rec, lp = _roundtrip(net, feat, dec, header, prior, "priority", 577,
                             tau=0.5)
        assert abs(lp["logp"] - rec["logp"]) < 5e-3, (rec, lp)
        assert abs(lp["choice"] - rec["lp"]["choice"]) < 5e-3
        # the negative control: same record recomputed at τ=1
        import torch

        from anvil.training.dataset import collate
        ex2, _ = feat.example(_wire(dec, prior), header, "priority")
        apply_mu_labels(ex2, rec)
        b2 = collate([ex2])
        with torch.no_grad():
            lp1 = float(composite_logp(net(b2), b2)["logp"][0])
        if abs(lp1 - rec["logp"]) > 0.2:
            mismatched += 1
        checked += 1
        if checked >= 24 and mismatched >= 1:
            return
    assert checked >= 24, checked
    # the policy is peaked on most priority windows (logp≈0 barely moves
    # under tempering), so wrong-τ trips are sparse — ~2/160 on the D5 ckpt.
    # ≥1 is enough teeth: real iterations sample 10^5 decisions.
    assert mismatched >= 1, ("τ=1 recompute of τ=0.5 records never tripped "
                             "the tripwire tolerance — control has no teeth",
                             mismatched)


def test_mu_roundtrip_combat(net_and_feat):
    net, feat = net_and_feat
    checked_a = checked_b = 0
    wins = _windows({"declareAttackers", "declareBlockers"}, n=40, games=120)
    for dec, header, prior in wins:
        task = "attack" if dec["m"] == "declareAttackers" else "block"
        ex_probe, _ = feat.example(_wire(dec, prior), header, task)
        if ex_probe["cmb_rows"].shape[0] == 0:
            continue
        rec, lp = _roundtrip(net, feat, dec, header, prior, task, 2718)
        assert abs(lp["logp"] - rec["logp"]) < 5e-3, (rec, lp)
        if task == "attack":
            assert abs(lp["atk"] - rec["lp"]["atk"]) < 5e-3
            assert abs(lp["cnt"] - rec["lp"]["cnt"]) < 5e-3
            assert abs(lp["atgt"] - rec["lp"]["atgt"]) < 5e-3
            checked_a += 1
        else:
            assert abs(lp["blk"] - rec["lp"]["blk"]) < 5e-3
            checked_b += 1
    assert checked_a >= 5 and checked_b >= 3
