"""Ante v0 ledger (design §7): AIVAT-style chance-node corrections over the
trajectory store.

At each corrected chance node, correction = v(actual outcome) − E[v(c)] over
the known distribution of the chance outcome c. Corrections are zero-mean by
construction for ANY value function v — critic quality sets only how much
variance they remove — so the apparatus certifies (mirror batch: ledger sums
to ~0, corrected winrate converges to 50% no slower than raw) with the
current BC value head, and the variance-reduction number is re-measured when
the D4 rollout-labeled critic lands.

v0 chance-node classes (per the 2026-07-11 D4 scope decision):

- **opener**: the FIRST `mulliganKeepHand` dec per player = the opening 7,
  a uniform 7-subset of (hand ∪ derived library). E[v] by Monte Carlo over
  sampled hands (an MC estimate of the expectation keeps the correction
  zero-mean; it only adds a little variance). Re-deal keeps are EXCLUDED
  (v1.1): Forge's London mulligan tucks before the keep decision, so those
  windows show a choice-filtered hand, not a chance outcome — measured
  +0.0076/node bias (t=+5.5) on the 12.8K-game mirror before exclusion.
- **draw**: k never-before-seen entity ids entering p's hand between
  consecutive decision records, with p's library count dropping by exactly k
  — a uniform k-subset of the library-before multiset. Exact enumeration for
  k=1 (weighted by multiplicity), MC for k>1. Draws are corrected only when
  the uniform distribution is *provable*:
    - p has no prior library-ORDER knowledge (`ORDER_METHODS` dec ⇒ p is
      poisoned for the rest of the game — v0-conservative; a shuffle would
      cleanse, but shuffles are not observable as decision records);
    - the drawn ids were never serialized in any earlier record (looked-at
      library tops appear as library rows under schema 5a, so a known-top
      card fails this check);
    - London put-backs (`tuckCardsViaMulligan`) are handled exactly: the
      tucked cards are known-bottom, so they are EXCLUDED from the candidate
      multiset, and correction stops when the library shrinks near the known
      bottom (`BOTTOM_MARGIN`).
- **die** (play/draw): recorded per game (`on_play`); the correction is
  applied at aggregation time with a split-half empirical on-play winrate
  (certify.py), which keeps it zero-mean for any constant.

Counterfactual values come from *observation surgery*: the logged full-state
record with the drawn/dealt cards' names swapped for the counterfactual ones
(hand rows carry only {e, n, z, c}, so a name swap IS the counterfactual
state at that record), re-assembled from p's perspective, batched through
the checkpoint's value head. The actual outcome is evaluated through the
identical path (identity surgery), so v(actual) and E[v(c)] share every
approximation — the zero-mean property survives any surgery infidelity.

Library multisets are never trusted blind: derived library = decklist −
(all serialized non-library, non-token entities owned by p), and a node is
skipped (and counted in `skips`) unless the derived total matches the
record's library count exactly.
"""

from __future__ import annotations

import dataclasses
import random
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import torch

from anvil.encoder.transform import HISTORY_K, assemble, history_tokens
from anvil.store.trajectories import GameTrajectory
from anvil.training.dataset import (T_MAX, TASK_OF_METHOD, TASKS, X_CLASSES,
                                    EmbeddingCache, MethodVocab, collate,
                                    default_methods)
from anvil.training.train import build_net

DECKS_DIR = Path(__file__).parents[2] / "data/pool/decks"

# Decs that give the acting player knowledge of (or control over) their
# library ORDER: subsequent draws by that player are no longer provably
# uniform over the multiset (scry-to-bottom leaves known-NOT-top information
# even though the card was serialized). v0 poisons the player game-long.
ORDER_METHODS = {"arrangeForScry", "arrangeForSurveil", "willPutCardOnTop",
                 "orderMoveToZoneList"}
BOTTOM_MARGIN = 20  # stop draw corrections when lib count nears known-bottom tucks
MC_SAMPLES = 16     # Monte Carlo hands per opener / multi-draw node

_deck_cache: dict[str, Counter] = {}


