#!/usr/bin/env python3
"""M9 rung 3 → D4: the payment drill accuracy scorer (per-kind).

D4's primary readout (m9-rung3-draft session pin 3): drill accuracy =
the model's ARGMAX pick lands in the certified-best outcome-equivalence
class, scored per shape and — separately, never blended — per metric
kind (positive vs auto_correct; evalset-assembly pin 2: the +2.0
auto-bias init scores ~100% on auto-correct at day zero, so blending
would inflate the headline).

Three subcommands around the fork's certify OBSERVE mode (CensusRun
-certify with "mode":"observe" jobs + -obsout):

  plan   evalset of record -> observe-jobs.jsonl. One job per drill
         (positive + auto-correct), renumbered sequentially (the obs
         store's game idx = job id, and batch-local job ids collide);
         provenance (batch, orig job, kind, shape, best, exp_options)
         stays in the master file, stripped from lane files.
  lanes  lane scripts: certify + -certout + -obsout per lane.
  score  join obs frames (the window's dec record, decoded straight from
         the lane obs.zst files — no store ingest) to drill verdicts,
         featurize with the standing pay_class path (scorer/serve parity:
         the fork emits the SAME labels the serve path presents), run the
         checkpoint's argmax, report per-(shape × kind) accuracy.

Integrity gates at score time, all loud:
  - a drill whose observe row missed (window drift) is counted, excluded;
  - a drill whose observe-time option count differs from its certify-time
    count (jar drift across eras — the ADR-0067 class) is counted as
    option_mismatch, excluded (its best-arm index no longer addresses the
    same option list);
  - the day-zero signature (every pick == auto) is printed when it holds:
    positive accuracy 0%, auto-correct 100% — the instrument's
    calibration point on a pre-M9 checkpoint.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from payment_certify import JAVA_JOB_FIELDS  # noqa: E402 (same scripts/ dir)

OBSERVE_JOB_FIELDS = JAVA_JOB_FIELDS + ("mode",)


def plan(args) -> None:
    jobs_by_batch: dict[str, dict[int, dict]] = {}
    for spec in args.jobs:
        name, path = spec.split("=", 1)
        jobs_by_batch[name] = {j["job"]: j for j in map(json.loads, open(path))}

    ev = Path(args.evalset)
    out_rows = []
    for fname in ("positive-drills.jsonl", "autocorrect-drills.jsonl"):
        for line in open(ev / fname):
            d = json.loads(line)
            batch = jobs_by_batch.get(d["batch"])
            if batch is None:
                raise SystemExit(f"no --jobs mapping for batch {d['batch']}")
            src = batch.get(d["job"])
            if src is None:
                raise SystemExit(f"batch {d['batch']} jobs file has no job {d['job']}")
            out_rows.append({
                "job": len(out_rows), "mode": "observe",
                "seed": src["seed"], "deck1": src["deck1"], "deck2": src["deck2"],
                "p": src["p"], "t": src["t"], "sa": src["sa"], "ord": src.get("ord", 0),
                "arms": 0, "k": 1, "horizon": 0,
                # provenance (stripped by lanes, joined at score)
                "batch": d["batch"], "orig_job": d["job"], "kind": d["kind"],
                "shape": d["shape"], "best": d["best"],
                # ADR-0082: the cleared-positive outcome class (v2 evalsets);
                # absent (v1 rows / auto-correct) => the exact index stands
                "cls": d.get("cls", [d["best"]]),
                "exp_options": src["arms"],  # |options| at certify-plan time
            })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        for r in out_rows:
            f.write(json.dumps(r) + "\n")
    by = defaultdict(int)
    for r in out_rows:
        by[(r["shape"], r["kind"])] += 1
    print(f"planned {len(out_rows)} observe jobs -> {out}")
    for (s, k), n in sorted(by.items()):
        print(f"  {s:<18} {k:<12} {n}")


def lanes(args) -> None:
    jobs = [json.loads(x) for x in open(args.jobs)]
    outdir = Path(args.jobs).resolve().parent
    prefix = Path(args.jobs).stem.removesuffix(".jobs").removesuffix("-jobs")
    gui = Path(args.jar).resolve().parent.parent.parent / "forge-gui"
    for i in range(args.n):
        chunk = jobs[i:: args.n]
        jf = outdir / f"{prefix}-lane-{i}.jobs.jsonl"
        with open(jf, "w") as f:
            for j in chunk:
                f.write(json.dumps({k: j[k] for k in OBSERVE_JOB_FIELDS}) + "\n")
        sh = outdir / f"{prefix}-lane-{i}.sh"
        sh.write_text(
            "#!/bin/sh\nset -e\n"
            f"cd '{gui}'\n"
            f"nice -n 19 java -Xms1g -Xmx2g -XX:ActiveProcessorCount=2 -jar '{args.jar}' "
            f"census -f Commander -paytelemetry -certify '{jf}' "
            f"-certout '{outdir}/{prefix}-lane-{i}.out.jsonl' "
            f"-obsout '{outdir}/{prefix}-lane-{i}.obs.zst'\n"
        )
        sh.chmod(0o755)
    print(f"wrote {args.n} lane scripts under {outdir}")


def _observe_frames(obs_paths: list[str]) -> dict[int, tuple[dict, dict]]:
    """job id (= obs game idx) -> (frame header, the window's wire dec)."""
    from anvil.bridge.featurize import store_wire_hist
    from anvil.store.trajectories import decode_frame

    out: dict[int, tuple[dict, dict]] = {}
    for path in obs_paths:
        idx_path = str(path)[:-4] + ".idx.jsonl" if str(path).endswith(".zst") else str(path) + ".idx.jsonl"
        data = Path(path).read_bytes()
        for line in open(idx_path):
            e = json.loads(line)
            try:
                header, decs, _end, _marks = decode_frame(data[e["off"]: e["off"] + e["clen"]])
            except Exception as ex:  # noqa: BLE001
                print(f"  DECODE FAIL g={e['g']} in {path}: {type(ex).__name__}: {ex}")
                continue
            pays = [d for d in decs if d.get("m") == "payManaCost" and d.get("opts")]
            if len(pays) != 1:
                print(f"  FRAME ANOMALY g={e['g']}: {len(pays)} bridged pay decs (expected 1)")
                continue
            w = dict(pays[0])
            w["hist"] = store_wire_hist([], w["_pos"])
            out[e["g"]] = (header, w)
    return out


def _accuracy_table(rows: list[dict]) -> dict:
    """rows: {shape, kind, status, correct} -> nested report dict."""
    tab: dict = defaultdict(lambda: {"n": 0, "correct": 0, "miss": 0, "option_mismatch": 0})
    for r in rows:
        cell = tab[(r["shape"], r["kind"])]
        if r["status"] == "scored":
            cell["n"] += 1
            cell["correct"] += int(r["correct"])
        else:
            cell[r["status"]] += 1
    return dict(tab)


def score(args) -> None:
    import torch

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import collate, default_methods
    from anvil.training.train import build_net

    jobs = [json.loads(x) for x in open(args.jobs)]
    cert: dict[int, dict] = {}
    for line in open(args.certout):
        r = json.loads(line)
        if r.get("ev") == "certify" and r.get("arm") == 0:
            cert[r["job"]] = r
    frames = _observe_frames(args.obs)

    methods = default_methods()
    stem = str(args.embed).removesuffix(".safetensors")
    ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    net = build_net(stem, ckpt["config"]["pool_manifest"], len(methods),
                    n_sa=ckpt["config"].get("sa_vocab_size", 0))
    net.load_compat(ckpt["model"])
    net.eval()
    feat = Featurizer(stem, methods)

    rows = []
    picks = []
    scored_jobs = []
    for j in jobs:
        c = cert.get(j["job"])
        f = frames.get(j["job"])
        if c is None or f is None or not c.get("fired") or c.get("exec") != "observed":
            rows.append({**j, "status": "miss"})
            continue
        header, w = f
        if len(w["opts"]) != j["exp_options"] + 1:
            # observe-time enumeration diverged from certify-time (jar
            # drift): the banked best-arm index no longer addresses this
            # option list — excluded, loudly
            rows.append({**j, "status": "option_mismatch"})
            continue
        ex, _aux = feat.example(w, header, "pay_class")
        batch = collate([ex])
        with torch.no_grad():
            out = net.act(batch)
        pick = int(out["choice"][0])
        picks.append(pick)
        # ADR-0082: correct = the pick lands IN the certified outcome class
        # (the docstring's promise, now the code's behavior); v1 jobs
        # without cls fall back to the exact index
        cls = j.get("cls") or [j["best"]]
        rows.append({**j, "status": "scored", "pick": pick, "correct": pick in cls})
        scored_jobs.append(j["job"])

    tab = _accuracy_table(rows)
    print(f"scored {len(scored_jobs)} / {len(jobs)} drills "
          f"(ckpt {args.ckpt})")
    for (s, k), cell in sorted(tab.items()):
        acc = f"{cell['correct'] / cell['n']:.3f}" if cell["n"] else "—"
        extras = "".join(
            f" {name}={cell[name]}" for name in ("miss", "option_mismatch") if cell[name])
        print(f"  {s:<18} {k:<12} n={cell['n']:<4} acc={acc}{extras}")
    for kind in ("positive", "auto_correct"):
        n = sum(c["n"] for (s, k), c in tab.items() if k == kind)
        good = sum(c["correct"] for (s, k), c in tab.items() if k == kind)
        print(f"  {kind:<12} overall: {good}/{n}" + (f" = {good / n:.3f}" if n else ""))
    if picks and all(p == 0 for p in picks):
        print("  DAY-ZERO SIGNATURE: every pick = auto (the +2.0 bias calibration point)")
    if args.out:
        with open(args.out, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"per-drill rows -> {args.out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("evalset", help="evalset-of-record directory")
    p.add_argument("--jobs", action="append", required=True,
                   help="BATCH=certify-jobs.jsonl mapping (repeatable)")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=plan)
    n = sub.add_parser("lanes")
    n.add_argument("--jobs", required=True)
    n.add_argument("--jar", required=True)
    n.add_argument("-n", type=int, default=4)
    n.set_defaults(fn=lanes)
    s = sub.add_parser("score")
    s.add_argument("--jobs", required=True, help="observe master jobs file (with provenance)")
    s.add_argument("--certout", required=True, help="concatenated observe certout")
    s.add_argument("--obs", nargs="+", required=True, help="lane obs.zst files")
    s.add_argument("--ckpt", required=True)
    s.add_argument("--embed", required=True)
    s.add_argument("--out", default=None, help="per-drill result rows (jsonl)")
    s.set_defaults(fn=score)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
