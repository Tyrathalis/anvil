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


def _window_key(c: dict) -> tuple:
    return (c["source"], c["g"], c["t"], c["sa"])


def plan(args) -> None:
    census_dir = Path(args.candidates).parent
    lanes = lane_index(census_dir)
    if not lanes:
        raise SystemExit(f"no lane-*.sh next to {args.candidates} — provenance shim needs them")

    # windows already certified in prior batches are excluded (scale runs
    # take the NEXT slice of the ranked pool, never re-run a window)
    seen: set[tuple] = set()
    for prior in getattr(args, "exclude", None) or []:
        for j in map(json.loads, open(prior)):
            seen.add(_window_key(j))
    if seen:
        print(f"excluding {len(seen)} previously-planned windows")

    # per-shape counts: --counts "blocker_pressure=240,color_hold=240"
    # overrides --per-shape for the named shapes
    counts: dict[str, int] = {}
    for part in (getattr(args, "counts", None) or "").split(","):
        if part:
            s, n = part.split("=")
            counts[s] = int(n)

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
    jobs = []
    for shape in [s for s in order if s in by_shape] + sorted(set(by_shape) - set(order)):
        added = 0
        quota = counts.get(shape, args.per_shape)
        for c in by_shape[shape]:
            if added >= quota:
                break
            key = _window_key(c)
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

    certified, auto_correct, stats = [], [], defaultdict(int)
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

        cleared_pos: list[tuple] = []  # (mean, arm) clearing threshold+consistency
        cleared_neg: list[tuple] = []
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
            if abs(mean) >= MARGIN.get(shape, 2.0) and agree >= CONSISTENT:
                (cleared_pos if mean > 0 else cleared_neg).append((mean, a))
        if cleared_pos:
            # best = largest POSITIVE margin (a stronger negative arm on the
            # same job must not mask a cleared positive one)
            best_margin, best = max(cleared_pos)
            certified.append({**_prov(job), "shape": shape, "kind": "positive",
                              "best": best, "margin": round(best_margin, 3),
                              "k": job["k"]})
            stats["certified"] += 1
        else:
            stats["failed_predicate"] += 1
            if cleared_neg:
                # auto-correct drill: every cleared deviation consistently
                # LOSES to auto — engine-adjudicated evidence that auto is the
                # certified-best class here (evalset-assembly pin 2026-08-20:
                # D4's failure modes are two-sided — never-deviates AND
                # deviates-wrongly; scored as a SEPARATE metric so the
                # auto-biased init cannot inflate the headline accuracy)
                worst_margin, worst = min(cleared_neg)
                auto_correct.append({**_prov(job), "shape": shape,
                                     "kind": "auto_correct", "best": 0,
                                     "worst": worst,
                                     "margin": round(worst_margin, 3),
                                     "k": job["k"]})
                stats["auto_correct"] += 1

    with open(args.out, "w") as f:
        for c in certified:
            f.write(json.dumps(c) + "\n")
    ac_out = getattr(args, "autocorrect_out", None) or str(
        Path(args.out).parent / "autocorrect-drills.jsonl")
    with open(ac_out, "w") as f:
        for c in auto_correct:
            f.write(json.dumps(c) + "\n")
    print(f"certified {stats['certified']} / {len(jobs)} jobs -> {args.out}")
    print(f"auto-correct {stats['auto_correct']} jobs -> {ac_out}")
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
    """Split jobs across N lane scripts invoking the certify CLI. Lane
    filenames derive from the jobs-file stem ("certify2-jobs.jsonl" ->
    certify2-lane-*) so a second batch never clobbers a banked one."""
    jobs = [json.loads(x) for x in open(args.jobs)]
    # absolute: the lane scripts cd to forge-gui before running the jar
    outdir = Path(args.jobs).resolve().parent
    prefix = Path(args.jobs).stem.removesuffix(".jobs").removesuffix("-jobs")
    for i in range(args.n):
        chunk = jobs[i:: args.n]
        jf = outdir / f"{prefix}-lane-{i}.jobs.jsonl"
        with open(jf, "w") as f:
            for j in chunk:
                f.write(json.dumps({k: j[k] for k in JAVA_JOB_FIELDS}) + "\n")
        sh = outdir / f"{prefix}-lane-{i}.sh"
        # cwd must be the fork's forge-gui (res bundles resolve relative to
        # it; a wrong cwd dies in FModel.initialize on the locale bundle)
        gui = Path(args.jar).resolve().parent.parent.parent / "forge-gui"
        sh.write_text(
            "#!/bin/sh\nset -e\n"
            f"cd '{gui}'\n"
            f"nice -n 19 java -Xms1g -Xmx2g -XX:ActiveProcessorCount=2 -jar '{args.jar}' "
            f"census -f Commander -paytelemetry -certify '{jf}' "
            f"-certout '{outdir}/{prefix}-lane-{i}.out.jsonl'\n"
        )
        sh.chmod(0o755)
    print(f"wrote {args.n} lane scripts under {outdir}")


