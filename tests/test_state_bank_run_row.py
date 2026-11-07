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
        ("data/runs/run-holdout-seg4", "state-ranking-run.json", "holdout"),  # its own file, holdout only
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
                                                            "holdout")


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
