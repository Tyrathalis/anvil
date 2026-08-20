"""M9 D3 rung 2: the payment-surface census read (scripts/payment_read.py)
and the obs-reader round-trip for the new bridged payment window."""

import json
import sys
from pathlib import Path

import zstandard

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from payment_read import read, report  # noqa: E402

from anvil.store import OBS_SCHEMA_VERSION, decode_frame  # noqa: E402


def _census_lines():
    """Two games of synthetic census: telemetry-mode records + one bridged
    window with a directed execution, plus the legacy shapes (effect=true,
    no-telemetry) that must be skipped, not miscounted."""
    lines = [
        {"ev": "start", "g": 0, "seed": 1},
        # telemetry-only mode records (heuristic play)
        {"g": 0, "m": "payManaCost", "effect": False, "classes": 1, "conseq": False,
         "forced": False, "trunc": False, "atoms": 3},
        {"g": 0, "m": "payManaCost", "effect": False, "classes": 2, "conseq": True,
         "forced": False, "trunc": False, "atoms": 4},
        {"g": 0, "m": "payManaCost", "effect": False, "classes": 1, "conseq": True,
         "forced": True, "trunc": False, "atoms": 3},  # the §4 forced window
        {"g": 0, "m": "payManaCost", "effect": True},   # out of scope: resolution payment
        {"g": 0, "m": "payManaCost", "effect": False},  # zero-mana / mode off: no kv
        {"g": 0, "m": "chooseColor", "effect": False},  # different method entirely
        {"ev": "start", "g": 1, "seed": 2},
        # a bridged window: class answer, directed ok
        {"g": 1, "m": "payManaCost", "by": "bridge", "options": 3, "pick": 2,
         "exec": "directed_ok", "paid": True, "float_residue": 0,
         "classes": 2, "conseq": True, "trunc": True, "forced": False},
        # a bridged window answered auto
        {"g": 1, "m": "payManaCost", "by": "bridge", "options": 2, "pick": "auto",
         "paid": True, "classes": 2, "conseq": True, "trunc": False, "forced": False},
    ]
    return [json.dumps(x) for x in lines]


def test_read_aggregates(tmp_path):
    p = tmp_path / "census.jsonl"
    p.write_text("\n".join(_census_lines()) + "\n")
    s = read([str(p)])

    assert s["games"] == 2
    assert s["pay_records"] == 7
    assert s["effect_true"] == 1
    assert s["no_telemetry"] == 1
    assert s["scoped_windows"] == 5
    assert s["consequential"] == 4
    assert s["forced"] == 1  # only the forced consequential window
    assert s["truncated"] == 1
    assert s["truncation_rate"] == 0.25  # 1 of 4 consequential
    assert s["class_hist"] == {1: 2, 2: 3}
    assert s["picks"] == {"class": 1, "auto": 1}
    assert s["execs"] == {"directed_ok": 1}
    assert s["float_residue_windows"] == 0
    # the truncation gate fires in the report (0.25 > 0.05), loudly
    assert "TRUNCATION GATE EXCEEDED" in report(s)


