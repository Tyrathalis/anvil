"""Player-target audit (09-21, ADR-0116) — the CLI over anvil.evals.player_targets.
Usage: player_target_audit.py <harness run dir>... [--json out]"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from anvil.evals.player_targets import audit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    r = audit(a.dirs)
    print(json.dumps(r, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
