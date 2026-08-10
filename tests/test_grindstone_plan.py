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
    defaults = {
        "curation": curation,
        "out": str(out),
        "ckpt": "ckpt/last.pt",
        "k": 16,
        "anchor": "crash",
        "turn_offset": 0,
        "tag": "",
        "limit": 0,
    }
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
    for k in (
        "seed_base",
        "games_per_pair",
        "bridge_seats",
        "reask",
        "fork_commit",
        "jar_sha256",
        "pool_version",
    ):
        assert arm[k] == SRC_CFG[k], k

    with open(arm["drillfile"]) as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    # Same-game windows merge, sorted; games sorted.
    assert lines == ["5 4,9\n", "7 13\n"]


def test_plan_turn_offset_clamps(tmp_path, src_arm):
    rows = [{"store": src_arm.name, "g": 0, "seed": 1, "crash_from_turn": 2}]
    out = tmp_path / "plan"
    m = _plan(_curation(tmp_path, rows), out, k=8, turn_offset=-5)
    with open(m["arms"][0]["drillfile"]) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    assert lines == ["0 1\n"]  # 2-5 clamps to 1, never 0 or negative


def test_plan_peak_anchor(tmp_path, src_arm):
    rows = [{"store": src_arm.name, "g": 3, "seed": 1, "crash_from_turn": 14, "peak_turn": 8}]
    out = tmp_path / "plan"
    m = _plan(_curation(tmp_path, rows), out, anchor="peak", turn_offset=-1)
    assert m["anchor"] == "peak" and m["turn_offset"] == -1
    with open(m["arms"][0]["drillfile"]) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
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
    return {
        "i": i,
        "seed": 1,
        "fp": 0,
        "t": tt,
        "tt": tt,
        "k": 8,
        "w": w,
        "draw": draw,
        "crash": crash,
        "copy_ms": 1,
        "ms": 1,
    }


def test_report_aggregates_and_supersedes(tmp_path, src_arm):
    store = src_arm.name
    rows = [
        {
            "store": store,
            "g": 5,
            "seed": 1,
            "crash_from_turn": 9,
            "v_before": 0.8,
            "drop": 0.5,
            "peak_turn": 7,
            "model_seat": 1,
            "decks": ["dc-a", "dc-b"],
        },
        {
            "store": store,
            "g": 7,
            "seed": 2,
            "crash_from_turn": 13,
            "v_before": 0.7,
            "drop": 0.4,
            "peak_turn": 11,
            "model_seat": 1,
            "decks": ["dc-a", "dc-c"],
        },
        {
            "store": store,
            "g": 9,
            "seed": 3,
            "crash_from_turn": 4,
            "v_before": 0.6,
            "drop": 0.3,
            "peak_turn": 2,
            "model_seat": 1,
            "decks": ["dc-a", "dc-d"],
        },
    ]
    out = tmp_path / "plan"
    _plan(_curation(tmp_path, rows), out)

    runs = gs.RUNS_DIR
    # Run 1 (map sweep): g5 all-crash, g7 labeled; g9 replay-missed.
    r1 = runs / f"drill-{store}-20260729-080000" / "workers" / "inv-0000"
    r1.mkdir(parents=True)
    (r1 / "labels.jsonl").write_text(
        json.dumps(_label(5, 9, [0, 0], crash=8)) + "\n" + json.dumps(_label(7, 13, [2, 6])) + "\n"
    )
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
    rows = [
        {
            "store": store,
            "g": 5,
            "seed": 1,
            "crash_from_turn": 9,
            "v_before": 0.8,
            "drop": 0.5,
            "peak_turn": 7,
            "model_seat": 1,
            "decks": ["dc-a", "dc-b"],
        }
    ]
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


def _label_src(tmp_path, name, rows):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "drills.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return d


def _drill_row(store, g, t, wins, n=8):
    return {"store": store, "g": g, "fired_t": t, "model_wins": wins, "n": n}


def _select(tmp_path, curation, labels, out="sel", holdout=None, band="0.25:0.75"):
    o = tmp_path / out
    gs.select(
        argparse.Namespace(
            curation=curation,
            labels=",".join(str(x) for x in labels),
            holdout=holdout,
            band=band,
            out=str(o),
        )
    )
    rows = [json.loads(l) for l in (o / "selection.jsonl").open()]
    meta = json.loads((o / "meta.json").read_text())
    return rows, meta


