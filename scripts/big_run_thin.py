"""Thin the closed big run's data (a utility for the M12 stale-data pass, ADR-0126 decision 5).

Two deletions, both under data/ of this checkout:

1. The raw `workers/` output of the in-loop arm reads (`data/runs/big-run-arm-*`,
   `big-run-armla-*`). The per-game files beside it stay: games.jsonl, summary.json,
   run.json, pairs.txt. A directory missing any of the first three is skipped.
2. The per-iteration weights `data/training/big-run/iter-NNN/train/last.pt`, except
   the kept iterations: the segment closes, the iterations the records cite by path,
   every 25th, and the last four. Everything else in an iteration directory stays
   (mu.jsonl, metrics, configs, the state-ranking read). `iter-301-rechead` is untouched.

Without --go it prints what it would delete and deletes nothing.

    uv run python scripts/big_run_thin.py          # dry run
    uv run python scripts/big_run_thin.py --go
"""
import json
import os
import re
import shutil
import sys

GO = '--go' in sys.argv
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
SEGMENT_CLOSES = {99, 202, 301, 405, 513}
CITED = {238, 259, 289, 291}
KEEP = SEGMENT_CLOSES | CITED | {510, 511, 512} | set(range(0, 514, 25))
ARM_DIR = re.compile(r'^big-run-arm(la)?-i\d{3}-s[01]-\d{8}-\d{6}$')
PER_GAME = ('games.jsonl', 'summary.json', 'run.json')


def tree_bytes(path: str) -> int:
    total = 0
    for d, _, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(d, f)).st_size
            except OSError:
                pass
    return total


def thin_arm_reads() -> None:
    runs = os.path.join(ROOT, 'runs')
    total = n = 0
    skipped = []
    for name in sorted(os.listdir(runs)):
        if not ARM_DIR.match(name):
            continue
        base = os.path.join(runs, name)
        workers = os.path.join(base, 'workers')
        if not os.path.isdir(workers) or os.path.islink(workers):
            continue
        if not all(os.path.isfile(os.path.join(base, f)) and os.path.getsize(os.path.join(base, f)) > 0
                   for f in PER_GAME):
            skipped.append(name)
            continue
        total += tree_bytes(workers)
        n += 1
        if GO:
            shutil.rmtree(workers)
    print(f'arm reads: {n} workers/ dirs, {total / 2**30:.1f} GiB; skipped for missing per-game files: {skipped}')


def thin_weights() -> None:
    run = os.path.join(ROOT, 'training', 'big-run')
    state = json.load(open(os.path.join(run, 'loop_state.json')))
    resume = re.search(r'iter-(\d{3})/', state['ckpt'])
    assert resume and int(resume.group(1)) in KEEP, f"the loop's resume checkpoint is not kept: {state['ckpt']}"
    total = n = 0
    kept = []
    for name in sorted(os.listdir(run)):
        m = re.match(r'^iter-(\d{3})$', name)
        if not m:
            continue
        i = int(m.group(1))
        for sub in ('train', 'train.rejected-1'):
            path = os.path.join(run, name, sub, 'last.pt')
            if not os.path.isfile(path) or os.path.islink(path):
                continue
            if i in KEEP and sub == 'train':
                kept.append(i)
                continue
            total += os.path.getsize(path)
            n += 1
            if GO:
                os.remove(path)
    print(f'weights: {n} last.pt files, {total / 2**30:.1f} GiB; kept {len(kept)}: {kept}')


if __name__ == '__main__':
    assert os.path.isdir(os.path.join(ROOT, 'training', 'big-run')), ROOT
    print('DELETING' if GO else 'dry run (pass --go to delete)')
    thin_arm_reads()
    thin_weights()
