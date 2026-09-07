"""build2_read — the M12 Build 2 day-zero read (m12-plan Build 2, ADR-0101 §3 items 2/4/5).

Two modes:

  smoke <run_dir>            the acting-rule smoke (scripts/build2_act_smoke.sh):
                             acting stats from the ev:search rows + game outcomes.
  arms --arm name=dir[,dir]  the day-zero paired read: every arm is a
       [--arm ...] --out X   final_read.py pair of seat runs (s0,s1) on the same
                             pairs file + seed base; game-by-game paired diffs
                             (scripts/paired_arms.py estimator) between every
                             arm and the FIRST arm, plus the pre-registered
                             gate on the named pairs.

Arm names the gate understands (any subset may be present):
  ref    iter-019 alone (the reference re-read on the boundary jar)
  dz     the day-zero ckpt alone
  dzla   the day-zero ckpt + lookahead (the acting rule ON)
  heur   the heuristic mirror (seat 0 heuristic vs heuristic; a 50% symmetry check)
  heurla the heuristic + lookahead
Extra arms (e.g. dzla10 = a second bar) are read against ref and dz too.

Gate (pre-registered): dzla − dz ≥ +1.5pp GO / ≤ 0 KILL-CANDIDATE / else IN-BAND
(proceeds; the big run needs a post-Build-4 read ≥ +1.5pp). Control: |heurla −
dzla| ≤ 1.0pp = "the value head carries it" (not a kill); heurla − heur banked.
Acting telemetry per with-lookahead arm: by-class shares, applied shares,
margin quantiles, sampled≠argmax, the forward-call multiplier vs the
mainline's bridged asks, and the wall multiplier vs the plain arm.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

GATE_GO = 0.015
CONTROL_BAND = 0.010


def q(v, p):
    if not v:
        return None
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def _rows(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        if not p.exists():
            continue
        for line in open(p):
            if line.startswith('{"ev":"search"'):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def _census_asks(paths: list[Path]) -> int:
    n = 0
    for p in paths:
        if not p.exists():
            continue
        for line in open(p):
            if '"by":"bridge"' in line:
                n += 1
    return n


def act_stats(rows: list[dict], census_paths: list[Path]) -> dict:
    by: Counter = Counter()
    applied: Counter = Counter()
    kinds: Counter = Counter()
    margins, ms_window, logps = [], [], []
    sampled_not_argmax = acted = 0
    per_game_windows: dict = defaultdict(int)
    per_game_calls: dict = defaultdict(int)
    for r in rows:
        by[r.get("by", "natural")] += 1
        if "applied" in r:
            applied[r["applied"]] += 1
        ms_window.append(r["ms"])
        per_game_windows[r["i"]] += 1
        if "margin" in r:
            margins.append(r["margin"])
        vals = {}
        for o in r["opts"]:
            for k, c in zip(o["kind"], o["calls"]):
                kinds[k] += 1
                per_game_calls[r["i"]] += c
            vs = [v for v in o["v"] if v is not None]
            if vs:
                vals[o["o"]] = st.mean(vs)
        if r.get("act_o") is not None:
            acted += 1
            logps.append(r.get("logp", float("nan")))
            if vals and max(vals, key=vals.get) != r["act_o"]:
                sampled_not_argmax += 1
    n = max(1, len(rows))
    tot_k = max(1, sum(kinds.values()))
    search_calls = sum(per_game_calls.values())
    main_asks = _census_asks(census_paths)
    return {
        "windows": len(rows),
        "games_searched": len(per_game_windows),
        "windows_per_game_p50": q(list(per_game_windows.values()), 0.5),
        "by": {k: [v, round(v / n, 4)] for k, v in by.most_common()},
        "applied": {k: [v, round(v / n, 4)] for k, v in applied.most_common()},
        "act_rate": round(sum(v for k, v in by.items() if k.startswith("search")) / n, 4),
        "acted_windows": acted,
        "sampled_not_argmax": [sampled_not_argmax, round(sampled_not_argmax / max(1, acted), 4)],
        "logp_mean": round(st.mean(logps), 4) if logps else None,
        "margin": {
            "n": len(margins),
            "p50": q(margins, 0.5),
            "p90": q(margins, 0.9),
            "p99": q(margins, 0.99),
            "max": max(margins) if margins else None,
            "ge_0.05": round(sum(1 for m in margins if m >= 0.05) / max(1, len(margins)), 4),
            "ge_0.10": round(sum(1 for m in margins if m >= 0.10) / max(1, len(margins)), 4),
        },
        "leaf_kinds": {k: [v, round(v / tot_k, 4)] for k, v in kinds.most_common()},
        "ms_per_window": {"p50": q(ms_window, 0.5), "p90": q(ms_window, 0.9), "max": max(ms_window) if ms_window else None},
        "search_calls": search_calls,
        "mainline_asks": main_asks,
        "call_multiplier": round((main_asks + search_calls) / main_asks, 3) if main_asks else None,
    }


def _games(run_dir: Path) -> dict[int, dict]:
    out = {}
    p = run_dir / "games.jsonl"
    if not p.exists():
        return out
    for line in open(p):
        try:
            g = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "i" in g:
            out[g["i"]] = g
    return out


def _model_prefix(run_dir: Path) -> str:
    """The read seat's winner-name prefix: the bridged seat ("Anvil") when one
    exists; on the heuristic control arms (no seat bridged, ADR-0104 item 5)
    the seat named by -searchseats in the run's forge args ("Heur(1)" = seat 0)."""
    m = json.loads((run_dir / "run.json").read_text())
    fa = m.get("forge_args") or []
    if m.get("bridge_seats") in (None, "0", "1", 0, 1):
        return "Anvil"
    seat = int(fa[fa.index("-searchseats") + 1]) if "-searchseats" in fa else 0
    return f"Heur({seat + 1})"


