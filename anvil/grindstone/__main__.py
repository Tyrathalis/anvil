"""Grindstone v0 (M4 D2): curated-position drill generation.

Two verbs:

  plan      curation.jsonl -> drill manifest (per-source-arm drillfiles +
            provenance). Every drill row traces to a real lost game: the
            source arm's run.json supplies the exact replay recipe (pairs
            file, seed base, games-per-pair, bridge seats, re-ask), the
            curation row supplies the fork turn (the value-crash window).
  generate  manifest -> harness launches that REPLAY each source game
            under the generating checkpoint (argmax; twin-determinism-
            certified), fork at the curated turn, and play K library-
            re-randomized completions as wire sessions (-rollout
            machinery re-aimed from sampled to curated windows). Labels
            JSONL per fork point; --no-drill-stop replays mainlines to
            their natural end (the determinism gate).

The mainline MUST be answered by the checkpoint that generated the source
game or the replay diverges before the crash window — the manifest pins
that checkpoint and generate serves it argmax, exactly as the source read
did. Obs stays ON during replay (the option scan is not a pure observer —
M1 D2), census stays off (fork decisions pollute telemetry).
"""

import argparse
import glob
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

RUNS_DIR = Path("data/runs")


def _load_curation(path: Path, limit: int = 0) -> list[dict]:
    rows = [json.loads(line) for line in path.open()]
    if limit:
        rows = rows[:limit]
    return rows


