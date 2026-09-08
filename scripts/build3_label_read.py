#!/usr/bin/env python3
"""M12 Build 3 (ADR-0105): the surface-label run's read — what the pool holds.

Over a harness run dir (workers/inv-*/{labels.jsonl, games.jsonl, obs.*}):
  games / statuses / wall; searched windows, act classes (the acting rule at
  the shakedown bar); sub rows per kind with the value spread (max V(answer)
  − V(natural)) quantiles and the ≥ 0.02 share (the headroom the search sees
  on each shape); directive misses; and on a sample of obs frames the key
  coverage: ability options carrying `ak`, surface decs carrying `args.sak`,
  and how many keys the ability cache lacks (the side-table append).

Usage: uv run python scripts/build3_label_read.py --run data/runs/b3-surflab-<ts> \\
           [--abilities data/embeddings/abil-cf2ca6ba-qwen3] [--frames 200]
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path


def q(v: list[float], p: float) -> float | None:
    if not v:
        return None
    s = sorted(v)
    return s[min(len(s) - 1, int(p * len(s)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--abilities", default="data/embeddings/abil-cf2ca6ba-qwen3")
    ap.add_argument("--frames", type=int, default=200)
    a = ap.parse_args()
    run = Path(a.run)
    games = []
    for f in glob.glob(str(run / "workers/inv-*/games.jsonl")):
        for ln in open(f):
            if ln.strip():
                try:
                    games.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    rows = []
    for f in glob.glob(str(run / "workers/inv-*/labels.jsonl")):
        for ln in open(f):
            if ln.startswith('{"ev":"search"'):
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    out: dict = {"run": str(run), "games": len(games), "statuses": dict(Counter(g["status"] for g in games))}
    out["ms_p50"] = q([g["ms"] for g in games], 0.5)
    out["windows"] = len(rows)
    out["applied"] = dict(Counter(r.get("applied") for r in rows))
    out["act_rate"] = round(sum(1 for r in rows if r.get("applied") in ("act", "pass")) / max(1, len(rows)), 4)
    subs = [s for r in rows for s in r.get("sub", [])]
    out["sub_rows"] = len(subs)
    out["sub_rows_per_game"] = round(len(subs) / max(1, len(games)), 2)
    by: dict[str, dict] = {}
    miss: Counter = Counter()
    for kind in sorted({s["kind"] for s in subs}):
        ks = [s for s in subs if s["kind"] == kind]
        spreads = []
        n_ans = 0
        for s in ks:
            nat = best = None
            for ans in s["ans"]:
                n_ans += 1
                for m in ans.get("miss", []) or []:
                    if m:
                        miss[f"{kind}:{m}"] += 1
                vs = [v for v in ans["v"] if v is not None]
                if not vs:
                    continue
                mv = sum(vs) / len(vs)
                if ans["a"] == s["nat"]:
                    nat = mv
                elif best is None or mv > best:
                    best = mv
            if nat is not None and best is not None:
                spreads.append(best - nat)
        by[kind] = {
            "sub_rows": len(ks),
            "answers": n_ans,
            "mean_n": round(sum(s["n"] for s in ks) / max(1, len(ks)), 2),
            "spread_p50": q(spreads, 0.5),
            "spread_p90": q(spreads, 0.9),
            "spread_max": q(spreads, 1.0),
            "ge_0.02": round(sum(1 for x in spreads if x >= 0.02) / max(1, len(spreads)), 3),
        }
    out["by_kind"] = by
    out["misses"] = dict(miss)
    # key coverage on a sample of frames
    try:
        from anvil.policy.surfaces import AbilityCache
        from anvil.store.trajectories import decode_frame

        abil = AbilityCache(a.abilities)
        cov = Counter()
        unknown: set[str] = set()
        n_frames = 0
        for idxf in glob.glob(str(run / "workers/inv-*/obs.idx.jsonl")):
            data = open(Path(idxf).with_name("obs.zst"), "rb").read()
            for ln in open(idxf):
                if n_frames >= a.frames:
                    break
                e = json.loads(ln)
                try:
                    hdr, decs, end, marks = decode_frame(data[e["off"]:e["off"] + e["clen"]], 3)
                except Exception:
                    continue
                n_frames += 1
                for d in decs:
                    args = d.get("args") or {}
                    for r in d.get("abil") or []:
                        cov["abil_side_table"] += 1
                        if abil.index(r["h"]) < 0:
                            unknown.add(r["h"])
                    if args.get("surf"):
                        cov["surface_decs"] += 1
                        cov["sak_present"] += 1 if args.get("sak") else 0
                    for o in d.get("opts") or []:
                        if isinstance(o, dict) and "sa" in o:
                            cov["ability_opts"] += 1
                            cov["ability_opts_with_ak"] += 1 if o.get("ak") else 0
                            if o.get("ak") and abil.index(o["ak"]) < 0:
                                cov["ak_not_in_cache"] += 1
        out["key_coverage"] = {**dict(cov), "frames": n_frames, "side_table_keys_not_in_cache": len(unknown)}
    except Exception as ex:  # noqa: BLE001
        out["key_coverage"] = {"error": str(ex)}
    (run / "label-read.json").write_text(json.dumps(out, indent=1) + "\n")
    lines = [f"# Surface-label run read — {run.name}", "",
             f"games {out['games']} {out['statuses']}; windows {out['windows']}; act rate {out['act_rate']}; "
             f"applied {out['applied']}; sub rows {out['sub_rows']} ({out['sub_rows_per_game']}/game)", "",
             "| kind | sub-rows | answers | mean n | spread p50 / p90 / max | ≥0.02 |", "|---|---|---|---|---|---|"]
    for k, v in by.items():
        lines.append(f"| {k} | {v['sub_rows']} | {v['answers']} | {v['mean_n']} | {v['spread_p50']:.3f} / {v['spread_p90']:.3f} / {v['spread_max']:.3f} | {v['ge_0.02']:.3f} |")
    lines += ["", f"misses {out['misses']}", f"key coverage {out['key_coverage']}"]
    (run / "label-read.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
