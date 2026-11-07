"""The run-distribution holdout bank (ADR-0124 addendum 2026-11-02): a second,
FROZEN state-ranking holdout drawn from the big run's own games, read by the
loop beside the Build 1 holdout (`selfplay.py --state-bank-run`).

Why a second holdout: the Build 1 bank's holdout is drawn from the bank the
value anchor trains on, so its Spearman reads generalization inside that
bank's distribution (August states, iter-019-era play), not to the states the
run plays. This bank's rows are fork points of games the checkpoint of record
played under the loop's own game mix, labelled by the fork's rollout labeler.
Nothing trains on it: every row is `holdout`; the anchor must never name it.

What the labeler can and cannot do: the fork labels LIVE games — at `-points`
sampled quiescent MAIN1 priority windows it copies the game and plays K
completions to the end (AnvilRun -rollout K -points M), one labels row per fork
point keyed to the mainline by a `fork` mark in the store frame. It cannot
restore a state out of an existing store (a model-played game is not
reproducible under another checkpoint's serving). So "the run's own games"
are the LABELLING RUN's mainlines: the labelling checkpoint, argmax,
network-alone, census off (the labeler's standing configuration, ADR-0015 /
ADR-0124 §2), playing the loop's mix (mirror + the two heuristic-seat
batches, --heur-frac 0.5 as the big run), recorded with --obs and ingested
with their labels. The states are then drawn from those stores, stratified by
turn x phase (the Build 1 bank's turn-stratified fork points; phase = MAIN1 by
the fork's construction, recorded) — `value_pretrain bank-run`.

Three steps, each a subcommand (the boundary session runs them in order;
`read.md` beside the bank is the template):

  label   start a server on the labelling checkpoint, launch the three
          batches in rollout-label mode, ingest each (labels ride along),
          write <out>/label.json (the run dirs, the stores, the pins).
          Price (ADR-0124 addendum 10-29): ≈ 650 labels per box-hour at K=8
          on iter-301 with 24 workers x 2 servers — 500 games x 4 points
          ≈ 2,000 labels ≈ 3 box-hours, on a QUIET box (the loop paused).
  sample  the stratified draw -> <out>/bank-state.pt + manifest.json
          (value_pretrain.bank_run_holdout; CPU).
  read    the boundary value: `value_pretrain eval` on the bank for the
          checkpoints named (CPU) -> <out>/boundary-read.jsonl; the segment's
          floor is that value minus two SE (the addendum's letter).

Usage:
  uv run python scripts/run_holdout_bank.py label  --out data/runs/run-holdout-seg4 \\
      --ckpt data/training/big-run/iter-NNN/train/last.pt --games 500 --workers 24
  uv run python scripts/run_holdout_bank.py sample --out data/runs/run-holdout-seg4 --n 2000
  uv run python scripts/run_holdout_bank.py read   --out data/runs/run-holdout-seg4 \\
      --ckpt data/training/big-run/iter-NNN/train/last.pt
  # a plumbing smoke (CPU server, one worker, K=1, two fork points, two games):
  uv run python scripts/run_holdout_bank.py label --out <dir> --ckpt <ckpt> --games 2 --workers 1 \\
      --rollout-k 1 --rollout-points 2 --device cpu --no-autocast --no-yield-gpu \\
      --dest-root <dir>/trajectories --tag runbank-smoke
"""

from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anvil.bridge.fleet import bridge_addrs, servers_for  # noqa: E402
from anvil.training.selfplay import RUNS_DIR, _start_server, _stop_server, batch_chunk  # noqa: E402
from anvil.training.value_pretrain import CKPT as FEATURIZE_CKPT  # noqa: E402
from anvil.training.value_pretrain import bank_run_holdout  # noqa: E402

LAUNCH_JAR = "data/runs/tgtmask/forge-tgtmask3.jar"  # fork 5bd040351f, the big run's jar (ADR-0123)


def batches(tag: str, games: int, heur_frac: float) -> list[tuple[str, int, int, "int | None"]]:
    """The loop's generation plan for one iteration (selfplay.iteration_batches):
    (purpose, n_games, start_index_offset, bridge_seats) — the mirror batch, then
    the heuristic-opponent games split across the two seats. The purposes end in
    `h0` / `h1` so the sampler knows the model seat (value_pretrain.model_seats_of)."""
    n_heur = int(round(games * heur_frac))
    h0 = n_heur // 2
    h1 = n_heur - h0
    n_mirror = games - n_heur
    out: list[tuple[str, int, int, "int | None"]] = []
    if n_mirror:
        out.append((f"{tag}-mirror", n_mirror, 0, None))
    if h0:
        out.append((f"{tag}-h0", h0, n_mirror, 0))
    if h1:
        out.append((f"{tag}-h1", h1, n_mirror + h0, 1))
    return out


