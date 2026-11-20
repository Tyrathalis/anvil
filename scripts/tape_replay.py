"""Forced-decision replay: replay stored served games from their answer tapes, with no server.

A served run with obs records an answer tape in each game's frame (the fork's `AnswerTape`): every
answer the mainline game took from the bridge, and every search verdict that changed it. This
script takes games from a harness run directory, writes their tapes to a file, runs the fork jar
with `-b tape:<file>` under the run's own worker command, and compares each replayed game with
the stored one: the results row (status, winner, turns, priority windows, cap, first player) and
the frame's record stream, record by record.

A game replays exactly when its record stream equals the stored one, record for record, apart
from wall times. A second verdict, "same game", means the two agree at every served decision (its
state, its options, its answer) and at the end, while some record differs in a way two launches
of the engine differ anyway (`decisions`). The report names the first differing record either way.

    uv run python scripts/tape_replay.py data/runs/<run> --games 20 --out data/runs/<run>-replay
    uv run python scripts/tape_replay.py data/runs/<run> --indices 12 40 --out <dir> --keep-going

The replay runs the run's own jar unless `--jar` names another (a later fork commit replays a
stored game only if it is behavior-identical on the game path).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import zstandard

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from anvil.bridge.harness.orchestrator import FORGE_GUI_DIR  # noqa: E402

# Worker flags a replay does not carry over: where the worker wrote, which games it played and
# what served it. The search flags stay: the fork's search monitor does on the replayed game what
# it did on the live one, short of playing copies, and the tape holds its verdicts.
DROP = {"range", "n", "results", "stopfile", "b", "obs", "census", "labels", "tape"}
RESULT_KEYS = ("status", "winner", "turns", "windows", "cap", "draw_clock", "first", "decks", "profiles")


def read_frame(obs: Path, entry: dict) -> list[dict]:
    with open(obs, "rb") as f:
        f.seek(entry["off"])
        data = f.read(entry["clen"])
    raw = zstandard.ZstdDecompressor().decompress(data, max_output_size=1 << 30)
    return [json.loads(line) for line in raw.splitlines()]


def split_tape(records: list[dict]) -> tuple[str | None, list[str]]:
    """(the tags line's value or None, the tape's entry lines)."""
    tags, lines = None, []
    for r in records:
        if r.get("k") != "ans":
            continue
        if r["a"].startswith("tags\t"):
            tags = r["a"].split("\t", 1)[1]
        else:
            lines.append(r["a"])
    return tags, lines


def comparable(records: list[dict]) -> list[dict]:
    """The record stream without tape records and wall times."""
    out = []
    for r in records:
        if r.get("k") == "ans":
            continue
        if r.get("k") == "end":
            r = {k: v for k, v in r.items() if k != "ms"}
        out.append(r)
    return out


def first_diff(stored: list[dict], replayed: list[dict]) -> dict | None:
    """The first record at which the two streams differ, or None."""
    for i, (x, y) in enumerate(zip(stored, replayed)):
        if x != y:
            keys = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
            return {"pos": i, "of": len(stored), "keys": keys, "stored": _brief(x), "replayed": _brief(y)}
    if len(stored) != len(replayed):
        return {"pos": min(len(stored), len(replayed)), "of": len(stored), "keys": ["length"],
                "stored": len(stored), "replayed": len(replayed)}
    return None


_EFFECT_ID = re.compile(r"Static Effect #\d+")


def decisions(records: list[dict]) -> list[str]:
    """The game as the tape's answers saw it: each served decision with the state it was asked in,
    its options and its answer, then the game's end.

    Two JVMs playing the same game from the same answers can still write different records, and
    this view leaves those differences out. An effect card's name carries a JVM-wide counter
    ("Static Effect #8552"). Equivalent options can be listed in either order, as can the engine's
    own callbacks inside one step (hash-ordered iteration, the engine's known difference between
    two launches). A search copy can call back into the live game's controller, which records a
    callback the replay lacks (ADR-0133). None of these is a served decision. What is kept must be
    equal: a different state, option set or answer at any served decision is a different game."""
    rets = {r["s"]: r for r in records if r.get("k") == "ret"}
    out = []
    for r in records:
        if r.get("k") == "dec" and "by" in r:
            ret = rets.get(r["s"], {})
            view = {k: v for k, v in r.items() if k not in ("s", "d", "opts", "abil")}
            view["opts"] = sorted(json.dumps(o, sort_keys=True) for o in r.get("opts") or [])
            view["ret"] = ret.get("v")
            out.append(_EFFECT_ID.sub("Static Effect #", json.dumps(view, sort_keys=True)))
        elif r.get("k") in ("game", "end"):
            out.append(json.dumps(r, sort_keys=True))
    return out


def same_decisions(stored: list[dict], replayed: list[dict]) -> tuple[bool, int]:
    """(whether the two games agree at every served decision and at the end, how many were compared)."""
    a, b = decisions(stored), decisions(replayed)
    return a == b, len(a)


def replay_cmd(cmd_txt: str, jar: str | None, tape: Path, out: Path) -> list[str]:
    toks = cmd_txt.split()
    at = toks.index("anvil")
    head = toks[: at + 1]
    if head[0] == "nice":
        head = head[3:]
    if jar:
        head[head.index("-jar") + 1] = jar
    kept: list[str] = []
    keep = True
    for t in toks[at + 1 :]:
        if t.startswith("-") and len(t) > 1 and not t[1].isdigit():
            keep = t[1:] not in DROP
        if keep:
            kept.append(t)
    return [*head, *kept, "-b", f"tape:{tape}", "-results", str(out / "games.jsonl"), "-obs", str(out / "obs.zst"),
            "-labels", str(out / "labels.jsonl")]


def _brief(r: dict) -> dict:
    return {k: (v if len(json.dumps(v)) < 200 else json.dumps(v)[:200] + "…") for k, v in r.items() if k != "obs"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--games", type=int, default=20, help="how many taped games to draw (seeded)")
    ap.add_argument("--indices", type=int, nargs="*", help="replay these game indices instead of a draw")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jar", default=None, help="replay on this jar instead of the run's own")
    ap.add_argument("--keep-going", action="store_true", help="exit 0 even when a game differs")
    ap.add_argument("--compare-only", action="store_true",
                    help="do not run the jar: compare again what an earlier call left in --out")
    a = ap.parse_args()

    # every taped game of the run: index -> (worker dir, idx entry)
    where: dict[int, tuple[Path, dict]] = {}
    for wdir in sorted(a.run_dir.glob("workers/inv-*")):
        idx = wdir / "obs.idx.jsonl"
        if not idx.exists():
            continue
        for line in idx.read_text().splitlines():
            e = json.loads(line)
            where[e["g"]] = (wdir, e)  # a re-issued game: the later worker's frame stands
    stored_rows = {}
    for f in a.run_dir.glob("workers/inv-*/games.jsonl"):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            stored_rows[r["i"]] = r
    if a.indices:
        chosen = list(a.indices)
    else:
        pool = sorted(g for g in where if g in stored_rows)
        chosen = sorted(random.Random(a.seed).sample(pool, min(a.games, len(pool))))

    a.out.mkdir(parents=True, exist_ok=True)
    by_worker: dict[Path, list[int]] = {}
    by_cmd: dict[tuple, Path] = {}
    stored_recs: dict[int, list[dict]] = {}
    tapes: dict[int, tuple[str, list[str], int]] = {}
    untaped = []
    for g in chosen:
        wdir, e = where[g]
        recs = read_frame(wdir / "obs.zst", e)
        tags, lines = split_tape(recs)
        if tags is None:
            untaped.append(g)
            continue
        stored_recs[g] = comparable(recs)
        tapes[g] = (tags, lines, e["seed"])
        # games whose workers ran the same flags replay in one JVM
        key = tuple(replay_cmd((wdir / "cmd.txt").read_text(), a.jar, Path("T"), Path("O")))
        wdir = by_cmd.setdefault(key, wdir)
        by_worker.setdefault(wdir, []).append(g)
    if untaped:
        print(f"no tape in {len(untaped)} games (recorded without -tape): {untaped[:10]}")

    env = dict(os.environ)
    if not env.get("DISPLAY"):
        xauth = sorted(Path("/run/user/1000").glob("xauth_*"))
        if xauth:
            env["DISPLAY"], env["XAUTHORITY"] = ":0", str(xauth[0])
    report = []
    for wdir, games in by_worker.items():
        out = a.out / wdir.name
        out.mkdir(exist_ok=True)
        rc = 0
        if not a.compare_only:
            for stale in ("games.jsonl", "obs.zst", "obs.idx.jsonl"):
                (out / stale).unlink(missing_ok=True)
            tape = out / "tape.tsv"
            with open(tape, "w") as f:
                for g in games:
                    tags, lines, seed = tapes[g]
                    f.write(f"G\t{g}\t{seed}\t{tags}\n")
                    f.writelines(line + "\n" for line in lines)
            cmd = replay_cmd((wdir / "cmd.txt").read_text(), a.jar, tape.resolve(), out.resolve())
            if not env.get("DISPLAY"):
                cmd.insert(cmd.index("-jar"), "-Djava.awt.headless=true")
            (out / "cmd.txt").write_text(" ".join(cmd) + "\n")
            with open(out / "out.log", "w") as log:
                rc = subprocess.run(cmd, cwd=FORGE_GUI_DIR, stdout=log, stderr=subprocess.STDOUT, env=env).returncode
        rows = {}
        if (out / "games.jsonl").exists():
            rows = {r["i"]: r for r in map(json.loads, (out / "games.jsonl").read_text().splitlines())}
        entries = {}
        if (out / "obs.idx.jsonl").exists():
            entries = {e["g"]: e for e in map(json.loads, (out / "obs.idx.jsonl").read_text().splitlines())}
        for g in games:
            row, old = rows.get(g), stored_rows[g]
            item = {"i": g, "worker": wdir.name, "tape": len(tapes[g][1]), "stored": {k: old.get(k) for k in RESULT_KEYS}}
            if row is None or g not in entries:
                item["verdict"] = f"not replayed (worker exit {rc})"
            else:
                # a stored row from an older jar has no "first"; compare the keys both carry
                row_diff = [k for k in RESULT_KEYS if k in old and old.get(k) != row.get(k)]
                diff = first_diff(stored_recs[g], comparable(read_frame(out / "obs.zst", entries[g])))
                item["records"] = len(stored_recs[g])
                item["replayed"] = {k: row.get(k) for k in RESULT_KEYS}
                item["tape_account"] = row.get("tape")
                item["row_diff"], item["first_diff"] = row_diff, diff
                item["verdict"] = "identical" if not row_diff and diff is None else "differs"
                if diff is not None and not row_diff:
                    ok, n_dec = same_decisions(stored_recs[g], comparable(read_frame(out / "obs.zst", entries[g])))
                    if ok:
                        item["verdict"], item["decisions"] = "same game", n_dec
            report.append(item)
            line = f"game {g}: {item['verdict']}"
            if item["verdict"] == "same game":
                d = item["first_diff"]
                line += (f" at all {item['decisions']} served decisions and the end; the records first differ at "
                         f"{d['pos']} of {d['of']} ({', '.join(d['keys'])})")
            elif item.get("first_diff"):
                d = item["first_diff"]
                line += f" at record {d['pos']} of {d['of']} ({', '.join(d['keys'])})"
            if item.get("tape_account") and item["tape_account"].get("diverged"):
                line += f"; tape {item['tape_account']['diverged']}"
            print(line, flush=True)

    same = sum(r["verdict"] == "identical" for r in report)
    near = sum(r["verdict"] == "same game" for r in report)
    summary = {"run": str(a.run_dir), "jar": a.jar, "games": len(report), "identical": same, "same_game": near,
               "untaped": untaped, "items": report}
    (a.out / "replay-report.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(f"{same} of {len(report)} games replayed identically"
          + (f", {near} more as the same game at every served decision" if near else "")
          + f"; report: {a.out / 'replay-report.json'}")
    if same + near != len(report) and not a.keep_going:
        sys.exit(1)


if __name__ == "__main__":
    main()
