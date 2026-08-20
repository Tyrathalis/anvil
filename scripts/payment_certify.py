#!/usr/bin/env python3
"""M9 rung 3: payment-drill certification driver + reader
(m9-rung3-draft.md, session-pinned protocol).

Three subcommands around the fork-side certify mode (CensusRun -certify):

  plan   mined candidates -> jobs.jsonl (+ lane scripts). Top-N per shape;
         deck pair + base seed joined from the census run's lane-*.sh (the
         provenance shim — candidates carry the absolute per-game seed, the
         lane scripts carry the deck pair per pair-file).
  read   certify rows (the Java contract: one line per (job, arm, roll)) ->
         certified-drills.jsonl via per-shape predicates. Arm 0 = auto is
         the paired baseline (the D2.4 rule); an option certifies iff its
         shape-score margin over arm 0 clears the threshold with k-roll
         sign consistency. Deterministic shapes run k=1.

Per-shape scoring (axes over the horizon snapshot, payer-perspective):
  forced_chain     deterministic: certified iff some arm>0 fired
                   directed_ok (the payment auto cannot construct happened).
  blocker_pressure life preserved + creatures kept vs arm 0.
  color_hold       development: hand spent + board added vs arm 0 (a later
                   castable spell shows as hand-down/board-up).
  wide_choice      any-axis max |delta| vs arm 0.
  phyrexian        life vs development trade (min_life arm vs life-pay arm).

Thresholds are certification-instrument constants (below), tunable at the
certification-run read with a recorded reason — they gate what enters the
evalset, never anything in training.
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

# per-shape (k rolls, margin threshold on the shape score)
SHAPE_K = {"forced_chain": 1, "blocker_pressure": 8, "color_hold": 8, "wide_choice": 8}
MARGIN = {"blocker_pressure": 2.0, "color_hold": 2.0, "wide_choice": 3.0}
CONSISTENT = 0.75  # fraction of rolls agreeing in sign for a k>1 certification
HORIZON = 2
DEFAULT_PER_SHAPE = 40


_CMD = re.compile(
    r"-d '([^']+)' '([^']+)' .*?-s (\d+) -o '([^']*/(pair-\d+)\.jsonl)\.tmp'"
)


def lane_index(census_dir: Path) -> dict:
    """pair-name -> (deck1, deck2, base_seed) from the run's lane scripts."""
    out = {}
    for lane in sorted(census_dir.glob("lane-*.sh")):
        for m in _CMD.finditer(lane.read_text()):
            out[m.group(5)] = (m.group(1), m.group(2), int(m.group(3)))
    return out


def plan(args) -> None:
    census_dir = Path(args.candidates).parent
    lanes = lane_index(census_dir)
    if not lanes:
        raise SystemExit(f"no lane-*.sh next to {args.candidates} — provenance shim needs them")

    by_shape: dict[str, list] = defaultdict(list)
    for line in open(args.candidates):
        c = json.loads(line)
        for t in c["tags"]:
            by_shape[t].append(c)

    # shape priority: forced first (6 exist, all precious), then the named
    # shapes; a multi-tag window fills the highest-priority shape's quota.
    # Quotas fill from the full ranked list — tag overlap must not starve
    # later shapes (the first cut sliced top-40 and color_hold got 1).
    order = ["forced_chain", "blocker_pressure", "color_hold", "wide_choice"]
    jobs, seen = [], set()
    for shape in [s for s in order if s in by_shape] + sorted(set(by_shape) - set(order)):
        added = 0
        for c in by_shape[shape]:
            if added >= args.per_shape:
                break
            key = (c["source"], c["g"], c["t"], c["sa"])
            if key in seen:
                continue
            seen.add(key)
            added += 1
            pair = Path(c["source"]).stem
            if pair not in lanes:
                continue
            d1, d2, _base = lanes[pair]
            jobs.append({
                "job": len(jobs), "shape": shape, "seed": c["seed"],
                "deck1": d1, "deck2": d2, "p": c["p"], "t": c["t"],
                "sa": c["sa"], "ord": 0,
                "arms": min(int(c.get("goals", 1)), 9),
                "k": SHAPE_K.get(shape, 8), "horizon": HORIZON,
                # provenance (ignored by the Java side, joined back at read)
                "source": c["source"], "g": c["g"], "tags": c["tags"],
            })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        for j in jobs:
            f.write(json.dumps(j) + "\n")
    n_by = defaultdict(int)
    for j in jobs:
        n_by[j["shape"]] += 1
    print(f"planned {len(jobs)} jobs -> {out}")
    for s, n in sorted(n_by.items()):
        print(f"  {s:<18} {n}")


