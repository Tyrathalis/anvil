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

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import torch

from anvil.encoder.transform import HISTORY_K, assemble
from anvil.training.dataset import (
    COMBAT_COUNT_MAX,
    KINDS,
    PAY_KINDS,
    PRIORITY,
    T_MAX,
    TASKS,
    X_CLASSES,
    EmbeddingCache,
    MethodVocab,
    SaVocab,
    _eligible_rows,
    default_sa_vocab,
    norm_sa,
)

_HOST_ID = re.compile(r"\((\d+)\)$")  # mirrors dataset._HOST_ID

TAG_TASK = {
    "mtg.priority": "priority",
    "mtg.mulligan_keep": "mull_keep",
    "mtg.trigger": "trigger",
    "mtg.binary": "binary",
    "mtg.number": "number",
    "mtg.attack": "attack",  # M2 D5 combat declarations
    "mtg.block": "block",
    # M9 §3c (rung 3): the payment goal decision. The server additionally
    # gates this tag on the ckpt carrying the pay_ params (server.has_pay,
    # the has_combat precedent) — a pre-M9 ckpt declines and the worker's
    # local echo stays AUTO (GrpcBridge pins the tag's echo to 0).
    "mtg.pay_mana_class": "pay_class",
}


def wire_history(
    hist: list[dict] | None, perspective: int, k: int = HISTORY_K
) -> list[dict[str, Any]]:
    """Mirrors transform.history_tokens' information-set rule: an opponent's
    chosen host is kept only for priority casts (public events)."""
    out = []
    for h in (hist or [])[-k:]:
        actor = h.get("p", -1)
        host = h.get("e", -1) if (actor == perspective or h.get("m") == PRIORITY) else -1
        out.append({"m": h.get("m", "?"), "self": 1 if actor == perspective else 0, "e": host})
    return out


def store_wire_hist(prior: list[dict], now_pos: int, k: int = HISTORY_K) -> list[dict[str, Any]]:
    """Reconstruct what the Java ring ships from STORE dec records: raw
    (m, p, ret-host) for the last K prior decs — the info-set rule is applied
    later in wire_history. Hosts back-fill at ret time, so a prior dec whose
    ret lands AFTER the current window (nested parent) ships host=-1 (M2 D2
    nested-window semantics). Used by the serve-parity tests and the D6 RL
    loader, which rebuilds serve-identical windows from stored games."""
    out = []
    for d in prior[-k:]:
        ret = d.get("ret")
        host = -1
        if (
            isinstance(ret, list)
            and ret
            and isinstance(ret[0], dict)
            and d.get("_retpos") is not None
            and d["_retpos"] < now_pos
        ):
            host = ret[0].get("e", -1)
        out.append({"m": d.get("m", "?"), "p": d.get("p", -1), "e": host})
    return out


SCHED_VIRTUAL_CAP = 48  # virtual candidates per window (hand casts + activations + board)
# mana abilities appear in the mined activation bucket (the engine offers
# them as options in some windows) but are never a plannable cast-window
# action — the plan waits forever on "tap the Signet". Payment is the
# executor's (Fork 6 names the extension).
_MANA_ABILITY = re.compile(r"(^|: )Add (\{|one |two |three |X |an amount|that much|mana)", re.IGNORECASE)


def is_mana_ability(sa: str) -> bool:
    return bool(_MANA_ABILITY.search(sa or ""))


MAIN_PHASES = ("MAIN1", "MAIN2")


def quiescent_main(dec: dict) -> bool:
    """A main-phase priority window with an EMPTY stack (sorcery-speed
    legality holds). Shared by the featurizer's virtual-candidate filter and
    the serve carry's binding rules (sched_serve.SchedServe.quiescent_main).

    The obs carries the stack two ways and both must be empty: cards on the
    stack are entities with z="stack"; triggered/activated ABILITIES on the
    stack never enter the zone and appear only in the separate obs["stack"]
    list (the Java option scan keys sorcery-speed legality on MagicStack for
    the same reason). Found 2026-09-04: the entities-only test read 9.3K of
    79K census windows with an ability on the stack as quiescent — binding
    rule 3 then failed sorcery-speed slots for timing (the hand-basis
    day-zero read's "unactivatable" pile) and the loyalty/once-per-turn
    filter below saw "absent at quiescence" where it was a trigger."""
    obs = dec["obs"]
    glob = obs.get("glob", {})
    if glob.get("ph") not in MAIN_PHASES:
        return False
    if obs.get("stack"):
        return False
    return not any(e.get("z") == "stack" for e in obs.get("ents", []))


# Board-host activation filter (m10-reset-draft §I refinement (b), session
# two): a permanent's activation that is not offered now is a plannable
# virtual candidate only if a road back exists this turn. The option scan
# does NOT filter by payability (AnvilOptions PAYCHECK off), so an absent
# board activation is absent for a NON-mana reason — and three of those
# reasons never clear within the turn, all readable from the seat's own
# visible state: the host is tapped ({T}/{Q} costs), the host is summoning-
# sick ({T}/{Q} costs; the engine's `sick` is creature-only already), or the
# ability was already used (loyalty abilities and "activate only once each
# turn" abilities absent at a QUIESCENT MAIN window — sorcery-speed timing
# holds there, so absence means spent). The hand-basis day-zero read paid
# 13.4K fast-failing slots per read to exactly these (ADR-0095 addendum).
_LOYALTY_COST = re.compile(r"^[+\-−]?\d+$")
_ONCE_PER_TURN = re.compile(r"only once each turn", re.IGNORECASE)


