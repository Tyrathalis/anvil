"""Model-server fleet (the throughput week, 2026-09-14; m12-plan record 09-10).

One model server is one Python process: the gRPC stream threads featurize
and the batcher thread forwards, all under one GIL. The h2 relabel found the
ceiling — 16 workers of network-played search copies pinned one server at
110% CPU with the GPU at 52% and the workers 30% idle on the bridge. The
lever the harness lacked is N servers: `anvil.bridge.server --servers N`
runs this supervisor, which spawns N children on consecutive ports
(port, port+1, ...), and the harness takes the matching comma list
(`--bridge grpc:localhost:P,grpc:localhost:P+1`) and assigns chunks
round-robin. The Java worker is untouched (one address per worker).

Per-child outputs: every path-valued output flag (`--mu-out`,
`--drill-mu-out`, `--bind-trace`, `--counts-out`) gets a `.sI` suffix for
child I; at shutdown the supervisor APPENDS the jsonl parts to the base path
(the "a fresh server appends" contract selfplay's partial resume relies on)
and sums the counts parts into the base counts file. Consumers see one file.

Readiness: children 1..N-1 start first and open their ports; child 0 (the
base port) starts last — so a launcher that polls only the base port (the
shell chains) sees the whole fleet up.
"""

from __future__ import annotations

import json
import math
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

PER_SERVER_WORKERS = 8  # the measured pin: one server keeps ≈ 8 workers fed
SPLIT_OUTPUTS = ("--mu-out", "--drill-mu-out", "--bind-trace", "--counts-out")


def servers_for(workers: int, servers: int = 0) -> int:
    """N servers for a worker count: an explicit N > 0, else ceil(workers / 8)."""
    if servers and servers > 0:
        return int(servers)
    return max(1, math.ceil(max(int(workers), 1) / PER_SERVER_WORKERS))


def bridge_addrs(port: int, servers: int = 1, host: str = "localhost") -> str:
    """The harness `--bridge` value for a fleet on consecutive ports."""
    return ",".join(f"grpc:{host}:{port + i}" for i in range(max(int(servers), 1)))


def _flag_value(argv: list[str], flag: str) -> str | None:
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a[len(flag) + 1 :]
    return None


def _part(path: str, i: int) -> str:
    return f"{path}.s{i}"


def child_argv(argv: list[str], i: int, port: int) -> list[str]:
    """Child I's argv: `--servers` dropped, `--port` = port + I, every
    path-valued output flag suffixed `.sI`."""
    out: list[str] = []
    k = 0
    while k < len(argv):
        a = argv[k]
        if a == "--servers":
            k += 2
            continue
        if a.startswith("--servers="):
            k += 1
            continue
        if a == "--port":
            out += ["--port", str(port + i)]
            k += 2
            continue
        if a.startswith("--port="):
            out.append(f"--port={port + i}")
            k += 1
            continue
        if a in SPLIT_OUTPUTS and k + 1 < len(argv):
            out += [a, _part(argv[k + 1], i)]
            k += 2
            continue
        split = next((f for f in SPLIT_OUTPUTS if a.startswith(f + "=")), None)
        if split:
            out.append(f"{split}={_part(a[len(split) + 1 :], i)}")
            k += 1
            continue
        out.append(a)
        k += 1
    return out


def output_paths(argv: list[str]) -> dict[str, str]:
    """Base output paths the supervisor merges: flag -> path. The counts
    file follows the server's own default (beside --mu-out) when unnamed."""
    paths = {f: v for f in SPLIT_OUTPUTS if (v := _flag_value(argv, f)) is not None}
    if "--counts-out" not in paths and "--mu-out" in paths:
        paths["--counts-out"] = paths["--mu-out"] + ".counts.json"
    return paths


