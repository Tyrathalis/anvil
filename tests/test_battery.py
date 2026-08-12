"""Battery v1 unit checks (run-analysis-protocol.md): the pure math — seed-half
consistency, model-win parsing, monitor anomaly encoding. The store-walking and
model-forward instruments are validated live (null + known-positive controls
recorded in data/runs/d3-rebaseline-analysis/baseline.json)."""

import json

import pytest

from anvil.evals import battery

pytest.importorskip("matplotlib")


def _arm(tmp_path, name, rows):
    d = tmp_path / name
    d.mkdir()
    (d / "games.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return d


def _row(i, model_wins, turns=20):
    return {
        "i": i,
        "status": "won",
        "winner": f"{'Anvil(1)' if model_wins else 'Heur(2)'}-dc-1.dck",
        "turns": turns,
        "decks": ["dc-1.dck", "dc-2.dck"],
    }


def test_model_won_parses_winner_tags():
    assert battery._model_won(_row(0, True)) is True
    assert battery._model_won(_row(0, False)) is False
    assert battery._model_won({"status": "draw_clock", "winner": None}) is None


def test_eval_read_flags_constructed_seed_half_disagreement(tmp_path):
    # even game indices: model always wins; odd: model always loses — the
    # maximal run12-class split. One arm suffices.
    rows = [_row(i, model_wins=(i % 2 == 0)) for i in range(400)]
    arm = _arm(tmp_path, "arm-s0", rows)
    an = battery.eval_read("t", [str(arm)], None, tmp_path / "out")
    assert any("seed-half disagreement" in a for a in an)
    numbers = json.loads((tmp_path / "out" / "analysis.json").read_text())
    assert numbers["seed_halves"]["even"][0] == 1.0
    assert numbers["seed_halves"]["odd"][0] == 0.0
    assert (tmp_path / "out" / "analysis.md").read_text().startswith("# t eval battery")


def test_eval_read_quiet_on_balanced_halves(tmp_path):
    # alternate wins WITHIN each parity class: halves agree at 0.5 exactly
    rows = [_row(i, model_wins=(i // 2 % 2 == 0)) for i in range(400)]
    arm = _arm(tmp_path, "arm-s0", rows)
    an = battery.eval_read("t", [str(arm)], None, tmp_path / "out")
    assert not any("seed-half" in a for a in an)


def test_monitor_anomalies_encode_the_adr0049_shapes(tmp_path):
    def mrow(k, kl, ent):
        return {
            "iteration": k,
            "gen_s": 100,
            "train_s": 50,
            "census": {"veto_rate": 0.15, "first_veto_rate": 0.1, "casts_per_game": 30},
            "games": {"turns_median": 20},
            "rl": {"mean": {"kl_mu": kl, "ent": ent, "rej": 5, "reward": 0.0, "v0": 0.0}},
        }

    run = tmp_path / "run"
    run.mkdir()
    rows = [mrow(k, 0.006 * (1 + k), 0.13) for k in range(5)]  # kl_mu 5x growth
    (run / "monitor.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    an, _ = battery.monitor_curves(run)
    assert any("kl_mu grew" in a for a in an)
    assert not any("entropy fell" in a for a in an)
    assert (run / "analysis" / "monitor.png").exists()


def test_emit_never_raises():
    def boom():
        raise RuntimeError("diagnostics must not block the run")

    assert battery.emit(boom) is None
