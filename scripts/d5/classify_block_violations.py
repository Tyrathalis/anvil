"""D5 groundwork: classify the 145 block-label violations found corpus-wide.

measure_combat_labels.py counted 141 blk_violation_target_not_attacker +
1 blk_violation_not_in_preobs + 3 blk_violation_other over 113,591 games but
captured no examples. This script re-runs the block half of that scan and
records rich context per violation so the class can be named before the
loader lands (devlog 2026-07-13).

Leading hypothesis: multi-combat turns. The label join is bounded by `turn`
only, so a declare-blockers dec can join to a later combat's blk window
(overshoot) or read stale flags from an earlier combat. Per violation we
record: phases and mono of dec/label windows, how many declareAttackers/
declareBlockers decs sit between them, whether the offending target ever
carried an `atk` flag earlier in the same turn, and entity names.

  uv run python scripts/d5/classify_block_violations.py \\
      --store data/trajectories/d3pilot-20260704-175219,data/trajectories/d6ext-20260706-220552
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from anvil.store.trajectories import open_store


def creature_rows(obs: dict, p: int) -> dict[int, dict]:
    out = {}
    for e in obs.get("ents", []):
        if e.get("z") != "battlefield" or e.get("c") != p or "pt" not in e:
            continue
        if e.get("tap"):
            continue
        out[e["e"]] = e
    return out


def label_window(decs: list[dict], i: int, turn: int) -> tuple[dict | None, int]:
    for j, d in enumerate(decs[i + 1:], start=i + 1):
        obs = d.get("obs")
        if obs is None:
            continue
        if obs["glob"].get("turn") != turn:
            return None, -1
        if any("blk" in e for e in obs.get("ents", [])):
            return obs, j
    return None, -1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="data/trajectories/d3pilot-20260704-175219")
    ap.add_argument("--max-games", type=int, default=None)
    ap.add_argument("--out", default="data/training/d5-block-violation-classify.json")
    a = ap.parse_args()

    st = Counter()
    examples: list[dict] = []
    games = 0

    for store_path in a.store.split(","):
        store = open_store(store_path)
        indices = store.game_indices()
        if a.max_games is not None:
            indices = indices[: max(0, a.max_games - games)]
        for g in indices:
            try:
                traj = store.game(g)
            except Exception:
                st["undecodable_game"] += 1
                continue
            games += 1
            if games % 5000 == 0:
                print(f"...{games} games, {len(examples)} violation examples", flush=True)
            decs = traj.decisions

            # per-turn running history of ids seen carrying atk flags, and
            # per-turn count of declare decs, for stale-flag classification
            turn_atk_seen: set[int] = set()
            turn_declare_atk = 0
            turn_declare_blk = 0
            cur_turn = None

            for i, d in enumerate(decs):
                obs = d.get("obs")
                if obs is None:
                    continue
                t = obs["glob"].get("turn")
                if t != cur_turn:
                    cur_turn = t
                    turn_atk_seen = set()
                    turn_declare_atk = 0
                    turn_declare_blk = 0
                atk_here = {e["e"] for e in obs.get("ents", []) if "atk" in e}
                turn_atk_seen |= atk_here
                if d["m"] == "declareAttackers":
                    turn_declare_atk += 1
                if d["m"] != "declareBlockers":
                    continue
                turn_declare_blk += 1

                p = d.get("p", -1)
                cands = creature_rows(obs, p)
                attacker_ids = atk_here
                if not attacker_ids:
                    continue
                lw, lj = label_window(decs, i, t)
                if lw is None:
                    continue
                blockers = {e["e"]: e["blk"] for e in lw["ents"]
                            if "blk" in e and e.get("c") == p}
                if not blockers:
                    continue

                viols = []
                for eid, blocked in blockers.items():
                    kinds = []
                    if eid not in cands:
                        pre = next((e for e in obs["ents"] if e["e"] == eid), None)
                        if pre is None:
                            kinds.append("blocker_not_in_preobs")
                        elif pre.get("tap"):
                            kinds.append("blocker_tapped")
                        else:
                            kinds.append("blocker_other")
                    for aid in blocked:
                        if aid not in attacker_ids:
                            kinds.append(("target_not_attacker", aid))
                    if kinds:
                        viols.append((eid, blocked, kinds))
                if not viols:
                    continue

                # context shared by all violations in this window
                between = decs[i + 1: lj]
                ctx = {
                    "store": store_path,
                    "game": g,
                    "dec_idx": i,
                    "turn": t,
                    "dec_ph": obs["glob"].get("ph"),
                    "dec_mono": obs["glob"].get("mono"),
                    "lw_idx": lj,
                    "lw_ph": lw["glob"].get("ph"),
                    "lw_mono": lw["glob"].get("mono"),
                    "declare_atk_between": sum(1 for b in between if b["m"] == "declareAttackers"),
                    "declare_blk_between": sum(1 for b in between if b["m"] == "declareBlockers"),
                    "nth_declare_atk_this_turn": turn_declare_atk,
                    "nth_declare_blk_this_turn": turn_declare_blk,
                    "attackers_at_dec": sorted(attacker_ids),
                    "violations": [],
                }
                name = {e["e"]: e.get("n") for e in obs.get("ents", [])}
                lw_name = {e["e"]: e.get("n") for e in lw.get("ents", [])}
                for eid, blocked, kinds in viols:
                    for k in kinds:
                        if isinstance(k, tuple):
                            _, aid = k
                            st["target_not_attacker"] += 1
                            lw_ent = next((e for e in lw["ents"] if e["e"] == aid), None)
                            ctx["violations"].append({
                                "kind": "target_not_attacker",
                                "blocker": eid,
                                "blocker_name": name.get(eid) or lw_name.get(eid),
                                "target": aid,
                                "target_name": name.get(aid) or lw_name.get(aid),
                                "target_in_dec_obs": any(e["e"] == aid for e in obs["ents"]),
                                "target_atk_in_lw": bool(lw_ent and "atk" in lw_ent),
                                "target_atk_earlier_this_turn": aid in turn_atk_seen,
                            })
                        else:
                            st[k] += 1
                            ctx["violations"].append({
                                "kind": k,
                                "blocker": eid,
                                "blocker_name": name.get(eid) or lw_name.get(eid),
                                "blocked": blocked,
                            })
                examples.append(ctx)

    report = {
        "store": a.store,
        "games": games,
        "counts": dict(st),
        "n_example_windows": len(examples),
        "examples": examples,
    }
    with open(a.out, "w") as f:
        json.dump(report, f, indent=1)
    print(f"{games} games | {dict(st)} | {len(examples)} example windows -> {a.out}")


if __name__ == "__main__":
    main()
