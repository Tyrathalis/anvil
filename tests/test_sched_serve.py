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


def test_pay_mark_and_follow():
    """M10 R5 actuation pin 1: at a pay window with remaining scheduled
    slots, one explicit goal option gets the mark (never auto), the mark
    rides ex + the fed mu row, and follow/deviate telemetry counts."""
    import json as _json

    ss = SchedServe(_feat())
    _emit(ss, choice=0)  # slot pending, nothing awaited
    pay_opts = [
        "{}",  # option 0 = auto
        _json.dumps({"ents": [10], "gk": [1]}),  # taps the scheduled entity
        _json.dumps({"ents": [99], "gk": [2]}),  # taps something else
    ]
    dec = _dec(s=101, opts=pay_opts)
    dec["m"] = "payManaCost"
    ex = {}
    ex["cand_rows"] = torch.zeros(3, dtype=torch.int64)  # width for the mark
    ctx = ss.inject(ex, AUX, dec, HDR, "pay_class")
    assert ctx is not None and not ctx["decode"]
    assert ctx["mark"] is not None and ctx["mark"] != 0  # never auto
    assert ctx["fed"]["mark"] == ctx["mark"]
    assert "cand_paymark" in ex and float(ex["cand_paymark"][ctx["mark"]]) == 1.0
    assert float(ex["cand_paymark"].sum()) == 1.0
    ss.after(ctx, {"choice": torch.tensor([ctx["mark"]])}, AUX, dec)
    assert ss.counts["sched_paymark_follow"] == 1
    ctx2 = ss.inject({"cand_rows": torch.zeros(3, dtype=torch.int64)},
                     AUX, dec, HDR, "pay_class")
    ss.after(ctx2, {"choice": torch.tensor([0])}, AUX, dec)
    assert ss.counts["sched_paymark_deviate"] == 1


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


# ---------------------------------------------------------------- binding
# M10 reset (ADR-0094 Fork 1): binding execution at serve — land-first,
# the NEXT slot forced, hold on spells, absent-NEXT = trigger 1, the forks
# scope latching the opening seat, and the mask riding ex/cand_allow.


def _opts(*items):
    """items: (e, sa, kind) -> opts with Pass at 0."""
    return [{"e": -1, "sa": "Pass"}] + [{"e": e, "sa": sa, "kind": k} for e, sa, k in items]


def _aux_for(opts):
    return {
        "row_of": {o["e"]: i for i, o in enumerate(opts[1:])},
        "cand_first_opt": [-1] + list(range(1, len(opts))),
    }


def _bind_feat():
    ids = {"Cast Foo": 7, "Cast Bar": 8, "Play Land": 9, "Tap: add": 10}
    return types.SimpleNamespace(sa_vocab=types.SimpleNamespace(id=lambda s: ids.get(s, 99)))


def _emit_bound(ss, opts, picks, hdr=HDR, dec_kw=None):
    aux = _aux_for(opts)
    dec = _dec(opts=opts, **(dec_kw or {}))
    ex = {}
    ctx = ss.inject(ex, aux, dec, hdr, "priority")
    assert ctx["decode"] and ctx["bind"]
    ss.after(ctx, _out(picks=picks), aux, dec, track=False)  # planning pass
    ctx = {**ctx, "decode": False}
    return ss, ctx, ex, aux, dec


def test_bind_land_first_then_forced_next_then_hold():
    ss = SchedServe(_bind_feat(), binding="all")
    opts = _opts((10, "Cast Foo", "spell"), (11, "Cast Bar", "spell"), (12, "Play Land", "land"))
    ss, ctx, ex, aux, dec = _emit_bound(ss, opts, picks=(1, 2, 0, 0, 0, 0))
    # rule 1: a land option at a quiescent MAIN1 window -> lands only
    b = ss.bind(ctx, ex, aux, dec)
    assert b["kind"] == "land" and b["allow"] == [3]
    assert ex["cand_allow"].tolist() == [False, False, False, True]
    # the land played: next own window has no land option -> NEXT forced
    opts2 = _opts((10, "Cast Foo", "spell"), (11, "Cast Bar", "spell"))
    aux2, dec2 = _aux_for(opts2), _dec(opts=opts2, s=101)
    ex2 = {}
    ctx2 = ss.inject(ex2, aux2, dec2, HDR, "priority")
    assert not ctx2["decode"]
    b2 = ss.bind(ctx2, ex2, aux2, dec2)
    assert b2["kind"] == "cast" and b2["allow"] == [1] and b2["slot"] == 0
    assert ex2["cand_allow"].tolist() == [False, True, False]
    row2 = ss.after(ctx2, _out(choice=1), aux2, dec2)
    assert ss.states[(5, 0)].awaiting == 0 and row2["st"] == "np"
    # slot 0 done, slot 1 = NEXT; Bar is castable -> forced again
    opts3 = _opts((11, "Cast Bar", "spell"), (13, "Tap: add", "ability"))
    aux3, dec3 = _aux_for(opts3), _dec(opts=opts3, s=102)
    ex3 = {}
    ctx3 = ss.inject(ex3, aux3, dec3, HDR, "priority")
    b3 = ss.bind(ctx3, ex3, aux3, dec3)
    assert b3["kind"] == "cast" and b3["allow"] == [1] and b3["slot"] == 1
    ss.after(ctx3, _out(choice=1), aux3, dec3)
    # exhausted (trigger 4 will revise); until then: hold on spells =
    # pass + the ability, spells closed
    opts4 = _opts((14, "Cast Foo", "spell"), (13, "Tap: add", "ability"))
    aux4, dec4 = _aux_for(opts4), _dec(opts=opts4, s=103, ph="MAIN2")
    ex4 = {}
    ctx4 = ss.inject(ex4, aux4, dec4, HDR, "priority")
    assert ctx4["decode"] and ctx4["trigger"] == "exhaust"
    ss.after(ctx4, _out(picks=(0, 0, 0, 0, 0, 0)), aux4, dec4, track=False)
    b4 = ss.bind({**ctx4, "decode": False}, ex4, aux4, dec4)
    assert b4["kind"] == "hold" and b4["allow"] == [0, 2]
    assert ss.counts["sched_bind_land"] == 1 and ss.counts["sched_bind_cast"] == 2
    assert ss.counts["sched_bind_hold"] == 1


