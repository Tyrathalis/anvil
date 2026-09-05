"""Driver-side serve regime + paired read wiring (M10 reset session two,
item 5): the flags every driver-started server receives derive from ONE
function of the args, and the paired read command carries the same regime."""

import argparse

from anvil.training.selfplay import PAIRED_CKPT_MAIN, paired_progress, paired_read_cmd, sched_flags


def _args(**kw):
    base = dict(name="probe7", sched_binding="off", sched_basis="legal", sched_empty_rev="hold",
                sched_empty_emit="hold", ability_table="data/pool/ability-table.json",
                paired_read="data/runs/sched-paired-pop", paired_ckpt_main=PAIRED_CKPT_MAIN,
                paired_lanes=6, paired_heap="3g", paired_limit=0)
    base.update(kw)
    return argparse.Namespace(**base)


def test_sched_flags_advisory_is_empty_and_binding_carries_regime():
    assert sched_flags(_args()) == []
    # binding alone: legal basis, pinned hold rule -> just the binding flag
    assert sched_flags(_args(sched_binding="all")) == ["--sched-binding", "all"]
    f = sched_flags(_args(sched_binding="all", sched_basis="hand", sched_empty_rev="release"))
    assert f == ["--sched-binding", "all", "--sched-basis", "hand",
                 "--ability-table", "data/pool/ability-table.json", "--sched-empty-rev", "release"]
    f2 = sched_flags(_args(sched_binding="all", sched_empty_emit="release"))
    assert f2[-2:] == ["--sched-empty-emit", "release"]


def test_paired_read_cmd_mirrors_regime():
    a = _args(sched_binding="all", sched_basis="hand", sched_empty_rev="release", paired_limit=4)
    cmd = paired_read_cmd(a, "data/training/x/last.pt", "dayzero", "/j/forge.jar")
    assert cmd[1].endswith("scripts/sched_paired_read.py") and cmd[2] == "run"
    kv = dict(zip(cmd[3::2], cmd[4::2]))
    assert kv["--plan"] == "data/runs/sched-paired-pop" and kv["--name"] == "probe7-dayzero"
    assert kv["--ckpt-main"] == PAIRED_CKPT_MAIN and kv["--ckpt"] == "data/training/x/last.pt"
    assert kv["--jar"] == "/j/forge.jar" and kv["--lanes"] == "6" and kv["--heap"] == "3g"
    assert kv["--basis"] == "hand" and kv["--empty-rev"] == "release" and kv["--limit"] == "4"
    assert "--empty-emit" not in kv
    # legal basis / hold rule / no limit: none of the optional flags ride
    cmd0 = paired_read_cmd(_args(sched_binding="all"), "c.pt", "final", "j")
    assert not ({"--basis", "--empty-rev", "--empty-emit", "--limit"} & set(cmd0))


def test_paired_progress_counts_lane_rows(tmp_path):
    """The paired-read heartbeat: per-side rolls + crashes from the lane
    outputs; zeros before the run dir exists (no false STALLED notices)."""
    assert paired_progress(None) == {"rolls_a": 0, "rolls_b": 0, "crashes_a": 0, "crashes_b": 0}
    for side, rows in (("A", ['{"ev":"sched","crash":false}', '{"ev":"sched","crash":true}']),
                       ("B", ['{"ev":"sched","crash":false}'] * 3)):
        d = tmp_path / f"lanes-{side}"
        d.mkdir()
        (d / "lane-0.out.jsonl").write_text("\n".join(rows) + "\n")
        (d / "lane-1.out.jsonl").write_text('{"ev":"sched","crash":false}\n')
        (d / "lane-1.sh").write_text("echo not counted\n")
    assert paired_progress(str(tmp_path)) == {"rolls_a": 3, "rolls_b": 4, "crashes_a": 1, "crashes_b": 0}
