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


def test_pay_param_group_splits_by_name(net_and_feat):
    """M9 D4 recipe pin 2: the fresh payment params get their own step size
    while the trunk keeps the pinned 1e-5. The loop takes ~417 optimizer steps
    per iteration, so at trunk lr the head displaces <=0.03 across a whole
    probe run — a false clean negative on the branch that retires the
    formulation. Split is by name so the grouping stays auditable."""
    import torch

    net, _ = net_and_feat
    pay = [n for n, _ in net.named_parameters() if n.startswith("pay_")]
    # pay_mark_emb joined at M10 R5 (the slot-conditions marked candidate,
    # zero-init) — a pay-surface param, rightly in the pay_lr group
    assert set(pay) == {"pay_bias", "pay_kind_emb.weight", "pay_mark_emb",
                        "pay_query.weight", "pay_query.bias", "pay_key.weight", "pay_key.bias",
                        "pay_gate.weight", "pay_gate.bias"}  # + the evening-4 role copies + the 09-11 deviation gate

    groups = [
        {"params": [p for n, p in net.named_parameters() if not n.startswith("pay_")], "lr": 1e-5},
        {"params": [p for n, p in net.named_parameters() if n.startswith("pay_")], "lr": 1e-3},
    ]
    opt = torch.optim.AdamW(groups, lr=1e-5, weight_decay=0.0)
    # every parameter lands in exactly one group
    assert sum(len(g["params"]) for g in opt.param_groups) == len(list(net.parameters()))
    assert opt.param_groups[0]["lr"] == 1e-5 and opt.param_groups[1]["lr"] == 1e-3

    # one coherent step moves the payment params ~100x further than the trunk
    for p in net.parameters():
        p.grad = torch.ones_like(p)
    before = {n: p.detach().clone() for n, p in net.named_parameters()}
    opt.step()
    moved = {
        n: float((p.detach() - before[n]).abs().max())
        for n, p in net.named_parameters()
        if p.grad is not None
    }
    assert moved["pay_bias"] == pytest.approx(1e-3, rel=0.05)
    trunk = max(v for n, v in moved.items() if not n.startswith("pay_"))
    assert trunk == pytest.approx(1e-5, rel=0.05)


def test_pay_role_copies_init_and_set_key(net_and_feat):
    """Evening 4 (ADR-0105): the payment role-copy head — pay_query / pay_key
    start as copies of the priority pointer's maps (load_compat), a goal's
    plan reaches the model as an entity SET (cand_ents), the pay branch
    scores pay windows only (a priority window's logits are byte-identical
    with the head present), and the day-zero argmax stays auto."""
    import torch

    from anvil.bridge.featurize import PAY_SET_K
    from anvil.training.dataset import collate

    net, feat = net_and_feat
    # the module fixture is shared and an earlier test steps the pay_ group:
    # reload the checkpoint so the role-init claim is read on a fresh load
    net.load_compat(torch.load(CKPT, map_location="cpu", weights_only=False)["model"])
    assert torch.equal(net.pay_query.weight, net.ptr_query.weight)
    assert torch.equal(net.pay_key.bias, net.ptr_key.bias)
    saved = {n: p.detach().clone() for n, p in net.named_parameters() if n.startswith("pay_")}
    w, header = _pay_windows(1)[0]
    ex, _ = feat.example(w, header, "pay_class")
    assert ex["cand_ents"].shape == (3, PAY_SET_K)
    assert (ex["cand_ents"][0] == -1).all()  # auto: no set
    ents = json.loads(w["opts"][1])["ents"]
    assert int((ex["cand_ents"][1] >= 0).sum()) == min(len(ents), PAY_SET_K)  # the plan's entities
    assert (ex["cand_ents"][2] == -1).all()  # the entless life plan
    batch = collate([ex])
    assert batch["cand_ents"].shape == (1, 3, PAY_SET_K)
    with torch.no_grad():
        fwd = net(batch)
        # the branch is live: perturbing pay_key moves a goal's logit, never auto's
        base = fwd["policy_logits"][0].clone()
        net.pay_key.weight.add_(0.01)
        moved = net(batch)["policy_logits"][0]
        net.pay_key.weight.sub_(0.01)
    assert int(torch.argmax(base).item()) == 0
    assert not torch.allclose(base[1:], moved[1:])
    # a PRIORITY window never touches the pay maps
    from tests.test_sampling import _windows, _wire

    dec, hdr, prior = next(iter(_windows({"chooseSpellAbilityToPlay"}, n=1)))
    pex, _ = feat.example(_wire(dec, prior), hdr, "priority")
    pb = collate([pex])
    with torch.no_grad():
        l0 = net(pb)["policy_logits"].clone()
        net.pay_key.weight.add_(0.1)
        net.pay_query.weight.add_(0.1)
        l1 = net(pb)["policy_logits"]
        for n, p in net.named_parameters():
            if n in saved:
                p.copy_(saved[n])  # exact restore for the tests that follow
    assert torch.equal(l0, l1)