def deck_multiset(name: str) -> Counter:
    """Parse data/pool/decks/<name>.dck -> card-name multiset (Commander+Main)."""
    if name not in _deck_cache:
        c: Counter = Counter()
        section = None
        for line in (DECKS_DIR / f"{name}.dck").read_text().splitlines():
            line = line.strip()
            if line.startswith("["):
                section = line.strip("[]").lower()
            elif line and section in ("commander", "main"):
                n, _, nm = line.partition(" ")
                c[nm.strip()] += int(n)
        _deck_cache[name] = c
    return Counter(_deck_cache[name])


def derive_library(deck: Counter, obs: dict, p: int) -> Counter | None:
    """decklist − serialized entities owned by p; None unless the total
    matches the record's library count exactly (the per-node self-check:
    name-form drift, DFC back faces, stack copies etc. all land here)."""
    out = Counter(deck)
    for e in obs["ents"]:
        if e.get("tok") or e["z"] == "library" or e.get("o", e["c"]) != p:
            continue
        if e["n"] not in deck:
            # engine pseudo-cards (Commander Effect, adventure trackers) are
            # not library-relevant; a RENAMED deck card (transformed DFC)
            # skipped here leaves the derived total one high, so the count
            # check below still catches it.
            continue
        out[e["n"]] -= 1
        if out[e["n"]] < 0:
            return None
        if out[e["n"]] == 0:
            del out[e["n"]]
    if sum(out.values()) != obs["players"][p]["lib"]:
        return None
    return out


@dataclasses.dataclass
class Node:
    cls: str              # "opener" | "draw"
    p: int                # the player whose chance outcome this is
    dec: dict             # the record whose obs the node evaluates at
    prior_idx: int        # decisions[:prior_idx] = history for the window
    drawn: dict[int, str]  # entity id -> actual name (the k cards / the 7)
    pool: Counter         # candidate multiset INCLUDING the actual cards
    k: int


def extract(traj: GameTrajectory,
            decks: dict[int, Counter]) -> tuple[list[Node], int | None, Counter]:
    """Walk one game's decision stream -> (nodes, on_play seat, skip census)."""
    n_players = len(traj.header["players"])
    seen: set[int] = set()
    poisoned = [False] * n_players
    tucked: list[list[str]] = [[] for _ in range(n_players)]
    hand_prev: list[set[int]] = [set() for _ in range(n_players)]
    lib_prev: list[int | None] = [None] * n_players
    mull_count = [0] * n_players  # keep decs seen; 0 = the pure-chance opening 7
    nodes: list[Node] = []
    skips: Counter = Counter()
    on_play: int | None = None

    for i, dec in enumerate(traj.decisions):
        obs = dec.get("obs")
        if obs is None:
            continue
        glob = obs["glob"]
        turn = glob.get("turn", 0)
        if on_play is None and turn >= 1 and glob.get("ap", -1) >= 0:
            on_play = glob["ap"]
        m = dec["m"]
        p_dec = dec.get("p", -1)

        hands: list[dict[int, str]] = [{} for _ in range(n_players)]
        for e in obs["ents"]:
            if e["z"] == "hand" and not e.get("tok") and 0 <= e["c"] < n_players:
                hands[e["c"]][e["e"]] = e["n"]

        if m == "mulliganKeepHand" and p_dec >= 0:
            hand = hands[p_dec]
            lib = derive_library(decks[p_dec], obs, p_dec)
            if mull_count[p_dec] > 0:
                # RE-DEAL keeps are NOT pure chance: Forge's London mulligan
                # tucks BEFORE the keep decision (mulliganDraw() draws 7 then
                # immediately asks tuckCardsViaMulligan), so this window's
                # hand is a choice-filtered best-k-of-7 — treating it as a
                # uniform k-subset biased the class (+0.0076/node, t=+5.5 on
                # the 12.8K-game mirror; deal #0 read clean at t=+0.5).
                # Correct anchor for re-deals = the tuck dec's pre-choice 7;
                # queued behind the critic upgrade. v1.1 skips them.
                skips["opener_redeal"] += 1
            elif lib is None:
                skips["opener_lib_mismatch"] += 1
            elif not 1 <= len(hand) <= 7:
                skips["opener_hand_size"] += 1
            else:
                nodes.append(Node("opener", p_dec, dec, i, dict(hand),
                                  lib + Counter(hand.values()), len(hand)))
            mull_count[p_dec] += 1
        elif turn >= 1:
            for p in range(n_players):
                if lib_prev[p] is None:
                    continue
                hand_now = hands[p]
                lib_now = obs["players"][p]["lib"]
                new = [e for e in hand_now if e not in hand_prev[p]]
                new_unseen = [e for e in new if e not in seen]
                if not new_unseen:
                    continue
                k = len(new_unseen)
                if poisoned[p]:
                    skips["draw_poisoned"] += k
                elif len(new) != k:
                    skips["draw_mixed_sources"] += k
                elif lib_prev[p] - lib_now != k:
                    skips["draw_lib_delta"] += k
                elif tucked[p] and lib_now - len(tucked[p]) < BOTTOM_MARGIN:
                    skips["draw_bottom_margin"] += k
                else:
                    lib_after = derive_library(decks[p], obs, p)
                    if lib_after is None:
                        skips["draw_lib_mismatch"] += k
                    else:
                        drawn = {e: hand_now[e] for e in new_unseen}
                        pool = lib_after + Counter(drawn.values())
                        ok = True
                        for nm in tucked[p]:  # known-bottom exclusion
                            pool[nm] -= 1
                            if pool[nm] <= 0:
                                if pool[nm] < 0:
                                    ok = False  # tucked card not in derived lib
                                    break
                                del pool[nm]
                        if ok:
                            nodes.append(Node("draw", p, dec, i, drawn, pool, k))
                        else:
                            skips["draw_tuck_mismatch"] += k

        for p in range(n_players):
            hand_prev[p] = set(hands[p])
            lib_prev[p] = obs["players"][p]["lib"]
        seen.update(e["e"] for e in obs["ents"])
        if m == "tuckCardsViaMulligan" and p_dec >= 0 and isinstance(dec.get("ret"), list):
            by_id = {e["e"]: e["n"] for e in obs["ents"]}
            for ref in dec["ret"]:
                if isinstance(ref, dict) and ref.get("e") in by_id:
                    tucked[p_dec].append(by_id[ref["e"]])
        if p_dec >= 0 and m in ORDER_METHODS:
            poisoned[p_dec] = True

    return nodes, on_play, skips


