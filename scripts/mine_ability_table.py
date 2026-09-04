#!/usr/bin/env python3
"""Mine the ABILITY TABLE for the hand-basis planner (m10-reset-draft §I).

The engine's option labels are rules text / "name - type P/T" — not
constructible from card data — so the planner's virtual candidates (a hand
card's cast ability before it is castable; a permanent's activations before
it exists) come from what the engine has EMITTED for each card across the
stores: per card name, per host zone, the option `sa` strings with counts.

  cast      options whose host sat in HAND (the card's cast abilities;
            alternates like "(by paying ...)" recorded with their counts)
  activate  options whose host sat on the BATTLEFIELD (activated abilities
            incl. equip/adapt/loyalty; mana abilities never appear as
            options by engine convention)
  command   options whose host sat in the COMMAND zone (commander casts)
  graveyard / exile / library  other castable-from zones (flashback, escape,
            impulse-draw exiles, ...)

Information-set hygiene (user principle 2026-09-04): the table is card
knowledge a player legitimately has (what a card can do), never game
state — which cards ARE in hand/on board comes from the seat-view obs at
the window.

Usage:
  uv run python scripts/mine_ability_table.py --stores data/trajectories/<s> [...] \
      --out data/pool/ability-table.json [--max-games N]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

ZONE_BUCKET = {"hand": "cast", "battlefield": "activate", "command": "command",
               "graveyard": "graveyard", "exile": "exile", "library": "library"}


def main() -> None:
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import norm_sa

    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-games", type=int, default=0, help="per store")
    a = ap.parse_args()
    table: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    kinds: dict[tuple, Counter] = defaultdict(Counter)
    stats = Counter()
    t0 = time.monotonic()
    for spath in a.stores:
        st = TrajectoryStore(Path(spath))
        games = st.game_indices()
        if a.max_games:
            games = games[: a.max_games]
        for g in games:
            try:
                traj = st.game(g)
            except Exception:  # noqa: BLE001
                stats["undecodable"] += 1
                continue
            stats["games"] += 1
            for d in traj.decisions:
                if d.get("m") != "chooseSpellAbilityToPlay" or not d.get("obs"):
                    continue
                ents = {e["e"]: e for e in d["obs"].get("ents", [])}
                for o in d.get("opts") or []:
                    e = ents.get(o.get("e"))
                    if e is None or not e.get("n"):
                        continue  # hidden / unnamed host
                    bucket = ZONE_BUCKET.get(e.get("z"))
                    if bucket is None:
                        stats["zone_" + str(e.get("z"))] += 1
                        continue
                    sa = norm_sa(o.get("sa", ""))
                    if not sa:
                        continue
                    table[e["n"]][bucket][sa] += 1
                    kinds[(e["n"], bucket, sa)][o.get("kind") or "other"] += 1
                    stats["options"] += 1
        print(f"[mine] {Path(spath).name}: cumulative {stats['games']} games, "
              f"{len(table)} cards, {stats['options']} options ({time.monotonic() - t0:.0f}s)", flush=True)
    out = {}
    for name, buckets in table.items():
        out[name] = {}
        for bucket, c in buckets.items():
            out[name][bucket] = [
                {"sa": sa, "n": n, "kind": kinds[(name, bucket, sa)].most_common(1)[0][0]}
                for sa, n in c.most_common()
            ]
    meta = {"stores": a.stores, "games": stats["games"], "options": stats["options"],
            "cards": len(out), "stats": dict(stats)}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"meta": meta, "cards": out}, open(a.out, "w"), indent=0)
    n_cast = sum(1 for v in out.values() if v.get("cast"))
    n_act = sum(1 for v in out.values() if v.get("activate"))
    multi = sum(1 for v in out.values() if len(v.get("cast", [])) > 1)
    print(f"[mine] {len(out)} cards ({n_cast} with cast abilities, {n_act} with activations, "
          f"{multi} with >1 cast label) from {stats['games']} games -> {a.out}")


if __name__ == "__main__":
    main()