def test_read_goal_era(tmp_path):
    """§12 goal-era records: goals/plans kvs, the costmod scope boundary +
    its retrospective leak backstop, nodecap gate — and the old class-era
    truncation banner never fires on goal records."""
    lines = [
        json.dumps({"ev": "start", "g": 0, "seed": 1}),
        # telemetry-mode goal records
        json.dumps({"g": 0, "m": "payManaCost", "effect": False, "goals": 1, "plans": 1,
                    "conseq": False, "forced": False, "trunc": False, "nodecap": False,
                    "atoms": 3, "srcclasses": 1, "nodes": 12}),
        json.dumps({"g": 0, "m": "payManaCost", "effect": False, "goals": 3, "plans": 40,
                    "conseq": True, "forced": False, "trunc": False, "nodecap": False,
                    "atoms": 9, "srcclasses": 5, "nodes": 900}),
        # §12b: statically detected cost-modified window — out of scope, never enumerated
        json.dumps({"g": 0, "m": "payManaCost", "effect": False, "costmod": True}),
        # §12b retrospective backstop: 0 plans yet auto paid (static-detector leak)
        json.dumps({"g": 0, "m": "payManaCost", "by": "auto", "effect": False, "goals": 0,
                    "plans": 0, "conseq": False, "trunc": False, "nodecap": False,
                    "costmod_late": True}),
        # nodecap window: degraded surface, logged
        json.dumps({"g": 0, "m": "payManaCost", "effect": False, "goals": 2, "plans": 130,
                    "conseq": True, "forced": True, "trunc": False, "nodecap": True,
                    "atoms": 14, "srcclasses": 8, "nodes": 200001}),
    ]
    p = tmp_path / "goal.jsonl"
    p.write_text("\n".join(lines) + "\n")
    s = read([str(p)])

    assert s["goal_era_records"] == 4
    assert s["scoped_windows"] == 4
    assert s["costmod"] == 1
    assert s["costmod_rate"] == 0.2  # 1 of 5 in-scope-shape windows
    assert s["costmod_late"] == 1
    assert s["nodecap"] == 1
    assert s["nodecap_rate"] == 0.25
    assert s["consequential"] == 2
    assert s["forced"] == 1
    assert s["class_hist"] == {0: 1, 1: 1, 2: 1, 3: 1}  # goals-per-window
    assert s["plans_hist"] == {0: 1, 1: 1, 40: 1, 65: 1}  # 130 clamps to the >64 bin
    r = report(s)
    assert "NODECAP GATE EXCEEDED" in r  # 0.25 > 0.01, loudly
    assert "GOAL TRUNCATION" not in r    # no goal-cap truncation in the fixture
    assert "K_MAX" not in r              # the retired banner never fires goal-era


def test_read_handles_legacy_census(tmp_path):
    """Files from runs without -paytelemetry (all pre-M9 census) parse fine
    and report zero telemetry coverage."""
    p = tmp_path / "old.jsonl"
    lines = [
        json.dumps({"ev": "start", "g": 0, "seed": 1}),
        json.dumps({"g": 0, "m": "payManaCost", "sa": "{T}: Add {R}.", "effect": False}),
        json.dumps({"g": 0, "m": "payManaCost", "sa": "Stomp...", "effect": True}),
    ]
    p.write_text("\n".join(lines) + "\n")
    s = read([str(p)])
    assert s["scoped_windows"] == 0
    assert s["no_telemetry"] == 1
    assert s["consequential_rate"] == 0.0


def test_payment_window_roundtrips_obs_reader():
    """The new bridged payment dec (opts + kv + ret) decodes through the
    standing frame codec with the option labels and exec verdict joined —
    no schema bump needed for additive kv (the sv bump rides the bundle).
    Record shape mirrors Obs.decInternal: kv nests under "args", decBridged
    opts are plain quoted labels (the class descriptors are JSON *text*
    inside those strings)."""
    records = [
        {"k": "game", "sv": OBS_SCHEMA_VERSION, "g": 7, "seed": 99, "players": ["a", "b"]},
        {"k": "dec", "s": 0, "g": 7, "t": 3, "ph": "MAIN1", "p": 0,
         "m": "payManaCost", "d": 20, "by": "bridge",
         "args": {"sa": "Thief of Sanity", "cost": "1 U B",
                  "fpool": "0,0,0,0,0,0", "classes": 1, "trunc": False,
                  "forced": True},
         "opts": ['{"auto":true}', '{"ents":[12,14,15],"pool":[0,0,0,0,0,0],"phy":0}'],
         "obs": None},
        {"k": "ret", "s": 0, "v": "directed_ok"},
        {"k": "end", "g": 7, "winner": "a"},
    ]
    raw = "\n".join(json.dumps(r) for r in records).encode()
    frame = zstandard.ZstdCompressor().compress(raw)
    header, decisions, end, _marks = decode_frame(frame)

    assert header["g"] == 7
    assert len(decisions) == 1
    d = decisions[0]
    assert d["m"] == "payManaCost"
    assert d["by"] == "bridge"
    assert d["args"]["forced"] is True
    assert d["args"]["fpool"] == "0,0,0,0,0,0"
    assert len(d["opts"]) == 2
    assert json.loads(d["opts"][1])["ents"] == [12, 14, 15]
    assert d["ret"] == "directed_ok"
    assert end["winner"] == "a"
