"""Decision-window dataset over a TrajectoryStore (M1 D4/D5).

Streams games (IterableDataset — random access would decode a whole zstd
frame per sample), yields one task-tagged example per rung-1 decision:
priority windows (the bulk) plus the one-field family (mull_keep/mull_tuck/
trigger/binary/number — see TASKS). Every example carries the same state
tensors; task-specific label fields are pad values (-1) elsewhere. Priority
examples:

  entities   (N, F) float32   dedup-group rows from the transform
  ent_emb    (N,)   int64     row into the embedding cache (-1 = hidden/token)
  globals    (G,)   float32
  players    (P, Q) float32
  history    (K, 3) int64     (method-id, actor-is-self, host-row or -1)
  cand_rows  (C,)   int64     candidate source rows; index 0 is always PASS (-1)
  cand_sa    (C,)   int64     SA-string vocab id per candidate (-1 = PASS/pad)
  cand_kind  (C,)   int64     KINDS id per candidate (-1 = PASS/pad)
  label      ()     int64     index into cand_rows the expert chose; -1 = the
                              SA-level label is ambiguous (masked from policy
                              loss; measured ~0.003% of casts, D2 sweep)
  label_row  ()     int64     expert's chosen HOST row (-1 = pass) — the
                              host-level agreement basis (continuity with M1),
                              known even when the SA-level label is masked
  has_outcome / won ()        value-head target (games without outcomes carry
                              has_outcome=0 and are excluded from value loss)

Design notes:
- All windows kept, pass included as candidate 0 (m1-bc-plan: imbalance is a
  training-time knob — weighting/downsampling lives in the sampler, not here).
- Candidates are (host dedup-group row, normalized SA string) pairs from the
  logged timing-legal options (ADR-0005 basis; M2 D2 moves the interface from
  host rows to SAs). Identical (row, sa) options collapse into ONE candidate:
  entity-level duplicates are §2 multiset semantics ("a Rat Colony"), and
  SA-level duplicates (commander permission routes, same-rendering cost
  variants) are indistinguishable to the model anyway — collapsing them makes
  the expert label exact at candidate level; the executor keeps first-fit for
  the residual engine-side tie.
- Labels resolve in order: exact logged option index ("oi", rets since
  2026-07-10) -> exact normalized-string match at the chosen host -> prefix-min
  match (the option/plan serializations truncate at different lengths) ->
  masked (-1). Masked windows keep their state, host-level label, and value
  target; the target/X heads are padded out (their conditioning is the chosen
  candidate, which is exactly what is unknown).
- entity_row_of is loader plumbing (label/candidate resolution); it is never
  a model input, so entity ids stay out of the information set.
- Windows whose chosen host resolves to no candidate row are IMPOSSIBLE by
  ADR-0005 construction; the loader raises rather than skipping (a silent
  skip here would hide exactly the corpus-poisoning class the validator
  exists to catch).

Combat examples (M2 D5, tasks attack/block) add per-candidate-row fields
(pad -1 / empty on other tasks; batch-padded in collate):

  cmb_rows        (A,) int64  candidate creature dedup rows (derived basis:
                              decider's battlefield creatures, untapped
                              [+unsick for attacks] — certified label superset)
  cmb_count       (A,) int64  dedup-group size (clamped COMBAT_COUNT_MAX)
  atk_label       (A,) int64  attack task: 1/0 per row
  cmb_count_label (A,) int64  k-1 class for multi-groups that acted (both tasks)
  atk_tgt_kind/idx(A,) int64  attack target per attacking row (0=entity row,
                              1=player position; -1 = none or mixed-in-group,
                              masked) -> collate builds atk_tgt_labels class ids
  blk_label       (A,) int64  block task: index into blk_atk_rows, or the none
                              class (per-example len(blk_atk_rows), remapped to
                              the batch none slot M in collate); -1 = masked
                              (multi-block or group split across attackers)
  blk_atk_rows    (M,) int64  attacker rows in the dec obs (pointer key set)

Labels come from the obs-side join (_combat_label_window): the declare
callbacks never serialized rets, but post-declaration windows carry atk/blk
flags. The join is bounded at the next declareAttackers dec — turn-only
bounding poisoned 145 corpus block labels via extra-combat overshoot
(classified 2026-07-13). Forced-empty windows (no candidates / no attackers)
are skipped: nothing to learn, and serve answers them without the model.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import torch
from torch.utils.data import IterableDataset, get_worker_info

from anvil.encoder.transform import HISTORY_K, assemble, history_tokens
from anvil.store.trajectories import open_store

PRIORITY = "chooseSpellAbilityToPlay"
T_MAX = 4       # target slots (100% coverage measured on the pilot; +1 STOP slot)
X_CLASSES = 18  # X = 0..16 + overflow bucket (3 casts past 16 in a 106K sample)

# one-field tasks (rung-1 committed scope beside priority; m1-bc-plan D4).
# Measured per 300 pilot games: mull_keep 746 / mull_tuck 146 / trigger 3,071
# (99.7% isMandatory -> forced, excluded from honest basis) / binary 54 /
# number 49 — mulligan is the real deliverable, the rest are per-tag coverage
# with honest tiny-n reporting.
# attack/block (M2 D5): factorized per-creature combat declarations. The
# declare callbacks never serialized rets; labels come from an obs-side JOIN
# (first later same-COMBAT window carrying the declared flags — see
# _combat_label_window). Corpus measure (d5-combat-label-measure-full):
# 1.41M attack windows / 382K block windows; derived candidate basis is a
# certified label superset (0 violations / 2.23M attackers).
TASKS = {"priority": 0, "mull_keep": 1, "mull_tuck": 2, "trigger": 3,
         "binary": 4, "number": 5, "attack": 6, "block": 7}
TASK_OF_METHOD = {PRIORITY: "priority", "mulliganKeepHand": "mull_keep",
                  "tuckCardsViaMulligan": "mull_tuck", "playTrigger": "trigger",
                  "chooseBinary": "binary", "chooseNumber": "number",
                  "declareAttackers": "attack", "declareBlockers": "block"}
COMBAT_COUNT_MAX = 12  # count-head classes k=1..12; per-group k beyond 12 is
                       # a handful corpus-wide (label clamps, serve un-clamps
                       # to "all" only via the executor's group size)
_HOST_ID = re.compile(r"\((\d+)\)$")  # "Spider-Man 2099 (100)" -> entity id 100

# SA candidate descriptors (M2 D2): option "kind" vocabulary + string
# normalization. Option strings render decision-time X ("... (X=0)") — strip
# it so the vocab key is state-independent; measured a no-op on corpus vocab
# size but insurance against serve-time X-bearing renders.
KINDS = {"land": 0, "spell": 1, "ability": 2, "other": 3}
_X_SUFFIX = re.compile(r" \(X=\d+\)")


def norm_sa(sa: str) -> str:
    return _X_SUFFIX.sub("", sa)


def _prefix_eq(a: str, b: str) -> bool:
    n = min(len(a), len(b))
    return n > 0 and a[:n] == b[:n]


class SaVocab:
    """Pinned SA-string vocab (normalized); unseen strings -> one OOV id
    (len(vocab)) — the embedding table is sized len+1. OOV mentions measured
    at 0.17-0.24% on held-out splits; the host entity + kind still carry
    such candidates."""

    def __init__(self, strings: list[str]):
        self.by_str = {s: i for i, s in enumerate(strings)}

    def id(self, s: str) -> int:
        return self.by_str.get(s, len(self.by_str))

    def __len__(self) -> int:
        return len(self.by_str)


def default_sa_vocab() -> list[str]:
    return json.loads((Path(__file__).parent / "sa_vocab_v1.json").read_text())["sa_strings"]


class MethodVocab:
    """Callback-method ids for history tokens; grown from data, stable order."""

    def __init__(self, methods: list[str]):
        self.by_name = {m: i for i, m in enumerate(methods)}

    def id(self, m: str) -> int:
        return self.by_name.get(m, len(self.by_name))  # unseen -> one OOV id


class EmbeddingCache:
    """fp16 card vectors + name->row lookup from anvil.encoder embed output."""

    def __init__(self, stem: Path):
        from safetensors.torch import load_file
        meta = json.loads(Path(f"{stem}.json").read_text())
        self.vectors = load_file(f"{stem}.safetensors")["embeddings"]
        self.row_of = {n: i for i, n in enumerate(meta["names"])}
        self.meta = meta

    def row(self, name: str | None) -> int:
        if name is None:
            return -1
        return self.row_of.get(name, -1)  # tokens/emblems etc. -> -1 (no text)


def default_methods() -> list[str]:
    return json.loads((Path(__file__).parent / "methods_v1.json").read_text())["methods"]


def _split_of(g: int, games_per_pair: int = 5) -> str:
    """Deterministic per-game split: ~2% val (random-by-game headline),
    ~2% of PAIRS as valpair (held-out-matchup generalization probe; all
    games of a held pair leave train together). Pure function of the game
    index — no split manifest to lose."""
    pair = g // games_per_pair
    if (pair * 2654435761) % 50 == 1:
        return "valpair"
    if (g * 2654435761) % 50 == 0:
        return "val"
    return "train"


def _combat_label_window(decs: list[dict], i: int, turn: int, flag: str) -> dict | None:
    """First later dec in the SAME combat whose obs carries any `flag` entity;
    None = the combat (or turn) ended unflagged — the empty label. Bounded at
    the next declareAttackers dec, not just the turn: extra-combat turns
    re-enter declare, and a turn-only bound let a no-block combat inherit a
    later combat's map (all 145 corpus block violations were this overshoot;
    classified 2026-07-13, scripts/d5/classify_block_violations.py)."""
    for d in decs[i + 1:]:
        if d.get("m") == "declareAttackers":
            return None
        obs = d.get("obs")
        if obs is None:
            continue
        if obs["glob"].get("turn") != turn:
            return None
        if any(flag in e for e in obs.get("ents", [])):
            return obs
    return None


def _eligible_rows(obs: dict, p: int, row_of: dict[int, int],
                   need_unsick: bool) -> tuple[list[int], dict[int, list[int]]]:
    """Decider's battlefield creature dedup rows, untapped (+unsick for
    attacks; sickness does not bar blocking) — the derived candidate basis.
    A timing superset by design (walls/Pacifism'd creatures stay candidates
    with 0-labels; ADR-0005 semantics), certified as a label superset by the
    corpus measure. Every eligibility field participates in the dedup key,
    so groups are uniformly eligible. Returns (sorted rows, row -> ids)."""
    members: dict[int, list[int]] = {}
    for e in obs.get("ents", []):
        if e.get("z") != "battlefield" or e.get("c") != p or "pt" not in e:
            continue
        if e.get("tap") or (need_unsick and e.get("sick")):
            continue
        members.setdefault(row_of[e["e"]], []).append(e["e"])
    return sorted(members), members


def attack_fields(decs: list[dict], i: int, dec: dict, row_of: dict[int, int],
                  n_players: int, g: int) -> dict | None:
    """Per-candidate-row attack labels for a declareAttackers window: 1/0
    attack, dedup count class (k-1, multi-groups with k>=1 only), and target
    ref (player position or entity row; a group whose members attack MIXED
    targets masks its target: multiset semantics can't order it). None =
    no eligible creatures (forced-empty window; nothing to learn or serve)."""
    obs = dec["obs"]
    p = dec["p"]
    rows, members = _eligible_rows(obs, p, row_of, need_unsick=True)
    if not rows:
        return None
    lw = _combat_label_window(decs, i, obs["glob"].get("turn"), "atk")
    attackers = {} if lw is None else {
        e["e"]: e["atk"] for e in lw["ents"] if "atk" in e and e.get("c") == p}
    member_row = {eid: r for r, ids in members.items() for eid in ids}
    for eid in attackers:
        if eid not in member_row:
            raise ValueError(
                f"game {g} s={dec.get('s')}: label attacker {eid} outside the "
                "derived candidate basis — superset violated (measured 0/2.23M; "
                "run scripts/d5/measure_combat_labels.py)")
    seats = [p] + [q for q in range(n_players) if q != p]
    out = {"cmb_rows": rows, "cmb_count": [], "atk_label": [],
           "cmb_count_label": [], "atk_tgt_kind": [], "atk_tgt_idx": []}
    for r in rows:
        ids = members[r]
        out["cmb_count"].append(min(len(ids), COMBAT_COUNT_MAX))
        ks = [eid for eid in ids if eid in attackers]
        out["atk_label"].append(1 if ks else 0)
        out["cmb_count_label"].append(
            min(len(ks), COMBAT_COUNT_MAX) - 1 if ks and len(ids) > 1 else -1)
        tk = ti = -1
        if ks:
            refs = {json.dumps(attackers[eid], sort_keys=True) for eid in ks}
            if len(refs) == 1:
                ref = attackers[ks[0]]
                if "pi" in ref:
                    tk, ti = 1, seats.index(ref["pi"])
                elif "e" in ref and ref["e"] in row_of:
                    tk, ti = 0, row_of[ref["e"]]
        out["atk_tgt_kind"].append(tk)
        out["atk_tgt_idx"].append(ti)
    return out


def block_fields(decs: list[dict], i: int, dec: dict, row_of: dict[int, int],
                 g: int) -> dict | None:
    """Per-candidate-row block labels: index into the window's attacker-row
    list, or the none class (= len(blk_atk_rows), remapped to the batch none
    slot in collate). Multi-blocks (measured 0 corpus-wide) and groups whose
    blocking members split across attackers mask the row (-1). None = no
    eligible blockers or no attackers in the obs (forced-empty window)."""
    obs = dec["obs"]
    p = dec["p"]
    rows, members = _eligible_rows(obs, p, row_of, need_unsick=False)
    atk_rows = sorted({row_of[e["e"]] for e in obs.get("ents", []) if "atk" in e})
    if not rows or not atk_rows:
        return None
    slot = {r: j for j, r in enumerate(atk_rows)}
    lw = _combat_label_window(decs, i, obs["glob"].get("turn"), "blk")
    blockers = {} if lw is None else {
        e["e"]: e["blk"] for e in lw["ents"] if "blk" in e and e.get("c") == p}
    member_row = {eid: r for r, ids in members.items() for eid in ids}
    for eid, blocked in blockers.items():
        if eid not in member_row:
            raise ValueError(
                f"game {g} s={dec.get('s')}: label blocker {eid} outside the "
                "derived candidate basis — superset violated")
        for aid in blocked:
            if row_of.get(aid) not in slot:
                raise ValueError(
                    f"game {g} s={dec.get('s')}: blocked target {aid} is not an "
                    "attacker in the dec obs — the combat-bounded join should "
                    "make this impossible (classified 2026-07-13)")
    none = len(atk_rows)
    out = {"cmb_rows": rows, "cmb_count": [], "blk_label": [],
           "cmb_count_label": [], "blk_atk_rows": atk_rows}
    for r in rows:
        ids = members[r]
        out["cmb_count"].append(min(len(ids), COMBAT_COUNT_MAX))
        bs = [eid for eid in ids if eid in blockers]
        if not bs:
            out["blk_label"].append(none)
            out["cmb_count_label"].append(-1)
            continue
        arows = {slot[row_of[blockers[eid][0]]] for eid in bs
                 if len(blockers[eid]) == 1}
        if len(arows) == 1 and all(len(blockers[eid]) == 1 for eid in bs):
            out["blk_label"].append(arows.pop())
        else:
            out["blk_label"].append(-1)
        out["cmb_count_label"].append(
            min(len(bs), COMBAT_COUNT_MAX) - 1 if len(ids) > 1 else -1)
    return out


class PriorityWindows(IterableDataset):
    def __init__(self, store_dir: str | Path | list, embedding_stem: str | Path,
                 methods: list[str] | None = None, shuffle_games: bool = True,
                 seed: int = 0, history_k: int = HISTORY_K,
                 split: str | None = None, games_per_pair: int = 5,
                 max_games: int | None = None, tasks: set[str] | None = None,
                 sa_vocab: list[str] | None = None, full_vis: bool = False):
        super().__init__()
        # full_vis: asymmetric-critic windows (design §4) — identities of all
        # entities visible. Critic training/eval only; never the policy input.
        self.full_vis = full_vis
        self.store_dir = store_dir  # raw spec: dir, comma-list, or list (open_store parses)
        self.embed = EmbeddingCache(Path(embedding_stem))
        self.methods = MethodVocab(methods or default_methods())
        self.sa_vocab = SaVocab(sa_vocab or default_sa_vocab())
        self.shuffle_games = shuffle_games
        self.seed = seed
        self.history_k = history_k
        self.split = split
        self.games_per_pair = games_per_pair
        self.max_games = max_games
        self.tasks = tasks if tasks is not None else set(TASKS)
        self._methods_wanted = {m for m, t in TASK_OF_METHOD.items() if t in self.tasks}
        self._epoch = 0  # per-worker: persistent workers re-call __iter__ each epoch

    def _examples(self, store, g: int) -> Iterator[dict[str, Any]]:
        traj = store.game(g)
        # TRUE winner via the store's outcome records (games.jsonl): the frame
        # end-record's "winner" was derived from the post-elimination live
        # player list in the fork (~always 0, wrong ~50% of games — found
        # 2026-07-11). Value labels before this fix were seat noise.
        winner = store.winner_seat(g)
        has_outcome = 1 if winner is not None else 0
        winner = -1 if winner is None else winner
        prior: list[dict] = []
        decs = traj.decisions
        for i, dec in enumerate(decs):
            task = TASK_OF_METHOD.get(dec.get("m"))
            # combat rets are null by construction (labels come from the
            # obs-side join), so the ret-None skip exempts attack/block
            if task is None or task not in self.tasks or dec.get("obs") is None \
                    or dec.get("ret") is None and task not in ("priority", "attack", "block"):
                prior.append(dec)
                continue
            if task == "trigger" and (dec.get("args") or {}).get("isMandatory"):
                # 99.7% of playTrigger calls; forced = no decision content, and
                # they'd flood the bool head with trivially-true labels. The
                # honest per-tag basis excludes forced either way.
                prior.append(dec)
                continue
            p = dec["p"]
            out = assemble(dec, traj.header, perspective=p,
                           history=history_tokens(prior, p, self.history_k,
                                                  now_pos=dec.get("_pos")),
                           full_vis=self.full_vis)
            row_of = out["entity_row_of"]

            # ---- shared pad values; each task fills its own labels ----
            cand_rows = [-1]
            cand_sa = [-1]
            cand_kind = [-1]
            label = 0
            label_row = -1
            tgt_kind = np.full(T_MAX + 1, -1, dtype=np.int64)
            tgt_idx = np.full(T_MAX + 1, -1, dtype=np.int64)
            x_val = -1
            bool_label = -1
            num_label, num_lo, num_hi = -1, 0, X_CLASSES - 1
            ctx_row = -1
            forced = 0
            cmb = {"cmb_rows": [], "cmb_count": [], "atk_label": [],
                   "cmb_count_label": [], "atk_tgt_kind": [], "atk_tgt_idx": [],
                   "blk_label": [], "blk_atk_rows": []}
            ret = dec.get("ret")
            args = dec.get("args") or {}

            if task == "priority":
                # candidates: PASS first, then (host row, SA) pairs in option
                # order; identical (row, normalized-sa) pairs collapse
                opts = dec.get("opts") or []
                key_of: dict[tuple[int, str], int] = {}
                for o in opts:
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
                if ret is not None:
                    plan = ret[0] if isinstance(ret, list) and ret else {}
                    host = plan.get("e")
                    r = row_of.get(host)
                    if r is None or all(k[0] != r for k in key_of):
                        raise ValueError(
                            f"game {g} s={dec['s']}: chosen host {host} not among candidate "
                            "rows — ADR-0005 superset violated; run `anvil.store validate`")
                    label_row = r
                    # SA-level label: exact oi -> exact string -> prefix-min -> masked
                    label = -1
                    oi = dec.get("oi")
                    if oi is not None and 0 <= oi < len(opts):
                        o = opts[oi]
                        label = key_of.get(
                            (row_of.get(o.get("e"), -1), norm_sa(o.get("sa", ""))), -1)
                    if label < 0:
                        psa = norm_sa(plan.get("sa", ""))
                        keys = [k for k in key_of if k[0] == r]
                        hit = [k for k in keys if k[1] == psa]
                        if not hit:
                            hit = [k for k in keys if _prefix_eq(k[1], psa)]
                        if len(hit) == 1:
                            label = key_of[hit[0]]
                    if label >= 0:
                        # target/X labels condition on the chosen candidate;
                        # masked windows leave them padded
                        refs = list(plan.get("tgt") or [])
                        for sb in plan.get("sub") or []:
                            refs.extend(sb.get("tgt") or [])
                        slot = 0
                        for ref in refs[:T_MAX]:
                            if "e" in ref and ref["e"] in row_of:
                                tgt_kind[slot], tgt_idx[slot] = 0, row_of[ref["e"]]
                                slot += 1
                            elif "pi" in ref:
                                tgt_kind[slot], tgt_idx[slot] = 1, ref["pi"]
                                slot += 1
                            # "str" refs (non-card/player/SA oddities) are unpointable; skipped
                        tgt_kind[slot], tgt_idx[slot] = 2, 0  # STOP
                        if plan.get("x") is not None:
                            x_val = min(int(plan["x"]), X_CLASSES - 1)
            elif task in ("mull_keep", "trigger", "binary"):
                bool_label = 1 if ret else 0
                if task == "trigger":  # mandatory ones skipped above
                    m = _HOST_ID.search(args.get("host") or "")
                    if m and int(m.group(1)) in row_of:
                        ctx_row = row_of[int(m.group(1))]
            elif task == "mull_tuck":
                # select-K via the target decoder: returned cards as entity
                # slots + STOP (cardsToReturn > T_MAX truncates; deep mulls rare)
                slot = 0
                for ref in (ret if isinstance(ret, list) else [])[:T_MAX]:
                    if isinstance(ref, dict) and ref.get("e") in row_of:
                        tgt_kind[slot], tgt_idx[slot] = 0, row_of[ref["e"]]
                        slot += 1
                tgt_kind[slot], tgt_idx[slot] = 2, 0  # STOP
            elif task == "number":
                num_lo = max(0, min(int(args.get("min", 0)), X_CLASSES - 1))
                num_hi = max(num_lo, min(int(args.get("max", X_CLASSES - 1)), X_CLASSES - 1))
                num_label = max(num_lo, min(int(ret), num_hi))
                forced = 1 if num_lo == num_hi else 0
            elif task in ("attack", "block"):
                f = (attack_fields(decs, i, dec, row_of,
                                   len(traj.header["players"]), g)
                     if task == "attack" else
                     block_fields(decs, i, dec, row_of, g))
                if f is None:  # forced-empty window (no candidates/attackers)
                    prior.append(dec)
                    continue
                cmb.update(f)

            hist = np.full((self.history_k, 3), -1, dtype=np.int64)
            for i, h in enumerate(out["history"][-self.history_k:]):
                hist[i] = (self.methods.id(h["m"]), h["self"], row_of.get(h["e"], -1))

            yield {
                "entities": torch.from_numpy(out["entities"]),
                "ent_emb": torch.tensor([self.embed.row(n) for n in out["entity_names"]],
                                        dtype=torch.int64),
                "globals": torch.from_numpy(out["globals"]),
                "players": torch.from_numpy(out["players"]),
                "history": torch.from_numpy(hist),
                "cand_rows": torch.tensor(cand_rows, dtype=torch.int64),
                "cand_sa": torch.tensor(cand_sa, dtype=torch.int64),
                "cand_kind": torch.tensor(cand_kind, dtype=torch.int64),
                "label": torch.tensor(label, dtype=torch.int64),
                "label_row": torch.tensor(label_row, dtype=torch.int64),
                "tgt_kind": torch.from_numpy(tgt_kind),
                "tgt_idx": torch.from_numpy(tgt_idx),
                "x_val": torch.tensor(x_val, dtype=torch.int64),
                "task": torch.tensor(TASKS[task], dtype=torch.int64),
                "bool_label": torch.tensor(bool_label, dtype=torch.int64),
                "num_label": torch.tensor(num_label, dtype=torch.int64),
                "num_lo": torch.tensor(num_lo, dtype=torch.int64),
                "num_hi": torch.tensor(num_hi, dtype=torch.int64),
                "ctx_row": torch.tensor(ctx_row, dtype=torch.int64),
                "forced": torch.tensor(forced, dtype=torch.int64),
                "has_outcome": torch.tensor(has_outcome, dtype=torch.int64),
                "won": torch.tensor(1 if winner == p else 0, dtype=torch.int64),
                **{k: torch.tensor(v, dtype=torch.int64) for k, v in cmb.items()},
            }
            prior.append(dec)

    def _epoch_games(self, store) -> list[int]:
        """Shard + shuffle this epoch's game order. Multi-epoch runs must not
        replay one order (the 2-epoch arm is the repetition-vs-diversity
        control); the epoch counter reseeds the shuffle each time a worker's
        iterator restarts. Worker respawn after a crash resets its counter —
        acceptable (matches pre-fix behavior, crash paths only)."""
        games = store.game_indices()
        if self.split is not None:
            games = [g for g in games if _split_of(g, self.games_per_pair) == self.split]
        if self.max_games is not None:
            games = games[:self.max_games]
        info = get_worker_info()
        if info is not None:
            games = games[info.id::info.num_workers]
        epoch, self._epoch = self._epoch, self._epoch + 1
        if self.shuffle_games:
            random.Random(self.seed + 100003 * epoch + (info.id if info else 0)).shuffle(games)
        return games

    def __iter__(self) -> Iterator[dict[str, Any]]:
        store = open_store(self.store_dir)  # per-worker handle
        for g in self._epoch_games(store):
            try:
                yield from self._examples(store, g)
            except Exception as e:
                if "did not decompress" in str(e):
                    continue  # quarantined frame (store policy)
                raise


def collate(batch: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
    """Pad entities/candidates to batch max; boolean masks carry validity."""
    b = len(batch)
    n = max(x["entities"].shape[0] for x in batch)
    c = max(x["cand_rows"].shape[0] for x in batch)
    f = batch[0]["entities"].shape[1]
    out = {
        "entities": torch.zeros(b, n, f),
        "ent_emb": torch.full((b, n), -1, dtype=torch.int64),
        "ent_mask": torch.zeros(b, n, dtype=torch.bool),
        "cand_rows": torch.full((b, c), -1, dtype=torch.int64),
        "cand_sa": torch.full((b, c), -1, dtype=torch.int64),
        "cand_kind": torch.full((b, c), -1, dtype=torch.int64),
        "cand_mask": torch.zeros(b, c, dtype=torch.bool),
        "globals": torch.stack([x["globals"] for x in batch]),
        "players": torch.stack([x["players"] for x in batch]),
        "history": torch.stack([x["history"] for x in batch]),
        "label": torch.stack([x["label"] for x in batch]),
        "label_row": torch.stack([x["label_row"] for x in batch]),
        "x_val": torch.stack([x["x_val"] for x in batch]),
        "has_outcome": torch.stack([x["has_outcome"] for x in batch]),
        "won": torch.stack([x["won"] for x in batch]),
        **{k: torch.stack([x[k] for x in batch]) for k in
           ("task", "bool_label", "num_label", "num_lo", "num_hi", "ctx_row", "forced")},
    }
    # target labels -> class ids over the padded batch: [0,n) entity rows,
    # [n, n+p) players, n+p = STOP; -1 stays "no slot" (loss ignore_index)
    p = batch[0]["players"].shape[0]
    kinds = torch.stack([x["tgt_kind"] for x in batch])
    idxs = torch.stack([x["tgt_idx"] for x in batch])
    tgt = torch.full_like(kinds, -1)
    tgt = torch.where(kinds == 0, idxs, tgt)
    tgt = torch.where(kinds == 1, n + idxs, tgt)
    tgt = torch.where(kinds == 2, torch.full_like(tgt, n + p), tgt)
    out["tgt_labels"] = tgt
    # combat (D5): per-candidate-row fields padded to batch max; attack
    # targets become class ids like tgt_labels (no STOP class); block labels
    # remap each example's none class (= its attacker count) to the batch
    # none slot M (the model's learned none key sits at index M)
    A = max(1, max(x["cmb_rows"].shape[0] for x in batch))
    M = max(1, max(x["blk_atk_rows"].shape[0] for x in batch))
    out["cmb_rows"] = torch.full((b, A), -1, dtype=torch.int64)
    out["cmb_mask"] = torch.zeros(b, A, dtype=torch.bool)
    out["cmb_count"] = torch.zeros(b, A, dtype=torch.int64)
    out["atk_label"] = torch.full((b, A), -1, dtype=torch.int64)
    out["cmb_count_label"] = torch.full((b, A), -1, dtype=torch.int64)
    out["atk_tgt_labels"] = torch.full((b, A), -1, dtype=torch.int64)
    out["blk_label"] = torch.full((b, A), -1, dtype=torch.int64)
    out["blk_atk_rows"] = torch.full((b, M), -1, dtype=torch.int64)
    out["blk_atk_mask"] = torch.zeros(b, M, dtype=torch.bool)
    for i, x in enumerate(batch):
        ni, ci = x["entities"].shape[0], x["cand_rows"].shape[0]
        out["entities"][i, :ni] = x["entities"]
        out["ent_emb"][i, :ni] = x["ent_emb"]
        out["ent_mask"][i, :ni] = True
        out["cand_rows"][i, :ci] = x["cand_rows"]
        out["cand_sa"][i, :ci] = x["cand_sa"]
        out["cand_kind"][i, :ci] = x["cand_kind"]
        out["cand_mask"][i, :ci] = True
        ai, mi = x["cmb_rows"].shape[0], x["blk_atk_rows"].shape[0]
        if ai:
            out["cmb_rows"][i, :ai] = x["cmb_rows"]
            out["cmb_mask"][i, :ai] = True
            out["cmb_count"][i, :ai] = x["cmb_count"]
            out["cmb_count_label"][i, :ai] = x["cmb_count_label"]
        if x["atk_label"].shape[0]:  # attack windows only
            out["atk_label"][i, :ai] = x["atk_label"]
            tk, ti = x["atk_tgt_kind"], x["atk_tgt_idx"]
            cls = torch.where(tk == 0, ti, torch.full_like(ti, -1))
            cls = torch.where(tk == 1, n + ti, cls)
            out["atk_tgt_labels"][i, :ai] = cls
        if x["blk_label"].shape[0]:  # block windows only
            lab = x["blk_label"]
            out["blk_label"][i, :ai] = torch.where(lab == mi,
                                                   torch.full_like(lab, M), lab)
        if mi:
            out["blk_atk_rows"][i, :mi] = x["blk_atk_rows"]
            out["blk_atk_mask"][i, :mi] = True
    return out
