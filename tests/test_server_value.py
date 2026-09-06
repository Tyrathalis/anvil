"""M12 Build 0 (ADR-0101 §1): the anvil.value ask and the greedy search-copy
session rule on the decision server."""
from collections import Counter
from types import SimpleNamespace

import torch

from anvil.bridge import server as srv
from anvil.bridge.server import ModelBackend


class _Feat:
    def example(self, dec, header, task):
        assert task == "priority" and dec["k"] == "peek"
        return {"ex": dec["p"]}, {}


class _Batcher:
    def __init__(self, win):
        self.win = win
        self.calls = []

    def submit(self, ex, pass_delta, noise):
        self.calls.append((ex, pass_delta, noise))
        return {"win": torch.tensor([self.win])}


def _backend(win):
    return SimpleNamespace(feat=_Feat(), batcher=_Batcher(win), counts=Counter())


def _req(obs):
    return srv.pb.DecisionRequest(
        game_id="g1.s0r0o2", decision_seq=7, decision_tag=srv.VALUE_TAG,
        shape=srv.pb.INT_IN_RANGE, observation=obs.encode(),
    )


def test_value_answer_micro_units_and_no_noise():
    be = _backend(0.7312)
    resp = ModelBackend.value(be, _req('{"k":"peek","p":1,"t":4,"opts":[],"obs":{}}'), {"g": -1})
    assert resp.decision_seq == 7 and resp.value == 731200
    assert be.batcher.calls == [({"ex": 1}, 0.0, None)]  # no pass delta, no sampling noise
    assert be.counts["value"] == 1


def test_value_answer_declines_without_header_or_observation():
    be = _backend(0.5)
    assert ModelBackend.value(be, _req('{"k":"peek","p":0,"opts":[],"obs":{}}'), None) is None
    assert ModelBackend.value(be, srv.pb.DecisionRequest(decision_seq=1), {"g": -1}) is None


def test_value_clamped_to_unit_interval():
    assert ModelBackend.value(_backend(1.7), _req('{"k":"peek","p":0,"opts":[],"obs":{}}'), {}).value == 1_000_000
    assert ModelBackend.value(_backend(-0.2), _req('{"k":"peek","p":0,"opts":[],"obs":{}}'), {}).value == 0


def test_search_sessions_are_named_by_the_s_infix():
    assert srv.is_search_session("g12.s3r0o4")
    assert not srv.is_search_session("g12")
    assert not srv.is_search_session("g12.f2r1")  # a drill fork completion, not a search copy


def test_servicer_value_answer_falls_back_loudly_on_error():
    class _Boom:
        def value(self, req, header):
            raise RuntimeError("no head")

    svc = SimpleNamespace(mode="model", backend=_Boom(), fallbacks=Counter())
    resp = srv.DecisionServicer._value_answer(svc, _req("{}"), {})
    assert resp.fallback and resp.decision_seq == 7 and svc.fallbacks[srv.VALUE_TAG] == 1
