#!/usr/bin/env python3
"""M11 routing-probe read — PRE-REGISTERED (m11-routing-probes-spec.md
launch pins; scripts/choice_pins.py imported, never redefined). Committed
before any forcing data exists.

Primary (per probe, the ceiling genre): paired best-forced vs natural
Δwr per point, select/score split (best arm chosen on SELECT_ROLLS mean
paired delta, scored on the complement; a point needs >= MIN_FIRED_SCORING
fired scoring rolls with natural pairs, else it moves to the coverage
denominator). Aggregate = mean per-point scored delta, game-clustered
bootstrap CI. Gate-scale = mean Δ x mined per-seat-game rate (pins) in
pp/game, with a coverage-discounted row (x FORKABLE). Routing verdict per
the adjudicated ADR-0078 scale: point >= ROUTING_POINT => SCHEDULE into
M11; below => RE-DEFER with the number.

Secondary (never gating): pooled each-arm-vs-natural deltas over all
rolls (unbiased, no split), P pay-minus-decline pooled, T per-index
deltas, fired/coverage rates, skip accounting. Health: crash + unended
(timeout/draw-clock class) rates, natural-vs-forced asymmetry flag.

Win convention: winner == point seat -> 1 else 0 (draws non-wins for
both — symmetric, cancels in paired differences; the forced_branch_read
convention).

Usage:
  uv run python scripts/choice_read.py --plan data/runs/choice-probes-m11
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import choice_pins as pins  # noqa: E402

BOOT = 2000
BOOT_SEED = 20520826


def load(plan_dir: Path):
    points = [json.loads(ln) for ln in open(plan_dir / "points.jsonl")]
    arms = defaultdict(list)  # (g, t) -> [(armId, kind, action)]
    for ln in (plan_dir / "choice.tsv").read_text().splitlines():
        if not ln or ln.startswith("#"):
            continue
        f = ln.split("\t")
        arms[(int(f[0]), int(f[1]))].append((int(f[4]), f[5], f[6]))
    rows: dict[tuple, dict] = {}
    skips = []
    for f in sorted((plan_dir / "lanes").glob("lane-*.out*.jsonl")):
        for ln in open(f):
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("ev") != "choice":
                continue
            if "skip" in r:
                skips.append(r)
                continue
            rows.setdefault((r["i"], r["t"], r["arm"], r["roll"]), r)
    return points, arms, rows, skips


def win(r: dict, seat: int) -> float:
    return 1.0 if r.get("winner") == seat else 0.0


def per_point(pt, arm_list, rows, kinds):
    """-> (scored delta | None, exclusion reason, per-arm pooled deltas,
    best arm id) for the probe restricted to `kinds`."""
    g, t, seat = pt["g"], pt["t"], pt["seat"]
    nat = {r: rows[(g, t, 0, r)] for r in range(pins.K_ROLLS)
           if (g, t, 0, r) in rows and not rows[(g, t, 0, r)].get("crash")}
    if not nat:
        return None, "no_natural", {}, None
    cand = [(aid, kind, act) for (aid, kind, act) in arm_list if kind in kinds]
    pooled = {}
    sel_mean = {}
    per_arm_scores = {}
    for aid, kind, act in cand:
        deltas_sel, deltas_score, deltas_all = [], [], []
        for r in range(pins.K_ROLLS):
            fr = rows.get((g, t, aid, r))
            if fr is None or fr.get("crash") or not fr.get("fired") or r not in nat:
                continue
            d = win(fr, seat) - win(nat[r], seat)
            deltas_all.append(d)
            (deltas_sel if r in pins.SELECT_ROLLS else deltas_score).append(d)
        if deltas_all:
            pooled[aid] = deltas_all
        if deltas_sel:
            sel_mean[aid] = sum(deltas_sel) / len(deltas_sel)
        if len(deltas_score) >= pins.MIN_FIRED_SCORING:
            per_arm_scores[aid] = sum(deltas_score) / len(deltas_score)
    if not cand:
        return None, "no_arms", pooled, None
    if not sel_mean:
        return None, "no_fired_select", pooled, None
    best = max(sel_mean, key=lambda a: (sel_mean[a], -a))
    if best not in per_arm_scores:
        return None, "insufficient_fired_scoring", pooled, best
    return per_arm_scores[best], None, pooled, best


def cluster_boot(vals_by_game: dict[int, list[float]]):
    games = sorted(vals_by_game)
    rng = random.Random(BOOT_SEED)
    means = []
    for _ in range(BOOT):
        vs = []
        for _ in games:
            vs.extend(vals_by_game[rng.choice(games)])
        means.append(sum(vs) / len(vs))
    means.sort()
    return means[int(0.025 * BOOT)], means[int(0.975 * BOOT)]


def probe_read(name, kinds, rate, forkable, points, arms, rows):
    per_game = defaultdict(list)
    excl = defaultdict(int)
    pooled_by_arm = defaultdict(list)
    n_pts = 0
    for pt in points:
        arm_list = arms.get((pt["g"], pt["t"]), [])
        if not any(k in kinds for (_, k, _a) in arm_list):
            continue
        n_pts += 1
        scored, why, pooled, _best = per_point(pt, arm_list, rows, kinds)
        for aid, ds in pooled.items():
            kindact = next((f"{k}:{a}" for (i, k, a) in arm_list if i == aid), str(aid))
            pooled_by_arm[kindact].extend(ds)
        if scored is None:
            excl[why] += 1
            continue
        per_game[pt["g"]].append(scored)
    used = sum(len(v) for v in per_game.values())
    rep = {"points_planned": n_pts, "points_used": used,
           "excluded": dict(excl)}
    if used == 0:
        rep["verdict"] = "NO DATA"
        return rep
    vals = [v for vs in per_game.values() for v in vs]
    mean = sum(vals) / len(vals)
    lo, hi = cluster_boot(per_game)
    gs_point = mean * rate * 100
    gs_lo = lo * rate * 100
    rep.update({
        "per_window_delta": {"mean": round(mean, 4),
                             "ci95": [round(lo, 4), round(hi, 4)]},
        "gate_scale_pp_per_game": {"point": round(gs_point, 2),
                                   "ci_lower": round(gs_lo, 2),
                                   "coverage_discounted": round(gs_point * forkable, 2)},
        "secondary_pooled_by_arm": {
            k: {"n": len(v), "mean": round(sum(v) / len(v), 4)}
            for k, v in sorted(pooled_by_arm.items())},
        "verdict": ("SCHEDULE into M11"
                    if gs_point >= pins.ROUTING_POINT else
                    f"RE-DEFER (point {gs_point:.2f} < {pins.ROUTING_POINT})"),
        "floor_row_met": bool(gs_lo >= pins.ROUTING_FLOOR),
    })
    return rep


def health(rows, skips):
    n = len(rows)
    crash = sum(1 for r in rows.values() if r.get("crash"))
    unended = sum(1 for r in rows.values()
                  if not r.get("crash") and not r.get("ended")
                  and not r.get("stopped"))
    nat = [r for r in rows.values() if r["arm"] == 0]
    frc = [r for r in rows.values() if r["arm"] != 0]
    def ur(rs):
        return (sum(1 for r in rs if not r.get("crash") and not r.get("ended")
                    and not r.get("stopped")) / len(rs)) if rs else 0.0
    fired = sum(1 for r in frc if r.get("fired"))
    return {"rows": n, "crash": crash, "unended": unended,
            "unended_rate_natural": round(ur(nat), 4),
            "unended_rate_forced": round(ur(frc), 4),
            "asymmetry_flag": bool(ur(nat) > 0 and
                                   max(ur(nat), ur(frc)) > 2 * max(1e-9, min(ur(nat), ur(frc)))),
            "fired_rate_forced": round(fired / len(frc), 4) if frc else 0.0,
            "skips": len(skips)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    a = ap.parse_args()
    plan_dir = Path(a.plan).resolve()
    points, arms, rows, skips = load(plan_dir)
    report = {
        "pins": {k: getattr(pins, k) for k in dir(pins) if k.isupper()},
        "T": probe_read("T", {"tutor"}, pins.RATE_T, pins.FORKABLE_T,
                        points, arms, rows),
        "P": probe_read("P", {"prevent"}, pins.RATE_P, pins.FORKABLE_P,
                        points, arms, rows),
        "health": health(rows, skips),
    }
    (plan_dir / "choice-read.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n")
    for k in ("T", "P"):
        r = report[k]
        gs = r.get("gate_scale_pp_per_game", {})
        print(f"probe {k}: used {r.get('points_used')}/{r.get('points_planned')}"
              f" | dWin/window {r.get('per_window_delta', {}).get('mean')}"
              f" | gate-scale {gs.get('point')}pp/g [lo {gs.get('ci_lower')}]"
              f" | {r.get('verdict')}")
    print(f"health: {report['health']}")
    print(f"-> {plan_dir}/choice-read.json")


if __name__ == "__main__":
    main()
