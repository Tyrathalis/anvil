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
import sys
from collections import Counter, defaultdict
from pathlib import Path

RUNS_DIR = Path("data/runs")

# Fork-turn anchor: the value-crash window itself, the last turn the
# critic still liked the position (peak), or a per-game selected turn
# (the `select` verb — D3's rule; the sweep proved no global offset
# wins: o4/peak recover different games, 65 vs 56 exclusive).
ANCHOR_FIELD = {"crash": "crash_from_turn", "peak": "peak_turn", "selected": "drill_turn"}


def _load_curation(path: Path, limit: int = 0) -> list[dict]:
    rows = [json.loads(line) for line in path.open()]
    if limit:
        rows = rows[:limit]
    return rows


def plan(a: argparse.Namespace) -> None:
    if a.tag and not a.tag.isalnum():
        sys.exit(
            f"FATAL: --tag must be alphanumeric (got {a.tag!r}) — it "
            f"lands in run-dir names and the report glob"
        )
    rows = _load_curation(a.curation, a.limit)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    by_store: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_store[r["store"]].append(r)

    arms = []
    for fork_ns, (store, srows) in enumerate(sorted(by_store.items())):
        run_dir = RUNS_DIR / store
        run_json = run_dir / "run.json"
        if not run_json.exists():
            sys.exit(f"FATAL: source run dir not found for store {store!r} (expected {run_json})")
        cfg = json.loads(run_json.read_text())
        pairs = run_dir / cfg["pairs_file"]
        if not pairs.exists():
            sys.exit(f"FATAL: pairs file missing: {pairs}")

        # One drillfile line per source game; multiple crash windows in one
        # game merge into one comma-joined turn list.
        turns: dict[int, list[int]] = defaultdict(list)
        for r in srows:
            t = int(r[ANCHOR_FIELD[a.anchor]]) + a.turn_offset
            turns[int(r["g"])].append(max(1, t))
        drillfile = out / f"drill-{store}.txt"
        with drillfile.open("w") as f:
            f.write(f"# drill targets from {a.curation} ({len(srows)} rows)\n")
            for g in sorted(turns):
                ts = ",".join(str(t) for t in sorted(set(turns[g])))
                f.write(f"{g} {ts}\n")

        idxs = sorted(turns)
        arms.append(
            {
                "store": store,
                # M9 boundary: per-source-store fork-id namespace (AnvilRun
                # -forkns) — synthetic fork ids unique ACROSS source stores
                # in one selection (the run17 iter-2 MultiStore collision)
                "fork_ns": fork_ns,
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
            }
        )

    manifest = {
        "curation": str(a.curation),
        "curation_sha256": hashlib.sha256(a.curation.read_bytes()).hexdigest(),
        "ckpt": a.ckpt,
        "k": a.k,
        "anchor": a.anchor,
        "turn_offset": a.turn_offset,
        "tag": a.tag,
        "limit": a.limit or None,
        "arms": arms,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    total = sum(x["n_drills"] for x in arms)
    print(
        f"[plan] {total} drills in {sum(x['n_games'] for x in arms)} games "
        f"across {len(arms)} arms -> {out / 'manifest.json'}"
    )


def _launch_arms(
    manifest: dict,
    port: int,
    workers: int,
    chunk: int,
    k: int,
    drill_stop: bool,
    purpose_prefix: str,
    fork_obs: bool = False,
    force_seq: int | None = None,
    seq_arms: str | None = None,
) -> None:
    from anvil.training.selfplay import _run

    for arm in manifest["arms"]:
        purpose = f"{purpose_prefix}-{arm['store']}"
        cmd = [
            sys.executable,
            "-m",
            "anvil.bridge.harness",
            "launch",
            "--pairs-file",
            arm["pairs_file"],
            "--games-per-pair",
            str(arm["games_per_pair"]),
            "--seed-base",
            str(arm["seed_base"]),
            "--start-index",
            str(arm["index_min"]),
            "--games",
            str(arm["index_span"]),
            "--workers",
            str(workers),
            "--chunk",
            str(chunk),
            "--bridge",
            f"grpc:localhost:{port}",
            "--purpose",
            purpose,
            "--obs",
            "--rollout-k",
            str(k),
            "--drill-file",
            arm["drillfile"],
        ]
        if arm["bridge_seats"] is not None:
            cmd += ["--bridge-seats", str(arm["bridge_seats"])]
        if arm["reask"]:
            cmd += ["--reask"]
        if drill_stop:
            cmd += ["--drill-stop"]
        if fork_obs:
            cmd += ["--fork-obs"]
            if arm.get("fork_ns") is not None:
                cmd += ["--fork-ns", str(arm["fork_ns"])]
        if force_seq:
            cmd += ["--force-seq", str(force_seq)]
            if seq_arms:
                cmd += ["--seq-arms", seq_arms]
        print(
            f"[launch] {purpose}: {arm['n_drills']} drills / "
            f"{arm['n_games']} games (span {arm['index_span']})"
        )
        _run(cmd)


def generate(a: argparse.Namespace) -> None:
    import shutil

    from anvil.training.selfplay import _start_server, _stop_server

    out = Path(a.manifest)
    manifest = json.loads((out / "manifest.json").read_text())
    prefix = "drill" + manifest.get("tag", "")
    if a.sample_mainline and a.sample_forks:
        sys.exit(
            "FATAL: --sample-mainline is the map path; "
            "--sample-forks pins an argmax mainline by design"
        )
    if a.force_seq:
        if a.fork_obs or a.sample_forks:
            sys.exit(
                "FATAL: --force-seq is labels-only (ADR-0054 / forced-branch "
                "pin 3) — no --fork-obs / --sample-forks"
            )
        if not a.drill_ckpt:
            sys.exit(
                "FATAL: --force-seq needs --drill-ckpt (the act arm is the "
                "CURRENT policy's preferred cast — labels are policy-conditional)"
            )
    if a.seq_arms and not a.force_seq:
        sys.exit("FATAL: --seq-arms requires --force-seq")
    if a.sample_forks:
        if not (a.drill_ckpt and a.fork_obs):
            sys.exit(
                "FATAL: --sample-forks requires --drill-ckpt and "
                "--fork-obs (mu joins need synthetic ids + "
                "per-completion seeds)"
            )
        # Training generation (M4 D3): mainline replay argmax on the pinned
        # manifest ckpt, fork completions SAMPLED by --drill-ckpt with mu
        # records. One server (and one mu file) PER ARM: mu is keyed by the
        # synthetic game id, and the arms' id namespaces overlap — a shared
        # file would cross-conflict. Arms run sequentially anyway.
        for i, arm in enumerate(manifest["arms"]):
            sub = dict(manifest, arms=[arm])
            mu_path = out / f"mu-{arm['store']}.jsonl"
            mu_path.unlink(missing_ok=True)
            server = _start_server(
                a.ckpt or manifest["ckpt"],
                a.port,
                out / f"drill-server-{i}.log",
                sample=False,
                drill_ckpt=a.drill_ckpt,
                drill_sample=True,
                drill_mu_out=mu_path,
            )
            try:
                _launch_arms(
                    sub,
                    a.port,
                    a.workers,
                    a.chunk,
                    a.k or manifest["k"],
                    a.drill_stop,
                    prefix,
                    fork_obs=True,
                )
            finally:
                _stop_server(server)
            run_dirs = sorted(glob.glob(str(RUNS_DIR / f"{prefix}-{arm['store']}-*")))
            if not run_dirs or not mu_path.exists():
                sys.exit(f"FATAL: no run dir or mu file for arm {arm['store']}")
            shutil.copy(mu_path, Path(run_dirs[-1]) / "mu.jsonl")
            print(f"[generate] mu -> {run_dirs[-1]}/mu.jsonl")
    else:
        # M7 map-serving fix: sampled sources need a SAMPLED mainline replay
        # or the map measures argmax-divergent states (the cycle3 band
        # mismatch: map wr 0.374 vs true 0.062, corr 0.23). --sample-mainline
        # serves the replay sampled (exact under the seeded noise stream);
        # wire-fork completions ride --fork-instrument (no mu). The replay's
        # own mu file is a serving requirement, not a training input.
        server = _start_server(
            a.ckpt or manifest["ckpt"],
            a.port,
            out / "drill-server.log",
            sample=a.sample_mainline,
            mu_out=out / "mu-mainline.jsonl",
            drill_ckpt=a.drill_ckpt,
            # forced-seq arms are always instrument-served (sampled, no mu —
            # labels-only); sampled mainline needs it for the wire forks too
            instrument=a.sample_mainline or bool(a.force_seq),
        )
        try:
            _launch_arms(
                manifest,
                a.port,
                a.workers,
                a.chunk,
                a.k or manifest["k"],
                a.drill_stop,
                prefix,
                fork_obs=a.fork_obs,
                force_seq=a.force_seq,
                seq_arms=a.seq_arms,
            )
        finally:
            _stop_server(server)
        if a.sample_mainline:
            manifest["mainline_serving"] = "sampled"
            (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[generate] done; labels under data/runs/{prefix}-*/workers/")


def report(a: argparse.Namespace) -> None:
    """Join drill labels back to curation rows; bin by rollout ground truth."""
    out = Path(a.manifest)
    manifest = json.loads((out / "manifest.json").read_text())
    cur = {}
    for line in Path(manifest["curation"]).open():
        r = json.loads(line)
        cur[(r["store"], r["g"])] = r

    prefix = "drill" + manifest.get("tag", "")
    joined, missed = [], []
    for arm in manifest["arms"]:
        seat = int(str(arm["bridge_seats"]))
        run_glob = str(RUNS_DIR / f"{prefix}-{arm['store']}-*")
        run_dirs = sorted(glob.glob(run_glob))
        if not run_dirs:
            sys.exit(f"FATAL: no drill run dirs match {run_glob}")
        # Aggregate across every drill run for this arm, ascending by
        # timestamp — a later run's label for the same (game, turn)
        # supersedes (the re-drill flow: fix a crash class, rerun just
        # those rows). Keyed per fork POINT, not per game: multi-turn
        # drillfiles fire several forks in one mainline (fp 0,1,...)
        # and a game-keyed join silently kept only one of them (caught
        # by the M8 audit sample, 2026-08-17 — 124 of 500 points lost).
        by_game: dict[tuple[int, int], dict] = {}
        for run_dir in run_dirs:
            for lf in glob.glob(f"{run_dir}/workers/*/labels.jsonl"):
                for line in open(lf):
                    r = json.loads(line)
                    c = cur.get((arm["store"], r["i"]))
                    if c is None:
                        continue
                    by_game[(r["i"], r["t"])] = {
                        "store": arm["store"],
                        "g": r["i"],
                        "tt": r["tt"],
                        "fired_t": r["t"],
                        "k": r["k"],
                        "model_wins": r["w"][seat],
                        "n": sum(r["w"]) + r["draw"],
                        "engine_crashes": r["crash"],
                        "v_before": c["v_before"],
                        "drop": c["drop"],
                        "crash_from_turn": c["crash_from_turn"],
                        "peak_turn": c["peak_turn"],
                        "deck": c["decks"][c["model_seat"]],
                    }
        joined += by_game.values()
        planned = {g for (s, g) in cur if s == arm["store"]}
        labeled_games = {g for (g, _) in by_game}
        missed += [{"store": arm["store"], "g": g} for g in planned - labeled_games]

    ok = [r for r in joined if r["n"] > 0]
    zero = [r for r in joined if r["n"] == 0]

    def bin_of(r):
        wr = r["model_wins"] / r["n"]
        return (
            "lost"
            if wr <= 0.2
            else "long_shot"
            if wr <= 0.45
            else "coin"
            if wr <= 0.7
            else "winnable"
        )

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
        "mean_v_before": round(sum(r["v_before"] for r in ok) / len(ok), 4) if ok else None,
        "bins": dict(bins),
        "zero_completion_decks": Counter(r["deck"] for r in zero).most_common(6),
        "missed": missed,
    }
    (out / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (out / "drills.jsonl").open("w") as f:
        for r in sorted(joined, key=lambda x: (x["store"], x["g"])):
            f.write(json.dumps(r) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "missed"}, indent=2))
    print(f"[report] -> {out / 'report.json'} + drills.jsonl ({len(missed)} replay-missed)")


