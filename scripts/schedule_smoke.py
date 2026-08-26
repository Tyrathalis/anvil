#!/usr/bin/env python3
"""M10 `-forceschedule` mechanical smoke (m10-ceiling-spec.md "Engine build
owed": 3 turns replayed end-to-end, directive traces validated, margins —
here full rows — reproduced across a re-run; the ADR-0073 smoke precedent).

This is the SERVE-FREE mechanics gate: games run under `-b local-oneshot`
(random-legal through the one-shot path, deterministic per seed), so it
validates the directive machinery — forced ordered casts, land-first,
degrade-and-count, hold-all, schedule-consistent payment plumbing, trace
schema, rollSeed pairing, horizon stop, re-run determinism — NOT model
behavior. The model-serve smoke rides the fresh census at launch.

Phases:
  mine    play N games with -census, mine turns where a seat realized >= 2
          MAIN-phase schedulable casts; pick the first --turns such turns.
  arm     write smoke.sched: per mined turn, 5 arms —
            1 joint  [c1, c2]   (as-played order)
            2 joint  [c2, c1]   (reversed)
            3 joint  []         (hold-all)
            4 joint  [bogus]    (must degrade:absent + void)
            5 auto   [c1, c2]   (marginal-stratum payment path)
  run     replay with -forceschedule -rollout K, twice (labels1/labels2).
  check   trace expectations + row accounting + byte-determinism
          (ms fields stripped); nonzero exit on any hard failure.

Usage:
  uv run python scripts/schedule_smoke.py \
      --jar /home/tyrathalis/Everything/Projects/forge/forge-gui-desktop/target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar \
      --out data/runs/sched-smoke-m10
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

MANA_ABILITY = re.compile(r"Add \{")
LAND_HINT = re.compile(r"[Pp]lay land|^Land ")

DEFAULT_JAR = ("/home/tyrathalis/Everything/Projects/forge/forge-gui-desktop/"
               "target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar")
BOGUS = "Smoke Bogus Card - this label matches nothing"


def run_jar(jar: str, args: list[str], log: Path) -> None:
    cmd = ["java", "-Xms1g", "-Xmx2g", "-XX:ActiveProcessorCount=2",
           "-jar", jar, "anvil"] + args
    with open(log, "w") as lf:
        lf.write("+ " + " ".join(cmd) + "\n")
        lf.flush()
        r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                           cwd=str(Path(jar).parents[2] / "forge-gui"))
    if r.returncode != 0:
        sys.exit(f"FATAL: jar run failed (exit {r.returncode}) — see {log}")


def schedulable(sa: str) -> bool:
    return not MANA_ABILITY.search(sa) and not LAND_HINT.search(sa)


def mine(census_path: Path, want_turns: int) -> list[dict]:
    """-> [{g, t, seat, casts:[labels...]}] for the first turns with >= 2
    realized MAIN-phase schedulable casts by one bridged seat."""
    per = defaultdict(list)  # (g, t, player) -> [labels]
    for line in open(census_path):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("m") != "chooseSpellAbilityToPlay" or r.get("by") != "bridge":
            continue
        if r.get("veto") or r.get("oor"):
            continue
        pick = r.get("pick")
        if not pick or pick == "pass":
            continue
        if r.get("ph") not in ("MAIN1", "MAIN2"):
            continue
        p = r.get("p") or ""
        if not p.startswith("Anvil("):
            continue
        if not schedulable(pick):
            continue
        per[(r["g"], r["t"], p)].append(pick)
    picked = []
    for (g, t, p), casts in sorted(per.items()):
        if len(casts) >= 2:
            seat = int(p[p.index("(") + 1]) - 1
            picked.append({"g": g, "t": t, "seat": seat, "player": p,
                           "casts": casts[:3]})
        if len(picked) >= want_turns:
            break
    return picked


def write_sched(points: list[dict], path: Path, horizon: int) -> None:
    with open(path, "w") as f:
        f.write("# M10 -forceschedule smoke jobs (schedule_smoke.py)\n")
        for pt in points:
            c = pt["casts"]
            for label in c + [BOGUS]:
                assert "\t" not in label and "\n" not in label
            base = f"{pt['g']}\t{pt['t']}\t{horizon}\t{pt['seat']}"
            f.write(f"{base}\t1\tjoint\t" + "\t".join(c[:2]) + "\n")
            f.write(f"{base}\t2\tjoint\t" + "\t".join(reversed(c[:2])) + "\n")
            f.write(f"{base}\t3\tjoint\n")
            f.write(f"{base}\t4\tjoint\t{BOGUS}\n")
            f.write(f"{base}\t5\tauto\t" + "\t".join(c[:2]) + "\n")


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))  # a parse error IS a smoke failure
    return rows


def strip_ms(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if k != "ms"} for r in rows]


def check(points: list[dict], rows1: list[dict], rows2: list[dict],
          k: int) -> list[str]:
    fails: list[str] = []
    sched = [r for r in rows1 if r.get("ev") == "sched"]
    skips = [r for r in sched if "skip" in r]
    comp = [r for r in sched if "skip" not in r]
    print(f"rows: {len(sched)} sched ({len(skips)} skip, {len(comp)} completions)")
    for s in skips:
        print(f"  SKIP g{s['i']} t{s.get('tt')}: {s['skip']}")
    if not comp:
        fails.append("no completions at all")
        return fails
    by_point = defaultdict(lambda: defaultdict(list))  # (i,t) -> arm -> rows
    for r in comp:
        by_point[(r["i"], r["t"])][r["arm"]].append(r)
    live_points = {(p["g"], p["t"]) for p in points}
    for key, arms in sorted(by_point.items()):
        if key not in live_points:
            fails.append(f"rows for unplanned point {key}")
        expect_arms = {0, 1, 2, 3, 4, 5}
        if set(arms) != expect_arms:
            fails.append(f"point {key}: arms {sorted(arms)} != {sorted(expect_arms)}")
        for arm, rr in sorted(arms.items()):
            if len(rr) != k:
                fails.append(f"point {key} arm {arm}: {len(rr)} rows != k={k}")
            crashes = sum(1 for r in rr if r.get("crash"))
            execs = [r.get("exec") for r in rr if "exec" in r]
            degr = [r.get("degrade_why") for r in rr if r.get("degrade_why")]
            voids = sum(1 for r in rr if r.get("void"))
            stops = sum(1 for r in rr if r.get("stopped"))
            pays = [r.get("pay") for r in rr if r.get("pay")]
            print(f"  point {key} arm {arm}: k={len(rr)} crash={crashes} "
                  f"stopped={stops} exec={execs or '-'} void={voids} "
                  f"degrade={degr or '-'} "
                  f"pay={pays[0] if pays else '-'}")
            if arm == 0:
                if any("exec" in r for r in rr):
                    fails.append(f"point {key}: natural rows carry directive fields")
            if arm == 3:  # hold-all: never void, executes nothing
                if voids or any(e not in (0, None) for e in execs):
                    fails.append(f"point {key} arm 3: hold-all executed or voided")
            if arm == 4:  # bogus: every non-crash row degrades absent + void
                ok = [r for r in rr if not r.get("crash")]
                if not all(r.get("degrade_why") == "absent" and r.get("void")
                           for r in ok):
                    fails.append(f"point {key} arm 4: bogus arm did not degrade:absent+void")
        # rollSeed pairing: same roll => same rollseed across arms
        for roll in range(k):
            seeds = {r["rollseed"] for a in arms.values() for r in a
                     if r["roll"] == roll}
            if len(seeds) > 1:
                fails.append(f"point {key} roll {roll}: rollSeeds not paired {seeds}")
    # at least one directed arm must actually execute a step somewhere
    if not any(r.get("exec", 0) > 0 for r in comp):
        fails.append("no directed arm executed any scheduled step anywhere")
    # determinism across the re-run
    if strip_ms(rows1) != strip_ms(rows2):
        a, b = strip_ms(rows1), strip_ms(rows2)
        diff = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
        fails.append(f"re-run rows differ ({diff} rows) — determinism broken")
    else:
        print("re-run: byte-identical modulo ms — determinism holds")
    return fails


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", default=DEFAULT_JAR)
    ap.add_argument("--out", default="data/runs/sched-smoke-m10")
    ap.add_argument("--decks", nargs=2, default=["dc-864792.dck", "dc-864158.dck"])
    ap.add_argument("--games", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260825)
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--horizon", type=int, default=2)
    args = ap.parse_args()

    if not os.environ.get("DISPLAY"):
        print("WARNING: DISPLAY unset — forge jars exit silently without it")
    out = Path(args.out).resolve()  # the jar runs with cwd=forge-gui
    out.mkdir(parents=True, exist_ok=True)

    census = out / "mine-census.jsonl"
    if census.exists():
        census.unlink()
    print(f"[mine] {args.games} games, seed base {args.seed} ...")
    run_jar(args.jar, ["-d", args.decks[0], args.decks[1], "-f", "Commander",
                       "-n", str(args.games), "-s", str(args.seed),
                       "-b", "local-oneshot", "-census", str(census)],
            out / "mine.log")
    points = mine(census, args.turns)
    if len(points) < args.turns:
        sys.exit(f"FATAL: only {len(points)} multi-cast turns mined "
                 f"(wanted {args.turns}) — raise --games")
    for p in points:
        print(f"[mine] g{p['g']} t{p['t']} seat{p['seat']}: {p['casts']}")

    sched = out / "smoke.sched"
    write_sched(points, sched, args.horizon)
    print(f"[arm] {sched}")

    for i in (1, 2):
        lbl = out / f"smoke-labels-{i}.jsonl"
        if lbl.exists():
            lbl.unlink()
        print(f"[run {i}] -forceschedule, k={args.k} ...")
        run_jar(args.jar, ["-d", args.decks[0], args.decks[1], "-f", "Commander",
                           "-n", str(args.games), "-s", str(args.seed),
                           "-b", "local-oneshot", "-rollout", str(args.k),
                           "-labels", str(lbl), "-forceschedule", str(sched)],
                out / f"run-{i}.log")

    rows1 = load_rows(out / "smoke-labels-1.jsonl")
    rows2 = load_rows(out / "smoke-labels-2.jsonl")
    fails = check(points, rows1, rows2, args.k)
    if fails:
        print("\nSMOKE FAILED:")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)
    print("\nSMOKE PASSED")


if __name__ == "__main__":
    main()
