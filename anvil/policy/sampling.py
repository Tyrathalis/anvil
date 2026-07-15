"""Seeded Gumbel-max sampling for serve-time exploration (M2 D6).

The V-trace actor samples instead of argmaxing. Noise is generated per
decision at the ITEM's own (unpadded) shapes from a Philox stream keyed by
(game_seed, dec seq) via the SplitMix64 convention (harness/seeds.py), then
scattered into the padded GPU batch — samples are therefore deterministic per
decision and independent of micro-batch composition (the D1 twin-determinism
property must survive batching; contiguous padding would misalign the
player/STOP/none columns and silently break it).

Gumbel-max = exact categorical sampling: argmax(logits + g), g ~ Gumbel(0,1).
Bernoulli heads use the logistic sign test: (logit + l) > 0, l ~ Logistic(0,1).
Masked positions carry -1e9 logits, so zero noise there never wins.
"""

from __future__ import annotations

import numpy as np
import torch

from anvil.bridge.harness.seeds import GOLDEN, MASK, splitmix64
from anvil.training.dataset import COMBAT_COUNT_MAX, T_MAX, X_CLASSES

# heads sampled per task; draw order within a task is FIXED (determinism)
_TASK_HEADS = {
    "priority": ("choice", "tgt", "x"),
    "mull_keep": ("bool",),
    "trigger": ("bool",),
    "binary": ("bool",),
    "number": ("num",),
    "attack": ("atk", "cnt", "atk_tgt"),
    "block": ("blk", "cnt"),
}


def noise_seed(game_seed: int, dec_seq: int) -> int:
    """Per-decision noise key, same keyed-stream shape as game_seed()."""
    return splitmix64((game_seed + (dec_seq + 1) * GOLDEN) & MASK)


def make_noise(ex: dict, task: str, temperature: float = 1.0, *,
               seed: int) -> dict[str, torch.Tensor]:
    """Item-level noise tensors at the example's own shapes, float32.

    temperature scales the noise INVERSELY (argmax(l/t + g) == argmax(l + t*g)),
    so act() never needs to rescale logits; logp is still reported for the
    tempered distribution by the caller when t != 1.
    """
    rng = np.random.Generator(np.random.Philox(seed))
    tiny = np.finfo(np.float64).tiny

    def gumbel(*shape: int) -> torch.Tensor:
        u = np.clip(rng.random(shape), tiny, 1.0 - 1e-16)
        return torch.from_numpy((-np.log(-np.log(u)) * temperature).astype(np.float32))

    def logistic(*shape: int) -> torch.Tensor:
        u = np.clip(rng.random(shape), tiny, 1.0 - 1e-16)
        return torch.from_numpy(((np.log(u) - np.log1p(-u)) * temperature).astype(np.float32))

    n = ex["entities"].shape[0]
    p = ex["players"].shape[0]
    a = ex["cmb_rows"].shape[0]
    m = ex["blk_atk_rows"].shape[0]
    shapes = {
        "choice": lambda: gumbel(ex["cand_rows"].shape[0]),
        "tgt": lambda: gumbel(T_MAX + 1, n + p + 1),
        "x": lambda: gumbel(X_CLASSES),
        "bool": lambda: logistic(1),
        "num": lambda: gumbel(X_CLASSES),
        "atk": lambda: logistic(a),
        "cnt": lambda: gumbel(a, COMBAT_COUNT_MAX),
        "atk_tgt": lambda: gumbel(a, n + p),
        "blk": lambda: gumbel(a, m + 1),
    }
    return {h: shapes[h]() for h in _TASK_HEADS[task]}


