"""Fit one rating per checkpoint from head-to-head reports (ADR-0126 decision 3; a utility).

Reads the `*-h2h.json` reports that scripts/h2h_read.py writes and fits a Bradley-Terry
model: P(A beats B) = sigmoid(r_A - r_B), a draw counted as half a win. Ratings are
reported in Elo units relative to the first checkpoint named in --order.

Errors come from a parametric bootstrap: each pair's score is redrawn from a normal with
the report's own standard error (which is taken over game indices, so the two seatings of
one seed count once), and the fit is repeated.

The transitivity check is each pair's observed score against the score the fitted ratings
predict, in units of that pair's standard error. Residuals well beyond 2 mean a single
rating per checkpoint does not describe the results.

    uv run python scripts/ladder_fit.py data/runs/lad-*-h2h.json data/runs/h2h-405-start-h2h.json \
        --out data/runs/ladder/fit
"""
import argparse
import json
import math
import re

import numpy as np

ELO = 400.0 / math.log(10.0)


def label(ckpt: str) -> str:
    """A short name for a checkpoint path: `big-run/iter-405`."""
    m = re.search(r'training/([^/]+/iter-\d+[^/]*)/', ckpt)
    return m.group(1) if m else ckpt


def fit(pairs: list[tuple[int, int, float, float]], n: int, iters: int = 200) -> np.ndarray:
    """Maximum-likelihood ratings by Newton steps, rating 0 pinned to zero.

    pairs holds (a, b, a_score, weight); weight is the pair's effective game count.
    """
    r = np.zeros(n)
    for _ in range(iters):
        grad = np.zeros(n)
        hess = np.zeros((n, n))
        for a, b, s, w in pairs:
            p = 1.0 / (1.0 + math.exp(-(r[a] - r[b])))
            g = w * (s - p)
            h = w * p * (1.0 - p)
            grad[a] += g
            grad[b] -= g
            hess[a, a] += h
            hess[b, b] += h
            hess[a, b] -= h
            hess[b, a] -= h
        step = np.linalg.solve(hess[1:, 1:] + 1e-9 * np.eye(n - 1), grad[1:])
        r[1:] += step
        if np.abs(step).max() < 1e-10:
            break
    return r


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('reports', nargs='+', help='h2h report files')
    ap.add_argument('--order', nargs='*', default=[],
                    help='checkpoint labels in display order; the first is the zero of the scale')
    ap.add_argument('--boot', type=int, default=2000, help='bootstrap draws')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', help='write <out>.json and <out>.md')
    a = ap.parse_args()

    rows = []
    for path in a.reports:
        rep = json.load(open(path))
        rows.append((label(rep['a']), label(rep['b']), rep['a_score'], rep['se'], rep['indices'], path))
    names = list(a.order)
    for la, lb, *_ in rows:
        for x in (lb, la):
            if x not in names:
                names.append(x)
    idx = {x: i for i, x in enumerate(names)}
    # weight = the game count a binomial would need to give the report's SE
    pairs = [(idx[la], idx[lb], s, s * (1 - s) / se ** 2) for la, lb, s, se, _, _ in rows]
    r = fit(pairs, len(names))

    rng = np.random.default_rng(a.seed)
    draws = np.empty((a.boot, len(names)))
    for k in range(a.boot):
        redrawn = [(i, j, float(np.clip(rng.normal(s, se), 0.01, 0.99)), w)
                   for (i, j, s, w), (_, _, _, se, _, _) in zip(pairs, rows)]
        draws[k] = fit(redrawn, len(names))
    sd = draws.std(axis=0)

    ratings = [{'ckpt': x, 'elo': ELO * r[i], 'se': ELO * sd[i]} for x, i in idx.items()]
    checks = []
    for (la, lb, s, se, n_idx, path) in rows:
        pred = 1.0 / (1.0 + math.exp(-(r[idx[la]] - r[idx[lb]])))
        checks.append({'a': la, 'b': lb, 'score': s, 'se': se, 'indices': n_idx,
                       'predicted': pred, 'residual_se': (s - pred) / se, 'report': path})

    md = ['| Checkpoint | Elo | ± |', '|---|---|---|']
    md += [f"| `{x['ckpt']}` | {x['elo']:+.1f} | {x['se']:.1f} |" for x in ratings]
    md += ['', '| A | B | A score | ± | fitted | residual (SE) |', '|---|---|---|---|---|---|']
    md += [f"| `{c['a']}` | `{c['b']}` | {c['score']:.4f} | {c['se']:.4f} | {c['predicted']:.4f} | "
           f"{c['residual_se']:+.2f} |" for c in checks]
    text = '\n'.join(md)
    print(text)
    if a.out:
        json.dump({'ratings': ratings, 'pairs': checks, 'boot': a.boot}, open(a.out + '.json', 'w'), indent=1)
        open(a.out + '.md', 'w').write(text + '\n')


if __name__ == '__main__':
    main()
