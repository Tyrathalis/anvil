"""A synthetic foreign GPU job (09-21): saturates the card's SMs for --seconds so a
run's GPU yield + the bridge deadline can be read under contention without a
real ComfyUI workflow. Run it under `setsid` so its session id differs from the
run's (gpu_yield.py's "foreign" = a compute process outside our session with
SM >= 20% or >= 1 GiB)."""

from __future__ import annotations

import argparse
import time

import torch


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=360)
    ap.add_argument("--size", type=int, default=8192)
    ap.add_argument("--gb", type=float, default=4.0, help="a resident allocation so fb counts too")
    a = ap.parse_args()
    dev = torch.device("cuda")
    hold = torch.empty(int(a.gb * 2**30 // 4), dtype=torch.float32, device=dev)  # noqa: F841
    x = torch.randn(a.size, a.size, device=dev, dtype=torch.bfloat16)
    t0 = time.time()
    n = 0
    while time.time() - t0 < a.seconds:
        x = (x @ x).tanh()
        n += 1
        if n % 50 == 0:
            torch.cuda.synchronize()
            print(f"[burner] {time.time() - t0:.0f} s, {n} matmuls", flush=True)
    torch.cuda.synchronize()
    print(f"[burner] done: {n} matmuls in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