def _run(cmd: list[str], dry: bool) -> None:
    print(f"[run-holdout] $ {' '.join(cmd)}", flush=True)
    if not dry:
        subprocess.run(cmd, check=True, cwd=ROOT)


def label(a: argparse.Namespace) -> None:
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    plan = batches(a.tag, a.games, a.heur_frac)
    n_servers = servers_for(a.workers, a.servers)
    labels_expected = a.games * a.rollout_points
    print(f"[run-holdout] label: ckpt={a.ckpt} jar={a.jar} games={a.games} ({plan}) K={a.rollout_k} "
          f"points={a.rollout_points} -> ≈ {labels_expected} labels; {a.workers} workers x {n_servers} servers "
          f"on :{a.port}; ≈ {labels_expected / 650:.1f} box-hours at the 10-29 price (K=8, 24 x 2)", flush=True)
    rec = {
        "kind": "run-distribution holdout — the labelling run (ADR-0124 addendum 11-02)",
        "ckpt": a.ckpt, "jar": a.jar, "rollout_k": a.rollout_k, "rollout_points": a.rollout_points,
        "games": a.games, "games_per_pair": a.games_per_pair, "heur_frac": a.heur_frac, "seed_base": a.seed_base,
        "workers": a.workers, "servers": n_servers, "serve": "argmax, network-alone, census off",
        "reask": True, "plan": plan, "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "runs": [], "stores": [],
    }
    if a.dry_run:
        print(json.dumps(rec, indent=2))
        return
    log = out / "label.server.log"
    server = _start_server(a.ckpt, a.port, log, sample=False, servers=n_servers,
                           device=a.device, autocast=not a.no_autocast)
    t0 = time.monotonic()
    try:
        for purpose, n, off, seats in plan:
            before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
            cmd = [
                sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
                "--pool-format", a.pool_format, "--format", a.format,
                "--games", str(n), "--games-per-pair", str(a.games_per_pair), "--start-index", str(off),
                "--workers", str(min(a.workers, n)), "--chunk", str(batch_chunk(n, a.workers, a.chunk)),
                "--bridge", bridge_addrs(a.port, n_servers), "--obs", "--reask",
                "--rollout-k", str(a.rollout_k), "--rollout-points", str(a.rollout_points),
                "--purpose", purpose, "--seed-base", str(a.seed_base),
            ]
            if seats is not None:
                cmd += ["--bridge-seats", str(seats)]
            if a.no_yield_gpu:
                # a smoke beside a running fleet: the loop's servers are a foreign GPU
                # session to this harness and it would yield to them forever
                cmd.append("--no-yield-gpu")
            if a.jar:
                cmd += ["--jar", str(ROOT / a.jar if not Path(a.jar).is_absolute() else a.jar)]
            _run(cmd, False)
            new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
            if len(new) != 1:
                raise RuntimeError(f"expected one new run dir for {purpose}, got {new}")
            rd = Path(new.pop())
            n_labels = sum(1 for f in rd.glob("workers/inv-*/labels.jsonl") for _ in f.open())
            icmd = [sys.executable, "-m", "anvil.store", "ingest", str(rd)]
            dest = None
            if a.dest_root:
                dest = ROOT / a.dest_root / rd.name
                icmd += ["--dest", str(dest)]
            _run(icmd, False)
            store = dest or (ROOT / "data/trajectories" / rd.name)
            rec["runs"].append({"purpose": purpose, "run_dir": str(rd), "games": n, "bridge_seats": seats,
                                "labels": n_labels})
            rec["stores"].append(str(store))
            (out / "label.json").write_text(json.dumps(rec, indent=2) + "\n")
    finally:
        _stop_server(server)
    rec["elapsed_s"] = round(time.monotonic() - t0, 1)
    rec["labels"] = sum(r["labels"] for r in rec["runs"])
    rec["labels_per_h"] = round(rec["labels"] / max(rec["elapsed_s"], 1) * 3600, 1)
    (out / "label.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(f"[run-holdout] label done: {rec['labels']} labels in {rec['elapsed_s']} s "
          f"({rec['labels_per_h']} / h) -> {out / 'label.json'}; stores {rec['stores']}", flush=True)


def _label_json(out: Path) -> dict:
    p = out / "label.json"
    return json.loads(p.read_text()) if p.exists() else {}


