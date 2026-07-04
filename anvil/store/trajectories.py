"""Trajectory store v0 (docs/design/observation-schema-v1.md).

Layout under data/trajectories/<run_id>/:
  manifest.json  provenance (run pins + pool version + obs schema); engine
                 hashes live here and ONLY here — never in records.
  obs-NNNN.zst   worker frame files, renumbered at ingest; one independent
                 zstd frame per game, JSONL records inside.
  index.jsonl    one line per game: file, offset, lengths, seed, record count.
  games.jsonl    per-game outcome records (merged worker progress logs).

Ingest is a copy + index, not a re-encode: frames are read back by (file,
offset, clen) so orphaned bytes from crashed games (frames that never got an
idx line) are skipped naturally. The corpus is regenerable (seeds + heuristic);
there is deliberately no backup story.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterator

import zstandard

OBS_SCHEMA_VERSION = 1
TRAJECTORIES_DIR = Path(__file__).parents[2] / "data/trajectories"


@dataclasses.dataclass
class GameTrajectory:
    """One game's decoded frame: header, decisions (answers joined), end."""

    header: dict[str, Any]
    decisions: list[dict[str, Any]]  # "dec" records; ret joined as ["ret"]
    end: dict[str, Any] | None
    index: dict[str, Any]  # the index.jsonl entry (seed, lengths, ...)

    @property
    def game_index(self) -> int:
        return self.header["g"]


def decode_frame(data: bytes) -> tuple[dict, list[dict], dict | None]:
    """Decode one game frame -> (header, decisions-with-ret-joined, end)."""
    records = [json.loads(line) for line in
               zstandard.ZstdDecompressor().decompress(data, max_output_size=1 << 30).splitlines()]
    if not records or records[0].get("k") != "game":
        raise ValueError("frame does not start with a game header record")
    header = records[0]
    if header["sv"] != OBS_SCHEMA_VERSION:
        raise ValueError(f"schema version {header['sv']} != reader version {OBS_SCHEMA_VERSION}")
    decisions: list[dict] = []
    by_seq: dict[int, dict] = {}
    end = None
    for r in records[1:]:
        kind = r.get("k")
        if kind == "dec":
            decisions.append(r)
            by_seq[r["s"]] = r
        elif kind == "ret":
            if r["s"] in by_seq:  # ret without dec = stale-thread record; drop
                by_seq[r["s"]]["ret"] = r["v"]
        elif kind == "end":
            end = r
    return header, decisions, end


class TrajectoryStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        self.index: list[dict] = [
            json.loads(line) for line in (self.root / "index.jsonl").read_text().splitlines()
        ]
        self._by_game = {e["g"]: e for e in self.index}

    def __len__(self) -> int:
        return len(self.index)

    def game_indices(self) -> list[int]:
        return sorted(self._by_game)

    def game(self, g: int) -> GameTrajectory:
        entry = self._by_game[g]
        with open(self.root / entry["file"], "rb") as f:
            f.seek(entry["off"])
            data = f.read(entry["clen"])
        header, decisions, end = decode_frame(data)
        if header["g"] != g:
            raise ValueError(f"index says game {g}, frame header says {header['g']}")
        return GameTrajectory(header, decisions, end, entry)

    def games(self) -> Iterator[GameTrajectory]:
        for g in self.game_indices():
            yield self.game(g)

    def iter_decisions(self, method: str | None = None,
                       by: str | None = None) -> Iterator[tuple[dict, dict]]:
        """Yield (game_header, dec_record) across the store, streaming."""
        for traj in self.games():
            for dec in traj.decisions:
                if method is not None and dec["m"] != method:
                    continue
                if by is not None and dec.get("by") != by:
                    continue
                yield traj.header, dec


