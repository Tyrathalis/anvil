"""M9 rung 3: the pay_class task (Option A — pointer-decoder SELECT_ONE +
per-task auto-bias, m9-rung3-draft.md session pins).

Pins under test: goal options featurize positionally with the goal-kind code
("gk") and a lowest-id representative entity (entless plans key on the kind
embedding alone); option 0 = auto rides the PASS slot with the +2.0 bias —
argmax stays auto at init (day-zero bit-identity where it matters); the mu
round-trip (mu_record -> apply_mu_labels -> forward -> composite_logp) holds
for the choice-only task; pre-M9 checkpoints load with pay_ params at their
fresh init (+2.0 / zeros). Synthetic payment windows are grafted onto real
stored obs (no stored payment windows exist pre-boundary); skips on a bare
checkout."""

import json
from pathlib import Path

import pytest

STORE = Path("data/trajectories/pilotv2-20260821-155339")  # bundle-jar fixture (M9 boundary)
EMBED = Path("data/embeddings/cf2ca6ba-qwen3.safetensors")
CKPT = Path("data/training/d5-combat/last.pt")

pytestmark = pytest.mark.skipif(
    not (STORE.exists() and EMBED.exists() and CKPT.exists()), reason="local pilot data not present"
)


@pytest.fixture(scope="module")
def net_and_feat():
    import torch

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net

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
    return net, Featurizer(stem, methods)


def _pay_windows(n=6):
    """Real priority windows rewritten into payment windows: same obs/history,
    payManaCost method, {auto} ∪ two goal options — one keyed on a real
    battlefield entity, one entless (a pay-life plan)."""
    from tests.test_sampling import _windows, _wire

    out = []
    for dec, header, prior in _windows({"chooseSpellAbilityToPlay"}, n=n * 3):
        ents = [e["e"] for e in dec["obs"].get("ents", []) if "e" in e][:3]
        if len(ents) < 2:
            continue
        w = _wire(dec, prior)
        w["m"] = "payManaCost"
        w["args"] = {"sa": "Test Spell", "cost": "1 U", "fpool": "0,0,0,0,0,0",
                     "goals": 2, "plans": 3, "trunc": False, "forced": False}
        w["opts"] = [
            '{"auto":true}',
            json.dumps({"goals": ["spare:Some Land"], "gk": [2],
                        "ents": sorted(ents), "pool": [0] * 6, "phy": 0}),
            json.dumps({"goals": ["pay_mana_not_life"], "gk": [5],
                        "ents": [], "pool": [0] * 6, "phy": 1}),
        ]
        out.append((w, header))
        if len(out) >= n:
            break
    return out


def test_pay_featurize_positional_and_kinds(net_and_feat):
    from anvil.training.dataset import PAY_KINDS

    _, feat = net_and_feat
    w, header = _pay_windows(1)[0]
    ex, aux = feat.example(w, header, "pay_class")

    assert ex["cand_rows"][0].item() == -1  # auto = the PASS slot
    assert ex["cand_rows"].shape[0] == 3  # positional: every wire option
    ents = json.loads(w["opts"][1])["ents"]
    assert ex["cand_rows"][1].item() >= 0  # lowest-id representative joined
    assert ex["cand_rows"][2].item() == -1  # entless life plan: no row
    assert ex["cand_paykind"].tolist() == [-1, PAY_KINDS["spare_land"], PAY_KINDS["min_life"]]
    assert ex["cand_sa"].tolist() == [-1, -1, -1]  # sa_vocab untouched (pinned)
    assert aux["cand_first_opt"] == [-1, 1, 2]
    assert min(ents) == sorted(ents)[0]  # the rep convention the fork sorts by


def test_day_zero_argmax_is_auto(net_and_feat):
    """The +2.0 pin's operative claim: on a pre-M9 checkpoint (fresh pay_
    params), argmax answers auto — day-zero behavior identical to today."""
    import torch

    from anvil.training.dataset import collate

    net, feat = net_and_feat
    for w, header in _pay_windows(6):
        ex, _ = feat.example(w, header, "pay_class")
        batch = collate([ex])
        with torch.no_grad():
            fwd = net(batch)
            out = net.act(batch)
        assert int(torch.argmax(fwd["policy_logits"][0]).item()) == 0
        assert int(out["choice"][0]) == 0  # act() is argmax without noise
        # both goal options stay live under the mask (the model COULD deviate)
        assert bool(batch["cand_mask"][0, 1]) and bool(batch["cand_mask"][0, 2])


def test_pay_mu_roundtrip(net_and_feat):
    """mu_record -> apply_mu_labels -> forward -> composite_logp reproduces
    the recorded behavior logp — the V-trace drift tripwire, choice-only."""
    import torch

    from anvil.policy.sampling import make_noise, mu_record, noise_seed, pad_noise
    from anvil.training.dataset import collate
    from anvil.training.rl import apply_mu_labels, composite_logp, mu_matches

    net, feat = net_and_feat
    w, header = _pay_windows(1)[0]
    ex, aux = feat.example(w, header, "pay_class")
    noise = make_noise(ex, "pay_class", 1.0, seed=noise_seed(99, w["s"]))
    batch = collate([ex])
    with torch.no_grad():
        out = net.act(batch, noise=pad_noise([noise], batch, "cpu"), temperature=1.0)
    rec = mu_record(header["g"], w["s"], "pay_class", ex, aux, out)

    assert set(rec) >= {"c", "task"} and rec["task"] == "pay_class"
    assert "tgt" not in rec and "x" not in rec  # choice-only, no other factors
    assert mu_matches(ex, rec)

    ex2, _ = feat.example(w, header, "pay_class")
    ex2 = apply_mu_labels(ex2, rec)
    b2 = collate([ex2])
    with torch.no_grad():
        terms = composite_logp(net(b2), b2, temperature=1.0)
    assert abs(float(terms["choice"][0]) - rec["lp"]["choice"]) < 1e-4


def test_load_compat_pay_params_fresh_init(net_and_feat):
    """The D5-era checkpoint predates every pay_ param: load_compat must
    accept it (pay_ allowlisted) and leave the pinned inits — bias +2.0 on
    pay_class, zero elsewhere; kind embedding all zeros (day-zero keys)."""
    import torch

    from anvil.training.dataset import TASKS

    net, _ = net_and_feat
    ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    assert not any(k.startswith("pay_") for k in ckpt["model"])  # genuinely pre-M9
    assert float(net.pay_bias[TASKS["pay_class"]]) == 2.0
    assert float(net.pay_bias.abs().sum()) == 2.0  # zero for every other task
    assert float(net.pay_kind_emb.weight.abs().sum()) == 0.0