def sample(a: argparse.Namespace) -> None:
    out = ROOT / a.out
    lj = _label_json(out)
    pats = a.stores or lj.get("stores") or []
    stores = sorted(p for pat in pats for p in glob.glob(str(ROOT / pat if not Path(pat).is_absolute() else pat)))
    if not stores:
        raise SystemExit(f"[run-holdout] no stores: pass --stores or run `label` first ({out / 'label.json'})")
    label_ckpt = a.label_ckpt or lj.get("ckpt")
    if not label_ckpt:
        raise SystemExit("[run-holdout] --label-ckpt is required without a label.json")
    bank_run_holdout(stores, out, a.n, a.seed, label_ckpt, a.featurize_ckpt, a.device, a.min_n)


def read(a: argparse.Namespace) -> None:
    out = ROOT / a.out
    cmd = [sys.executable, "-m", "anvil.training.value_pretrain", "eval", "--out", str(out), "--device", a.device,
           "--fmt", a.fmt, "--split", "holdout", "--write", str(out / "boundary-read.jsonl")]
    for c in a.ckpt:
        cmd += ["--ckpt", c]
    _run(cmd, False)
    rows = [json.loads(ln) for ln in (out / "boundary-read.jsonl").read_text().splitlines()][-len(a.ckpt):]
    for r in rows:
        floor = round(r["spearman"] - 2 * r["se_boot"], 4)
        print(f"[run-holdout] {r['ckpt']}: spearman_run {r['spearman']} ± {r['se_boot']} (n {r['n']}); "
              f"the segment's --guard-spearman-run-floor at the addendum's letter = {floor}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("label", help="the labelling run: server + three rollout-label batches + ingest")
    p.add_argument("--out", required=True, help="the bank dir (label.json lands here)")
    p.add_argument("--ckpt", required=True, help="the labelling checkpoint (the segment's close ckpt)")
    p.add_argument("--jar", default=LAUNCH_JAR, help="the harness --jar (default: the big run's launch jar)")
    p.add_argument("--games", type=int, default=500, help="mainlines (x --rollout-points = labels)")
    p.add_argument("--games-per-pair", type=int, default=2, help="the loop's value")
    p.add_argument("--heur-frac", type=float, default=0.5, help="the loop's mix: half vs the heuristic")
    p.add_argument("--rollout-k", type=int, default=8, help="completions per fork point (K); 1-2 for a smoke")
    p.add_argument("--rollout-points", type=int, default=4, help="fork points per mainline (uniform distinct turns)")
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--servers", type=int, default=0, help="model servers (0 = ceil(workers / 12))")
    p.add_argument("--chunk", type=int, default=30, help="ceiling; auto-clamped")
    p.add_argument("--port", type=int, default=50090)
    p.add_argument("--seed-base", type=int, default=20261102)
    p.add_argument("--tag", default="runbank-seg4", help="the run purposes' prefix (-mirror / -h0 / -h1)")
    p.add_argument("--pool-format", default="dc")
    p.add_argument("--format", default="Commander")
    p.add_argument("--device", default=None, help="the server's device (cpu for a smoke beside a running fleet)")
    p.add_argument("--no-autocast", action="store_true")
    p.add_argument("--dest-root", default=None,
                   help="ingest the stores under this dir instead of data/trajectories (a smoke)")
    p.add_argument("--no-yield-gpu", action="store_true",
                   help="the harness does not yield to foreign GPU jobs (a CPU-served smoke beside a running "
                        "fleet; the real labelling run keeps the yield and runs on a quiet box)")
    p.add_argument("--dry-run", action="store_true", help="print the plan, launch nothing")
    p.set_defaults(fn=label)
    p = sub.add_parser("sample", help="the stratified draw -> bank-state.pt + manifest.json")
    p.add_argument("--out", required=True)
    p.add_argument("--stores", nargs="*", default=None, help="globs (default: label.json's stores)")
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20261102)
    p.add_argument("--label-ckpt", default=None, help="default: label.json's ckpt")
    p.add_argument("--featurize-ckpt", default=FEATURIZE_CKPT)
    p.add_argument("--device", default="cpu")
    p.add_argument("--min-n", type=int, default=1)
    p.set_defaults(fn=sample)
    p = sub.add_parser("read", help="the boundary value on the bank (value_pretrain eval, CPU)")
    p.add_argument("--out", required=True)
    p.add_argument("--ckpt", action="append", required=True)
    p.add_argument("--device", default="cpu")
    p.add_argument("--fmt", default="Commander")
    p.set_defaults(fn=read)
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    a.fn(a)


if __name__ == "__main__":
    main()
