import argparse
import secrets
from pathlib import Path

from anvil.bridge.harness import orchestrator as orc


def main() -> None:
    ap = argparse.ArgumentParser(prog="anvil.bridge.harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    la = sub.add_parser("launch")
    group = la.add_mutually_exclusive_group(required=True)
    group.add_argument("--decks", nargs=2, default=None)
    group.add_argument(
        "--pool", action="store_true", help="deck pairs scheduled over the latest pool manifest"
    )
    group.add_argument(
        "--pairs-file",
        type=Path,
        default=None,
        help="explicit pair schedule (D8 arms: valpair-only held-out matchups)",
    )
    la.add_argument(
        "--games-per-pair",
        type=int,
        default=5,
        help="games per scheduled pair (pool mode; default 5)",
    )
    la.add_argument("--games", type=int, required=True)
    la.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="first game index (extend a prior run's seed stream: same "
        "--seed-base + disjoint range = one deterministic corpus)",
    )
    la.add_argument(
        "--format",
        default="Commander",
        help="Forge GameType passed to -f (e.g. Commander, Constructed)",
    )
    la.add_argument(
        "--pool-format",
        choices=["dc", "pauper"],
        default="dc",
        help="which pool (--pool mode) to schedule pairs from; "
        "dc -> Commander decks, pauper -> Constructed decks "
        "(pair with --format Constructed)",
    )
    la.add_argument("--workers", type=int, default=16)
    la.add_argument("--colocated", action="store_true")
    la.add_argument("--bridge", default="local-random")
    la.add_argument("--tags", default="")
    la.add_argument("--purpose", default="run")
    la.add_argument("--seed-base", type=int, default=None)
    la.add_argument(
        "--pool-version",
        default=None,
        help="stamp this pool version into run.json. The --pool "
        "branch derives it; an explicit --pairs-file run has "
        "no pool to derive it FROM, so without this the store "
        "ingest warns 'provenance is incomplete' (every "
        "final_read arm did, through the D4 re-baseline).",
    )
    la.add_argument("--chunk", type=int, default=200)
    la.add_argument("--calibrated", action="store_true")
    la.add_argument(
        "--obs",
        action="store_true",
        help="write observation logs (obs.zst per worker; observation-schema-v1)",
    )
    la.add_argument(
        "--census",
        action="store_true",
        help="write census logs (census.jsonl per worker; D8 veto/rung telemetry)",
    )
    la.add_argument(
        "--paytelemetry",
        action="store_true",
        help="payment-surface telemetry (M9 D3 §3c: enumeration + flag kv on "
        "every in-scope payManaCost). Trajectory-perturbing like --obs — "
        "replays must run under the same flag; runs pin it (the M10 ceiling "
        "census requires it for sweep replay parity)",
    )
    la.add_argument(
        "--bridge-seats",
        default=None,
        help="csv of bridged seat indices (mixed-seat D8 arms; default all seats)",
    )
    la.add_argument(
        "--reask",
        action="store_true",
        help="re-ask-on-veto (d6-vtrace-loop §6b): re-issue vetoed priority "
        "decisions with the vetoed candidate removed",
    )
    la.add_argument(
        "--rollout-k",
        type=int,
        default=None,
        help="rollout-label mode (M2 D4): K fork completions per point",
    )
    la.add_argument(
        "--rollout-points",
        type=int,
        default=4,
        help="sampled fork points per game (rollout-label mode)",
    )
    la.add_argument(
        "--drill-file",
        type=Path,
        default=None,
        help="drill mode (M4 D2): explicit per-index fork turns; "
        "unlisted indices are skipped (requires --rollout-k)",
    )
    la.add_argument(
        "--drill-stop", action="store_true", help="end mainlines after their last drill fork point"
    )
    la.add_argument(
        "--fork-obs",
        action="store_true",
        help="fork-session store (M4 D3): completions written as "
        "store frames to obs-forks.zst with per-completion "
        "seeds (requires --obs and --rollout-k)",
    )
    la.add_argument(
        "--fork-ns",
        type=int,
        default=None,
        help="store-namespace ordinal for fork-session synthetic game ids "
        "(M9 boundary: unique per source store within a selection; the "
        "planner assigns and the manifest records it)",
    )
    la.add_argument(
        "--certify",
        type=int,
        default=None,
        metavar="HORIZON",
        help="M10 reset Fork 3 inline certification: at -points-sampled quiescent "
        "MAIN1 fork points the worker asks the bridge for schedule arms and "
        "rolls them out K times to this turn horizon (0 = natural end); the "
        "server's --certify-rate is the accept gate (requires --rollout-k; "
        "excludes --fork-obs/--drill-file/--force-branch/--force-seq)",
    )
    la.add_argument(
        "--heap",
        default="2g",
        help="worker JVM heap (-Xms/-Xmx); certifying workers run 4g (the mint's "
        "AiCache mainline-accumulation OOM class)",
    )
    la.add_argument(
        "--force-branch",
        action="store_true",
        help="forced-branch paired rollouts (M7 D2): act/hold "
        "branches x K paired completions per drilled fork "
        "point, labels-only (requires --drill-file + "
        "--rollout-k; excludes --fork-obs)",
    )
    la.add_argument(
        "--force-seq",
        type=int,
        default=None,
        help="sequence probe (M7 D2 routing pin): natural/hold-N/"
        "act-N arms x K paired completions per drilled fork "
        "point over an N-turn horizon, labels-only (requires "
        "--drill-file + --rollout-k; excludes --fork-obs and "
        "--force-branch)",
    )
    la.add_argument(
        "--seq-arms",
        choices=("nat", "all"),
        default=None,
        help="M8 D1: 'nat' runs the NATURAL arm alone under an "
        "OBSERVE directive (records first-spell/first-land "
        "timing per completion, never forces); requires "
        "--force-seq",
    )

    for name in ("resume", "pause", "status", "summarize"):
        p = sub.add_parser(name)
        p.add_argument("run_dir", type=Path)

    rp = sub.add_parser("replay")
    rp.add_argument("run_dir", type=Path)
    rp.add_argument("index", type=int)

    a = ap.parse_args()
    if a.cmd == "launch":
        if a.seed_base is None:
            a.seed_base = secrets.randbelow(1 << 62)
        orc.launch(a)
    elif a.cmd == "resume":
        orc.resume(a.run_dir)
    elif a.cmd == "pause":
        orc.pause(a.run_dir)
    elif a.cmd == "status":
        orc.status(a.run_dir)
    elif a.cmd == "replay":
        orc.replay(a.run_dir, a.index)
    elif a.cmd == "summarize":
        orc.summarize(a.run_dir)


if __name__ == "__main__":
    main()
