"""M9 D4: the payment drill accuracy scorer (scripts/payment_drill_score.py) —
observe-job planning (renumber + provenance + deck join), lane stripping, and
the per-(shape × kind) accuracy table with its loud exclusion classes."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import payment_drill_score as ps  # noqa: E402


def _evalset(tmp_path):
    ev = tmp_path / "evalset"
    ev.mkdir()
    pos = [
        {"batch": "b1", "job": 3, "kind": "positive", "shape": "blocker_pressure",
         "best": 2, "source": "/r/pair-000.jsonl", "g": 0, "seed": 1000,
         "p": "Census(1)-dc-1", "t": 9, "sa": "Spell A", "tags": ["blocker_pressure"],
         "margin": 5.0, "k": 8},
        {"batch": "b4", "job": 0, "kind": "positive", "shape": "phyrexian",
         "best": 1, "source": "/r/pair-001.jsonl", "g": 1, "seed": 2000,
         "p": "Census(2)-hb-phy", "t": 12, "sa": "Gut Shot", "tags": ["phyrexian"],
         "margin": 3.0, "k": 8},
    ]
    ac = [
        {"batch": "b1", "job": 7, "kind": "auto_correct", "shape": "color_hold",
         "best": 0, "worst": 1, "source": "/r/pair-002.jsonl", "g": 2, "seed": 3000,
         "p": "Census(1)-dc-1", "t": 15, "sa": "Spell C", "tags": ["color_hold"],
         "margin": -4.0, "k": 8},
    ]
    (ev / "positive-drills.jsonl").write_text("".join(json.dumps(r) + "\n" for r in pos))
    (ev / "autocorrect-drills.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ac))
    b1 = tmp_path / "b1-jobs.jsonl"
    b1.write_text("".join(json.dumps(j) + "\n" for j in [
        {"job": 3, "seed": 1000, "deck1": "d1.dck", "deck2": "d2.dck", "p": "Census(1)-dc-1",
         "t": 9, "sa": "Spell A", "ord": 0, "arms": 4, "k": 8, "horizon": 2},
        {"job": 7, "seed": 3000, "deck1": "d1.dck", "deck2": "d2.dck", "p": "Census(1)-dc-1",
         "t": 15, "sa": "Spell C", "ord": 0, "arms": 2, "k": 8, "horizon": 2},
    ]))
    b4 = tmp_path / "b4-jobs.jsonl"
    b4.write_text(json.dumps(
        {"job": 0, "seed": 2000, "deck1": "hb-phy.dck", "deck2": "hb-phy.dck",
         "p": "Census(2)-hb-phy", "t": 12, "sa": "Gut Shot", "ord": 0, "arms": 2,
         "k": 8, "horizon": 2}) + "\n")
    return ev, b1, b4


def test_plan_renumbers_and_joins_decks(tmp_path):
    """Observe jobs renumber sequentially (obs game idx = job id; batch-local
    ids collide) and carry deck pair + provenance + certify-time option count."""
    ev, b1, b4 = _evalset(tmp_path)
    out = tmp_path / "observe-jobs.jsonl"
    ps.plan(SimpleNamespace(evalset=str(ev), jobs=[f"b1={b1}", f"b4={b4}"], out=str(out)))
    jobs = [json.loads(x) for x in open(out)]

    assert [j["job"] for j in jobs] == [0, 1, 2]  # renumbered, collision-free
    assert all(j["mode"] == "observe" and j["arms"] == 0 and j["k"] == 1 for j in jobs)
    phy = next(j for j in jobs if j["shape"] == "phyrexian")
    assert (phy["deck1"], phy["seed"], phy["batch"], phy["orig_job"]) == \
        ("hb-phy.dck", 2000, "b4", 0)
    assert phy["exp_options"] == 2  # certify-plan arms = |options| then
    ac = next(j for j in jobs if j["kind"] == "auto_correct")
    assert ac["best"] == 0 and ac["exp_options"] == 2


def test_lanes_strip_provenance_keep_mode(tmp_path):
    ev, b1, b4 = _evalset(tmp_path)
    jobs_f = tmp_path / "observe-jobs.jsonl"
    ps.plan(SimpleNamespace(evalset=str(ev), jobs=[f"b1={b1}", f"b4={b4}"], out=str(jobs_f)))
    ps.lanes(SimpleNamespace(jobs=str(jobs_f), jar="/x/y/target/forge.jar", n=2))
    lane0 = [json.loads(x) for x in open(tmp_path / "observe-lane-0.jobs.jsonl")]
    assert lane0 and set(lane0[0]) == set(ps.OBSERVE_JOB_FIELDS)
    assert lane0[0]["mode"] == "observe"
    sh = (tmp_path / "observe-lane-0.sh").read_text()
    assert "-obsout" in sh and "observe-lane-0.obs.zst" in sh


def test_accuracy_table_counts_exclusions_separately():
    rows = [
        {"shape": "phyrexian", "kind": "positive", "status": "scored", "correct": True},
        {"shape": "phyrexian", "kind": "positive", "status": "scored", "correct": False},
        {"shape": "phyrexian", "kind": "positive", "status": "option_mismatch"},
        {"shape": "color_hold", "kind": "auto_correct", "status": "scored", "correct": True},
        {"shape": "color_hold", "kind": "auto_correct", "status": "miss"},
    ]
    tab = ps._accuracy_table(rows)
    p = tab[("phyrexian", "positive")]
    assert (p["n"], p["correct"], p["option_mismatch"]) == (2, 1, 1)
    a = tab[("color_hold", "auto_correct")]
    assert (a["n"], a["correct"], a["miss"]) == (1, 1, 1)
