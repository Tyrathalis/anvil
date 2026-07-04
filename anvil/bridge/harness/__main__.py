import argparse
import secrets
from pathlib import Path

from anvil.bridge.harness import orchestrator as orc


def main() -> None:
    ap = argparse.ArgumentParser(prog="anvil.bridge.harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    la = sub.add_parser("launch")
    la.add_argument("--decks", nargs=2, required=True)
    la.add_argument("--games", type=int, required=True)
    la.add_argument("--format", default="Commander")
    la.add_argument("--workers", type=int, default=16)
    la.add_argument("--colocated", action="store_true")
    la.add_argument("--bridge", default="local-random")
    la.add_argument("--tags", default="")
    la.add_argument("--purpose", default="run")
    la.add_argument("--seed-base", type=int, default=None)
    la.add_argument("--chunk", type=int, default=200)
    la.add_argument("--calibrated", action="store_true")
    la.add_argument("--obs", action="store_true",
                    help="write observation logs (obs.zst per worker; observation-schema-v1)")

    for name in ("resume", "pause", "status", "summarize"):
        p = sub.add_parser(name)
        p.add_argument("run_dir", type=Path)

    rp = sub.add_parser("replay")
    rp.add_argument("run_dir", type=Path)
    rp.add_argument("index", type=int)

    a = ap.parse_args()
    if a.cmd == "launch":
        if a.seed_base is None:
            a.seed_base = secrets.randbelow(1 << 62)
        orc.launch(a)
    elif a.cmd == "resume":
        orc.resume(a.run_dir)
    elif a.cmd == "pause":
        orc.pause(a.run_dir)
    elif a.cmd == "status":
        orc.status(a.run_dir)
    elif a.cmd == "replay":
        orc.replay(a.run_dir, a.index)
    elif a.cmd == "summarize":
        orc.summarize(a.run_dir)


if __name__ == "__main__":
    main()
