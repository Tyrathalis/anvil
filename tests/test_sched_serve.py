"""M10 v2: the serve-side schedule carry (m10-build-spec §3, sched_serve.py).

Stub-driven contract tests (the test_serve_carry_semantics pattern): emission
at the first own MAIN1 priority window, conditioning fed on later windows
with statuses advancing, revision ONLY at the four triggers, off-turn/
off-seat windows idle, turn advance resets, exhaustion never refires into a
decode loop, and the mu `sched` row serializes exactly what was fed."""

import types

import torch

from anvil.bridge.sched_serve import SchedServe


def _feat():
    return types.SimpleNamespace(sa_vocab=types.SimpleNamespace(id=lambda s: 7))


def _dec(t=3, ph="MAIN1", ap=0, p=0, s=100, hist=None, retry=False, ents=None, opts=None):
    d = {
        "p": p,
        "t": t,
        "s": s,
        "m": "chooseSpellAbilityToPlay",
        "obs": {
            "glob": {"ph": ph, "ap": ap},
            "ents": ents if ents is not None else [{"e": 10, "n": "Foo", "z": "hand", "c": p}],
            "players": [{}, {}],
        },
        "opts": opts
        if opts is not None
        else [{"e": -1, "sa": "Pass"}, {"e": 10, "sa": "Cast Foo", "kind": "spell"}],
        "hist": hist or [],
    }
    if retry:
        d["retry_of"] = True
    return d


AUX = {"row_of": {10: 0}, "cand_first_opt": [-1, 1]}
HDR = {"g": 5}


def _out(picks=(1, 0, 0, 0, 0, 0), choice=0):
    return {
        "sched_picks": torch.tensor([list(picks)]),
        "choice": torch.tensor([choice]),
    }


def _emit(ss, dec=None, choice=0):
    ctx = ss.inject({}, AUX, dec or _dec(), HDR, "priority")
    assert ctx is not None and ctx["decode"] and ctx["trigger"] == "emit"
    return ss.after(ctx, _out(choice=choice), AUX, dec or _dec())


def test_emission_and_feed():
    ss = SchedServe(_feat())
    ex = {}
    dec = _dec()
    ctx = ss.inject(ex, AUX, dec, HDR, "priority")
    assert ctx["decode"] and ctx["trigger"] == "emit" and ctx["fed"] is None
    assert "sched_mask" not in ex  # emission window: no conditioning
    row = ss.after(ctx, _out(picks=(1, 1, 0, 0, 0, 0), choice=1), AUX, dec)
    assert row["emit"] == 1 and row["new"] == [[10, 7], [10, 7]] and row["rev"] == 0
    st = ss.states[(5, 0)]
    assert [s.st for s in st.slots] == ["n", "p"]
    assert st.awaiting == 0  # the answer executed the NEXT slot
    # next own window: slot 0 done + slot 1 promoted, conditioning fed,
    # serialization verbatim (a completed 2-slot plan is not yet exhausted)
    ex2 = {}
    dec2 = _dec(s=101)
    ctx2 = ss.inject(ex2, AUX, dec2, HDR, "priority")
    assert not ctx2["decode"]
    assert ex2["sched_mask"].tolist() == [True, True] + [False] * 4
    assert ex2["sched_rows"][0] == 0 and ex2["sched_sa"][0] == 7
    assert ctx2["fed"]["st"] == "dn" and ctx2["fed"]["slots"] == [[10, 7], [10, 7]]
    row2 = ss.after(ctx2, _out(choice=0), AUX, dec2)
    assert row2["emit"] == 0 and row2["st"] == "dn"


