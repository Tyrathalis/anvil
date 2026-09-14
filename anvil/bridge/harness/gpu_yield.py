"""GPU yield (the crude autoscaler, 2026-09-14; user pin).

When a GPU compute process from OUTSIDE the run's own session takes the
card (a training run, ComfyUI generating), the scheduler stops launching
new chunks and lets the active ones finish; it resumes once the card has
been foreign-free for a while. Pausing the model server itself would trip
the bridge deadline and poison every in-flight game, so the launch gate is
the only safe lever. A `YIELD` file in the run dir is the manual form of
the same gate (unlike STOP, workers are not asked to exit).

"Foreign" = a compute-type process (`nvidia-smi pmon` type C or C+G) whose
session id is not ours AND that is actually using the card: framebuffer
>= 1 GiB or SM >= 20%. Idle CUDA contexts (a desktop app, an idle ComfyUI
at 386 MiB) do not count. Our own session covers the servers the launcher
started and the loop's trainer between generations.

Hysteresis: foreign present for on_s seconds -> yielding; absent for
off_s seconds -> resumed. Sampled at most every sample_s seconds.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field


@dataclass
class GpuProc:
    pid: int
    kind: str
    sm: float
    fb_mb: float
    name: str


def sample_pmon(timeout: float = 10.0) -> list[GpuProc] | None:
    """`nvidia-smi pmon -c 1 -s um` parsed; None when nvidia-smi is unavailable."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "pmon", "-c", "1", "-s", "um"],
            capture_output=True, text=True, timeout=timeout, check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_pmon(out)


def parse_pmon(text: str) -> list[GpuProc]:
    """Column names come from pmon's own `# gpu pid type sm ... fb ... command`
    header (the column set varies by driver: jpg/ofa/ccpm appear on newer
    ones), so fields are indexed by name."""
    procs: list[GpuProc] = []
    cols_by_name: dict[str, int] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            names = line.lstrip("# ").split()
            if "pid" in names and "fb" in names:
                cols_by_name = {n: i for i, n in enumerate(names)}
            continue
        if not cols_by_name:
            continue
        cols = line.split()
        if len(cols) < len(cols_by_name):
            continue
        try:
            pid = int(cols[cols_by_name["pid"]])
        except ValueError:
            continue
        procs.append(
            GpuProc(
                pid=pid,
                kind=cols[cols_by_name.get("type", 2)],
                sm=_num(cols[cols_by_name.get("sm", 3)]),
                fb_mb=_num(cols[cols_by_name["fb"]]),
                name=" ".join(cols[cols_by_name.get("command", len(cols) - 1) :]),
            )
        )
    return procs


def _num(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        return 0.0


def _sid(pid: int) -> int | None:
    try:
        return os.getsid(pid)
    except (ProcessLookupError, PermissionError, OSError):
        return None


def foreign_procs(
    procs: list[GpuProc], own_sid: int, fb_mb: float = 1024.0, sm_pct: float = 20.0
) -> list[GpuProc]:
    out = []
    for p in procs:
        if "C" not in p.kind:
            continue
        if p.fb_mb < fb_mb and p.sm < sm_pct:
            continue
        if _sid(p.pid) == own_sid:
            continue
        out.append(p)
    return out


@dataclass
class GpuYield:
    own_sid: int = field(default_factory=lambda: os.getsid(0))
    on_s: float = 60.0
    off_s: float = 120.0
    sample_s: float = 30.0
    fb_mb: float = 1024.0
    sm_pct: float = 20.0
    sampler: "callable" = sample_pmon
    clock: "callable" = time.monotonic
    yielding: bool = False
    foreign: list = field(default_factory=list)
    _since: float | None = None  # when the current foreign presence/absence began
    _last_sample: float = -1e9
    _present: bool = False

    def poll(self) -> bool:
        """Advance the state machine; returns True while yielding."""
        now = self.clock()
        if now - self._last_sample < self.sample_s:
            return self.yielding
        self._last_sample = now
        procs = self.sampler()
        if procs is None:
            return self.yielding  # no nvidia-smi: never yield
        self.foreign = foreign_procs(procs, self.own_sid, self.fb_mb, self.sm_pct)
        present = bool(self.foreign)
        if present != self._present or self._since is None:
            self._present = present
            self._since = now
        held = now - self._since
        if present and not self.yielding and held >= self.on_s:
            self.yielding = True
        elif not present and self.yielding and held >= self.off_s:
            self.yielding = False
        return self.yielding

    def describe(self) -> str:
        return ", ".join(f"{p.name}[{p.pid}] {p.fb_mb:.0f} MB sm {p.sm:.0f}%" for p in self.foreign)
