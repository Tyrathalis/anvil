"""The union target mask (ADR-0122), Python side: the shared builder, the
collate re-basing, the decoder's pad helper, the consumer rule, the store
validator's agreement check, and the surface decoder's player-position
fold-in. Synthetic records throughout (no local data needed)."""

from __future__ import annotations

import numpy as np
import torch

from anvil.encoder.target_mask import (
    MASK_FLAG,
    PRUNE_FLAG,
    apply_target_mask,
    target_allow,
    union_stats,
)
from anvil.encoder.transform import player_target_position

# obs rows: entity id -> row (ids 10, 11 share a dedup row 0; 12 -> row 1; 13 -> row 2)
ROW_OF = {10: 0, 11: 0, 12: 1, 13: 2}
N_ROWS, P = 3, 2
WIDTH = N_ROWS + P + 1
STOP = WIDTH - 1


def test_masked_option_allows_its_union_and_stop_only():
    opts = [{"e": 12, "sa": "Bolt", "kind": "spell", "tg": [{"e": 10}, {"pi": 1}], "tn": 1}]
    allow, unfit = target_allow(opts, [[], [0]], ROW_OF, perspective=0, n_players=P, n_rows=N_ROWS)
    assert allow.shape == (2, WIDTH)
    assert allow[0].all()  # PASS: everything open
    exp = np.zeros(WIDTH, dtype=bool)
    exp[0] = True  # row of entity 10
    exp[N_ROWS + 1] = True  # seat 1 from seat 0 = position 1
    exp[STOP] = True
    assert (allow[1] == exp).all()
    assert not unfit.any()


def test_player_refs_follow_the_self_first_convention_from_seat_one():
    opts = [{"e": 12, "sa": "Bolt", "kind": "spell", "tg": [{"pi": 1}], "tn": 1}]
    allow, _ = target_allow(opts, [[], [0]], ROW_OF, perspective=1, n_players=P, n_rows=N_ROWS)
    pos = player_target_position(1, 1, P)
    assert pos == 0  # seat 1 is "self" from seat 1
    assert allow[1, N_ROWS + pos]
    assert not allow[1, N_ROWS + 1]


def test_unmasked_or_legacy_member_opens_the_candidate_and_absent_field_is_no_mask():
    opts = [
        {"e": 12, "sa": "A", "kind": "spell", "tg": [{"e": 10}], "tn": 1},
        {"e": 12, "sa": "A", "kind": "spell", "tg": None, "tu": "x"},  # collapsed with the first
        {"e": 13, "sa": "B", "kind": "spell"},  # legacy entry, no field
    ]
    allow, _ = target_allow(opts, [[], [0, 1], [2]], ROW_OF, 0, P, N_ROWS)
    assert allow[1].all() and allow[2].all()
    legacy = [{"e": 12, "sa": "A", "kind": "spell"}, {"e": 13, "sa": "B", "kind": "spell"}]
    assert target_allow(legacy, [[], [0], [1]], ROW_OF, 0, P, N_ROWS) is None
    assert union_stats(opts) == {"masked": 1, "unmasked": 1, "legacy": 1, "unfit": 0, "unmasked_x": 1}


def test_collapsed_options_take_the_union_and_hidden_ids_are_dropped():
    opts = [
        {"e": 12, "sa": "A", "kind": "spell", "tg": [{"e": 10}], "tn": 1},
        {"e": 12, "sa": "A", "kind": "spell", "tg": [{"e": 13}, {"e": 999}], "tn": 1},
    ]
    allow, _ = target_allow(opts, [[], [0, 1]], ROW_OF, 0, P, N_ROWS)
    assert allow[1, 0] and allow[1, 2] and not allow[1, 1]
    assert allow[1, STOP]


def test_unfit_only_when_every_member_is_unfit_and_stack_refs_join_on_the_host():
    opts = [
        {"e": 12, "sa": "Counter", "kind": "spell", "tg": [], "tn": 1, "tz": 1},
        {"e": 13, "sa": "Counter2", "kind": "spell", "tg": [{"e": 11, "stk": 1}], "tn": 1},
        {"e": 13, "sa": "Counter2", "kind": "spell", "tg": [], "tn": 1, "tz": 1},
    ]
    allow, unfit = target_allow(opts, [[], [0], [1, 2]], ROW_OF, 0, P, N_ROWS)
    assert unfit.tolist() == [False, True, False]
    assert allow[1].sum() == 1 and allow[1, STOP]  # STOP alone
    assert allow[2, 0]  # the stack entry's host row


