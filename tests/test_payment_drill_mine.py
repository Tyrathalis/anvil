"""M9 rung 3: the payment-drill candidate miner (scripts/payment_drill_mine.py) —
adopted as a standing script at the rung-3 design session (2026-08-20), so it
meets the test bar: shape tags fire on their joins and nowhere else, scores
rank forced above everything, provenance fields survive."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from payment_drill_mine import WEIGHTS, mine_file  # noqa: E402


def _write(tmp_path, lines):
    p = tmp_path / "census.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    return str(p)


def test_shape_tags_fire_on_their_joins(tmp_path):
    lines = [
        {"ev": "start", "g": 0, "seed": 42},
        # forced window (also wide via goals>=4? no — goals 1): forced_chain only
        {"g": 0, "t": 5, "ph": "MAIN1", "p": "P1", "m": "payManaCost", "effect": False,
         "sa": "Thief", "goals": 1, "plans": 1, "conseq": True, "forced": True, "atoms": 3},
        # consequential window followed by P1 declaring blockers at t+2: blocker_pressure
        {"g": 0, "t": 10, "ph": "MAIN1", "p": "P1", "m": "payManaCost", "effect": False,
         "sa": "Bear", "goals": 2, "plans": 3, "conseq": True, "forced": False, "atoms": 4},
        {"g": 0, "t": 12, "p": "P1", "m": "declareBlockers"},
        # two scoped windows same (player, turn): color_hold on both
        {"g": 0, "t": 20, "ph": "MAIN1", "p": "P2", "m": "payManaCost", "effect": False,
         "sa": "SpellA", "goals": 2, "plans": 2, "conseq": True, "forced": False, "atoms": 4},
        {"g": 0, "t": 20, "ph": "MAIN1", "p": "P2", "m": "payManaCost", "effect": False,
         "sa": "SpellB", "goals": 5, "plans": 9, "conseq": True, "forced": False, "atoms": 6},
        # non-consequential window: never a candidate, but still joins color_hold counting
        {"g": 0, "t": 30, "ph": "MAIN1", "p": "P1", "m": "payManaCost", "effect": False,
         "sa": "Solo", "goals": 1, "plans": 1, "conseq": False, "forced": False, "atoms": 2},
    ]
    cands = mine_file(_write(tmp_path, lines))
    by_sa = {c["sa"]: c for c in cands}

    assert set(by_sa) == {"Thief", "Bear", "SpellA", "SpellB"}
    assert by_sa["Thief"]["tags"] == ["forced_chain"]
    assert by_sa["Bear"]["tags"] == ["blocker_pressure"]
    assert by_sa["SpellA"]["tags"] == ["color_hold"]
    assert set(by_sa["SpellB"]["tags"]) == {"color_hold", "wide_choice"}  # goals>=4
    # forced outranks every join-based tag combination
    assert by_sa["Thief"]["score"] > by_sa["SpellB"]["score"]
    assert by_sa["SpellB"]["score"] == WEIGHTS["color_hold"] + WEIGHTS["wide_choice"]


def test_blocker_join_is_bounded_to_two_turns(tmp_path):
    lines = [
        {"ev": "start", "g": 0, "seed": 7},
        {"g": 0, "t": 10, "ph": "MAIN1", "p": "P1", "m": "payManaCost", "effect": False,
         "sa": "Bear", "goals": 2, "plans": 2, "conseq": True, "forced": False, "atoms": 4},
        {"g": 0, "t": 13, "p": "P1", "m": "declareBlockers"},   # t+3: outside the window
        {"g": 0, "t": 9, "p": "P1", "m": "declareBlockers"},    # before: outside
        {"g": 0, "t": 12, "p": "P2", "m": "declareBlockers"},   # other player: no join
    ]
    cands = mine_file(_write(tmp_path, lines))
    assert cands == []  # consequential but no tag ⇒ not a candidate


def test_phyrexian_tag_fires_on_sa_join_with_choice(tmp_path):
    """phyrexian tags by card-name join (census rows carry no per-option
    labels) and only when ≥2 options exist (the min_life choice surfaced)."""
    lines = [
        {"ev": "start", "g": 0, "seed": 1},
        {"g": 0, "t": 5, "ph": "MAIN1", "p": "P1", "m": "payManaCost", "effect": False,
         "sa": "Dismember", "goals": 3, "plans": 4, "conseq": True, "forced": False, "atoms": 3},
        # phyrexian card but a single option: no choice, no tag
        {"g": 0, "t": 8, "ph": "MAIN1", "p": "P1", "m": "payManaCost", "effect": False,
         "sa": "Gut Shot", "goals": 1, "plans": 1, "conseq": True, "forced": False, "atoms": 1},
        # non-phyrexian card with choices: no tag
        {"g": 0, "t": 9, "ph": "MAIN1", "p": "P1", "m": "payManaCost", "effect": False,
         "sa": "Bear", "goals": 3, "plans": 3, "conseq": True, "forced": False, "atoms": 3},
    ]
    cands = mine_file(_write(tmp_path, lines), phy_sa=("Dismember", "Gut Shot"))
    by_sa = {c["sa"]: c for c in cands}
    assert "phyrexian" in by_sa["Dismember"]["tags"]
    assert "Gut Shot" not in by_sa and "Bear" not in by_sa  # no tags at all
    # without the list, no phyrexian tag ever
    assert not any("phyrexian" in c["tags"] for c in mine_file(_write(tmp_path, lines)))


def test_provenance_fields_survive(tmp_path):
    lines = [
        {"ev": "start", "g": 3, "seed": 20260820},
        {"g": 3, "t": 4, "ph": "MAIN2", "p": "P1", "m": "payManaCost", "effect": False,
         "sa": "Thief", "goals": 1, "plans": 1, "conseq": True, "forced": True,
         "atoms": 3, "srcclasses": 2},
    ]
    path = _write(tmp_path, lines)
    (c,) = mine_file(path)
    assert (c["source"], c["g"], c["seed"]) == (path, 3, 20260820)
    assert (c["t"], c["ph"], c["srcclasses"]) == (4, "MAIN2", 2)