def test_select_rule_band_above_excluded(tmp_path, src_arm):
    store = src_arm.name
    cur_rows = [
        {"store": store, "g": g, "seed": g, "crash_from_turn": 14, "peak_turn": 8}
        for g in (1, 2, 3)
    ]
    cur = _curation(tmp_path, cur_rows)
    # g1: in-band at t12 (4/8) and t10 (5/8) -> latest in-band wins (12).
    # g2: never in-band, above at t8 (7/8) -> latest above wins.
    # g3: nothing clears the floor anywhere -> excluded.
    src = _label_src(
        tmp_path,
        "arms",
        [
            _drill_row(store, 1, 14, 1),
            _drill_row(store, 1, 12, 4),
            _drill_row(store, 1, 10, 5),
            _drill_row(store, 2, 14, 0),
            _drill_row(store, 2, 12, 1),
            _drill_row(store, 2, 8, 7),
            _drill_row(store, 3, 14, 0),
            _drill_row(store, 3, 8, 1),
        ],
    )
    rows, meta = _select(tmp_path, cur, [src])
    by_g = {r["g"]: r for r in rows}
    assert by_g[1]["drill_turn"] == 12 and by_g[1]["sel_rule"] == "band"
    assert by_g[1]["sel_wr"] == 0.5
    assert by_g[2]["drill_turn"] == 8 and by_g[2]["sel_rule"] == "above"
    assert 3 not in by_g and meta["stats"]["excluded"] == 1
    assert meta["offset_vs_crash"] == {"-6": 1, "-2": 1}


def test_select_later_source_supersedes_and_holdout(tmp_path, src_arm):
    store = src_arm.name
    cur = _curation(
        tmp_path,
        [
            {"store": store, "g": 1, "seed": 1, "crash_from_turn": 10, "peak_turn": 6},
            {"store": store, "g": 2, "seed": 2, "crash_from_turn": 10, "peak_turn": 6},
        ],
    )
    # Map says t10 is in-band (selection-time label); the re-measure says
    # t10 is lost — listed later, it must supersede, pushing g1 to t8.
    map_src = _label_src(
        tmp_path, "map", [_drill_row(store, 1, 10, 4), _drill_row(store, 2, 10, 4)]
    )
    remeasure = _label_src(
        tmp_path, "o0", [_drill_row(store, 1, 10, 0), _drill_row(store, 1, 8, 3)]
    )
    es = tmp_path / "es"
    es.mkdir()
    (es / "meta.json").write_text(json.dumps({"held_out": [[store, 2]]}))
    rows, meta = _select(tmp_path, cur, [map_src, remeasure], holdout=str(es))
    assert len(rows) == 1
    assert rows[0]["g"] == 1 and rows[0]["drill_turn"] == 8
    assert meta["stats"] == {"band": 1, "held_out": 1}


def test_plan_consumes_selection(tmp_path, src_arm):
    store = src_arm.name
    cur = _curation(
        tmp_path, [{"store": store, "g": 5, "seed": 1, "crash_from_turn": 14, "peak_turn": 8}]
    )
    src = _label_src(tmp_path, "arms", [_drill_row(store, 5, 11, 4)])
    _rows, _ = _select(tmp_path, cur, [src])
    sel = tmp_path / "sel" / "selection.jsonl"
    assert [json.loads(l)["drill_turn"] for l in sel.open()] == [11]
    m = _plan(sel, tmp_path / "plan", anchor="selected")
    with open(m["arms"][0]["drillfile"]) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    assert lines == ["5 11\n"]  # the selected turn, not crash or peak


def test_evalset_stratifies_and_holds_out(tmp_path, src_arm):
    store = src_arm.name
    # 6 mapped drills: 2 winnable (7/8), 2 lost (0/8), 2 coin (4/8).
    rows, drills = [], []
    for g, wins in [(1, 7), (2, 7), (3, 0), (4, 0), (5, 4), (6, 4)]:
        rows.append(
            {
                "store": store,
                "g": g,
                "seed": g,
                "crash_from_turn": 10,
                "v_before": 0.7,
                "drop": 0.4,
                "peak_turn": 8,
                "model_seat": 1,
                "decks": ["dc-a", "dc-b"],
            }
        )
        drills.append(
            {
                "store": store,
                "g": g,
                "tt": 10,
                "fired_t": 10,
                "k": 8,
                "model_wins": wins,
                "n": 8,
                "engine_crashes": 0,
                "v_before": 0.7,
                "drop": 0.4,
                "crash_from_turn": 10,
                "peak_turn": 8,
                "deck": "dc-b",
            }
        )
    out = tmp_path / "plan"
    m = _plan(_curation(tmp_path, rows), out)
    (out / "drills.jsonl").write_text("".join(json.dumps(d) + "\n" for d in drills))

    es = tmp_path / "es"
    a = argparse.Namespace(map=str(out), out=str(es), winnable=-1, coin=-1, long_shot=-1, lost=1)
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
