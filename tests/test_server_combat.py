"""D5: server combat answer translation (per-row picks -> entity-ref
AttackMap/BlockMap), unit-tested with a stub backend and synthetic act()
output — no checkpoint or GPU needed."""

from collections import Counter
from types import SimpleNamespace

import torch

from anvil.bridge.server import ModelBackend


def _stub():
    return SimpleNamespace(counts=Counter())


def test_attackmap_expansion_and_targets():
    # rows: row 3 = pair (ids 7,9) attacking the opponent player; row 5 =
    # single (id 11) attacking a planeswalker (entity row 8, min id 20);
    # row 6 declines
    out = {
        "n_ent": torch.tensor(10),
        "atk_yes": torch.tensor([[True, True, False]]),
        "cmb_count": torch.tensor([[2, 1, 3]]),
        "atk_tgt": torch.tensor([[11, 8, 0]]),   # 10+1 = player position 1
    }
    aux = {
        "cmb_rows": [3, 5, 6],
        "cmb_members": {3: [7, 9], 5: [11], 6: [4]},
        "row_min_id": {8: 20},
        "seats": [1, 0],  # perspective p=1: position 1 = registered player 0
        "blk_atk_rows": [],
    }
    am = ModelBackend._attackmap(_stub(), out, aux)
    got = [(a.attacker.entity,
            a.defender.player if a.defender.WhichOneof("ref") == "player"
            else a.defender.entity) for a in am.assignments]
    # pair expands to k=2 first-fit members at the mapped registered player
    assert got == [(7, 0), (9, 0), (11, 20)]


def test_blockmap_none_and_group_expansion():
    # blocker row 2 = pair (ids 5,6), count head says 1 blocks slot 0
    # (attacker row 9, min id 30); row 4 picks the none slot (M=2)
    out = {
        "n_ent": torch.tensor(10),
        "blk_pick": torch.tensor([[0, 2]]),
        "cmb_count": torch.tensor([[1, 1]]),
    }
    aux = {
        "cmb_rows": [2, 4],
        "cmb_members": {2: [5, 6], 4: [8]},
        "row_min_id": {9: 30, 11: 40},
        "seats": [0, 1],
        "blk_atk_rows": [9, 11],
    }
    bm = ModelBackend._blockmap(_stub(), out, aux)
    got = [(a.blocker.entity, a.attacker.entity) for a in bm.assignments]
    assert got == [(5, 30)]
