"""Wire observation -> model batch, and model output -> wire answer (M1 D8).

The featurization half MIRRORS anvil.training.dataset.PriorityWindows._examples
FIELD FOR FIELD — this is the train/serve skew boundary: any change to the
loader's featurization must land here (and vice versa). Labels are pads at
serve time; the shared pieces (assemble, EmbeddingCache, MethodVocab, SaVocab,
norm_sa, collate) are imported, not copied. Since M2 D2 priority candidates
are (host row, normalized SA) pairs with identical keys collapsed; aux's
cand_first_opt maps the model's candidate choice back to the first matching
wire-option index (first-fit among collapsed duplicates, matching the
training label semantics).

History arrives pre-extracted from the worker ("hist": last-K prior decisions
as {"m","p","e"}, hosts back-filled at ret time to match the training loader's
joined view); the information-set rule is applied here, mirroring
transform.history_tokens.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import torch

from anvil.encoder.transform import HISTORY_K, assemble
from anvil.training.dataset import (COMBAT_COUNT_MAX, KINDS, PRIORITY, T_MAX,
                                    TASKS, X_CLASSES, EmbeddingCache,
                                    MethodVocab, SaVocab, _eligible_rows,
                                    default_sa_vocab, norm_sa)

_HOST_ID = re.compile(r"\((\d+)\)$")  # mirrors dataset._HOST_ID

TAG_TASK = {
    "mtg.priority": "priority",
    "mtg.mulligan_keep": "mull_keep",
    "mtg.trigger": "trigger",
    "mtg.binary": "binary",
    "mtg.number": "number",
    "mtg.attack": "attack",   # M2 D5 combat declarations
    "mtg.block": "block",
}


def wire_history(hist: list[dict] | None, perspective: int,
                 k: int = HISTORY_K) -> list[dict[str, Any]]:
    """Mirrors transform.history_tokens' information-set rule: an opponent's
    chosen host is kept only for priority casts (public events)."""
    out = []
    for h in (hist or [])[-k:]:
        actor = h.get("p", -1)
        host = h.get("e", -1) if (actor == perspective or h.get("m") == PRIORITY) else -1
        out.append({"m": h.get("m", "?"), "self": 1 if actor == perspective else 0,
                    "e": host})
    return out


class Featurizer:
    def __init__(self, embedding_stem: str | Path, methods: list[str],
                 sa_vocab: list[str] | None = None):
        self.embed = EmbeddingCache(Path(embedding_stem))
        self.methods = MethodVocab(methods)
        self.sa_vocab = SaVocab(sa_vocab or default_sa_vocab())

    def example(self, dec: dict, header: dict, task: str) -> tuple[dict, dict]:
        """One wire dec record -> (model example with label pads, aux maps for
        answer translation)."""
        p = dec["p"]
        out = assemble(dec, header, perspective=p,
                       history=wire_history(dec.get("hist"), p))
        row_of = out["entity_row_of"]

        cand_rows = [-1]
        cand_sa = [-1]
        cand_kind = [-1]
        cand_first_opt = [-1]  # per candidate: FIRST matching wire-option index
        ctx_row = -1
        num_lo, num_hi = 0, X_CLASSES - 1
        cmb_rows: list[int] = []
        cmb_count: list[int] = []
        blk_atk_rows: list[int] = []
        cmb_members: dict[int, list[int]] = {}
        args = dec.get("args") or {}
        if task == "priority":
            # mirrors the loader: (host row, normalized sa) pairs in option
            # order, identical keys collapsed; first-fit picks the executor's
            # option among collapsed duplicates
            key_of: dict[tuple[int, str], int] = {}
            for i, o in enumerate(dec.get("opts") or []):
                r = row_of.get(o.get("e"))
                if r is None:
                    continue
                key = (r, norm_sa(o.get("sa", "")))
                if key in key_of:
                    continue
                key_of[key] = len(cand_rows)
                cand_rows.append(r)
                cand_sa.append(self.sa_vocab.id(key[1]))
                cand_kind.append(KINDS.get(o.get("kind"), KINDS["other"]))
                cand_first_opt.append(i)
        elif task == "trigger":
            m = _HOST_ID.search(args.get("host") or "")
            if m and int(m.group(1)) in row_of:
                ctx_row = row_of[int(m.group(1))]
        elif task == "number":
            num_lo = max(0, min(int(args.get("min", 0)), X_CLASSES - 1))
            num_hi = max(num_lo, min(int(args.get("max", X_CLASSES - 1)), X_CLASSES - 1))
        elif task in ("attack", "block"):
            # candidate basis mirrors the loader EXACTLY (same helper): the
            # derived superset; engine legality gates at the worker's realizer
            cmb_rows, cmb_members = _eligible_rows(
                dec["obs"], p, row_of, need_unsick=(task == "attack"))
            cmb_count = [min(len(cmb_members[r]), COMBAT_COUNT_MAX) for r in cmb_rows]
            if task == "block":
                blk_atk_rows = sorted({row_of[e["e"]] for e in dec["obs"].get("ents", [])
                                       if "atk" in e})

        hist = np.full((HISTORY_K, 3), -1, dtype=np.int64)
        for i, h in enumerate(out["history"][-HISTORY_K:]):
            hist[i] = (self.methods.id(h["m"]), h["self"], row_of.get(h["e"], -1))

        ex = {
            "entities": torch.from_numpy(out["entities"]),
            "ent_emb": torch.tensor([self.embed.row(n) for n in out["entity_names"]],
                                    dtype=torch.int64),
            "globals": torch.from_numpy(out["globals"]),
            "players": torch.from_numpy(out["players"]),
            "history": torch.from_numpy(hist),
            "cand_rows": torch.tensor(cand_rows, dtype=torch.int64),
            "cand_sa": torch.tensor(cand_sa, dtype=torch.int64),
            "cand_kind": torch.tensor(cand_kind, dtype=torch.int64),
            "label": torch.tensor(0, dtype=torch.int64),
            "label_row": torch.tensor(-1, dtype=torch.int64),
            "tgt_kind": torch.from_numpy(np.full(T_MAX + 1, -1, dtype=np.int64)),
            "tgt_idx": torch.from_numpy(np.full(T_MAX + 1, -1, dtype=np.int64)),
            "x_val": torch.tensor(-1, dtype=torch.int64),
            "task": torch.tensor(TASKS[task], dtype=torch.int64),
            "bool_label": torch.tensor(-1, dtype=torch.int64),
            "num_label": torch.tensor(-1, dtype=torch.int64),
            "num_lo": torch.tensor(num_lo, dtype=torch.int64),
            "num_hi": torch.tensor(num_hi, dtype=torch.int64),
            "ctx_row": torch.tensor(ctx_row, dtype=torch.int64),
            "forced": torch.tensor(0, dtype=torch.int64),
            "has_outcome": torch.tensor(0, dtype=torch.int64),
            "won": torch.tensor(0, dtype=torch.int64),
            # combat fields (D5): candidates for attack/block windows, empty
            # elsewhere; labels stay empty at serve except cmb_count_label,
            # which collate slices at candidate width (pads -1)
            "cmb_rows": torch.tensor(cmb_rows, dtype=torch.int64),
            "cmb_count": torch.tensor(cmb_count, dtype=torch.int64),
            "cmb_count_label": torch.full((len(cmb_rows),), -1, dtype=torch.int64),
            "blk_atk_rows": torch.tensor(blk_atk_rows, dtype=torch.int64),
            **{k: torch.zeros(0, dtype=torch.int64) for k in
               ("atk_label", "atk_tgt_kind", "atk_tgt_idx", "blk_label")},
        }

        # ---- answer-translation maps ----
        row_min_id: dict[int, int] = {}
        for eid, r in row_of.items():
            if r not in row_min_id or eid < row_min_id[r]:
                row_min_id[r] = eid
        stack_ids = {e["e"] for e in dec["obs"].get("ents", []) if e.get("z") == "stack"}
        n_players = len(header["players"])
        aux = {"cand_rows": cand_rows, "cand_first_opt": cand_first_opt,
               "row_min_id": row_min_id, "stack_ids": stack_ids,
               "n_players": n_players,
               # combat answer translation (D5): candidate rows in example
               # order; members per row (sorted — first-fit expansion is the
               # multiset-tie convention); attacker slots; seats maps the
               # model's self-first player positions back to registered
               # indices (combat heads use positions, unlike the target
               # decoder's absolute-pi convention)
               "cmb_rows": cmb_rows,
               "cmb_members": {r: sorted(ids) for r, ids in cmb_members.items()},
               "blk_atk_rows": blk_atk_rows,
               "seats": [p] + [q for q in range(n_players) if q != p]}
        return ex, aux
