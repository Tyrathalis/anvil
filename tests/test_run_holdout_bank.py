"""ADR-0124 addendum (11-02): the run-distribution holdout bank — the
stratified draw, the fork-point join, the all-holdout bank + its manifest."""

import json
from collections import Counter

import pytest
import torch

from anvil.training import value_pretrain as vp
from anvil.training.value_pretrain import (
    bank_run_holdout,
    eval_split_rows,
    fork_point_candidates,
    model_seats_of,
    stratified_draw,
)


def test_stratified_draw_is_flat_seeded_and_sorted():
    strata = ["a"] * 10 + ["b"] * 10 + ["c"] * 2
    pick = stratified_draw(strata, 12, seed=1)
    assert len(pick) == 12 and pick == sorted(pick) and len(set(pick)) == 12
    c = Counter(strata[i] for i in pick)
    assert c["c"] == 2 and c["a"] == 5 and c["b"] == 5  # the short stratum gives all it has, the slack re-dealt
    assert stratified_draw(strata, 12, seed=1) == pick
    assert stratified_draw(strata, 12, seed=2) != pick
    assert len(stratified_draw(strata, 50, seed=1)) == 22  # n above the pool = the pool
    # an odd remainder lands on strata chosen by the seed, never twice on one
    even = ["a"] * 10 + ["b"] * 10 + ["c"] * 10
    c7 = Counter(even[i] for i in stratified_draw(even, 7, seed=3))
    assert sorted(c7.values()) == [2, 2, 3]


class _Traj:
    def __init__(self, decisions, marks, header=None):
        self.decisions, self.marks, self.header = decisions, marks, header or {"g": 0}


class _Store:
    """A duck-typed TrajectoryStore: one game per key, mark at `_pos` 2, three
    obs-carrying windows after it (the first one is the fork point's window)."""

    def __init__(self, games: dict, manifest=None):
        self._g = games
        self.manifest = manifest or {}
        self.root = None

    def __len__(self):
        return len(self._g)

    def game(self, g):
        if g not in self._g:
            raise KeyError(g)
        return self._g[g]


def _game(turn=5, ph="MAIN1", p=1, ap=1):
    decs = [
        {"_pos": 0, "p": 0, "obs": {"glob": {"turn": 1, "ph": "MAIN1", "ap": 0}}},
        {"_pos": 1, "p": 0},
        {"_pos": 3, "p": p},  # no obs: not a window
        {"_pos": 4, "p": p, "obs": {"glob": {"turn": turn, "ph": ph, "ap": ap}}},
        {"_pos": 5, "p": 0, "obs": {"glob": {"turn": turn + 1, "ph": "MAIN1", "ap": 0}}},
    ]
    return _Traj(decs, [{"k": "mark", "m": "fork", "fp": 0, "_pos": 2}, {"k": "mark", "m": "shuffle", "_pos": 0}])


def test_fork_point_candidates_join_wr_and_perspective():
    ts = _Store({7: _game(turn=5, p=1), 8: _game(turn=9, p=0)})
    labels = [
        {"i": 7, "fp": 0, "t": 5, "tt": 5, "k": 8, "w": [6, 1], "draw": 1, "crash": 0},
        {"i": 8, "fp": 0, "t": 9, "tt": 9, "k": 8, "w": [0, 8], "draw": 0, "crash": 0},
        {"i": 8, "fp": 1, "t": 12, "tt": 12, "k": 8, "w": [4, 4], "draw": 0, "crash": 0},  # no mark for fp 1
        {"i": 9, "fp": 0, "t": 3, "tt": 3, "k": 8, "w": [1, 1], "draw": 0, "crash": 6},  # game not in the store
        {"i": 7, "fp": 0, "t": 5, "tt": 5, "k": 8, "w": [0, 0], "draw": 0, "crash": 8},  # all crashed
    ]
    # a mirror store: the perspective is the window's own player
    cs, tally = fork_point_candidates(ts, "runbank-mirror-20261102-000000", labels, {0, 1})
    assert tally == {"no_mark": 1, "game_missing": 1, "no_completion": 1}
    assert [(c["g"], c["seat"], c["wr"], c["n"], c["turn"], c["ph"], c["dec_i"]) for c in cs] == [
        (7, 1, 1 / 8, 8, 5, "MAIN1", 3),  # w[1] / (6 + 1 + 1): draws count as non-wins
        (8, 0, 0.0, 8, 9, "MAIN1", 3),
    ]
    # a heuristic-seat store: the model seat, whoever holds the window
    cs0, _ = fork_point_candidates(ts, "runbank-h0-20261102-000000", labels[:2], {0})
    assert [(c["seat"], c["wr"]) for c in cs0] == [(0, 6 / 8), (0, 0.0)]


def test_model_seats_of_reads_the_name_when_no_run_json(tmp_path):
    ts = _Store({}, manifest={"run_id": "nope-20261102-000000"})
    assert model_seats_of(ts, "runbank-seg4-h0-20261102-000000") == {0}
    assert model_seats_of(ts, "runbank-seg4-h1-20261102-000000") == {1}
    assert model_seats_of(ts, "c2ext-s1-20260806-184149") == {1}
    assert model_seats_of(ts, "runbank-seg4-mirror-20261102-000000") == {0, 1}


