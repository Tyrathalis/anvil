"""obs_diff — the obs-diff gate (2026-08-11 protocol; a standing instrument
since M12 Build 0, ADR-0102): compare two same-seed stores window by window
on the recorded masks and answers.

Usage:
    uv run python scripts/obs_diff.py <store_a> <store_b> [--max-games N] [--dump-first]

Per game (same index in both stores): the sequence of decision records is
compared as (s, m, t, p, option labels, chosen option index); the first
divergent window is reported. A cache/filter whose OUTPUT is in the recorded
stream is equivalence-checked exactly and cheaply — the 08-11 finding.
Exit status 1 when any game diverges (a gate, not a report).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from anvil.store.trajectories import TrajectoryStore


def _key(d: dict) -> tuple:
    opts = d.get("opts")
    labels = tuple((o.get("e"), o.get("sa"), o.get("kind")) for o in opts) if opts else None
    ret = d.get("ret")
    return (d.get("s"), d.get("m"), d.get("t"), d.get("p"), labels, d.get("oi"),
            json.dumps(ret, sort_keys=True) if isinstance(ret, (dict, list)) else ret)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("store_a")
    ap.add_argument("store_b")
    ap.add_argument("--max-games", type=int, default=0)
    ap.add_argument("--dump-first", action="store_true", help="print the first divergent window pair")
    a = ap.parse_args()
    sa, sb = TrajectoryStore(Path(a.store_a)), TrajectoryStore(Path(a.store_b))
    common = sorted(set(sa.game_indices()) & set(sb.game_indices()))
    if a.max_games:
        common = common[: a.max_games]
    games = identical = 0
    windows = windows_same = 0
    divergent: list[tuple[int, int, str]] = []
    for g in common:
        try:
            ta, tb = sa.game(g), sb.game(g)
        except Exception as e:  # noqa: BLE001
            print(f"[obs_diff] game {g}: undecodable ({e})", file=sys.stderr)
            continue
        games += 1
        ka = [_key(d) for d in ta.decisions]
        kb = [_key(d) for d in tb.decisions]
        n = min(len(ka), len(kb))
        div = next((i for i in range(n) if ka[i] != kb[i]), None)
        if div is None and len(ka) == len(kb):
            identical += 1
            windows += len(ka)
            windows_same += len(ka)
            continue
        i = div if div is not None else n
        windows += max(len(ka), len(kb))
        windows_same += i
        da = ta.decisions[i] if i < len(ta.decisions) else {}
        db = tb.decisions[i] if i < len(tb.decisions) else {}
        why = f"t{da.get('t', db.get('t'))} {da.get('m', db.get('m'))} s{da.get('s', db.get('s'))}"
        divergent.append((g, i, why))
        if a.dump_first and len(divergent) == 1:
            print(json.dumps({"a": {k: v for k, v in da.items() if k != "obs"},
                              "b": {k: v for k, v in db.items() if k != "obs"}}, indent=1)[:4000])
    print(f"games compared {games}  identical {identical}  divergent {len(divergent)}")
    print(f"windows {windows}  identical-prefix {windows_same}  ({windows_same / max(windows, 1):.4f})")
    for g, i, why in divergent[:20]:
        print(f"  game {g}: first divergence at record {i} ({why})")
    return 1 if divergent else 0


if __name__ == "__main__":
    sys.exit(main())
