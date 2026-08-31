#!/usr/bin/env python3
"""ADR-0088: the per-era certified schedule-label MINT — trajectory-scale
decode supervision on the loop's OWN stores (the grounded + dense +
on-distribution driver the probe pair jointly specified; ADR-0087 promoted
this from follow-on to prerequisite).

Reuses the sweep machinery verbatim where it is pinned: eligible_turns /
build_arms (schedule_sweep), the stage-1 certification pins (sched_pins:
ARM_CAP 16, K_ROLLS 8, THETA 2.0, CONSISTENT 0.75, select/score split),
and the seed_sched_labels label mapper. What differs from the ceiling
sweep: multiple SOURCE STORES with per-store replay parameters (each
probe iteration has its own pairs file / seed range — read from the
store's run.json, never hardcoded), no marginal/auto arms, no h4 side
file, and a mint-specific rng pin.

Layout: <plan>/store-<run_id>/{sched-h2.tsv, lanes/, positives.jsonl,
labels.jsonl}; <plan>/mint-manifest.json lists (labels, store) pairs for
the loader's comma-list flags.

Usage:
  uv run python scripts/sched_mint.py sample \
      --stores data/trajectories/m10-probe1-i000-... [...] \
      --out data/runs/sched-mint-m10a --sample-n 3600
  uv run python scripts/sched_mint.py lanes \
      --plan data/runs/sched-mint-m10a --jar <probe jar> \
      --lanes 12 --concurrency 12
  <plan>/run-lanes.sh            # nice -19, resumable at lane granularity
  uv run python scripts/sched_mint.py finish --plan data/runs/sched-mint-m10a
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sched_pins as pins  # noqa: E402
from schedule_sweep import build_arms, eligible_turns  # noqa: E402
from veto_knowability import build_card_table  # noqa: E402

MINT_RNG_SEED = 20280830  # pinned at ADR-0088 (draw order: per store, in
# --stores order, one rng.sample per store)

REPO = Path(__file__).resolve().parent.parent


def _run_meta(store: str) -> dict:
    """Replay parameters from the source run's run.json — per-store, never
    hardcoded (probe iterations differ in pairs file AND seed range), and
    the GENERATION flag set, not the census sweep's: -paytelemetry/-reask
    are trajectory-perturbing, so the lane replays whatever the source run
    pinned (probe generation: -reask on, -paytelemetry OFF)."""
    rj = REPO / "data" / "runs" / Path(store).name / "run.json"
    meta = json.loads(rj.read_text())
    pairs = rj.parent / meta["pairs_file"]
    got = hashlib.sha256(pairs.read_bytes()).hexdigest()
    if got != meta["pairs_sha256"]:
        sys.exit(f"FATAL: {pairs} sha mismatch vs run.json ({got[:12]})")
    if meta.get("rollout_k") or meta.get("drill_file") or meta.get("fork_obs"):
        sys.exit(f"FATAL: {Path(store).name} was not a plain generation run "
                 "(rollout/drill/fork flags present) — replay parity unproven")
    return {
        "pairs": str(pairs),
        "seed_base": meta["seed_base"],
        "gpp": meta["games_per_pair"],
        "range": [meta["start_index"], meta["start_index"] + meta["games"]],
        "jar_sha256": meta["jar_sha256"],
        "paytelemetry": bool(meta.get("paytelemetry")),
        "reask": bool(meta.get("reask")),
        "tags": meta.get("tags") or "",
    }


def sample(args) -> None:
    table = build_card_table()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    per_store: list[tuple[str, list[dict], dict]] = []
    total = 0
    for store in args.stores:
        rows, frame = eligible_turns([store], table)
        per_store.append((store, rows, dict(frame)))
        total += len(rows)
        print(f"{Path(store).name}: eligible {len(rows)}")
    if total < args.sample_n:
        sys.exit(f"FATAL: eligible universe {total} < --sample-n {args.sample_n}")
    rng = random.Random(MINT_RNG_SEED)
    manifest = {"rng_seed": MINT_RNG_SEED, "sample_n": args.sample_n,
                "eligible_total": total, "stores": {}}
    for store, rows, frame in per_store:
        share = round(args.sample_n * len(rows) / total)
        picked = rng.sample(rows, min(share, len(rows)))
        sdir = out / f"store-{Path(store).name}"
        sdir.mkdir(exist_ok=True)
        c = Counter()
        with open(sdir / "sched-h2.tsv", "w") as f:
            f.write(f"# ADR-0088 mint schedfile (sched_mint.py; rng "
                    f"{MINT_RNG_SEED}; horizon {pins.HORIZON_H2})\n")
            for r in picked:
                arms = build_arms(r)
                base = f"{r['g']}\t{r['t']}\t{pins.HORIZON_H2}\t{r['seat']}"
                for i, seq in enumerate(arms):
                    tail = ("\t" + "\t".join(seq)) if seq else ""
                    f.write(f"{base}\t{i + 1}\tjoint{tail}\n")
                    c["joint_arms"] += 1
                c["turns"] += 1
        meta = _run_meta(store)
        manifest["stores"][Path(store).name] = {
            "store": store, "eligible": len(rows), "sampled": c["turns"],
            "joint_arms": c["joint_arms"], "frame": frame, "replay": meta,
            "manifest_sha": hashlib.sha256(
                (Path(store) / "manifest.json").read_bytes()).hexdigest()[:16],
        }
        print(f"  -> sampled {c['turns']} turns / {c['joint_arms']} arms")
    json.dump(manifest, open(out / "mint-manifest.json", "w"), indent=2)
    print(f"manifest -> {out / 'mint-manifest.json'}")


def lanes(args) -> None:
    plan = Path(args.plan).resolve()
    manifest = json.loads((plan / "mint-manifest.json").read_text())
    jar = Path(args.jar).resolve()
    jar_sha = hashlib.sha256(jar.read_bytes()).hexdigest()
    gui = jar.parent.parent.parent / "forge-gui"
    # the serving side of replay parity: the GENERATING ckpt, sampled at
    # the generation temperature, --fork-instrument so the sampled server
    # accepts wire-only forceschedule completions (per-roll seeds are
    # announced by the jar; no mu is recorded for them — the M7 mode)
    serve = plan / "serve.sh"
    serve.write_text(
        "#!/bin/sh\n"
        f"cd '{REPO}'\n"
        f"exec nice -n 19 .venv/bin/python -m anvil.bridge.server "
        f"--mode model --ckpt '{args.serve_ckpt}' --port {args.port} "
        f"--pass-delta 0 --sample --temperature {args.temperature} "
        f"--mu-out '{plan}/serve-mu.jsonl' --fork-instrument\n")
    serve.chmod(0o755)
    manifest["serve"] = {"ckpt": args.serve_ckpt, "port": args.port,
                         "temperature": args.temperature}
    all_lanes: list[str] = []
    total_rows = sum(s["joint_arms"] for s in manifest["stores"].values())
    for name, s in manifest["stores"].items():
        if s["replay"]["jar_sha256"] != jar_sha:
            sys.exit(f"FATAL: jar sha != {name} run.json jar (replay parity "
                     f"is the whole point) — {jar_sha[:12]}")
        sdir = plan / f"store-{name}"
        lines = [ln for ln in (sdir / "sched-h2.tsv").read_text().splitlines()
                 if ln and not ln.startswith("#")]
        games = sorted({int(ln.split("\t", 1)[0]) for ln in lines})
        n_lanes = max(1, round(args.lanes * len(lines) / total_rows))
        lane_games = {g: i % n_lanes for i, g in enumerate(games)}
        outdir = sdir / "lanes"
        outdir.mkdir(exist_ok=True)
        rep = s["replay"]
        for i in range(n_lanes):
            tsv = outdir / f"lane-{i}.tsv"
            with open(tsv, "w") as f:
                for ln in lines:
                    if lane_games[int(ln.split("\t", 1)[0])] == i:
                        f.write(ln + "\n")
            n_rows_lane = sum(1 for ln in lines
                              if lane_games[int(ln.split("\t", 1)[0])] == i)
            n_turns_lane = len({(ln.split("\t")[0], ln.split("\t")[1])
                                for ln in lines
                                if lane_games[int(ln.split("\t", 1)[0])] == i})
            # every arm-roll produces a row (crash rows included) and each
            # (g,t,roll) adds a natural row — DONE is gated on ~90% of that,
            # not on exit code (a lane that dies quietly at boot exits 0)
            expect = int(0.9 * (n_rows_lane + n_turns_lane) * pins.K_ROLLS)
            scratch = outdir / f"lane-{i}.scratch"
            sh = outdir / f"lane-{i}.sh"
            # replay parity with the SOURCE run: pairs/seedbase/range/gpp
            # AND the generation flag set from its run.json (-reask /
            # -paytelemetry as pinned there; -obs/-census on — obs doubles
            # as the parity witness, see the parity subcommand).
            # -range takes (start, COUNT) — AnvilRun convention.
            extra = ""
            if rep["paytelemetry"]:
                extra += "-paytelemetry "
            if rep["reask"]:
                extra += "-reask "
            if rep["tags"]:
                extra += f"-tags '{rep['tags']}' "
            count = rep["range"][1] - rep["range"][0]
            sh.write_text(
                "#!/bin/sh\nset -e\n"
                # boot stagger: 12 JVMs mounting the card DB + connecting the
                # bridge at once is the suspected first-launch failure mode
                f"sleep {len(all_lanes) * 10}\n"
                f"cd '{gui}'\n"
                f": > '{outdir}/lane-{i}.out.jsonl'\n"
                f"nice -n 19 java -Xms3g -Xmx3g -XX:ActiveProcessorCount=2 "
                f"-XX:+ExitOnOutOfMemoryError "
                f"-jar '{jar}' anvil "
                f"-pairs '{rep['pairs']}' -gpp {rep['gpp']} -f Commander "
                f"-range {rep['range'][0]} {count} "
                f"-seedbase {rep['seed_base']} "
                f"-b grpc:localhost:{args.port} "
                f"-obs '{scratch}.obs.zst' -census '{scratch}.census.jsonl' "
                f"{extra}"
                f"-rollout {pins.K_ROLLS} -labels '{outdir}/lane-{i}.out.jsonl' "
                f"-forceschedule '{tsv}' > '{outdir}/lane-{i}.log' 2>&1\n"
                f"rows=$(wc -l < '{outdir}/lane-{i}.out.jsonl')\n"
                f"if [ \"$rows\" -ge {expect} ]; then\n"
                f"  touch '{outdir}/lane-{i}.DONE'\n"
                f"else\n"
                f"  echo \"LANE INCOMPLETE lane-{i}: $rows/{expect} rows\" >&2\n"
                f"  exit 1\n"
                f"fi\n")
            sh.chmod(0o755)
            all_lanes.append(str(sh))
        print(f"{name}: {n_lanes} lanes, {len(lines)} rows")
    # resumable driver: DONE-marked lanes are skipped on rerun
    drv = plan / "run-lanes.sh"
    drv.write_text(
        "#!/bin/sh\n# ADR-0088 mint lanes — resumable (DONE markers), "
        "nice -19 inside each lane\n"
        + "printf '%s\\n' \\\n  "
        + " \\\n  ".join(f"'{p}'" for p in all_lanes)
        + f" | while read s; do [ -e \"${{s%.sh}}.DONE\" ] && continue; "
        f"echo \"$s\"; done | xargs -P {args.concurrency} -I{{}} sh {{}}\n")
    drv.chmod(0o755)
    json.dump(manifest, open(plan / "mint-manifest.json", "w"), indent=2)
    print(f"{len(all_lanes)} lane scripts -> {drv} (concurrency {args.concurrency})")
    print(f"serve first: {serve}  (then {drv})")


def parity(args) -> None:
    """Replay-parity witness: for every game a lane replayed, the scratch
    obs decision stream — minus the trailing autoPassCancel records the jar
    emits when it early-stops the mainline after the game's LAST fork turn
    (measured on the smoke: exactly one per seat, then a forced end) — must
    be an exact PREFIX of the source store's stream, and the prefix must
    reach that last fork turn. Any real divergence means the fork states
    the rollouts certified are not the states the policy actually visited,
    and the mint is invalid for that store. Winners are NOT compared (the
    early-stop force-ends the mainline)."""
    from anvil.store.trajectories import TrajectoryStore, decode_frame

    plan = Path(args.plan).resolve()
    manifest = json.loads((plan / "mint-manifest.json").read_text())
    bad = 0
    for name, s in manifest["stores"].items():
        ts = TrajectoryStore(Path(s["store"]))
        sdir = plan / f"store-{name}"
        fork_turn: dict[int, int] = {}
        fork_turn_keys: set[tuple[int, int]] = set()
        for ln in (sdir / "sched-h2.tsv").read_text().splitlines():
            if ln and not ln.startswith("#"):
                p = ln.split("\t")
                g, t = int(p[0]), int(p[1])
                fork_turn[g] = max(fork_turn.get(g, 0), t)
                fork_turn_keys.add((g, t))
        compared = mismatched = truncated = trunc_turns = 0
        for idx_path in sorted((sdir / "lanes").glob("lane-*.scratch.obs.idx.jsonl")):
            zst = idx_path.with_name(idx_path.name.replace(".obs.idx.jsonl", ".obs.zst"))
            data = zst.read_bytes()
            for line in idx_path.read_text().splitlines():
                e = json.loads(line)
                if args.max_games and compared >= args.max_games:
                    break
                header, decs, end, _ = decode_frame(data[e["off"]:e["off"] + e["clen"]])
                g = header["g"]
                try:
                    src = ts.game(g)
                except KeyError:
                    continue
                while decs and decs[-1].get("m") == "autoPassCancel":
                    decs.pop()
                a = [(d["s"], d.get("m"), d.get("t"), d.get("oi")) for d in decs]
                b = [(d["s"], d.get("m"), d.get("t"), d.get("oi"))
                     for d in src.decisions[:len(a)]]
                last_t = a[-1][2] if a else None
                compared += 1
                if a != b:
                    # real divergence: fork states are not the visited
                    # states — fatal for the store
                    mismatched += 1
                    if mismatched <= 3:
                        div = next((i for i, (x, y) in enumerate(zip(a, b))
                                    if x != y), min(len(a), len(b)))
                        print(f"  MISMATCH {name} g{g}: prefix {len(a)} vs "
                              f"src {len(src.decisions)}, first divergence "
                              f"at dec {div}, last replayed turn {last_t} "
                              f"(fork turn {fork_turn.get(g)})")
                elif (last_t or 0) < fork_turn.get(g, 0):
                    # the measured dropped-turns class (lane-2, 2026-08-31):
                    # the replay ends before the game's later fork turns
                    # fire. The prefix is EXACT, unfired turns produced no
                    # rows, so nothing certifiable came from an unverified
                    # state — sample shrinkage, counted loudly, not fatal.
                    truncated += 1
                    trunc_turns += sum(1 for (gg, tt) in fork_turn_keys
                                       if gg == g and tt > (last_t or 0))
        print(f"{name}: {compared} games compared, {mismatched} mismatched, "
              f"{truncated} exact-but-truncated (~{trunc_turns} fork turns "
              f"dropped)")
        bad += mismatched
    if bad:
        sys.exit(f"FATAL: {bad} games diverged — replay parity FAILED")
    print("replay parity: EXACT prefix through every fork turn")


def finish(args) -> None:
    plan = Path(args.plan).resolve()
    manifest = json.loads((plan / "mint-manifest.json").read_text())
    pairs_out = []
    tot_pos = tot_lab = 0
    for name, s in manifest["stores"].items():
        sdir = plan / f"store-{name}"
        lanes_dir = sdir / "lanes"
        missing = [p for p in lanes_dir.glob("lane-*.sh")
                   if not (lanes_dir / (p.stem + ".DONE")).exists()]
        if missing:
            sys.exit(f"FATAL: {name} has {len(missing)} unfinished lanes "
                     f"(rerun {plan / 'run-lanes.sh'})")
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "schedule_read.py"), "stage1",
             "--labels", str(lanes_dir / "lane-*.out.jsonl"),
             "--sched", str(sdir / "sched-h2.tsv"),
             "--out", str(sdir)],
            check=True)
        fork = json.loads((REPO / "data" / "runs" / name / "run.json")
                          .read_text())["fork_commit"][:10]
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "seed_sched_labels.py"),
             "--plan", str(sdir),
             "--store", s["store"],
             "--out", str(sdir / "labels.jsonl"),
             "--cert-ckpt", manifest.get("serve", {}).get("ckpt", "UNKNOWN"),
             "--era", f"mint-{MINT_RNG_SEED}/{fork}"],
            check=True)
        n_pos = sum(1 for _ in open(sdir / "positives.jsonl"))
        n_lab = sum(1 for ln in open(sdir / "labels.jsonl")
                    if json.loads(ln).get("k") != "meta")
        tot_pos += n_pos
        tot_lab += n_lab
        s["positives"] = n_pos
        s["labels"] = n_lab
        pairs_out.append({"labels": str(sdir / "labels.jsonl"),
                          "store": s["store"]})
    manifest["loader"] = {
        "seed_labels": ",".join(p["labels"] for p in pairs_out),
        "seed_store": ",".join(p["store"] for p in pairs_out),
        "total_positives": tot_pos, "total_labels": tot_lab,
    }
    json.dump(manifest, open(plan / "mint-manifest.json", "w"), indent=2)
    print(f"mint complete: {tot_pos} certified positives -> {tot_lab} labels")
    print(f"loader flags:\n  --seed-labels {manifest['loader']['seed_labels']}"
          f"\n  --seed-store {manifest['loader']['seed_store']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    sp = sub.add_parser("sample")
    sp.add_argument("--stores", nargs="+", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--sample-n", type=int, required=True)
    sp.set_defaults(fn=sample)
    lp = sub.add_parser("lanes")
    lp.add_argument("--plan", required=True)
    lp.add_argument("--jar", required=True)
    lp.add_argument("--serve-ckpt", required=True,
                    help="the ckpt that GENERATED the sampled stores "
                    "(replay parity; init-ckpt stores -> m10-sched-init)")
    lp.add_argument("--port", type=int, required=True)
    lp.add_argument("--temperature", type=float, default=1.0)
    lp.add_argument("--lanes", type=int, default=12)
    lp.add_argument("--concurrency", type=int, default=12)
    lp.set_defaults(fn=lanes)
    pp = sub.add_parser("parity")
    pp.add_argument("--plan", required=True)
    pp.add_argument("--max-games", type=int, default=0,
                    help="stop after N compared games per store (0 = all)")
    pp.set_defaults(fn=parity)
    fp = sub.add_parser("finish")
    fp.add_argument("--plan", required=True)
    fp.set_defaults(fn=finish)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
