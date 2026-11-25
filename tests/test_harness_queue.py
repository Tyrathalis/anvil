"""The harness's shared queue (M13 Build 2): several runs through one set
of worker slots, each keeping its own dir; the loop's batch plan with the
Monte Carlo share; the port check."""

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from anvil.bridge.harness import orchestrator as orc

WORKER = """
import json, sys, time
out, start, count, sleep = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
for i in range(start, start + count):
    time.sleep(sleep)
    with open(out, "a") as f:
        f.write(json.dumps({"i": i, "status": "won", "ms": 1, "turns": 1}) + "\\n")
"""


def _mk_run(root: Path, name: str, games: int, chunk: int, start: int = 0) -> orc.Run:
    d = root / name
    (d / "workers").mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({
        "run_id": name, "purpose": name, "games": games, "chunk": chunk, "start_index": start,
        "workers": 4, "heap": "2g", "bridge": "local-random", "seed_base": 1,
    }))
    return orc.Run(d)


@pytest.fixture
def fake_workers(monkeypatch):
    """Workers that write their span's game rows and exit; records the
    high-water mark of live workers per run and overall."""
    seen = {"live": [], "by_run": {}, "peak": 0, "peak_by_run": {}, "order": []}

    def launch_worker(self, span, inv):
        wdir = self.workers_dir / f"inv-{inv:04d}"
        wdir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([sys.executable, "-c", WORKER, str(wdir / "games.jsonl"),
                                 str(span[0]), str(span[1]), "0.05"])
        seen["order"].append(self.manifest["purpose"])
        seen["live"] = [(p, n) for p, n in seen["live"] if p.poll() is None] + [(proc, self.manifest["purpose"])]
        seen["peak"] = max(seen["peak"], len(seen["live"]))
        for name in {n for _, n in seen["live"]}:
            k = sum(1 for _, n in seen["live"] if n == name)
            seen["peak_by_run"][name] = max(seen["peak_by_run"].get(name, 0), k)
        return proc

    monkeypatch.setattr(orc.Run, "launch_worker", launch_worker)
    monkeypatch.setattr(orc, "POLL_S", 0.02)
    return seen


def test_next_run_takes_the_first_run_with_room():
    assert orc.next_run([3, 5], [0, 0], [None, None]) == 0
    assert orc.next_run([0, 5], [0, 0], [None, None]) == 1
    assert orc.next_run([3, 5], [2, 0], [2, None]) == 1  # run 0 at its cap
    assert orc.next_run([3, 0], [2, 0], [2, None]) is None  # only capped work left
    assert orc.next_run([0, 0], [0, 0], [None, None]) is None


def test_group_plays_every_game_of_every_run_in_its_own_dir(tmp_path, fake_workers):
    a = _mk_run(tmp_path, "a", games=6, chunk=1)
    b = _mk_run(tmp_path, "b", games=10, chunk=2, start=100)
    orc.schedule_group([a, b], slots=4, caps=[1, None])
    assert sorted(a.completed()) == list(range(6))
    assert sorted(b.completed()) == list(range(100, 110))
    assert (a.dir / "summary.json").exists() and (b.dir / "games.jsonl").exists()
    assert fake_workers["peak"] <= 4
    assert fake_workers["peak_by_run"]["a"] == 1  # the cap held
    # the capped run did not wait for the other to finish: its work is interleaved
    assert fake_workers["order"].index("b") < len(fake_workers["order"]) - 1
    assert "a" in fake_workers["order"][:2]
    last_a = max(i for i, n in enumerate(fake_workers["order"]) if n == "a")
    first_b = fake_workers["order"].index("b")
    assert first_b < last_a


def test_one_run_alone_is_the_old_scheduler(tmp_path, fake_workers):
    a = _mk_run(tmp_path, "solo", games=9, chunk=2)
    a.schedule()
    assert sorted(a.completed()) == list(range(9))
    assert fake_workers["peak"] <= 4