def test_bind_absent_next_is_trigger_one_only_when_quiescent():
    ss = SchedServe(_bind_feat(), binding="all")
    opts = _opts((10, "Cast Foo", "spell"), (11, "Cast Bar", "spell"))
    ss, ctx, ex, aux, dec = _emit_bound(ss, opts, picks=(1, 0, 0, 0, 0, 0))
    assert ss.bind(ctx, ex, aux, dec)["kind"] == "cast"
    # stack up (own trigger): Foo not castable -> HOLD, no revision
    stack_ents = [{"e": 10, "n": "Foo", "z": "hand", "c": 0}, {"e": 50, "n": "Trig", "z": "stack", "c": 0}]
    opts_s = _opts((11, "Cast Bar", "spell"))
    aux_s, dec_s = _aux_for(opts_s), _dec(opts=opts_s, s=101, ents=stack_ents)
    ex_s = {}
    ctx_s = ss.inject(ex_s, aux_s, dec_s, HDR, "priority")
    assert not ctx_s["decode"] and ss.counts["sched_bind_absent"] == 0
    assert ss.bind(ctx_s, ex_s, aux_s, dec_s)["kind"] == "hold"
    assert ss.states[(5, 0)].slots[0].st == "n"
    # quiescent MAIN1, no land, Foo gone (discarded) -> trigger 1 "absent"
    aux_q, dec_q = _aux_for(opts_s), _dec(opts=opts_s, s=102)
    ex_q = {}
    ctx_q = ss.inject(ex_q, aux_q, dec_q, HDR, "priority")
    assert ctx_q["decode"] and ctx_q["trigger"] == "absent"
    assert ss.counts["sched_bind_absent"] == 1
    assert ss.states[(5, 0)].slots[0].st == "f"
    row = ss.after(ctx_q, _out(picks=(1, 0, 0, 0, 0, 0)), aux_q, dec_q, track=False)
    assert row["emit"] == 1 and row["trigger"] == "absent" and row["rev"] == 1
    b = ss.bind({**ctx_q, "decode": False}, ex_q, aux_q, dec_q)
    assert b["kind"] == "cast" and b["allow"] == [1]  # the revised plan binds here


def test_bind_scope_forks_latches_opening_seat_and_off_mode_never_binds():
    opts = _opts((10, "Cast Foo", "spell"))
    aux = _aux_for(opts)
    # off: advisory — ctx carries bind=False, bind() returns None
    ss = SchedServe(_bind_feat(), binding="off")
    ctx = ss.inject({}, aux, _dec(opts=opts), HDR, "priority")
    assert ctx["bind"] is False and ss.bind(ctx, {}, aux, _dec(opts=opts)) is None
    # forks: a store-indexed game never binds; a wire session binds the
    # seat that opened it, not the other seat
    ss = SchedServe(_bind_feat(), binding="forks")
    ctx = ss.inject({}, aux, _dec(opts=opts), HDR, "priority")
    assert ctx["bind"] is False
    wire = {"g": -1, "wid": "g3.f0r1s0"}
    ctx1 = ss.inject({}, aux, _dec(opts=opts, p=1, ap=1), wire, "priority")
    assert ctx1["bind"] is True and ss.bind_seat["g3.f0r1s0"] == 1
    assert ctx1["key"] == ("g3.f0r1s0", 1)
    ctx0 = ss.inject({}, aux, _dec(opts=opts, p=0, ap=0, t=4), wire, "priority")
    assert ctx0["bind"] is False  # the opponent seat: advisory
    assert ss.counts["sched_bind_seat_latched"] == 1


def test_sched_lp_rides_decode_rows():
    ss = SchedServe(_bind_feat(), binding="off")
    opts = _opts((10, "Cast Foo", "spell"))
    aux, dec = _aux_for(opts), _dec(opts=opts)
    ctx = ss.inject({}, aux, dec, HDR, "priority")
    out = _out(picks=(1, 0, 0, 0, 0, 0))
    out["sched_lp"] = torch.tensor([-0.25])
    row = ss.after(ctx, out, aux, dec)
    assert row["emit"] == 1 and row["lp"] == -0.25
