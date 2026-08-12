"""C3 pre-work read (m7-plan): re-ask chains vs independent vetoed attempts.

The §6c re-tune decision hinges on WHERE the rejected-intent penalty mass
sits: if vetoed cast attempts cluster into §6b re-ask chains (one doomed
window paying up to 8 lambda), first-attempt-only pricing removes the
pile-up without touching the per-event signal; if they are mostly isolated
single-attempt events, the lever is the lambda magnitude itself (decay
0.02 -> ~0.005 floor). ADR-0053's calibration bound frames both: the
penalty for TRYING must stay below the measured cost of NOT trying
(-1.5pp per held turn ~ 0.015 reward units per window).

Chains are inferred positionally (the store keeps no retry marker): a
vetoed attempt = mu-covered priority dec with a cast pick (c > 0) and no
realized SA (ret null); consecutive such decs by the same seat in the
same turn, adjacent in the decision stream, are one re-ask chain
(d6-vtrace-loop 6b re-asks the same window immediately, so nothing can
intervene). The dec that ends a chain classifies its outcome: a realized
cast by the same seat/turn = rescued (the re-ask walk found a payable
line); a pass (c == 0) = abandoned; anything else = other (window end,
combat handoff, game end).

No featurization needed (priority vetoes read straight off mu + ret), so
this walks full stores in seconds.

Usage:
  uv run python scripts/rejected_chain_read.py data/trajectories/d6-run13-i0* \
      [--per-store]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter


def turn_of(dec: dict) -> int | None:
    obs = dec.get("obs")
    return obs["glob"].get("turn") if obs else None


def read_store(path: str) -> dict:
    from anvil.store.trajectories import open_store

    store = open_store(path)
    out: dict = {"store": path, "games": 0, "traj": 0, "veto_events": 0,
                 "singletons": 0, "chains": Counter(), "chain_events": 0,
                 "chain_end": Counter(), "per_traj": [], "cap_hits": 0}
    for g in store.game_indices():
        mu = store.mu_for_game(g)
        if not mu:
            continue
        try:
            traj = store.game(g)
        except Exception:
            continue
        out["games"] += 1
        # per-seat veto count for the per-trajectory distribution
        seat_vetoes: Counter = Counter()
        decs = traj.decisions
        i = 0
        while i < len(decs):
            dec = decs[i]
            rec = mu.get(dec["s"])
            vetoed = (rec is not None and rec["task"] == "priority"
                      and rec["c"] > 0 and dec.get("ret") is None)
            if not vetoed:
                i += 1
                continue
            seat, turn = dec["p"], turn_of(dec)
            run = 1
            j = i + 1
            while j < len(decs):
                d2 = decs[j]
                r2 = mu.get(d2["s"])
                if (d2["p"] == seat and turn_of(d2) == turn
                        and r2 is not None and r2["task"] == "priority"
                        and r2["c"] > 0 and d2.get("ret") is None):
                    run += 1
                    j += 1
                else:
                    break
            seat_vetoes[seat] += run
            out["veto_events"] += run
            if run == 1:
                out["singletons"] += 1
            else:
                out["chains"][run] += 1
                out["chain_events"] += run
                if run >= 8:
                    out["cap_hits"] += 1
            # classify what ended the run
            end = "other"
            if j < len(decs):
                d2 = decs[j]
                r2 = mu.get(d2["s"])
                if (d2["p"] == seat and turn_of(d2) == turn
                        and r2 is not None and r2["task"] == "priority"):
                    if r2["c"] > 0 and d2.get("ret") is not None:
                        end = "rescued"
                    elif r2["c"] == 0:
                        end = "abandoned"
            key = "singleton" if run == 1 else "chain"
            out["chain_end"][f"{key}:{end}"] += 1
            i = j
        # trajectories = bridged seats with any mu coverage
        by_seat = Counter(d["p"] for d in decs if mu.get(d["s"]) is not None)
        for seat in by_seat:
            out["traj"] += 1
            out["per_traj"].append(seat_vetoes.get(seat, 0))
    return out


def merge(rows: list[dict]) -> dict:
    tot: dict = {"games": 0, "traj": 0, "veto_events": 0, "singletons": 0,
                 "chains": Counter(), "chain_events": 0,
                 "chain_end": Counter(), "per_traj": [], "cap_hits": 0}
    for r in rows:
        for k in ("games", "traj", "veto_events", "singletons",
                  "chain_events", "cap_hits"):
            tot[k] += r[k]
        tot["chains"].update(r["chains"])
        tot["chain_end"].update(r["chain_end"])
        tot["per_traj"].extend(r["per_traj"])
    return tot


def report(tag: str, t: dict) -> None:
    n_chain = sum(t["chains"].values())
    events = t["veto_events"]
    lam_units = t["singletons"] + sum(min(k, 8) * v
                                      for k, v in t["chains"].items())
    first_only_units = t["singletons"] + n_chain
    pt = sorted(t["per_traj"])
    mean_pt = sum(pt) / len(pt) if pt else 0.0
    p90 = pt[int(0.9 * len(pt))] if pt else 0
    print(f"[{tag}] {t['games']} games, {t['traj']} trajectories")
    print(f"  veto events        {events:7}  ({mean_pt:.2f}/traj mean, "
          f"p90 {p90}, max {pt[-1] if pt else 0})")
    print(f"  singletons         {t['singletons']:7}  "
          f"({t['singletons'] / max(events, 1):.1%} of events)")
    print(f"  chains (len>=2)    {n_chain:7}  carrying {t['chain_events']} "
          f"events ({t['chain_events'] / max(events, 1):.1%}); "
          f"len dist {dict(sorted(t['chains'].items()))}")
    print(f"  cap hits (len>=8)  {t['cap_hits']:7}")
    print(f"  penalty exposure   {lam_units:7} lambda-units under current "
          f"pricing; {first_only_units} under first-attempt-only "
          f"({first_only_units / max(lam_units, 1):.1%} of current)")
    print(f"  window outcomes    {dict(sorted(t['chain_end'].items()))}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stores", nargs="+")
    ap.add_argument("--per-store", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    rows = []
    for p in args.stores:
        r = read_store(p)
        rows.append(r)
        if args.per_store:
            report(p.rstrip("/").rsplit("/", 1)[-1], r)
    tot = merge(rows)
    report("ALL", tot)
    if args.json_out:
        for r in rows:
            r["chains"] = dict(r["chains"])
            r["chain_end"] = dict(r["chain_end"])
            del r["per_traj"]
        tot["chains"] = dict(tot["chains"])
        tot["chain_end"] = dict(tot["chain_end"])
        tot["per_traj_mean"] = (sum(tot["per_traj"]) / len(tot["per_traj"])
                                if tot["per_traj"] else 0.0)
        del tot["per_traj"]
        with open(args.json_out, "w") as f:
            json.dump({"stores": rows, "all": tot}, f, indent=1)
        print(f"json: {args.json_out}")


if __name__ == "__main__":
    main()
