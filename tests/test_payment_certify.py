"""M9 rung 3: certification driver/reader (scripts/payment_certify.py) —
the lane-script provenance join, per-shape job planning, and the paired
per-shape predicates over the fork certify-row contract."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import payment_certify as pc  # noqa: E402

LANE = (
    "#!/bin/sh\nset -e\n"
    "nice -n 19 java -jar '/x/forge.jar' census -d 'dc-1.dck' 'dc-2.dck' -f Commander "
    "-paytelemetry -n 5 -s 1000 -o '/data/run/pair-000.jsonl.tmp' && mv a b\n"
    "nice -n 19 java -jar '/x/forge.jar' census -d 'dc-3.dck' 'dc-4.dck' -f Commander "
    "-paytelemetry -n 5 -s 2000 -o '/data/run/pair-001.jsonl.tmp' && mv a b\n"
)


def _mk_candidates(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    (d / "lane-0.sh").write_text(LANE)
    cands = [
        {"source": str(d / "pair-000.jsonl"), "g": 0, "seed": 1000, "t": 9,
         "ph": "MAIN1", "p": "Census(1)-dc-1", "sa": "Spell A", "goals": 3,
         "plans": 7, "conseq": True, "forced": True, "atoms": 5,
         "tags": ["forced_chain"], "score": 100},
        {"source": str(d / "pair-001.jsonl"), "g": 2, "seed": 2002, "t": 12,
         "ph": "MAIN1", "p": "Census(2)-dc-4", "sa": "Spell B", "goals": 4,
         "plans": 20, "conseq": True, "forced": False, "atoms": 8,
         "tags": ["blocker_pressure", "wide_choice"], "score": 13},
    ]
    f = d / "drill-candidates.jsonl"
    f.write_text("\n".join(json.dumps(c) for c in cands) + "\n")
    return f


def test_plan_joins_lanes_and_shapes(tmp_path, capsys):
    cf = _mk_candidates(tmp_path)
    out = tmp_path / "jobs.jsonl"
    pc.plan(SimpleNamespace(candidates=str(cf), out=str(out), per_shape=40))
    jobs = [json.loads(x) for x in open(out)]

    assert len(jobs) == 2  # the two-tag window plans ONCE (first shape wins)
    j0 = next(j for j in jobs if j["shape"] == "forced_chain")
    assert (j0["deck1"], j0["deck2"], j0["seed"]) == ("dc-1.dck", "dc-2.dck", 1000)
    assert j0["k"] == 1  # deterministic shape
    j1 = next(j for j in jobs if j["shape"] == "blocker_pressure")
    assert (j1["deck1"], j1["seed"], j1["k"]) == ("dc-3.dck", 2002, 8)
    assert j1["arms"] == 4  # bounded by the window's goal count


def _row(job, arm, roll, fired=True, exec_="auto", life=(30, 30), creatures=(2, 2),
         power=(4, 4), hand=(4, 4), lands=(5, 5), winner=-1):
    return {"ev": "certify", "job": job, "arm": arm, "roll": roll, "fired": fired,
            "exec": exec_, "t_fired": 9, "t_end": 11, "ended": False, "winner": winner,
            "snap": {"life": list(life), "creatures": list(creatures),
                     "power": list(power), "hand": list(hand), "lands": list(lands),
                     "avail_options": 3}}


def test_read_certifies_forced_and_paired_margin(tmp_path):
    cf = _mk_candidates(tmp_path)
    jobs_f = tmp_path / "jobs.jsonl"
    pc.plan(SimpleNamespace(candidates=str(cf), out=str(jobs_f), per_shape=40))
    jobs = [json.loads(x) for x in open(jobs_f)]
    jf = next(j for j in jobs if j["shape"] == "forced_chain")["job"]
    jb = next(j for j in jobs if j["shape"] == "blocker_pressure")["job"]

    rows = []
    # forced job: arm0 auto, arm1 executes the chain -> certified, best=1
    rows.append(_row(jf, 0, 0))
    rows.append(_row(jf, 1, 0, exec_="directed_ok"))
    # blocker job (payer = seat 1, "Census(2)-dc-4"): arm1 keeps 2 more life
    # + a creature vs arm0, consistently across all 8 paired rolls
    for r in range(8):
        rows.append(_row(jb, 0, r, life=(30, 24), creatures=(2, 1)))
        rows.append(_row(jb, 1, r, exec_="directed_ok", life=(30, 27), creatures=(2, 2)))
    certout = tmp_path / "cert.jsonl"
    certout.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    out = tmp_path / "certified.jsonl"
    pc.read(SimpleNamespace(jobs=str(jobs_f), certout=str(certout), out=str(out)))
    certified = {c["shape"]: c for c in map(json.loads, open(out))}

    assert certified["forced_chain"]["best"] == 1
    b = certified["blocker_pressure"]
    assert b["best"] == 1 and b["margin"] >= pc.MARGIN["blocker_pressure"]
    assert b["seed"] == 2002  # provenance survives to the drill record


def test_read_positive_not_masked_by_stronger_negative(tmp_path):
    """A cleared positive arm certifies even when another arm has a LARGER
    negative margin (best = best positive, never best |margin|)."""
    cf = _mk_candidates(tmp_path)
    jobs_f = tmp_path / "jobs.jsonl"
    pc.plan(SimpleNamespace(candidates=str(cf), out=str(jobs_f), per_shape=40))
    jb = next(j for j in map(json.loads, open(jobs_f)) if j["shape"] == "blocker_pressure")["job"]

    rows = []
    for r in range(8):
        rows.append(_row(jb, 0, r, life=(30, 24), creatures=(2, 1)))
        # arm 1: +3 margin (life +2, creature +1), consistent
        rows.append(_row(jb, 1, r, exec_="directed_ok", life=(30, 26), creatures=(2, 2)))
        # arm 2: -8 margin, consistent — bigger |margin| but negative
        rows.append(_row(jb, 2, r, exec_="directed_ok", life=(30, 16), creatures=(2, 1)))
    certout = tmp_path / "cert.jsonl"
    certout.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = tmp_path / "certified.jsonl"
    pc.read(SimpleNamespace(jobs=str(jobs_f), certout=str(certout), out=str(out)))
    b = {c["shape"]: c for c in map(json.loads, open(out))}["blocker_pressure"]
    assert b["best"] == 1 and b["margin"] > 0 and b["kind"] == "positive"


def test_read_emits_auto_correct_drills(tmp_path):
    """No positive cleared arm + a consistently-losing deviation -> the job
    lands in autocorrect-drills.jsonl (separate file, never in --out)."""
    cf = _mk_candidates(tmp_path)
    jobs_f = tmp_path / "jobs.jsonl"
    pc.plan(SimpleNamespace(candidates=str(cf), out=str(jobs_f), per_shape=40))
    jb = next(j for j in map(json.loads, open(jobs_f)) if j["shape"] == "blocker_pressure")["job"]

    rows = []
    for r in range(8):
        rows.append(_row(jb, 0, r, life=(30, 24), creatures=(2, 1)))
        rows.append(_row(jb, 1, r, exec_="directed_ok", life=(30, 18), creatures=(2, 0)))
    certout = tmp_path / "cert.jsonl"
    certout.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = tmp_path / "certified.jsonl"
    ac = tmp_path / "ac.jsonl"
    pc.read(SimpleNamespace(jobs=str(jobs_f), certout=str(certout), out=str(out),
                            autocorrect_out=str(ac)))
    assert "blocker_pressure" not in {c["shape"] for c in map(json.loads, open(out))}
    acs = [json.loads(x) for x in open(ac)]
    assert len(acs) == 1
    a = acs[0]
    assert a["kind"] == "auto_correct" and a["best"] == 0
    assert a["worst"] == 1 and a["margin"] < 0
    assert a["seed"] == 2002  # provenance survives


def test_plan_exclude_and_counts(tmp_path):
    """--exclude skips previously-planned windows; --counts overrides the
    per-shape quota by name."""
    cf = _mk_candidates(tmp_path)
    first = tmp_path / "jobs1.jsonl"
    pc.plan(SimpleNamespace(candidates=str(cf), out=str(first), per_shape=40))
    second = tmp_path / "jobs2.jsonl"
    pc.plan(SimpleNamespace(candidates=str(cf), out=str(second), per_shape=40,
                            exclude=[str(first)], counts=""))
    assert open(second).read() == ""  # every window already planned

    only_bp = tmp_path / "jobs3.jsonl"
    pc.plan(SimpleNamespace(candidates=str(cf), out=str(only_bp), per_shape=40,
                            exclude=[], counts="forced_chain=0"))
    shapes = {j["shape"] for j in map(json.loads, open(only_bp))}
    assert shapes == {"blocker_pressure"}  # forced quota zeroed


def test_read_rejects_inconsistent_rolls(tmp_path):
    """A margin that flips sign across rolls fails the consistency gate —
    no certification from noise."""
    cf = _mk_candidates(tmp_path)
    jobs_f = tmp_path / "jobs.jsonl"
    pc.plan(SimpleNamespace(candidates=str(cf), out=str(jobs_f), per_shape=40))
    jb = next(j for j in map(json.loads, open(jobs_f)) if j["shape"] == "blocker_pressure")["job"]

    rows = []
    for r in range(8):
        rows.append(_row(jb, 0, r))
        flip = 6 if r % 2 else -6  # alternating sign, mean ~0
        rows.append(_row(jb, 1, r, life=(30, 30 + flip)))
    certout = tmp_path / "cert.jsonl"
    certout.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = tmp_path / "certified.jsonl"
    pc.read(SimpleNamespace(jobs=str(jobs_f), certout=str(certout), out=str(out)))
    assert "blocker_pressure" not in {c["shape"] for c in map(json.loads, open(out))}
