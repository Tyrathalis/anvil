"""Inline certification finish step: arm definitions from sched_arms rows, the
arm spread, and the stage-1 adjudication on synthetic completion rows."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sched_pins as pins  # noqa: E402
from sched_certify_finish import load_arms, spread  # noqa: E402
from schedule_read import certify_turn, load_rows  # noqa: E402


def _snap(life_me, creatures_me, winner=-1):
    return {"life": [life_me, 30], "creatures": [creatures_me, 2], "power": [creatures_me * 2, 4],
            "hand": [3, 3], "lands": [5, 5]}, winner


def _row(g, t, arm, roll, snap, winner, void=False):
    r = {"ev": "sched", "i": g, "seed": 1, "fp": 0, "t": t, "arm": arm, "roll": roll,
         "rollseed": roll, "crash": False, "snap": snap, "winner": winner}
    if arm > 0:
        r.update({"joint": True, "sched_n": 1, "exec": 0 if void else 1, "void": void,
                  "deferred": 0, "degraded_at": 0 if void else -1})
    return r


def test_load_arms_and_adjudication(tmp_path):
    w = tmp_path / "workers" / "inv-0000"
    w.mkdir(parents=True)
    rows = [{"ev": "sched_arms", "i": 7, "seed": 1, "fp": 0, "t": 9, "seat": 0, "horizon": 2,
             "n_opts": 5, "arms": [[], ["Cast A"], ["Cast B", "Cast A"]]}]
    for roll in range(pins.K_ROLLS):
        s, wn = _snap(30, 2)
        rows.append(_row(7, 9, 0, roll, s, wn))                      # natural
        s, wn = _snap(30, 2)
        rows.append(_row(7, 9, 1, roll, s, wn))                      # hold-all: ties natural
        s, wn = _snap(30, 4)                                         # arm 2: +2 creatures (dev +2)
        rows.append(_row(7, 9, 2, roll, s, wn))
        s, wn = _snap(30, 5, winner=0)                               # arm 3: +3 creatures, wins
        rows.append(_row(7, 9, 3, roll, s, wn))
    rows.append(_row(7, 9, 3, 0, _snap(30, 5)[0], -1, void=True))   # a void row on arm 3
    (w / "labels.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    pat = [str(tmp_path / "workers" / "inv-*" / "labels.jsonl")]
    arms = load_arms(pat)
    assert arms[(7, 9)]["seat"] == 0 and arms[(7, 9)]["arms"] == {
        1: ("joint", []), 2: ("joint", ["Cast A"]), 3: ("joint", ["Cast B", "Cast A"])}
    turns = load_rows(pat)
    entry = turns[(7, 9)]
    assert len(entry["nat"]) == pins.K_ROLLS and set(entry["arms"]) == {1, 2, 3}
    rec = certify_turn(entry, 0)
    # arm 3 is void -> excluded; arm 2 beats natural by dev +2 and power +4 (composite 4.0 >= THETA), consistent
    assert rec["read"] and rec["arm"] == 2 and rec["certified"]
    assert rec["score_mean"] == 4.0 and rec["agree"] == 1.0
    sp = spread(entry, 0)
    assert [a["arm"] for a in sp] == [1, 2, 3]
    assert sp[0]["select_mean"] == 0.0 and sp[1]["score_mean"] == 4.0
