"""Acquisition layer: mtgtop8 (f=EDH = Duel Commander) and the DC banlist.

Raw artifacts only — no interpretation here. Every deck lands as
raw/decks/<id>.txt (MTGO export, commander in the Sideboard section by DC
convention) plus <id>.json sidecar (source URL, event, fetch date). Deck ids
already on disk are never re-fetched; politeness is a hard >=2s gap between
requests on a single connectionless client.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import time
import urllib.request

from anvil.pool import RAW_DIR, RAW_DECKS_DIR

MTGTOP8 = "https://mtgtop8.com"
FORMAT_URL = f"{MTGTOP8}/format?f=EDH"
BANLIST_URL = "https://www.duelcommander.com/banlist/"
REQUEST_GAP_S = 2.0

_last_request = 0.0


def _get(url: str) -> str:
    global _last_request
    wait = _last_request + REQUEST_GAP_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (anvil pool pipeline; non-commercial research)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        # mtgtop8 declares iso-8859-1; trust the header, don't assume utf-8
        body = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
    _last_request = time.monotonic()
    return body


def _today() -> str:
    return _dt.date.today().isoformat()


# --- mtgtop8 ---

def _event_ids(format_html: str) -> list[int]:
    return sorted({int(e) for e in re.findall(r"event\?e=(\d+)&f=EDH", format_html)}, reverse=True)


def _event_meta(event_html: str) -> dict:
    title = re.search(r"<title>([^<]*)</title>", event_html)
    # event pages carry a dd/mm/yy date near the event name
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
        event_html = _get(f"{MTGTOP8}/event?e={event_id}&f=EDH")
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
            (RAW_DECKS_DIR / f"{deck_id}.json").write_text(json.dumps({
                "deck_id": deck_id,
                "source_url": f"{MTGTOP8}/event?e={event_id}&d={deck_id}&f=EDH",
                "event_id": event_id, "event_title": meta["title"],
                "event_date": meta["date"], "fetched": _today(),
            }, indent=2))
            stats["decks_new"] += 1
            if limit_decks and stats["decks_new"] >= limit_decks:
                return stats
    return stats


# --- duelcommander.com banlist ---

# page sections -> pool semantics; sections not listed are informational
SECTION_KIND = {
    "Banned in Deck": "banned",
    "Banned for Offensive Content": "banned",
    "Banned as Commander only": "banned_commander",
    "Banned as Companion": "banned_companion",
}


def parse_banlist(html: str) -> list[dict]:
    """data-card-name attrs attributed to the nearest preceding header."""
    events: list[tuple[int, str, str]] = []
    for m in re.finditer(r"<h([1-4])[^>]*>(.*?)</h\1>", html, re.S):
        header = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        header = re.sub(r"^[^A-Za-z]+", "", header)  # strip emoji prefixes
        events.append((m.start(), "header", header))
    for m in re.finditer(r'data-card-name="([^"]+)"', html):
        events.append((m.start(), "card", m.group(1)))
    events.sort()
    section, out = None, []
    for _, kind, value in events:
        if kind == "header":
            section = value
        elif section in SECTION_KIND and "${" not in value:  # skip JS template refs
            out.append({"name": value, "kind": SECTION_KIND[section], "section": section})
    return out


def fetch_banlist() -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cards = parse_banlist(_get(BANLIST_URL))
    if len(cards) < 50:  # the list is ~100+; a thin parse means the page changed
        raise RuntimeError(f"banlist parse looks broken: only {len(cards)} cards — page layout changed?")
    snapshot = {"source_url": BANLIST_URL, "fetched": _today(), "cards": cards}
    path = RAW_DIR / f"banlist-{_today()}.json"
    path.write_text(json.dumps(snapshot, indent=2))
    return {"cards": len(cards), "path": str(path)}


def latest_banlist() -> dict | None:
    snaps = sorted(RAW_DIR.glob("banlist-*.json"))
    return json.loads(snaps[-1].read_text()) if snaps else None