def mu_record(g: int, s: int, task: str, ex: dict, aux: dict,
              out: dict) -> dict:
    """Behavior-policy record for one sampled decision (one mu.jsonl line).

    Actions are recorded in item-canonical index spaces (entity ROW < N_i;
    player = N_i + p; block none = M_i) so the RL loader — which rebuilds the
    identical window (serve/loader parity) — can recompute logp under any
    checkpoint. Composite inclusion rules (which factors are part of the
    action) must stay in lockstep with anvil.training.rl.apply_mu_labels:
      priority: choice, + tgt/x iff choice > 0
      one-field: the single bool/num factor
      attack: every real row's yes/no, + cnt (group>1) / target for yes rows
      block: every real row's slot pick, + cnt for blocking group>1 rows
    """
    n_pad, stop = int(out["n_ent"]), int(out["stop_idx"])
    n_i = ex["entities"].shape[0]
    rec: dict = {"g": g, "s": s, "task": task}
    lp: dict[str, float] = {}
    ent: dict[str, float] = {}

    def canon(pick: int) -> int:  # padded key index -> item-canonical
        return pick if pick < n_pad else n_i + (pick - n_pad)

    if task == "priority":
        c = int(out["choice"][0])
        rec["c"] = c
        lp["choice"] = float(out["logp_choice"][0])
        ent["choice"] = float(out["ent_choice"][0])
        if c > 0:
            picks = []
            for t in range(out["tgt_picks"].shape[1]):
                pk = int(out["tgt_picks"][0, t])
                if pk == stop:
                    break
                picks.append(canon(pk))
            rec["tgt"] = picks
            rec["x"] = int(out["x_cls"][0])
            lp["tgt"] = float(out["logp_tgt"][0])
            lp["x"] = float(out["logp_x"][0])
            ent["tgt"] = float(out["ent_tgt"][0])
            ent["x"] = float(out["ent_x"][0])
    elif task in ("mull_keep", "trigger", "binary"):
        rec["b"] = int(bool(out["bool"][0]))
        lp["bool"] = float(out["logp_bool"][0])
        ent["bool"] = float(out["ent_bool"][0])
    elif task == "number":
        rec["n"] = int(out["num"][0])
        lp["num"] = float(out["logp_num"][0])
        ent["num"] = float(out["ent_num"][0])
    elif task in ("attack", "block"):
        a_i = len(aux["cmb_rows"])
        groups = [len(aux["cmb_members"][r]) for r in aux["cmb_rows"]]
        rec["cnt"] = [int(out["cmb_count"][0, i]) for i in range(a_i)]
        if task == "attack":
            yes = [bool(out["atk_yes"][0, i]) for i in range(a_i)]
            rec["atk"] = [int(y) for y in yes]
            rec["atgt"] = [canon(int(out["atk_tgt"][0, i])) for i in range(a_i)]
            lp["atk"] = float(out["logp_atk"][0, :a_i].sum())
            lp["cnt"] = float(sum(out["logp_cnt"][0, i] for i in range(a_i)
                                  if yes[i] and groups[i] > 1))
            lp["atgt"] = float(sum(out["logp_atk_tgt"][0, i]
                                   for i in range(a_i) if yes[i]))
            ent["atk"] = float(out["ent_atk"][0, :a_i].mean()) if a_i else 0.0
        else:
            m_i = len(aux["blk_atk_rows"])
            blocking = [int(out["blk_pick"][0, i]) < m_i for i in range(a_i)]
            rec["blk"] = [min(int(out["blk_pick"][0, i]), m_i) for i in range(a_i)]
            lp["blk"] = float(out["logp_blk"][0, :a_i].sum())
            lp["cnt"] = float(sum(out["logp_cnt"][0, i] for i in range(a_i)
                                  if blocking[i] and groups[i] > 1))
            ent["blk"] = float(out["ent_blk"][0, :a_i].mean()) if a_i else 0.0
    rec["lp"] = {k: round(v, 5) for k, v in lp.items()}
    rec["logp"] = round(sum(lp.values()), 5)
    rec["ent"] = {k: round(v, 4) for k, v in ent.items()}
    return rec


def pad_noise(noises: list[dict[str, torch.Tensor]], batch: dict,
              device) -> dict[str, torch.Tensor]:
    """Scatter item noise into batch-padded tensors (zeros elsewhere).

    Layout-aware: tgt/atk_tgt keys are [entities.. players.. (STOP)], blk keys
    are [attacker slots.. none], so the trailing columns sit at the PADDED
    offset, not the item's own.
    """
    b = len(noises)
    n = batch["entities"].shape[1]
    c = batch["cand_rows"].shape[1]
    p = batch["players"].shape[1]
    a = batch["cmb_rows"].shape[1]
    m = batch["blk_atk_rows"].shape[1]
    out = {
        "choice": torch.zeros(b, c), "tgt": torch.zeros(b, T_MAX + 1, n + p + 1),
        "x": torch.zeros(b, X_CLASSES), "bool": torch.zeros(b),
        "num": torch.zeros(b, X_CLASSES), "atk": torch.zeros(b, a),
        "cnt": torch.zeros(b, a, COMBAT_COUNT_MAX),
        "atk_tgt": torch.zeros(b, a, n + p), "blk": torch.zeros(b, a, m + 1),
    }
    for i, nz in enumerate(noises):
        if "choice" in nz:
            out["choice"][i, : nz["choice"].shape[0]] = nz["choice"]
        if "tgt" in nz:
            ni = nz["tgt"].shape[1] - p - 1
            out["tgt"][i, :, :ni] = nz["tgt"][:, :ni]
            out["tgt"][i, :, n:] = nz["tgt"][:, ni:]
        if "x" in nz:
            out["x"][i] = nz["x"]
        if "bool" in nz:
            out["bool"][i] = nz["bool"][0]
        if "num" in nz:
            out["num"][i] = nz["num"]
        if "atk" in nz:
            out["atk"][i, : nz["atk"].shape[0]] = nz["atk"]
        if "cnt" in nz:
            out["cnt"][i, : nz["cnt"].shape[0]] = nz["cnt"]
        if "atk_tgt" in nz:
            ai, ki = nz["atk_tgt"].shape
            ni = ki - p
            out["atk_tgt"][i, :ai, :ni] = nz["atk_tgt"][:, :ni]
            out["atk_tgt"][i, :ai, n:] = nz["atk_tgt"][:, ni:]
        if "blk" in nz:
            ai, ki = nz["blk"].shape
            mi = ki - 1
            out["blk"][i, :ai, :mi] = nz["blk"][:, :mi]
            out["blk"][i, :ai, m] = nz["blk"][:, mi]
    return {k: v.to(device) for k, v in out.items()}
