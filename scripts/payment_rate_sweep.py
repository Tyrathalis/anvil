#!/usr/bin/env python3
"""M9 window-rate sweep (ADR-0073 decision 4; pins in m9-plan "The ceiling
measurement" addendum): what fraction of the tagged consequential-window
universe certifies positive, uniformly sampled — the missing factor in the
gate-scale arithmetic.

The ceiling read established conversion (+12.5pp/window where certified
in-era); the mined rate (0.112/g/seat) is a lower bound because only the
top-ranked ~20% of tagged windows were ever adjudicated, and miner rank is
measured non-predictive. This sweep certifies a UNIFORM sample of the
tagged universe on the bundle jar and reads the rate with a CI.

  gen     mirror a template census's deck pairs into fresh lane scripts
          (fresh seed base, current jar, new outdir).
  sample  mined candidates -> uniform sample of N unique windows ->
          certify jobs (shape by the evalset priority rule) + frame.json.
  rate    certified output + frame -> rate CI + gate-scale arithmetic.

Certification itself reuses payment_certify.py (lanes + read) unchanged.
Recorded assumption: untagged consequential windows are outside the frame —
the shape predicates are the only certification instrument that exists, so
the rate is "certifiable BY the standing taxonomy", a lower bound on any
broader notion of payment value.
"""

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import payment_certify as pc  # noqa: E402

SHAPE_PRIORITY = ["forced_chain", "phyrexian", "blocker_pressure",
                  "color_hold", "wide_choice"]
# ADR-0073 conversion factors (pp per certified window, game-end)
CONV_CENTRAL = 4.62
CONV_RECERT = 12.50
GATE_FLOOR_PP = 1.1

_TMPL = re.compile(r"-d '([^']+)' '([^']+)' -f (\S+) .*?-n (\d+) -s (\d+) "
                   r"-o '([^']*/pair-(\d+)\.jsonl)\.tmp'")


def gen(args) -> None:
    pairs = []
    for lane in sorted(Path(args.template).glob("lane-*.sh")):
        for m in _TMPL.finditer(lane.read_text()):
            pairs.append((int(m.group(7)), m.group(1), m.group(2),
                          m.group(3), int(m.group(4))))
    pairs.sort()
    if not pairs:
        raise SystemExit(f"no census commands parsed from {args.template}")
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    gui = Path(args.jar).resolve().parent.parent.parent / "forge-gui"
    lanes = [["#!/bin/sh", "set -e", f"cd '{gui}'"] for _ in range(args.n)]
    for idx, d1, d2, fmt, ngames in pairs:
        seed = args.seed_base + 4000 * idx
        out = outdir / f"pair-{idx:03d}.jsonl"
        lanes[idx % args.n].append(
            f"nice -n 19 java -Xms1g -Xmx2g -XX:ActiveProcessorCount=2 "
            f"-jar '{Path(args.jar).resolve()}' census -d '{d1}' '{d2}' "
            f"-f {fmt} -paytelemetry -n {ngames} -s {seed} -o '{out}.tmp' "
            f"&& mv '{out}.tmp' '{out}'")
    for i, lines in enumerate(lanes):
        sh = outdir / f"lane-{i}.sh"
        sh.write_text("\n".join(lines) + "\n")
        sh.chmod(0o755)
    n_games = sum(p[4] for p in pairs)
    print(f"{len(pairs)} pairs / {n_games} games -> {args.n} lanes under {outdir}")
    print(f"seed range {args.seed_base}..{args.seed_base + 4000 * pairs[-1][0]}")


