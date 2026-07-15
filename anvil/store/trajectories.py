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
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterator

import zstandard

_SEAT = re.compile(r"\((\d+)\)")  # "Anvil(2)-dc-864160" / "Heur(1)-..." -> seat

OBS_SCHEMA_VERSION = 1
TRAJECTORIES_DIR = Path(__file__).parents[2] / "data/trajectories"


@dataclasses.dataclass
class GameTrajectory:
    """One game's decoded frame: header, decisions (answers joined), end.
    marks: fork-point marker records (M2 D4 rollout labels) with _pos set —
    a label's training window is the first priority dec after its mark."""

    header: dict[str, Any]
    decisions: list[dict[str, Any]]  # "dec" records; ret joined as ["ret"]
    end: dict[str, Any] | None
    index: dict[str, Any]  # the index.jsonl entry (seed, lengths, ...)
    marks: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    @property
    def game_index(self) -> int:
        return self.header["g"]


def decode_frame(data: bytes) -> tuple[dict, list[dict], dict | None, list[dict]]:
    """Decode one game frame -> (header, decisions-with-ret-joined, end, marks)."""
    records = [json.loads(line) for line in
               zstandard.ZstdDecompressor().decompress(data, max_output_size=1 << 30).splitlines()]
    if not records or records[0].get("k") != "game":
        raise ValueError("frame does not start with a game header record")
    header = records[0]
    if header["sv"] != OBS_SCHEMA_VERSION:
        raise ValueError(f"schema version {header['sv']} != reader version {OBS_SCHEMA_VERSION}")
    decisions: list[dict] = []
    marks: list[dict] = []
    by_seq: dict[int, dict] = {}
    end = None
    for pos, r in enumerate(records[1:]):
        kind = r.get("k")
        if kind == "mark":
            r["_pos"] = pos
            marks.append(r)
        elif kind == "dec":
            # _pos/_retpos: record-stream positions (in-memory only, never
            # serialized). Decisions NEST — a parent's ret can land after its
            # children's decs — and the serve-time history ring back-fills
            # hosts only at ret time, so training history must know WHEN each
            # answer arrived, not just that it eventually did (M2 D2 fix for
            # the nested-window skew documented in Obs.java).
            r["_pos"] = pos
            decisions.append(r)
            by_seq[r["s"]] = r
        elif kind == "ret":
            if r["s"] in by_seq:  # ret without dec = stale-thread record; drop
                by_seq[r["s"]]["ret"] = r["v"]
                by_seq[r["s"]]["_retpos"] = pos
                if "oi" in r:  # exact SA-level option index (logged since 2026-07-10)
                    by_seq[r["s"]]["oi"] = r["oi"]
        elif kind == "end":
            end = r
    return header, decisions, end, marks


class TrajectoryStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        self.index: list[dict] = [
            json.loads(line) for line in (self.root / "index.jsonl").read_text().splitlines()
        ]
        self._by_game = {e["g"]: e for e in self.index}
        # Per-game outcome records (harness progress logs, merged at ingest).
        # These carry the TRUE winner: the frame end-record's "winner" field
        # is broken pre-fork-fix (derived from the post-elimination live
        # player list -> ~always 0; found 2026-07-11, D4). Never read
        # end["winner"] for outcomes — use winner_seat().
        self.outcomes: dict[int, dict] = {}
        games_path = self.root / "games.jsonl"
        if games_path.exists():
            for line in games_path.read_text().splitlines():
                try:
                    r = json.loads(line)
                    self.outcomes[r["i"]] = r
                except (json.JSONDecodeError, KeyError):
                    continue

    def winner_seat(self, g: int) -> int | None:
        """True winning seat from the outcome record; None for non-decisive
        games, missing records, or unparseable winner names. Verified against
        final life totals/lost flags 492/492 on the D3 pilot (2026-07-11)."""
        r = self.outcomes.get(g)
        if not r or r.get("status") != "won" or not r.get("winner"):
            return None
        m = _SEAT.search(r["winner"])
        return int(m.group(1)) - 1 if m else None

    def mu_for_game(self, g: int) -> dict[int, dict] | None:
        """Behavior-policy records for game g, keyed by dec seq (M2 D6
        sampled-actor stores); None when the store carries no mu.jsonl.
        Lazy whole-file load — RL iteration stores are small (~10^5 recs)."""
        if not hasattr(self, "_mu"):
            self._mu: dict[int, dict[int, dict]] | None = None
            self.mu_meta: dict | None = None
            path = self.root / "mu.jsonl"
            if path.exists():
                self._mu = {}
                for line in path.read_text().splitlines():
                    r = json.loads(line)
                    if r.get("k") == "meta":
                        self.mu_meta = r
                        continue
                    self._mu.setdefault(r["g"], {})[r["s"]] = r
        return None if self._mu is None else self._mu.get(g, {})

    def __len__(self) -> int:
        return len(self.index)

    def game_indices(self) -> list[int]:
        return sorted(self._by_game)

    def game(self, g: int) -> GameTrajectory:
        entry = self._by_game[g]
        with open(self.root / entry["file"], "rb") as f:
            f.seek(entry["off"])
            data = f.read(entry["clen"])
        header, decisions, end, marks = decode_frame(data)
        if header["g"] != g:
            raise ValueError(f"index says game {g}, frame header says {header['g']}")
        return GameTrajectory(header, decisions, end, entry, marks)

    def games(self, skip_undecodable: bool = False) -> Iterator[GameTrajectory]:
        """skip_undecodable: quarantine truncated/corrupt frames (a hard-capped
        game killed mid-write) instead of raising — training readers want the
        49,999 good games, not an exception on the one bad frame."""
        for g in self.game_indices():
            try:
                yield self.game(g)
            except Exception:
                if not skip_undecodable:
                    raise

    def iter_decisions(self, method: str | None = None,
                       by: str | None = None) -> Iterator[tuple[dict, dict]]:
        """Yield (game_header, dec_record) across the store, streaming."""
        for traj in self.games(skip_undecodable=True):
            for dec in traj.decisions:
                if method is not None and dec["m"] != method:
                    continue
                if by is not None and dec.get("by") != by:
                    continue
                yield traj.header, dec


