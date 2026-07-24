"""Early-doom analysis (M3 flex track: ceiling estimate + Grindstone
curation signal, queued in the 2026-07-23 devlog).

Question: of the model's LOSSES in the 2,000-game closing read, what
fraction were luck-locked — games the omniscient critic says were never
winnable (matchup + opener + draws), as opposed to winnable games the
policy threw away? The luck-locked fraction bounds what any policy
improvement can buy on this eval (the ceiling); the complement — losses
where the model WAS ahead and lost the lead — is the curation signal:
each carries a crash window, a concrete position to seed Grindstone
drills from.

Method: walk each arm's trajectory store, evaluate the full-vis critic
(P(model_seat wins)) at the first obs-carrying decision of every turn,
from the model's perspective. Featurization/inference reuse the Ante
ledger's ValueEvaluator verbatim (full-vis detection, load_compat,
batching). Two passes:

  trace    stores -> per-game value trajectories (traces.jsonl)
  analyze  traces -> summary.json (doom curves over a threshold sweep,
           win-side false-doom control, reliability bins, ceiling curve)
           + curation.jsonl (addressable losses ranked by value crash)

The doom label depends on the critic's absolute CALIBRATION, not just
ranking — the reliability table in the summary is the check that the
whole exercise means anything. Run with two critics (the on-policy
run7b iter-014 critic and the standing d4-critic-fullvis) and compare:
conclusions that survive both are the ones to act on.

Usage:
  uv run python scripts/early_doom.py trace \
      --arm data/trajectories/run7b-bestarm-s0-20260723-131157:0 \
      --arm data/trajectories/run7b-bestarm-s1-20260723-135300:1 \
      --ckpt data/training/d6-run7b/iter-014/critic/last.pt \
      --out data/runs/early-doom-run7b-i14
  uv run python scripts/early_doom.py analyze --out data/runs/early-doom-run7b-i14
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

THETAS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
FROM_TURNS = [1, 3, 5]  # "doomed from turn k on": max_{turn>=k} v < theta


def trace(args: argparse.Namespace) -> None:
    from anvil.ante.ledger import ValueEvaluator
    from anvil.store.trajectories import TrajectoryStore

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ev = ValueEvaluator(args.ckpt)
    t0 = time.time()
    census: Counter = Counter()
    n_rows = 0

    with open(out_dir / "traces.jsonl", "w") as f:
        for arm in args.arm:
            root, _, seat_s = arm.rpartition(":")
            model_seat = int(seat_s)
            store = TrajectoryStore(root)
            n_arm = 0
            for traj in store.games(skip_undecodable=True):
                if args.limit and n_arm >= args.limit:
                    break
                n_arm += 1
                winner = store.winner_seat(traj.game_index)
                if winner is None:
                    census["skip_no_winner"] += 1
                    continue
                # first obs-carrying dec per turn, model's perspective
                exs, turns = [], []
                seen_turn = -1
                for i, dec in enumerate(traj.decisions):
                    obs = dec.get("obs")
                    if obs is None:
                        continue
                    turn = obs["glob"].get("turn", 0)
                    if turn < 1 or turn == seen_turn:
                        continue
                    seen_turn = turn
                    exs.append(ev.example(dec, traj.header, model_seat,
                                          traj.decisions[:i]))
                    turns.append(turn)
                if not exs:
                    census["skip_no_windows"] += 1
                    continue
                v = ev.win_probs(exs)
                end = traj.end or {}
                f.write(json.dumps({
                    "store": Path(root).name, "g": traj.game_index,
                    "seed": traj.header["seed"], "model_seat": model_seat,
                    "won": int(winner == model_seat),
                    "turns": end.get("turns"),
                    "decks": [pl["deck"] for pl in traj.header["players"]],
                    "vals": [[t, round(float(x), 4)] for t, x in zip(turns, v)],
                }) + "\n")
                n_rows += 1
                census["games"] += 1
                census["windows"] += len(exs)
                if n_rows % 200 == 0:
                    rate = n_rows / (time.time() - t0)
                    print(f"[trace] {n_rows} games ({rate:.1f}/s)", flush=True)

    meta = {"ckpt": ev.ckpt, "ckpt_step": ev.step, "arms": args.arm,
            "census": dict(census),
            "emb_misses": dict(ev.emb_misses.most_common(10)),
            "wall_s": round(time.time() - t0, 1)}
    (out_dir / "trace-meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[trace] done: {dict(census)} in {meta['wall_s']}s -> {out_dir}")


def _auc(v: np.ndarray, y: np.ndarray) -> float:
    """Mann-Whitney AUC of value v predicting y (ties handled by ranks)."""
    if y.min() == y.max():
        return float("nan")
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(len(v))
    ranks[order] = np.arange(1, len(v) + 1)
    # midranks for ties
    sv = v[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2
        i = j + 1
    n1 = int(y.sum())
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def analyze(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    rows = [json.loads(line)
            for line in (out_dir / "traces.jsonl").read_text().splitlines()]
    losses = [r for r in rows if not r["won"]]
    wins = [r for r in rows if r["won"]]
    n = len(rows)

    def max_from(r: dict, k: int) -> float:
        vs = [v for t, v in r["vals"] if t >= k]
        return max(vs) if vs else max(v for _, v in r["vals"])

    # ---- doom curves: P(never above theta from turn k on) ----
    doom: dict[str, dict] = {}
    for k in FROM_TURNS:
        ml = np.array([max_from(r, k) for r in losses])
        mw = np.array([max_from(r, k) for r in wins])
        doom[f"from_turn_{k}"] = {
            f"theta_{th:.2f}": {
                "loss_doom_frac": round(float((ml < th).mean()), 4),
                "win_false_doom_frac": round(float((mw < th).mean()), 4),
                # ceiling on THIS eval if every non-doomed loss were converted
                "ceiling": round((len(wins) + int(((ml >= th)).sum())) / n, 4),
            } for th in THETAS
        }

    # ---- reliability: does v mean P(win)? (doom labels need calibration) ----
    v_all = np.array([v for r in rows for _, v in r["vals"]])
    y_all = np.array([r["won"] for r in rows for _ in r["vals"]])
    bins = np.clip((v_all * 10).astype(int), 0, 9)
    reliability = [{"bin": f"[{b/10:.1f},{(b+1)/10:.1f})",
                    "n": int((bins == b).sum()),
                    "v_mean": round(float(v_all[bins == b].mean()), 4),
                    "win_rate": round(float(y_all[bins == b].mean()), 4)}
                   for b in range(10) if (bins == b).any()]

    # turn-bucketed AUC (absolute turn, not turns-from-end: what the doom
    # criterion actually conditions on)
    t_all = np.array([t for r in rows for t, _ in r["vals"]])
    auc_by_turn = {}
    for lo, hi in [(1, 3), (4, 6), (7, 10), (11, 16), (17, 99)]:
        m = (t_all >= lo) & (t_all <= hi)
        if m.sum() > 100:
            auc_by_turn[f"t{lo}-{hi}"] = {"n": int(m.sum()),
                                          "auc": round(_auc(v_all[m], y_all[m]), 4)}

    # ---- symmetric luck read: wins the model never trailed in ----
    always_ahead_wins = sum(1 for r in wins
                            if min(v for _, v in r["vals"]) >= 0.5)

    # ---- curation: addressable losses ranked by value crash ----
    curation = []
    for r in losses:
        vals = r["vals"]
        peak_i = max(range(len(vals)), key=lambda i: vals[i][1])
        peak_t, peak_v = vals[peak_i]
        if peak_v < 0.5:
            continue  # never ahead — luck-locked, nothing to drill
        drops = [(vals[i][1] - vals[i + 1][1], i)
                 for i in range(peak_i, len(vals) - 1)]
        if not drops:
            continue
        drop, i = max(drops)
        curation.append({
            "store": r["store"], "g": r["g"], "seed": r["seed"],
            "model_seat": r["model_seat"], "decks": r["decks"],
            "peak_turn": peak_t, "peak_v": peak_v,
            "crash_from_turn": vals[i][0], "crash_to_turn": vals[i + 1][0],
            "v_before": vals[i][1], "v_after": vals[i + 1][1],
            "drop": round(drop, 4), "game_turns": r["turns"],
        })
    curation.sort(key=lambda c: -c["drop"])
    with open(out_dir / "curation.jsonl", "w") as f:
        for c in curation:
            f.write(json.dumps(c) + "\n")

    summary = {
        "traces": str(out_dir / "traces.jsonl"),
        "ckpt": json.loads((out_dir / "trace-meta.json").read_text())["ckpt"],
        "games": n, "wins": len(wins), "losses": len(losses),
        "winrate": round(len(wins) / n, 4),
        "doom": doom,
        "always_ahead_win_frac": round(always_ahead_wins / len(wins), 4),
        "addressable_losses": len(curation),
        "addressable_loss_frac": round(len(curation) / len(losses), 4),
        "reliability": reliability,
        "auc_by_turn": auc_by_turn,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trace")
    t.add_argument("--arm", action="append", required=True,
                   help="store_dir:model_seat (repeatable)")
    t.add_argument("--ckpt", required=True, help="full-vis critic checkpoint")
    t.add_argument("--out", required=True)
    t.add_argument("--limit", type=int, default=0, help="games per arm (smoke)")
    t.set_defaults(fn=trace)
    a = sub.add_parser("analyze")
    a.add_argument("--out", required=True)
    a.set_defaults(fn=analyze)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