def evalset(args) -> None:
    """Merge certified batches into the evalset of record (one directory:
    positive-drills.jsonl + autocorrect-drills.jsonl + held-drills.jsonl +
    meta.json). Each --batch is NAME=certout,certified,autocorrect.

    Holds (never merges) any drill whose job carried a fired arm that did
    NOT execute directed_ok: the drill's verdict then rests on at least one
    unverified arm (an auto-correct's "auto is best" claim, or a positive's
    best-arm identity). ADR-0066 standing rule: deterministic per-arm
    salvage means suspect the enumerator — the row is routed by name in
    meta.json, not silently dropped or silently kept."""
    from datetime import date

    # --retire BATCH:JOB=REASON — a drill removed by name after external
    # re-adjudication (e.g. a held row whose re-run verdict changed).
    # Recorded in meta.json, never silently dropped.
    retire: dict[str, str] = {}
    for spec in getattr(args, "retire", None) or []:
        key, reason = spec.split("=", 1)
        retire[key] = reason

    batches, positives, autocorrects, held, retired = [], [], [], [], []
    seen: dict[tuple, str] = {}  # window key -> batch, dup = loud failure
    for spec in args.batch:
        name, files = spec.split("=", 1)
        certout, certified_f, autocorrect_f = files.split(",")
        # jobs whose non-auto arms ever fired without a faithful execution
        suspect: dict[int, set] = defaultdict(set)
        jobs_seen = set()
        for line in open(certout):
            r = json.loads(line)
            if r.get("ev") != "certify":
                continue
            jobs_seen.add(r["job"])
            if r["arm"] > 0 and r.get("fired") and r.get("exec") != "directed_ok":
                suspect[r["job"]].add(r.get("exec_why") or r.get("exec", "?"))
        n_held = 0
        for f, sink in ((certified_f, positives), (autocorrect_f, autocorrects)):
            for line in open(f):
                row = {**json.loads(line), "batch": name}
                key = _window_key(row)
                if key in seen:
                    raise SystemExit(
                        f"duplicate window across batches ({seen[key]} vs {name}): {key}")
                seen[key] = name
                if f"{name}:{row['job']}" in retire:
                    retired.append({**row, "retired_why": retire[f"{name}:{row['job']}"]})
                elif row["job"] in suspect:
                    held.append({**row, "held_why": sorted(suspect[row["job"]])})
                    n_held += 1
                else:
                    sink.append(row)
        batches.append({"name": name, "certout": certout, "jobs": len(jobs_seen),
                        "held": n_held})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for fname, rows in (("positive-drills.jsonl", positives),
                        ("autocorrect-drills.jsonl", autocorrects),
                        ("held-drills.jsonl", held)):
        with open(out / fname, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def _by_shape(rows):
        d = defaultdict(int)
        for r in rows:
            d[r["shape"]] += 1
        return dict(sorted(d.items()))

    floors = {s: n >= args.floor for s, n in _by_shape(positives).items()}
    meta = {
        "version": out.name,
        "created": date.today().isoformat(),
        "census": str(Path(batches[0]["certout"]).resolve().parent),
        "thresholds": {"margin": MARGIN, "consistent": CONSISTENT,
                       "horizon": HORIZON, "shape_k": SHAPE_K},
        "batches": batches,
        "counts": {"positive": _by_shape(positives),
                   "autocorrect": _by_shape(autocorrects),
                   "held": _by_shape(held)},
        "floor": {"per_shape": args.floor, "met": floors},
        "held": [{k: h[k] for k in ("batch", "job", "kind", "shape", "sa", "held_why")}
                 for h in held],
        "retired": [{k: r[k] for k in ("batch", "job", "kind", "shape", "sa", "retired_why")}
                    for r in retired],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"evalset {out.name}: positive {len(positives)} {meta['counts']['positive']}")
    print(f"  auto-correct {len(autocorrects)} {meta['counts']['autocorrect']}")
    for h in held:
        print(f"  HELD {h['batch']} job {h['job']} ({h['kind']}, {h['shape']}): "
              f"{'; '.join(h['held_why'])}")
    for r in retired:
        print(f"  RETIRED {r['batch']} job {r['job']} ({r['kind']}, {r['shape']}): "
              f"{r['retired_why']}")
    for s, ok in floors.items():
        print(f"  floor {s:<18} {'ok' if ok else 'MISS (top-up night, not a redesign)'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("candidates")
    p.add_argument("--out", required=True)
    p.add_argument("--per-shape", type=int, default=DEFAULT_PER_SHAPE)
    p.add_argument("--counts", default="",
                   help="per-shape quota overrides, e.g. 'blocker_pressure=240,color_hold=240'")
    p.add_argument("--exclude", action="append", default=[],
                   help="prior jobs.jsonl whose windows are skipped (repeatable)")
    p.set_defaults(fn=plan)
    r = sub.add_parser("read")
    r.add_argument("--jobs", required=True)
    r.add_argument("--certout", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--autocorrect-out", default=None,
                   help="auto-correct drill output (default: autocorrect-drills.jsonl beside --out)")
    r.set_defaults(fn=read)
    e = sub.add_parser("evalset")
    e.add_argument("--batch", action="append", required=True,
                   help="NAME=certout.jsonl,certified.jsonl,autocorrect.jsonl (repeatable)")
    e.add_argument("--out", required=True, help="evalset-of-record directory")
    e.add_argument("--floor", type=int, default=10,
                   help="per-shape positive floor (evalset-assembly pin 3)")
    e.add_argument("--retire", action="append", default=[],
                   help="BATCH:JOB=REASON — drop a drill by name after external "
                        "re-adjudication; recorded in meta.json (repeatable)")
    e.set_defaults(fn=evalset)
    n = sub.add_parser("lanes")
    n.add_argument("--jobs", required=True)
    n.add_argument("--jar", required=True)
    n.add_argument("-n", type=int, default=4)
    n.set_defaults(fn=lanes)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