class MultiStore:
    """Several stores read as one corpus. Game indices must be disjoint —
    the intended shape is runs that extend one seed stream (harness
    --start-index: the D3 pilot holds games [0, 50K), the D6 extension
    [50K, ...)), so a global game index keeps meaning "one deterministic
    game" and split functions of it stay consistent across stores."""

    def __init__(self, roots):
        self.stores = [TrajectoryStore(r) for r in roots]
        self._store_of: dict[int, TrajectoryStore] = {}
        for s in self.stores:
            for g in s.game_indices():
                if g in self._store_of:
                    raise ValueError(
                        f"game {g} present in both {self._store_of[g].root} and "
                        f"{s.root} — extension runs must use disjoint index ranges")
                self._store_of[g] = s

    def __len__(self) -> int:
        return len(self._store_of)

    def game_indices(self) -> list[int]:
        return sorted(self._store_of)

    def game(self, g: int) -> GameTrajectory:
        return self._store_of[g].game(g)

    def winner_seat(self, g: int) -> int | None:
        return self._store_of[g].winner_seat(g)

    def mu_for_game(self, g: int) -> dict[int, dict] | None:
        return self._store_of[g].mu_for_game(g)

    def games(self, skip_undecodable: bool = False) -> Iterator[GameTrajectory]:
        for g in self.game_indices():
            try:
                yield self.game(g)
            except Exception:
                if not skip_undecodable:
                    raise


def open_store(spec) -> TrajectoryStore | MultiStore:
    """One store dir, a comma-separated string of dirs, or a list of dirs."""
    if isinstance(spec, str) and "," in spec:
        spec = spec.split(",")
    if isinstance(spec, (list, tuple)):
        return MultiStore(spec) if len(spec) > 1 else TrajectoryStore(spec[0])
    return TrajectoryStore(spec)


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

    # merge rollout-label records (M2 D4 labeler runs); keyed (i, fp),
    # first record wins on chunk re-issue like the frame rule above
    label_rows: dict[tuple[int, int], dict] = {}
    for f_ in sorted(run_dir.glob("workers/inv-*/labels.jsonl")):
        for line in f_.read_text().splitlines():
            try:
                r = json.loads(line)
                label_rows.setdefault((r["i"], r["fp"]), r)
            except (json.JSONDecodeError, KeyError):
                continue
    if label_rows:
        with open(dest / "labels.jsonl", "w") as f:
            for key in sorted(label_rows):
                f.write(json.dumps(label_rows[key]) + "\n")
        print(f"[ingest] {len(label_rows)} rollout-label records -> labels.jsonl")

    # merge behavior-policy records (M2 D6 sampled actors; server-side file,
    # run-level). Keyed (g, s), LAST wins — a re-issued game (first attempt
    # crashed mid-game) answers again and the completing attempt is the later
    # one; the rare kept-frame/mu mismatch is caught by the learner's logp
    # recompute tripwire, not here.
    mu_src = run_dir / "mu.jsonl"
    if mu_src.exists():
        meta = None
        mu_rows: dict[tuple[int, int], dict] = {}
        for line in mu_src.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("k") == "meta":
                meta = r
                continue
            if "g" in r and "s" in r:
                mu_rows[(r["g"], r["s"])] = r
        with open(dest / "mu.jsonl", "w") as f:
            if meta is not None:
                f.write(json.dumps(meta) + "\n")
            for key in sorted(mu_rows):
                f.write(json.dumps(mu_rows[key]) + "\n")
        print(f"[ingest] {len(mu_rows)} behavior-policy records -> mu.jsonl")

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
