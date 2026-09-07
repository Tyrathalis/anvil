"""forkcheck compare — the ADR-0025 exemption proof read: per-seed mainTraceHash
equality between a candidate forkcheck run and the baseline (default: the
08-21 m9boundary run, the standing seed set 20260703+500).

Usage: uv run python scripts/forkcheck/compare.py <candidate_dir> [--baseline <dir>]
Prints identical / differing counts, the differing seeds, and the fork-fidelity
status mix of the candidate; exit 0 always (the verdict is the reader's — a
miss is PASS only if it replays to the baseline hash on the same jar).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

BASE = Path("data/forkcheck/run-20260821-m9boundary")


def load(d: Path) -> dict[int, dict]:
    out = {}
    for line in open(d / "results.jsonl"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        out[r["seed"]] = r
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--baseline", default=str(BASE))
    a = ap.parse_args()
    c, b = load(Path(a.candidate)), load(Path(a.baseline))
    common = sorted(set(c) & set(b))
    same = [s for s in common if c[s]["mainTraceHash"] == b[s]["mainTraceHash"]]
    diff = [s for s in common if s not in set(same)]
    print(f"candidate {len(c)} rows, baseline {len(b)} rows, common {len(common)}")
    print(f"main-trace hashes identical: {len(same)}/{len(common)}")
    for s in diff:
        print(f"  DIFF seed {s}: {c[s]['mainTraceHash']} vs baseline {b[s]['mainTraceHash']} "
              f"(turns {c[s]['mainTurns']} vs {b[s]['mainTurns']})")
    st = Counter(r["status"] for r in c.values())
    print(f"fork fidelity (candidate): {dict(st)}")
    bst = Counter(r["status"] for r in b.values())
    print(f"fork fidelity (baseline):  {dict(bst)}")


if __name__ == "__main__":
    main()
