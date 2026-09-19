"""M12 Build 4½ — the loop wiring's join (anvil.training.search_join): pure
unit tests on synthetic rows / decs / mu records. ADR-0113."""

import math

from anvil.training.search_join import (
    acted_override,
    alloc_fields,
    behavior_mass,
    cand_of_options,
    derive_tau,
    forced_after,
    match_rows,
)


def _dec(t, ph, seat, opts, by=None, s=0, stack=False):
    obs = {"ents": [{"e": 1}], "glob": {"ap": seat}}
    if stack:
        obs["stack"] = [{"e": 99}]
    d = {"m": "chooseSpellAbilityToPlay", "t": t, "ph": ph, "p": seat, "s": s,
         "opts": [{"e": e, "sa": sa} for e, sa in opts], "obs": obs}
    if by:
        d["by"] = by
    return d


def _row(t, ph, seat, sw, labels, n_opts=None, **kw):
    opts = [{"o": 0, "label": "pass"}] + [{"o": i + 1, "label": lab} for i, lab in enumerate(labels)]
    return {"ev": "search", "t": t, "ph": ph, "seat": seat, "sw": sw, "opts": opts,
            "n_opts": len(labels) if n_opts is None else n_opts, **kw}


def test_match_rows_skips_forced_reask_and_walks_in_order():
    decs = [
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt"), (11, "Play land Forest")], s=1),
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt")], by="search", s=2),  # the forced re-ask
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt")], s=3),  # a later window, one option
    ]
    rows = [_row(3, "MAIN1", 0, 0, ["Cast Bolt", "Play land Fores"]), _row(3, "MAIN1", 0, 1, ["Cast Bolt"])]
    matched, counts = match_rows(decs, rows)
    assert counts["row_matched"] == 2 and counts["row_unmatched"] == 0
    assert [i for i, _, _ in matched] == [0, 2]  # never the forced dec at 1
    assert matched[0][2] == {1: 0, 2: 1}


def test_forced_after_finds_the_single_option_search_dec():
    decs = [
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt"), (11, "Play land")], s=1),
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt")], by="search", s=2),
        _dec(4, "MAIN1", 0, [(10, "Cast Bolt")], s=3),
    ]
    assert forced_after(decs, 0, "Cast Bolt") == 1
    assert forced_after(decs, 0, "Play land") is None  # the label must match
    assert forced_after(decs, 2, "Cast Bolt") is None


def test_forced_after_walks_past_setup_and_reask_chain_but_not_another_window():
    decs = [
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt"), (11, "Play land"), (12, "Delve")], s=1),
        _dec(3, "MAIN1", 0, [(11, "Play land"), (12, "Delve")], s=2),  # a re-ask (veto) of the natural
        {"m": "chooseOptionalCosts", "t": 3, "ph": "MAIN1", "p": 0, "s": 3},  # the natural's setup
        _dec(3, "MAIN1", 0, [(12, "Delve")], by="search", s=4),
    ]
    assert forced_after(decs, 0, "Delve") == 3
    decs2 = [
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt")], s=1),
        _dec(3, "MAIN1", 1, [(20, "Counter")], s=2),  # the other seat: the window ended
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt")], by="search", s=3),
    ]
    assert forced_after(decs2, 0, "Cast Bolt") is None


def test_match_rows_skips_non_candidate_windows_and_option_count_mismatch():
    # a non-quiescent earlier window with the same options, then the real one
    decs = [
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt"), (11, "Play land")], s=1, stack=True),
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt"), (11, "Play land"), (12, "Tap")], s=2),  # a superset
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt"), (11, "Play land")], s=3),
    ]
    matched, counts = match_rows(decs, [_row(3, "MAIN1", 0, 0, ["Cast Bolt", "Play land"])])
    assert counts["row_matched"] == 1 and matched[0][0] == 2


def test_cand_of_options_collapses_duplicate_keys():
    dec = _dec(3, "MAIN1", 0, [(10, "Cast Bolt"), (12, "Cast Bolt"), (11, "Play land")])
    # entities 10 and 12 share a row (two identical cards) -> one candidate
    aux = {"row_of": {10: 0, 12: 0, 11: 1}, "cand_first_opt": [-1, 0, 2]}
    assert cand_of_options(dec, aux) == {0: 1, 1: 1, 2: 2}


def test_behavior_mass_sums_onto_candidates():
    row = _row(3, "MAIN1", 0, 0, ["Cast Bolt", "Cast Bolt", "Play land"], p=[0.1, 0.3, 0.2, 0.4])
    o_to_dec = {1: 0, 2: 1, 3: 2}
    opt_to_cand = {0: 1, 1: 1, 2: 2}
    mass = behavior_mass(row, o_to_dec, opt_to_cand)
    assert math.isclose(mass[0], 0.1) and math.isclose(mass[1], 0.5) and math.isclose(mass[2], 0.4)


def _mu(c, tgt=None, x=0, lp=None):
    rec = {"g": 0, "s": 1, "task": "priority", "c": c, "lp": lp or {"choice": -0.5}, "ent": {}}
    if c > 0:
        rec["tgt"] = tgt or []
        rec["x"] = x
        rec["lp"] = {"choice": -0.5, "tgt": -0.2, "x": -0.1, **(lp or {})}
    rec["logp"] = sum(rec["lp"].values())
    return rec


