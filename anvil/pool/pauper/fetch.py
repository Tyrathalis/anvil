"""Acquisition layer: mtgtop8 (f=PAU = Pauper) and the Wizards Pauper banlist.

Raw artifacts only — no interpretation here. Every deck lands as
raw/decks/<id>.txt (MTGO export, real deck+sideboard split — unlike DC,
Pauper has no command zone) plus <id>.json sidecar (source URL, event, fetch
date). Deck ids already on disk are never re-fetched; politeness is a hard
>=2s gap between requests on a single connectionless client (shared policy
with anvil.pool.dc.fetch, kept as a separate copy per module independence).
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import time
import urllib.error
import urllib.request

from anvil.pool import pool_dir

RAW_DIR = pool_dir("pauper") / "raw"
RAW_DECKS_DIR = RAW_DIR / "decks"

MTGTOP8 = "https://mtgtop8.com"
FORMAT_URL = f"{MTGTOP8}/format?f=PAU"
BANLIST_URL = "https://magic.wizards.com/en/banned-restricted-list"
REQUEST_GAP_S = 2.0

_last_request = 0.0


def _get(url: str, retries: int = 3) -> str:
    global _last_request
    for attempt in range(retries):
        wait = _last_request + REQUEST_GAP_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (anvil pool pipeline; non-commercial research)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
            _last_request = time.monotonic()
            return body
        except (TimeoutError, urllib.error.URLError):
            _last_request = time.monotonic()
            if attempt == retries - 1:
                raise
            time.sleep(REQUEST_GAP_S * 2**attempt)
    raise RuntimeError("unreachable")  # pragma: no cover


def _today() -> str:
    return _dt.datetime.now(_dt.UTC).date().isoformat()


# --- mtgtop8 ---


def _event_ids(format_html: str) -> list[int]:
    return sorted({int(e) for e in re.findall(r"event\?e=(\d+)&f=PAU", format_html)}, reverse=True)


def _event_meta(event_html: str) -> dict:
    title = re.search(r"<title>([^<]*)</title>", event_html)
    date = re.search(r"\b(\d{2}/\d{2}/\d{2})\b", event_html)
    iso = None
    if date:
        d, m, y = date.group(1).split("/")
        iso = f"20{y}-{m}-{d}"
    return {"title": title.group(1).strip() if title else None, "date": iso}


def _deck_ids(event_html: str, event_id: int) -> list[int]:
    return sorted({int(d) for d in re.findall(rf"e={event_id}&d=(\d+)", event_html)})


def fetch_decks(since: str | None = None, limit_decks: int | None = None) -> dict:
    """Walk format page -> events -> deck exports; skip decks already on disk."""
    RAW_DECKS_DIR.mkdir(parents=True, exist_ok=True)
    stats = {"events": 0, "events_skipped_old": 0, "decks_new": 0, "decks_existing": 0}
    for event_id in _event_ids(_get(FORMAT_URL)):
        event_html = _get(f"{MTGTOP8}/event?e={event_id}&f=PAU")
        meta = _event_meta(event_html)
        if since and meta["date"] and meta["date"] < since:
            stats["events_skipped_old"] += 1
            continue
        stats["events"] += 1
        for deck_id in _deck_ids(event_html, event_id):
            if (RAW_DECKS_DIR / f"{deck_id}.txt").exists():
                stats["decks_existing"] += 1
                continue
            export = _get(f"{MTGTOP8}/mtgo?d={deck_id}")
            (RAW_DECKS_DIR / f"{deck_id}.txt").write_text(export)
            (RAW_DECKS_DIR / f"{deck_id}.json").write_text(
                json.dumps(
                    {
                        "deck_id": deck_id,
                        "source_url": f"{MTGTOP8}/event?e={event_id}&d={deck_id}&f=PAU",
                        "event_id": event_id,
                        "event_title": meta["title"],
                        "event_date": meta["date"],
                        "fetched": _today(),
                    },
                    indent=2,
                )
            )
            stats["decks_new"] += 1
            if limit_decks and stats["decks_new"] >= limit_decks:
                return stats
    return stats


# --- Wizards official Pauper banlist ---


def parse_banlist(html: str) -> list[dict]:
    """<section id="Pauper-banned"> -> flat <li>Name</li> list. One
    informational bullet (the sticker/Attraction announcement pointer) has
    an embedded <a> and no real card name — skipped."""
    m = re.search(r'id="Pauper-banned".*?</section>', html, re.DOTALL)
    if not m:
        raise RuntimeError("Pauper-banned section not found — page layout changed?")
    cards = []
    for item in re.findall(r"<li>(.*?)</li>", m.group(0), re.DOTALL):
        if "<a" in item or "click" in item.lower():
            continue  # informational bullet, not a card name
        name = re.sub(r"<[^>]+>", "", item).strip()
        if name:
            cards.append({"name": name, "kind": "banned", "section": "Pauper Banned Cards"})
    return cards


def fetch_banlist() -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cards = parse_banlist(_get(BANLIST_URL))
    if len(cards) < 20:  # the list runs 30+; a thin parse means the page changed
        raise RuntimeError(
            f"banlist parse looks broken: only {len(cards)} cards — page layout changed?"
        )
    snapshot = {"source_url": BANLIST_URL, "fetched": _today(), "cards": cards}
    path = RAW_DIR / f"banlist-{_today()}.json"
    path.write_text(json.dumps(snapshot, indent=2))
    return {"cards": len(cards), "path": str(path)}


def latest_banlist() -> dict | None:
    snaps = sorted(RAW_DIR.glob("banlist-*.json"))
    return json.loads(snaps[-1].read_text()) if snaps else None
