#!/usr/bin/env python3
"""M12 Build 3 surface smoke read (ADR-0103): what the surface enumerators and
the expansion round did on the search jar.

Reads the ev:"search" rows of a -searchsurf run: per candidate copy the
number of traced surface callbacks (n_surf), per expanded sub-row the surface
kind, option count, answers enumerated, per-answer leaf kinds and directive
misses, and the value spread — max V(answer) − V(natural) — the headroom a
surface answer shows over the heuristic's pick under the unsharpened head
(a smoke number, not a read of strength). Also the obs-side check: how many
non-priority decision records now carry a named option list.

Usage:
  uv run python scripts/surface_smoke_read.py --run data/runs/build3-surface-smoke
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def q(v: list[float], p: float) -> float | None:
    if not v:
        return None
    s = sorted(v)
    return s[min(len(s) - 1, int(p * len(s)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = Path(a.run)
    rows = [json.loads(ln) for ln in (run / "search.jsonl").open() if ln.strip()]
    rows = [r for r in rows if r.get("ev") == "search"]
    n_win = len(rows)
    n_cand = sum(len(r["opts"]) for r in rows)
    cand_with_surf = sum(1 for r in rows for o in r["opts"] if o.get("n_surf", 0) > 0)
    sub_rows = [(r, s) for r in rows for s in r.get("sub", [])]
    by_kind: dict[str, Counter] = defaultdict(Counter)
    spreads: dict[str, list[float]] = defaultdict(list)
    ans_ms: list[float] = []
    for r, s in sub_rows:
        k = s["kind"]
        by_kind[k]["sub_rows"] += 1
        by_kind[k]["answers"] += len(s["ans"])
        by_kind[k]["n_opts_sum"] += s["n"]
        nat_v = None
        best = None
        for ans in s["ans"]:
            is_nat = ans["a"] == s["nat"]
            vs = [v for v in ans["v"] if v is not None]
            for kd in ans["kind"]:
                by_kind[k][f"kind:{kd}"] += 1
            for m in ans.get("miss", []):
                if m:
                    by_kind[k][f"miss:{m}"] += 1
            if vs:
                mv = sum(vs) / len(vs)
                if is_nat:
                    nat_v = mv
                elif best is None or mv > best:
                    best = mv
        if nat_v is not None and best is not None:
            spreads[k].append(best - nat_v)
        ans_ms.append(r.get("ms", 0))
    lines = [
        f"# Surface smoke read — {run.name}",
        "",
        f"windows {n_win}; candidate copies {n_cand}; copies that traced ≥1 surface callback {cand_with_surf} "
        f"({cand_with_surf / max(1, n_cand):.1%}); expanded sub-rows {len(sub_rows)}",
        f"window ms p50 {q([r.get('ms', 0) for r in rows], 0.5)} / p90 {q([r.get('ms', 0) for r in rows], 0.9)}",
        "",
        "| kind | sub-rows | answers | mean n opts | leaf kinds | misses | Δ(best − natural) p50 / p90 / max | ≥0.02 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k, c in sorted(by_kind.items()):
        kinds = ", ".join(f"{kk[5:]} {v}" for kk, v in sorted(c.items()) if kk.startswith("kind:"))
        misses = (
            ", ".join(f"{kk[5:]} {v}" for kk, v in sorted(c.items()) if kk.startswith("miss:"))
            or "none"
        )
        sp = spreads.get(k, [])
        pos = sum(1 for x in sp if x >= 0.02)
        lines.append(
            f"| {k} | {c['sub_rows']} | {c['answers']} | {c['n_opts_sum'] / max(1, c['sub_rows']):.1f} | {kinds} | {misses} | "
            f"{q(sp, 0.5)} / {q(sp, 0.9)} / {max(sp) if sp else None} | {pos}/{len(sp)} |"
        )
    # census side: how often the surface callbacks fire per game
    total = Counter()
    n_games = 0
    games = run / "games.jsonl"
    if games.exists():
        n_games = sum(1 for ln in games.open() if ln.strip())
    census = run / "census.jsonl"
    if census.exists():
        for ln in census.open():
            try:
                r = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            m = r.get("m")
            if m:
                total[m] += 1
    surf_methods = [
        "chooseSingleEntityForEffect",
        "chooseEntitiesForEffect",
        "chooseCardsToDiscardFrom",
        "choosePermanentsToSacrifice",
        "orderSimultaneousSa",
        "orderMoveToZoneList",
        "arrangeForScry",
        "arrangeForSurveil",
        "chooseModeForAbility",
        "chooseCardName",
        "chooseSomeType",
        "assignCombatDamage",
        "chooseSingleCardForZoneChange",
        "chooseCardsToDiscardToMaximumHandSize",
    ]
    if total:
        lines += [
            "",
            "census callbacks per game (surface methods): "
            + ", ".join(f"{m} {total[m] / max(1, n_games):.1f}" for m in surf_methods if total[m]),
        ]
    out = "\n".join(lines) + "\n"
    (run / "surface-smoke-read.md").write_text(out)
    json.dump(
        {
            "windows": n_win,
            "cands": n_cand,
            "cands_with_surface": cand_with_surf,
            "sub_rows": len(sub_rows),
            "by_kind": {k: dict(c) for k, c in by_kind.items()},
            "spreads": {k: v for k, v in spreads.items()},
        },
        open(run / "surface-smoke-read.json", "w"),
        indent=1,
    )
    print(out)


if __name__ == "__main__":
    main()
