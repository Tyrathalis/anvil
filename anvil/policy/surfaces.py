"""M12 Build 3 (ADR-0105): the decision surfaces' option sets on the Python
side — shared by the training loader (anvil.training.dataset) and the serve
featurizer (anvil.bridge.featurize), so a surface window is built ONE way.

A surface record (sv=3, Surfaces.dec in the fork) carries `args.surf` = the
answer shape, `opts` = the option list as raw entries ({e} entity, {pi}
player, {e, sa, ak} ability, "..." string), the callback's min/max, the
resolving ability's key (`args.sak`), and — on mainlines — the heuristic's
answer as `ret`. Every option becomes one KEY in the option-set decoder
(anvil.policy.model AnvilNet._surface_decode): an entity option keys on its
entity row, a player option on its player key, an ability option on its host
row + the ability table vector (the pinned LLM embedding of the ability's
canonical engine text, keyed by `ak`), each plus a small option-kind
embedding. The answer is a sequence of option indices closed by STOP:

  surf_one   (entity_one)  exactly one pick, then STOP
  surf_set   (entity_set)  min..max distinct picks, then STOP
  surf_order (order)       every option once (min = max = n), no early STOP
  surf_scry  (scry)        the top cards in order, then STOP (the rest bottom)
  surf_mode  (mode)        min..num modes, then STOP
  surf_name  (name)        one pick (a face / a type), then STOP
  surf_damage(damage)      routed to the ordering evening

SURF_MAX = the longest answer decoded (the decoder's surface slot count;
longer heuristic answers are truncated and counted).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

SURF_TASK = {
    "entity_one": "surf_one",
    "entity_set": "surf_set",
    "order": "surf_order",
    "scry": "surf_scry",
    "mode": "surf_mode",
    "name": "surf_name",
    "damage": "surf_damage",
}
# the shapes whose loader / serve path exist (grows one evening at a time)
SURF_BUILT = {"surf_one", "surf_set"}
OPT_KINDS = {"entity": 0, "player": 1, "ability": 2, "other": 3}
SURF_MAX = 12  # answer slots (+1 STOP); discard-to-hand-size and sacrifice-N sit under it


class AbilityCache:
    """The ability table (anvil.encoder abilities): fp16 vectors + key -> row.
    Missing keys (an ability play generated that no dump or side table has
    seen yet) -> -1, counted by the caller; the model keys such an option on
    its host row + kind alone."""

    def __init__(self, stem: str | Path):
        from safetensors.torch import load_file

        stem = str(stem)
        stem = stem[: -len(".safetensors")] if stem.endswith(".safetensors") else stem
        self.stem = stem
        self.meta = json.loads(Path(stem + ".json").read_text())
        self.vectors = load_file(stem + ".safetensors")["embeddings"]
        self.row_of = {k: i for i, k in enumerate(self.meta["keys"])}

    def index(self, key: str | None) -> int:
        if not key:
            return -1
        return self.row_of.get(key, -1)

    @property
    def dim(self) -> int:
        return int(self.vectors.shape[1])


def surface_task(dec: dict) -> str | None:
    """The surface task of a dec record, or None (not a surface / not built)."""
    surf = (dec.get("args") or {}).get("surf")
    t = SURF_TASK.get(surf) if surf else None
    return t if t in SURF_BUILT else None


def _opt_key(o: Any) -> tuple:
    if isinstance(o, dict):
        if "ak" in o:
            return ("a", o.get("e"), o["ak"])
        if "sa" in o:
            return ("s", o.get("e"), o.get("sa"))
        if "e" in o:
            return ("e", o["e"])
        if "pi" in o:
            return ("p", o["pi"])
    return ("x", str(o))


def surface_fields(
    dec: dict,
    row_of: dict[int, int],
    abil: AbilityCache | None,
    method_id: int,
    with_labels: bool,
) -> dict | None:
    """Option-set fields for one surface window; None = not a decision (one
    option, nothing to pick, a forced full set) or, with labels, an answer
    that does not resolve to the option set (counted by the caller through
    the returned `_miss` reason instead of raising)."""
    args = dec.get("args") or {}
    task = surface_task(dec)
    if task is None:
        return None
    opts = dec.get("opts") or []
    n = len(opts)
    if n < 2:
        return None
    if task == "surf_one":
        lo, hi = 1, 1
    else:
        if args.get("numDiscard") is not None:  # chooseCardsToDiscardToMaximumHandSize
            lo = hi = int(args["numDiscard"])
        elif args.get("num") is not None and args.get("min") is None:  # chooseSpellAbilitiesForEffect
            lo, hi = 0, int(args["num"])
        else:
            lo = max(0, int(args.get("min", 1) if args.get("min") is not None else 1))
            hi = int(args.get("max", n) if args.get("max") is not None else n)
        hi = max(0, min(hi, n))
        lo = max(0, min(lo, hi))
        if hi < 1:
            return None
        if lo == hi == n:
            return None  # every option is taken — no decision
    opt_row = np.full(n, -1, dtype=np.int64)
    opt_pi = np.full(n, -1, dtype=np.int64)
    opt_ak = np.full(n, -1, dtype=np.int64)
    opt_kind = np.full(n, OPT_KINDS["other"], dtype=np.int64)
    key_index: dict[tuple, int] = {}
    ak_miss = 0
    ent_miss = 0
    for i, o in enumerate(opts):
        k = _opt_key(o)
        key_index.setdefault(k, i)
        if isinstance(o, dict):
            if "ak" in o or "sa" in o:
                opt_kind[i] = OPT_KINDS["ability"]
                opt_row[i] = row_of.get(o.get("e"), -1)
                if abil is not None and o.get("ak"):
                    opt_ak[i] = abil.index(o["ak"])
                    if opt_ak[i] < 0:
                        ak_miss += 1
            elif "e" in o:
                opt_kind[i] = OPT_KINDS["entity"]
                opt_row[i] = row_of.get(o["e"], -1)
                if opt_row[i] < 0:
                    ent_miss += 1
            elif "pi" in o:
                opt_kind[i] = OPT_KINDS["player"]
                opt_pi[i] = int(o["pi"])
    out = {
        "task": task,
        "opt_row": opt_row,
        "opt_pi": opt_pi,
        "opt_ak": opt_ak,
        "opt_kind": opt_kind,
        "opt_min": lo,
        "opt_max": min(hi, SURF_MAX),
        "surf_ctx_ak": abil.index(args.get("sak")) if abil is not None else -1,
        "surf_method": method_id,
        "_ak_miss": ak_miss,
        "_ent_miss": ent_miss,
        "_n": n,
    }
    if not with_labels:
        return out
    ret = dec.get("ret")
    if task == "surf_one":
        picks = [ret] if ret is not None else []
    else:
        picks = list(ret) if isinstance(ret, list) else ([ret] if ret is not None else [])
    labels = np.full(SURF_MAX + 1, -1, dtype=np.int64)
    idxs: list[int] = []
    for r in picks:
        j = key_index.get(_opt_key(r))
        if j is None and isinstance(r, dict) and "e" in r:
            # an ability answer serialized as a CastPlan (kind/tgt extras) —
            # match on host + sa when the exact key misses
            j = key_index.get(("s", r.get("e"), r.get("sa")))
            if j is None:
                j = next((key_index[k] for k in key_index if k[0] == "a" and k[1] == r.get("e")), None) \
                    if "sa" in r else key_index.get(("e", r["e"]))
        if j is None or j in idxs:
            out["_miss"] = "label_unmatched" if j is None else "label_repeat"
            return out
        idxs.append(j)
    if task == "surf_one" and len(idxs) != 1:
        out["_miss"] = "label_count"
        return out
    if task == "surf_set" and not (lo <= len(idxs) <= hi):
        out["_miss"] = "label_count"
        return out
    if len(idxs) > SURF_MAX:
        out["_miss"] = "label_truncated"
        idxs = idxs[:SURF_MAX]
    for t, j in enumerate(idxs):
        labels[t] = j
    labels[len(idxs)] = n  # STOP = the option count (collate remaps to the batch width)
    out["surf_labels"] = labels
    return out
