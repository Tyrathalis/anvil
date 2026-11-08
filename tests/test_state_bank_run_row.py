"""ADR-0124 addendum (11-02): the loop's second state-ranking row on the
run-distribution holdout (`--state-bank-run`) and its collapse floor."""

import argparse
from pathlib import Path

from anvil.training import selfplay
from anvil.training.selfplay import _ranking_meter, guard_flags


def _args(**kw):
    base = dict(state_bank="data/runs/m12-build1", state_bank_fmt="Commander", value_anchor=None,
                state_bank_run=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _fake_ranking(calls):
    rows = {
        "data/runs/m12-build1": {"spearman": 0.41, "se_boot": 0.028, "n": 1197, "wall_s": 25.0},
        "data/runs/run-holdout-seg4": {"spearman": 0.33, "se_boot": 0.02, "n": 2000, "wall_s": 40.0},
        "data/runs/empty-bank": None,
    }

    def fake(ckpt, bank, fmt, out_json, splits="holdout"):
        calls.append((str(bank), Path(out_json).name, splits))
        return dict(rows[str(bank)]) if rows.get(str(bank)) else None

    return fake


def test_run_bank_row_rides_beside_the_build1_row(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(selfplay, "_state_ranking", _fake_ranking(calls))
    row = _ranking_meter(_args(state_bank_run="data/runs/run-holdout-seg4"), "ckpt.pt",
                         tmp_path / "state-ranking.json")
    assert row["spearman"] == 0.41 and row["se_boot"] == 0.028 and row["n"] == 1197
    assert row["spearman_run"] == 0.33 and row["se_boot_run"] == 0.02 and row["n_run"] == 2000
    assert "gap" not in row and "train_spearman" not in row  # no anchor: no meter
    assert calls == [
        ("data/runs/m12-build1", "state-ranking.json", "holdout"),
        ("data/runs/run-holdout-seg4", "state-ranking-run.json", "holdout,contested"),  # its own file
    ]


def test_run_bank_row_is_absent_when_the_flag_is_off_or_the_bank_fails(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(selfplay, "_state_ranking", _fake_ranking(calls))
    row = _ranking_meter(_args(), "ckpt.pt", tmp_path / "state-ranking.json")
    assert row["spearman"] == 0.41 and "spearman_run" not in row and len(calls) == 1
    row = _ranking_meter(_args(state_bank_run="data/runs/empty-bank"), "ckpt.pt", tmp_path / "state-ranking.json")
    assert row["spearman"] == 0.41 and "spearman_run" not in row  # a failed run-bank eval never loses the row


def test_run_bank_row_keeps_the_anchor_meter(monkeypatch, tmp_path):
    calls = []
    fake = _fake_ranking(calls)

    def with_meter(ckpt, bank, fmt, out_json, splits="holdout"):
        r = fake(ckpt, bank, fmt, out_json, splits)
        if r and "train" in splits:
            r.update(train_spearman=0.45, gap=0.04)
        return r

    monkeypatch.setattr(selfplay, "_state_ranking", with_meter)
    row = _ranking_meter(_args(value_anchor="data/runs/m12-build1", state_bank_run="data/runs/run-holdout-seg4"),
                         "ckpt.pt", tmp_path / "state-ranking.json")
    assert row["gap"] == 0.04 and row["train_spearman"] == 0.45 and row["spearman_run"] == 0.33
    assert calls[0][2] == "holdout,train" and calls[1] == ("data/runs/run-holdout-seg4", "state-ranking-run.json",
                                                            "holdout,contested")


def test_run_floor_trips_like_the_spearman_guard():
    rl = {"mean": {"kl_mu": 0.01}}
    assert guard_flags({}, rl, None, state_spearman=0.5, spearman_floor=0.15,
                       state_spearman_run=0.25, spearman_run_floor=0.0) == []  # off by default
    assert guard_flags({}, rl, None, state_spearman_run=None, spearman_run_floor=0.3) == []  # no row
    assert guard_flags({}, rl, None, state_spearman_run=0.31, spearman_run_floor=0.3) == []
    flags = guard_flags({}, rl, None, state_spearman=0.5, spearman_floor=0.15,
                        state_spearman_run=0.29, spearman_run_floor=0.3)
    assert flags == ["guard: state_spearman_run 0.29 < floor 0.3"]
    # both floors can trip on the same iteration, each with its own line
    both = guard_flags({}, rl, None, state_spearman=0.1, spearman_floor=0.15,
                       state_spearman_run=0.29, spearman_run_floor=0.3)
    assert len(both) == 2 and both[0].startswith("guard: state_spearman 0.1") and "state_spearman_run" in both[1]


def test_run_bank_row_carries_its_contested_rows(monkeypatch, tmp_path):
    """11-07: the run row's contested rows (rollout winrate in (0.2, 0.8)) ride
    beside the pooled one; a bank eval without them leaves the row as it was."""
    calls = []
    fake = _fake_ranking(calls)

    def with_contested(ckpt, bank, fmt, out_json, splits="holdout"):
        r = fake(ckpt, bank, fmt, out_json, splits)
        if r and "contested" in splits:
            r.update(contested_spearman=0.31, contested_se_boot=0.033, contested_n=698)
        return r

    monkeypatch.setattr(selfplay, "_state_ranking", with_contested)
    row = _ranking_meter(_args(state_bank_run="data/runs/run-holdout-seg4"), "ckpt.pt",
                         tmp_path / "state-ranking.json")
    assert row["spearman_run"] == 0.33
    assert row["spearman_run_contested"] == 0.31 and row["se_boot_run_contested"] == 0.033
    assert row["n_run_contested"] == 698
    assert "contested_spearman" not in row  # only the run row's names reach the top level


def test_state_ranking_parses_the_contested_split(monkeypatch, tmp_path):
    import json
    import types

    bank = tmp_path / "bank"
    bank.mkdir()
    (bank / "bank-state.pt").write_bytes(b"")
    out_json = tmp_path / "state-ranking-run.json"

    def fake_run(cmd, **kw):
        assert cmd[cmd.index("--split") + 1] == "holdout,contested"
        out_json.write_text(
            json.dumps({"split": "holdout", "spearman": 0.76, "se_boot": 0.01, "n": 1894, "wall_s": 3.0}) + "\n"
            + json.dumps({"split": "contested", "spearman": 0.31, "se_boot": 0.03, "n": 698, "wall_s": 3.0}) + "\n")
        return types.SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(selfplay.subprocess, "run", fake_run)
    r = selfplay._state_ranking("ckpt.pt", str(bank), "Commander", out_json, splits="holdout,contested")
    assert r["spearman"] == 0.76 and r["n"] == 1894
    assert r["contested_spearman"] == 0.31 and r["contested_se_boot"] == 0.03 and r["contested_n"] == 698