def _merge_counts(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict):
            dst.setdefault(k, {})
            if isinstance(dst[k], dict):
                _merge_counts(dst[k], v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            dst[k] = dst.get(k, 0) + v
        else:
            dst.setdefault(k, v)


def merge_outputs(argv: list[str], n: int) -> dict[str, int]:
    """Append every child's jsonl part to its base path and sum the counts
    parts into the base counts file; the parts are removed. Returns the
    number of parts folded per base path."""
    folded: dict[str, int] = {}
    for flag, base in output_paths(argv).items():
        parts = []
        for i in range(n):
            if flag == "--counts-out" and _flag_value(argv, "--counts-out") is None:
                # the child's default: beside ITS mu part
                p = Path(_part(_flag_value(argv, "--mu-out") or "", i) + ".counts.json")
            else:
                p = Path(_part(base, i))
            if p.exists():
                parts.append(p)
        if not parts:
            continue
        bp = Path(base)
        bp.parent.mkdir(parents=True, exist_ok=True)
        if flag == "--counts-out":
            merged: dict = {}
            if bp.exists():
                try:
                    merged = json.loads(bp.read_text())
                except json.JSONDecodeError:
                    merged = {}
            for p in parts:
                try:
                    _merge_counts(merged, json.loads(p.read_text()))
                except json.JSONDecodeError:
                    continue
            merged["servers"] = n
            bp.write_text(json.dumps(merged, indent=1) + "\n")
        else:
            with open(bp, "ab") as f:
                for p in parts:
                    data = p.read_bytes()
                    if data and not data.endswith(b"\n"):
                        data += b"\n"
                    f.write(data)
        for p in parts:
            p.unlink()
        folded[base] = len(parts)
    return folded


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def wait_ports(port: int, servers: int, timeout: float = 300.0) -> None:
    """Block until every port of the fleet accepts a connection."""
    t0 = time.monotonic()
    for p in range(port, port + max(int(servers), 1)):
        while not _port_open(p):
            if time.monotonic() - t0 > timeout:
                raise TimeoutError(f"server never opened port {p}")
            time.sleep(1)


def supervise(argv: list[str], n: int, port: int, stagger_ready: bool = True) -> int:
    """Run N children of `python -m anvil.bridge.server <argv>` and merge their
    outputs at shutdown. SIGTERM/SIGINT fan out to the children (each
    converges on its own stats + counts dump). An unexpected child exit
    terminates the fleet (rc 1) — a half fleet would strand every chunk
    assigned to the dead port."""
    n = max(int(n), 1)
    # clear stale parts from an interrupted attempt (the base files keep
    # whatever an earlier fleet already folded in — the append contract)
    for flag, base in output_paths(argv).items():
        for i in range(n):
            Path(_part(base, i)).unlink(missing_ok=True)
            if flag == "--mu-out":
                Path(_part(base, i) + ".counts.json").unlink(missing_ok=True)
    children: dict[int, subprocess.Popen] = {}
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    order = list(range(n - 1, -1, -1)) if stagger_ready else list(range(n))
    stopping = {"flag": False}

    def _term(_sig, _frm):
        stopping["flag"] = True
        for c in children.values():
            if c.poll() is None:
                c.send_signal(signal.SIGTERM)

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    rc = 0
    try:
        for i in order:
            cmd = [sys.executable, "-m", "anvil.bridge.server", *child_argv(argv, i, port)]
            children[i] = subprocess.Popen(cmd, env=env)
            print(f"[fleet] server s{i} pid {children[i].pid} port {port + i}", flush=True)
            if stagger_ready and i != 0:
                while not _port_open(port + i):
                    if children[i].poll() is not None:
                        print(f"[fleet] server s{i} exited rc={children[i].returncode} before opening", flush=True)
                        rc = 1
                        raise KeyboardInterrupt
                    time.sleep(1)
        print(f"[fleet] {n} servers on ports {port}..{port + n - 1}", flush=True)
        while not stopping["flag"]:
            for i, c in children.items():
                r = c.poll()
                if r is not None:
                    print(f"[fleet] server s{i} exited rc={r} — stopping the fleet", flush=True)
                    rc = 1
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for c in children.values():
            if c.poll() is None:
                c.send_signal(signal.SIGTERM)
        for c in children.values():
            try:
                c.wait(timeout=40)
            except subprocess.TimeoutExpired:
                c.kill()
        folded = merge_outputs(argv, n)
        for base, k in folded.items():
            print(f"[fleet] merged {k} parts -> {base}", flush=True)
    return rc
