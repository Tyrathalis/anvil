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
import subprocess
import sys
import time
from pathlib import Path

from anvil.bridge.harness.gpu_yield import GpuYield
from anvil.bridge.harness.seeds import game_seed
from anvil.runs import heartbeat
from anvil.store.trajectories import OBS_SCHEMA_VERSION

FORGE_DIR = Path(os.environ.get("FORGE_DIR", Path.home() / "Everything/Projects/forge"))
FORGE_GUI_DIR = FORGE_DIR / "forge-gui"
RUNS_DIR = Path(os.environ.get("ANVIL_RUNS_DIR", Path(__file__).parents[3] / "data/runs"))
PROTOCOL_VERSION = 0
POLL_S = 2.0


YIELD_DRAW_STATUS = "yield_clock"  # a game the wall game clock drew while a foreign job held the GPU
YIELD_DRAW_SLACK_S = 70.0          # a finished game is first seen up to a progress tick after its end


def yield_draws(run_dir: Path) -> set[int]:
    """The games of a run the yield guard voided (`yield-draws.jsonl`)."""
    f = Path(run_dir) / "yield-draws.jsonl"
    if not f.exists():
        return set()
    out: set[int] = set()
    for line in f.read_text().splitlines():
        try:
            out.add(int(json.loads(line)["i"]))
        except (ValueError, KeyError, TypeError):
            continue
    return out


def void_yield_draws(row: dict, voided: set[int]) -> dict:
    """A voided game's outcome row: its status says why, so the learner skips
    it (rl.py trains won and draw only) and no report counts it as a draw."""
    if row.get("i") in voided:
        return dict(row, status=YIELD_DRAW_STATUS, yield_draw=True)
    return row


def overlaps_yield(ms: float, seen_at: float, windows: "list[tuple[float, float]]",
                   slack_s: float = YIELD_DRAW_SLACK_S) -> bool:
    """Did a game of `ms` milliseconds, first seen finished at `seen_at`, run
    during any GPU-yield window ((start, end) epoch seconds)?"""
    start = seen_at - ms / 1000.0 - slack_s
    return any(w0 <= seen_at and w1 >= start for w0, w1 in windows)


def progress_note(n_done: int, total: int, rate: float, yield_why: str, last: "tuple | None") -> "tuple[str | None, tuple]":
    """The scheduler's once-a-minute progress line, or None when neither the
    completed count nor the yield state has moved since the last one
    printed. The line lands in the launching loop's log, which the launcher's
    stall tick watches: repeated every minute at an unchanged count
    ("29/120 … 29/120 …") it would keep that tick fresh while every worker
    is wedged. Silence means nothing completed; a yield is still
    announced (the transition lines, the marked line once) and heartbeats.
    Returns (line or None, the key to pass back as `last`)."""
    key = (n_done, yield_why)
    if key == last:
        return None, key
    mark = f" (yielding: {yield_why})" if yield_why else ""
    return f"[harness] {n_done}/{total} ({rate:.0f} g/h this session){mark}", key


def mem_available_mb(meminfo: str = "/proc/meminfo") -> "float | None":
    """MemAvailable in MB; None where /proc/meminfo is absent (macOS)."""
    try:
        for line in open(meminfo):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return None


def mem_floor_mb() -> float:
    """The generation phase's host-memory floor: no NEW worker starts while
    MemAvailable is under it ($ANVIL_GEN_MEM_FLOOR_GB, default 4; 0 = off)."""
    try:
        return float(os.environ.get("ANVIL_GEN_MEM_FLOOR_GB", "4")) * 1024
    except ValueError:
        return 4096.0


