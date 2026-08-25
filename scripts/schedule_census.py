#!/usr/bin/env python3
"""M10 design round — the candidate-actions-per-turn terrain census
(m10-plan "Pre-instrument census", funded 2026-08-25).

Question: what does the within-turn schedule space actually look like at
the model's turn-start windows? Sizes the planning-ceiling instrument's
arm caps (fork 6), the §15-bet regime coverage (3-4 action turns), and
the enumeration budget — from existing stores, no rollouts, no engine
work.

Unit: the (game, model-seat, turn) group of `chooseSpellAbilityToPlay`
windows; every quantity is a SNAPSHOT at the group's emission window
(first window with an obs — the plan-latent emission convention,
m9-d6-plan-latent-spec §1). Strata: own_turn (obs.glob.ap == seat) vs
off_turn (blocks/instants on the opponent's turn).

Conventions (recorded, shared with the veto-knowability instrument v2):
- Candidates dedupe by (entity, sa-text); mana-ability options ("Add {")
  are EXCLUDED from the schedulable set — they are payment machinery,
  not schedule actions.
- Costs resolve per the classify_window convention: plain cast -> card
  table; alt-keyword lead -> cost_from_sa; altcost/multiface/unparsed ->
  the `uncertain` bucket (counted, never guessed). Commander tax
  optimistic (2 x min cmdcast). X=0, phyrexian free (optimistic
  throughout, matching the instrument).
- Affordability under the `now` source view; `full` view separately
  (sickness-blocked headroom). `chained` flags an untapped Signet-class
  source (the ordering-sensitive board shape).
- demand = sum of optimistic cmc over individually-now-affordable
  candidates; capacity = len(now sources). resource_bound = (>=2
  affordable) AND demand > capacity — the turns where scheduling can
  matter at all.
- Schedule-space size per turn: ordered subsets of the affordable set,
  sum_{k=0..n} n!/(n-k)! (reported capped at n=8 for the tail).

Usage:
  uv run python scripts/schedule_census.py \
      --stores data/trajectories/m9-rebaselinearm-s0-20260821-164002 \
               data/trajectories/m9-rebaselinearm-s1-20260821-170608 \
      --out data/runs/schedule-census-m10
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veto_knowability import (  # noqa: E402
    ALT_KEYWORD,
    Cost,
    build_card_table,
    can_pay,
    cost_from_sa,
    source_views,
)

MANA_ABILITY_SA = re.compile(r"Add \{")


def cmc(cost: Cost, extra: int = 0) -> int:
    """Optimistic converted cost in source-units (X=0, phyrexian free,
    twobrid at its 1-pip color mode)."""
    return cost.generic + len(cost.pips) + len(cost.twobrid_colors) + extra


def resolve_cost(opt: dict, ents: dict, table: dict) -> tuple[str, Cost | None, int, str]:
    """-> (bucket, cost, extra_generic, name). bucket in
    {land, mana_ability, ability, spell, uncertain}."""
    sa = str(opt.get("sa") or "")
    kind = opt.get("kind")
    ent = ents.get(opt.get("e"))
    name = (ent or {}).get("n", "")
    if kind == "land":
        return "land", None, 0, name
    if kind == "ability":
        if MANA_ABILITY_SA.search(sa.split(".", 1)[0]):
            return "mana_ability", None, 0, name
        cost, free = cost_from_sa(sa)
        if ent is not None and "T" in free and ent.get("z") == "battlefield" \
                and (ent.get("tap") or ent.get("sick")):
            # {T} ability on a tapped/sick host — unaffordable on its face
            return "ability", Cost(generic=10 ** 6), 0, name
        return "ability", cost or Cost(), 0, name
    # spell cast
    if ent is None:
        return "uncertain", None, 0, name
    card = table.get(name)
    if card is None:
        return "uncertain", None, 0, name
    if card.altcost:
        return "uncertain", None, 0, name
    extra = 0
    if ent.get("z") == "command":
        extra = 0  # filled by caller from obs (needs seat context)
    plain = sa.startswith(f"{name} - ") or sa == name
    if plain:
        cost = card.cost
    elif ALT_KEYWORD.match(sa):
        cost, _ = cost_from_sa(sa)
        if cost is None:
            return "uncertain", None, extra, name
    elif card.multiface:
        return "uncertain", None, extra, name
    else:
        cost = card.cost
    if cost.uncertain:
        return "uncertain", None, extra, name
    return "spell", cost, extra, name


def sched_space(n: int) -> int:
    """Ordered subsets of an n-set (incl. empty): sum n!/(n-k)!."""
    return sum(math.factorial(n) // math.factorial(n - k) for k in range(n + 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from anvil.store.trajectories import TrajectoryStore

    table = build_card_table()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows_f = open(out / "turns.jsonl", "w")

    n_games = 0
    for store in args.stores:
        ts = TrajectoryStore(Path(store))
        sname = Path(store).name
        for traj in ts.games(skip_undecodable=True):
            g = traj.header["g"]
            players = traj.header.get("players") or []
            seat = next((i for i, p in enumerate(players)
                         if str(p.get("name", "")).startswith("Anvil")), 0)
            n_games += 1
            groups: dict[int, list] = defaultdict(list)
            for dec in traj.decisions:
                if dec.get("m") != "chooseSpellAbilityToPlay":
                    continue
                if dec.get("p") != seat or dec.get("t", 0) < 1:
                    continue
                groups[dec["t"]].append(dec)
            for t, decs in sorted(groups.items()):
                emis = next((d for d in decs if d.get("obs")), None)
                if emis is None:
                    continue
                obs = emis["obs"]
                ents = {e["e"]: e for e in obs.get("ents", [])}
                stratum = "own_turn" if obs.get("glob", {}).get("ap") == seat else "off_turn"
                try:
                    cmd_extra = 2 * min(obs["players"][seat]["cmdcast"])
                except (KeyError, IndexError, TypeError, ValueError):
                    cmd_extra = 0
                views = source_views(obs, seat, table)
                capacity = len(views.now)

                seen: set[tuple] = set()
                counts = Counter()
                afford_now = afford_full = 0
                demand = 0
                for opt in emis.get("opts", []):
                    key = (opt.get("e"), str(opt.get("sa") or "")[:60])
                    if key in seen:
                        continue
                    seen.add(key)
                    bucket, cost, extra, name = resolve_cost(opt, ents, table)
                    if bucket == "spell" and ents.get(opt.get("e"), {}).get("z") == "command":
                        extra = cmd_extra
                    counts[bucket] += 1
                    if bucket in ("spell", "ability") and cost is not None:
                        if can_pay(cost, views.now, extra):
                            afford_now += 1
                            demand += cmc(cost, extra)
                        if can_pay(cost, views.full, extra):
                            afford_full += 1

                n_sched = counts["spell"] + counts["ability"]
                realized = Counter()
                for d in decs:
                    for r in d.get("ret") or []:
                        k = r.get("kind")
                        if k and not (k == "ability" and MANA_ABILITY_SA.search(
                                str(r.get("sa") or ""))):
                            realized[k] += 1
                row = {
                    "store": sname, "g": g, "seat": seat, "t": t,
                    "stratum": stratum, "windows": len(decs),
                    "cands": n_sched, "lands": counts["land"],
                    "mana_abilities": counts["mana_ability"],
                    "uncertain": counts["uncertain"],
                    "afford_now": afford_now, "afford_full": afford_full,
                    "capacity": capacity, "demand": demand,
                    "resource_bound": int(afford_now >= 2 and demand > capacity),
                    "chained": int(views.chained),
                    "realized_spells": realized["spell"],
                    "realized_abilities": realized["ability"],
                    "realized_lands": realized["land"],
                }
                rows_f.write(json.dumps(row) + "\n")
    rows_f.close()

    # ---------------------------------------------------------------- report
    rows = [json.loads(x) for x in open(out / "turns.jsonl")]
    rep: dict = {"games": n_games, "turn_groups": len(rows), "strata": {}}
    for stratum in ("own_turn", "off_turn"):
        rs = [r for r in rows if r["stratum"] == stratum]
        if not rs:
            continue
        n = len(rs)
        ch = Counter(min(r["cands"], 8) for r in rs)
        ah = Counter(min(r["afford_now"], 8) for r in rs)
        multi = [r for r in rs if r["afford_now"] >= 2]
        s = {
            "turns": n,
            "turns_per_game": round(n / n_games, 2),
            "cands_hist": {str(k): ch[k] for k in sorted(ch)},
            "afford_now_hist": {str(k): ah[k] for k in sorted(ah)},
            "frac_afford_ge2": round(len(multi) / n, 4),
            "frac_afford_3to4": round(
                sum(1 for r in rs if 3 <= r["afford_now"] <= 4) / n, 4),
            "frac_resource_bound": round(
                sum(r["resource_bound"] for r in rs) / n, 4),
            "frac_resource_bound_of_ge2": round(
                sum(r["resource_bound"] for r in multi) / max(len(multi), 1), 4),
            "frac_chained": round(sum(r["chained"] for r in rs) / n, 4),
            "frac_any_uncertain": round(
                sum(1 for r in rs if r["uncertain"]) / n, 4),
            "sickness_headroom_frac": round(
                sum(1 for r in rs if r["afford_full"] > r["afford_now"]) / n, 4),
            "mean_realized_casts": round(
                sum(r["realized_spells"] + r["realized_abilities"]
                    for r in rs) / n, 3),
            "sched_space": {},
        }
        for k in sorted(ah):
            s["sched_space"][str(k)] = {
                "turns": ah[k],
                "ordered_subsets": sched_space(k) if k < 8 else ">=109601",
            }
        rep["strata"][stratum] = s
    json.dump(rep, open(out / "report.json", "w"), indent=2)
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