def test_collate_rebases_player_block_and_stop_onto_the_padded_width():
    from anvil.training.dataset import collate

    def item(n_ent, with_mask):
        ex = {
            "entities": torch.zeros(n_ent, 4),
            "ent_emb": torch.zeros(n_ent, dtype=torch.int64),
            "cand_rows": torch.tensor([-1, 0]),
            "cand_sa": torch.tensor([-1, 0]),
            "cand_kind": torch.tensor([-1, 0]),
            "cand_ak": torch.tensor([-1, -1]),
            "globals": torch.zeros(3),
            "players": torch.zeros(P, 6),
            "history": torch.zeros(8, 3, dtype=torch.int64),
            "label": torch.tensor(1),
            "label_row": torch.tensor(0),
            "tgt_kind": torch.full((5,), -1),
            "tgt_idx": torch.full((5,), -1),
            "x_val": torch.tensor(-1),
            "has_outcome": torch.tensor(0),
            "won": torch.tensor(0),
            "task": torch.tensor(0),
            "bool_label": torch.tensor(-1),
            "num_label": torch.tensor(-1),
            "num_lo": torch.tensor(0),
            "num_hi": torch.tensor(1),
            "ctx_row": torch.tensor(-1),
            "forced": torch.tensor(0),
            "cmb_rows": torch.zeros(0, dtype=torch.int64),
            "cmb_count": torch.zeros(0, dtype=torch.int64),
            "cmb_count_label": torch.zeros(0, dtype=torch.int64),
            "blk_atk_rows": torch.zeros(0, dtype=torch.int64),
            "atk_label": torch.zeros(0, dtype=torch.int64),
            "atk_tgt_kind": torch.zeros(0, dtype=torch.int64),
            "atk_tgt_idx": torch.zeros(0, dtype=torch.int64),
            "blk_label": torch.zeros(0, dtype=torch.int64),
        }
        if with_mask:
            a = torch.zeros(2, n_ent + P + 1, dtype=torch.bool)
            a[0] = True
            a[1, 0] = True  # row 0
            a[1, n_ent + 1] = True  # player position 1
            a[1, n_ent + P] = True  # STOP
            ex["tgt_allow"] = a
        return ex

    batch = collate([item(2, True), item(5, False)])
    n = 5
    ta = batch["tgt_allow"]
    assert ta.shape == (2, 2, n + P + 1)
    assert ta[1].all()  # the item without a mask allows everything
    row = ta[0, 1]
    assert row[0] and not row[1]
    assert not row[2:n].any()  # padded rows closed
    assert not row[n] and row[n + 1]  # player positions re-based
    assert row[n + P]  # STOP re-based
    assert batch["tgt_labels"].shape == (2, 5)


def test_tgt_pad_closes_padding_and_the_candidates_illegal_keys():
    from anvil.policy.model import AnvilNet

    B, n, d = 2, 4, 3
    ent_out = torch.zeros(B, n, d)
    ent_mask = torch.tensor([[True, True, False, False], [True, True, True, True]])
    allow = torch.ones(B, 3, n + P + 1, dtype=torch.bool)
    allow[0, 1] = False
    allow[0, 1, 0] = True
    allow[0, 1, n + P] = True
    batch = {"ent_mask": ent_mask, "tgt_allow": allow}
    pad = AnvilNet._tgt_pad(batch, ent_out, P, torch.tensor([1, 0]))
    assert pad.shape == (B, n + P + 1)
    # item 0, candidate 1: only row 0 and STOP open (padding rows closed too)
    assert pad[0].tolist() == [False, True, True, True, True, True, False]
    # item 1, PASS: only padding closes (none here)
    assert not pad[1].any()
    # without the field: the padding mask alone
    pad2 = AnvilNet._tgt_pad({"ent_mask": ent_mask}, ent_out, P, torch.tensor([1, 0]))
    assert pad2[0].tolist() == [False, False, True, True, False, False, False]


def test_apply_target_mask_records_the_consumers_flags():
    unfit = torch.tensor([False, True, False])
    ex = {"tgt_allow": torch.ones(3, 7, dtype=torch.bool), "cand_unfit": unfit.clone()}
    aux: dict = {}
    assert apply_target_mask(ex, aux, mask=True, prune=True) == MASK_FLAG | PRUNE_FLAG
    assert aux["tm"] == MASK_FLAG | PRUNE_FLAG
    assert "cand_unfit" not in ex and "tgt_allow" in ex
    assert ex["cand_allow"].tolist() == [True, False, True]
    ex2 = {"tgt_allow": torch.ones(3, 7, dtype=torch.bool), "cand_unfit": unfit.clone()}
    assert apply_target_mask(ex2, None, mask=False, prune=False) == 0
    assert "tgt_allow" not in ex2 and "cand_allow" not in ex2
    # an existing narrowing composes with the prune
    ex3 = {"cand_unfit": unfit.clone(), "cand_allow": torch.tensor([True, True, False])}
    assert apply_target_mask(ex3, None, mask=True, prune=True) == PRUNE_FLAG
    assert ex3["cand_allow"].tolist() == [True, False, False]