def _bin_of(model_wins: int, n: int) -> str:
    wr = model_wins / n
    return (
        "lost" if wr <= 0.2 else "long_shot" if wr <= 0.45 else "coin" if wr <= 0.7 else "winnable"
    )


def select(a: argparse.Namespace) -> None:
    """Per-game drill fork-turn selection from K-rollout labels (M4 D3).

    The turn-offset sweep resolved that no global offset wins — drill
    fork turns are selected per game from measured ground truth. Rule:
    the LATEST labeled fork turn whose rollout winrate lands in the
    trainable band (default [0.25, 0.75] — outcome variance exists, and
    later = closest to the decision error, cheapest completions); if no
    turn is in-band, the latest turn ABOVE the band (the position is
    winnable early — converting won positions is still a drill); if
    nothing clears the band floor anywhere, the game is excluded (the
    luck-locked profile: lost before the critic ever liked it).

    Label sources are dirs containing drills.jsonl (the map, sweep
    arms); LATER sources supersede earlier ones at the same fork turn —
    list re-measures after selection-time labels (the D2.4 lesson).
    Output rows are the source curation rows plus drill_turn/selection
    provenance: `plan --anchor selected` consumes them directly.
    Evalset holdout is subtracted HERE — this is where training lists
    are built.
    """
    cur = {}
    for line in a.curation.open():
        c = json.loads(line)
        cur[(c["store"], c["g"])] = c

    cands: dict[tuple, dict[int, tuple[int, int]]] = defaultdict(dict)
    for src in a.labels.split(","):
        for line in (Path(src) / "drills.jsonl").open():
            r = json.loads(line)
            if r["n"] > 0:
                cands[(r["store"], r["g"])][r["fired_t"]] = (r["model_wins"], r["n"])

    holdout = set()
    if a.holdout:
        meta = json.loads((Path(a.holdout) / "meta.json").read_text())
        holdout = {tuple(x) for x in meta["held_out"]}

    lo, hi = (float(x) for x in a.band.split(":"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    picked, stats = [], Counter()
    for key in sorted(cands, key=lambda k: (k[0], k[1])):
        if key not in cur:
            sys.exit(f"FATAL: labeled game {key} has no curation row")
        if key in holdout:
            stats["held_out"] += 1
            continue
        by_t = cands[key]
        in_band = [t for t, (w, n) in by_t.items() if lo <= w / n <= hi]
        above = [t for t, (w, n) in by_t.items() if w / n > hi]
        if in_band:
            t, rule = max(in_band), "band"
        elif above:
            t, rule = max(above), "above"
        else:
            stats["excluded"] += 1
            continue
        stats[rule] += 1
        w, n = by_t[t]
        picked.append(dict(cur[key], drill_turn=t, sel_rule=rule, sel_wr=round(w / n, 4), sel_n=n))

    # Fork-store index namespace (run17 iter-2, 2026-08-18): fork indices
    # encode source_g only — the same g selected in two source stores
    # collides in the training mixture. Loud until the next-era namespace
    # fix (run13's selection carried 38 such pairs and survived on
    # rotation luck alone).
    stores_by_g: dict[int, set] = defaultdict(set)
    for r in picked:
        stores_by_g[r["g"]].add(r["store"])
    dup_g = {g: sorted(s) for g, s in stores_by_g.items() if len(s) > 1}
    if dup_g:
        sys.exit(
            f"FATAL: {len(dup_g)} cross-store duplicate source-g values in "
            f"the selection (fork-index encoding collides in training "
            f"mixtures): {dict(list(dup_g.items())[:3])} ... — dedupe the "
            f"selection or namespace the fork encoding (next-era item)"
        )

    with (out / "selection.jsonl").open("w") as f:
        for r in picked:
            f.write(json.dumps(r) + "\n")
    offsets = Counter(min(r["drill_turn"] - r["crash_from_turn"], 0) for r in picked)
    meta = {
        "curation": str(a.curation),
        "labels": a.labels.split(","),
        "holdout": a.holdout,
        "band": [lo, hi],
        "selected": len(picked),
        "stats": dict(stats),
        "mean_sel_wr": round(sum(r["sel_wr"] for r in picked) / len(picked), 4) if picked else None,
        "offset_vs_crash": {str(k): v for k, v in sorted(offsets.items())},
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    print(f"[select] {len(picked)} drill points -> {out / 'selection.jsonl'}")


def evalset(a: argparse.Namespace) -> None:
    """Select a fixed held-out drill set from a mapped manifest.

    Stratified over rollout-ground-truth bins, deterministic (sorted rows,
    even-spaced picks). The selected games are HELD OUT: D3 training plans
    must subtract them (meta.json carries the membership list).
    """
    map_dir = Path(a.map)
    manifest = json.loads((map_dir / "manifest.json").read_text())
    drills = [json.loads(line) for line in (map_dir / "drills.jsonl").open()]
    ok = sorted((r for r in drills if r["n"] > 0), key=lambda r: (r["store"], r["g"]))
    by_bin: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        by_bin[_bin_of(r["model_wins"], r["n"])].append(r)

    takes = {"winnable": a.winnable, "coin": a.coin, "long_shot": a.long_shot, "lost": a.lost}
    picked = []
    for b in ("winnable", "coin", "long_shot", "lost"):
        rows, t = by_bin.get(b, []), takes[b]
        if t < 0 or t >= len(rows):
            sel = rows
        else:
            step = len(rows) / t
            sel = [rows[int(i * step)] for i in range(t)]
        picked += [dict(r, bin=b) for r in sel]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cur_by_key = {}
    for line in Path(manifest["curation"]).open():
        c = json.loads(line)
        cur_by_key[(c["store"], c["g"])] = c
    subset = out / "evalset-curation.jsonl"
    with subset.open("w") as f:
        for r in picked:
            f.write(json.dumps(cur_by_key[(r["store"], r["g"])]) + "\n")
    with (out / "baseline.jsonl").open("w") as f:
        for r in picked:
            f.write(json.dumps(r) + "\n")

    plan(
        argparse.Namespace(
            curation=subset,
            out=str(out / "plan"),
            ckpt=manifest["ckpt"],
            k=manifest["k"],
            anchor=manifest.get("anchor", "crash"),
            turn_offset=manifest.get("turn_offset", 0),
            tag="",
            limit=0,
        )
    )
    meta = {
        "map": str(map_dir),
        "pinned_ckpt": manifest["ckpt"],
        "k": manifest["k"],
        "n": len(picked),
        "bins": dict(Counter(r["bin"] for r in picked)),
        "held_out": [[r["store"], r["g"]] for r in picked],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[evalset] {len(picked)} drills {meta['bins']} -> {out}")


def eval_ckpt(a: argparse.Namespace) -> None:
    """Run the held-out drill set with completions played by --ckpt.

    Mainline replays stay on the evalset's pinned checkpoint (dual-policy
    server, fork wids routed to --ckpt argmax); per-drill deltas are paired
    against the baseline map labels.
    """
    import time as _time

    from anvil.training.selfplay import _start_server, _stop_server

    es = Path(a.evalset)
    meta = json.loads((es / "meta.json").read_text())
    plan_manifest = json.loads((es / "plan" / "manifest.json").read_text())
    if meta.get("baseline_eval"):
        # Baseline-of-record = the pinned policy's own re-measurement under
        # eval conditions (rows carry the same model_wins/n/bin fields).
        # Never pair against the map's selection-time labels: bins were
        # selected on those, so they regress on re-measure (winnable
        # 0.865->0.794 with zero policy change).
        baseline = {
            (r["store"], r["g"]): r
            for r in json.loads((es / meta["baseline_eval"]).read_text())["rows"]
        }
    else:
        baseline = {
            (r["store"], r["g"]): r for r in map(json.loads, (es / "baseline.jsonl").open())
        }
    t0 = _time.strftime("%Y%m%d-%H%M%S")

    server = _start_server(
        meta["pinned_ckpt"], a.port, es / "eval-server.log", sample=False, drill_ckpt=a.ckpt
    )
    try:
        _launch_arms(plan_manifest, a.port, a.workers, a.chunk, meta["k"], True, "drilleval")
    finally:
        _stop_server(server)

    rows = []
    for arm in plan_manifest["arms"]:
        seat = int(str(arm["bridge_seats"]))
        for run_dir in sorted(glob.glob(str(RUNS_DIR / f"drilleval-{arm['store']}-*"))):
            if run_dir.rsplit("-", 2)[-2] + "-" + run_dir.rsplit("-", 1)[-1] < t0:
                continue
            for lf in glob.glob(f"{run_dir}/workers/*/labels.jsonl"):
                for line in open(lf):
                    r = json.loads(line)
                    b = baseline.get((arm["store"], r["i"]))
                    if b is None:
                        continue
                    n = sum(r["w"]) + r["draw"]
                    rows.append(
                        {
                            "store": arm["store"],
                            "g": r["i"],
                            "bin": b["bin"],
                            "model_wins": r["w"][seat],
                            "n": n,
                            "base_wins": b["model_wins"],
                            "base_n": b["n"],
                        }
                    )

    per_bin: dict[str, dict] = {}
    for b in ("winnable", "coin", "long_shot", "lost"):
        sub = [r for r in rows if r["bin"] == b and r["n"] > 0]
        if not sub:
            continue
        w = sum(r["model_wins"] for r in sub)
        n = sum(r["n"] for r in sub)
        bw = sum(r["base_wins"] for r in sub)
        bn = sum(r["base_n"] for r in sub)
        per_bin[b] = {"drills": len(sub), "winrate": round(w / n, 4), "baseline": round(bw / bn, 4)}
    tot_w = sum(r["model_wins"] for r in rows)
    tot_n = sum(r["n"] for r in rows)
    result = {
        "evalset": str(es),
        "ckpt": a.ckpt,
        "at": t0,
        "drills": len(rows),
        "planned": meta["n"],
        "winrate": round(tot_w / tot_n, 4) if tot_n else None,
        "baseline": round(sum(r["base_wins"] for r in rows) / sum(r["base_n"] for r in rows), 4)
        if rows
        else None,
        "per_bin": per_bin,
        "rows": rows,
    }
    rep = es / f"eval-{t0}.json"
    rep.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    print(f"[eval] -> {rep}")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan")
    p.add_argument("--curation", type=Path, required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--ckpt",
        required=True,
        help="checkpoint that generated the source games (mainline replay policy; served argmax)",
    )
    p.add_argument("--k", type=int, default=16, help="completions per fork point")
    p.add_argument(
        "--anchor",
        choices=sorted(ANCHOR_FIELD),
        default="crash",
        help="fork-turn anchor: the value-crash window or the "
        "pre-crash value peak (default: crash)",
    )
    p.add_argument(
        "--turn-offset",
        type=int,
        default=0,
        help="fork this many turns before (+after) the anchor (default: at the anchor turn)",
    )
    p.add_argument(
        "--tag",
        default="",
        help="alphanumeric run-dir tag: generate launches as "
        "drill<tag>-* and report aggregates only drill<tag>-* "
        "dirs — REQUIRED to keep concurrent sweep arms from "
        "superseding each other's labels",
    )
    p.add_argument("--limit", type=int, default=0, help="first N curation rows only (smokes)")
    p.set_defaults(fn=plan)

    g = sub.add_parser("generate")
    g.add_argument("--manifest", required=True, help="directory written by plan")
    g.add_argument("--ckpt", default=None, help="override the manifest checkpoint")
    g.add_argument("--k", type=int, default=None, help="override the manifest K")
    g.add_argument("--port", type=int, default=50067)
    g.add_argument("--workers", type=int, default=8)
    g.add_argument("--chunk", type=int, default=50)
    g.add_argument(
        "--drill-stop",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="end mainlines after their last fork point "
        "(--no-drill-stop = full replay, the determinism "
        "gate)",
    )
    g.add_argument(
        "--fork-obs",
        action="store_true",
        help="training generation (M4 D3): completions written "
        "as store frames (obs-forks.zst, per-completion "
        "seeds) for `anvil.store ingest --forks`",
    )
    g.add_argument(
        "--drill-ckpt",
        default=None,
        help="dual-policy serving: fork completions answered by "
        "this checkpoint, mainline replay stays on the "
        "manifest ckpt",
    )
    g.add_argument(
        "--sample-forks",
        action="store_true",
        help="sample the drill backend with mu records (per-arm "
        "server + mu file; requires --drill-ckpt and "
        "--fork-obs) — the drill TRAINING generation mode",
    )
    g.add_argument(
        "--sample-mainline",
        action="store_true",
        help="serve the mainline replay SAMPLED (required for "
        "sampled-source curation: argmax replay diverges "
        "and the map prices the wrong states); completions "
        "ride --fork-instrument, replay mu is discarded",
    )
    g.add_argument(
        "--force-seq",
        type=int,
        default=None,
        help="ADR-0054 C-seq campaign: forced-seq arms (natural/"
        "hold-N/act-N x K, N = this horizon) at the manifest's "
        "fork points, labels-only (no fork obs; the era jar runs "
        "3 arms — the 2-arm trim waits for the next boundary "
        "window). Arms answered by --drill-ckpt (the current "
        "policy) via --fork-instrument sampled serving.",
    )
    g.add_argument(
        "--seq-arms",
        choices=("nat", "all"),
        default=None,
        help="M8 D1: 'nat' = the NATURAL arm alone under an OBSERVE "
        "directive (per-completion first-spell/first-land timing "
        "recording, never forces); requires --force-seq",
    )
    g.set_defaults(fn=generate)

    r = sub.add_parser("report")
    r.add_argument(
        "--manifest",
        required=True,
        help="directory written by plan (aggregates every drill "
        "run dir for its arms; later runs supersede per game)",
    )
    r.set_defaults(fn=report)

    s = sub.add_parser("select")
    s.add_argument(
        "--curation", type=Path, required=True, help="full curation rows (payload for the output)"
    )
    s.add_argument(
        "--labels",
        required=True,
        help="comma-joined dirs each holding drills.jsonl "
        "(map, sweep arms); later supersedes at the same "
        "fork turn — list re-measures last",
    )
    s.add_argument(
        "--holdout",
        default=None,
        help="evalset dir whose meta.json held_out games are "
        "subtracted (training lists MUST pass this)",
    )
    s.add_argument("--band", default="0.25:0.75", help="trainable winrate band lo:hi")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=select)

    e = sub.add_parser("evalset")
    e.add_argument(
        "--map", required=True, help="mapped manifest dir (plan + generate + report done)"
    )
    e.add_argument("--out", required=True)
    e.add_argument("--winnable", type=int, default=-1, help="-1 = all")
    e.add_argument("--coin", type=int, default=-1)
    e.add_argument("--long-shot", dest="long_shot", type=int, default=40)
    e.add_argument("--lost", type=int, default=20)
    e.set_defaults(fn=evalset)

    v = sub.add_parser("eval")
    v.add_argument("--evalset", required=True, help="directory written by evalset")
    v.add_argument(
        "--ckpt", required=True, help="checkpoint under evaluation (plays the completions)"
    )
    v.add_argument("--port", type=int, default=50067)
    v.add_argument("--workers", type=int, default=8)
    v.add_argument("--chunk", type=int, default=50)
    v.set_defaults(fn=eval_ckpt)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