def plan(a: argparse.Namespace) -> None:
    rows = _load_curation(a.curation, a.limit)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    by_store: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_store[r["store"]].append(r)

    arms = []
    for store, srows in sorted(by_store.items()):
        run_dir = RUNS_DIR / store
        run_json = run_dir / "run.json"
        if not run_json.exists():
            sys.exit(f"FATAL: source run dir not found for store {store!r} "
                     f"(expected {run_json})")
        cfg = json.loads(run_json.read_text())
        pairs = run_dir / cfg["pairs_file"]
        if not pairs.exists():
            sys.exit(f"FATAL: pairs file missing: {pairs}")

        # One drillfile line per source game; multiple crash windows in one
        # game merge into one comma-joined turn list.
        turns: dict[int, list[int]] = defaultdict(list)
        for r in srows:
            t = int(r["crash_from_turn"]) + a.turn_offset
            turns[int(r["g"])].append(max(1, t))
        drillfile = out / f"drill-{store}.txt"
        with drillfile.open("w") as f:
            f.write(f"# drill targets from {a.curation} ({len(srows)} rows)\n")
            for g in sorted(turns):
                ts = ",".join(str(t) for t in sorted(set(turns[g])))
                f.write(f"{g} {ts}\n")

        idxs = sorted(turns)
        arms.append({
            "store": store,
            "source_run": str(run_dir),
            "drillfile": str(drillfile),
            "pairs_file": str(pairs),
            "pairs_sha256": cfg["pairs_sha256"],
            "seed_base": cfg["seed_base"],
            "games_per_pair": cfg["games_per_pair"],
            "bridge_seats": cfg["bridge_seats"],
            "reask": cfg["reask"],
            "fork_commit": cfg["fork_commit"],
            "jar_sha256": cfg["jar_sha256"],
            "pool_version": cfg["pool_version"],
            "n_drills": len(srows),
            "n_games": len(idxs),
            "index_min": idxs[0],
            "index_span": idxs[-1] - idxs[0] + 1,
        })

    manifest = {
        "curation": str(a.curation),
        "curation_sha256": hashlib.sha256(
            a.curation.read_bytes()).hexdigest(),
        "ckpt": a.ckpt,
        "k": a.k,
        "turn_offset": a.turn_offset,
        "limit": a.limit or None,
        "arms": arms,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    total = sum(x["n_drills"] for x in arms)
    print(f"[plan] {total} drills in {sum(x['n_games'] for x in arms)} games "
          f"across {len(arms)} arms -> {out / 'manifest.json'}")


def generate(a: argparse.Namespace) -> None:
    from anvil.training.selfplay import _run, _start_server, _stop_server

    out = Path(a.manifest)
    manifest = json.loads((out / "manifest.json").read_text())
    server = _start_server(a.ckpt or manifest["ckpt"], a.port,
                           out / "drill-server.log", sample=False)
    try:
        for arm in manifest["arms"]:
            purpose = f"drill-{arm['store']}"
            cmd = [sys.executable, "-m", "anvil.bridge.harness", "launch",
                   "--pairs-file", arm["pairs_file"],
                   "--games-per-pair", str(arm["games_per_pair"]),
                   "--seed-base", str(arm["seed_base"]),
                   "--start-index", str(arm["index_min"]),
                   "--games", str(arm["index_span"]),
                   "--workers", str(a.workers),
                   "--chunk", str(a.chunk),
                   "--bridge", f"grpc:localhost:{a.port}",
                   "--purpose", purpose,
                   "--obs",
                   "--rollout-k", str(a.k or manifest["k"]),
                   "--drill-file", arm["drillfile"]]
            if arm["bridge_seats"] is not None:
                cmd += ["--bridge-seats", str(arm["bridge_seats"])]
            if arm["reask"]:
                cmd += ["--reask"]
            if a.drill_stop:
                cmd += ["--drill-stop"]
            print(f"[generate] {purpose}: {arm['n_drills']} drills / "
                  f"{arm['n_games']} games (span {arm['index_span']})")
            _run(cmd)
    finally:
        _stop_server(server)
    print(f"[generate] done; labels under data/runs/drill-*/workers/")


def report(a: argparse.Namespace) -> None:
    """Join drill labels back to curation rows; bin by rollout ground truth."""
    out = Path(a.manifest)
    manifest = json.loads((out / "manifest.json").read_text())
    cur = {}
    for line in Path(manifest["curation"]).open():
        r = json.loads(line)
        cur[(r["store"], r["g"])] = r

    joined, missed = [], []
    for arm in manifest["arms"]:
        seat = int(str(arm["bridge_seats"]))
        run_glob = str(RUNS_DIR / f"drill-{arm['store']}-*")
        run_dirs = sorted(glob.glob(run_glob))
        if not run_dirs:
            sys.exit(f"FATAL: no drill run dirs match {run_glob}")
        # Aggregate across every drill run for this arm, ascending by
        # timestamp — a later run's label for the same game supersedes
        # (the re-drill flow: fix a crash class, rerun just those rows).
        by_game: dict[int, dict] = {}
        for run_dir in run_dirs:
            for lf in glob.glob(f"{run_dir}/workers/*/labels.jsonl"):
                for line in open(lf):
                    r = json.loads(line)
                    c = cur.get((arm["store"], r["i"]))
                    if c is None:
                        continue
                    by_game[r["i"]] = {
                        "store": arm["store"], "g": r["i"], "tt": r["tt"],
                        "fired_t": r["t"], "k": r["k"],
                        "model_wins": r["w"][seat],
                        "n": sum(r["w"]) + r["draw"],
                        "engine_crashes": r["crash"],
                        "v_before": c["v_before"], "drop": c["drop"],
                        "crash_from_turn": c["crash_from_turn"],
                        "peak_turn": c["peak_turn"],
                        "deck": c["decks"][c["model_seat"]],
                    }
        joined += by_game.values()
        planned = {g for (s, g) in cur if s == arm["store"]}
        missed += [{"store": arm["store"], "g": g}
                   for g in planned - set(by_game)]

    ok = [r for r in joined if r["n"] > 0]
    zero = [r for r in joined if r["n"] == 0]

    def bin_of(r):
        wr = r["model_wins"] / r["n"]
        return ("lost" if wr <= 0.2 else "long_shot" if wr <= 0.45
                else "coin" if wr <= 0.7 else "winnable")

    bins = Counter(bin_of(r) for r in ok)
    tot_w = sum(r["model_wins"] for r in ok)
    tot_n = sum(r["n"] for r in ok)
    summary = {
        "manifest": str(out / "manifest.json"),
        "drills_planned": sum(x["n_drills"] for x in manifest["arms"]),
        "drills_labeled": len(joined),
        "replay_missed": len(missed),
        "all_completions_crashed": len(zero),
        "completions": tot_n,
        "model_wins": tot_w,
        "rollout_winrate": round(tot_w / tot_n, 4) if tot_n else None,
        "mean_v_before": round(sum(r["v_before"] for r in ok) / len(ok), 4)
                         if ok else None,
        "bins": dict(bins),
        "zero_completion_decks":
            Counter(r["deck"] for r in zero).most_common(6),
        "missed": missed,
    }
    (out / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (out / "drills.jsonl").open("w") as f:
        for r in sorted(joined, key=lambda x: (x["store"], x["g"])):
            f.write(json.dumps(r) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "missed"},
                     indent=2))
    print(f"[report] -> {out / 'report.json'} + drills.jsonl "
          f"({len(missed)} replay-missed)")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan")
    p.add_argument("--curation", type=Path, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ckpt", required=True,
                   help="checkpoint that generated the source games "
                        "(mainline replay policy; served argmax)")
    p.add_argument("--k", type=int, default=16,
                   help="completions per fork point")
    p.add_argument("--turn-offset", type=int, default=0,
                   help="fork this many turns before (+after) the crash "
                        "window (default: at crash_from_turn)")
    p.add_argument("--limit", type=int, default=0,
                   help="first N curation rows only (smokes)")
    p.set_defaults(fn=plan)

    g = sub.add_parser("generate")
    g.add_argument("--manifest", required=True,
                   help="directory written by plan")
    g.add_argument("--ckpt", default=None,
                   help="override the manifest checkpoint")
    g.add_argument("--k", type=int, default=None,
                   help="override the manifest K")
    g.add_argument("--port", type=int, default=50067)
    g.add_argument("--workers", type=int, default=8)
    g.add_argument("--chunk", type=int, default=50)
    g.add_argument("--drill-stop", action=argparse.BooleanOptionalAction,
                   default=True,
                   help="end mainlines after their last fork point "
                        "(--no-drill-stop = full replay, the determinism "
                        "gate)")
    g.set_defaults(fn=generate)

    r = sub.add_parser("report")
    r.add_argument("--manifest", required=True,
                   help="directory written by plan (aggregates every drill "
                        "run dir for its arms; later runs supersede per game)")
    r.set_defaults(fn=report)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
