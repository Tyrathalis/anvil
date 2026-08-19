"""VRAM cotenancy elasticity helpers (task #12 + the 2026-08-18 extension).

Scale-to-zero (user directive, the run17 iter-8 ComfyUI incident): when
batch/seg halving hits its floor and even a single-example forward
cannot fit, the batch dimension has nothing left to give — the fixed
footprint (weights + frozen embedding table + optimizer state + CUDA
context, ~7.8 GB for the critic finetune) dominates, so the learner
PARKS and polls free VRAM instead of crashing the driver. The watchd
stall alert (75m) doubles as the page if a park outlives it.

Scale-back-up: a free-VRAM tier probe (the driver seg-autotune's
run-3-incident thresholds) restores segment size when the cotenant
releases — replacing rl.py's original sticks-for-the-run policy.
"""

from __future__ import annotations

import time

import torch


def seg_tier(free_mb_now: float) -> int:
    """The driver seg-autotune tiers (selfplay.py, run-3 thresholds)."""
    return 256 if free_mb_now >= 16000 else 128 if free_mb_now >= 9000 else 64


def free_mb() -> float:
    free, _total = torch.cuda.mem_get_info()
    return free / 2**20


def park_for_cotenant(who: str, min_free: float = 9000) -> bool:
    """Floor-OOM triage. True iff the OOM looks like genuine cotenant
    scarcity AND we parked until recovery — the caller retries. False =
    VRAM is free (or CUDA absent): parking cannot fix what scarcity did
    not cause, the caller re-raises — fragmentation, a stub, or a real
    bug (the free-but-OOM spin caught by the legacy floor tests at the
    M8-close merge gate). Preserves the original raise contract on CPU
    and on healthy cards."""
    if not torch.cuda.is_available():
        return False
    torch.cuda.empty_cache()
    if free_mb() >= min_free:
        return False
    wait_for_vram(who, min_free_mb=min_free)
    return True


def wait_for_vram(
    who: str,
    min_free_mb: float = 9000,
    poll_s: float = 30,
    _free=None,
    _sleep=time.sleep,
    _notify=None,
) -> int:
    """Park until free VRAM >= min_free_mb; returns polls waited.

    Default floor 9000 MB = the seg-128 autotune tier — comfortably above
    the critic finetune's ~7.8 GB fixed footprint. Notifies once on
    entering the parked state. _free/_sleep/_notify are test seams.
    """
    f = _free or free_mb
    cur = f()
    if cur >= min_free_mb:
        return 0
    notify = _notify
    if notify is None:
        try:
            from anvil.training.notify import notify as notify_fn

            notify = notify_fn
        except Exception:
            notify = lambda *a: None  # noqa: E731
    notify(
        "vram starved",
        f"{who} parked: {cur:.0f} MB free < {min_free_mb:.0f}; polling every {poll_s}s",
    )
    n = 0
    while cur < min_free_mb:
        _sleep(poll_s)
        n += 1
        torch.cuda.empty_cache()
        cur = f()
        print(
            f"[vram] {who} parked ({cur:.0f} MB free, want {min_free_mb:.0f}) — poll {n}",
            flush=True,
        )
    print(f"[vram] {who} resuming ({cur:.0f} MB free after {n} polls)", flush=True)
    return n
