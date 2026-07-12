"""CastPlan label contract (M1 D2): parse + validate synthetic frames.

Frames mimic the Java writer's D2 output: priority decs carry structured opts
({"e","sa","kind"} objects), rets carry CastPlan objects, and each cast is
followed by a playChosenSpellAbility window for the same seat. The Java side
is pinned by the D2 smoke run; these tests pin the Python contract.
"""

import json

import zstandard

from anvil.store import OBS_SCHEMA_VERSION, decode_frame, parse_ret
from anvil.store.castplan import ValidationReport, validate_game
from anvil.store.trajectories import GameTrajectory

BOLT = {"e": 81, "sa": "Lightning Bolt - deals 3 damage", "kind": "spell",
        "tgt": [{"pi": 1}]}
KICKED = {"e": 90, "sa": "Rite of Replication (Kicked)", "kind": "spell",
          "tgt": [{"e": 55}], "x": None, "opt": ["Kicker1"]}
LAND = {"e": 70, "sa": "Play Mountain", "kind": "land"}


def _obs(ents=(70, 81, 90, 55), stack=()):
    obs = {
        "glob": {"turn": 3, "ph": "MAIN1", "ap": 0},
        "players": [{"life": 40}, {"life": 38}],
        "ents": [{"e": e, "n": f"C{e}", "z": "hand", "c": 0} for e in ents],
    }
    if stack:
        obs["stack"] = [{"e": e, "c": 1, "lbl": f"S{e}"} for e in stack]
    return obs


def _dec(s, method, p=0, obs=None, opts=None, args=None, ret="__absent__"):
    d = {"k": "dec", "s": s, "t": 3, "ph": "MAIN1", "p": p, "m": method, "d": 10}
    if obs is not None:
        d["obs"] = obs
    if opts is not None:
        d["opts"] = opts
    if args is not None:
        d["args"] = args
    if ret != "__absent__":
        d["ret"] = ret
    return d


def _traj(decisions):
    header = {"k": "game", "sv": OBS_SCHEMA_VERSION, "g": 0, "seed": 1, "fmt": "Commander",
              "players": [{"name": "P0", "deck": "D0"}, {"name": "P1", "deck": "D1"}]}
    return GameTrajectory(header, decisions, {"k": "end", "status": "won", "winner": 0}, {})


OPTS = [{"e": 81, "sa": "Lightning Bolt - deals 3 damage", "kind": "spell"},
        {"e": 70, "sa": "Play Mountain", "kind": "land"}]


def test_parse_ret_shapes():
    assert parse_ret(None) is None
    plans = parse_ret([KICKED])
    assert len(plans) == 1
    p = plans[0]
    assert p.host == 90 and p.kind == "spell"
    assert p.optional_costs == ["Kicker1"] and p.multikicker == 0
    assert list(p.all_target_refs) == [{"e": 55}]
    # nested modes + sub targets both feed all_target_refs
    modal = parse_ret([{"e": 1, "sa": "Charm", "kind": "spell",
                        "modes": [{"e": 1, "sa": "Mode A", "kind": "other", "tgt": [{"pi": 0}]}],
                        "sub": [{"i": 2, "tgt": [{"e": 55}]}]}])[0]
    assert {"pi": 0} in list(modal.all_target_refs)
    assert {"e": 55} in list(modal.all_target_refs)


def test_validate_clean_game():
    decs = [
        _dec(0, "chooseSpellAbilityToPlay", obs=_obs(), opts=OPTS, ret=[BOLT]),
        _dec(1, "playChosenSpellAbility", args={"sa": "Lightning Bolt - deals 3 damage"}),
        _dec(2, "chooseSpellAbilityToPlay", p=1, obs=_obs(), ret=None),
        _dec(3, "chooseSpellAbilityToPlay", obs=_obs(), opts=[], ret=None),
    ]
    r = ValidationReport()
    validate_game(_traj(decs), r)
    assert r.ok, r.errors
    assert r.windows == 3 and r.casts == 1 and r.passes == 2
    assert r.windows_with_opts == 2  # empty structured opts list still counts
    assert r.with_targets == 1


def test_validate_catches_bad_refs():
    decs = [
        # host 99 not observed; target e=123 not observed; pi out of range
        _dec(0, "chooseSpellAbilityToPlay", obs=_obs(), opts=OPTS,
             ret=[{"e": 99, "sa": "Ghost", "kind": "spell",
                   "tgt": [{"e": 123}, {"pi": 5}]}]),
    ]
    r = ValidationReport()
    validate_game(_traj(decs), r)
    msgs = " | ".join(r.errors)
    assert "host e=99" in msgs and "target e=123" in msgs and "pi=5" in msgs
    # chosen not among options is also flagged
    assert "not among 2 options" in msgs


def test_validate_stack_target_ok():
    counterspell = {"e": 81, "sa": "Counterspell", "kind": "spell",
                    "tgt": [{"e": 200, "stk": 1}]}
    decs = [_dec(0, "chooseSpellAbilityToPlay", obs=_obs(stack=[200]),
                 opts=[{"e": 81, "sa": "Counterspell", "kind": "spell"}],
                 ret=[counterspell]),
            _dec(1, "playChosenSpellAbility", args={"sa": "Counterspell"})]
    r = ValidationReport()
    validate_game(_traj(decs), r)
    assert r.ok, r.errors


def test_validate_play_mismatch_and_seat_isolation():
    decs = [
        _dec(0, "chooseSpellAbilityToPlay", obs=_obs(), opts=OPTS, ret=[BOLT]),
        # opponent's play window must NOT consume seat 0's pending label
        _dec(1, "playChosenSpellAbility", p=1, args={"sa": "Something Else"}),
        _dec(2, "playChosenSpellAbility", p=0, args={"sa": "Wrong Spell"}),
    ]
    r = ValidationReport()
    validate_game(_traj(decs), r)
    assert len(r.errors) == 1
    assert "!= played" in r.errors[0]


def test_validate_string_opts_are_not_structured():
    """M0 bridged-path opts are plain strings incl. 'pass'; no opts checks."""
    decs = [_dec(0, "chooseSpellAbilityToPlay", obs=_obs(),
                 opts=["pass", "Lightning Bolt - deals 3 damage"], ret=[BOLT]),
            _dec(1, "playChosenSpellAbility", args={"sa": "Lightning Bolt"})]
    r = ValidationReport()
    validate_game(_traj(decs), r)
    assert r.ok, r.errors
    assert r.windows_with_opts == 0


def test_roundtrip_through_frame():
    """The D2 record shapes survive the zstd frame + decode_frame join."""
    recs = [
        {"k": "game", "sv": OBS_SCHEMA_VERSION, "g": 7, "seed": 3, "fmt": "Commander",
         "players": [{"name": "P0"}, {"name": "P1"}]},
        _dec(0, "chooseSpellAbilityToPlay", obs=_obs(), opts=OPTS),
        {"k": "ret", "s": 0, "v": [LAND]},
        {"k": "end", "status": "won", "winner": 0, "turns": 5, "ms": 100},
    ]
    raw = "".join(json.dumps(r) + "\n" for r in recs).encode()
    header, decisions, end, _marks = decode_frame(zstandard.ZstdCompressor().compress(raw))
    assert decisions[0]["opts"][1]["kind"] == "land"
    plans = parse_ret(decisions[0]["ret"])
    assert plans[0].host == 70 and plans[0].kind == "land"
