#!/usr/bin/env python3
"""M9 ceiling measurement (ADR-0072 'NEXT'; pins in m9-plan.md §"The ceiling
measurement"): do the 69 certified 2-turn-proxy positives convert to WINRATE
at game end?

Two job sets over the evalset-of-record positives, identical except horizon
(2 = in-era re-certification, 999 = game end). Jobs reuse the revalidation
job ids and seeds so rollSeed matches across sets: each (job, arm, roll) is
the same determinized trajectory truncated at two points.

  plan   revalidation score rows + original certify jobs (arms join) +
         positive-drills.jsonl (certification margins) -> master provenance
         file + two Java job files (horizon 2 / 999).
  read   the two certout sets -> per-drill paired win-diff + in-era
         re-certification + pooled/per-shape/Spearman report per the pins.

Lane scripts come from payment_certify.py lanes (unchanged machinery).
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import payment_certify as pc  # noqa: E402  (_score/_axes/_payer_seat/MARGIN/CONSISTENT)

HORIZON_END = 999
MIN_PAIRED_ROLLS = 6  # pin 1


def plan(args) -> None:
    drills = [r for r in map(json.loads, open(args.drills)) if r["kind"] == "positive"]
    jobsrc = {}
    for spec in args.jobs_src:
        name, path = spec.split("=", 1)
        jobsrc[name] = {j["job"]: j for j in map(json.loads, open(path))}
    cert = {(r["batch"], r["job"]): r
            for r in map(json.loads, open(args.evalset))}

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    master = []
    for d in drills:
        src = jobsrc[d["batch"]][d["orig_job"]]
        c = cert[(d["batch"], d["orig_job"])]
        master.append({
            # Java contract fields (horizon added per set below)
            "job": d["job"], "seed": d["seed"],
            "deck1": d["deck1"], "deck2": d["deck2"],
            "p": d["p"], "t": d["t"], "sa": d["sa"],
            "ord": d.get("ord", 0), "arms": src["arms"], "k": args.k,
            # provenance
            "batch": d["batch"], "orig_job": d["orig_job"],
            "shape": d["shape"], "best": d["best"],
            "margin_cert": c.get("margin"), "tags": c.get("tags"),
            "reval_status": d["status"], "exp_options": d["exp_options"],
        })
    ids = [m["job"] for m in master]
    if len(ids) != len(set(ids)):
        raise SystemExit("revalidation job ids not unique — rollSeed pairing broken")

    with open(outdir / "ceiling-master.jsonl", "w") as f:
        for m in master:
            f.write(json.dumps(m) + "\n")
    for name, hz in (("ceilh2", 2), ("ceilend", HORIZON_END)):
        with open(outdir / f"{name}-jobs.jsonl", "w") as f:
            for m in master:
                row = {k: m[k] for k in pc.JAVA_JOB_FIELDS if k != "horizon"}
                row["horizon"] = hz
                f.write(json.dumps(row) + "\n")
    n_games = sum((m["arms"] + 1) * args.k for m in master)
    print(f"planned {len(master)} drills x 2 horizons -> {outdir}")
    print(f"  ~{n_games} games per set ({2 * n_games} total), k={args.k}")
    by = defaultdict(int)
    for m in master:
        by[m["shape"]] += 1
    for s, n in sorted(by.items()):
        print(f"  {s:<18} {n}")


def _win(row: dict, seat: int) -> float:
    w = row.get("winner", -1)
    return 1.0 if w == seat else (0.5 if w == -1 else 0.0)


def _load(path: str) -> dict:
    rows = defaultdict(dict)  # (job, arm) -> {roll: row}
    for line in open(path):
        r = json.loads(line)
        if r.get("ev") == "certify":
            rows[(r["job"], r["arm"])][r["roll"]] = r
    return rows


def _spearman(xs: list, ys: list) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for t in range(i, j + 1):
                rk[order[t]] = (i + j) / 2.0
            i = j + 1
        return rk
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def read(args) -> None:
    master = [json.loads(l) for l in open(args.master)]
    h2, end = _load(args.h2), _load(args.end)

    per_drill, dropped = [], defaultdict(int)
    n_unended = 0
    arm_points = []  # (margin, windiff) per directed arm, all arms
    for m in master:
        jid, best, shape = m["job"], m["best"], m["shape"]
        seat_row = h2.get((jid, 0)) or end.get((jid, 0))
        if not seat_row:
            dropped["no_baseline"] += 1
            continue
        seat = pc._payer_seat(next(iter(seat_row.values())), m)

        def paired(arm):
            """(margin, windiff) per roll with faithful execution + ended ends."""
            out = []
            nonlocal n_unended
            for roll, rh in sorted(h2.get((jid, arm), {}).items()):
                re_ = end.get((jid, arm), {}).get(roll)
                bh = h2.get((jid, 0), {}).get(roll)
                be = end.get((jid, 0), {}).get(roll)
                if re_ is None or bh is None or be is None:
                    continue
                if not (rh.get("fired") and rh.get("exec") == "directed_ok"
                        and re_.get("fired") and re_.get("exec") == "directed_ok"):
                    continue
                if not (bh.get("fired") and be.get("fired")):
                    continue
                if not (re_.get("ended") and be.get("ended")):
                    n_unended += 1
                    continue
                out.append((
                    pc._score(shape, pc._axes(rh, seat), pc._axes(bh, seat)),
                    _win(re_, seat) - _win(be, seat),
                ))
            return out

        rolls = paired(best)
        for arm in range(1, m["arms"] + 1):
            pts = rolls if arm == best else paired(arm)
            if pts:
                arm_points.append((
                    sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts),
                ))
        if len(rolls) < args.min_pairs:
            dropped["thin_pairs"] += 1
            continue
        margins = [p[0] for p in rolls]
        diffs = [p[1] for p in rolls]
        mmean = sum(margins) / len(margins)
        agree = sum(1 for s in margins if (s > 0) == (mmean > 0)) / len(margins)
        per_drill.append({
            **{k: m[k] for k in ("job", "batch", "orig_job", "shape", "best",
                                 "margin_cert", "seed", "t", "sa")},
            "n_pairs": len(rolls),
            "margin_h2": round(mmean, 3),
            "recert": bool(mmean > 0 and abs(mmean) >= pc.MARGIN.get(shape, 2.0)
                           and agree >= pc.CONSISTENT),
            "windiff": round(sum(diffs) / len(diffs), 4),
        })

    outdir = Path(args.master).parent
    with open(outdir / "ceiling-drills.jsonl", "w") as f:
        for d in per_drill:
            f.write(json.dumps(d) + "\n")

    n = len(per_drill)
    print(f"denominator: {n}/{len(master)} drills "
          f"(dropped: {dict(dropped)}; unended rolls excluded: {n_unended})")
    if not n:
        raise SystemExit("no drills survived — nothing to read")

    def pooled(rows, label):
        vals = [d["windiff"] for d in rows]
        mean = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1))
        se = sd / math.sqrt(len(vals))
        z = mean / se if se else float("nan")
        rec = sum(1 for d in rows if d["recert"])
        print(f"  {label:<18} n={len(rows):>3}  dWin={mean:+.4f} +/- {se:.4f} "
              f"(z={z:+.2f})  recert {rec}/{len(rows)}")
        return {"n": len(rows), "windiff": mean, "se": se, "z": z,
                "recert": rec}

    print("pooled (per-drill clustered, pin 2):")
    headline = pooled(per_drill, "ALL")
    by_shape = {}
    for shape in sorted({d["shape"] for d in per_drill}):
        by_shape[shape] = pooled([d for d in per_drill if d["shape"] == shape], shape)

    rho_drill = _spearman([d["margin_h2"] for d in per_drill],
                          [d["windiff"] for d in per_drill])
    rho_arms = _spearman([a[0] for a in arm_points], [a[1] for a in arm_points]) \
        if len(arm_points) > 2 else float("nan")
    print(f"spearman(margin_h2, windiff): drills {rho_drill:+.3f} "
          f"(n={n}), all-arms {rho_arms:+.3f} (n={len(arm_points)})")

    # pin 3 adjudication inputs (branch verdict stays a human read)
    recert_rate = headline["recert"] / n
    refire_ok = n >= 55
    recert_ok = recert_rate >= 0.70
    print(f"guards: refire {'ok' if refire_ok else 'QUALIFIED (<55)'} ({n}), "
          f"in-era recert {'ok' if recert_ok else 'DRIFTED (<70%)'} "
          f"({recert_rate:.1%})")
    mined_rate = 56 / 500  # pin 4 lower bound, b4 hand-built excluded
    print(f"gate-scale arithmetic (pin 4, lower bound): dWin x {mined_rate:.3f} "
          f"windows/game/seat = {headline['windiff'] * mined_rate * 100:+.2f}pp/game "
          f"vs gate floor 1.1pp")

    report = {
        "pins": "m9-plan.md 'The ceiling measurement' (2026-08-24)",
        "denominator": n, "dropped": dict(dropped), "unended_rolls": n_unended,
        "headline": headline, "by_shape": by_shape,
        "spearman_drills": rho_drill, "spearman_arms": rho_arms,
        "recert_rate": recert_rate,
        "guards": {"refire_ok": refire_ok, "recert_ok": recert_ok},
    }
    (outdir / "ceiling-read.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"-> {outdir / 'ceiling-read.json'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--drills", required=True,
                   help="revalidation score-dayzero-*.jsonl (job ids + windows)")
    p.add_argument("--evalset", required=True,
                   help="payment-evalset positive-drills.jsonl (cert margins)")
    p.add_argument("--jobs-src", action="append", required=True,
                   help="BATCH=original-certify-jobs.jsonl (arms join, repeatable)")
    p.add_argument("--outdir", required=True)
    p.add_argument("--k", type=int, default=8)
    p.set_defaults(fn=plan)
    r = sub.add_parser("read")
    r.add_argument("--master", required=True)
    r.add_argument("--h2", required=True)
    r.add_argument("--end", required=True)
    r.add_argument("--min-pairs", type=int, default=MIN_PAIRED_ROLLS,
                   help="pin 1 denominator floor (lower only for smokes)")
    r.set_defaults(fn=read)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