def _payer_seat(row: dict, job: dict) -> int:
    # census player names carry the deck stem: "Census(1)-dc-864792" is seat 0
    return 0 if job["deck1"].removesuffix(".dck") in job["p"] else 1


def _axes(row: dict, seat: int) -> dict:
    s = row["snap"]
    o = 1 - seat
    return {
        "life": s["life"][seat] - s["life"][o],
        "creatures": s["creatures"][seat],
        "power": s["power"][seat],
        "dev": s["creatures"][seat] + s["lands"][seat] - s["hand"][seat],
        "won": 1 if row.get("winner") == seat else (-1 if row.get("winner") == o else 0),
    }


def _score(shape: str, ax: dict, base: dict) -> float:
    d = {k: ax[k] - base[k] for k in ax}
    if shape == "blocker_pressure":
        return d["life"] + d["creatures"] + 0.5 * d["power"] + 3 * d["won"]
    if shape == "color_hold":
        return d["dev"] + 0.5 * d["life"] + 3 * d["won"]
    return max(d.values(), key=abs)  # wide_choice: dominant axis


def read(args) -> None:
    jobs = {j["job"]: j for j in map(json.loads, open(args.jobs))}
    rows: dict[tuple, list] = defaultdict(list)  # (job, arm) -> [roll rows]
    exec_n: dict[str, int] = defaultdict(int)
    why_n: dict[str, int] = defaultdict(int)  # salvage failure points (exec_why)
    for line in open(args.certout):
        r = json.loads(line)
        if r.get("ev") == "certify":
            rows[(r["job"], r["arm"])].append(r)
            if r["arm"] > 0 and r.get("fired"):
                exec_n[r.get("exec", "?")] += 1
                if r.get("exec_why"):
                    why_n[r["exec_why"]] += 1

    certified, stats = [], defaultdict(int)
    for jid, job in jobs.items():
        arms = sorted(a for (j, a) in rows if j == jid)
        base_rolls = rows.get((jid, 0), [])
        if not base_rolls:
            stats["no_baseline"] += 1
            continue
        seat = _payer_seat(base_rolls[0], job)
        shape = job["shape"]

        if shape == "forced_chain":
            ok = [a for a in arms if a > 0 and any(
                r["fired"] and r["exec"] == "directed_ok" for r in rows[(jid, a)])]
            if ok:
                certified.append({**_prov(job), "shape": shape, "best": ok[0],
                                  "margin": None, "k": 1})
                stats["certified"] += 1
            else:
                stats["failed_predicate"] += 1
            continue

        best, best_margin = None, 0.0
        for a in arms:
            if a == 0:
                continue
            # only faithfully-executed arms certify: a salvage means the
            # composition partially failed and auto completed — the drill's
            # "do X" is unverified (salvage rate is its own finding, spec §7)
            paired = [
                (_score(shape, _axes(r, seat), _axes(b, seat)))
                for r, b in zip(
                    sorted(rows[(jid, a)], key=lambda x: x["roll"]),
                    sorted(base_rolls, key=lambda x: x["roll"]),
                )
                if r["fired"] and r.get("exec") == "directed_ok"
            ]
            if not paired:
                continue
            mean = sum(paired) / len(paired)
            agree = sum(1 for s in paired if (s > 0) == (mean > 0)) / len(paired)
            if abs(mean) >= MARGIN.get(shape, 2.0) and agree >= CONSISTENT and abs(mean) > abs(best_margin):
                best, best_margin = a, mean
        if best is not None and best_margin > 0:
            certified.append({**_prov(job), "shape": shape, "best": best,
                              "margin": round(best_margin, 3), "k": job["k"]})
            stats["certified"] += 1
        else:
            stats["failed_predicate"] += 1

    with open(args.out, "w") as f:
        for c in certified:
            f.write(json.dumps(c) + "\n")
    print(f"certified {stats['certified']} / {len(jobs)} jobs -> {args.out}")
    for k, v in sorted(stats.items()):
        print(f"  {k:<18} {v}")
    n_directed = sum(exec_n.values())
    n_salvage = exec_n.get("directed_salvage", 0) + exec_n.get("directed_fail", 0)
    if n_directed:
        rate = n_salvage / n_directed
        gate = "FIRED" if rate > 0.01 else "ok"
        print(f"  salvage gate (>1%): {rate:.4f} on {n_directed} directed rows [{gate}]")
        for k, v in sorted(exec_n.items()):
            print(f"    {k:<18} {v}")
    if why_n:
        print("  salvage failure points (exec_why):")
        for k, v in sorted(why_n.items(), key=lambda kv: -kv[1])[:12]:
            print(f"    {v:>5}  {k}")