def test_group_resumes_minus_completed_games(tmp_path, fake_workers):
    a = _mk_run(tmp_path, "a", games=4, chunk=2)
    b = _mk_run(tmp_path, "b", games=4, chunk=2)
    w = a.workers_dir / "inv-0000"
    w.mkdir()
    (w / "games.jsonl").write_text("".join(json.dumps({"i": i, "status": "won", "ms": 1, "turns": 1}) + "\n" for i in (0, 1, 2)))
    orc.schedule_group([a, b], slots=2)
    assert fake_workers["order"].count("a") == 1  # only game 3 was left
    assert sorted(a.completed()) == [0, 1, 2, 3] and sorted(b.completed()) == [0, 1, 2, 3]


def test_stop_in_any_member_pauses_the_group(tmp_path, fake_workers):
    a = _mk_run(tmp_path, "a", games=4, chunk=1)
    b = _mk_run(tmp_path, "b", games=4, chunk=1)
    b.stop_file.touch()
    orc.schedule_group([a, b], slots=2)
    assert not a.completed() and not b.completed()


def test_iteration_batches_takes_the_monte_carlo_share_from_the_heuristic_games():
    from anvil.training.selfplay import is_mc_batch, iteration_batches, queue_order

    b = iteration_batches("arm", 7, 480, 0.5, 0.1)
    assert b == [
        ("arm-i007", 240, 0, None),
        ("arm-i007h0", 96, 240, 0),
        ("arm-i007h1", 96, 336, 1),
        ("arm-i007m0", 24, 432, 0),
        ("arm-i007m1", 24, 456, 1),
    ]
    assert [is_mc_batch(p) for p, *_ in b] == [False, False, False, True, True]
    assert not is_mc_batch("farm0") and not is_mc_batch("x-i007h0")
    # no Monte Carlo share: the pre-Build-2 plan, unchanged
    assert iteration_batches("r6", 3, 480, 0.5) == iteration_batches("r6", 3, 480, 0.5, 0.0)
    assert [p for p, *_ in iteration_batches("r6", 3, 480, 0.5)] == ["r6-i003", "r6-i003h0", "r6-i003h1"]
    # the indices are disjoint and cover the iteration
    spans = sorted((off, off + n) for _, n, off, _ in b)
    assert spans[0][0] == 0 and spans[-1][1] == 480
    assert all(spans[i][1] == spans[i + 1][0] for i in range(len(spans) - 1))
    # Monte Carlo first and capped, the rest in plan order
    assert queue_order(b, 3) == [(3, 3), (4, 3), (0, None), (1, None), (2, None)]
    with pytest.raises(ValueError):
        iteration_batches("arm", 0, 480, 0.05, 0.1)


def test_mc_props_is_the_calibrated_eight_round_budget():
    from anvil.training.selfplay import MC_PROPS

    sh = Path(__file__).parents[1] / "scripts/m13_mc.sh"
    src = sh.read_text()
    fn = src[src.index("DESKTOP="):src.index("# One JVM")]
    got = subprocess.run(["bash", "-c", fn + "\ncount_props 8"], capture_output=True, text=True, check=True).stdout.strip()
    assert got == MC_PROPS


def test_games_cmd_gives_a_monte_carlo_batch_its_heap_and_flags():
    from types import SimpleNamespace

    from anvil.training.selfplay import games_cmd

    a = SimpleNamespace(games_per_pair=2, workers=24, chunk=30, port=50063, seed_base=5, servers=0, reask=True, jar=None)
    plain = games_cmd("r-i000h0", 96, 240, a, bridge_seats=0, forge_args=["-search"], labels=True)
    assert "--heap" not in plain and "--forge-args=-search" in plain and "--labels" in plain
    mc = games_cmd("r-i000m0", 24, 432, a, bridge_seats=0, forge_args=["-mc", "on"], heap="3g", labels=False)
    assert mc[mc.index("--heap") + 1] == "3g" and "--labels" not in mc and "--forge-args=-mc on" in mc
    assert mc[mc.index("--chunk") + 1] == "1"  # 24 games on 24 workers: a game per worker slice


def test_check_ports_free_refuses_a_live_port():
    from anvil.bridge.fleet import check_ports_free

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        with pytest.raises(RuntimeError, match=str(port)):
            check_ports_free(port)
        with pytest.raises(RuntimeError, match=str(port)):
            check_ports_free(port - 1, 2)
    check_ports_free(port)  # closed again