def test_bank_run_holdout_writes_an_all_holdout_bank_and_its_manifest(tmp_path, monkeypatch):
    # two labelled "stores" on disk (manifest + labels), their frames faked
    games = {}
    labels = {}
    for name, seats_turns in (("rb-mirror-20261102-000001", [(1, 5), (2, 5), (3, 9), (4, 9), (5, 13)]),
                              ("rb-h1-20261102-000002", [(1, 5), (2, 9), (3, 9), (4, 13), (5, 13), (6, 13)])):
        d = tmp_path / name
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({"run_id": name, "run": {"fork_commit": "abc", "seed_base": 1}}))
        rows = [{"i": g, "fp": 0, "t": t, "tt": t, "k": 2, "w": [g % 2, (g + 1) % 2], "draw": 0, "crash": 0}
                for g, t in seats_turns]
        (d / "labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        games[name] = {g: _game(turn=t, p=g % 2) for g, t in seats_turns}
        labels[name] = rows

    class FakeStore(_Store):
        def __init__(self, path):
            path = str(path)
            name = path.rsplit("/", 1)[-1]
            super().__init__(games[name], json.loads(open(path + "/manifest.json").read()))

    monkeypatch.setattr("anvil.store.trajectories.TrajectoryStore", FakeStore)
    monkeypatch.setattr(vp, "_git_head", lambda: "deadbeef")
    feat_calls = []

    def featurize(ts, c):
        feat_calls.append((c["store"], c["g"], c["seat"], c["dec_i"]))
        return {"globals": torch.zeros(3), "label": torch.tensor(0)}

    out = tmp_path / "bank"
    man = bank_run_holdout([tmp_path / "rb-mirror-20261102-000001", tmp_path / "rb-h1-20261102-000002"],
                           out, n=6, seed=7, label_ckpt="data/training/big-run/iter-999/train/last.pt",
                           featurize=featurize)
    assert (out / "bank-state.pt").exists() and (out / "manifest.json").exists()
    st = torch.load(out / "bank-state.pt", weights_only=False)
    meta = st["meta"]
    assert len(meta) == 6 == len(st["examples"]) == len(feat_calls)
    assert all(m["holdout"] and not m["inner"] for m in meta)
    assert [m["idx"] for m in meta] == list(range(6))
    assert eval_split_rows(meta, "holdout").tolist() == list(range(6))  # the loop's eval scores every row
    assert len(eval_split_rows(meta, "train")) == 0  # nothing to train on
    # stratified by (turn, phase): three turns in the pool -> two per turn
    assert man["strata_sampled"] == {"t5|MAIN1": 2, "t9|MAIN1": 2, "t13|MAIN1": 2}
    assert man["strata_pool"] == {"t5|MAIN1": 3, "t9|MAIN1": 4, "t13|MAIN1": 4}
    assert man["frozen"] is True and man["split"] == "holdout" and man["seed"] == 7
    assert man["n_rows"] == 6 and man["n_requested"] == 6 and man["n_candidates"] == 11
    assert man["label_ckpt"].endswith("iter-999/train/last.pt") and man["rollout_k"] == [2]
    assert man["anvil_commit"] == "deadbeef" and man["featurize_ckpt"] == vp.CKPT
    assert [s["run_id"] for s in man["stores"]] == ["rb-mirror-20261102-000001", "rb-h1-20261102-000002"]
    assert man["stores"][1]["model_seats"] == [1] and man["stores"][0]["model_seats"] == [0, 1]
    assert all(s["candidates"] == s["labels"] for s in man["stores"])
    # the h1 store's rows read from seat 1; the mirror store's from the window's player
    for m in meta:
        if m["game"].startswith("rb-h1"):
            assert m["seat"] == 1
    assert json.loads((out / "manifest.json").read_text())["n_rows"] == 6
    assert st["manifest"]["kind"].startswith("run-distribution holdout")
    # the same seed, the same draw
    man2 = bank_run_holdout([tmp_path / "rb-mirror-20261102-000001", tmp_path / "rb-h1-20261102-000002"],
                            tmp_path / "bank2", n=6, seed=7, label_ckpt="x", featurize=featurize)
    assert [m["game"] for m in torch.load(tmp_path / "bank2" / "bank-state.pt", weights_only=False)["meta"]] == \
        [m["game"] for m in meta]
    assert man2["strata_sampled"] == man["strata_sampled"]


def test_bank_run_holdout_refuses_a_store_without_labels(tmp_path, monkeypatch):
    d = tmp_path / "plain-20261102-000003"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"run_id": d.name}))
    monkeypatch.setattr("anvil.store.trajectories.TrajectoryStore", lambda p: _Store({}, {"run_id": d.name}))
    with pytest.raises(SystemExit, match="no labels.jsonl"):
        bank_run_holdout([d], tmp_path / "bank", n=5, seed=0, label_ckpt="x", featurize=lambda ts, c: {})