def sample(args) -> None:
    cands, seen = [], set()
    for line in open(args.candidates):
        c = json.loads(line)
        key = (c["source"], c["g"], c["t"], c["sa"])
        if key in seen:
            continue
        seen.add(key)
        cands.append(c)
    census_dir = Path(args.candidates).parent
    lanes = pc.lane_index(census_dir)
    rng = random.Random(args.rng)
    picked = rng.sample(cands, min(args.n, len(cands)))

    n_games = 0
    for pair in sorted(census_dir.glob("pair-*.jsonl")):
        n_games += sum(1 for l in open(pair) if '"ev": "start"' in l or '"ev":"start"' in l)

    jobs, dropped = [], 0
    for c in picked:
        pair = Path(c["source"]).stem
        if pair not in lanes:
            dropped += 1
            continue
        d1, d2, _ = lanes[pair]
        shape = next(s for s in SHAPE_PRIORITY if s in c["tags"])
        jobs.append({
            "job": len(jobs), "shape": shape, "seed": c["seed"],
            "deck1": d1, "deck2": d2, "p": c["p"], "t": c["t"],
            "sa": c["sa"], "ord": 0, "arms": min(int(c.get("goals", 1)), 9),
            "k": pc.SHAPE_K.get(shape, 8), "horizon": pc.HORIZON,
            "source": c["source"], "g": c["g"], "tags": c["tags"],
        })
    out = Path(args.out)
    with open(out, "w") as f:
        for j in jobs:
            f.write(json.dumps(j) + "\n")
    frame = {
        "census": str(census_dir), "games": n_games,
        "tagged_windows": len(cands), "sampled": len(jobs),
        "dropped_no_lane": dropped, "rng": args.rng,
        "by_shape": {s: sum(1 for j in jobs if j["shape"] == s)
                     for s in SHAPE_PRIORITY if any(j["shape"] == s for j in jobs)},
    }
    (out.parent / "frame.json").write_text(json.dumps(frame, indent=2) + "\n")
    print(f"frame: {len(cands)} tagged windows / {n_games} games "
          f"({len(cands) / max(1, n_games):.2f}/g); sampled {len(jobs)} -> {out}")
    for s, n in frame["by_shape"].items():
        print(f"  {s:<18} {n}")


def _wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if not n:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), c + h)


def rate(args) -> None:
    frame = json.load(open(args.frame))
    n_pos = sum(1 for _ in open(args.certified))
    n = frame["sampled"]
    p, lo, hi = _wilson(n_pos, n)
    per_game = frame["tagged_windows"] / frame["games"]
    print(f"certifiable rate: {n_pos}/{n} = {p:.4f} [{lo:.4f}, {hi:.4f}] "
          f"(Wilson 95)")
    print(f"tagged universe: {per_game:.2f} windows/game "
          f"=> certifiable windows/game: {p * per_game:.3f} "
          f"[{lo * per_game:.3f}, {hi * per_game:.3f}]")
    rows = []
    for conv, label in ((CONV_CENTRAL, "central (+4.62pp pooled)"),
                        (CONV_RECERT, "upper (+12.5pp recert)")):
        est = p * per_game * conv
        cl, ch = lo * per_game * conv, hi * per_game * conv
        verdict = "CLEARS" if cl >= GATE_FLOOR_PP else (
            "reaches" if ch >= GATE_FLOOR_PP else "below")
        rows.append({"conv": label, "pp_per_game": est, "ci": [cl, ch],
                     "vs_gate_floor": verdict})
        print(f"  perfect-play value @ {label}: {est:+.2f}pp/game "
              f"[{cl:+.2f}, {ch:+.2f}] -> {verdict} the {GATE_FLOOR_PP}pp floor")
    report = {
        "pins": "m9-plan rate-sweep addendum (2026-08-24)",
        "positives": n_pos, "sampled": n, "rate": [p, lo, hi],
        "tagged_per_game": per_game, "frame": frame, "arithmetic": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(f"-> {args.out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--template", required=True)
    g.add_argument("--outdir", required=True)
    g.add_argument("--jar", required=True)
    g.add_argument("--seed-base", type=int, required=True)
    g.add_argument("-n", type=int, default=4)
    g.set_defaults(fn=gen)
    s = sub.add_parser("sample")
    s.add_argument("--candidates", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--n", type=int, default=600)
    s.add_argument("--rng", type=int, default=20260824)
    s.set_defaults(fn=sample)
    r = sub.add_parser("rate")
    r.add_argument("--frame", required=True)
    r.add_argument("--jobs", required=False)
    r.add_argument("--certified", required=True)
    r.add_argument("--out", required=True)
    r.set_defaults(fn=rate)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
