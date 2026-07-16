"""M0 batch orchestrator (docs/design/m0-batch-harness-spec.md).

A run is a list of globally-indexed games consumed in chunks: one JVM worker
invocation per chunk, exiting when its chunk is done (recycling = chunk
boundary). The per-game JSONL each worker appends is the progress record —
resume rescans it and re-issues chunks minus completed games. Pause = the
run-dir STOP file (workers check it between games; finish current game, flush,
exit 0). A game whose worker dies twice is skipped and flagged loudly (free
engine-bug repro), never allowed to wedge the run.

run.json is the per-run pinning manifest: fork commit + dirty flag + jar
sha256 (re-verified before every worker launch — the orchestrator is the sole
launcher at M0, so this enforces the spec's "worker refuses on mismatch"),
anvil commit, protocol version, seeds, flags. Manifests are immutable;
changing worker count or flags mid-run is a new run.

Verbs (python -m anvil.bridge.harness ...):
  launch (--decks D1 D2 | --pool [--games-per-pair 5]) --games N
         [--workers 16] [--colocated] [--bridge MODE]
         [--tags CSV] [--purpose TXT] [--seed-base X] [--chunk 200] [--calibrated]
  resume <run-dir>      status <run-dir>       pause <run-dir>
  replay <run-dir> <index>                     summarize <run-dir>
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from anvil.bridge.harness.seeds import game_seed

FORGE_DIR = Path(os.environ.get("FORGE_DIR", Path.home() / "Everything/Projects/forge"))
FORGE_GUI_DIR = FORGE_DIR / "forge-gui"
RUNS_DIR = Path(os.environ.get("ANVIL_RUNS_DIR", Path(__file__).parents[3] / "data/runs"))
PROTOCOL_VERSION = 0
POLL_S = 2.0


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _find_jar() -> Path:
    jars = sorted((FORGE_DIR / "forge-gui-desktop/target").glob("*-jar-with-dependencies.jar"))
    if not jars:
        sys.exit(f"no forge jar under {FORGE_DIR}/forge-gui-desktop/target — build the fork first")
    return jars[-1]


class Run:
    def __init__(self, run_dir: Path):
        # Resolve: workers run with cwd=FORGE_GUI_DIR, so every path handed to
        # them must be absolute or the results file lands in the wrong tree.
        self.dir = Path(run_dir).resolve()
        self.manifest = json.loads((self.dir / "run.json").read_text())
        self.stop_file = self.dir / "STOP"
        self.workers_dir = self.dir / "workers"
        self.skips_file = self.dir / "skips.json"

    # ---------- state scanning ----------

    def completed(self) -> dict[int, dict]:
        done: dict[int, dict] = {}
        for f in self.workers_dir.glob("inv-*/games.jsonl"):
            for line in f.read_text().splitlines():
                try:
                    r = json.loads(line)
                    done[r["i"]] = r
                except (json.JSONDecodeError, KeyError):
                    continue
        return done

    def skipped(self) -> set[int]:
        if self.skips_file.exists():
            return set(json.loads(self.skips_file.read_text())["indices"])
        return set()

    def remaining_chunks(self) -> list[tuple[int, int]]:
        """Contiguous (start, count) spans still to play, chunk-aligned."""
        done = set(self.completed()) | self.skipped()
        chunk = self.manifest["chunk"]
        start = self.manifest.get("start_index", 0)
        end = start + self.manifest["games"]
        spans = []
        for cstart in range(start, end, chunk):
            cend = min(cstart + chunk, end)
            todo = [i for i in range(cstart, cend) if i not in done]
            i = 0
            while i < len(todo):  # split into contiguous spans
                j = i
                while j + 1 < len(todo) and todo[j + 1] == todo[j] + 1:
                    j += 1
                spans.append((todo[i], j - i + 1))
                i = j + 1
        return spans

    # ---------- worker launch ----------

    def _deck_args(self) -> list[str]:
        """-d for fixed-pair runs, -pairs/-gpp for pool-schedule runs."""
        m = self.manifest
        if m.get("pairs_file"):
            return ["-pairs", str(self.dir / m["pairs_file"]),
                    "-gpp", str(m["games_per_pair"])]
        return ["-d", m["decks"][0], m["decks"][1]]

    def _verify_jar(self) -> Path:
        jar = Path(self.manifest["jar"])
        if not jar.exists() or _sha256(jar) != self.manifest["jar_sha256"]:
            sys.exit("jar hash mismatch vs manifest — the fork was rebuilt since this run "
                     "was created; start a new run (manifests are immutable)")
        return jar

    def launch_worker(self, span: tuple[int, int], inv: int) -> subprocess.Popen:
        jar = self._verify_jar()
        m = self.manifest
        wdir = self.workers_dir / f"inv-{inv:04d}"
        wdir.mkdir(parents=True, exist_ok=True)
        cmd = []
        if m["nice"]:
            cmd += ["nice", "-n", "19"]
        cmd += ["java", f"-Xms{m['heap']}", f"-Xmx{m['heap']}", *m["jvm_opts"],
                "-jar", str(jar), "anvil",
                *self._deck_args(), "-f", m["format"],
                "-range", str(span[0]), str(span[1]),
                "-seedbase", str(m["seed_base"]),
                "-results", str(wdir / "games.jsonl"),
                "-stopfile", str(self.stop_file),
                "-b", m["bridge"]]
        if m.get("tags"):
            cmd += ["-tags", m["tags"]]
        if m.get("obs"):
            cmd += ["-obs", str(wdir / "obs.zst")]
        if m.get("census"):
            # D8: veto reasons + disambiguation rungs live in the census log
            cmd += ["-census", str(wdir / "census.jsonl")]
        if m.get("bridge_seats") is not None:
            cmd += ["-bridgeseats", str(m["bridge_seats"])]
        if m.get("reask"):
            # D6 run-2: re-ask-on-veto (d6-vtrace-loop §6b) — environment
            # change; arms under -reask are not comparable to arms without
            cmd += ["-reask"]
        if m.get("rollout_k"):
            # M2 D4 rollout-label mode: fork points + K completions per game
            cmd += ["-rollout", str(m["rollout_k"]),
                    "-points", str(m.get("rollout_points", 4)),
                    "-labels", str(wdir / "labels.jsonl")]
        (wdir / "cmd.txt").write_text(" ".join(cmd) + "\n")
        out = open(wdir / "out.log", "a")
        return subprocess.Popen(cmd, cwd=FORGE_GUI_DIR, stdout=out, stderr=subprocess.STDOUT)

    # ---------- scheduler ----------

    def schedule(self) -> None:
        pending = self.remaining_chunks()
        total = self.manifest["games"]
        crash_counts: dict[int, int] = {}
        zero_progress_exits = 0  # systemic-failure guard (vs per-game skip rule)
        inv = max([int(p.name[4:]) for p in self.workers_dir.glob("inv-*")] or [-1]) + 1
        active: list[tuple[subprocess.Popen, tuple[int, int]]] = []
        slots = self.manifest["workers"]
        t0 = time.monotonic()
        print(f"[harness] {len(self.completed())}/{total} done, "
              f"{len(pending)} spans pending, {slots} slots")

        while pending or active:
            while pending and len(active) < slots and not self.stop_file.exists():
                span = pending.pop(0)
                active.append((self.launch_worker(span, inv), span))
                print(f"[harness] inv-{inv:04d} <- games [{span[0]},{span[0] + span[1]})")
                inv += 1
            still = []
            for proc, span in active:
                rc = proc.poll()
                if rc is None:
                    still.append((proc, span))
                    continue
                done = set(self.completed()) | self.skipped()
                todo = [i for i in range(span[0], span[0] + span[1]) if i not in done]
                if not todo:
                    continue
                if self.stop_file.exists() and rc == 0:
                    continue  # graceful partial exit; remainder re-issued on resume
                if todo[0] == span[0] and len(todo) == span[1]:
                    zero_progress_exits += 1
                    if zero_progress_exits >= 3:
                        sys.exit("[harness] 3 consecutive workers exited with ZERO games "
                                 "completed — systemic failure (bad paths? server down? "
                                 "see workers/inv-*/out.log), aborting instead of skipping")
                else:
                    zero_progress_exits = 0
                first = todo[0]
                crash_counts[first] = crash_counts.get(first, 0) + 1
                if crash_counts[first] >= 2:
                    skips = self.skipped() | {first}
                    self.skips_file.write_text(json.dumps({"indices": sorted(skips)}))
                    print(f"[harness] !! game {first} (seed "
                          f"{game_seed(self.manifest['seed_base'], first)}) killed its worker "
                          f"twice -> SKIPPED (free engine-bug repro; see skips.json)")
                    todo = todo[1:]
                if todo:
                    pending.insert(0, (todo[0], todo[-1] - todo[0] + 1))
                    print(f"[harness] inv rc={rc}; re-queueing [{todo[0]},{todo[-1] + 1})")
            active = still
            if self.stop_file.exists() and not active:
                print("[harness] paused (STOP present); `resume` to continue")
                return
            n_done = len(self.completed())
            if int(time.monotonic() - t0) % 60 < POLL_S and n_done:
                rate = n_done / max(time.monotonic() - t0, 1) * 3600
                print(f"[harness] {n_done}/{total} ({rate:.0f} g/h this session)")
            time.sleep(POLL_S)
        print(f"[harness] run complete: {len(self.completed())}/{total} "
              f"(+{len(self.skipped())} skipped)")
        summarize(self.dir)


# ---------- verbs ----------

def launch(a) -> Path:
    jar = _find_jar()
    run_id = f"{a.purpose}-{_dt.datetime.now():%Y%m%d-%H%M%S}"
    run_dir = RUNS_DIR / run_id
    (run_dir / "workers").mkdir(parents=True)

    pool_fields = {}
    if getattr(a, "pairs_file", None):
        # D8 arms: an explicit pair schedule (e.g. valpair-only held-out
        # matchups) replaces the pool-derived one; same worker mechanism.
        import shutil
        shutil.copy(a.pairs_file, run_dir / "pairs.txt")
        n_lines = sum(1 for _ in open(run_dir / "pairs.txt"))
        pool_fields = {
            "pairs_file": "pairs.txt",
            "pairs_source": str(a.pairs_file),
            "pairs_sha256": _sha256(run_dir / "pairs.txt"),
            "n_pairs": n_lines,
            "games_per_pair": a.games_per_pair,
        }
        print(f"[harness] explicit pairs file: {n_lines} pairs x {a.games_per_pair} games")
    elif a.pool:
        from anvil.bridge.harness.pairs import (latest_pool_manifest, pair_schedule,
                                                write_pairs_file)
        pool = latest_pool_manifest()
        # schedule covers [0, start+games) so a start-index run's pair mapping
        # (index // gpp) is identical to the run it extends — pair_schedule is
        # prefix-stable in n_pairs, so the shared prefix matches by construction
        n_pairs = -(-(a.start_index + a.games) // a.games_per_pair)  # ceil
        pairs = pair_schedule([d["file"] for d in pool["decks"]], n_pairs, a.seed_base)
        write_pairs_file(run_dir / "pairs.txt", pairs)
        pool_fields = {
            "pool_version": pool["pool_version"],
            "pairs_file": "pairs.txt",
            "pairs_sha256": _sha256(run_dir / "pairs.txt"),
            "n_pairs": n_pairs,
            "games_per_pair": a.games_per_pair,
        }
        print(f"[harness] pool {pool['pool_version']}: {len(pool['decks'])} decks -> "
              f"{n_pairs} pairs x {a.games_per_pair} games")

    manifest = {
        "run_id": run_id, "purpose": a.purpose,
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "fork_commit": _git(FORGE_DIR, "rev-parse", "HEAD"),
        "fork_dirty": bool(_git(FORGE_DIR, "status", "--porcelain")),
        "anvil_commit": _git(Path(__file__).parents[3], "rev-parse", "HEAD"),
        "jar": str(jar), "jar_sha256": _sha256(jar),
        "protocol_version": PROTOCOL_VERSION,
        "decks": a.decks, "format": a.format, **pool_fields,
        "seed_base": a.seed_base, "games": a.games, "chunk": a.chunk,
        "start_index": a.start_index,
        "workers": 12 if a.colocated else a.workers,
        # ExitOnOutOfMemoryError: a batch worker must die (chunk re-issue
        # covers it), not limp — an OOM that escaped the game-loop catch
        # reached Forge's GUI bug-report dialog and wedged two headless
        # workers forever (model-mirror run, 2026-07-12). The fork also
        # installs a headless uncaught handler; this is the JVM-level belt.
        "heap": "2g", "jvm_opts": ["-XX:ActiveProcessorCount=2",
                                   "-XX:+ExitOnOutOfMemoryError"],
        "bridge": a.bridge, "tags": a.tags, "nice": not a.calibrated,
        "obs": a.obs, "obs_schema": 1 if a.obs else None,
        "census": getattr(a, "census", False),
        "bridge_seats": getattr(a, "bridge_seats", None),
        "reask": getattr(a, "reask", False),
        "rollout_k": getattr(a, "rollout_k", None),
        "rollout_points": getattr(a, "rollout_points", None),
    }
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[harness] run {run_id}: {a.games} games, w={manifest['workers']}, "
          f"bridge={a.bridge}, seed_base={a.seed_base}")
    if a.calibrated:
        print("[harness] CALIBRATED run: workers at normal priority — keep the box quiet")
    Run(run_dir).schedule()
    return run_dir


def resume(run_dir: Path) -> None:
    r = Run(run_dir)
    if r.stop_file.exists():
        r.stop_file.unlink()
    r.schedule()


def pause(run_dir: Path) -> None:
    Run(run_dir).stop_file.touch()
    print("[harness] STOP written; workers finish their current game and exit")


def status(run_dir: Path) -> None:
    r = Run(run_dir)
    done = r.completed()
    m = r.manifest
    state = ("paused" if r.stop_file.exists()
             else "complete" if len(done) + len(r.skipped()) >= m["games"] else "in progress")
    print(f"{m['run_id']}: {len(done)}/{m['games']} done, {len(r.skipped())} skipped [{state}]")
    if done:
        ms = sorted(g["ms"] for g in done.values())
        print(f"  median {ms[len(ms) // 2] / 1000:.1f}s/game, "
              f"draws {sum(1 for g in done.values() if g['status'] != 'won')}")


def replay(run_dir: Path, index: int) -> None:
    r = Run(run_dir)
    m = r.manifest
    print(f"[harness] replaying game {index} "
          f"(seed {game_seed(m['seed_base'], index)}) of {m['run_id']}")
    r._verify_jar()
    cmd = ["java", f"-Xms{m['heap']}", f"-Xmx{m['heap']}", *m["jvm_opts"],
           "-jar", m["jar"], "anvil", *r._deck_args(),
           "-f", m["format"], "-range", str(index), "1",
           "-seedbase", str(m["seed_base"]), "-b", m["bridge"]]
    if m.get("tags"):
        cmd += ["-tags", m["tags"]]
    if m.get("obs"):
        # The priority-option scan perturbs which trajectory a seed plays
        # (D2 smoke, 2026-07-04: 14/20 identical without it) — a replay must
        # match the original run's logging configuration to reproduce it.
        # The replay's own observation output is a throwaway.
        cmd += ["-obs", str(run_dir / f"replay-{index}-obs.zst")]
    subprocess.run(cmd, cwd=FORGE_GUI_DIR, check=False)


def summarize(run_dir: Path) -> None:
    r = Run(run_dir)
    done = r.completed()
    merged = r.dir / "games.jsonl"
    with open(merged, "w") as f:
        for i in sorted(done):
            f.write(json.dumps(done[i]) + "\n")
    games = list(done.values())
    ms = sorted(g["ms"] for g in games) or [0]
    obs_bytes = sum(f.stat().st_size for f in r.workers_dir.glob("inv-*/obs.zst"))
    # Wall-clock tail = the convoke/improvise watch-item (M1 plan D3): the
    # slowest games are the ones to pull frames for if the tail is ugly.
    slowest = sorted(games, key=lambda g: -g["ms"])[:10]
    summary = {
        "games": len(games), "skipped": sorted(r.skipped()),
        "decisive": sum(1 for g in games if g["status"] == "won"),
        "draw_clock_hits": sum(1 for g in games if g.get("draw_clock")),
        "statuses": {s: sum(1 for g in games if g["status"] == s)
                     for s in {g["status"] for g in games}},
        "turns_median": sorted(g["turns"] for g in games)[len(games) // 2] if games else 0,
        "ms_median": ms[len(ms) // 2],
        "ms_p90": ms[int(len(ms) * 0.9)] if games else 0,
        "ms_max": ms[-1],
        "game_hours_played": sum(g["ms"] for g in games) / 3.6e6,
        "obs_bytes": obs_bytes,
        "obs_kb_per_game": round(obs_bytes / max(len(games), 1) / 1e3, 1),
        "slowest_games": [{k: g.get(k) for k in ("i", "seed", "ms", "turns", "decks")}
                          for g in slowest],
    }
    (r.dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
