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
    defaults = dict(curation=curation, out=str(out), ckpt="ckpt/last.pt",
                    k=16, anchor="crash", turn_offset=0, tag="", limit=0)
    defaults.update(kw)
    a = argparse.Namespace(**defaults)
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
    m = _plan(_curation(tmp_path, rows), out, k=8, turn_offset=-5)
    lines = [ln for ln in open(m["arms"][0]["drillfile"])
             if not ln.startswith("#")]
    assert lines == ["0 1\n"]  # 2-5 clamps to 1, never 0 or negative


def test_plan_peak_anchor(tmp_path, src_arm):
    rows = [{"store": src_arm.name, "g": 3, "seed": 1,
             "crash_from_turn": 14, "peak_turn": 8}]
    out = tmp_path / "plan"
    m = _plan(_curation(tmp_path, rows), out, anchor="peak", turn_offset=-1)
    assert m["anchor"] == "peak" and m["turn_offset"] == -1
    lines = [ln for ln in open(m["arms"][0]["drillfile"])
             if not ln.startswith("#")]
    assert lines == ["3 7\n"]  # peak 8 - 1, crash turn ignored


def test_plan_rejects_non_alnum_tag(tmp_path, src_arm):
    rows = [{"store": src_arm.name, "g": 0, "seed": 1, "crash_from_turn": 5}]
    with pytest.raises(SystemExit):
        _plan(_curation(tmp_path, rows), tmp_path / "plan", tag="o-2")


def test_plan_unknown_store_fatal(tmp_path, src_arm):
    rows = [{"store": "no-such-arm", "g": 0, "seed": 1, "crash_from_turn": 5}]
    with pytest.raises(SystemExit):
        _plan(_curation(tmp_path, rows), tmp_path / "plan")


def _label(i, tt, w, draw=0, crash=0):
    return {"i": i, "seed": 1, "fp": 0, "t": tt, "tt": tt, "k": 8,
            "w": w, "draw": draw, "crash": crash, "copy_ms": 1, "ms": 1}


def test_report_aggregates_and_supersedes(tmp_path, src_arm):
    store = src_arm.name
    rows = [
        {"store": store, "g": 5, "seed": 1, "crash_from_turn": 9,
         "v_before": 0.8, "drop": 0.5, "peak_turn": 7, "model_seat": 1,
         "decks": ["dc-a", "dc-b"]},
        {"store": store, "g": 7, "seed": 2, "crash_from_turn": 13,
         "v_before": 0.7, "drop": 0.4, "peak_turn": 11, "model_seat": 1,
         "decks": ["dc-a", "dc-c"]},
        {"store": store, "g": 9, "seed": 3, "crash_from_turn": 4,
         "v_before": 0.6, "drop": 0.3, "peak_turn": 2, "model_seat": 1,
         "decks": ["dc-a", "dc-d"]},
    ]
    out = tmp_path / "plan"
    _plan(_curation(tmp_path, rows), out)

    runs = gs.RUNS_DIR
    # Run 1 (map sweep): g5 all-crash, g7 labeled; g9 replay-missed.
    r1 = runs / f"drill-{store}-20260729-080000" / "workers" / "inv-0000"
    r1.mkdir(parents=True)
    (r1 / "labels.jsonl").write_text(
        json.dumps(_label(5, 9, [0, 0], crash=8)) + "\n"
        + json.dumps(_label(7, 13, [2, 6])) + "\n")
    # Run 2 (post-fix re-drill): g5 now labels — must supersede run 1.
    r2 = runs / f"drill-{store}-20260729-090000" / "workers" / "inv-0000"
    r2.mkdir(parents=True)
    (r2 / "labels.jsonl").write_text(json.dumps(_label(5, 9, [3, 5])) + "\n")

    a = argparse.Namespace(manifest=str(out))
    gs.report(a)
    rep = json.loads((out / "report.json").read_text())

    assert rep["drills_labeled"] == 2
    assert rep["replay_missed"] == 1 and rep["missed"][0]["g"] == 9
    assert rep["all_completions_crashed"] == 0  # run 2 superseded g5
    # bridge_seats "1": model wins are w[1] -> g5: 5/8, g7: 6/8.
    assert rep["model_wins"] == 11 and rep["completions"] == 16
    drills = [json.loads(l) for l in (out / "drills.jsonl").open()]
    assert {d["g"]: d["model_wins"] for d in drills} == {5: 5, 7: 6}