def ingest(run_dir: Path | str, dest: Path | str | None = None,
           pool_version: str | None = None, verify: bool = False) -> Path:
    """Consolidate a harness run's worker observation files into the store."""
    run_dir = Path(run_dir)
    run_manifest = json.loads((run_dir / "run.json").read_text())
    run_id = run_manifest["run_id"]
    dest = Path(dest) if dest else TRAJECTORIES_DIR / run_id
    if (dest / "manifest.json").exists():
        sys.exit(f"store already exists at {dest}; ingest is one-shot (delete it to re-ingest)")
    dest.mkdir(parents=True, exist_ok=True)

    index_entries: list[dict] = []
    n_files = 0
    total_clen = 0
    total_rlen = 0
    seen_games: set[int] = set()
    worker_files = sorted(run_dir.glob("workers/inv-*/obs.zst"))
    for src in worker_files:
        idx_path = src.with_name("obs.idx.jsonl")
        if not idx_path.exists():
            print(f"[ingest] WARNING: {src} has no index sidecar, skipping", file=sys.stderr)
            continue
        fname = f"obs-{n_files:04d}.zst"
        size = src.stat().st_size
        kept = 0
        for line in idx_path.read_text().splitlines():
            e = json.loads(line)
            if e["off"] + e["clen"] > size:
                print(f"[ingest] WARNING: game {e['g']} frame extends past EOF in {src}, dropped",
                      file=sys.stderr)
                continue
            if e["g"] in seen_games:
                # a re-issued game (worker crash path); first complete frame wins
                continue
            seen_games.add(e["g"])
            index_entries.append({"file": fname, **e})
            total_clen += e["clen"]
            total_rlen += e["rlen"]
            kept += 1
        if kept:
            shutil.copy2(src, dest / fname)
            n_files += 1

    if not index_entries:
        sys.exit(f"no observation frames found under {run_dir}/workers/ — "
                 "was the run launched with --obs?")

    index_entries.sort(key=lambda e: e["g"])
    with open(dest / "index.jsonl", "w") as f:
        for e in index_entries:
            f.write(json.dumps(e) + "\n")

    # merge per-game outcome records (the harness progress logs)
    outcomes: dict[int, dict] = {}
    for f_ in sorted(run_dir.glob("workers/inv-*/games.jsonl")):
        for line in f_.read_text().splitlines():
            try:
                r = json.loads(line)
                outcomes[r["i"]] = r
            except (json.JSONDecodeError, KeyError):
                continue
    with open(dest / "games.jsonl", "w") as f:
        for i in sorted(outcomes):
            f.write(json.dumps(outcomes[i]) + "\n")

    if pool_version is None:
        pool_version = run_manifest.get("pool_version")
    if pool_version is None:
        print("[ingest] WARNING: no pool version in run.json or --pool-version; "
              "provenance is incomplete", file=sys.stderr)
    manifest = {
        "run_id": run_id,
        "source": "selfplay-heuristic",
        "obs_schema": OBS_SCHEMA_VERSION,
        "pool_version": pool_version,
        "games": len(index_entries),
        "decisions": sum(e["recs"] - 2 for e in index_entries),  # minus game+end records
        "bytes_compressed": total_clen,
        "bytes_raw": total_rlen,
        # run pins, verbatim (fork/jar/anvil hashes, seeds, decks, flags)
        "run": {k: run_manifest[k] for k in
                ("purpose", "created", "fork_commit", "fork_dirty", "anvil_commit",
                 "jar_sha256", "protocol_version", "decks", "pairs_sha256", "n_pairs",
                 "games_per_pair", "format", "seed_base",
                 "games", "bridge", "tags") if k in run_manifest},
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    if verify:
        store = TrajectoryStore(dest)
        n_dec = 0
        for traj in store.games():
            if traj.end is None:
                print(f"[ingest] WARNING: game {traj.game_index} has no end record",
                      file=sys.stderr)
            n_dec += len(traj.decisions)
        print(f"[ingest] verified: {len(store)} games, {n_dec} decisions decode cleanly")

    ratio = total_rlen / total_clen if total_clen else 0
    print(f"[ingest] {run_id}: {len(index_entries)} games -> {dest}\n"
          f"[ingest] {total_rlen / 1e6:.1f} MB raw -> {total_clen / 1e6:.1f} MB "
          f"({ratio:.1f}x, {total_clen / max(len(index_entries), 1) / 1e3:.0f} KB/game)")
    return dest


def status(root: Path | str) -> None:
    store = TrajectoryStore(root)
    m = store.manifest
    print(f"{m['run_id']}: {m['games']} games, {m['decisions']} decisions, "
          f"schema v{m['obs_schema']}, pool {m['pool_version']}")
    print(f"  {m['bytes_raw'] / 1e6:.1f} MB raw / {m['bytes_compressed'] / 1e6:.1f} MB compressed "
          f"({m['bytes_raw'] / max(m['bytes_compressed'], 1):.1f}x), "
          f"{m['bytes_compressed'] / max(m['games'], 1) / 1e3:.0f} KB/game")
