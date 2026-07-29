"""Grindstone `plan` (M4 D2): curation rows -> drill manifest.

Pinned-fixture test: a fake source arm (run.json + pairs.txt) plus three
curation rows — two crash windows in one game (must merge into one
drillfile line), one in another. The manifest must carry the source arm's
replay recipe verbatim (seed base, bridge seats, re-ask, jar/fork pins).
"""

import argparse
import json

import pytest

from anvil.grindstone import __main__ as gs


SRC_CFG = {
    "pairs_file": "pairs.txt",
    "pairs_sha256": "ab" * 32,
    "seed_base": 20260710,
    "games_per_pair": 5,
    "bridge_seats": "1",
    "reask": True,
    "fork_commit": "5fbc2ac98d",
    "jar_sha256": "cd" * 32,
    "pool_version": "cf2ca6ba",
}


@pytest.fixture
def src_arm(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    arm = runs / "srcarm-s1-20260729-000000"
    arm.mkdir(parents=True)
    (arm / "run.json").write_text(json.dumps(SRC_CFG))
    (arm / "pairs.txt").write_text("dc-1 dc-2\n")
    monkeypatch.setattr(gs, "RUNS_DIR", runs)
    return arm


def _curation(tmp_path, rows):
    p = tmp_path / "curation.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def _plan(curation, out, **kw):
    a = argparse.Namespace(curation=curation, out=str(out),
                           ckpt="ckpt/last.pt", k=16, turn_offset=0,
                           limit=0, **kw)
    gs.plan(a)
    return json.loads((out / "manifest.json").read_text())


def test_plan_merges_and_pins(tmp_path, src_arm):
    store = src_arm.name
    rows = [
        {"store": store, "g": 5, "seed": 1, "crash_from_turn": 9},
        {"store": store, "g": 7, "seed": 2, "crash_from_turn": 13},
        {"store": store, "g": 5, "seed": 1, "crash_from_turn": 4},
    ]
    out = tmp_path / "plan"
    m = _plan(_curation(tmp_path, rows), out)

    assert len(m["arms"]) == 1
    arm = m["arms"][0]
    assert arm["n_drills"] == 3 and arm["n_games"] == 2
    assert arm["index_min"] == 5 and arm["index_span"] == 3
    # Replay recipe carried verbatim from the source run.json:
    for k in ("seed_base", "games_per_pair", "bridge_seats", "reask",
              "fork_commit", "jar_sha256", "pool_version"):
        assert arm[k] == SRC_CFG[k], k

    lines = [ln for ln in open(arm["drillfile"])
             if ln.strip() and not ln.startswith("#")]
    # Same-game windows merge, sorted; games sorted.
    assert lines == ["5 4,9\n", "7 13\n"]


def test_plan_turn_offset_clamps(tmp_path, src_arm):
    rows = [{"store": src_arm.name, "g": 0, "seed": 1, "crash_from_turn": 2}]
    out = tmp_path / "plan"
    a = argparse.Namespace(curation=_curation(tmp_path, rows), out=str(out),
                           ckpt="c", k=8, turn_offset=-5, limit=0)
    gs.plan(a)
    m = json.loads((out / "manifest.json").read_text())
    lines = [ln for ln in open(m["arms"][0]["drillfile"])
             if not ln.startswith("#")]
    assert lines == ["0 1\n"]  # 2-5 clamps to 1, never 0 or negative


def test_plan_unknown_store_fatal(tmp_path, src_arm):
    rows = [{"store": "no-such-arm", "g": 0, "seed": 1, "crash_from_turn": 5}]
    with pytest.raises(SystemExit):
        _plan(_curation(tmp_path, rows), tmp_path / "plan")
