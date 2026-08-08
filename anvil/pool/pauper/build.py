"""Derivation layer: raw decks + banlist + flex -> pool manifest, .dck files,
report. Deterministic: same raw dir -> same output; the manifest content hash
(computed with the hash field absent) is the pool version.

Gates, in order per deck: parse/shape -> name resolution vs the fork's
cardsfolder -> current banlist. Excluded decks are counted and reported,
never silently dropped. No commander/color-identity concept here (unlike
DC) and no independent rarity check — the engine adjudicates at game setup.
"""

from __future__ import annotations

import hashlib
import json

from anvil.pool import forge_db, pool_dir
from anvil.pool.pauper import decklist
from anvil.pool.pauper.decklist import ShapeError, deck_from_export
from anvil.pool.pauper.fetch import latest_banlist

POOL_DIR = pool_dir("pauper")
RAW_DECKS_DIR = POOL_DIR / "raw" / "decks"
DECKS_OUT_DIR = POOL_DIR / "decks"
FLEX_FILE = POOL_DIR / "flex.txt"
OVERRIDES_FILE = POOL_DIR / "overrides.json"


def _load_flex() -> list[str]:
    if not FLEX_FILE.exists():
        return []
    return [
        ln.strip()
        for ln in FLEX_FILE.read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def _load_overrides() -> dict[str, str]:
    return json.loads(OVERRIDES_FILE.read_text()) if OVERRIDES_FILE.exists() else {}


def build() -> dict:
    universe = forge_db.load_names()
    overrides = _load_overrides()
    banlist = latest_banlist()
    if banlist is None:
        raise SystemExit(
            "no banlist snapshot — run `python -m anvil.pool --format pauper banlist` first"
        )
    banned = {forge_db.normalize(c["name"]) for c in banlist["cards"]}

    decks_out, excluded, unresolved_freq = [], [], {}
    pool: dict[str, dict] = {}  # forge name -> {sources, first_seen}

    for path in sorted(RAW_DECKS_DIR.glob("*.txt"), key=lambda p: int(p.stem)):
        deck_id = int(path.stem)
        meta = json.loads(path.with_suffix(".json").read_text())

        def exclude(reason: str, deck_id=deck_id, meta=meta) -> None:
            excluded.append({"deck_id": deck_id, "reason": reason, "url": meta.get("source_url")})

        try:
            deck = deck_from_export(deck_id, path.read_text(), meta)
        except ShapeError as e:
            exclude(f"shape: {e}")
            continue

        all_lines = deck.main + deck.sideboard
        resolved, missing = {}, []
        for _, name in all_lines:
            hit = forge_db.resolve(name, universe, overrides)
            if hit is None:
                missing.append(name)
                unresolved_freq[name] = unresolved_freq.get(name, 0) + 1
            else:
                resolved[name] = hit
        if missing:
            exclude(f"unresolved in Forge: {missing}")
            continue

        hit_banned = sorted(
            {resolved[n] for _, n in all_lines if forge_db.normalize(resolved[n]) in banned}
        )
        if hit_banned:
            exclude(f"banned: {hit_banned}")
            continue

        main = [(c, resolved[n]) for c, n in deck.main]
        side = [(c, resolved[n]) for c, n in deck.sideboard]
        decks_out.append(
            {
                "deck_id": deck_id,
                "file": f"pau-{deck_id}.dck",
                "event_title": meta.get("event_title"),
                "event_date": meta.get("event_date"),
                "source_url": meta.get("source_url"),
            }
        )
        DECKS_OUT_DIR.mkdir(parents=True, exist_ok=True)
        (DECKS_OUT_DIR / f"pau-{deck_id}.dck").write_text(
            decklist.to_dck(f"pau-{deck_id}", main, side)
        )
        for name in {n for _, n in main} | {n for _, n in side}:
            entry = pool.setdefault(name, {"sources": [], "first_seen": None})
            entry["sources"].append(deck_id)
            date = meta.get("event_date")
            if date and (entry["first_seen"] is None or date < entry["first_seen"]):
                entry["first_seen"] = date

    flex_unresolved = []
    for name in _load_flex():
        hit = forge_db.resolve(name, universe, overrides)
        if hit is None:
            flex_unresolved.append(name)
        elif forge_db.normalize(hit) in banned:
            excluded.append({"deck_id": None, "reason": f"flex card banned: {hit}"})
        else:
            pool.setdefault(hit, {"sources": [], "first_seen": None})["sources"].append("flex")

    manifest = {
        "format": "pauper",
        "banlist": {
            "fetched": banlist["fetched"],
            "sha256": hashlib.sha256(json.dumps(banlist, sort_keys=True).encode()).hexdigest(),
        },
        "fork_commit": forge_db.fork_commit(),
        "decks": decks_out,
        "pool": {name: pool[name] for name in sorted(pool)},
        "counts": {
            "decks_included": len(decks_out),
            "decks_excluded": len(excluded),
            "pool_cards": len(pool),
        },
        "excluded": excluded,
    }
    blob = json.dumps(manifest, sort_keys=True).encode()
    pool_hash = hashlib.sha256(blob).hexdigest()
    manifest["pool_version"] = pool_hash[:8]
    out = POOL_DIR / f"pool-{pool_hash[:8]}.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (POOL_DIR / "CURRENT").write_text(pool_hash[:8] + "\n")

    _write_report(manifest, unresolved_freq, flex_unresolved)
    return {
        "manifest": str(out),
        "pool_version": pool_hash[:8],
        **manifest["counts"],
        "unresolved_names": len(unresolved_freq),
    }


def _write_report(
    manifest: dict, unresolved_freq: dict[str, int], flex_unresolved: list[str]
) -> None:
    lines = [f"# Pauper pool build report — version {manifest['pool_version']}", ""]
    c = manifest["counts"]
    lines += [
        f"- decks: {c['decks_included']} included, {c['decks_excluded']} excluded",
        f"- pool: {c['pool_cards']} cards",
        f"- banlist snapshot: {manifest['banlist']['fetched']}",
        f"- fork commit: {manifest['fork_commit'][:12]}",
        "",
    ]
    if unresolved_freq:
        lines += ["## Unresolved names (override/upstream-gap worklist, by frequency)", ""]
        for name, n in sorted(unresolved_freq.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {n}× `{name}`")
        lines.append("")
    if flex_unresolved:
        lines += ["## Unresolved flex cards", ""] + [f"- `{n}`" for n in flex_unresolved] + [""]
    if manifest["excluded"]:
        lines += ["## Excluded decks", ""]
        for e in manifest["excluded"]:
            lines.append(f"- {e['deck_id']}: {e['reason']}")
        lines.append("")
    (POOL_DIR / "report.md").write_text("\n".join(lines))