def _prov(job: dict) -> dict:
    return {k: job[k] for k in ("job", "source", "g", "seed", "p", "t", "sa", "tags")}


# the Java-side jobs contract (CensusRun -certify's flat parser accepts
# EXACTLY these; provenance stays in the master jobs file, joined at read)
JAVA_JOB_FIELDS = ("job", "seed", "deck1", "deck2", "p", "t", "sa", "ord", "arms", "k", "horizon")


def lanes(args) -> None:
    """Split jobs across N lane scripts invoking the certify CLI."""
    jobs = [json.loads(x) for x in open(args.jobs)]
    outdir = Path(args.jobs).parent
    for i in range(args.n):
        chunk = jobs[i:: args.n]
        jf = outdir / f"certify-lane-{i}.jobs.jsonl"
        with open(jf, "w") as f:
            for j in chunk:
                f.write(json.dumps({k: j[k] for k in JAVA_JOB_FIELDS}) + "\n")
        sh = outdir / f"certify-lane-{i}.sh"
        # cwd must be the fork's forge-gui (res bundles resolve relative to
        # it; a wrong cwd dies in FModel.initialize on the locale bundle)
        gui = Path(args.jar).resolve().parent.parent.parent / "forge-gui"
        sh.write_text(
            "#!/bin/sh\nset -e\n"
            f"cd '{gui}'\n"
            f"nice -n 19 java -Xms1g -Xmx2g -XX:ActiveProcessorCount=2 -jar '{args.jar}' "
            f"census -f Commander -paytelemetry -certify '{jf}' "
            f"-certout '{outdir}/certify-lane-{i}.out.jsonl'\n"
        )
        sh.chmod(0o755)
    print(f"wrote {args.n} lane scripts under {outdir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("candidates")
    p.add_argument("--out", required=True)
    p.add_argument("--per-shape", type=int, default=DEFAULT_PER_SHAPE)
    p.set_defaults(fn=plan)
    r = sub.add_parser("read")
    r.add_argument("--jobs", required=True)
    r.add_argument("--certout", required=True)
    r.add_argument("--out", required=True)
    r.set_defaults(fn=read)
    n = sub.add_parser("lanes")
    n.add_argument("--jobs", required=True)
    n.add_argument("--jar", required=True)
    n.add_argument("-n", type=int, default=4)
    n.set_defaults(fn=lanes)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