def ability_cost(sa: str) -> str:
    """The cost half of an activation's rules text ('{1}{B}, {T}: ...' ->
    '{1}{B}, {T}'); '' when the text carries no cost separator."""
    head, sep, _ = (sa or "").partition(":")
    return head if sep else ""


def board_activation_open(sa: str, ent: dict, quiet: bool) -> bool:
    """False = this board host's activation has no road back this turn."""
    cost = ability_cost(sa)
    taps = "{T}" in cost or "{Q}" in cost
    if taps and (ent.get("tap") or ent.get("sick")):
        return False
    if quiet and (_LOYALTY_COST.match(cost.strip()) or _ONCE_PER_TURN.search(sa or "")):
        return False
    return True


def load_ability_table(path: str | Path) -> dict:
    """The mined ability table (scripts/mine_ability_table.py): card name ->
    {cast/activate/command/...: [{sa (normalized), n, kind}, ...]}."""
    return json.loads(Path(path).read_text())["cards"]


class Featurizer:
    def __init__(
        self,
        embedding_stem: str | Path,
        methods: list[str],
        sa_vocab: list[str] | None = None,
        ability_table: "str | Path | dict | None" = None,
    ):
        self.embed = EmbeddingCache(Path(embedding_stem))
        self.methods = MethodVocab(methods)
        self.sa_vocab = SaVocab(sa_vocab or default_sa_vocab())
        # M10 hand-basis planner (m10-reset-draft §I): with a table, priority
        # windows carry the schedule decode's SUPERSET key space (legal
        # candidates as a prefix + virtual candidates: each own hand card's
        # primary cast ability and activations, each own permanent's
        # activations not legal now, the commander's cast from the command
        # zone). Information-set principle: virtual candidates come only from
        # the seat's visible zones + card knowledge, never engine state.
        self.ability_table = (
            ability_table if isinstance(ability_table, dict)
            else (load_ability_table(ability_table) if ability_table else None)
        )

    def _sched_superset(self, dec: dict, p: int, row_of: dict, cand_rows: list,
                        cand_sa: list, cand_kind: list, cand_first_opt: list) -> tuple:
        """-> (rows, sa, kind, opts) over the superset; opts[i] = the wire opt
        (legal prefix) or a synthetic {e, sa, kind} (virtual); opts[0] None."""
        opts = dec.get("opts") or []
        s_rows, s_sa, s_kind = list(cand_rows), list(cand_sa), list(cand_kind)
        s_opts: list = [None] + [opts[fo] if fo >= 0 else None for fo in cand_first_opt[1:]]
        seen = {(r, sa) for r, sa in zip(cand_rows[1:], cand_sa[1:])}
        seen_key = set()
        for o in opts:
            r = row_of.get(o.get("e"))
            if r is not None:
                seen_key.add((r, norm_sa(o.get("sa", ""))))
        n_virtual = 0
        quiet = quiescent_main(dec)
        for e in dec["obs"].get("ents", []):
            if e.get("c") != p or n_virtual >= SCHED_VIRTUAL_CAP:
                continue
            z = e.get("z")
            info = self.ability_table.get(e.get("n") or "")
            if info is None:
                continue
            r = row_of.get(e.get("e"))
            if r is None:
                continue
            buckets = []
            if z == "hand":
                buckets = [("cast", 1), ("activate", 1)]   # primary cast + primary activation
            elif z == "battlefield":
                buckets = [("activate", 3)]                  # up to 3 activations not legal now
            elif z == "command":
                buckets = [("command", 1)]
            for bucket, top in buckets:
                taken = 0
                for entry in info.get(bucket) or []:
                    if taken >= top:
                        break
                    sa = entry["sa"]
                    if bucket in ("activate",) and is_mana_ability(sa):
                        continue
                    if z == "battlefield" and not board_activation_open(sa, e, quiet):
                        continue  # tapped / sick / spent host: no road back this turn
                    taken += 1
                    if (r, sa) in seen_key:
                        continue  # legal now: already in the prefix
                    sid = self.sa_vocab.id(sa)
                    if (r, sid) in seen:
                        continue
                    seen.add((r, sid))
                    seen_key.add((r, sa))
                    s_rows.append(r)
                    s_sa.append(sid)
                    s_kind.append(KINDS.get(entry.get("kind"), KINDS["other"]))
                    s_opts.append({"e": e.get("e"), "sa": sa, "kind": entry.get("kind"), "virtual": 1})
                    n_virtual += 1
                    if n_virtual >= SCHED_VIRTUAL_CAP:
                        break
        return s_rows, s_sa, s_kind, s_opts

    def example(
        self, dec: dict, header: dict, task: str, full_vis: bool = False
    ) -> tuple[dict, dict]:
        """One wire dec record -> (model example with label pads, aux maps for
        answer translation). full_vis (M3 §6f): asymmetric-critic windows —
        same window/history semantics, info-set gate bypassed in assemble;
        NEVER a policy input (rl.py's pass-B leak boundary is test-pinned)."""
        p = dec["p"]
        out = assemble(
            dec, header, perspective=p, history=wire_history(dec.get("hist"), p), full_vis=full_vis
        )
        row_of = out["entity_row_of"]

        cand_rows = [-1]
        cand_sa = [-1]
        cand_kind = [-1]
        cand_paykind = [-1]
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
        elif task == "pay_class":
            # M9 §3c goal options (m9-payment-surface-spec §12a / rung-3 pins).
            # Option 0 = {"auto":true} rides the PASS slot. Each goal option
            # keys on ONE representative tapped entity (lowest id; life/pool-
            # only plans tap nothing -> row -1, the model keys on the goal-kind
            # embedding alone) plus the label's "gk" goal-kind code. Positional:
            # every wire option occupies a candidate slot even when its
            # entities miss the obs join — the answer index space is the wire's.
            for i, lab in enumerate(dec.get("opts") or []):
                if i == 0:
                    continue
                try:
                    o = json.loads(lab)
                except (TypeError, ValueError):
                    o = {}
                ents = o.get("ents") or []
                cand_rows.append(row_of.get(min(ents), -1) if ents else -1)
                cand_sa.append(-1)
                cand_kind.append(-1)
                gk = o.get("gk") or []
                cand_paykind.append(int(gk[0]) if gk else PAY_KINDS["spare_other"])
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
                dec["obs"], p, row_of, need_unsick=(task == "attack")
            )
            cmb_count = [min(len(cmb_members[r]), COMBAT_COUNT_MAX) for r in cmb_rows]
            if task == "block":
                blk_atk_rows = sorted(
                    {row_of[e["e"]] for e in dec["obs"].get("ents", []) if "atk" in e}
                )

        hist = np.full((HISTORY_K, 3), -1, dtype=np.int64)
        for i, h in enumerate(out["history"][-HISTORY_K:]):
            hist[i] = (self.methods.id(h["m"]), h["self"], row_of.get(h["e"], -1))

        sched_ex: dict = {}
        sched_opts = None
        if task == "priority" and self.ability_table is not None:
            s_rows, s_sa, s_kind, sched_opts = self._sched_superset(
                dec, p, row_of, cand_rows, cand_sa, cand_kind, cand_first_opt
            )
            sched_ex = {
                "sched_cand_rows": torch.tensor(s_rows, dtype=torch.int64),
                "sched_cand_sa": torch.tensor(s_sa, dtype=torch.int64),
                "sched_cand_kind": torch.tensor(s_kind, dtype=torch.int64),
            }
        ex = {
            "entities": torch.from_numpy(out["entities"]),
            "ent_emb": torch.tensor(
                [self.embed.row(n) for n in out["entity_names"]], dtype=torch.int64
            ),
            "globals": torch.from_numpy(out["globals"]),
            "players": torch.from_numpy(out["players"]),
            "history": torch.from_numpy(hist),
            "cand_rows": torch.tensor(cand_rows, dtype=torch.int64),
            "cand_sa": torch.tensor(cand_sa, dtype=torch.int64),
            "cand_kind": torch.tensor(cand_kind, dtype=torch.int64),
            "cand_paykind": torch.tensor(cand_paykind, dtype=torch.int64),
            **sched_ex,
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
            **{
                k: torch.zeros(0, dtype=torch.int64)
                for k in ("atk_label", "atk_tgt_kind", "atk_tgt_idx", "blk_label")
            },
        }

        # ---- answer-translation maps ----
        if sched_opts is not None:
            aux_sched = {"sched_cand_opts": sched_opts}
        else:
            aux_sched = {}
        row_min_id: dict[int, int] = {}
        for eid, r in row_of.items():
            if r not in row_min_id or eid < row_min_id[r]:
                row_min_id[r] = eid
        stack_ids = {e["e"] for e in dec["obs"].get("ents", []) if e.get("z") == "stack"}
        n_players = len(header["players"])
        aux = {
            "cand_rows": cand_rows,
            "cand_first_opt": cand_first_opt,
            "row_min_id": row_min_id,
            "stack_ids": stack_ids,
            "n_players": n_players,
            # M10 v2 schedule surface: wire entity id -> obs row, for slot-
            # token row resolution (serve carry + loader reconstruction)
            "row_of": row_of,
            # combat answer translation (D5): candidate rows in example
            # order; members per row (sorted — first-fit expansion is the
            # multiset-tie convention); attacker slots; seats maps the
            # model's self-first player positions back to registered
            # indices (combat heads use positions, unlike the target
            # decoder's absolute-pi convention)
            "cmb_rows": cmb_rows,
            "cmb_members": {r: sorted(ids) for r, ids in cmb_members.items()},
            "blk_atk_rows": blk_atk_rows,
            "seats": [p] + [q for q in range(n_players) if q != p],
            **aux_sched,
        }
        return ex, aux
