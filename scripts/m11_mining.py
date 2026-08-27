#!/usr/bin/env python3
"""M11-routing probes — the CPU mining rungs (m11-routing-probes-spec.md,
adjudicated 2026-08-26; mining-rung-first discipline).

Walks census.jsonl sidecars and emits the mining census for both probes:

  Probe T (tutor/fetch targets): both adjudicated SELECT_ONE classes —
    chooseSingleCardForZoneChange + chooseSingleEntityForEffect —
    classified into tutor_fetch ("Search your librar…" in sa/prompt),
    dig ("Look at the top …" library reveals), and other; candidate-
    count distribution per class (the k-pin input), isOptional split,
    per-seat/per-phase rates. Multi-entity variants counted only
    (chooseEntitiesForEffect / chooseCardsForEffect, per adjudication).

  Probe P (resolution-effect payments): payManaCost effect=true rows —
    classified into phase_sa ("[Phase: …]" marker), text_optional
    ("may pay"/"unless"/"you may"/"may have"), text_other (nonempty sa,
    no optional marker), empty_sa (by phase). The optionality bit is
    NOT in the current telemetry (prompt is always null): the knowable
    decline-legal count here is a LOWER BOUND; the isCancellable +
    source-name fields ride the planned engine-delta session.

Rate conventions reported explicitly: per-game (500 self-play games,
both seats are the model) AND per seat-game (/1000) — the gate-scale
denominator at eval is per seat-game.

Usage:
  uv run python scripts/m11_mining.py \
      --workers data/runs/m10-ceiling-census-20260825-212414/workers \
      --out data/runs/m11-mining
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

SEARCH_RX = re.compile(r"[Ss]earch (?:your|their|his|her) librar")
DIG_RX = re.compile(r"[Ll]ook at the top")
OPT_RX = re.compile(r"may pay|unless|[Yy]ou may|may have")
PHASE_RX = re.compile(r"^\[Phase: ")

T_CLASSES = ("chooseSingleCardForZoneChange", "chooseSingleEntityForEffect")
T_MULTI = ("chooseEntitiesForEffect", "chooseCardsForEffect")


def seat_of(p: str) -> int:
    m = re.match(r"Anvil\((\d)\)", p or "")
    return int(m.group(1)) - 1 if m else -1


def classify_t(r: dict) -> str:
    text = " ".join(str(r.get(k) or "") for k in ("sa", "selectPrompt", "title"))
    if SEARCH_RX.search(text):
        return "tutor_fetch"
    if DIG_RX.search(text):
        return "dig"
    return "other"


def classify_p(r: dict) -> str:
    sa = (r.get("sa") or "").strip()
    if not sa:
        return "empty_sa"
    if PHASE_RX.match(sa):
        return "phase_sa"
    if OPT_RX.search(sa):
        return "text_optional"
    return "text_other"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    games = 0
    t_rows: list[dict] = []
    t_multi = Counter()
    p_cls, p_phase_empty, p_cat = Counter(), Counter(), Counter()
    p_n = 0

    for cj in sorted(Path(a.workers).glob("inv-*/census.jsonl")):
        for ln in open(cj):
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("ev") == "start":
                games += 1
                continue
            m = r.get("m")
            if m in T_MULTI:
                t_multi[m] += 1
            elif m in T_CLASSES:
                ncand = r.get("fetchList", r.get("optionList", 0)) or 0
                t_rows.append({
                    "cls": m, "cat": classify_t(r), "ncand": int(ncand),
                    "seat": seat_of(r.get("p")), "ph": r.get("ph"),
                    "optional": bool(r.get("isOptional")),
                    "sa": (r.get("sa") or "")[:60],
                })
            elif m == "payManaCost" and r.get("effect"):
                p_n += 1
                c = classify_p(r)
                p_cls[c] += 1
                if c == "empty_sa":
                    p_phase_empty[r.get("ph")] += 1
                else:
                    p_cat[(c, (r.get("sa") or "")[:60])] += 1

    # ---- probe T report ----
    def dist(rows, key):
        return dict(Counter(x[key] for x in rows).most_common())

    t_rep = {"games": games, "raw_events": len(t_rows),
             "multi_entity_counted_only": dict(t_multi)}
    for cat in ("tutor_fetch", "dig", "other"):
        rs = [x for x in t_rows if x["cat"] == cat]
        forceable = [x for x in rs if x["ncand"] >= 2]
        t_rep[cat] = {
            "n": len(rs), "per_game": round(len(rs) / games, 3),
            "per_seat_game": round(len(rs) / (2 * games), 3),
            "n_cand_ge2": len(forceable),
            "cand_ge2_per_seat_game": round(len(forceable) / (2 * games), 3),
            "by_class": dist(rs, "cls"),
            "ncand_hist": dict(sorted(Counter(x["ncand"] for x in rs).items())),
            "optional_frac": round(sum(x["optional"] for x in rs)
                                   / max(1, len(rs)), 3),
            "by_phase": dist(rs, "ph"),
        }

    # ---- probe P report ----
    p_rep = {"games": games, "effect_true_events": p_n,
             "per_game": round(p_n / games, 2),
             "per_seat_game": round(p_n / (2 * games), 2),
             "classes": {k: {"n": v, "per_seat_game": round(v / (2 * games), 3)}
                         for k, v in p_cls.most_common()},
             "empty_sa_by_phase": dict(p_phase_empty.most_common()),
             "knowable_decline_legal_lower_bound":
                 {"n": p_cls["text_optional"],
                  "per_seat_game": round(p_cls["text_optional"] / (2 * games), 3)},
             "telemetry_gap": "prompt always null; no isCancellable/source "
                              "fields — ride the engine-delta session"}

    report = {"probe_t": t_rep, "probe_p": p_rep}
    (out / "mining-report.json").write_text(json.dumps(report, indent=2) + "\n")
    with open(out / "t-catalog.jsonl", "w") as f:
        for (cls, cat, sa), v in sorted(
                Counter((x["cls"], x["cat"], x["sa"]) for x in t_rows).items(),
                key=lambda kv: -kv[1]):
            f.write(json.dumps({"cls": cls, "cat": cat, "sa": sa, "n": v}) + "\n")
    with open(out / "p-catalog.jsonl", "w") as f:
        for (c, sa), v in p_cat.most_common():
            f.write(json.dumps({"cat": c, "sa": sa, "n": v}) + "\n")
    print(json.dumps({"probe_t": {k: t_rep[k]["per_seat_game"] if isinstance(t_rep[k], dict) and "per_seat_game" in t_rep[k] else None
                                  for k in ("tutor_fetch", "dig", "other")},
                      "probe_p_classes": {k: v["n"] for k, v in p_rep["classes"].items()}},
                     indent=2))
    print(f"-> {out}/mining-report.json + catalogs")


if __name__ == "__main__":
    main()
