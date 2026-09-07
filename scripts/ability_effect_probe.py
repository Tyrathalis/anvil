#!/usr/bin/env python3
"""The ability-representation frozen probe (ADR-0105 item 7; the ADR-0049
frozen-probe benchmark asked fork K's question): is an ability's ENGINE EFFECT
linearly decodable from the pinned LLM embedding of its text?

Two caches, one label set. The labels come from the canonical text itself
(the fork's script parameters, `A:<api> | k$v ...` lines), never from games:

  api      the effect class = the set of API names on the ability's chain
           (Mana, Draw, Destroy, ChangeZone, DealDamage, PutCounter, Pump, ...);
           one binary probe per class with >= --min-pos positives
  produced for Mana abilities: the produced-mana class (W/U/B/R/G/C, Any,
           Combo) — the "add {G}" vs "add one mana of any color" distinction
  zone     for ChangeZone abilities: the destination zone (Hand, Battlefield,
           Graveyard, Exile, Library)

Each probe: logistic regression on the unit embedding, 5-fold cross-validated
AUC (binary) or accuracy (multiclass), reported for the canonical-text cache
(--cache) and the description-only control (--control, `--field D`). Decodable
from the canonical text -> re-segmentation by construction is enough and the
effect-prediction auxiliary loss stays an instrument; not decodable -> fork K's
option (a) enters the Build 4 evening.

Usage:
  uv run python scripts/ability_effect_probe.py --cache data/embeddings/abil-XXXX-qwen3 \
      --control data/embeddings/abil-XXXX-D-qwen3 [--out data/runs/build3-ability-probe]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np

_API = re.compile(r"^\s*A:([A-Za-z0-9_?]+)")
_PARAM = re.compile(r"(\w+)\$([^|]*)")

ZONES = ("Hand", "Battlefield", "Graveyard", "Exile", "Library")


def load_cache(stem: str) -> tuple[np.ndarray, list[str], dict[str, str]]:
    from safetensors.numpy import load_file

    stem = stem[: -len(".safetensors")] if stem.endswith(".safetensors") else stem
    meta = json.loads(Path(stem + ".json").read_text())
    emb = load_file(stem + ".safetensors")["embeddings"].astype(np.float32)
    texts = json.loads(Path(stem + "-texts.json").read_text())
    return emb, meta["keys"], texts


def labels_of(text: str) -> dict:
    apis: set[str] = set()
    produced = None
    zone = None
    for ln in text.split("\n"):
        m = _API.match(ln)
        if not m:
            continue
        api = m.group(1)
        apis.add(api)
        params = dict((k, v.strip()) for k, v in _PARAM.findall(ln))
        if api == "Mana" and produced is None:
            p = params.get("Produced", "")
            if p in ("W", "U", "B", "R", "G", "C"):
                produced = p
            elif p == "Any":
                produced = "Any"
            elif p:
                produced = "Combo"
        if api == "ChangeZone" and zone is None:
            d = params.get("Destination", "")
            zone = d if d in ZONES else None
    return {"apis": apis, "produced": produced, "zone": zone}


def cv_auc(x: np.ndarray, y: np.ndarray, seed: int = 0) -> float:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    scores = np.zeros(len(y))
    for tr, te in skf.split(x, y):
        clf = LogisticRegression(max_iter=2000, C=1.0)
        clf.fit(x[tr], y[tr])
        scores[te] = clf.decision_function(x[te])
    return float(roc_auc_score(y, scores))


def cv_acc(x: np.ndarray, y: np.ndarray, seed: int = 0) -> tuple[float, float]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    hit = 0
    for tr, te in skf.split(x, y):
        clf = LogisticRegression(max_iter=3000, C=1.0)
        clf.fit(x[tr], y[tr])
        hit += int((clf.predict(x[te]) == y[te]).sum())
    maj = Counter(y.tolist()).most_common(1)[0][1] / len(y)
    return hit / len(y), maj


def run(stem: str, min_pos: int) -> dict:
    emb, keys, texts = load_cache(stem)
    labs = [labels_of(texts[k]) for k in keys]
    out: dict = {"stem": stem, "n": len(keys), "api": {}, "produced": None, "zone": None}
    api_counts = Counter(a for l in labs for a in l["apis"])
    for api, n in sorted(api_counts.items(), key=lambda kv: -kv[1]):
        if n < min_pos or n > len(keys) - min_pos:
            continue
        y = np.array([1 if api in l["apis"] else 0 for l in labs])
        out["api"][api] = {"n_pos": int(n), "auc": round(cv_auc(emb, y), 4)}
    for field in ("produced", "zone"):
        idx = [i for i, l in enumerate(labs) if l[field] is not None]
        if len(idx) >= 4 * min_pos:
            y = np.array([labs[i][field] for i in idx])
            cls = Counter(y.tolist())
            keep = [i for i, v in zip(idx, y) if cls[v] >= 5]
            if len(set(np.array([labs[i][field] for i in keep]).tolist())) >= 2:
                y2 = np.array([labs[i][field] for i in keep])
                acc, maj = cv_acc(emb[keep], y2)
                out[field] = {"n": len(keep), "classes": dict(Counter(y2.tolist())), "acc": round(acc, 4), "majority": round(maj, 4)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, help="stem of the canonical-text cache")
    ap.add_argument("--control", default=None, help="stem of the description-only cache")
    ap.add_argument("--min-pos", type=int, default=20)
    ap.add_argument("--out", default="data/runs/build3-ability-probe")
    a = ap.parse_args()
    res = {"canonical": run(a.cache, a.min_pos)}
    if a.control:
        res["control"] = run(a.control, a.min_pos)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe.json").write_text(json.dumps(res, indent=1) + "\n")
    lines = ["# Ability-representation frozen probe (ADR-0105)", ""]
    lines.append("| effect class | n_pos | canonical AUC | description-only AUC |")
    lines.append("|---|---|---|---|")
    c = res["canonical"]["api"]
    d = res.get("control", {}).get("api", {})
    for api, r in sorted(c.items(), key=lambda kv: -kv[1]["n_pos"]):
        lines.append(f"| {api} | {r['n_pos']} | {r['auc']:.3f} | {d.get(api, {}).get('auc', float('nan')):.3f} |")
    for field in ("produced", "zone"):
        r = res["canonical"].get(field)
        if r:
            rc = res.get("control", {}).get(field) or {}
            lines += ["", f"**{field}** ({r['n']} abilities, classes {r['classes']}): canonical acc "
                      f"{r['acc']:.3f} / description-only {rc.get('acc', float('nan')):.3f} / majority {r['majority']:.3f}"]
    (out / "probe.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
