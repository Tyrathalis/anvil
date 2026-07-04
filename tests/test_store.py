"""Trajectory store v0: synthetic frames -> ingest -> read-back.

The synthetic frames mimic the Java writer's output byte-for-byte in structure
(one zstd frame per game appended to obs.zst, idx sidecar with offsets), so
these tests pin the file-format contract from the Python side; the Java side
is pinned by the end-to-end smoke run (devlog 2026-07-04).
"""

import json
from pathlib import Path

import pytest
import zstandard

from anvil.store import OBS_SCHEMA_VERSION, TrajectoryStore, decode_frame, ingest


def _obs(turn=1, ph="MAIN1"):
    return {
        "glob": {"turn": turn, "ph": ph, "ap": 0},
        "players": [{"life": 40, "hand": 7, "lib": 92}, {"life": 40, "hand": 7, "lib": 92}],
        "ents": [{"e": 1, "n": "Sol Ring", "z": "hand", "c": 0}],
    }


def _frame_records(g, seed, n_decisions=3, with_end=True):
    recs = [{"k": "game", "sv": OBS_SCHEMA_VERSION, "g": g, "seed": seed, "fmt": "Commander",
             "players": [{"name": "P0", "deck": "D0"}, {"name": "P1", "deck": "D1"}]}]
    for s in range(n_decisions):
        recs.append({"k": "dec", "s": s, "t": 1, "ph": "MAIN1", "p": 0,
                     "m": "chooseSpellAbilityToPlay", "d": 10, "obs": _obs()})
        recs.append({"k": "ret", "s": s, "v": {"e": 1, "sa": "Sol Ring - cast"}})
    if with_end:
        recs.append({"k": "end", "status": "won", "winner": 0, "turns": 9, "ms": 1234})
    return recs


def _write_worker(wdir: Path, frames: list[list[dict]], truncate_last=False):
    """Append frames the way Obs.java does: independent zstd frames + idx lines."""
    wdir.mkdir(parents=True)
    obs_path = wdir / "obs.zst"
    idx_path = wdir / "obs.idx.jsonl"
    cctx = zstandard.ZstdCompressor(level=3)
    offset = 0
    with open(obs_path, "wb") as f, open(idx_path, "w") as idx:
        for recs in frames:
            raw = "".join(json.dumps(r) + "\n" for r in recs).encode()
            frame = cctx.compress(raw)
            f.write(frame)
            g = recs[0]["g"]
            idx.write(json.dumps({"g": g, "off": offset, "clen": len(frame),
                                  "rlen": len(raw), "seed": recs[0]["seed"],
                                  "recs": len(recs)}) + "\n")
            offset += len(frame)
        if truncate_last:
            # simulate a JVM death mid-frame: orphan bytes past the last idx entry
            f.write(b"\x28\xb5\x2f\xfd partial")
    with open(wdir / "games.jsonl", "w") as f:
        for recs in frames:
            f.write(json.dumps({"i": recs[0]["g"], "seed": recs[0]["seed"], "status": "won",
                                "winner": "P0", "turns": 9, "ms": 1234}) + "\n")


def _make_run(tmp_path: Path, frames_by_worker: list[list[list[dict]]]) -> Path:
    run_dir = tmp_path / "run"
    for i, frames in enumerate(frames_by_worker):
        _write_worker(run_dir / f"workers/inv-{i:04d}", frames)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "test-run", "purpose": "test", "created": "2026-07-04T00:00:00",
        "fork_commit": "deadbeef", "fork_dirty": False, "anvil_commit": "cafebabe",
        "jar_sha256": "0" * 64, "protocol_version": 0, "decks": ["D0", "D1"],
        "format": "Commander", "seed_base": 1, "games": 4, "chunk": 2,
        "workers": 1, "heap": "2g", "jvm_opts": [], "bridge": "local-random", "tags": "none",
    }))
    return run_dir


def test_roundtrip_and_join(tmp_path):
    run_dir = _make_run(tmp_path, [[_frame_records(0, 11), _frame_records(1, 22)],
                                   [_frame_records(2, 33)]])
    dest = ingest(run_dir, dest=tmp_path / "store", pool_version="cf2ca6ba")
    store = TrajectoryStore(dest)

    assert len(store) == 3
    assert store.game_indices() == [0, 1, 2]
    traj = store.game(1)
    assert traj.header["seed"] == 22
    assert traj.end["winner"] == 0
    assert len(traj.decisions) == 3
    # ret joined onto its dec by seq
    assert traj.decisions[0]["ret"] == {"e": 1, "sa": "Sol Ring - cast"}
    assert store.manifest["pool_version"] == "cf2ca6ba"
    assert store.manifest["obs_schema"] == OBS_SCHEMA_VERSION
    assert store.manifest["run"]["fork_commit"] == "deadbeef"

    decs = list(store.iter_decisions(method="chooseSpellAbilityToPlay"))
    assert len(decs) == 9


def test_orphan_bytes_and_duplicate_games(tmp_path):
    # worker 0 died mid-frame after game 0; worker 1 re-played game 0 and added game 1
    run_dir = tmp_path / "run"
    _write_worker(run_dir / "workers/inv-0000", [_frame_records(0, 11)], truncate_last=True)
    _write_worker(run_dir / "workers/inv-0001", [_frame_records(0, 11), _frame_records(1, 22)])
    (run_dir / "run.json").write_text(json.dumps({"run_id": "t", "games": 2, "chunk": 2}))

    dest = ingest(run_dir, dest=tmp_path / "store")
    store = TrajectoryStore(dest)
    assert store.game_indices() == [0, 1]  # dup dropped, orphan bytes ignored
    assert store.game(0).header["seed"] == 11
    assert store.game(1).end is not None


def test_schema_version_gate():
    raw = json.dumps({"k": "game", "sv": 999, "g": 0, "seed": 1, "players": []}).encode() + b"\n"
    frame = zstandard.ZstdCompressor().compress(raw)
    with pytest.raises(ValueError, match="schema version"):
        decode_frame(frame)


def test_stale_ret_dropped():
    """A ret whose dec never landed in this frame (stale thread) is ignored."""
    recs = _frame_records(0, 11, n_decisions=1)
    recs.append({"k": "ret", "s": 999, "v": True})
    raw = "".join(json.dumps(r) + "\n" for r in recs).encode()
    header, decisions, end = decode_frame(zstandard.ZstdCompressor().compress(raw))
    assert len(decisions) == 1
    assert decisions[0]["ret"] is not None
