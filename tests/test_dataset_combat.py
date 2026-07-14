"""D5 combat label extraction: attack_fields / block_fields / the bounded
join / collate remapping, on hand-built dec records (no store needed).

Entity/row fixture: decider p=0 owns a dedup PAIR (ids 1,2 -> row 0) and a
unique creature (id 3 -> row 1); opponent p=1 attacks with ids 10,11
(row 5) and has a planeswalker id 20 (row 7). row_of is handed to the
helpers directly — dedup semantics are the transform's tests' job.
"""

from __future__ import annotations

import pytest
import torch

from anvil.training.dataset import (COMBAT_COUNT_MAX, _combat_label_window,
                                    attack_fields, block_fields, collate)

ROW_OF = {1: 0, 2: 0, 3: 1, 10: 5, 11: 5, 20: 7}


def ent(eid, c=0, tap=0, sick=0, **kw):
    e = {"e": eid, "z": "battlefield", "c": c, "pt": [2, 2]}
    if tap:
        e["tap"] = 1
    if sick:
        e["sick"] = 1
    e.update(kw)
    return e


def dec_of(m, ents, turn=5, p=0, s=100):
    return {"m": m, "p": p, "s": s,
            "obs": {"glob": {"turn": turn}, "ents": ents}}


def test_attack_labels_pair_partial_and_target():
    d = dec_of("declareAttackers", [ent(1), ent(2), ent(3)])
    # label window: 1 of the pair attacks the opponent, the unique sits home
    lw = dec_of("x", [ent(1, atk={"pi": 1}), ent(2), ent(3)])
    f = attack_fields([d, lw], 0, d, ROW_OF, 2, g=0)
    assert f["cmb_rows"] == [0, 1]
    assert f["cmb_count"] == [2, 1]
    assert f["atk_label"] == [1, 0]
    assert f["cmb_count_label"] == [0, -1]        # k=1 of the pair -> class 0
    assert f["atk_tgt_kind"] == [1, -1]           # player target
    assert f["atk_tgt_idx"] == [1, -1]            # seat 1 -> player position 1


def test_attack_planeswalker_target_and_full_group():
    d = dec_of("declareAttackers", [ent(1), ent(2)])
    lw = dec_of("x", [ent(1, atk={"e": 20}), ent(2, atk={"e": 20})])
    f = attack_fields([d, lw], 0, d, ROW_OF, 2, g=0)
    assert f["atk_label"] == [1]
    assert f["cmb_count_label"] == [1]            # k=2 -> class 1
    assert f["atk_tgt_kind"] == [0]
    assert f["atk_tgt_idx"] == [ROW_OF[20]]       # entity-row target


def test_attack_mixed_group_targets_mask():
    d = dec_of("declareAttackers", [ent(1), ent(2)])
    lw = dec_of("x", [ent(1, atk={"pi": 1}), ent(2, atk={"e": 20})])
    f = attack_fields([d, lw], 0, d, ROW_OF, 2, g=0)
    assert f["atk_label"] == [1]
    assert f["cmb_count_label"] == [1]
    assert f["atk_tgt_kind"] == [-1]              # split targets -> masked


def test_attack_empty_label_and_eligibility():
    # tapped + sick excluded from candidates; no label window -> all-zero labels
    d = dec_of("declareAttackers", [ent(1), ent(2, tap=1), ent(3, sick=1)])
    f = attack_fields([d], 0, d, ROW_OF, 2, g=0)
    assert f["cmb_rows"] == [0] and f["cmb_count"] == [1]
    assert f["atk_label"] == [0]
    # no eligible creatures -> forced-empty window, skipped
    d2 = dec_of("declareAttackers", [ent(1, tap=1)])
    assert attack_fields([d2], 0, d2, ROW_OF, 2, g=0) is None


def test_join_bounded_at_next_combat():
    # the dec's own combat never flags; a later combat this turn does. The
    # bounded join must return the EMPTY label, not the later combat's map
    # (the 145-violation overshoot class, classified 2026-07-13).
    d = dec_of("declareAttackers", [ent(1)])
    redeclare = dec_of("declareAttackers", [ent(1)], s=101)
    later = dec_of("x", [ent(1, atk={"pi": 1})], s=102)
    assert _combat_label_window([d, redeclare, later], 0, 5, "atk") is None
    f = attack_fields([d, redeclare, later], 0, d, ROW_OF, 2, g=0)
    assert f["atk_label"] == [0]
    # turn boundary still bounds
    next_turn = dec_of("x", [ent(1, atk={"pi": 1})], turn=6)
    assert _combat_label_window([d, next_turn], 0, 5, "atk") is None


def test_attack_superset_violation_raises():
    d = dec_of("declareAttackers", [ent(1, tap=1), ent(3)])
    lw = dec_of("x", [ent(1, atk={"pi": 1}, tap=1), ent(3)])
    with pytest.raises(ValueError, match="superset"):
        attack_fields([d, lw], 0, d, ROW_OF, 2, g=0)


