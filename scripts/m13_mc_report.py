"""Read the Monte Carlo cells of M13 Build 0 step 3 (ADR-0129; the driver is scripts/m13_mc.sh).

    uv run python scripts/m13_mc_report.py cal  --clock data/runs/m13-mc/clock --ladder data/runs/m13-mc/ladder
    uv run python scripts/m13_mc_report.py read --out data/runs/m13-mc/read

`cal` puts the desktop mode on its clock beside every count-budget rung: what a decision was offered,
what it sampled, how long it took. The rung to pin is the one whose samples per decision sit nearest
the clock's. It also checks the instrument: the desktop counts through the max flag and through
profile properties must give the same games.

`read` gives the Monte Carlo seat's winrate against the plain heuristic (a win over all games, so a
draw or a crash counts against it, as in arms_report.py), paired on seed against the plain mirror,
with each arm's wall cost and the AI deadline's firings.
"""
import argparse
import glob
import json
import math
import os
import statistics as st


def rows(path: str) -> list[dict]:
    """A worker that died mid-write (out of memory) leaves a cut last line; it is skipped."""
    out = []
    if os.path.isfile(path):
        for x in open(path, errors="replace"):
            try:
                out.append(json.loads(x)) if x.strip() else None
            except json.JSONDecodeError:
                pass
    return out


def decisions(paths: list[str]) -> list[dict]:
    return [r for p in paths for r in rows(p) if r["mode"] != "null"]


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float("nan")


def dec_line(name: str, dec: list[dict], games: list[dict], cap: int | None = None) -> str:
    if not dec:
        return f"| {name} | 0 | | | | | | | | |"
    main = [r for r in dec if r["mode"] == "MAIN"]
    f = lambda rs, k: st.fmean(r[k] for r in rs) if rs else float("nan")  # noqa: E731
    ms = [r["us"] / 1000 for r in dec]
    full = sum(r["rounds"] >= cap for r in main) / max(len(main), 1) if cap else float("nan")
    secs = [g["ms"] / 1000 for g in games]
    return (
        f"| {name} | {len(dec)} | {f(dec, 'rollouts'):.2f} | {f(main, 'rollouts'):.2f} | {f(main, 'rounds'):.2f} "
        f"| {f(main, 'offered'):.2f} | {f(main, 'evaluated'):.2f} | {full:.0%} | {st.median(ms):.0f} / {pct(ms, 0.95):.0f} "
        f"| {st.median(secs):.1f} / {st.fmean(secs):.1f} |"
    )


HEAD = (
    "| cell | decisions | rollouts per decision | main: rollouts | main: rounds | main: lines offered "
    "| main: lines sampled | main: at the round cap | decision ms, median / p95 | game s, median / mean |\n"
    "|---|---|---|---|---|---|---|---|---|---|"
)


def cal(a) -> None:
    print(HEAD)
    clock = decisions([f"{a.clock}/clock/mc-decisions.jsonl"])
    print(dec_line("clock (desktop mode, idle box)", clock, rows(f"{a.clock}/clock/games.jsonl"), 14))
    target = st.fmean(r["rollouts"] for r in clock) if clock else float("nan")
    best = None
    for d in sorted(glob.glob(f"{a.ladder}/*/"), key=lambda x: (len(os.path.basename(x[:-1])), x)):
        tag = os.path.basename(d[:-1])
        dec = decisions([f"{d}mc-decisions.jsonl"])
        cap = int(tag[1:]) if tag[0] == "r" and tag[1:].isdigit() else 14
        print(dec_line(f"count budget, {tag}", dec, rows(f"{d}games.jsonl"), cap))
        if dec and tag[0] == "r" and tag[1:].isdigit():
            gap = abs(st.fmean(r["rollouts"] for r in dec) - target)
            best = min(best or (gap, cap), (gap, cap))
    if best:
        print(f"\nNearest rung to the clock's {target:.2f} rollouts per decision: {best[1]} rounds (gap {best[0]:.2f}).")
    strip = lambda g: {k: v for k, v in g.items() if k not in ("ms", "mc")}  # noqa: E731
    flag, props = (rows(f"{a.ladder}/{t}/games.jsonl") for t in ("max-flag", "max-props"))
    if flag and props:
        same = sum(strip(x) == strip(y) for x, y in zip(flag, props))
        fd, pd = (decisions([f"{a.ladder}/{t}/mc-decisions.jsonl"]) for t in ("max-flag", "max-props"))
        drop = lambda r: {k: v for k, v in r.items() if k != "us"}  # noqa: E731
        print(
            f"Instrument: the max flag and the profile properties give the same game in {same} of {len(flag)}; "
            f"decision rows {len(fd)} and {len(pd)}, identical apart from time: {[drop(r) for r in fd] == [drop(r) for r in pd]}."
        )


