"""C-bundle unit checks (ADR-0054): §6c first-attempt-only grouping, the
forced-seq label parse (Â clip, agreement fallback, wr_nat), and the L_seq
contrast math. The store-join path is smoked live on a real drill fork store
(see the 2026-08-12 devlog); these pin the pure logic."""

import json

import pytest

torch = pytest.importorskip("torch")

from anvil.training.rl import rejected_events, seq_pass  # noqa: E402
from anvil.training.seqlabels import load_rows  # noqa: E402


def _dec(s, seat, turn, cast, realized):
    d = {"s": s, "p": seat, "obs": {"glob": {"turn": turn}}}
    if realized:
        d["ret"] = [{"e": 5}]
    return d


def _mu(s, c):
    return {"task": "priority", "c": c, "logp": -0.1}


def test_rejected_events_grouping_prices_chains_once():
    # seat 0, turn 3: a length-3 re-ask chain then an abandoning pass,
    # then a separate singleton veto on turn 4.
    decs = [
        _dec(0, 0, 3, cast=True, realized=False),
        _dec(1, 0, 3, cast=True, realized=False),
        _dec(2, 0, 3, cast=True, realized=False),
        _dec(3, 0, 3, cast=False, realized=False),
        _dec(4, 0, 4, cast=True, realized=False),
    ]
    mu = {0: _mu(0, 2), 1: _mu(1, 1), 2: _mu(2, 3), 3: _mu(3, 0), 4: _mu(4, 1)}

    def total(grouping):
        return sum(
            rejected_events(decs, i, d, mu[d["s"]], {}, mu=mu, grouping=grouping)
            for i, d in enumerate(decs)
            if mu[d["s"]]["c"] > 0
        )

    assert total("event") == 4  # the superseded per-attempt pricing
    assert total("first") == 2  # one per veto window (ADR-0054 C3)


def test_rejected_events_first_needs_same_seat_and_turn():
    decs = [
        _dec(0, 0, 3, cast=True, realized=False),
        _dec(1, 1, 3, cast=True, realized=False),  # other seat: own window
        _dec(2, 1, 4, cast=True, realized=False),  # turn changed: own window
    ]
    mu = {i: _mu(i, 1) for i in range(3)}
    assert (
        sum(
            rejected_events(decs, i, d, mu[i], {}, mu=mu, grouping="first")
            for i, d in enumerate(decs)
        )
        == 3
    )


def _label_row(**kw):
    r = {
        "i": 7,
        "fp": 1,
        "t": 9,
        "seq": True,
        "k": 16,
        "n": 4,
        "seat": "Anvil(1)-dc-1",
        "triples": 16,
        "w_nat": [10, 6],
        "w_hold": [4, 12],
        "w_act": [12, 4],
        "act_first_modal": "Cast Lightning Bolt",
        "act_first_agree": 0.8,
    }
    r.update(kw)
    return r


def test_load_rows_advantage_clip_and_fallback(tmp_path):
    f = tmp_path / "labels.jsonl"
    rows = [
        _label_row(),  # adv = (12-4)/16 = 0.5 -> clipped to 0.25
        _label_row(i=8, act_first_agree=0.3),  # low agreement -> mass fallback
        _label_row(i=9, seat_skip=True),  # dropped
        _label_row(i=10, w_act=[2, 14], w_hold=[6, 10]),  # adv=-0.25 exactly
    ]
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = load_rows([str(f)])
    assert len(out) == 3
    by_i = {r["key"][0]: r for r in out}
    assert by_i[7]["adv"] == 0.25 and by_i[7]["cast_star"] == "Cast Lightning Bolt"
    assert by_i[7]["wr_nat"] == 10 / 16
    assert by_i[8]["cast_star"] is None  # agreement below threshold
    assert by_i[10]["adv"] == -0.25


def test_seq_pass_contrast_math():
    # one segment, two windows, three candidates (PASS + 2). Window 0
    # targets candidate 1 with adv +0.2; window 1 is mass-fallback (both
    # nonpass) with adv -0.1. Hand-check L_seq against the formula.
    logits = torch.tensor([[0.0, 1.0, -1.0], [0.5, 0.5, 0.5]], requires_grad=True)
    seg = {
        "seq_adv": torch.tensor([0.2, -0.1]),
        "seq_tmask": torch.tensor([[False, True, False], [False, True, True]]),
        "seq_wr": torch.tensor([0.6, 0.4]),
        "x": torch.zeros(2),  # any tensor supplies the batch dim
    }
    fwd = {"policy_logits": logits, "value_logit": torch.tensor([0.1, -0.2], requires_grad=True)}

    def fake_forward_segments(net, segs, grad):
        yield segs[0], fwd

    raw, aux = seq_pass(None, [seg], fake_forward_segments, w_seq=1.0, aux_w=0.0, grad=False)
    lp = logits.log_softmax(1)
    c0 = lp[0, 1] - lp[0, 0]
    c1 = torch.logsumexp(lp[1, 1:], 0) - lp[1, 0]
    expect = -(0.2 * c0 + (-0.1) * c1) / 2
    assert abs(raw - float(expect)) < 1e-5
    assert aux > 0  # BCE toward wr targets

    # grad=True must backward without error and leave gradients
    raw2, _ = seq_pass(None, [seg], fake_forward_segments, w_seq=1.0, aux_w=0.5, grad=True)
    assert logits.grad is not None and abs(raw2 - raw) < 1e-5
