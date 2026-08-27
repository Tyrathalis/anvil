#!/usr/bin/env python3
"""M11 `-forcechoice` mechanical smoke (m11-routing-probes-spec.md engine
delta; the schedule_smoke.py precedent verbatim).

SERVE-FREE mechanics gate under `-b local-oneshot` (random-legal one-shot,
deterministic per seed): validates the ChoiceDirective machinery — family
window matching, index forcing, idx_oob miss, pay/decline forcing, trace
schema, rollSeed pairing, natural-arm purity, re-run determinism — NOT
model behavior and NOT window-recurrence rates (post-fork play diverges by
roll rng, so a directive firing is chancy per roll; the smoke asserts each
kind fires SOMEWHERE, not everywhere).

Phases:
  mine    play N games with -census; mine (g, t, seat) points where a seat
          saw a family SELECT_ONE window (tutor) or a payCostToPreventEffect
          window (prevent) on its own turn (own-turn proxy: the seat holds a
          MAIN1 chooseSpellAbilityToPlay window at the same (g, t)).
  arm     write smoke.choice —
            tutor points:   1 tutor 0 | 2 tutor 1 (ncand >= 2) | 3 tutor 99
                            (must fire-with-miss idx_oob when it fires)
            prevent points: 1 prevent pay | 2 prevent decline
  run     replay with -forcechoice -rollout K, twice (labels1/labels2).
  check   trace expectations + row accounting + byte-determinism (ms
          stripped); nonzero exit on any hard failure.

Usage:
  uv run python scripts/choice_smoke.py \
      --jar .../forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar \
      --out data/runs/choice-smoke-m11
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schedule_smoke import load_rows, run_jar, strip_ms  # noqa: E402

# Mirrors ChoiceDirective.FAMILY / m11_mining.py exactly.
FAMILY = re.compile(r"[Ss]earch (?:your|their|his|her) librar|[Ll]ook at the top")
T_CLASSES = ("chooseSingleCardForZoneChange", "chooseSingleEntityForEffect")

DEFAULT_JAR = ("/home/tyrathalis/Everything/Projects/forge/forge-gui-desktop/"
               "target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar")


def mine(census_path: Path, want_each: int) -> tuple[list[dict], list[dict]]:
    """-> (tutor points, prevent points): [{g, t, seat, ncand}]. Own-turn
    proxy: the seat holds a MAIN1 chooseSpellAbilityToPlay window at (g, t)."""
    main1 = set()  # (g, t, player) with a MAIN1 cast window
    tutor_raw, prevent_raw = [], []
    for line in open(census_path):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = r.get("m")
        p = r.get("p") or ""
        if not p.startswith("Anvil("):
            continue
        if m == "chooseSpellAbilityToPlay" and r.get("ph") == "MAIN1":
            main1.add((r["g"], r["t"], p))
        elif m in T_CLASSES:
            text = " ".join(str(r.get(k) or "")
                            for k in ("sa", "selectPrompt", "title"))
            ncand = r.get("fetchList", r.get("optionList", 0)) or 0
            if FAMILY.search(text) and ncand >= 2:
                tutor_raw.append({"g": r["g"], "t": r["t"], "p": p,
                                  "ncand": int(ncand)})
        elif m == "payCostToPreventEffect":
            prevent_raw.append({"g": r["g"], "t": r["t"], "p": p})

    def pick(raw: list[dict], n: int) -> list[dict]:
        out, seen = [], set()
        for r in raw:
            key = (r["g"], r["t"])
            if key in seen or (r["g"], r["t"], r["p"]) not in main1:
                continue
            seen.add(key)
            seat = int(r["p"][r["p"].index("(") + 1]) - 1
            out.append({"g": r["g"], "t": r["t"], "seat": seat,
                        "ncand": r.get("ncand", 0)})
            if len(out) >= n:
                break
        return out

    return pick(tutor_raw, want_each), pick(prevent_raw, want_each)


def write_choice(tutor: list[dict], prevent: list[dict], path: Path,
                 horizon: int) -> None:
    with open(path, "w") as f:
        f.write("# M11 -forcechoice smoke jobs (choice_smoke.py)\n")
        for pt in tutor:
            base = f"{pt['g']}\t{pt['t']}\t{pt['seat']}\t{horizon}"
            f.write(f"{base}\t1\ttutor\t0\n")
            if pt["ncand"] >= 2:
                f.write(f"{base}\t2\ttutor\t1\n")
            f.write(f"{base}\t3\ttutor\t99\n")
        for pt in prevent:
            base = f"{pt['g']}\t{pt['t']}\t{pt['seat']}\t{horizon}"
            f.write(f"{base}\t1\tprevent\tpay\n")
            f.write(f"{base}\t2\tprevent\tdecline\n")


def check(tutor: list[dict], prevent: list[dict], rows1: list[dict],
          rows2: list[dict], k: int) -> list[str]:
    fails: list[str] = []
    rows = [r for r in rows1 if r.get("ev") == "choice"]
    skips = [r for r in rows if "skip" in r]
    comp = [r for r in rows if "skip" not in r]
    print(f"rows: {len(rows)} choice ({len(skips)} skip, {len(comp)} completions)")
    for s in skips:
        print(f"  SKIP g{s['i']} t{s.get('tt')}: {s['skip']}")
    if not comp:
        fails.append("no completions at all")
        return fails
    tutor_pts = {(p["g"], p["t"]) for p in tutor}
    prevent_pts = {(p["g"], p["t"]) for p in prevent}
    by_point = defaultdict(lambda: defaultdict(list))
    for r in comp:
        by_point[(r["i"], r["t"])][r["arm"]].append(r)
    fired_tutor = fired_oob = fired_pay = fired_decline = 0
    for key, arms in sorted(by_point.items()):
        if key not in tutor_pts and key not in prevent_pts:
            fails.append(f"rows for unplanned point {key}")
            continue
        for arm, rr in sorted(arms.items()):
            if len(rr) != k:
                fails.append(f"point {key} arm {arm}: {len(rr)} rows != k={k}")
            fired = [r for r in rr if r.get("fired")]
            crashes = sum(1 for r in rr if r.get("crash"))
            print(f"  point {key} arm {arm} "
                  f"({rr[0].get('kind', 'nat')}/{rr[0].get('act', '-')}): "
                  f"k={len(rr)} crash={crashes} fired={len(fired)} "
                  f"chosen={[r.get('chosen') for r in fired] or '-'} "
                  f"miss={[r.get('miss') for r in fired if r.get('miss')] or '-'}")
            if arm == 0:
                if any("fired" in r or "kind" in r for r in rr):
                    fails.append(f"point {key}: natural rows carry directive fields")
                continue
            for r in fired:
                if r.get("kind") == "tutor":
                    if r.get("act") == 99:
                        fired_oob += 1
                        if r.get("miss") != "idx_oob":
                            fails.append(f"point {key} arm {arm}: idx-99 fired "
                                         f"without idx_oob miss: {r.get('miss')}")
                    else:
                        fired_tutor += 1
                        if not r.get("chosen") or r.get("ncand", 0) < 1:
                            fails.append(f"point {key} arm {arm}: fired tutor row "
                                         f"missing chosen/ncand")
                elif r.get("kind") == "prevent":
                    if r.get("act") == 1:
                        fired_pay += 1
                        if r.get("chosen") != "pay":
                            fails.append(f"point {key} arm {arm}: pay arm chose "
                                         f"{r.get('chosen')}")
                    else:
                        fired_decline += 1
                        if r.get("chosen") != "decline" or r.get("pay_ok"):
                            fails.append(f"point {key} arm {arm}: decline arm "
                                         f"chose {r.get('chosen')} pay_ok="
                                         f"{r.get('pay_ok')}")
        for roll in range(k):
            seeds = {r["rollseed"] for a in arms.values() for r in a
                     if r["roll"] == roll}
            if len(seeds) > 1:
                fails.append(f"point {key} roll {roll}: rollSeeds not paired {seeds}")
    print(f"fired totals: tutor={fired_tutor} oob={fired_oob} "
          f"pay={fired_pay} decline={fired_decline}")
    if tutor and (fired_tutor == 0 or fired_oob == 0):
        fails.append("no tutor (or no idx_oob) firing anywhere — raise --games")
    if prevent and (fired_pay == 0 or fired_decline == 0):
        fails.append("no prevent pay/decline firing anywhere — raise --games")
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
    ap.add_argument("--out", default="data/runs/choice-smoke-m11")
    ap.add_argument("--decks", nargs=2, default=["dc-864792.dck", "dc-864158.dck"])
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260826)
    ap.add_argument("--points", type=int, default=3)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--horizon", type=int, default=2)
    args = ap.parse_args()

    if not os.environ.get("DISPLAY"):
        print("WARNING: DISPLAY unset — forge jars exit silently without it")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    census = out / "mine-census.jsonl"
    if census.exists():
        census.unlink()
    print(f"[mine] {args.games} games, seed base {args.seed} ...")
    run_jar(args.jar, ["-d", args.decks[0], args.decks[1], "-f", "Commander",
                       "-n", str(args.games), "-s", str(args.seed),
                       "-b", "local-oneshot", "-census", str(census)],
            out / "mine.log")
    tutor, prevent = mine(census, args.points)
    if not tutor or not prevent:
        sys.exit(f"FATAL: mined {len(tutor)} tutor / {len(prevent)} prevent "
                 f"points — raise --games")
    for p in tutor:
        print(f"[mine] tutor   g{p['g']} t{p['t']} seat{p['seat']} ncand={p['ncand']}")
    for p in prevent:
        print(f"[mine] prevent g{p['g']} t{p['t']} seat{p['seat']}")

    choice = out / "smoke.choice"
    write_choice(tutor, prevent, choice, args.horizon)
    print(f"[arm] {choice}")

    for i in (1, 2):
        lbl = out / f"smoke-labels-{i}.jsonl"
        if lbl.exists():
            lbl.unlink()
        print(f"[run {i}] -forcechoice, k={args.k} ...")
        run_jar(args.jar, ["-d", args.decks[0], args.decks[1], "-f", "Commander",
                           "-n", str(args.games), "-s", str(args.seed),
                           "-b", "local-oneshot", "-rollout", str(args.k),
                           "-labels", str(lbl), "-forcechoice", str(choice)],
                out / f"run-{i}.log")

    rows1 = load_rows(out / "smoke-labels-1.jsonl")
    rows2 = load_rows(out / "smoke-labels-2.jsonl")
    fails = check(tutor, prevent, rows1, rows2, args.k)
    if fails:
        print("\nSMOKE FAILED:")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)
    print("\nSMOKE PASSED")


if __name__ == "__main__":
    main()
