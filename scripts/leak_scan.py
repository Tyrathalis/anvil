"""Scan stored games for mana a search copy leaked into the live game (ADR-0133).

At a searched window the search scans the seat's options, plays its copies, and then the seat is
asked. Some scans fire a callback that is recorded with the game's state (an optional cost, a cost
reducer to choose). The seat's own scan fires the same callback again after the copies. Nothing
in the game happens between those records, so a mana pool that grew between the first of them and
the seat's ask grew during the copies.

This sees only the windows whose scan fired a recorded callback, so its count is a floor on the
leaks and its rate is per such window. A store played without search is the control: the same
record pattern, no copies, and the count must be zero.

    uv run python scripts/leak_scan.py data/trajectories/<store> [<store> ...] [--max-games N]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import zstandard

# Callbacks a cost or option scan fires; answering one changes nothing in the game.
PROBES = {"chooseOptionalCosts", "chooseSingleStaticAbility"}
MAX_RLEN = 300 << 20  # skip the rare huge frame: the scan holds one record at a time, but slowly


def frames(root: Path):
    """(game index, a line iterator over the game's records) for each indexed game of a store or run."""
    idx = root / "index.jsonl"
    if idx.exists():
        for line in idx.read_text().splitlines():
            e = json.loads(line)
            yield e, root / e["file"]
    else:
        for wi in sorted(root.glob("workers/inv-*/obs.idx.jsonl")):
            for line in wi.read_text().splitlines():
                yield json.loads(line), wi.with_name("obs.zst")


def records(path: Path, e: dict):
    with open(path, "rb") as f:
        f.seek(e["off"])
        data = f.read(e["clen"])
    reader = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data))
    for line in io.TextIOWrapper(reader, encoding="utf-8"):
        yield line


def pools(obs) -> list[int]:
    if isinstance(obs, str):
        obs = json.loads(obs)
    return [sum((p.get("mana") or {}).values()) for p in obs["players"]]


def scan_game(lines) -> tuple[int, int, list[dict]]:
    """(searched-shaped windows with a probe before the ask, windows read, the leaks)."""
    first_probe = None  # (pools, t, ph, p) of the first probe record in the block before an ask
    with_probe = windows = 0
    leaks = []
    for line in lines:
        head = line[:160]
        if '"k":"ret"' in head or '"k":"ans"' in head or '"k":"mark"' in head:
            continue
        if '"k":"dec"' not in head:
            first_probe = None
            continue
        r = json.loads(line)
        m = r.get("m")
        if m in PROBES:
            if first_probe is None:
                first_probe = (pools(r["obs"]), r.get("t"), r.get("ph"), r.get("p"))
            continue
        if m == "chooseSpellAbilityToPlay" and r.get("by") == "bridge" and r.get("ph") in ("MAIN1", "MAIN2"):
            windows += 1
            if first_probe and first_probe[1:] == (r.get("t"), r.get("ph"), r.get("p")):
                with_probe += 1
                before, after = first_probe[0], pools(r["obs"])
                if any(b < a for b, a in zip(before, after)):
                    leaks.append({"t": r["t"], "ph": r["ph"], "p": r["p"], "s": r["s"], "before": before, "after": after})
        first_probe = None
    return with_probe, windows, leaks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stores", nargs="+", type=Path)
    ap.add_argument("--max-games", type=int, default=0)
    a = ap.parse_args()
    for root in a.stores:
        games = probed = windows = leaky_games = skipped = 0
        leaks = []
        for e, path in frames(root):
            if a.max_games and games >= a.max_games:
                break
            if e.get("rlen", 0) > MAX_RLEN:
                skipped += 1
                continue
            games += 1
            wp, w, found = scan_game(records(path, e))
            probed += wp
            windows += w
            if found:
                leaky_games += 1
                leaks += [{"g": e["g"], **x} for x in found]
        print(f"{root.name}: {games} games ({skipped} oversize skipped), {windows} bridged main-phase windows, "
              f"{probed} with a recorded scan callback; {len(leaks)} leaks in {leaky_games} games")
        for x in leaks[:8]:
            print("   ", json.dumps(x))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
