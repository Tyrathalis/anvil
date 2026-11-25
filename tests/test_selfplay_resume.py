"""Game-level resume of an interrupted generation (M13, ADR-0136)."""
import json
import os

import pytest

from anvil.training import selfplay as sp


def _run_dir(root, name, games, start, seed_base=7, group=None, done=()):
    rd = root / name
    (rd / "workers").mkdir(parents=True)
    m = {"run_id": name, "purpose": name.rsplit("-", 2)[0], "games": games, "start_index": start, "seed_base": seed_base}
    if group:
        m["queue"] = {"group": group, "slots": 4, "max_active": None, "position": 0}
    (rd / "run.json").write_text(json.dumps(m))
    for inv, ids in done:
        d = rd / "workers" / inv
        d.mkdir()
        (d / "games.jsonl").write_text("".join(json.dumps({"i": i, "status": "won"}) + "\n" for i in ids))
    return rd


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    runs, traj = tmp_path / "runs", tmp_path / "traj"
    (runs / "queues").mkdir(parents=True)
    traj.mkdir()
    monkeypatch.setattr(sp, "RUNS_DIR", runs)
    monkeypatch.setattr(sp, "TRAJ_DIR", traj)
    return runs, traj


def _queue(runs, group, names):
    (runs / "queues" / f"{group}.queue.json").write_text(json.dumps({"group": group, "slots": 4, "runs": names}))


def test_resumable_runs_takes_an_interrupted_queue(dirs):
    runs, traj = dirs
    a = _run_dir(runs, "x-i003-20260101-000000", 4, 100, group="g1", done=[("inv-0000", [100])])
    b = _run_dir(runs, "x-i003h0-20260101-000000", 2, 104, group="g1")
    _queue(runs, "g1", [a.name, b.name])
    todo = [("x-i003", 4, 100, 7), ("x-i003h0", 2, 104, 7)]
    assert sp.resumable_runs(todo) == [a, b]
    # a batch already stored is not in todo; its dir may still be a queue member
    (traj / b.name).mkdir()
    (traj / b.name / "manifest.json").write_text("{}")
    assert sp.resumable_runs(todo[:1]) == [a]


def test_resumable_runs_refuses_what_a_fresh_launch_would_not_play(dirs):
    runs, _ = dirs
    a = _run_dir(runs, "x-i003-20260101-000000", 4, 100, group="g1")
    b = _run_dir(runs, "x-i003h0-20260101-000000", 2, 104, group="g2")
    _queue(runs, "g1", [a.name])
    _queue(runs, "g2", [b.name])
    assert sp.resumable_runs([("x-i003", 4, 100, 7), ("x-i003h0", 2, 104, 7)]) is None  # two queues
    assert sp.resumable_runs([("x-i003", 4, 100, 8)]) is None  # another seed base
    assert sp.resumable_runs([("x-i003", 4, 96, 7)]) is None  # another start index
    assert sp.resumable_runs([("x-i004", 4, 100, 7)]) is None  # no dir
    (runs / "queues" / "g1.queue.json").unlink()
    assert sp.resumable_runs([("x-i003", 4, 100, 7)]) is None  # the queue's record is gone
    solo = _run_dir(runs, "y-i000-20260101-000000", 4, 0)
    assert sp.resumable_runs([("y-i000", 4, 0, 7)]) == [solo]  # one run with no queue stands alone


def test_purge_drops_only_unfinished_games_rows(dirs, tmp_path):
    runs, _ = dirs
    a = _run_dir(runs, "x-i003-20260101-000000", 4, 100, done=[("inv-0000", [100]), ("inv-0001", [])])
    lab0 = a / "workers" / "inv-0000" / "labels.jsonl"
    lab1 = a / "workers" / "inv-0001" / "labels.jsonl"
    lab0.write_text(json.dumps({"ev": "search", "i": 100, "sw": 0}) + "\n" + json.dumps({"ev": "search", "i": 101, "sw": 0}) + "\n")
    lab1.write_text(json.dumps({"ev": "search", "i": 102, "sw": 0}) + "\n" + '{"ev":"search","i":10')  # cut off by the stop
    mu = tmp_path / "mu.jsonl"
    mu.write_text("".join(json.dumps(r) + "\n" for r in [
        {"k": "meta", "ckpt": "c"}, {"g": 100, "s": 1}, {"g": 101, "s": 1}, {"g": 100, "s": 2}, {"g": 102, "s": 1}]))
    assert sp.purge_partial_attempts([a], mu) == {"mu": 2, "labels": 3}
    assert [json.loads(x) for x in mu.read_text().splitlines()] == [{"k": "meta", "ckpt": "c"}, {"g": 100, "s": 1}, {"g": 100, "s": 2}]
    assert [json.loads(x)["i"] for x in lab0.read_text().splitlines()] == [100]
    assert lab1.read_text() == ""
    assert sp.purge_partial_attempts([a], mu) == {"mu": 0, "labels": 0}  # a second pass changes nothing


def test_batches_short_counts_finished_and_skipped(dirs):
    runs, _ = dirs
    a = _run_dir(runs, "x-i003-20260101-000000", 3, 100, done=[("inv-0000", [100]), ("inv-0001", [101])])
    assert sp.batches_short([a]) == [(a.name, 2, 3)]
    (a / "skips.json").write_text(json.dumps({"indices": [102]}))
    assert sp.batches_short([a]) == []


def test_lost_segment_is_start_to_last_finished_game(dirs, tmp_path):
    runs, _ = dirs
    a = _run_dir(runs, "x-i003-20260101-000000", 3, 100, done=[("inv-0000", [100])])
    op = tmp_path / "gen-open.json"
    assert sp.lost_segment_s(op, [a]) == 0.0
    op.write_text(json.dumps({"t0": 1000.0}))
    os.utime(a / "workers" / "inv-0000" / "games.jsonl", (1600.0, 1600.0))
    assert sp.lost_segment_s(op, [a]) == 600.0
    os.utime(a / "workers" / "inv-0000" / "games.jsonl", (900.0, 900.0))
    assert sp.lost_segment_s(op, [a]) == 0.0  # no game finished in the segment


def test_resumable_runs_for_reads_ignores_stores(dirs):
    runs, traj = dirs
    a = _run_dir(runs, "x-arm-i004-s0-20260101-000000", 2, 0, group="g9", done=[("inv-0000", [0, 1])])
    b = _run_dir(runs, "x-arm-i004-s1-20260101-000000", 2, 0, group="g9", done=[("inv-0000", [0])])
    _queue(runs, "g9", [a.name, b.name])
    todo = [("x-arm-i004-s0", 2, 0, 7), ("x-arm-i004-s1", 2, 0, 7)]
    assert sp.resumable_runs(todo, stores=False) == [a, b]  # a finished member is still the batch's dir
    assert sp.batches_short([a, b]) == [(b.name, 1, 2)]
    assert sp.resumable_runs([("x-arm-i005-s0", 2, 0, 7)], stores=False) is None  # an uninterrupted read finds none