def _wins(games: dict[int, dict], prefix: str = "Anvil") -> dict[int, int]:
    return {i: (1 if (g.get("winner") or "").startswith(prefix) else 0)
            for i, g in games.items() if g.get("status") == "won"}


def paired(a_dirs: list[Path], b_dirs: list[Path]) -> dict:
    diffs: list[int] = []
    for ad, bd in zip(a_dirs, b_dirs):
        sa = json.loads((ad / "run.json").read_text())
        sb = json.loads((bd / "run.json").read_text())
        for key in ("seed_base", "pairs_sha256", "n_pairs", "games_per_pair"):
            if sa.get(key) != sb.get(key):
                raise SystemExit(f"{ad.name} vs {bd.name}: {key} mismatch — not paired")
        aw, bw = _wins(_games(ad), _model_prefix(ad)), _wins(_games(bd), _model_prefix(bd))
        common = sorted(set(aw) & set(bw))
        diffs += [aw[i] - bw[i] for i in common]
    n = len(diffs)
    if n < 2:
        return {"n": n}
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    return {
        "n": n,
        "diff_pp": round(mean * 100, 3),
        "se_pp": round(se * 100, 3),
        "t": round(mean / se, 2) if se else None,
        "up": sum(1 for d in diffs if d > 0),
        "down": sum(1 for d in diffs if d < 0),
    }


def arm_summary(dirs: list[Path]) -> dict:
    wins, ms, turns, statuses = [], [], [], Counter()
    for d in dirs:
        gs = _games(d)
        prefix = _model_prefix(d)
        for g in gs.values():
            statuses[g.get("status")] += 1
            if g.get("status") == "won":
                wins.append(1 if (g.get("winner") or "").startswith(prefix) else 0)
                ms.append(g.get("ms", 0))
                turns.append(g.get("turns", 0))
    n = len(wins)
    wr = sum(wins) / n if n else None
    return {
        "dirs": [str(d) for d in dirs],
        "games": n,
        "statuses": dict(statuses),
        "winrate": round(wr, 4) if wr is not None else None,
        "se": round(math.sqrt(wr * (1 - wr) / n), 4) if n else None,
        "ms_p50": q(ms, 0.5),
        "ms_p90": q(ms, 0.9),
        "turns_p50": q(turns, 0.5),
        "forge_args": json.loads((dirs[0] / "run.json").read_text()).get("forge_args") if dirs else None,
    }


def _arm_paths(dirs: list[Path], name: str) -> list[Path]:
    out = []
    for d in dirs:
        out += [Path(p) for p in sorted(glob.glob(str(d / "workers" / "*" / name)))]
        if (d / name).exists():
            out.append(d / name)
    return out


def verdict(reads: dict) -> dict:
    v = {}
    gate = reads.get("dzla_vs_dz")
    if gate and "diff_pp" in gate:
        d = gate["diff_pp"] / 100
        v["gate"] = "GO" if d >= GATE_GO else ("KILL-CANDIDATE" if d <= 0 else "IN-BAND")
        v["gate_diff_pp"] = gate["diff_pp"]
        v["gate_se_pp"] = gate["se_pp"]
    ctrl = reads.get("heurla_vs_dzla_abs_pp")
    if ctrl is not None:
        v["control"] = "value head carries it" if ctrl <= CONTROL_BAND * 100 else "network adds beyond the head"
    return v