def arm_stats(run_dir: str) -> dict:
    games = {g["i"]: g for g in rows(f"{run_dir}/games.jsonl")}
    secs = [g["ms"] / 1000 for g in games.values()]
    timeouts = 0
    for log in glob.glob(f"{run_dir}/workers/inv-*/out.log"):
        with open(log, errors="replace") as f:
            timeouts += sum("AI eval thread at timeout" in line for line in f)
    # a decision row counts only where its worker finished the game (a dead worker's games are replayed)
    dec, oom = [], 0
    for w in glob.glob(f"{run_dir}/workers/inv-*/"):
        done = {g["i"] for g in rows(f"{w}games.jsonl")}
        dec += [r for r in decisions([f"{w}mc-decisions.jsonl"]) if r["i"] in done]
        with open(f"{w}out.log", errors="replace") as f:
            oom += any("OutOfMemoryError" in line for line in f)
    statuses: dict[str, int] = {}
    for g in games.values():
        statuses[g["status"]] = statuses.get(g["status"], 0) + 1
    return {
        "games": games, "n": len(games), "statuses": statuses, "timeouts": timeouts,
        "s_median": st.median(secs) if secs else float("nan"), "s_mean": st.fmean(secs) if secs else float("nan"),
        "dec": dec, "oom": oom,
    }


def seat_won(g: dict, seat: int) -> int:
    return 1 if (g.get("winner") or "").startswith(f"Heur({seat + 1})") else 0


def mean_se(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    m = st.fmean(xs)
    return m, math.sqrt(st.pvariance(xs) / n) if n > 1 else float("nan")


def read(a) -> None:
    def load(name):
        p = f"{a.out}/{name}.done"
        return arm_stats(open(p).read().strip()) if os.path.isfile(p) else None

    plain = load("mc-plain")
    print("| arm | games | statuses | game s, median / mean | AI deadline firings | workers out of memory | rollouts per decision |")
    print("|---|---|---|---|---|---|---|")
    arms = {n: load(n) for n in ("mc-plain", "mc-count-s0", "mc-count-s1", "mc-clock-s0", "mc-clock-s1")}
    for name, s in arms.items():
        if s:
            rp = f"{st.fmean(r['rollouts'] for r in s['dec']):.2f}" if s["dec"] else "-"
            print(f"| {name} | {s['n']} | {s['statuses']} | {s['s_median']:.1f} / {s['s_mean']:.1f} | {s['timeouts']} | {s['oom']} | {rp} |")
    print()
    if plain:
        m, se = mean_se([seat_won(g, 0) for g in plain["games"].values()])
        print(f"- Plain mirror: seat 0 wins {m:.4f} ± {se:.4f} of {plain['n']} games.")
    for kind in ("count", "clock"):
        wins, paired = [], []
        for seat in (0, 1):
            s = arms.get(f"mc-{kind}-s{seat}")
            if not s:
                continue
            w = [seat_won(g, seat) for g in s["games"].values()]
            m, se = mean_se(w)
            print(f"- Monte Carlo ({kind}) in seat {seat}: wins {m:.4f} ± {se:.4f} of {s['n']} games.")
            wins += w
            if plain:
                paired += [seat_won(g, seat) - seat_won(plain["games"][i], seat)
                           for i, g in s["games"].items() if i in plain["games"]]
        if wins:
            m, se = mean_se(wins)
            print(f"- **Monte Carlo ({kind}), both seats: {m:.4f} ± {se:.4f}** of {len(wins)} games.")
        if paired:
            m, se = mean_se(paired)
            print(f"  Paired on seed against the plain heuristic in the same seat: {m * 100:+.2f} ± {se * 100:.2f}pp ({len(paired)} pairs).")
    for kind in ("count", "clock"):
        dec = [r for seat in (0, 1) if arms.get(f"mc-{kind}-s{seat}") for r in arms[f"mc-{kind}-s{seat}"]["dec"]]
        if dec:
            print(f"\nDecisions, {kind}:\n{HEAD}")
            games = [g for seat in (0, 1) if arms.get(f"mc-{kind}-s{seat}") for g in arms[f"mc-{kind}-s{seat}"]["games"].values()]
            print(dec_line(kind, dec, games, 14 if kind == "clock" else a.rounds))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cal")
    c.add_argument("--clock", default="data/runs/m13-mc/clock")
    c.add_argument("--ladder", default="data/runs/m13-mc/ladder")
    r = sub.add_parser("read")
    r.add_argument("--out", default="data/runs/m13-mc/read")
    r.add_argument("--rounds", type=int, default=None)
    a = ap.parse_args()
    cal(a) if a.cmd == "cal" else read(a)


if __name__ == "__main__":
    main()