def test_report_tag_isolates_sweep_arms(tmp_path, src_arm):
    """A tagged manifest must aggregate ONLY its own drill<tag>-* run dirs:
    untagged (and other-tag) runs of the same store would otherwise
    supersede this arm's labels per game."""
    store = src_arm.name
    rows = [{"store": store, "g": 5, "seed": 1, "crash_from_turn": 9,
             "v_before": 0.8, "drop": 0.5, "peak_turn": 7, "model_seat": 1,
             "decks": ["dc-a", "dc-b"]}]
    out = tmp_path / "plan"
    _plan(_curation(tmp_path, rows), out, tag="o2", turn_offset=-2)

    runs = gs.RUNS_DIR
    # Decoy: an untagged (map) run for the same store, LATER timestamp.
    decoy = runs / f"drill-{store}-20260729-090000" / "workers" / "inv-0000"
    decoy.mkdir(parents=True)
    (decoy / "labels.jsonl").write_text(json.dumps(_label(5, 9, [0, 0])) + "\n")
    ours = runs / f"drillo2-{store}-20260729-080000" / "workers" / "inv-0000"
    ours.mkdir(parents=True)
    (ours / "labels.jsonl").write_text(json.dumps(_label(5, 7, [2, 6])) + "\n")

    gs.report(argparse.Namespace(manifest=str(out)))
    rep = json.loads((out / "report.json").read_text())
    assert rep["drills_labeled"] == 1 and rep["model_wins"] == 6
    drill = json.loads((out / "drills.jsonl").read_text())
    assert drill["fired_t"] == 7  # the offset arm's fork turn, not the decoy's


def test_evalset_stratifies_and_holds_out(tmp_path, src_arm):
    store = src_arm.name
    # 6 mapped drills: 2 winnable (7/8), 2 lost (0/8), 2 coin (4/8).
    rows, drills = [], []
    for g, wins in [(1, 7), (2, 7), (3, 0), (4, 0), (5, 4), (6, 4)]:
        rows.append({"store": store, "g": g, "seed": g, "crash_from_turn": 10,
                     "v_before": 0.7, "drop": 0.4, "peak_turn": 8,
                     "model_seat": 1, "decks": ["dc-a", "dc-b"]})
        drills.append({"store": store, "g": g, "tt": 10, "fired_t": 10,
                       "k": 8, "model_wins": wins, "n": 8,
                       "engine_crashes": 0, "v_before": 0.7, "drop": 0.4,
                       "crash_from_turn": 10, "peak_turn": 8, "deck": "dc-b"})
    out = tmp_path / "plan"
    m = _plan(_curation(tmp_path, rows), out)
    (out / "drills.jsonl").write_text(
        "".join(json.dumps(d) + "\n" for d in drills))

    es = tmp_path / "es"
    a = argparse.Namespace(map=str(out), out=str(es), winnable=-1, coin=-1,
                           long_shot=-1, lost=1)
    gs.evalset(a)
    meta = json.loads((es / "meta.json").read_text())
    assert meta["bins"] == {"winnable": 2, "coin": 2, "lost": 1}
    assert meta["n"] == 5 and len(meta["held_out"]) == 5
    # deterministic pick: lost=1 takes the first of the sorted lost rows (g3)
    assert [store, 3] in meta["held_out"] and [store, 4] not in meta["held_out"]
    # the nested plan is complete and pins the map's replay ckpt
    pm = json.loads((es / "plan" / "manifest.json").read_text())
    assert pm["ckpt"] == m["ckpt"] and pm["arms"][0]["n_drills"] == 5
    baseline = [json.loads(l) for l in (es / "baseline.jsonl").open()]
    assert {b["g"] for b in baseline} == {1, 2, 3, 5, 6}
