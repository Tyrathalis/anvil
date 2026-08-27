#!/usr/bin/env python3
"""M11 routing-probe planner (m11-routing-probes-spec.md launch pins in
scripts/choice_pins.py — imported, never redefined).

  plan    census worker dirs -> the EXHAUSTIVE point set (adjudicated
          2026-08-26): every active-player-forkable family window (probe
          T: tutor/dig SELECT_ONE, first event's ncand caps the arm
          fan-out; probe P: payCostToPreventEffect), one combined
          choicefile (T + P arms share a point's natural rolls when they
          collide on (g, t, seat)) + frame.json.
  lanes   split the choicefile across N lane TSVs (round-robin by game)
          + lane shell scripts replaying the census configuration with
          -forcechoice (obs/census/paytelemetry parity; the enriched-jar
          census output doubles as the src catalog).
  resume  scan lanes-*/lane-*.out*.jsonl, drop COMPLETE points (all arms
          incl. natural x all K rolls present; crash rows terminal) from
          the lane TSVs, rotate each lane's out file (the reader globs
          out*.jsonl generations). Kill lanes anytime; rollSeeds are
          point-keyed so a resume reproduces identical rolls.

Family classification mirrors m11_mining.py / ChoiceDirective.FAMILY —
the mined universe, the forced universe, and the rate multiplier are the
same universe by construction.

Usage:
  uv run python scripts/choice_plan.py plan \
      --workers data/runs/m10-ceiling-census-20260825-212414/workers \
      --out data/runs/choice-probes-m11
  uv run python scripts/choice_plan.py lanes \
      --plan data/runs/choice-probes-m11 --jar <enriched jar> \
      --pairs data/runs/m10-ceiling-census-pairs.tsv
  uv run python scripts/choice_plan.py resume --plan data/runs/choice-probes-m11
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import choice_pins as pins  # noqa: E402

SEARCH_RX = re.compile(r"[Ss]earch (?:your|their|his|her) librar")
DIG_RX = re.compile(r"[Ll]ook at the top")
T_CLASSES = ("chooseSingleCardForZoneChange", "chooseSingleEntityForEffect")


def seat_of(p: str) -> int:
    m = re.match(r"Anvil\((\d)\)", p or "")
    return int(m.group(1)) - 1 if m else -1


# ------------------------------------------------------------------ plan

def mine_points(workers: str) -> tuple[list[dict], dict]:
    """-> (points sorted (g, t), frame). Point: {g, t, seat, t_ncand
    (first family SELECT_ONE event's ncand; 0 = no T arms), p_window
    (bool)}. Active-player proxy: the seat holding the FIRST MAIN1
    chooseSpellAbilityToPlay window of (g, t)."""
    active: dict[tuple[int, int], str] = {}
    t_first: dict[tuple[int, int, str], int] = {}
    p_seen: set[tuple[int, int, str]] = set()
    frame = Counter()
    for cj in sorted(Path(workers).glob("inv-*/census.jsonl")):
        for ln in open(cj):
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            m = r.get("m")
            p = r.get("p") or ""
            if not p.startswith("Anvil("):
                continue
            key = (r.get("g"), r.get("t"))
            if m == "chooseSpellAbilityToPlay" and r.get("ph") == "MAIN1":
                active.setdefault(key, p)
            elif m in T_CLASSES:
                text = " ".join(str(r.get(k) or "")
                                for k in ("sa", "selectPrompt", "title"))
                nc = r.get("fetchList", r.get("optionList", 0)) or 0
                if (SEARCH_RX.search(text) or DIG_RX.search(text)) and nc >= 2:
                    frame["t_events"] += 1
                    t_first.setdefault((r["g"], r["t"], p), int(nc))
            elif m == "payCostToPreventEffect":
                frame["p_events"] += 1
                p_seen.add((r["g"], r["t"], p))

    points: dict[tuple[int, int, int], dict] = {}
    for (g, t, p), nc in t_first.items():
        if active.get((g, t)) != p:
            frame["t_not_forkable"] += 1
            continue
        points[(g, t, seat_of(p))] = {"g": g, "t": t, "seat": seat_of(p),
                                      "t_ncand": nc, "p_window": False}
    for (g, t, p) in p_seen:
        if active.get((g, t)) != p:
            frame["p_not_forkable"] += 1
            continue
        pt = points.setdefault((g, t, seat_of(p)),
                               {"g": g, "t": t, "seat": seat_of(p),
                                "t_ncand": 0, "p_window": False})
        pt["p_window"] = True
    out = sorted(points.values(), key=lambda r: (r["g"], r["t"]))
    frame.update({
        "points": len(out),
        "t_points": sum(1 for r in out if r["t_ncand"] >= 2),
        "p_points": sum(1 for r in out if r["p_window"]),
        "collide_points": sum(1 for r in out if r["t_ncand"] >= 2 and r["p_window"]),
    })
    return out, dict(frame)


def arms_of(pt: dict) -> list[tuple[int, str, str]]:
    """-> [(armId, kind, action)] for one point; ids stable from the spec:
    T arms first (1..min(ncand,cap)), then P arms."""
    arms = []
    aid = 0
    if pt["t_ncand"] >= 2:
        for idx in range(min(pt["t_ncand"], pins.T_ARM_CAP)):
            aid += 1
            arms.append((aid, "tutor", str(idx)))
    if pt["p_window"]:
        aid += 1
        arms.append((aid, "prevent", "pay"))
        aid += 1
        arms.append((aid, "prevent", "decline"))
    return arms


def plan(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    points, frame = mine_points(args.workers)
    n_arms = 0
    with open(out / "choice.tsv", "w") as f:
        f.write("# M11 routing-probe choicefile (choice_plan.py; exhaustive; "
                "pins choice_pins.py)\n")
        for pt in points:
            base = f"{pt['g']}\t{pt['t']}\t{pt['seat']}\t{pins.HORIZON}"
            for aid, kind, action in arms_of(pt):
                f.write(f"{base}\t{aid}\t{kind}\t{action}\n")
                n_arms += 1
    frame.update({
        "arms": n_arms,
        "completions_budget": (n_arms + len(points)) * pins.K_ROLLS,
        "pins": {k: getattr(pins, k) for k in dir(pins) if k.isupper()},
        "workers": args.workers,
    })
    (out / "frame.json").write_text(json.dumps(frame, indent=2,
                                               default=str) + "\n")
    with open(out / "points.jsonl", "w") as f:
        for pt in points:
            f.write(json.dumps(pt) + "\n")
    print(f"{len(points)} points, {n_arms} forced arms, "
          f"{frame['completions_budget']} completions budgeted -> {out}")


# ----------------------------------------------------------------- lanes

def lanes(args) -> None:
    plan_dir = Path(args.plan).resolve()
    lines = [ln for ln in (plan_dir / "choice.tsv").read_text().splitlines()
             if ln and not ln.startswith("#")]
    games = sorted({int(ln.split("\t", 1)[0]) for ln in lines})
    lane_games = {g: i % args.lanes for i, g in enumerate(games)}
    gui = Path(args.jar).resolve().parent.parent.parent / "forge-gui"
    outdir = plan_dir / "lanes"
    outdir.mkdir(exist_ok=True)
    for i in range(args.lanes):
        tsv = outdir / f"lane-{i}.tsv"
        with open(tsv, "w") as f:
            for ln in lines:
                if lane_games[int(ln.split("\t", 1)[0])] == i:
                    f.write(ln + "\n")
        scratch = outdir / f"lane-{i}.scratch"
        sh = outdir / f"lane-{i}.sh"
        sh.write_text(
            "#!/bin/sh\nset -e\n"
            f"cd '{gui}'\n"
            f"nice -n 19 java -Xms3g -Xmx3g -XX:ActiveProcessorCount=2 "
            f"-XX:+ExitOnOutOfMemoryError "
            f"-jar '{Path(args.jar).resolve()}' anvil "
            f"-pairs '{Path(args.pairs).resolve()}' -gpp 5 -f Commander "
            f"-range 0 {pins.CENSUS_GAMES} -seedbase {pins.CENSUS_SEED_BASE} "
            f"-b {args.bridge} "
            f"-obs '{scratch}.obs.zst' -census '{scratch}.census.jsonl' "
            f"-paytelemetry "
            f"-rollout {pins.K_ROLLS} -labels '{outdir}/lane-{i}.out.jsonl' "
            f"-forcechoice '{tsv}'\n")
        sh.chmod(0o755)
    print(f"{args.lanes} lanes -> {outdir} (games {len(games)}, rows {len(lines)})")


# ---------------------------------------------------------------- resume

def _planned(plan_dir: Path) -> dict[int, dict[tuple[int, int], int]]:
    """game -> {(t, armId) -> 1} incl. the implicit natural arm 0."""
    want: dict[int, dict[tuple[int, int], int]] = defaultdict(dict)
    turns_seen: set[tuple[int, int]] = set()
    for ln in (plan_dir / "choice.tsv").read_text().splitlines():
        if not ln or ln.startswith("#"):
            continue
        f = ln.split("\t")
        g, t, aid = int(f[0]), int(f[1]), int(f[4])
        want[g][(t, aid)] = 1
        if (g, t) not in turns_seen:
            turns_seen.add((g, t))
            want[g][(t, 0)] = 1
    return want


def resume(args) -> None:
    plan_dir = Path(args.plan).resolve()
    outdir = plan_dir / "lanes"
    want = _planned(plan_dir)
    have: dict[int, Counter] = defaultdict(Counter)
    skipped: set[tuple[int, int]] = set()
    for f in sorted(outdir.glob("lane-*.out*.jsonl")):
        for ln in open(f):
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("ev") != "choice":
                continue
            if "skip" in r:
                skipped.add((r["i"], r.get("tt", -1)))
                continue
            have[r["i"]][(r["t"], r["arm"], r["roll"])] += 1
    complete_games = set()
    for g, arms in want.items():
        need = {(t, a, r) for (t, a) in arms for r in range(pins.K_ROLLS)}
        done = set(have.get(g, Counter()))
        # a skipped point (drift/seat mismatch) never produces completions:
        # its turns count as terminally done
        skipped_turns = {t for (gg, t) in skipped if gg == g}
        need = {(t, a, r) for (t, a, r) in need if t not in skipped_turns}
        if need <= done:
            complete_games.add(g)
    total_games = len(want)
    print(f"complete games: {len(complete_games)}/{total_games}")
    if not (outdir / "lane-0.tsv").exists():
        sys.exit("FATAL: no lane TSVs — run lanes first")
    gen = 1 + max((int(m.group(1)) for f in outdir.glob("lane-*.out.*.jsonl")
                   for m in [re.search(r"out\.(\d+)\.jsonl$", f.name)] if m),
                  default=0)
    for tsv in sorted(outdir.glob("lane-*.tsv")):
        lines = [ln for ln in tsv.read_text().splitlines() if ln]
        keep = [ln for ln in lines
                if int(ln.split("\t", 1)[0]) not in complete_games]
        tsv.write_text("\n".join(keep) + ("\n" if keep else ""))
        outf = outdir / tsv.name.replace(".tsv", ".out.jsonl")
        if outf.exists():
            outf.rename(outdir / tsv.name.replace(".tsv", f".out.{gen}.jsonl"))
        print(f"  {tsv.name}: {len(lines)} -> {len(keep)} rows"
              + (" (out rotated)" if keep != lines or True else ""))
    print("rerun the lane scripts to continue; the reader globs out*.jsonl")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    sp = sub.add_parser("plan")
    sp.add_argument("--workers", required=True)
    sp.add_argument("--out", required=True)
    sp.set_defaults(fn=plan)
    lp = sub.add_parser("lanes")
    lp.add_argument("--plan", required=True)
    lp.add_argument("--lanes", type=int, default=pins.LANES)
    lp.add_argument("--jar", required=True)
    lp.add_argument("--pairs", required=True)
    lp.add_argument("--bridge", default="grpc:localhost:50065")
    lp.set_defaults(fn=lanes)
    rp = sub.add_parser("resume")
    rp.add_argument("--plan", required=True)
    rp.set_defaults(fn=resume)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
