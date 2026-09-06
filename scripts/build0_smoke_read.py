"""build0_smoke_read — the M12 Build 0 smoke read (ADR-0102 consequences, step d).

Usage:
    uv run python scripts/build0_smoke_read.py [--ref <rebaseline run dir>] [--ingest]

Reads the build0-smoke{A,B,C} arm dirs under data/runs (newest per arm) and prints
one table: per arm — games, status mix, cap hits, windows/turns/ms quantiles,
games/hour (from data/runs/build0-smoke/arms.jsonl wall_s), bridged census
veto rates (first-attempt and re-ask), veto reason classes, and for the shadow
arm the paymask n/rej/rescue sums. With --ingest, arms A and B are ingested
(if not already) and the heuristic-seat "expert pick outside the mask" count
(a priority dec with a non-pass ret and no 'oi' label) is read from A's store;
run scripts/obs_diff.py on the two stores for the cache gate.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from anvil.training.selfplay import _census_tallies  # noqa: E402

RUNS = REPO / "data/runs"


def _q(v: list, p: float):
    if not v:
        return None
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def games_summary(run_dir: Path) -> dict:
    rows = []
    for f in run_dir.glob("workers/inv-*/games.jsonl"):
        for line in open(f):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    st = Counter(r.get("status") for r in rows)
    caps = Counter(r.get("cap") for r in rows if r.get("cap"))
    w = [r["windows"] for r in rows if r.get("windows") is not None]
    t = [r["turns"] for r in rows if r.get("turns") is not None]
    ms = [r["ms"] for r in rows if r.get("ms") is not None]
    return {
        "games": len(rows), "status": dict(st), "caps": dict(caps),
        "draw_clock": sum(1 for r in rows if r.get("draw_clock")),
        "windows_p50_p99_p995_max": [_q(w, .5), _q(w, .99), _q(w, .995), max(w) if w else None],
        "turns_p50_p99_max": [_q(t, .5), _q(t, .99), max(t) if t else None],
        "ms_p50_p90_p99_max": [_q(ms, .5), _q(ms, .9), _q(ms, .99), max(ms) if ms else None],
        "ms_sum": sum(ms),
    }


def veto_reasons(run_dir: Path) -> tuple[Counter, Counter]:
    first: Counter = Counter()
    pm: Counter = Counter()
    for f in run_dir.glob("workers/inv-*/census.jsonl"):
        for line in open(f):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("m") == "paymask":
                pm["windows"] += 1
                for k in ("n", "rej", "rescue"):
                    pm[k] += int(r.get(k) or 0)
            if r.get("by") != "bridge" or r.get("m") != "chooseSpellAbilityToPlay":
                continue
            if r.get("veto") and not r.get("reask"):
                first[str(r["veto"])] += 1
    return first, pm


def outside_mask(store_dir: Path, heur_seat: int = 1) -> dict:
    from anvil.store.trajectories import TrajectoryStore

    ts = TrajectoryStore(store_dir)
    n = out = passes = 0
    for traj in ts.games(skip_undecodable=True):
        for d in traj.decisions:
            if d.get("m") != "chooseSpellAbilityToPlay" or d.get("p") != heur_seat:
                continue
            ret = d.get("ret")
            if not ret:
                passes += 1
                continue
            n += 1
            if d.get("oi") is None:
                out += 1
    return {"heur_casts": n, "heur_passes": passes, "outside_mask": out,
            "rate": round(out / max(n, 1), 4)}


def newest(purpose: str) -> Path | None:
    hits = sorted(glob.glob(str(RUNS / f"{purpose}-*")))
    return Path(hits[-1]) if hits else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=None, help="a pre-boundary run dir for the reference row")
    ap.add_argument("--ingest", action="store_true")
    a = ap.parse_args()
    walls = {}
    arms_file = RUNS / "build0-smoke/arms.jsonl"
    if arms_file.exists():
        for line in open(arms_file):
            r = json.loads(line)
            walls[r["arm"]] = r
    rows = []
    if a.ref:
        rows.append(("ref", Path(a.ref)))
    for arm in ("A", "B", "C"):
        d = newest(f"build0-smoke{arm}")
        if d:
            rows.append((arm, d))
    for name, d in rows:
        gs = games_summary(d)
        c = _census_tallies(d)
        first, pm = veto_reasons(d)
        w = walls.get(name)
        gph = round(gs["games"] / (w["wall_s"] / 3600), 1) if w and w.get("wall_s") else None
        print(f"== {name}: {d.name}")
        print(f"   games {gs['games']} status {gs['status']} caps {gs['caps']} draw_clock {gs['draw_clock']}"
              f" games/h {gph}")
        print(f"   windows p50/p99/p99.5/max {gs['windows_p50_p99_p995_max']}  turns p50/p99/max {gs['turns_p50_p99_max']}"
              f"  ms p50/p90/p99/max {gs['ms_p50_p90_p99_max']}")
        print(f"   veto_rate {c.get('veto_rate')} first_veto_rate {c.get('first_veto_rate')}"
              f" (veto {c.get('veto')} cast {c.get('cast')} first_veto {c.get('first_veto')} first_cast {c.get('first_cast')}"
              f" reask_rescued {c.get('reask_rescued')} fallback {c.get('fallback')})")
        print(f"   first-veto reasons {dict(first.most_common(8))}")
        if pm:
            print(f"   paymask windows {pm['windows']} scanned {pm['n']} rejected {pm['rej']} rescue {pm['rescue']}"
                  f" (rescue/rejected {pm['rescue'] / max(pm['rej'], 1):.4f})")
        if a.ingest and name in ("A", "B"):
            from anvil.store.trajectories import TRAJECTORIES_DIR, ingest

            run_id = json.loads((d / "run.json").read_text())["run_id"]
            dest = TRAJECTORIES_DIR / run_id
            if not (dest / "manifest.json").exists():
                ingest(d)
            if name == "A":
                print(f"   heuristic seat outside-mask {outside_mask(dest)}")
            print(f"   store {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