def _validate(opts, ret, oi=None):
    from anvil.store import OBS_SCHEMA_VERSION
    from anvil.store.castplan import ValidationReport, validate_game
    from anvil.store.trajectories import GameTrajectory

    obs = {
        "glob": {"turn": 3, "ph": "MAIN1", "ap": 0},
        "players": [{"life": 40}, {"life": 38}],
        "ents": [{"e": e, "n": f"C{e}", "z": "battlefield", "c": 0} for e in (10, 12, 13, 81)],
    }
    dec = {"k": "dec", "s": 1, "t": 3, "ph": "MAIN1", "p": 0, "m": "chooseSpellAbilityToPlay",
           "d": 10, "obs": obs, "opts": opts, "ret": ret}
    if oi is not None:
        dec["oi"] = oi
    play = {"k": "dec", "s": 2, "t": 3, "ph": "MAIN1", "p": 0, "m": "playChosenSpellAbility",
            "d": 10, "args": {"sa": ret[0]["sa"]}}
    header = {"k": "game", "sv": OBS_SCHEMA_VERSION, "g": 0, "seed": 1, "fmt": "Commander",
              "players": [{"name": "P0", "deck": "D0"}, {"name": "P1", "deck": "D1"}]}
    traj = GameTrajectory(header, [dec, play], {"k": "end", "status": "won", "winner": 0}, {})
    rep = ValidationReport()
    validate_game(traj, rep)
    return rep


def test_validator_agreement_check_passes_inside_and_fails_outside():
    bolt = {"e": 81, "sa": "Lightning Bolt - deals 3", "kind": "spell",
            "tg": [{"e": 10}, {"pi": 1}], "tn": 1}
    rep = _validate([bolt], [{"e": 81, "sa": bolt["sa"], "kind": "spell", "tgt": [{"pi": 1}]}], oi=0)
    assert rep.ok and rep.mask_targets_checked == 1 and rep.mask_targets_outside == 0
    assert rep.mask_opts_masked == 1
    rep = _validate([bolt], [{"e": 81, "sa": bolt["sa"], "kind": "spell", "tgt": [{"e": 12}]}], oi=0)
    assert not rep.ok and rep.mask_targets_outside == 1
    assert rep.mask_outside_by_sa == {bolt["sa"]: 1}
    assert "outside the mask" in rep.errors[0]
    assert "OUTSIDE" in rep.summary()


def test_validator_counts_unmasked_and_legacy_without_checking_and_flags_unfit_casts():
    unmasked = {"e": 81, "sa": "Edict X", "kind": "spell", "tg": None, "tu": "x"}
    rep = _validate([unmasked], [{"e": 81, "sa": "Edict X", "kind": "spell", "tgt": [{"e": 12}]}])
    assert rep.ok and rep.mask_opts_unmasked == 1 and rep.mask_unmasked_reasons == {"x": 1}
    legacy = {"e": 81, "sa": "Edict X", "kind": "spell"}
    rep = _validate([legacy], [{"e": 81, "sa": "Edict X", "kind": "spell", "tgt": [{"e": 12}]}])
    assert rep.ok and rep.mask_opts_legacy == 1 and rep.mask_targets_checked == 0
    unfit = {"e": 81, "sa": "Counter", "kind": "spell", "tg": [], "tn": 1, "tz": 1}
    rep = _validate([unfit], [{"e": 81, "sa": "Counter", "kind": "spell"}], oi=0)
    assert not rep.ok and rep.mask_unfit_chosen == 1


def test_surface_player_options_key_the_self_first_position():
    from anvil.policy.surfaces import surface_fields

    dec = {"m": "chooseSingleEntityForEffect", "p": 1, "args": {"surf": "entity_one"},
           "opts": [{"pi": 0}, {"pi": 1}, {"e": 12}]}
    legacy = surface_fields(dec, ROW_OF, None, 0, False)
    assert legacy["opt_pi"].tolist() == [0, 1, -1]
    fixed = surface_fields(dec, ROW_OF, None, 0, False, perspective=1, n_players=2)
    # from seat 1: seat 1 is position 0 (self), seat 0 is position 1
    assert fixed["opt_pi"].tolist() == [1, 0, -1]
    from_seat0 = surface_fields(dec, ROW_OF, None, 0, False, perspective=0, n_players=2)
    assert from_seat0["opt_pi"].tolist() == [0, 1, -1]
