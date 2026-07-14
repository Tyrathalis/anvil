"""D5 groundwork: measure combat-label recoverability on the corpus.

The declare-combat callbacks never serialized their answers (ret: null),
but the obs side carries the declared state: post-declaration windows show
`atk` refs ({"pi": n} player / {"e": id} permanent) on attackers and
`blk: [attackerIds]` on blockers. The D5 label algorithm is therefore a
JOIN: the training window is the declare dec itself (pre-declaration obs =
the decision input); the label is the combat map read from the first
subsequent same-turn window whose obs shows declared flags.

This script measures, over the corpus, exactly what the loader will run:

- join coverage: declare decs that find a label window (attacks may be
  empty — "no attack" is the most common label and joins to the next
  window regardless of flags via the phase change);
- candidate superset check (ADR-0005 semantics): label attackers must sit
  inside the derived eligibility basis (battlefield creature rows of the
  decider, untapped, non-sick); blockers inside (decider's creatures,
  untapped — sickness does NOT bar blocking); violations counted by reason;
- dedup-group partials: how often 0 < attacking < group-count within an
  identical-entity group (the count head's workload);
- target kinds (player vs permanent), block fan-out (multi-block rate),
  label-size distributions.

  uv run python scripts/d5/measure_combat_labels.py \\
      --store data/trajectories/d3pilot-20260704-175219 --max-games 2000
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from anvil.encoder.transform import _dedup_key  # dedup basis must match training
from anvil.store.trajectories import open_store


def creature_rows(obs: dict, p: int, need_untapped: bool, need_unsick: bool) -> dict[int, dict]:
    out = {}
    for e in obs.get("ents", []):
        if e.get("z") != "battlefield" or e.get("c") != p or "pt" not in e:
            continue
        if need_untapped and e.get("tap"):
            continue
        if need_unsick and e.get("sick"):
            continue
        out[e["e"]] = e
    return out


def label_window(decs: list[dict], i: int, turn: int, flag: str) -> dict | None:
    """First later dec, same COMBAT, whose obs carries any `flag` entity.
    Bounded at the next declareAttackers dec as well as the turn boundary:
    extra-combat turns re-enter declare, and a turn-only bound lets a dec
    whose own combat had no flags join a later combat's window (the 145
    block violations classified 2026-07-13 — all were this overshoot).
    Returns None when the combat ends with no flagged window (empty label)."""
    for d in decs[i + 1:]:
        if d["m"] == "declareAttackers":
            return None
        obs = d.get("obs")
        if obs is None:
            continue
        if obs["glob"].get("turn") != turn:
            return None
        if any(flag in e for e in obs.get("ents", [])):
            return obs
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="data/trajectories/d3pilot-20260704-175219")
    ap.add_argument("--max-games", type=int, default=2000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    store = open_store(a.store)
    st = Counter()
    atk_sizes = Counter()
    blk_fanout = Counter()
    group_partials = Counter()  # (attacked, group_size) events where 0<attacked<size
    games = 0

    for g in store.game_indices()[:a.max_games]:
        try:
            traj = store.game(g)
        except Exception:
            st["undecodable_game"] += 1
            continue
        games += 1
        decs = traj.decisions
        for i, d in enumerate(decs):
            obs = d.get("obs")
            if obs is None or d["m"] not in ("declareAttackers", "declareBlockers"):
                continue
            p = d.get("p", -1)
            turn = obs["glob"].get("turn")

            if d["m"] == "declareAttackers":
                st["atk_windows"] += 1
                cands = creature_rows(obs, p, need_untapped=True, need_unsick=True)
                lw = label_window(decs, i, turn, "atk")
                if lw is None:
                    st["atk_label_empty"] += 1
                    atk_sizes[0] += 1
                    continue
                attackers = {e["e"]: e["atk"] for e in lw["ents"]
                             if "atk" in e and e.get("c") == p}
                if not attackers:
                    st["atk_label_empty_flagged_window"] += 1
                    atk_sizes[0] += 1
                    continue
                st["atk_label_nonempty"] += 1
                atk_sizes[min(len(attackers), 12)] += 1
                for eid, ref in attackers.items():
                    st["atk_target_player" if "pi" in ref else "atk_target_permanent"] += 1
                    if eid not in cands:
                        # why? tapped/sick/missing in pre-obs
                        pre = next((e for e in obs["ents"] if e["e"] == eid), None)
                        if pre is None:
                            st["atk_violation_not_in_preobs"] += 1
                        elif pre.get("tap"):
                            st["atk_violation_tapped"] += 1
                        elif pre.get("sick"):
                            st["atk_violation_sick"] += 1
                        elif "pt" not in pre:
                            st["atk_violation_not_creature"] += 1
                        else:
                            st["atk_violation_other"] += 1
                # dedup-group partial counts (the count head's workload)
                groups: dict[str, list[int]] = {}
                for eid, e in cands.items():
                    groups.setdefault(_dedup_key(e, e.get("n")), []).append(eid)
                for key, ids in groups.items():
                    k = sum(1 for eid in ids if eid in attackers)
                    if 0 < k < len(ids):
                        group_partials[(k, len(ids))] += 1
                        st["atk_group_partial_events"] += 1
                    if len(ids) > 1:
                        st["atk_multi_groups_seen"] += 1

            else:  # declareBlockers
                st["blk_windows"] += 1
                cands = creature_rows(obs, p, need_untapped=True, need_unsick=False)
                attacker_ids = {e["e"] for e in obs.get("ents", []) if "atk" in e}
                if not attacker_ids:
                    st["blk_no_attackers_in_obs"] += 1
                    continue
                lw = label_window(decs, i, turn, "blk")
                if lw is None:
                    st["blk_label_empty"] += 1
                    continue
                blockers = {e["e"]: e["blk"] for e in lw["ents"]
                            if "blk" in e and e.get("c") == p}
                if not blockers:
                    st["blk_label_empty_flagged_window"] += 1
                    continue
                st["blk_label_nonempty"] += 1
                for eid, blocked in blockers.items():
                    blk_fanout[min(len(blocked), 4)] += 1
                    if eid not in cands:
                        pre = next((e for e in obs["ents"] if e["e"] == eid), None)
                        if pre is None:
                            st["blk_violation_not_in_preobs"] += 1
                        elif pre.get("tap"):
                            st["blk_violation_tapped"] += 1
                        else:
                            st["blk_violation_other"] += 1
                    for aid in blocked:
                        if aid not in attacker_ids:
                            st["blk_violation_target_not_attacker"] += 1

    report = {
        "store": a.store, "games": games,
        "stats": dict(st),
        "atk_label_sizes": {str(k): v for k, v in sorted(atk_sizes.items())},
        "blk_fanout": {str(k): v for k, v in sorted(blk_fanout.items())},
        "group_partials": {f"{k}of{n}": v for (k, n), v in sorted(group_partials.items())},
    }
    out = a.out or "data/training/d5-combat-label-measure.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=1)

    aw, bw = st["atk_windows"], st["blk_windows"]
    viol_a = sum(v for k, v in st.items() if k.startswith("atk_violation"))
    viol_b = sum(v for k, v in st.items() if k.startswith("blk_violation"))
    print(f"{games} games | attack windows {aw} ({aw/max(games,1):.1f}/game), "
          f"block windows {bw} ({bw/max(games,1):.1f}/game)")
    print(f"attacks: nonempty {st['atk_label_nonempty']} "
          f"({st['atk_label_nonempty']/max(aw,1):.1%}), "
          f"violations {viol_a} ({viol_a/max(st['atk_target_player']+st['atk_target_permanent'],1):.2%} of attackers), "
          f"targets player/permanent {st['atk_target_player']}/{st['atk_target_permanent']}")
    print(f"blocks: nonempty {st['blk_label_nonempty']} "
          f"({st['blk_label_nonempty']/max(bw,1):.1%}), violations {viol_b}")
    print(f"dedup partial-count events: {st['atk_group_partial_events']} "
          f"(multi-groups seen {st['atk_multi_groups_seen']})")
    print(f"label sizes: {dict(sorted(atk_sizes.items()))}")
    print(f"block fanout: {dict(sorted(blk_fanout.items()))}")
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
