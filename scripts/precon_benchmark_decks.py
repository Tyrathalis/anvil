"""Build the Commander precon benchmark's deck list (M13 pin 6; ADR-0130, addendum).

The list is every paper Commander precon: the fork's packaged files
(forge-gui/res/quest/commanderprecons), less the Commander Anthology reprints (set codes CMA and
CM2, card-for-card copies of earlier decks), plus the decks in scripts/precon_extra/ that Forge
does not package. Each deck is written as pc-NNN.dck in release order, with a map that names it and
gives its share of non-basic cards outside a pool.

    uv run python scripts/precon_benchmark_decks.py --out data/benchmark/precons-178 \
        --install ~/.forge/decks/commander/anvil-precons-178
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
REPRINT_SETS = {"CMA", "CM2"}


def cards(path: Path) -> tuple[list[str], list[str]]:
    """(commander names, main-deck names) of a deck file; foil marks and printings dropped."""
    out: dict[str, list[str]] = {}
    sec = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("["):
            sec = line.strip("[]").lower()
        elif sec in ("commander", "main") and (m := re.match(r"(\d+)\s+(.*)", line)):
            out.setdefault(sec, []).append(m.group(2).split("|")[0].rstrip("+").strip())
    return out.get("commander", []), out.get("main", [])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--forge", default=str(REPO.parent / "forge"))
    ap.add_argument("--pool-names", default=str(REPO / "data/embeddings/cf2ca6ba-qwen3.json"),
                    help="a card table's json; its names are the pool the unseen share is measured against")
    ap.add_argument("--out", required=True)
    ap.add_argument("--install", help="also copy the pc-NNN.dck files to this deck-store folder")
    a = ap.parse_args()

    meta = json.loads(Path(a.pool_names).read_text())
    pool = set(meta["names"][: meta.get("base_count", len(meta["names"]))])
    files = sorted(Path(a.forge, "forge-gui/res/quest/commanderprecons").glob("*.dck")) + sorted((REPO / "scripts/precon_extra").glob("*.dck"))
    decks = []
    for f in files:
        m = re.match(r"(.*) \[(\w+)\] \[(\d{4})\]$", f.stem.strip())
        assert m, f.name
        if m.group(2) in REPRINT_SETS:
            continue
        decks.append((int(m.group(3)), f.stem.strip(), f))
    decks.sort()
    assert len({n for _, n, _ in decks}) == len(decks)

    out = Path(a.out)
    (out / "decks").mkdir(parents=True, exist_ok=True)
    dmap, names = {}, set()
    for i, (year, name, f) in enumerate(decks):
        cmd, main_ = cards(f)
        uniq = sorted({c for c in cmd + main_ if c not in BASICS})
        names |= set(uniq)
        unseen = [c for c in uniq if c not in pool and c.split(" // ")[0] not in pool]
        key = f"pc-{i:03d}.dck"
        shutil.copyfile(f, out / "decks" / key)
        dmap[key] = {"name": name, "year": year, "uniq": len(uniq), "unseen": len(unseen),
                     "share": len(unseen) / len(uniq), "commander_seen": all(c in pool for c in cmd)}
    (out / "deck-map.json").write_text(json.dumps(dmap, indent=1) + "\n")
    (out / "names.txt").write_text("\n".join(sorted(names)) + "\n")
    if a.install:
        dst = Path(a.install).expanduser()
        dst.mkdir(parents=True, exist_ok=True)
        for f in (out / "decks").glob("pc-*.dck"):
            shutil.copyfile(f, dst / f.name)
    sh = [d["share"] for d in dmap.values()]
    print(f"[precons] {len(dmap)} decks, {len(names)} unique non-basic cards, {len(names & pool)} in the pool; "
          f"unseen share median {st.median(sh):.1%}, {min(sh):.1%} to {max(sh):.1%}; "
          f"commanders in the pool: {sum(d['commander_seen'] for d in dmap.values())}")
    by: dict[int, int] = {}
    for d in dmap.values():
        by[d["year"]] = by.get(d["year"], 0) + 1
    print("[precons] decks by year: " + ", ".join(f"{y}: {n}" for y, n in sorted(by.items())))


if __name__ == "__main__":
    main()