def cmd_smoke(a) -> int:
    run = Path(a.run_dir)
    rows = _rows([run / "search.jsonl"] + _arm_paths([run], "labels.jsonl"))
    if not rows:
        print("no search rows")
        return 1
    stats = act_stats(rows, [run / "census.jsonl"] + _arm_paths([run], "census.jsonl"))
    games = _games(run)
    stats["games"] = {
        "n": len(games),
        "status": dict(Counter(g.get("status") for g in games.values())),
        "model_wins": sum(1 for g in games.values() if (g.get("winner") or "").startswith("Anvil")),
        "ms_p50": q([g.get("ms", 0) for g in games.values()], 0.5),
        "turns_p50": q([g.get("turns", 0) for g in games.values()], 0.5),
    }
    print(json.dumps(stats, indent=1))
    return 0


def cmd_arms(a) -> int:
    arms: dict[str, list[Path]] = {}
    for spec in a.arm:
        name, dirs = spec.split("=", 1)
        arms[name] = [Path(d) for d in dirs.split(",")]
    names = list(arms)
    out: dict = {"arms": {}, "acting": {}, "paired": {}, "verdict": {}}
    for n in names:
        out["arms"][n] = arm_summary(arms[n])
        rows = _rows(_arm_paths(arms[n], "labels.jsonl"))
        if rows:
            out["acting"][n] = act_stats(rows, _arm_paths(arms[n], "census.jsonl"))
    ref = names[0]
    for n in names[1:]:
        out["paired"][f"{n}_vs_{ref}"] = paired(arms[n], arms[ref])
    if "dz" in arms and "dzla" in arms:
        out["paired"]["dzla_vs_dz"] = paired(arms["dzla"], arms["dz"])
    for n in names:
        if n.startswith("dzla") and n != "dzla" and "dz" in arms:
            out["paired"][f"{n}_vs_dz"] = paired(arms[n], arms["dz"])
    if "heur" in arms and "heurla" in arms:
        out["paired"]["heurla_vs_heur"] = paired(arms["heurla"], arms["heur"])
    if "dzla" in arms and "heurla" in arms:
        out["paired"]["heurla_vs_dzla"] = paired(arms["heurla"], arms["dzla"])
        wa, wb = out["arms"]["heurla"]["winrate"], out["arms"]["dzla"]["winrate"]
        if wa is not None and wb is not None:
            out["paired"]["heurla_vs_dzla_abs_pp"] = round(abs(wa - wb) * 100, 3)
    plain = out["arms"].get("dz") or out["arms"].get(ref)
    for n, st_ in out["acting"].items():
        if plain and plain.get("ms_p50") and out["arms"][n].get("ms_p50"):
            st_["wall_multiplier_p50"] = round(out["arms"][n]["ms_p50"] / plain["ms_p50"], 3)
    out["verdict"] = verdict({**out["paired"]})
    Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    # ---- print
    print(f"{'arm':8} {'games':>6} {'winrate':>8} {'±se':>6} {'ms p50':>8} {'turns':>6}  forge_args")
    for n in names:
        s = out["arms"][n]
        print(f"{n:8} {s['games']:>6} {s['winrate'] if s['winrate'] is not None else '-':>8} "
              f"{s['se'] if s['se'] is not None else '-':>6} {s['ms_p50'] or '-':>8} {s['turns_p50'] or '-':>6}  "
              f"{' '.join(s['forge_args'] or [])}")
    for k, p in out["paired"].items():
        if isinstance(p, dict) and "diff_pp" in p:
            print(f"paired {k:18} {p['diff_pp']:+.2f}pp ± {p['se_pp']:.2f} (t={p['t']}, n={p['n']}, {p['up']} up / {p['down']} down)")
    for n, st_ in out["acting"].items():
        print(f"acting {n}: windows {st_['windows']} act_rate {st_['act_rate']} by {st_['by']} applied {st_['applied']} "
              f"margin p50/p90/max {st_['margin']['p50']}/{st_['margin']['p90']}/{st_['margin']['max']} "
              f"call× {st_['call_multiplier']} wall× {st_.get('wall_multiplier_p50')}")
    print(f"verdict: {out['verdict']}")
    print(f"wrote {a.out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("smoke")
    s.add_argument("run_dir")
    s.set_defaults(fn=cmd_smoke)
    r = sp.add_parser("arms")
    r.add_argument("--arm", action="append", required=True, help="name=run_dir[,run_dir] (first = the reference)")
    r.add_argument("--out", required=True)
    r.set_defaults(fn=cmd_arms)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