def test_acted_override_act_merges_forced_plan_under_search_mass():
    row = _row(3, "MAIN1", 0, 0, ["Cast Bolt", "Play land"], p=[0.02, 0.9, 0.08], act_o=1, applied="act", margin=0.15)
    o_to_dec, opt_to_cand = {1: 0, 2: 1}, {0: 1, 1: 2}
    natural = _mu(2)  # the policy's own sample: play land
    forced = _mu(1, tgt=[4], x=3, lp={"tgt": -0.7, "x": -0.3})
    rec, cls = acted_override(row, natural, o_to_dec, opt_to_cand, forced)
    assert cls == "act" and rec["acted"] and rec["c"] == 1
    assert rec["tgt"] == [4] and rec["x"] == 3
    assert math.isclose(rec["lp"]["choice"], math.log(0.9))
    assert math.isclose(rec["logp"], math.log(0.9) - 0.7 - 0.3)


def test_acted_override_act_without_forced_record_drops_the_window():
    row = _row(3, "MAIN1", 0, 0, ["Cast Bolt"], p=[0.1, 0.9], act_o=1, applied="act")
    rec, cls = acted_override(row, _mu(0), {1: 0}, {0: 1}, None)
    assert rec is None and cls == "act_no_forced"


def test_acted_override_pass_and_act_void_and_natural():
    o_to_dec, opt_to_cand = {1: 0, 2: 1}, {0: 1, 1: 2}
    row = _row(3, "MAIN1", 0, 0, ["Cast Bolt", "Play land"], p=[0.7, 0.2, 0.1], act_o=0, applied="pass")
    rec, cls = acted_override(row, _mu(2), o_to_dec, opt_to_cand, None)
    assert cls == "pass" and rec["c"] == 0 and rec["acted"] and math.isclose(rec["logp"], math.log(0.7))
    # act_void: the natural (candidate 2 = play land) played; mass = p[nat] + p[act_o]
    row = _row(3, "MAIN1", 0, 0, ["Cast Bolt", "Play land"], p=[0.1, 0.6, 0.3], act_o=1, applied="act_void")
    rec, cls = acted_override(row, _mu(2), o_to_dec, opt_to_cand, None)
    assert cls == "act_void" and rec["c"] == 2 and not rec["acted"]
    assert math.isclose(rec["lp"]["choice"], math.log(0.9))
    # natural with p: the rule fired and sampled the natural
    row = _row(3, "MAIN1", 0, 0, ["Cast Bolt", "Play land"], p=[0.1, 0.2, 0.7], applied="natural")
    rec, cls = acted_override(row, _mu(2), o_to_dec, opt_to_cand, None)
    assert cls == "natural_sampled" and math.isclose(rec["lp"]["choice"], math.log(0.7))
    # natural without p: untouched
    row = _row(3, "MAIN1", 0, 0, ["Cast Bolt", "Play land"], applied="natural")
    nat = _mu(2)
    rec, cls = acted_override(row, nat, o_to_dec, opt_to_cand, None)
    assert cls == "natural" and rec is nat


def test_alloc_fields_label_and_population_weight():
    assert alloc_fields({"margin": 0.12}, 0.10) == (1, 1.0)
    assert alloc_fields({"margin": 0.05, "alloc": {"by": "head"}}, 0.10) == (0, 1.0)
    assert alloc_fields({"margin": 0.3, "alloc": {"by": "floor"}}, 0.10, floor=0.1) == (1, 10.0)
    assert alloc_fields({}, 0.10) == (0, 1.0)


def test_derive_tau_recall_target_and_auc():
    p = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05]
    y = [1, 1, 1, 0, 1, 0, 0, 0, 0, 0]
    rec = derive_tau(p, y, 0.9)
    assert rec["n"] == 10 and rec["n_pos"] == 4
    assert rec["tau"] == 0.5 and rec["recall"] == 1.0
    assert rec["auc"] > 0.9
    assert derive_tau([0.1, 0.2], [0, 0], 0.9)["tau"] is None
    # weighted: one floor positive at p 0.3 stands for ten -> the 0.9 recall
    # target cannot drop it; tau falls to 0.3
    w = [1, 1, 1, 1, 1, 1, 10, 1, 1, 1]
    y2 = [1, 1, 1, 0, 1, 0, 1, 0, 0, 0]
    rec = derive_tau(p, y2, 0.9, w)
    assert rec["tau"] == 0.3 and rec["recall"] == 1.0
    # unweighted the same labels keep tau at 0.5 (one of five positives dropped = 0.8 < 0.9? no: 4/5)
    assert derive_tau(p, y2, 0.75)["tau"] == 0.5


def test_natural_before_walks_back_to_the_candidate_window():
    from anvil.training.search_join import natural_before

    decs = [
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt"), (11, "Play land")], s=1),
        _dec(3, "MAIN1", 0, [(11, "Play land")], s=2),  # the re-ask chain
        {"m": "chooseOptionalCosts", "t": 3, "ph": "MAIN1", "p": 0, "s": 3},
        _dec(3, "MAIN1", 0, [(10, "Cast Bolt")], by="search", s=4),
    ]
    assert natural_before(decs, 3) == 0
    decs2 = [_dec(3, "MAIN1", 1, [(20, "Counter")], s=1), _dec(3, "MAIN1", 0, [(10, "Cast Bolt")], by="search", s=2)]
    assert natural_before(decs2, 1) is None