def swap_hand(dec: dict, mapping: dict[int, str]) -> dict:
    """Observation surgery: the same record with hand-card names swapped."""
    obs = dec["obs"]
    ents = [({**e, "n": mapping[e["e"]]} if e["e"] in mapping else e)
            for e in obs["ents"]]
    return {**dec, "obs": {**obs, "ents": ents}}


class ValueEvaluator:
    """Batched value-head eval of (possibly surgered) decision records,
    from an arbitrary perspective. Trunk state ignores candidate rows, so
    windows carry a PASS-only candidate pad."""

    def __init__(self, ckpt: str, device: str | None = None, batch: int = 256):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        ck = torch.load(ckpt, map_location=self.device, weights_only=False)
        cfg = ck["config"]
        methods = default_methods()
        self.net = build_net(cfg["embed"], cfg["pool_manifest"], len(methods),
                             n_sa=cfg.get("sa_vocab_size", 0)).to(self.device)
        self.net.load_compat(ck["model"])
        self.net.eval()
        # full-vis critics (M2 D4) evaluate on full-vis windows — §7's
        # omniscient-critic tier; detected from the ckpt's fine-tune stamp
        self.full_vis = bool((cfg.get("value_finetune") or {}).get("full_vis"))
        if self.full_vis:
            print("[ante] full-visibility critic checkpoint — omniscient windows")
        self.embed = EmbeddingCache(Path(cfg["embed"]))
        self.methods = MethodVocab(methods)
        self.batch = batch
        self.step = ck.get("step")
        self.ckpt = str(ckpt)
        self.emb_misses: Counter = Counter()

    def example(self, dec: dict, header: dict, perspective: int,
                prior: list[dict]) -> dict[str, Any]:
        out = assemble(dec, header, perspective=perspective,
                       history=history_tokens(prior, perspective, HISTORY_K,
                                              now_pos=dec.get("_pos")),
                       full_vis=self.full_vis)
        row_of = out["entity_row_of"]
        hist = np.full((HISTORY_K, 3), -1, dtype=np.int64)
        for j, h in enumerate(out["history"][-HISTORY_K:]):
            hist[j] = (self.methods.id(h["m"]), h["self"], row_of.get(h["e"], -1))
        emb = []
        for n in out["entity_names"]:
            r = self.embed.row(n)
            if r < 0 and n is not None:
                self.emb_misses[n] += 1
            emb.append(r)
        task = TASKS.get(TASK_OF_METHOD.get(dec.get("m"), "priority"), 0)
        z = lambda v: torch.tensor(v, dtype=torch.int64)  # noqa: E731
        return {
            "entities": torch.from_numpy(out["entities"]),
            "ent_emb": torch.tensor(emb, dtype=torch.int64),
            "globals": torch.from_numpy(out["globals"]),
            "players": torch.from_numpy(out["players"]),
            "history": torch.from_numpy(hist),
            "cand_rows": z([-1]), "cand_sa": z([-1]), "cand_kind": z([-1]),
            "label": z(0), "label_row": z(-1),
            "tgt_kind": torch.full((T_MAX + 1,), -1, dtype=torch.int64),
            "tgt_idx": torch.full((T_MAX + 1,), -1, dtype=torch.int64),
            "x_val": z(-1), "task": z(task), "bool_label": z(-1),
            "num_label": z(-1), "num_lo": z(0), "num_hi": z(X_CLASSES - 1),
            "ctx_row": z(-1), "forced": z(0), "has_outcome": z(0), "won": z(0),
        }

    @torch.no_grad()
    def win_probs(self, examples: list[dict]) -> np.ndarray:
        out = []
        for i in range(0, len(examples), self.batch):
            chunk = collate(examples[i:i + self.batch])
            chunk = {k: v.to(self.device) for k, v in chunk.items()}
            with torch.autocast(self.device, dtype=torch.bfloat16):
                res = self.net(chunk)
            out.append(torch.sigmoid(res["value_logit"].float()).cpu().numpy())
        return np.concatenate(out) if out else np.zeros(0)


