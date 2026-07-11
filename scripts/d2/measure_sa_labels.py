"""M2 D2 groundwork: SA-label resolvability on the existing corpus.

Measures, over priority cast windows (non-pass, structured opts):
  1. multi-SA mass — chosen host offers >=2 DISTINCT sa strings (the decision
     the host-level pointer cannot express; play-time analogue read 31-36%).
  2. sa-string join outcome at the chosen host:
       unique   — plan.sa matches exactly one of the host's option strings
       dupes    — plan.sa matches >=2 identical option strings (permission-route
                  duplicates; collapsible into ONE candidate, so the label is
                  resolvable at candidate level — the model can't distinguish
                  identical descriptors anyway; the executor keeps first-fit)
       nomatch  — plan.sa matches no option string (the true masked mass)
  3. sa-string vocab size, raw vs normalized (strip decision-time "(X=n)"
     suffixes), plus kind histogram — prices the learned-embedding table.
  4. train-vocab OOV rate on val/valpair-split windows (split is the standing
     pure function of game index) — serve-time OOV proxy.

Usage:
  uv run python scripts/d2/measure_sa_labels.py \
      --store data/trajectories/d3pilot-20260704-175219,data/trajectories/d6ext-20260706-220552 \
      [--sample 8000] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from anvil.store.trajectories import open_store
from anvil.training.dataset import _split_of

PRIORITY = "chooseSpellAbilityToPlay"
_X_SUFFIX = re.compile(r" \(X=\d+\)")


def norm(sa: str) -> str:
    return _X_SUFFIX.sub("", sa)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--sample", type=int, default=None,
                    help="uniform-stride sample of this many games (default: all)")
    ap.add_argument("--json", default=None)
    ap.add_argument("--vocab-out", default=None,
                    help="write the pinned SA-string vocab (normalized, sorted by "
                         "count desc then lexicographic) — the D2 sa_vocab file")
    args = ap.parse_args()

    store = open_store(args.store)
    games = store.game_indices()
    if args.sample and args.sample < len(games):
        stride = len(games) / args.sample
        games = [games[int(i * stride)] for i in range(args.sample)]

    c = Counter()
    vocab_raw: Counter[str] = Counter()
    vocab_norm: Counter[str] = Counter()
    train_vocab: set[str] = set()
    eval_strings: list[tuple[str, str]] = []  # (split, norm sa) for OOV pass
    kind_of: dict[str, str] = {}
    nomatch_examples: list[str] = []

    for gi, g in enumerate(games):
        if gi and gi % 2000 == 0:
            print(f"  ... {gi}/{len(games)} games, windows={c['windows']}")
        try:
            traj = store.game(g)
        except Exception:
            c["undecodable_games"] += 1
            continue
        split = _split_of(g)
        for dec in traj.decisions:
            if dec.get("m") != PRIORITY or dec.get("obs") is None:
                continue
            opts = dec.get("opts")
            if opts is None or (opts and not isinstance(opts[0], dict)):
                continue
            c["windows"] += 1
            for o in opts:
                s = norm(o.get("sa", ""))
                vocab_raw[o.get("sa", "")] += 1
                vocab_norm[s] += 1
                kind_of[s] = o.get("kind", "other")
                if split == "train":
                    train_vocab.add(s)
                else:
                    eval_strings.append((split, s))
            ret = dec.get("ret")
            if ret is None:
                c["pass"] += 1
                continue
            plan = ret[0] if isinstance(ret, list) and ret else None
            if not isinstance(plan, dict):
                c["bad_ret"] += 1
                continue
            c["casts"] += 1
            host = plan.get("e")
            host_opts = [o for o in opts if o.get("e") == host]
            if not host_opts:
                c["host_not_in_opts"] += 1  # ADR-0005 violation; validator's job
                continue
            distinct = {norm(o.get("sa", "")) for o in host_opts}
            if len(distinct) >= 2:
                c["multi_sa_host"] += 1
            psa = norm(plan.get("sa", ""))
            # the planned label algorithm: candidates = DISTINCT (host, sa_norm)
            # keys (identical strings collapse); stage 1 exact match, stage 2
            # prefix-min fallback for the truncation-skew residue; ambiguous
            # or zero-match after both stages -> masked from the SA-level loss
            exact = [s for s in distinct if s == psa]
            if exact:
                outcome = "resolved_exact"
            else:
                pref = [s for s in distinct
                        if min(len(s), len(psa)) > 0
                        and s[:min(len(s), len(psa))] == psa[:min(len(s), len(psa))]]
                if len(pref) == 1:
                    outcome = "resolved_prefix"
                elif len(pref) >= 2:
                    outcome = "masked_prefix_ambiguous"
                else:
                    outcome = "masked_nomatch"
            c[outcome] += 1
            if outcome.startswith("masked") and len(nomatch_examples) < 12:
                nomatch_examples.append(
                    f"g={g} s={dec.get('s')} [{outcome}]\n"
                    f"    plan={plan.get('sa', '')!r}\n"
                    f"    keys={sorted(distinct)!r}")
            if len(distinct) >= 2:
                c[f"multi_{outcome}"] += 1

    oov = Counter()
    for split, s in eval_strings:
        oov[f"{split}_total"] += 1
        if s not in train_vocab:
            oov[f"{split}_oov"] += 1

    print(f"\n=== {len(games)} games sampled, {c['windows']} priority windows "
          f"({c['pass']} pass / {c['casts']} casts) ===")
    print(f"multi-SA hosts among casts: {c['multi_sa_host']} "
          f"({100 * c['multi_sa_host'] / max(c['casts'], 1):.1f}%)")
    n = max(c["casts"], 1)
    for k in ("resolved_exact", "resolved_prefix", "masked_prefix_ambiguous", "masked_nomatch"):
        print(f"  {k}: {c[k]} ({100 * c[k] / n:.2f}%)")
    if c["multi_sa_host"]:
        m = c["multi_sa_host"]
        print("  within multi-SA hosts: "
              + " / ".join(f"{k.removeprefix('multi_')} {100 * c[k] / m:.2f}%"
                           for k in ("multi_resolved_exact", "multi_resolved_prefix",
                                     "multi_masked_prefix_ambiguous", "multi_masked_nomatch")))
    print(f"vocab: raw {len(vocab_raw)} / normalized {len(vocab_norm)} distinct sa strings")
    print("kind histogram (normalized vocab): "
          + json.dumps(Counter(kind_of.values()).most_common()))
    for split in ("val", "valpair"):
        t, o = oov[f"{split}_total"], oov[f"{split}_oov"]
        if t:
            print(f"OOV vs train vocab, {split}: {o}/{t} option mentions "
                  f"({100 * o / t:.2f}%)")
    if c["host_not_in_opts"]:
        print(f"WARNING: {c['host_not_in_opts']} chosen hosts not in opts")
    if nomatch_examples:
        print("\nnomatch examples:")
        for e in nomatch_examples:
            print("  " + e)

    if args.vocab_out:
        ordered = sorted(vocab_norm, key=lambda s: (-vocab_norm[s], s))
        with open(args.vocab_out, "w") as f:
            json.dump({"source": args.store, "games": len(games),
                       "normalization": "strip ' (X=n)' suffixes",
                       "sa_strings": ordered,
                       "counts": {s: vocab_norm[s] for s in ordered}}, f, indent=1)
        print(f"wrote {args.vocab_out} ({len(ordered)} strings)")

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"games": len(games), "counts": dict(c), "oov": dict(oov),
                       "vocab_raw": len(vocab_raw), "vocab_norm": len(vocab_norm),
                       "top_sa": vocab_norm.most_common(30)}, f, indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