def mem_hold(avail_mb: "float | None", floor_mb: float, holding: bool, margin_mb: float = 1024.0) -> bool:
    """Whether new workers are held for host memory. Entered under the
    floor, left a margin above it, so a level that sits at the floor does
    not flap. Unknown memory or a zero floor never holds."""
    if avail_mb is None or floor_mb <= 0:
        return False
    return avail_mb < (floor_mb + margin_mb if holding else floor_mb)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def default_chunk(games: int, workers: int) -> int:
    """The chunk rule: four rounds of refill per worker — the tail is then
    one game, not one chunk (at one round a run waits ~20 min on its last
    chunk); a JVM start per chunk is ~20 s."""
    return max(1, -(-int(games) // (4 * max(int(workers), 1))))


def bridge_addrs(m: dict) -> list[str]:
    """`--bridge` is a comma list of addresses (one
    model server each, `anvil.bridge.fleet`); a worker gets ONE of them."""
    return [b.strip() for b in str(m["bridge"]).split(",") if b.strip()]


def bridge_for(m: dict, inv: int) -> str:
    """Round-robin by invocation index: every chunk is a fresh worker launch,
    so a rebalance is a per-chunk address choice (never a live migration)."""
    addrs = bridge_addrs(m)
    return addrs[inv % len(addrs)]


def is_grpc(m: dict) -> bool:
    return any(b.startswith("grpc:") for b in bridge_addrs(m))


def _worker_deadline(m: dict, extra: list[str]) -> list[str]:
    """The bridge deadline for a served run: 20 s unless the caller pinned
    one. The 5 s Java default poisons every game under a first-window
    burst (a surface expansion round at eight workers, or 16 workers with
    no search at all), and a served fleet at 16+ workers is the norm, so
    the raise is unconditional for grpc runs (a stuck server is still
    detected, 15 s later)."""
    if not is_grpc(m):
        return []
    if any(o.startswith("-Danvil.bridge.deadline.ms=") for o in [*m["jvm_opts"], *extra]):
        return []
    return ["-Danvil.bridge.deadline.ms=20000"]


def _provenance_args(m: dict) -> list[str]:
    """ADR-0102 item 4: the pool id and fork commit ride the worker command
    line into the obs game header and the bridge hello (both from run.json,
    so a replay carries the run's own pins)."""
    args: list[str] = []
    if m.get("pool_version"):
        args += ["-pool", str(m["pool_version"])]
    if m.get("fork_commit"):
        args += ["-forkcommit", str(m["fork_commit"])]
    return args


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _find_jar() -> Path:
    # newest-mtime, not alphabetical: an ADR-0059-class hazard — a stale
    # lower-versioned jar sorts before a fresh one and silently wins
    jars = sorted(
        (FORGE_DIR / "forge-gui-desktop/target").glob("*-jar-with-dependencies.jar"),
        key=lambda p: p.stat().st_mtime,
    )
    if not jars:
        sys.exit(f"no forge jar under {FORGE_DIR}/forge-gui-desktop/target — build the fork first")
    if len(jars) > 1:
        print(f"WARNING: multiple candidate jars in target/ — using newest: {jars[-1]}", file=sys.stderr)
    return jars[-1]


class Run:
    def __init__(self, run_dir: Path):
        # Resolve: workers run with cwd=FORGE_GUI_DIR, so every path handed to
        # them must be absolute or the results file lands in the wrong tree.
        self.dir = Path(run_dir).resolve()
        self.manifest = json.loads((self.dir / "run.json").read_text())
        self.stop_file = self.dir / "STOP"
        self.yield_file = self.dir / "YIELD"  # manual: no new chunks, workers keep going
        self.yield_state_file = self.dir / "gpu-yield.json"
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
            return ["-pairs", str(self.dir / m["pairs_file"]), "-gpp", str(m["games_per_pair"])]
        return ["-d", m["decks"][0], m["decks"][1]]

    def _verify_jar(self) -> Path:
        jar = Path(self.manifest["jar"])
        if not jar.exists() or _sha256(jar) != self.manifest["jar_sha256"]:
            sys.exit(
                "jar hash mismatch vs manifest — the fork was rebuilt since this run "
                "was created; start a new run (manifests are immutable)"
            )
        return jar

    def launch_worker(self, span: tuple[int, int], inv: int) -> subprocess.Popen:
        jar = self._verify_jar()
        m = self.manifest
        wdir = self.workers_dir / f"inv-{inv:04d}"
        wdir.mkdir(parents=True, exist_ok=True)
        cmd = []
        if m["nice"]:
            cmd += ["nice", "-n", "19"]
        # ANVIL_EXTRA_JVM_OPTS: ad-hoc worker JVM flags (e.g.
        # -Danvil.crash.trace=true for crash-class diagnosis) without a
        # manifest change; space-separated.
        extra = os.environ.get("ANVIL_EXTRA_JVM_OPTS", "").split()
        extra = [*extra, *_worker_deadline(m, extra)]
        cmd += [
            "java",
            f"-Xms{m['heap']}",
            f"-Xmx{m['heap']}",
            *m["jvm_opts"],
            *extra,
            "-jar",
            str(jar),
            "anvil",
            *self._deck_args(),
            "-f",
            m["format"],
            "-range",
            str(span[0]),
            str(span[1]),
            "-seedbase",
            str(m["seed_base"]),
            "-results",
            str(wdir / "games.jsonl"),
            "-stopfile",
            str(self.stop_file),
            "-b",
            bridge_for(m, inv),
            *_provenance_args(m),
        ]
        if m.get("tags"):
            cmd += ["-tags", m["tags"]]
        if m.get("obs"):
            cmd += ["-obs", str(wdir / "obs.zst")]
        if m.get("tape"):
            cmd += ["-tape"]
        if m.get("census"):
            # D8: veto reasons + disambiguation rungs live in the census log
            cmd += ["-census", str(wdir / "census.jsonl")]
        if m.get("paytelemetry"):
            # M9 D3 §3c payment-surface telemetry — trajectory-perturbing;
            # the manifest pin is what makes sweep replays reproduce
            cmd += ["-paytelemetry"]
        if m.get("bridge_seats") is not None:
            cmd += ["-bridgeseats", str(m["bridge_seats"])]
        if m.get("reask"):
            # re-ask-on-veto (d6-vtrace-loop §6b) — environment
            # change; arms under -reask are not comparable to arms without
            cmd += ["-reask"]
        if m.get("rollout_k"):
            # M2 D4 rollout-label mode: fork points + K completions per game
            cmd += [
                "-rollout",
                str(m["rollout_k"]),
                "-points",
                str(m.get("rollout_points", 4)),
                "-labels",
                str(wdir / "labels.jsonl"),
            ]
        if m.get("drill_file"):
            # M4 D2 drill mode: curated fork turns replace -points sampling
            cmd += ["-drillfile", str(self.dir / m["drill_file"])]
            if m.get("drill_stop"):
                cmd += ["-drillstop"]
        if m.get("fork_obs"):
            # M4 D3: completions become store frames of their own
            cmd += ["-forkobs"]
        if m.get("fork_ns") is not None:
            # store-namespaced fork ids (unnamespaced ids collide across
            # stores) — the planner assigns ns per source store
            cmd += ["-forkns", str(m["fork_ns"])]
        if m.get("force_branch"):
            # M7 D2: act/hold paired branches at drilled fork points
            cmd += ["-forcebranch"]
        if m.get("force_seq"):
            # M7 D2 sequence probe: natural/hold-N/act-N paired arms
            cmd += ["-forceseq", str(m["force_seq"])]
            if m.get("seq_arms"):
                # M8 D1: single-natural-arm OBSERVE mode ('nat')
                cmd += ["-seqarms", str(m["seq_arms"])]
        if m.get("certify_horizon") is not None:
            # M10 reset Fork 3: inline certification (arms decided at the
            # window by the bridge; rate = the server's --certify-rate)
            cmd += ["-certify", str(m["certify_horizon"])]
        if m.get("labels") and not m.get("rollout_k"):
            # the search directive's rows outside rollout mode
            cmd += ["-labels", str(wdir / "labels.jsonl")]
        if m.get("forge_args"):
            # verbatim AnvilRun flags (the search directive's
            # budget / acting pins) — part of the arm's identity
            cmd += list(m["forge_args"])
        (wdir / "cmd.txt").write_text(" ".join(cmd) + "\n")
        out = open(wdir / "out.log", "a")
        # Forge's Main inits Sentry + AWT before CLI dispatch; with no
        # DISPLAY the JVM dies exit-1 with ZERO output (Sentry swallows the
        # crash). Agent/SSH shells are tty — default the display env so
        # headless-launched workers survive.
        env = dict(os.environ)
        if not env.get("DISPLAY"):
            xauth = sorted(Path("/run/user/1000").glob("xauth_*"))
            if xauth:
                env["DISPLAY"] = ":0"
                env["XAUTHORITY"] = str(xauth[0])
            else:
                # no graphical session at all (a relaunch after a reboot,
                # before anyone logs in) — the jar plays headless with AWT told
                # so. Only taken
                # when no display exists, so the normal path is unchanged.
                cmd.insert(cmd.index("-jar"), "-Djava.awt.headless=true")
                print("[harness] no display: workers launched with -Djava.awt.headless=true", flush=True)

        def _die_with_parent() -> None:
            # ADR-0092 teardown cascade: the harness process already dies
            # with the driver (PR_SET_PDEATHSIG in selfplay), but its JVM
            # workers were grandchildren with no such tie — every guard
            # halt / SIGTERM this week orphaned a full worker fleet plus
            # the server's clients. Same prctl on the worker.
            try:
                import ctypes
                import signal as _signal

                ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, _signal.SIGTERM)
            except Exception:
                pass

        return subprocess.Popen(
            cmd, cwd=FORGE_GUI_DIR, stdout=out, stderr=subprocess.STDOUT, env=env,
            preexec_fn=_die_with_parent,
        )

    # ---------- scheduler ----------

    def schedule(self) -> None:
        schedule_group([self])


# ---------- the queue ----------


def schedule_group(runs: "list[Run]", slots: "int | None" = None, caps: "list[int | None] | None" = None) -> None:
    """One queue over one or more runs (M13 Build 2). Every run keeps its own
    dir, manifest, invocation numbers, skips and store; the runs share the
    worker slots, so a run's last games overlap the next run's first and the
    fleet drains once per group where it drained once per run. A game is its
    run's seed base and index and nothing else, so which slot or neighbour
    it gets does not enter it.

    Chunks are issued in list order: the first run with work pending and
    room under its cap takes the free slot. `caps[j]` bounds run j's live
    workers (None = no bound): a run of long, heavy games listed first with
    a small cap starts early and overlaps the rest without holding the
    fleet. A STOP or YIELD file in any member dir applies to the group.
    The systemic-failure count is the group's; the two-crash skip is per
    game, as before. One run alone is the pre-queue scheduler."""
    n = len(runs)
    slots = slots or runs[0].manifest["workers"]
    caps = list(caps) if caps else [None] * n
    solo = n == 1
    pending = [r.remaining_chunks() for r in runs]
    totals = [r.manifest["games"] for r in runs]
    total = sum(totals)
    crash_counts: list[dict[int, int]] = [{} for _ in runs]
    zero_progress_exits = 0  # systemic-failure guard (vs per-game skip rule)
    invs = [max([int(p.name[4:]) for p in r.workers_dir.glob("inv-*")] or [-1]) + 1 for r in runs]
    active: list[tuple[subprocess.Popen, tuple[int, int], int]] = []
    t0 = time.monotonic()
    last_note: "tuple | None" = None

    def _tag(j: int) -> str:
        return "" if solo else f" {runs[j].manifest['purpose']}"

    def _n_done() -> int:
        return sum(len(r.completed()) for r in runs)

    def _stopped() -> bool:
        return any(r.stop_file.exists() for r in runs)

    if solo:
        addrs = bridge_addrs(runs[0].manifest)
        print(
            f"[harness] {_n_done()}/{total} done, "
            f"{len(pending[0])} spans pending, {slots} slots, "
            f"{len(addrs)} bridge address{'es' if len(addrs) != 1 else ''}"
        )
    else:
        print(f"[harness] queue of {n} runs: {_n_done()}/{total} done, "
              f"{sum(len(p) for p in pending)} spans pending, {slots} slots")
        for j, r in enumerate(runs):
            print(f"[harness]   {r.manifest['run_id']}: {totals[j]} games, {len(pending[j])} spans, "
                  f"heap {r.manifest['heap']}" + (f", at most {caps[j]} workers at once" if caps[j] else ""))
    # the GPU yield (gpu_yield.py): a foreign GPU job or the YIELD file
    # gates NEW chunk launches only; active workers finish their chunks
    yielder = GpuYield() if any(r.manifest.get("yield_gpu") for r in runs) else None
    # the yield ledger — cumulative yielded seconds (closed windows + the
    # live one), so a loop can take them OUT of its wall budget instead of
    # charging an arm for a foreign job's hours. A group writes it to its
    # FIRST run's dir only: the loop sums every member's ledger.
    yield_state = {"on": False, "since": 0.0, "closed_s": 0.0, "why": ""}
    ledger = runs[0].yield_state_file

    # the yield guard (11-25): a game that hits the wall game clock while a
    # foreign job held the GPU was slowed, not stalled — it is voided, not
    # recorded as a draw. Nothing here runs on a box that never yields.
    gpu_windows: "list[list[float]]" = []
    gpu_window = {"open": False}
    checked = [set(r.completed()) for r in runs]  # a resumed run's earlier games: their spans are unknown

    def _void_yield_draws() -> None:
        if not gpu_windows:
            return
        now = time.time()
        for r, seen in zip(runs, checked):
            for i, g in r.completed().items():
                if i in seen:
                    continue
                seen.add(i)
                if g.get("draw_clock") and overlaps_yield(g.get("ms", 0), now, [(a, b) for a, b in gpu_windows]):
                    with open(r.dir / "yield-draws.jsonl", "a") as f:
                        f.write(json.dumps({"i": i, "ms": g.get("ms"), "at": round(now, 1)}) + "\n")
                    print(f"[harness] game {i} hit the game clock during a GPU yield -> voided "
                          f"(status {YIELD_DRAW_STATUS})", flush=True)

    def _yielded_s() -> float:
        live = (time.monotonic() - yield_state["since"]) if yield_state["on"] else 0.0
        return yield_state["closed_s"] + live

    def _manual() -> bool:
        return any(r.yield_file.exists() for r in runs)

    def _write_yield_state(on: bool, manual: bool, why: str) -> None:
        ledger.write_text(
            json.dumps({"yielding": on, "manual": manual, "foreign": why,
                        "at": _dt.datetime.now().isoformat(timespec='seconds'),
                        "yielded_s": round(_yielded_s(), 1)}) + "\n"
        )

    floor_mb = mem_floor_mb()
    mem_state = {"hold": False}

    def _yielding() -> bool:
        manual = _manual()
        auto = bool(yielder and yielder.poll())
        # the generation phase's memory guard (M13 Build 2): under the floor no
        # new worker starts; live workers finish and give their heaps back. A
        # hold is a yield in every respect (logged, heartbeated, off the wall).
        avail = mem_available_mb()
        mem = mem_state["hold"] = mem_hold(avail, floor_mb, mem_state["hold"])
        on = manual or auto or mem
        # the yield guard's windows: only a foreign GPU job slows the games in flight
        if auto and not gpu_window["open"]:
            gpu_window["open"] = True
            gpu_windows.append([time.time(), float("inf")])
        elif not auto and gpu_window["open"]:
            gpu_window["open"] = False
            gpu_windows[-1][1] = time.time()
        if on != yield_state["on"]:
            why = ("YIELD file" if manual
                   else f"host memory ({avail:.0f} MB available, floor {floor_mb:.0f} MB)" if mem and not auto
                   else (yielder.describe() if yielder else ""))
            if on:
                yield_state["since"] = time.monotonic()
            else:
                yield_state["closed_s"] += time.monotonic() - yield_state["since"]
            yield_state["on"] = on
            yield_state["why"] = why or "gpu quiet"
            print(f"[harness] {'YIELDING' if on else 'resumed'}: {why or 'gpu quiet'}"
                  f" (yielded {_yielded_s():.0f} s so far)", flush=True)
            _write_yield_state(on, manual, why)
        if on:
            # a yield is idle on purpose — tell the launcher's stall
            # tick so a long foreign GPU job does not raise a false stall
            heartbeat("gpu yield")
        return on

    def _next() -> "int | None":
        live = [0] * n
        for _, _, j in active:
            live[j] += 1
        return next_run([len(p) for p in pending], live, caps)

    while any(pending) or active:
        # evaluated once per tick (not only while chunks are pending) so
        # the YIELDING / resumed transitions land in the log and
        # gpu-yield.json even when every chunk is already out
        yielding = _yielding()
        while len(active) < slots and not yielding and not _stopped():
            j = _next()
            if j is None:
                break
            span = pending[j].pop(0)
            r = runs[j]
            active.append((r.launch_worker(span, invs[j]), span, j))
            n_addr = len(bridge_addrs(r.manifest))
            print(
                f"[harness]{_tag(j)} inv-{invs[j]:04d} <- games [{span[0]},{span[0] + span[1]})"
                + (f" @ {bridge_for(r.manifest, invs[j])}" if n_addr > 1 else "")
            )
            invs[j] += 1
        still = []
        for proc, span, j in active:
            rc = proc.poll()
            if rc is None:
                still.append((proc, span, j))
                continue
            r = runs[j]
            done = set(r.completed()) | r.skipped()
            todo = [i for i in range(span[0], span[0] + span[1]) if i not in done]
            if not todo:
                # a completed span resets the systemic-failure counter too: a
                # reset on a PARTIAL exit alone is one a one-game span can never
                # produce, so three crashed workers anywhere in a run of one-game
                # chunks would read as "3 consecutive" and abort it
                zero_progress_exits = 0
                continue
            if _stopped() and rc == 0:
                continue  # graceful partial exit; remainder re-issued on resume
            if todo[0] == span[0] and len(todo) == span[1]:
                zero_progress_exits += 1
                if zero_progress_exits >= 3:
                    sys.exit(
                        "[harness] 3 consecutive workers exited with ZERO games "
                        "completed — systemic failure (bad paths? server down? "
                        "see workers/inv-*/out.log), aborting instead of skipping"
                    )
            else:
                zero_progress_exits = 0
            first = todo[0]
            crash_counts[j][first] = crash_counts[j].get(first, 0) + 1
            if crash_counts[j][first] >= 2:
                skips = r.skipped() | {first}
                r.skips_file.write_text(json.dumps({"indices": sorted(skips)}))
                print(
                    f"[harness]{_tag(j)} !! game {first} (seed "
                    f"{game_seed(r.manifest['seed_base'], first)}) killed its worker "
                    f"twice -> SKIPPED (free engine-bug repro; see skips.json)"
                )
                todo = todo[1:]
            if todo:
                pending[j].insert(0, (todo[0], todo[-1] - todo[0] + 1))
                print(f"[harness]{_tag(j)} inv rc={rc}; re-queueing [{todo[0]},{todo[-1] + 1})")
        active = still
        if _stopped() and not active:
            print("[harness] paused (STOP present); `resume` to continue")
            return
        if int(time.monotonic() - t0) % 60 < POLL_S:
            _void_yield_draws()
            n_done = _n_done()
            if n_done:
                # the rate excludes yielded time; a live yield is marked on the
                # line, so a yielded harness is not mistaken for a stall
                rate = n_done / max(time.monotonic() - t0 - _yielded_s(), 1) * 3600
                note, last_note = progress_note(n_done, total, rate, yield_state["why"] if yielding else "", last_note)
                if note:
                    print(note, flush=True)
                if yielding:  # the ledger keeps its minute cadence: yielded_s stays current for `status`
                    _write_yield_state(True, _manual(), yield_state["why"])
        time.sleep(POLL_S)
    _void_yield_draws()  # the games that finished after the last progress tick
    if yield_state["on"] or yield_state["closed_s"]:
        if yield_state["on"]:  # close the live window at the run's end
            yield_state["closed_s"] += time.monotonic() - yield_state["since"]
            yield_state["on"] = False
        _write_yield_state(False, _manual(), yield_state["why"])
    for r in runs:
        print(
            f"[harness] run complete{'' if solo else ' ' + r.manifest['run_id']}: "
            f"{len(r.completed())}/{r.manifest['games']} (+{len(r.skipped())} skipped)"
        )
        summarize(r.dir, quiet=not solo)


def next_run(pending: "list[int]", live: "list[int]", caps: "list[int | None]") -> "int | None":
    """The run the next free slot goes to: the first, in list order, with
    chunks pending and fewer live workers than its cap. None = nothing can
    start (all issued, or every run with work is at its cap)."""
    for j, n_pending in enumerate(pending):
        if n_pending and (caps[j] is None or live[j] < caps[j]):
            return j
    return None


# ---------- verbs ----------


def create(a, queue: "dict | None" = None) -> Path:
    """Write a run's dir and pinning manifest without starting it. `queue`
    (a group member) is recorded in the manifest: the group's id, its
    slots, this run's cap."""
    jar = Path(a.jar).resolve() if getattr(a, "jar", None) else _find_jar()
    if not jar.exists():
        sys.exit(f"--jar {jar}: no such file")
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
        if getattr(a, "pool_version", None):
            pool_fields["pool_version"] = a.pool_version
        print(f"[harness] explicit pairs file: {n_lines} pairs x {a.games_per_pair} games")
    if getattr(a, "drill_file", None):
        # M4 D2 drill mode: the run dir carries its own copy (provenance +
        # workers resolve it relative to the run dir, like pairs.txt).
        import shutil

        shutil.copy(a.drill_file, run_dir / "drillfile.txt")
    elif a.pool:
        from anvil.bridge.harness.pairs import (
            latest_pool_manifest,
            pair_schedule,
            write_pairs_file,
        )

        pool_format = getattr(a, "pool_format", "dc")
        pool = latest_pool_manifest(pool_format)
        # the playable build's GUI shares this deck store (worklist "shared user
        # store"): a GUI edit would silently change generation, so gate on content
        from anvil.pool import verify_installed_decks

        problems = verify_installed_decks([d["file"] for d in pool["decks"]], format=pool_format)
        if problems:
            for p in problems[:10]:
                print(f"[harness] deck store: {p}", file=sys.stderr)
            if len(problems) > 10:
                print(f"[harness] ... and {len(problems) - 10} more", file=sys.stderr)
            sys.exit(
                "installed pool decks differ from data/pool/decks — "
                "re-run `uv run python -m anvil.pool install`"
            )
        # schedule covers [0, start+games) so a start-index run's pair mapping
        # (index // gpp) is identical to the run it extends — pair_schedule is
        # prefix-stable in n_pairs, so the shared prefix matches by construction
        n_pairs = -(-(a.start_index + a.games) // a.games_per_pair)  # ceil
        pairs = pair_schedule([d["file"] for d in pool["decks"]], n_pairs, a.seed_base)
        write_pairs_file(run_dir / "pairs.txt", pairs)
        pool_fields = {
            "pool_format": pool_format,
            "pool_version": pool["pool_version"],
            "pairs_file": "pairs.txt",
            "pairs_sha256": _sha256(run_dir / "pairs.txt"),
            "n_pairs": n_pairs,
            "games_per_pair": a.games_per_pair,
        }
        print(
            f"[harness] pool {pool_format}/{pool['pool_version']}: {len(pool['decks'])} decks -> "
            f"{n_pairs} pairs x {a.games_per_pair} games"
        )

    manifest = {
        "run_id": run_id,
        "purpose": a.purpose,
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "fork_commit": _git(FORGE_DIR, "rev-parse", "HEAD"),
        "fork_dirty": bool(_git(FORGE_DIR, "status", "--porcelain")),
        "anvil_commit": _git(Path(__file__).parents[3], "rev-parse", "HEAD"),
        "jar": str(jar),
        "jar_sha256": _sha256(jar),
        "protocol_version": PROTOCOL_VERSION,
        "decks": a.decks,
        "format": a.format,
        **pool_fields,
        "seed_base": a.seed_base,
        "games": a.games,
        "chunk": a.chunk or default_chunk(a.games, 12 if a.colocated else a.workers),
        "start_index": a.start_index,
        "workers": 12 if a.colocated else a.workers,
        # ExitOnOutOfMemoryError: a batch worker must die (chunk re-issue
        # covers it), not limp — an OOM that escapes the game-loop catch
        # reaches Forge's GUI bug-report dialog and wedges a headless
        # worker forever. The fork also
        # installs a headless uncaught handler; this is the JVM-level belt.
        "heap": getattr(a, "heap", None) or "2g",
        "jvm_opts": [
            "-XX:ActiveProcessorCount=2",
            "-XX:+ExitOnOutOfMemoryError",
            "-Dapple.awt.UIElement=true",  # macOS: no Dock icon per worker (Talor, #5); ignored elsewhere
        ],
        "bridge": a.bridge,
        "yield_gpu": bool(
            getattr(a, "yield_gpu", True)
            and "grpc:" in str(a.bridge)
            and not os.environ.get("ANVIL_NO_GPU_YIELD")
        ),
        "tags": a.tags,
        "nice": not a.calibrated,
        "obs": a.obs,
        "obs_schema": OBS_SCHEMA_VERSION if a.obs else None,
        "census": getattr(a, "census", False),
        "paytelemetry": getattr(a, "paytelemetry", False),
        "bridge_seats": getattr(a, "bridge_seats", None),
        "reask": getattr(a, "reask", False),
        "rollout_k": getattr(a, "rollout_k", None),
        "rollout_points": getattr(a, "rollout_points", None),
        "drill_file": "drillfile.txt" if getattr(a, "drill_file", None) else None,
        "drill_source": str(a.drill_file) if getattr(a, "drill_file", None) else None,
        "drill_stop": getattr(a, "drill_stop", False),
        "fork_obs": getattr(a, "fork_obs", False),
        "fork_ns": getattr(a, "fork_ns", None),
        "force_branch": getattr(a, "force_branch", False),
        "force_seq": getattr(a, "force_seq", None),
        "seq_arms": getattr(a, "seq_arms", None),
        # M10 reset Fork 3: inline certification horizon (None = off)
        "certify_horizon": getattr(a, "certify", None),
        # verbatim AnvilRun flags + per-worker labels
        "forge_args": (getattr(a, "forge_args", None) or "").split() or None,
        "labels": getattr(a, "labels", False),
        # The answer tape (forced-decision replay, scripts/tape_replay.py): a
        # served run with obs writes it into its frames. Recording only.
        "tape": bool(a.obs and "grpc:" in str(a.bridge) and not getattr(a, "no_tape", False)),
    }
    if queue:
        manifest["queue"] = queue
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"[harness] run {run_id}: {a.games} games, w={manifest['workers']}, "
        f"bridge={a.bridge}, seed_base={a.seed_base}"
    )
    if a.calibrated:
        print("[harness] CALIBRATED run: workers at normal priority — keep the box quiet")
    return run_dir


def launch(a) -> Path:
    run_dir = create(a)
    Run(run_dir).schedule()
    return run_dir


def launch_group(members: "list[tuple[object, int | None]]", slots: int, group_id: str) -> "list[Path]":
    """Create every member run, then play them through one queue.
    `members` = (parsed launch args, cap or None) in queue order."""
    purposes = [a.purpose for a, _ in members]
    if len(set(purposes)) != len(purposes):
        sys.exit(f"launch-group: purposes must differ, got {purposes}")
    dirs = [create(a, queue={"group": group_id, "slots": slots, "max_active": cap, "position": j})
            for j, (a, cap) in enumerate(members)]
    (RUNS_DIR / "queues").mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / "queues" / f"{group_id}.queue.json").write_text(
        json.dumps({"group": group_id, "slots": slots, "runs": [d.name for d in dirs]}, indent=1) + "\n")
    schedule_group([Run(d) for d in dirs], slots, [cap for _, cap in members])
    return dirs