def test_block_labels_none_and_pointer():
    atk = [ent(10, c=1, atk={"pi": 0}), ent(11, c=1, atk={"pi": 0})]
    d = dec_of("declareBlockers", [ent(1), ent(2), ent(3), *atk])
    lw = dec_of("x", [ent(1, blk=[10]), ent(2), ent(3), *atk])
    f = block_fields([d, lw], 0, d, ROW_OF, g=0)
    assert f["blk_atk_rows"] == [5]               # ids 10,11 dedup to one row
    assert f["cmb_rows"] == [0, 1]
    assert f["blk_label"] == [0, 1]               # pair blocks slot 0; unique = none(1)
    assert f["cmb_count_label"] == [0, -1]        # 1 of the pair blocks -> class 0
    # sick creatures may block
    d2 = dec_of("declareBlockers", [ent(3, sick=1), *atk])
    f2 = block_fields([d2], 0, d2, ROW_OF, g=0)
    assert f2["cmb_rows"] == [1]
    assert f2["blk_label"] == [1]                 # empty label -> none class


def test_block_split_group_masks_and_forced_empty():
    atk = [ent(10, c=1, atk={"pi": 0}), ent(20, c=1, atk={"pi": 0})]
    d = dec_of("declareBlockers", [ent(1), ent(2), *atk])
    lw = dec_of("x", [ent(1, blk=[10]), ent(2, blk=[20]), *atk])
    f = block_fields([d, lw], 0, d, ROW_OF, g=0)
    assert f["blk_label"] == [-1]                 # pair split across attackers
    assert f["cmb_count_label"] == [1]            # but 2 of the pair do block
    # no attackers in obs -> skipped window
    d2 = dec_of("declareBlockers", [ent(1)])
    assert block_fields([d2], 0, d2, ROW_OF, g=0) is None


def test_block_target_not_attacker_raises():
    d = dec_of("declareBlockers", [ent(1), ent(10, c=1, atk={"pi": 0})])
    lw = dec_of("x", [ent(1, blk=[20]), ent(10, c=1, atk={"pi": 0})])
    with pytest.raises(ValueError, match="not an attacker"):
        block_fields([d, lw], 0, d, ROW_OF, g=0)


def _example(n_ent=8, **cmb):
    """Minimal example dict for collate; combat fields default empty."""
    base = {"cmb_rows": [], "cmb_count": [], "atk_label": [],
            "cmb_count_label": [], "atk_tgt_kind": [], "atk_tgt_idx": [],
            "blk_label": [], "blk_atk_rows": []}
    base.update(cmb)
    x = {
        "entities": torch.zeros(n_ent, 17), "ent_emb": torch.full((n_ent,), -1),
        "globals": torch.zeros(8), "players": torch.zeros(2, 6),
        "history": torch.full((8, 3), -1),
        "cand_rows": torch.tensor([-1]), "cand_sa": torch.tensor([-1]),
        "cand_kind": torch.tensor([-1]),
        "label": torch.tensor(0), "label_row": torch.tensor(-1),
        "tgt_kind": torch.full((5,), -1), "tgt_idx": torch.full((5,), -1),
        "x_val": torch.tensor(-1), "task": torch.tensor(6),
        "bool_label": torch.tensor(-1), "num_label": torch.tensor(-1),
        "num_lo": torch.tensor(0), "num_hi": torch.tensor(17),
        "ctx_row": torch.tensor(-1), "forced": torch.tensor(0),
        "has_outcome": torch.tensor(1), "won": torch.tensor(0),
    }
    for k, v in base.items():
        x[k] = torch.tensor(v, dtype=torch.int64)
    return x


def test_collate_combat_padding_and_none_remap():
    a = _example(cmb_rows=[0, 1], cmb_count=[2, 1], atk_label=[1, 0],
                 cmb_count_label=[0, -1], atk_tgt_kind=[1, -1],
                 atk_tgt_idx=[1, -1])
    blk = _example(cmb_rows=[2], cmb_count=[1], blk_label=[1],  # none = len(atk_rows) = 1
                   cmb_count_label=[-1], blk_atk_rows=[5])
    plain = _example()
    out = collate([a, blk, plain])
    n = out["entities"].shape[1]
    assert out["cmb_mask"].tolist() == [[True, True], [True, False], [False, False]]
    assert out["atk_label"][0].tolist() == [1, 0]
    assert out["atk_tgt_labels"][0].tolist() == [n + 1, -1]  # player 1 class id
    assert out["atk_label"][1].tolist() == [-1, -1]          # block window: padded
    # blk none class (per-example 1) remapped to batch none slot M=1 here
    M = out["blk_atk_rows"].shape[1]
    assert out["blk_label"][1, 0].item() == M
    assert out["blk_atk_mask"].tolist() == [[False], [True], [False]]
    assert out["cmb_count"][0].tolist() == [2, 1]
    assert COMBAT_COUNT_MAX == 12
