"""ADR-0136's proof: the loop resumes an interrupted generation (and an interrupted in-loop read) at the game.

Seven small loops (96 games, one iteration, from iter-405), run one after another through `anvil.runs`:

  1a  search off, uninterrupted            1c  the same again (the floor: what two uninterrupted runs differ by)
  1b  search off, `pause --now --scope all` mid-generation, relaunched
  2a  the recipe, uninterrupted, with one in-loop read
  2b  the recipe, killed mid-generation, relaunched
  3   search off, a graceful `pause --scope all` mid-generation, relaunched
  5   the recipe with one in-loop read, killed mid-read, relaunched

Each interrupted run is checked against ITSELF (the exact invariants: every game finished before the stop is
unchanged afterwards, with its mu rows; every game is in the store once; ingest saw no conflicting attempt) and
against its uninterrupted twin (ADR-0136's registered comparison). Cell 4, the clock, is read from the loops'
states. Idempotent: a cell with a result file is skipped.

  uv run python scripts/m13_resume_proof.py [--cells 1a,1c,1b,2a,2b,3,5] [--out data/runs/m13-resume-proof]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
KEYS = ("seed", "status", "winner", "turns", "windows", "first", "cap", "draw_clock", "decks", "profiles")
CELLS = {  # cell -> (arm, in-loop read?, interruption)
    "1a": ("nosearch", False, None), "1c": ("nosearch", False, None), "1b": ("nosearch", False, "kill-gen"),
    "2a": ("control", True, None), "2b": ("control", False, "kill-gen"),
    "3": ("nosearch", False, "stop-gen"), "5": ("control", True, "kill-read"),
}
TWIN = {"1c": "1a", "1b": "1a", "2b": "2a", "3": "1a", "5": "2a"}


def sh(*cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=WT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: rc {r.returncode}\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return r


def runs(*a: str, check: bool = True) -> subprocess.CompletedProcess:
    return sh("uv", "run", "python", "-m", "anvil.runs", *a, check=check)


def name_of(cell: str) -> str:
    return f"rp{cell}"


def gen_dirs(name: str) -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(WT / "data/runs" / f"{name}-i000*-2*")))


def read_dirs(name: str) -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(WT / "data/runs" / f"{name}-arm*-i000-*")))


def finished(dirs: list[Path]) -> dict[str, dict]:
    """Every game some worker invocation has finished: '<batch purpose>:<index>' -> its row."""
    out: dict[str, dict] = {}
    for d in dirs:
        purpose = d.name.rsplit("-", 2)[0]
        for f in list(d.glob("workers/*/games.jsonl")) + [d / "games.jsonl"]:
            if not f.exists():
                continue
            for line in f.read_text().splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue  # a row cut off by the kill
                out[f"{purpose}:{r['i']}"] = r
    return out


def mu_rows(name: str, games: set[int]) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in glob.glob(str(WT / "data/training" / name / "iter-000" / "mu.jsonl*")):
        if f.endswith(".json"):
            continue
        for line in open(f):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("g") in games:
                out[f"{r['g']}:{r.get('s')}:{r.get('task')}"] = line.strip()
    return out


def launch(cell: str) -> None:
    arm, read, _ = CELLS[cell]
    name = name_of(cell)
    env = [f"REPO={WT}", f"NAME={name}", "GAMES=96", "ITERS=1", "DAYZERO=0", "ARMS_GAMES=24",
           f"ARMS_EVERY={1 if read else 99}"]
    r = runs("launch", "--name", name, "--dir", f"data/runs/{name}", "--checkin", "none", "--stall-min", "90",
             "--watch", f"data/training/{name}", "--watch", f"data/runs/{name}-*",
             "--", "env", *env, "bash", "scripts/m13_arms.sh", arm, "84")
    print(r.stdout.strip()[:200], flush=True)


def wait_done(name: str) -> str:
    runs("wait", "--name", name, check=False)
    return json.loads((Path.home() / ".local/state/anvil/runs" / f"{name}.json").read_text())["state"]


def run_cell(cell: str, out: Path) -> dict:
    arm, read, cut = CELLS[cell]
    name = name_of(cell)
    res: dict = {"cell": cell, "name": name, "arm": arm, "cut": cut}
    launch(cell)
    if cut:
        dirs_fn = read_dirs if cut == "kill-read" else gen_dirs
        need = 12 if cut == "kill-read" else 30
        t0 = time.time()
        while len(finished(dirs_fn(name))) < need:
            if time.time() - t0 > 3600:
                raise RuntimeError(f"{name}: {need} finished games not reached in an hour")
            time.sleep(5)
        args = ["pause", "--name", name, "--scope", "all", "--wait"] + ([] if cut == "stop-gen" else ["--now"])
        p = runs(*args, check=False)
        res["pause"] = (p.stdout + p.stderr).strip()[-300:]
        pre = finished(dirs_fn(name))
        res["finished_at_stop"] = len(pre)
        pre_mu = mu_rows(name, {r["i"] for r in pre.values()}) if cut != "kill-read" else {}
        res["stores_at_stop"] = len(glob.glob(str(WT / "data/trajectories" / f"{name}-i000*" / "manifest.json")))
        res["state_at_stop"] = json.loads(
            (Path.home() / ".local/state/anvil/runs" / f"{name}.json").read_text())["state"]
        (out / f"{cell}.pre.json").write_text(json.dumps({"games": pre, "mu": pre_mu}))
        r = runs("relaunch", "--name", name, "--checkin", "none")
        print(r.stdout.strip()[:200], flush=True)
    res["state"] = wait_done(name)
    post = finished(gen_dirs(name))
    res["games"] = len(post)
    res["gen_dirs"] = [d.name for d in gen_dirs(name)]
    log = (WT / "data/runs" / name / "loop.log").read_text(errors="replace")
    res["log_conflict_lines"] = [ln[:200] for ln in log.splitlines() if "conflict" in ln.lower()][:5]
    res["log_resume_lines"] = [ln[:200] for ln in log.splitlines() if "resum" in ln.lower()][:8]
    mon = WT / "data/training" / name / "monitor.jsonl"
    if mon.exists():
        m = json.loads(mon.read_text().splitlines()[-1])
        res["monitor"] = {"wall_used_h": m.get("wall_used_h"), "gen_s": m.get("gen_s"), "train_s": m.get("train_s"),
                          "skips": (m.get("rl") or {}).get("skips"), "traj": (m.get("rl") or {}).get("traj"),
                          "statuses": (m.get("games") or {}).get("statuses"),
                          "search_join": ((m.get("rl") or {}).get("final") or {}).get("search_join")}
    st = WT / "data/training" / name / "loop_state.json"
    if st.exists():
        res["wall_used_s"] = json.loads(st.read_text()).get("wall_used_s")
    if cut and cut != "kill-read":
        pre = json.loads((out / f"{cell}.pre.json").read_text())
        kept = {k: r for k, r in pre["games"].items()}
        res["kept_changed"] = [k for k, r in kept.items() if k not in post or any(post[k].get(x) != r.get(x) for x in KEYS + ("ms",))]
        after_mu = mu_rows(name, {r["i"] for r in kept.values()})
        res["kept_mu_rows"] = len(pre["mu"])
        res["kept_mu_changed"] = sum(1 for k, v in pre["mu"].items() if after_mu.get(k) != v)
        res["kept_mu_extra"] = sum(1 for k in after_mu if k not in pre["mu"])
    if read:
        rd = finished(read_dirs(name))
        res["read_games"] = len(rd)
        res["read_dirs"] = [d.name for d in read_dirs(name)]
        res["read_reports"] = sum(1 for ln in log.splitlines() if ln.startswith("iter000:") or ln.startswith("iter000la:"))
        if cut == "kill-read":
            pre = json.loads((out / f"{cell}.pre.json").read_text())["games"]
            res["read_kept_changed"] = [k for k, r in pre.items() if k not in rd or any(rd[k].get(x) != r.get(x) for x in KEYS + ("ms",))]
    return res


def strip(k: str, name: str) -> str:
    return k.replace(name, "RUN", 1)


def versus(a: str, b: str) -> dict:
    """Game-for-game agreement of two cells' generations (and reads, when both have one)."""
    out = {}
    for label, fn in (("gen", gen_dirs), ("read", read_dirs)):
        ra = {strip(k, name_of(a)): r for k, r in finished(fn(name_of(a))).items()}
        rb = {strip(k, name_of(b)): r for k, r in finished(fn(name_of(b))).items()}
        if not ra or not rb:
            continue
        both = sorted(set(ra) & set(rb))
        same = sum(1 for k in both if all(ra[k].get(x) == rb[k].get(x) for x in KEYS))
        out[label] = {"paired": len(both), "identical": same, "only_a": len(set(ra) - set(rb)), "only_b": len(set(rb) - set(ra))}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="1a,1c,1b,2a,2b,3,5")
    ap.add_argument("--out", default="data/runs/m13-resume-proof")
    a = ap.parse_args()
    out = WT / a.out
    out.mkdir(parents=True, exist_ok=True)
    os.chdir(WT)
    for cell in a.cells.split(","):
        f = out / f"{cell}.json"
        if not f.exists():
            print(f"=== cell {cell} {time.strftime('%H:%M:%S')}", flush=True)
            res = run_cell(cell, out)
            f.write_text(json.dumps(res, indent=1))
        res = json.loads(f.read_text())
        if cell in TWIN and (out / f"{TWIN[cell]}.json").exists():
            res["versus_" + TWIN[cell]] = versus(cell, TWIN[cell])
            f.write_text(json.dumps(res, indent=1))
        print(json.dumps({k: v for k, v in res.items() if k not in ("gen_dirs", "read_dirs")}, indent=1), flush=True)
    print("PROOF RUNS DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