def resume(run_dir: Path) -> None:
    """Resume a run; a group member resumes its whole group, on the
    group's slots and caps."""
    r = Run(run_dir)
    q = r.manifest.get("queue")
    runs = [r]
    if q:
        rec = json.loads((RUNS_DIR / "queues" / f"{q['group']}.queue.json").read_text())
        runs = [Run(RUNS_DIR / name) for name in rec["runs"]]
    for m in runs:
        if m.stop_file.exists():
            m.stop_file.unlink()
    if q:
        schedule_group(runs, q["slots"], [m.manifest["queue"]["max_active"] for m in runs])
    else:
        r.schedule()


def pause(run_dir: Path) -> None:
    Run(run_dir).stop_file.touch()
    print("[harness] STOP written; workers finish their current game and exit")


def status(run_dir: Path) -> None:
    r = Run(run_dir)
    done = r.completed()
    m = r.manifest
    state = (
        "paused"
        if r.stop_file.exists()
        else "complete"
        if len(done) + len(r.skipped()) >= m["games"]
        else "in progress"
    )
    print(f"{m['run_id']}: {len(done)}/{m['games']} done, {len(r.skipped())} skipped [{state}]")
    if r.yield_state_file.exists():
        try:
            ys = json.loads(r.yield_state_file.read_text())
            if ys.get("yielding"):
                print(f"  YIELDING since {ys.get('at')}: {ys.get('foreign')}")
        except json.JSONDecodeError:
            pass
    if done:
        ms = sorted(g["ms"] for g in done.values())
        print(
            f"  median {ms[len(ms) // 2] / 1000:.1f}s/game, "
            f"draws {sum(1 for g in done.values() if g['status'] != 'won')}"
        )


