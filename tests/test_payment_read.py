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