def eval_nodes(ev: ValueEvaluator, traj: GameTrajectory, nodes: list[Node],
               rng: random.Random, mc: int = MC_SAMPLES) -> list[dict]:
    """Per node: v(actual) − E[v(c)]; exact enumeration for k=1 draws,
    MC hands elsewhere. Values are win probabilities for node.p."""
    header = traj.header
    rows = []
    for node in nodes:
        prior = traj.decisions[:node.prior_idx]
        exs = [ev.example(node.dec, header, node.p, prior)]  # index 0 = actual
        weights = None
        ids = sorted(node.drawn)
        if node.cls == "draw" and node.k == 1:
            names = sorted(node.pool)
            weights = np.array([node.pool[n] for n in names], dtype=np.float64)
            exs += [ev.example(swap_hand(node.dec, {ids[0]: nm}),
                               header, node.p, prior) for nm in names]
        else:
            flat = sorted(node.pool.elements())
            exs += [ev.example(swap_hand(node.dec, dict(zip(ids, rng.sample(flat, node.k)))),
                               header, node.p, prior) for _ in range(mc)]
        v = ev.win_probs(exs)
        v_act = float(v[0])
        e_v = float(np.average(v[1:], weights=weights))
        rows.append({"cls": node.cls, "p": node.p, "k": node.k,
                     "turn": node.dec["obs"]["glob"].get("turn", 0),
                     "m": node.dec["m"],
                     "v": round(v_act, 6), "ev": round(e_v, 6),
                     "corr": round(v_act - e_v, 6), "n_cand": len(v) - 1})
    return rows


def game_ledger(ev: ValueEvaluator, traj: GameTrajectory, winner: int | None,
                mc: int = MC_SAMPLES) -> dict | None:
    """One game -> ledger record (None for non-decisive games). `winner` is
    the TRUE winning seat from the store's outcome records (games.jsonl via
    TrajectoryStore.winner_seat) — never the frame end-record's broken field."""
    if winner is None:
        return None
    end = traj.end or {}
    decks = {i: deck_multiset(pl["deck"])
             for i, pl in enumerate(traj.header["players"])}
    nodes, on_play, skips = extract(traj, decks)
    rng = random.Random(traj.header["seed"] & 0x7FFFFFFF)  # deterministic MC
    return {"g": traj.game_index, "seed": traj.header["seed"],
            "winner": winner, "turns": end.get("turns"),
            "on_play": on_play,
            "decks": [pl["deck"] for pl in traj.header["players"]],
            "profiles": [pl.get("profile") for pl in traj.header["players"]],
            "nodes": eval_nodes(ev, traj, nodes, rng, mc),
            "skips": dict(skips)}
