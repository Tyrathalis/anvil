"""τ-strength curve (M3 D2): winrate arms vs the heuristic at sampled
temperatures on one checkpoint — prices the sampling tax the run-6
reward-split diagnosis identified (heur-half τ=1 sampled play read
0.5064 ± 0.0081 where the same ckpt's argmax arms read ~0.53-0.54).

Each τ arm = two seat-mirrored harness runs against the standing D8/D5
pairs file at the standing arms seed base, so every arm is paired-seed
comparable with the in-run argmax arms (which supply the τ→0 point for
free — no argmax arm is re-run here). Serve is the normal sampling path
(--sample --temperature τ, mu.jsonl written and kept for diagnostics);
noise seeds derive from (game_seed, dec seq), so all τ arms share the
same underlying uniforms — common-random-numbers across the curve.

Usage:
  uv run python scripts/tau_curve.py \
      --ckpt data/training/d6-run6/iter-019/train/last.pt \
      --taus 0.3,0.5,0.8,1.0 \
      --out data/runs/tau-curve-run6i19
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from anvil.training.selfplay import RUNS_DIR, _run, _start_server, _stop_server


def main() -> None:
    ap = argparse.ArgumentParser(description="τ-strength winrate curve")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--taus", default="0.3,0.5,0.8,1.0")
    ap.add_argument("--games", type=int, default=200, help="games per seat arm")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--port", type=int, default=50064)
    ap.add_argument("--pairs-file",
                    default="data/runs/d5arm-d0-s0-20260714-143546/pairs.txt")
    ap.add_argument("--seed-base", type=int, default=20260710)
    ap.add_argument("--reask", action="store_true", default=True)
    ap.add_argument("--out", required=True,
                    help="output stem: <out>-report.json + per-τ logs/mu")
    a = ap.parse_args()

    out_stem = Path(a.out)
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    arms: list[tuple[str, list[str]]] = []

    for tau_s in a.taus.split(","):
        tau = float(tau_s)
        tag = tau_s.replace(".", "")
        mu_out = Path(f"{a.out}-mu-t{tag}.jsonl")
        server = _start_server(a.ckpt, a.port, Path(f"{a.out}-server-t{tag}.log"),
                               sample=True, mu_out=mu_out, temperature=tau)
        arm_dirs: list[str] = []
        try:
            for seat in (0, 1):
                purpose = f"taucurve-t{tag}-s{seat}"
                before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
                cmd = [sys.executable, "-m", "anvil.bridge.harness", "launch",
                       "--pairs-file", a.pairs_file, "--games", str(a.games),
                       "--workers", str(a.workers), "--chunk", str(a.chunk),
                       "--bridge", f"grpc:localhost:{a.port}",
                       "--census", "--obs", "--purpose", purpose,
                       "--seed-base", str(a.seed_base),
                       "--bridge-seats", str(seat)]
                if a.reask:
                    cmd.append("--reask")
                _run(cmd)
                new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
                if len(new) != 1:
                    raise RuntimeError(f"expected one new run dir, got {new}")
                arm_dirs.append(new.pop())
        finally:
            _stop_server(server)
        arms.append((tau_s, arm_dirs))
        print(f"[tau_curve] τ={tau_s} arm complete: {arm_dirs}")

    report_cmd = [sys.executable, "scripts/arms_report.py"]
    for tau_s, dirs in arms:
        report_cmd += ["--arm", f"tau{tau_s}={','.join(dirs)}"]
    report_cmd += ["--out", f"{a.out}-report.json"]
    _run(report_cmd)

    rep = json.loads(Path(f"{a.out}-report.json").read_text())
    for name, arm in rep.items():
        if isinstance(arm, dict) and "winrate" in arm:
            print(f"[tau_curve] {name}: winrate {arm['winrate']:.4f} "
                  f"± {arm['se']:.4f} veto {arm.get('veto_rate', 0):.3f} "
                  f"first_veto {arm.get('first_veto_rate', 0):.3f}")


if __name__ == "__main__":
    main()