def test_pay_deviation_gate_init_and_loss(net_and_feat):
    """The deviation gate (ADR-0105 addendum 09-11): a fresh gate sits at the
    pool's base rate (P ≈ 0.11, never clears a serve threshold), forward and
    act expose it, the distillation loss adds its BCE only when weighted, and
    the fit's curve read runs over the stats' raw rows."""
    import math

    import torch

    from anvil.training.dataset import collate, default_methods
    from anvil.training.pay_distill import pay_distill_loss
    from anvil.training.pay_fit import gate_curve
    from anvil.training.train import build_net

    net, feat = net_and_feat
    # the init on a FRESH net (the module fixture's net is stepped by an
    # earlier test): zero weights, the base-rate bias
    cfg = torch.load(CKPT, map_location="cpu", weights_only=False)["config"]
    fresh = build_net(str(EMBED).removesuffix(".safetensors"), cfg["pool_manifest"],
                      len(default_methods()), n_sa=cfg.get("sa_vocab_size", 0))
    assert float(fresh.pay_gate.weight.detach().abs().sum()) == 0.0
    assert abs(float(fresh.pay_gate.bias.detach()) + 2.05) < 1e-6
    del fresh
    with torch.no_grad():
        net.pay_gate.weight.zero_()
        net.pay_gate.bias.fill_(-2.05)
    exs = [feat.example(w, header, "pay_class")[0] for w, header in _pay_windows(4)]
    batch = collate(exs)
    n = batch["cand_mask"].shape[1]
    batch["pay_target"] = torch.zeros(4, n)
    batch["pay_target"][:, 0] = 1.0
    batch["pay_target"][0] = 0.0
    batch["pay_target"][0, 1] = 1.0  # one positive row
    batch["pay_positive"] = torch.tensor([True, False, False, False])
    batch["pay_margin"] = torch.tensor([0.05, 0.0, 0.0, 0.0])
    batch["pay_vals"] = torch.full((4, n), float("nan"))
    batch["pay_vals"][:, 0] = 0.5
    batch["pay_vals"][:, 1] = 0.55
    with torch.no_grad():
        fwd = net(batch)
        out = net.act(batch)
    assert fwd["pay_gate"].shape == (4,)
    assert all(abs(float(v) - 1 / (1 + math.exp(2.05))) < 1e-4 for v in out["pay_gate"])
    l0, st0 = pay_distill_loss(fwd, batch)
    l1, st1 = pay_distill_loss(fwd, batch, gate_weight=1.0)
    assert float(l1) > float(l0)  # the gate's BCE joined the loss
    assert st1["_gate"].shape == (4, 4)
    curve = gate_curve(st1["_gate"].numpy())
    assert curve["n"] == 4 and curve["n_pos"] == 1 and len(curve["curve"]) > 0
