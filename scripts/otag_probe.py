"""Oracle-tag functional-feature probe (M6 exploratory, 2026-08-08).

Three steps, all cheap (no GPU — safe alongside a running campaign):

  fetch     one official Scryfall search per candidate oracle tag
            (`otag:<name>`), intersected with the ACTIVE pool; unknown
            tags recorded and skipped. -> otags.json (tag -> pool names)
  features  functional-group counts at the 6,117 frozen-benchmark
            positions (anvil/encoder/otag_features.py; same turn-join
            convention as every probe) -> otag-features.npz
  probe     delegate to feature_probe.py probe --features-npz — identical
            split/CV/ridge, per-family attribution, gate vs the 0.455
            plateau (run it directly; this script stops at features)

Usage:
  uv run python scripts/otag_probe.py fetch --out data/runs/otag-probe-v1
  uv run python scripts/otag_probe.py features --out data/runs/otag-probe-v1
  uv run python scripts/feature_probe.py probe \
      --out data/runs/frozen-probe-ext2-c2 \
      --features-npz data/runs/otag-probe-v1/otag-features.npz \
      --report otag-probe-report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frozen_probe as fp

from anvil.encoder.otag_features import (
    FAMILY_OF,
    FEATURE_NAMES,
    GROUPS,
    OTAG_VERSION,
    otag_features,
)
from anvil.pool import current_manifest

DATASET = "data/runs/frozen-probe-ext2-c2/dataset.jsonl"
API = "https://api.scryfall.com/cards/search"
UA = {"User-Agent": "anvil-research/0.1 (non-commercial; otag probe)", "Accept": "application/json"}


def _search_tag(tag: str) -> list[str] | None:
    """All card names with otag:<tag> (paginated); None if the tag is
    unknown to Scryfall (404)."""
    names: list[str] = []
    url = f"{API}?q={urllib.parse.quote(f'otag:{tag} legal:duel')}&unique=cards"
    while url:
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                page = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None if not names else names
            raise
        names += [c["name"] for c in page.get("data", [])]
        url = page.get("next_page")
        time.sleep(0.15)  # Scryfall rate-limit courtesy
    return names


def fetch(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = current_manifest()
    pool = set(manifest["pool"])
    # obs names are canonical pool names; Scryfall multi-face names are
    # "A // B" — index pool by front face too
    front = {n.split(" // ")[0]: n for n in pool}
    tag_names: dict[str, list[str]] = {}
    unknown, hits = [], {}
    for group, tags in GROUPS.items():
        for tag in tags:
            names = _search_tag(tag)
            if names is None:
                unknown.append(tag)
                print(f"[fetch] {group}/{tag}: UNKNOWN tag, skipped", flush=True)
                continue
            in_pool = sorted({front.get(n.split(" // ")[0], n) for n in names} & pool)
            tag_names[tag] = in_pool
            hits[tag] = {"scryfall": len(names), "pool": len(in_pool)}
            print(f"[fetch] {group}/{tag}: {len(names)} cards, {len(in_pool)} in pool", flush=True)
    doc = {
        "pool_version": manifest.get("version"),
        "otag_version": OTAG_VERSION,
        "unknown_tags": unknown,
        "hits": hits,
        "tags": tag_names,
    }
    (out_dir / "otags.json").write_text(json.dumps(doc, indent=1) + "\n")
    covered = len({n for ns in tag_names.values() for n in ns})
    print(
        f"[fetch] {len(tag_names)} tags resolved ({len(unknown)} unknown), "
        f"{covered}/{len(pool)} pool cards carry >=1 tag -> otags.json"
    )


def groups_of_map(otags_path: Path) -> dict[str, frozenset[str]]:
    doc = json.loads(otags_path.read_text())
    out: dict[str, set[str]] = defaultdict(set)
    for group, tags in GROUPS.items():
        for tag in tags:
            for name in doc["tags"].get(tag, []):
                out[name].add(group)
    return {n: frozenset(gs) for n, gs in out.items()}


def features(args: argparse.Namespace) -> None:
    from anvil.store.trajectories import TrajectoryStore

    out_dir = Path(args.out)
    groups_of = groups_of_map(out_dir / "otags.json")
    rows = fp.load_rows(args.dataset)
    positions = sorted({(r["store"], r["g"], r["t"]) for r in rows})
    by_store: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for store, g, t in positions:
        by_store[store].append((g, t))
    print(f"[ofeat] {len(positions)} positions; tag table covers {len(groups_of)} pool cards")

    t0 = time.time()
    keys, feats, missed = [], [], []
    for store, wants in sorted(by_store.items()):
        ts = TrajectoryStore(Path("data/trajectories") / store)
        seat = fp._seat_of(store)
        for g in sorted({g for g, _ in wants}):
            traj = ts.game(g)
            first_of_turn: dict[int, int] = {}
            seen_turn = -1
            for i, dec in enumerate(traj.decisions):
                obs = dec.get("obs")
                if obs is None:
                    continue
                turn = obs["glob"].get("turn", 0)
                if turn < 1 or turn == seen_turn:
                    continue
                seen_turn = turn
                first_of_turn[turn] = i
            for g2, t in wants:
                if g2 != g:
                    continue
                i = first_of_turn.get(t)
                if i is None:
                    missed.append((store, g, t))
                    continue
                keys.append(f"{store}:{g}:{t}")
                feats.append(otag_features(traj.decisions[i], traj.header, seat, groups_of))
    if missed:
        raise SystemExit(
            f"[ofeat] {len(missed)} positions missed the turn "
            "join — convention drift, refusing partial dump"
        )
    arr = np.stack(feats)
    np.savez_compressed(
        out_dir / "otag-features.npz",
        keys=np.array(keys),
        feats=arr,
        feature_names=np.array(FEATURE_NAMES),
        family=np.array([FAMILY_OF[n] for n in FEATURE_NAMES]),
    )
    nz = {n: round(float((arr[:, j] > 0).mean()), 3) for j, n in enumerate(FEATURE_NAMES)}
    meta = {
        "otag_version": OTAG_VERSION,
        "n_positions": len(keys),
        "nonzero_frac": nz,
        "per_feature_std": {n: round(float(s), 3) for n, s in zip(FEATURE_NAMES, arr.std(0))},
    }
    (out_dir / "otag-features-meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    dead = [n for n, s in zip(FEATURE_NAMES, arr.std(0)) if s == 0]
    print(
        f"[ofeat] {len(keys)} x {len(FEATURE_NAMES)} in "
        f"{time.time() - t0:.0f}s -> otag-features.npz"
        + (f"; dead features: {dead}" if dead else "")
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("fetch", fetch), ("features", features)):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        p.add_argument("--dataset", default=DATASET)
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