def test_trigger_veto_marks_failed_and_revises():
    ss = SchedServe(_feat())
    _emit(ss, choice=1)
    dec = _dec(s=101, retry=True)
    ctx = ss.inject({}, AUX, dec, HDR, "priority")
    st = ss.states[(5, 0)]
    assert st.slots[0].st == "f"
    assert ctx["decode"] and ctx["trigger"] == "veto"
    row = ss.after(ctx, _out(choice=0), AUX, dec)
    assert row["emit"] == 1 and row["rev"] == 1
    # the failed slot was CONSUMED by the revision (user pin 2026-08-27)
    assert [s.st for s in ss.states[(5, 0)].slots] == ["n"]
    assert ss.counts["sched_rev_veto"] == 1


def test_trigger_opp_action():
    ss = SchedServe(_feat())
    _emit(ss)
    h = [{"m": "chooseSpellAbilityToPlay", "p": 1, "e": 44}]
    dec = _dec(s=101, hist=h)
    ctx = ss.inject({}, AUX, dec, HDR, "priority")
    assert ctx["decode"] and ctx["trigger"] == "opp"
    ss.after(ctx, _out(), AUX, dec)
    # same signature again: NO retrigger (plan stability between triggers)
    ctx2 = ss.inject({}, AUX, _dec(s=102, hist=h), HDR, "priority")
    assert not ctx2["decode"]


def test_trigger_eot_once():
    ss = SchedServe(_feat())
    _emit(ss)
    dec = _dec(s=101, ph="END_OF_TURN")
    ctx = ss.inject({}, AUX, dec, HDR, "priority")
    assert ctx["decode"] and ctx["trigger"] == "eot"
    ss.after(ctx, _out(), AUX, dec)
    ctx2 = ss.inject({}, AUX, _dec(s=102, ph="END_OF_TURN"), HDR, "priority")
    assert not ctx2["decode"]  # once per turn


def test_trigger_exhaust_no_refire_loop():
    ss = SchedServe(_feat())
    _emit(ss, choice=1)  # slot awaiting
    dec = _dec(s=101)
    ctx = ss.inject({}, AUX, dec, HDR, "priority")  # slot -> done -> exhausted
    assert ctx["decode"] and ctx["trigger"] == "exhaust"
    ss.after(ctx, _out(picks=(0, 0, 0, 0, 0, 0)), AUX, dec)  # pure-hold revision
    assert ss.counts["sched_pure_hold"] == 1
    # empty schedule: exhaust must NOT refire into a decode loop
    ctx2 = ss.inject({}, AUX, _dec(s=102), HDR, "priority")
    assert not ctx2["decode"]


def test_off_turn_off_seat_and_turn_reset():
    ss = SchedServe(_feat())
    _emit(ss)
    assert ss.inject({}, AUX, _dec(s=101, ap=1), HDR, "priority") is None  # opp turn
    ex = {}
    ctx = ss.inject(ex, AUX, _dec(s=102, t=4), HDR, "priority")  # new turn
    assert ctx["decode"] and ctx["trigger"] == "emit" and "sched_mask" not in ex


def test_deviation_counting():
    ss = SchedServe(_feat())
    opts = [
        {"e": -1, "sa": "Pass"},
        {"e": 10, "sa": "Cast Foo", "kind": "spell"},
        {"e": 11, "sa": "Cast Bar", "kind": "spell"},
    ]
    ents = [
        {"e": 10, "n": "Foo", "z": "hand", "c": 0},
        {"e": 11, "n": "Bar", "z": "hand", "c": 0},
    ]
    aux = {"row_of": {10: 0, 11: 1}, "cand_first_opt": [-1, 1, 2]}
    dec = _dec(ents=ents, opts=opts)
    ctx = ss.inject({}, aux, dec, HDR, "priority")
    ss.after(ctx, {"sched_picks": torch.tensor([[1, 2, 0, 0, 0, 0]]),
                   "choice": torch.tensor([2])}, aux, dec)
    # answered Bar while Foo was NEXT: a later-slot deviation, statuses hold
    assert ss.counts["sched_dev_later_slot"] == 1
    st = ss.states[(5, 0)]
    assert [s.st for s in st.slots] == ["n", "p"] and st.awaiting is None