def test_mem_hold_enters_under_the_floor_and_leaves_a_margin_above():
    assert not orc.mem_hold(5000, 4096, False)
    assert orc.mem_hold(4000, 4096, False)
    assert orc.mem_hold(4500, 4096, True)  # still holding inside the margin
    assert not orc.mem_hold(5200, 4096, True)
    assert not orc.mem_hold(None, 4096, False) and not orc.mem_hold(10, 0, False)


def test_group_holds_new_workers_while_memory_is_low(tmp_path, fake_workers, monkeypatch):
    a = _mk_run(tmp_path, "a", games=4, chunk=1)
    levels = iter([1000.0] * 5)
    monkeypatch.setattr(orc, "mem_available_mb", lambda: next(levels, 60000.0))
    monkeypatch.setattr(orc, "heartbeat", lambda *_: None)
    orc.schedule_group([a], slots=2)
    assert sorted(a.completed()) == [0, 1, 2, 3]
    ledger = json.loads(a.yield_state_file.read_text())
    assert ledger["yielding"] is False and ledger["yielded_s"] > 0  # the hold is on the yield ledger


# ---- the yield guard (11-25): a clock draw during a GPU yield is voided

def test_overlaps_yield_reads_the_games_own_span():
    w = [(1000.0, 1600.0)]
    assert orc.overlaps_yield(1_200_000, 2000.0, w)            # ran 800..2000: inside the window
    assert not orc.overlaps_yield(60_000, 2000.0, w)           # ran 1940..2000: after it, past the slack
    assert orc.overlaps_yield(60_000, 1650.0, w)               # within the slack of the window's end
    assert not orc.overlaps_yield(1_200_000, 900.0, w)         # finished before the window opened
    assert orc.overlaps_yield(1_200_000, 5000.0, [(4000.0, float("inf"))])  # a window still open
    assert not orc.overlaps_yield(1_200_000, 5000.0, [])


def test_group_voids_a_clock_draw_under_a_gpu_yield_and_leaves_the_rest(tmp_path, monkeypatch):
    a = _mk_run(tmp_path, "a", games=4, chunk=4)
    m = json.loads((a.dir / "run.json").read_text())
    (a.dir / "run.json").write_text(json.dumps(dict(m, yield_gpu=True)))
    a = orc.Run(a.dir)
    worker = WORKER.replace('"status": "won", "ms": 1', '"status": "draw" if i % 2 else "won", "draw_clock": bool(i % 2), "ms": 1')

    def launch_worker(self, span, inv):
        wdir = self.workers_dir / f"inv-{inv:04d}"
        wdir.mkdir(parents=True, exist_ok=True)
        return subprocess.Popen([sys.executable, "-c", worker, str(wdir / "games.jsonl"),
                                 str(span[0]), str(span[1]), "0.05"])

    class Busy:  # quiet until the workers are out, then a foreign job for the rest of the run
        n = 0

        def poll(self):
            Busy.n += 1
            return Busy.n > 1

        def describe(self):
            return "python[1] 9000 MB sm 90%"

    monkeypatch.setattr(orc.Run, "launch_worker", launch_worker)
    monkeypatch.setattr(orc.Run, "_verify_jar", lambda self: Path("x.jar"), raising=False)
    monkeypatch.setattr(orc, "GpuYield", Busy)
    monkeypatch.setattr(orc, "heartbeat", lambda *_: None)
    orc.schedule_group([a], slots=1)
    assert orc.yield_draws(a.dir) == {1, 3}
    rows = {r["i"]: r for r in map(json.loads, (a.dir / "games.jsonl").read_text().splitlines())}
    assert [rows[i]["status"] for i in range(4)] == ["won", orc.YIELD_DRAW_STATUS, "won", orc.YIELD_DRAW_STATUS]
    assert rows[1]["yield_draw"] is True and "yield_draw" not in rows[0]
    assert json.loads((a.dir / "summary.json").read_text())["statuses"] == {"won": 2, orc.YIELD_DRAW_STATUS: 2}


def test_no_yield_no_void(tmp_path, fake_workers, monkeypatch):
    a = _mk_run(tmp_path, "a", games=3, chunk=1)
    monkeypatch.setattr(orc, "heartbeat", lambda *_: None)
    orc.schedule_group([a], slots=2)
    assert not (a.dir / "yield-draws.jsonl").exists()
    assert all(json.loads(x)["status"] == "won" for x in (a.dir / "games.jsonl").read_text().splitlines())
