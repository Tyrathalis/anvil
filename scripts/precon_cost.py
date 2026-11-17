"""Price heuristic-only Commander precon games on a stock Forge jar (ADR-0126, the benchmark addendum; a utility).

Plays pods of precon decks with Forge's own `sim` mode, every seat the stock AI, no bridge and
no GPU, and reads each game's wall time, turn count and play counts from the game log. It is
the cost side of the two-player and four-player benchmark tracks: how long a game is and how
much happens in it. The same pod draw serves every cell, so a two-player cell plays the first
two decks of each four-player pod.

Each pod is one JVM under an isolated `user.home`, so the user's Forge profile and deck store
are neither read nor written. A JVM's first game carries its warm-up; the report gives the
figures with and without first games.

    uv run python scripts/precon_cost.py --players 4 --pods 24 --games 5 --out <dir>/p4-off
    uv run python scripts/precon_cost.py --players 4 --mc max --pods 12 --games 3 --out <dir>/p4-max
"""
import argparse
import json
import os
import random
import re
import statistics
import subprocess
from concurrent.futures import ThreadPoolExecutor

FORGE = os.path.expanduser('~/Everything/Projects/forge-upstream')


def run_pod(a, i: int, decks: list[str]) -> str:
    out = os.path.join(a.out, f'pod-{i:03d}.log')
    if os.path.isfile(out) and 'Match Result' in open(out, errors='replace').read():
        return out
    home = os.path.join(a.out, 'home')
    os.makedirs(home, exist_ok=True)
    cmd = ['java', '-Xmx4g', f'-Duser.home={home}', '-Djava.awt.headless=true', '-jar', a.jar, 'sim',
           '-D', a.decks, '-d', *decks, '-f', 'Commander', '-n', str(a.games), '-c', str(a.clock),
           '-s', str(a.seed + i)]
    if a.mc != 'off':
        cmd += ['-mc', a.mc]
    with open(out, 'w') as f:
        subprocess.run(cmd, cwd=os.path.join(FORGE, 'forge-gui'), stdout=f, stderr=subprocess.STDOUT, check=False)
    return out


def parse(path: str, pod: int) -> list[dict]:
    games, lines = [], []
    for line in open(path, errors='replace'):
        lines.append(line)
        m = re.match(r'Game Result: Game (\d+) ended in (?:a Draw! Took )?(\d+) ms', line)
        if not m:
            continue
        heads = [x.split(':', 1)[0] for x in lines]
        turn = [int(t.group(1)) for x in lines if (t := re.match(r'Game Outcome: Turn (\d+)', x))]
        games.append({
            'pod': pod, 'game': int(m.group(1)), 'ms': int(m.group(2)), 'draw': 'Draw' in line,
            'timeout': any('Stopping slow match' in x for x in lines),
            'turns': turn[-1] if turn else None,
            'stack': heads.count('Add To Stack'), 'lands': heads.count('Land'),
            'combats': heads.count('Combat'), 'log_lines': len(lines),
        })
        lines = []
    return games


def stats(xs: list[float]) -> dict:
    xs = sorted(xs)
    if not xs:
        return {}
    return {'n': len(xs), 'median': statistics.median(xs), 'mean': statistics.fmean(xs),
            'p90': xs[int(0.9 * (len(xs) - 1))], 'max': xs[-1]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--players', type=int, default=4)
    ap.add_argument('--mc', default='off', choices=['off', 'on', 'max'], help='Flat Monte Carlo for every seat')
    ap.add_argument('--pods', type=int, default=24)
    ap.add_argument('--games', type=int, default=5, help='games per pod')
    ap.add_argument('--parallel', type=int, default=6, help='JVMs at once; keep the box under-loaded')
    ap.add_argument('--clock', type=int, default=3600, help='seconds before Forge calls a game a draw')
    ap.add_argument('--seed', type=int, default=20261117)
    ap.add_argument('--jar', default=os.path.join(
        FORGE, 'forge-gui-desktop/target/forge-gui-desktop-2.0.16-SNAPSHOT-jar-with-dependencies.jar'))
    ap.add_argument('--decks', default=os.path.join(FORGE, 'forge-gui/res/quest/commanderprecons'))
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    names = sorted(x for x in os.listdir(a.decks) if x.endswith('.dck'))
    rng = random.Random(a.seed)
    pods = [rng.sample(names, 4)[:a.players] for _ in range(a.pods)]
    with ThreadPoolExecutor(a.parallel) as ex:
        logs = list(ex.map(lambda t: run_pod(a, *t), enumerate(pods)))
    games = [g for i, path in enumerate(logs) for g in parse(path, i)]
    warm = [g for g in games if g['game'] > 1]
    report = {
        'players': a.players, 'mc': a.mc, 'pods': a.pods, 'games_per_pod': a.games, 'parallel': a.parallel,
        'seed': a.seed, 'jar': a.jar, 'played': len(games), 'expected': a.pods * a.games,
        'draws': sum(g['draw'] for g in games), 'timeouts': sum(g['timeout'] for g in games),
        'seconds': stats([g['ms'] / 1000 for g in games]),
        'seconds_after_first': stats([g['ms'] / 1000 for g in warm]),
        'turns': stats([g['turns'] for g in games if g['turns']]),
        'stack_adds': stats([g['stack'] for g in games]),
        'lands': stats([g['lands'] for g in games]),
        'combats': stats([g['combats'] for g in games]),
        'seconds_per_turn_after_first': stats([g['ms'] / 1000 / g['turns'] for g in warm if g['turns']]),
        'mc_summary': [x.rstrip() for path in logs for x in open(path, errors='replace')
                       if 'FlatMonteCarlo' in x or 'Flat MC' in x][:40],
    }
    json.dump({'report': report, 'games': games, 'pods': pods}, open(os.path.join(a.out, 'report.json'), 'w'), indent=1)
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
