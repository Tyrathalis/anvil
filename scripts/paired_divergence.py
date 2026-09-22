"""Paired first-divergence read (09-21, Kryptic's suggestion; ADR-0116's read).

Two harness runs on the SAME pairs file and seed base share every draw and every
heuristic decision until the first decision the model answers differently from
the heuristic — the mirror run (both seats heuristic, --heuristic-control) and
the model run (one seat bridged) are the same game up to that window. For each
game aligned by (seat run, game index): the first divergent decision (turn,
phase, method, the model's answer vs the heuristic's at the same state), whether
it was a player-target window, and the outcome pair (the heuristic won that seat
from this draw / the model did) — the apples-to-apples per-draw comparison; the
per-seed sign is what the paired read sums.

Caveats: only the FIRST divergence is attributable (after it the games differ
everywhere); ~0.2% of games diverge with identical decisions (the identity-hash
residual, ADR-0025); a decision the model answers identically leaves no trace.

Usage: paired_divergence.py --model <arm dir>[,<arm dir>] --mirror <arm dir>[,<arm dir>] [--json out] [--top 20]
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
from pathlib import Path

import zstandard


def games_of(dirs: str):
    """Yield (seed, header, [(dec, ret)], end) per game over the dirs' obs.zst."""
    for d in dirs.split(","):
        for f in sorted(glob.glob(f"{d}/workers/inv-*/obs.zst")):
            with open(f, "rb") as fh:
                r = zstandard.ZstdDecompressor().stream_reader(fh)
                buf = b""
                cur = None
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    buf += chunk
                    lines = buf.split(b"\n")
                    buf = lines.pop()
                    for l in lines:
                        if not l.strip():
                            continue
                        rec = json.loads(l)
                        k = rec.get("k")
                        if k == "game":
                            if cur:
                                yield cur
                            cur = {"seed": rec.get("seed"), "hdr": rec, "decs": {}, "order": [], "end": None}
                        elif cur is None:
                            continue
                        elif k == "dec":
                            cur["decs"][rec["s"]] = {"dec": rec, "ret": None}
                            cur["order"].append(rec["s"])
                        elif k == "ret" and rec.get("s") in cur["decs"]:
                            cur["decs"][rec["s"]]["ret"] = rec.get("v")
                        elif k == "end":
                            cur["end"] = rec
                if cur:
                    yield cur
                    cur = None


def _has_player_target(ret) -> bool:
    if not isinstance(ret, list):
        return False
    for plan in ret:
        if not isinstance(plan, dict):
            continue
        refs = list(plan.get("tgt") or [])
        for s in plan.get("sub") or []:
            refs += s.get("tgt") or []
        if any("pi" in x for x in refs):
            return True
    return False


def _winner_seat(g) -> int | None:
    e = g["end"] or {}
    w = e.get("winner")
    if isinstance(w, int):
        return w
    if isinstance(w, str):
        if "(1)" in w:
            return 0
        if "(2)" in w:
            return 1
    return None


def compare(model: dict, mirror: dict) -> dict:
    """First decision (in sequence order) whose (method, seat, turn) or answer differs."""
    mseat = None
    for s in model["order"]:
        d = model["decs"][s]["dec"]
        if d.get("by") == "bridge":
            mseat = int(d["p"])
            break
    out = {"seed": model["seed"], "model_seat": mseat, "diverged": False}
    for s in model["order"]:
        a = model["decs"][s]
        b = mirror["decs"].get(s)
        da = a["dec"]
        if b is None:
            out.update(diverged=True, at="missing-in-mirror", turn=da.get("t"), phase=da.get("ph"),
                       method=da.get("m"), seat=da.get("p"))
            break
        db = b["dec"]
        same_id = (da.get("m"), da.get("p"), da.get("t"), da.get("ph")) == (db.get("m"), db.get("p"), db.get("t"), db.get("ph"))
        if not same_id or a["ret"] != b["ret"]:
            out.update(diverged=True, at="answer" if same_id else "state", turn=da.get("t"), phase=da.get("ph"),
                       method=da.get("m"), seat=da.get("p"), by=da.get("by"),
                       model_answer=json.dumps(a["ret"])[:160], heuristic_answer=json.dumps(b["ret"])[:160],
                       player_target=_has_player_target(a["ret"]) or _has_player_target(b["ret"]))
            break
    wm, wh = _winner_seat(model), _winner_seat(mirror)
    if mseat is not None and wm is not None and wh is not None:
        out["model_won"] = wm == mseat
        out["heuristic_won_that_seat"] = wh == mseat
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--mirror", required=True)
    ap.add_argument("--json", default=None)
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()
    mirror = {}
    for g in games_of(a.mirror):
        mirror[g["seed"]] = g
    rows = []
    for g in games_of(a.model):
        m = mirror.get(g["seed"])
        if m is None:
            continue
        rows.append(compare(g, m))
    n = len(rows)
    div = [r for r in rows if r["diverged"]]
    by_method = collections.Counter(r.get("method") for r in div)
    pt = sum(1 for r in div if r.get("player_target"))
    pairs = [(r["model_won"], r["heuristic_won_that_seat"]) for r in rows if "model_won" in r]
    flips = collections.Counter(pairs)
    summary = {
        "games_aligned": n, "diverged": len(div), "never_diverged": n - len(div),
        "first_divergence_turn_median": sorted(r.get("turn") or 0 for r in div)[len(div) // 2] if div else None,
        "first_divergence_by_method": dict(by_method.most_common(8)),
        "first_divergence_on_player_target_window": pt,
        "outcome_pairs (model_won, heuristic_won_that_seat)": {f"{k[0]},{k[1]}": v for k, v in flips.items()},
        "model_better_from_draw": flips[(True, False)], "model_worse_from_draw": flips[(False, True)],
    }
    print(json.dumps(summary, indent=2))
    print("\nearliest divergences:")
    for r in sorted(div, key=lambda r: (r.get("turn") or 0))[: a.top]:
        print(f"  seed {r['seed']} t{r.get('turn')} {r.get('phase')} {r.get('method')} seat {r.get('seat')} "
              f"[{r.get('at')}{' PLAYER-TARGET' if r.get('player_target') else ''}]\n"
              f"    model: {r.get('model_answer')}\n    heur:  {r.get('heuristic_answer')}")
    if a.json:
        Path(a.json).write_text(json.dumps({"summary": summary, "games": rows}, indent=2))


if __name__ == "__main__":
    main()