def replay(run_dir: Path, index: int) -> None:
    r = Run(run_dir)
    m = r.manifest
    print(
        f"[harness] replaying game {index} "
        f"(seed {game_seed(m['seed_base'], index)}) of {m['run_id']}"
    )
    r._verify_jar()
    cmd = [
        "java",
        f"-Xms{m['heap']}",
        f"-Xmx{m['heap']}",
        *m["jvm_opts"],
        "-jar",
        m["jar"],
        "anvil",
        *r._deck_args(),
        "-f",
        m["format"],
        "-range",
        str(index),
        "1",
        "-seedbase",
        str(m["seed_base"]),
        "-b",
        m["bridge"],
        *_provenance_args(m),
    ]
    if m.get("tags"):
        cmd += ["-tags", m["tags"]]
    if m.get("obs"):
        # The priority-option scan perturbs which trajectory a seed plays
        # (measured: 14/20 identical without it) — a replay must
        # match the original run's logging configuration to reproduce it.
        # The replay's own observation output is a throwaway.
        cmd += ["-obs", str(run_dir / f"replay-{index}-obs.zst")]
    subprocess.run(cmd, cwd=FORGE_GUI_DIR, check=False)


def summarize(run_dir: Path, quiet: bool = False) -> None:
    r = Run(run_dir)
    voided = yield_draws(r.dir)
    done = {i: void_yield_draws(g, voided) for i, g in r.completed().items()}
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
        "games": len(games),
        "skipped": sorted(r.skipped()),
        "decisive": sum(1 for g in games if g["status"] == "won"),
        "draw_clock_hits": sum(1 for g in games if g.get("draw_clock")),
        "statuses": {
            s: sum(1 for g in games if g["status"] == s) for s in {g["status"] for g in games}
        },
        "turns_median": sorted(g["turns"] for g in games)[len(games) // 2] if games else 0,
        "ms_median": ms[len(ms) // 2],
        "ms_p90": ms[int(len(ms) * 0.9)] if games else 0,
        "ms_max": ms[-1],
        "game_hours_played": sum(g["ms"] for g in games) / 3.6e6,
        "obs_bytes": obs_bytes,
        "obs_kb_per_game": round(obs_bytes / max(len(games), 1) / 1e3, 1),
        "slowest_games": [
            {k: g.get(k) for k in ("i", "seed", "ms", "turns", "decks")} for g in slowest
        ],
    }
    (r.dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not quiet:
        print(json.dumps(summary, indent=2))
