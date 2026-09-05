"""M9 D1 — veto knowability decomposition (m9-plan.md D1, pinned 2026-08-19).

Question: of the vetoes the current policy eats, what fraction are
knowable-from-public — the acting seat's OWN observation carried enough
information to know the cast was unaffordable/illegal — vs
hidden-info-plausible? This is (a) the baseline the D4/D5 veto-collapse
mechanism check is measured against and (b) the premise check on the
interface theory (ADR-0062: probing-via-veto is optimal play only if
the vetoes are about things the model could in principle know).

Method (pinned at the D1 session): join census veto records to the raw
obs stream at (g, s) — census carries the veto + reason + pick, the obs
dec record carries the exact observation the model saw — and compute
affordability from that observation alone: untapped battlefield sources
(`tap` flag) resolved through a card table parsed from the fork's card
scripts (ManaCost + `A:AB$ Mana ... Produced$`, basic-land subtypes,
tokenscripts), commander tax from `cmdcast`. OPTIMISTIC arithmetic by
design: phyrexian pips payable via life, Combo/Any/ColorIdentity treated
as any color. v2 (ADR-0063 addendum) is sick-aware: `sick` IS in the obs
schema, so tap-production on summoning-sick hosts is excluded from the
usable view and payable-only-with-sick-sources is KNOWABLE
(`sickness_short`); spend-restricted / board-cost production
(RestrictValid, tapXType) is a separate conditional view resolving to
`uncertain`. Optimism only strengthens "unaffordable" verdicts, so
`knowable` classifications are conservative and disagreements
("obs says payable, engine vetoed") land OUTSIDE the knowable numerator.
Windows the arithmetic cannot settle (unparsed costs, chained
mana-costed activations available, unknown battlefield names, snow) go
to an explicit `uncertain` bucket — in the gate denominator, never the
numerator.

Gate basis (pinned): FIRST-ATTEMPT vetoes (census `reask` absent — the
chain-independent M3 rule), mana-relevant reasons only (`unpayable` +
`timing`). Gate: knowable fraction >= 0.50 => premise stands. The
all-reasons decomposition and the all-attempt basis are reported as
secondary tables.

Instrument validity bar (pinned): the same arithmetic must call >= 95%
of engine-ACCEPTED first-attempt casts affordable (accepted casts are
free engine-adjudicated ground truth; the miss rate bounds systematic
classifier error, chiefly cost-reduction statics and card-table gaps).

Usage:
  uv run python scripts/veto_knowability.py classify \
      --pop sampled=data/runs/d6-run17-i000-20260818-101603,data/runs/d6-run17-i000h0-20260818-102516,data/runs/d6-run17-i000h1-20260818-102923 \
      --pop argmax=data/runs/d3-rebaselinearm-s0-20260811-222754,data/runs/d3-rebaselinearm-s1-20260811-225502 \
      --out data/runs/veto-knowability-m9d1
  uv run python scripts/veto_knowability.py report --out data/runs/veto-knowability-m9d1
"""

from __future__ import annotations

import argparse
import io
import json
import math
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import zstandard

ROOT = Path(__file__).resolve().parent.parent
CARDSFOLDER = ROOT.parent / "forge" / "forge-gui" / "res" / "cardsfolder"
TOKENSCRIPTS = ROOT.parent / "forge" / "forge-gui" / "res" / "tokenscripts"

MANA_RELEVANT = {"unpayable", "timing"}
COLORS = frozenset("WUBRG")
ANY_COLOR = frozenset("WUBRGC")
BASIC_PROD = {
    "Plains": "W",
    "Island": "U",
    "Swamp": "B",
    "Mountain": "R",
    "Forest": "G",
    "Wastes": "C",
}
# Activation-cost words that don't require mana (payable-from-public).
NONMANA_COST = re.compile(
    r"^(T|Q|Sac<[^>]*>|Discard<[^>]*>|PayLife<[^>]*>|ExileFromHand<[^>]*>|"
    r"Mill<[^>]*>|SubCounter<[^>]*>|AddCounter<[^>]*>|Return<[^>]*>|"
    r"Reveal<[^>]*>|tapXType<[^>]*>|Untap)$"
)


# ---------------------------------------------------------------- mana costs


@dataclass
class Cost:
    generic: int = 0
    pips: list = field(default_factory=list)  # list[frozenset] — any member pays
    twobrid: int = 0  # count of "2/C" pips already folded into pips as color-or-2
    twobrid_colors: list = field(default_factory=list)
    phyrexian: int = 0  # pips payable with 2 life each (optimistic: free)
    x: int = 0
    snow: int = 0
    uncertain: str | None = None


def parse_mana_cost(s: str) -> Cost:
    """Forge ManaCost grammar: space-separated tokens — int (generic), single
    letters WUBRGCS, X, two-letter hybrids "BG", two-brid "2R", phyrexian "BP",
    hybrid-phyrexian "GUP", colorless-hybrid "CW". "no cost" => uncastable as a
    spell (lands); callers treat it as free."""
    c = Cost()
    s = (s or "").strip()
    if not s or s == "no cost":
        return c
    for tok in s.replace("/", "").split():
        if tok.isdigit():
            c.generic += int(tok)
        elif tok == "X":
            c.x += 1  # X=0 is the optimistic minimum
        elif tok == "S":
            c.snow += 1
            c.uncertain = "snow"
        elif tok in ("W", "U", "B", "R", "G", "C"):
            c.pips.append(frozenset(tok))
        elif tok.endswith("P") and all(ch in "WUBRGC2" for ch in tok[:-1]):
            c.phyrexian += 1  # payable via 2 life — optimistic: free
        elif tok[0] == "2" and len(tok) == 2 and tok[1] in "WUBRG":
            c.twobrid += 1
            c.twobrid_colors.append(frozenset(tok[1]))
        elif all(ch in "WUBRGC" for ch in tok) and 2 <= len(tok) <= 3:
            c.pips.append(frozenset(tok))
        else:
            c.uncertain = f"cost_token:{tok}"
    return c


def can_pay(cost: Cost, sources: list[frozenset], extra_generic: int = 0) -> bool:
    """Backtracking pip assignment. `sources` — one frozenset of producible
    colors per untapped source (each usable once, any color also pays generic).
    Optimistic: X=0, phyrexian free. extra_generic = commander tax."""
    generic = cost.generic + extra_generic
    pips = sorted(cost.pips, key=len)  # most-constrained first

    def assign(i: int, avail: list[frozenset]) -> bool:
        if i == len(pips):
            # two-brid: each pays with its color or 2 generic; try color-greedy
            # then fall through to the generic check with the leftovers.
            return _twobrid(0, avail)
        pip = pips[i]
        seen: set[int] = set()
        for j, src in enumerate(avail):
            if src & pip and id(src) not in seen:
                seen.add(id(src))
                if assign(i + 1, avail[:j] + avail[j + 1 :]):
                    return True
        return False

    def _twobrid(k: int, avail: list[frozenset]) -> bool:
        if k == len(cost.twobrid_colors):
            return len(avail) >= generic
        col = cost.twobrid_colors[k]
        for j, src in enumerate(avail):
            if src & col and _twobrid(k + 1, avail[:j] + avail[j + 1 :]):
                return True
        # pay 2 generic instead
        return len(avail) >= 2 and _twobrid(k + 1, avail[2:])

    return assign(0, list(sources))


# ---------------------------------------------------------------- card table


class ProdUnit(NamedTuple):
    """One mana ability's production (v2, sick-aware instrument)."""

    colors: frozenset
    amount: int
    variable: bool
    needs_tap: bool  # {T}/{Q} in the activation cost — summoning-sickness-gated
    conditional: bool  # RestrictValid$ spend restriction or tapXType board cost
    zone: str  # "battlefield" (default) or "hand" (ActivationZone$ Hand)


@dataclass
class CardInfo:
    name: str
    cost: Cost
    types: str = ""
    prod: list = field(default_factory=list)  # ProdUnit entries
    chained: bool = False  # has a mana ability whose activation costs mana
    multiface: bool = False
    altcost: bool = False  # S:Mode$ AlternativeCost — printed cost unreliable
    keywords: str = ""
    # cost-modifying statics: (amount | None if unquantifiable, valid, activator)
    raises: list = field(default_factory=list)
    reduces: list = field(default_factory=list)


def _parse_face(lines: list[str], multiface: bool) -> CardInfo | None:
    name = cost_s = types = keywords = ""
    prod: list[frozenset] = []
    raises: list = []
    reduces: list = []
    chained = altcost = False
    for line in lines:
        if line.startswith("Name:") and not name:
            name = line[5:].strip()
        elif line.startswith("ManaCost:") and not cost_s:
            cost_s = line[9:].strip()
        elif line.startswith("Types:") and not types:
            types = line[6:].strip()
        elif line.startswith("K:"):
            keywords += line[2:].strip() + ";"
        elif "Mode$ AlternativeCost" in line:
            altcost = True
        elif "Mode$ RaiseCost" in line or "Mode$ ReduceCost" in line:
            parts = dict(
                (kv.split("$", 1) + [""])[:2]
                for kv in (p.strip() for p in line.split("|"))
                if "$" in kv
            )
            if parts.get("Type", "Spell").strip() not in ("Spell", ""):
                continue  # ability-cost statics — out of scope (spell casts only)
            amt_s = parts.get("Amount", "1").strip()
            amt = int(amt_s) if amt_s.isdigit() else None
            entry = (amt, parts.get("ValidCard", parts.get("ValidSpell", "Card")).strip(),
                     parts.get("Activator", "").strip())
            (raises if "RaiseCost" in line else reduces).append(entry)
        elif line.startswith("A:AB$ Mana") or line.startswith("A:AB$ ManaReflected"):
            parts = dict(
                (kv.split("$", 1) + [""])[:2]
                for kv in (p.strip() for p in line[2:].split("|"))
                if "$" in kv
            )
            azone = parts.get("ActivationZone", "Battlefield").strip()
            if azone not in ("Battlefield", "Hand"):
                continue  # command/graveyard-activated mana — out of scope
            acost = parts.get("Cost", "").strip()
            tokens = [t for t in acost.split() if t]
            needs_mana = not all(NONMANA_COST.match(t) for t in tokens)
            if needs_mana:
                chained = True
                continue
            needs_tap = any(t in ("T", "Q") for t in tokens)
            conditional = ("RestrictValid" in parts) or any(
                t.startswith("tapXType<") for t in tokens
            )
            produced = parts.get("Produced", "Any").strip()
            amt_s = parts.get("Amount", "1").strip()
            amount, variable = (int(amt_s), False) if amt_s.isdigit() else (1, True)
            if line.startswith("A:AB$ ManaReflected"):
                colors = ANY_COLOR  # depends on board — optimistic
            elif produced.startswith("Combo"):
                rest = produced[5:].strip()
                if rest in ("ColorIdentity", "Any") or not rest:
                    colors = ANY_COLOR
                else:
                    colors = frozenset(t for t in rest.split() if t in ANY_COLOR)
            elif produced == "Any":
                colors = ANY_COLOR
            elif produced in ANY_COLOR:
                colors = frozenset(produced)
            else:
                colors = ANY_COLOR  # Special/Defined variants — optimistic
            prod.append(ProdUnit(colors, amount, variable, needs_tap,
                                 conditional, azone.lower()))
    if not name:
        return None
    # basic land subtypes grant intrinsic abilities (scripts carry no A: line)
    for sub, col in BASIC_PROD.items():
        if types and sub in types.split():
            prod.append(ProdUnit(frozenset(col), 1, False, True, False,
                                 "battlefield"))
    return CardInfo(name, parse_mana_cost(cost_s), types, prod, chained,
                    multiface, altcost, keywords, raises, reduces)


def _parse_script(text: str) -> list[CardInfo]:
    """All faces — back faces (MDFC lands etc.) resolve as battlefield sources
    under their own names."""
    sections: list[list[str]] = [[]]
    for line in text.splitlines():
        if line.strip() == "ALTERNATE":
            sections.append([])
        else:
            sections[-1].append(line)
    multiface = len(sections) > 1
    return [f for s in sections if (f := _parse_face(s, multiface))]


def build_card_table() -> dict[str, CardInfo]:
    table: dict[str, CardInfo] = {}
    for folder in (CARDSFOLDER, TOKENSCRIPTS):
        for path in folder.rglob("*.txt"):
            try:
                faces = _parse_script(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            for info in faces:
                table.setdefault(info.name, info)
    # token display names drop the " Token" suffix in obs entity names
    for name in list(table):
        if name.endswith(" Token"):
            table.setdefault(name[: -len(" Token")], table[name])
    return table


# ---------------------------------------------------------------- obs frames


def read_frame(worker: Path, off: int, clen: int) -> list[dict]:
    with open(worker / "obs.zst", "rb") as fh:
        fh.seek(off)
        blob = fh.read(clen)
    out = []
    text = zstandard.ZstdDecompressor().decompress(blob, max_output_size=1 << 28)
    for line in io.TextIOWrapper(io.BytesIO(text), encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def frame_index(worker: Path) -> dict[int, tuple[int, int]]:
    idx = {}
    f = worker / "obs.idx.jsonl"
    if not f.exists():
        return idx
    for line in open(f):
        try:
            r = json.loads(line)
            idx[r["g"]] = (r["off"], r["clen"])
        except (json.JSONDecodeError, KeyError):
            continue
    return idx


# ---------------------------------------------------------------- classifier

BRACES = re.compile(r"\{([^}]+)\}")
# spell SA texts that lead with an alternate-cost mode ("Bestow {2}{W} (...)",
# "Channel — {3}{R}, Discard ...") — anything else displaying effect text is
# the plain cast at printed cost
ALT_KEYWORD = re.compile(
    r"^(Bestow|Channel|Flashback|Overload|Dash|Evoke|Prototype|Madness|Escape"
    r"|Foretell|Disturb|Jump-start|Spectacle|Surge|Emerge|Cleave|Blitz|Unearth"
    r"|Retrace|Awaken|Mutate|Morph|Disguise|Cycling|\w+cycling)\b"
)
FREE_TOKENS = {"T", "Q", "E"}  # tap/untap/energy — payable without mana


def cost_from_sa(sa: str) -> tuple[Cost | None, set[str]]:
    """Extract the leading brace-run cost from an SA text. The cost segment
    ends at the first period OR the first '(' — reminder text repeats the
    cost ("Reconfigure {2} ({2}: Attach ...)") and would double it.
    Returns (cost, non-mana tokens seen); cost None if no braces at all."""
    cut = len(sa)
    for ch in ".(":
        i = sa.find(ch)
        if i >= 0:
            cut = min(cut, i)
    toks = [t.replace("/", "") for t in BRACES.findall(sa[:cut]) if t.strip()]
    if not toks:
        return None, set()
    free = {t for t in toks if t in FREE_TOKENS}
    mana = [t for t in toks if t not in FREE_TOKENS
            and (t.isdigit() or all(ch in "WUBRGCSXP" for ch in t))]
    return parse_mana_cost(" ".join(mana)), free


_COLOR_WORD = {"White": "W", "Blue": "U", "Black": "B", "Red": "R", "Green": "G"}
_TYPE_WORDS = ("Creature", "Artifact", "Enchantment", "Instant", "Sorcery",
               "Planeswalker", "Land", "Battle")


def _static_applies(valid: str, activator: str, static_seat: int, seat: int,
                    card: CardInfo) -> bool:
    """Coarse ValidCard/Activator filter match. Unknown conditions match
    (the engine's own unpayable verdict corroborates the raise path; the
    reduce path only downgrades to uncertain)."""
    if activator == "You" and static_seat != seat:
        return False
    if "Opponent" in activator and static_seat == seat:
        return False
    ctypes = set(card.types.split())
    colors = set().union(*card.cost.pips, *card.cost.twobrid_colors) if (
        card.cost.pips or card.cost.twobrid_colors) else set()
    for group in valid.split(","):
        ok = True
        for cond in group.strip().split(".")[1:]:
            neg = cond.startswith("non")
            base = cond[3:] if neg else cond
            if base in _TYPE_WORDS:
                hit = base in ctypes
            elif base in _COLOR_WORD:
                hit = _COLOR_WORD[base] in colors
            else:
                hit = True  # unknown condition — treat as matching
            if hit == neg:
                ok = False
                break
        if ok:
            return True
    return False


MANA_ABILITY_SA = re.compile(r"Add \{")


class SourceViews(NamedTuple):
    """Affordability source units from the seat's own observation. Each
    PERMANENT taps once: its abilities are choose-one alternatives, so a
    host contributes max-amount units of the union of every color its
    AVAILABLE abilities can make (optimistic). Three nested availability
    views (v2, sick-aware — `sick` IS emitted for battlefield creatures,
    ADR-0063 addendum):
      now  — unconditional abilities usable this turn
      cond — + spend-restricted / board-cost production (RestrictValid,
             tapXType): applicability unsettleable from the obs
      full — + tap-production on summoning-sick hosts (unusable in fact:
             payable only here => knowably unaffordable via sickness)"""

    now: list
    cond: list
    full: list
    chained: bool
    var_amount: bool
    unknown_untapped: int


def source_views(obs: dict, seat: int, table: dict[str, CardInfo]) -> SourceViews:
    src_now: list[frozenset] = []
    src_cond: list[frozenset] = []
    src_full: list[frozenset] = []
    chained_avail = var_amount_avail = False
    unknown_untapped = 0
    for e in obs.get("ents", []):
        if e.get("c") != seat:
            continue
        ez = e.get("z")
        if ez not in ("battlefield", "hand"):
            continue
        info = table.get(e.get("n", ""))
        if info is None:
            if ez == "battlefield" and not e.get("tap"):
                unknown_untapped += 1
            continue
        abz = [u for u in info.prod if u.zone == ez]
        tapped, sick = bool(e.get("tap")), bool(e.get("sick"))

        def _collapse(view: list, out: list) -> None:
            if view:
                allcolors = frozenset().union(*(u.colors for u in view))
                out.extend([allcolors] * max(u.amount for u in view))

        usable = [u for u in abz if not (u.needs_tap and (tapped or sick))]
        _collapse([u for u in usable if not u.conditional], src_now)
        _collapse(usable, src_cond)
        _collapse([u for u in abz if not (u.needs_tap and tapped)], src_full)
        if any(u.variable for u in usable):
            # variable-amount production that could actually be activated
            # this turn (tapped/sick hosts can't rescue affordability)
            var_amount_avail = True
        if info.chained and ez == "battlefield" and not tapped:
            chained_avail = True
    return SourceViews(src_now, src_cond, src_full, chained_avail,
                       var_amount_avail, unknown_untapped)


def classify_window(cen: dict, dec: dict, table: dict[str, CardInfo],
                    corroborated: bool = True) -> dict:
    """One vetoed (or validation) window -> verdict record. `corroborated`:
    the engine really vetoed this window as unpayable, so its verdict can
    break ties (the statics-tax branch); validation records pass False."""
    obs = dec.get("obs") or {}
    seat = dec.get("p")
    ents = {e["e"]: e for e in obs.get("ents", [])}
    reason = cen.get("veto")

    # -- resolve the picked option (census pick text == opts sa text, modulo
    # truncation on either side)
    pick = cen.get("pick") or ""
    opt = None
    for o in dec.get("opts", []):
        sa = str(o.get("sa") or "")
        if sa == pick or sa.startswith(pick) or pick.startswith(sa):
            opt = o
            break
    if opt is None:
        return {"verdict": "uncertain", "why": "pick_unmatched"}
    ent = ents.get(opt.get("e"))
    if ent is None:
        return {"verdict": "uncertain", "why": "entity_missing"}
    name = ent.get("n", "")
    card = table.get(name)
    zone = ent.get("z")
    sa = str(opt.get("sa") or "")
    kind = opt.get("kind")

    # -- timing reasons: fully public arithmetic on phase/priority/stack
    if reason == "timing":
        ttypes = (card.types if card else "").split()
        flashy = "Instant" in ttypes or (card and "Flash" in card.keywords)
        if flashy:
            return {"verdict": "not_knowable", "why": "timing_flexible", "card": name}
        glob = obs.get("glob", {})
        # both stack representations (anvil.bridge.featurize.quiescent_main):
        # cards on the stack are entities; triggered/activated abilities live
        # only in obs["stack"] (found 2026-09-04; this branch misrouted ~1
        # window per report into timing_unexplained before the fix)
        stack = bool(obs.get("stack")) or any(e.get("z") == "stack" for e in obs.get("ents", []))
        offphase = glob.get("ph") not in ("MAIN1", "MAIN2") or glob.get("ap") != seat
        if offphase or stack:
            return {"verdict": "knowable", "why": "timing", "card": name}
        return {"verdict": "not_knowable", "why": "timing_unexplained", "card": name}

    # -- determine the cost being attempted
    if kind == "ability":
        cost, free = cost_from_sa(sa)
        # a {T}-cost ability from an already-tapped battlefield host is
        # unaffordable on its face, no mana arithmetic needed
        if "T" in free and zone == "battlefield" and ent.get("tap"):
            return {"verdict": "knowable", "why": "source_tapped", "card": name}
        if "T" in free and zone == "battlefield" and ent.get("sick"):
            # {T} ability on a summoning-sick host — unusable, and the obs
            # carries the flag (v2: `sick` IS in the schema, ADR-0063 addendum)
            return {"verdict": "knowable", "why": "ability_sick", "card": name}
        if MANA_ABILITY_SA.search(sa.split(".", 1)[0]):
            # a mana-ability pick rejected by the realizer — rules-payable,
            # the interface can't route it (ADR-0062 artifact family)
            return {"verdict": "not_knowable", "why": "interface_mana_ability",
                    "card": name}
        if cost is None:
            cost = Cost()  # no brace cost — non-mana activation, payable
    else:  # spell cast
        if card is None:
            return {"verdict": "uncertain", "why": "card_unresolved", "card": name}
        if card.altcost:
            return {"verdict": "uncertain", "why": "alternative_cost", "card": name}
        plain = sa.startswith(f"{name} - ") or sa == name
        alt = ALT_KEYWORD.match(sa)
        if plain:
            cost = card.cost  # front face — correct even for multiface plain casts
        elif alt:
            cost, _ = cost_from_sa(sa)
            if cost is None:
                return {"verdict": "uncertain", "why": "altmode_cost_unparsed", "card": name}
        elif card.multiface:
            # split/adventure secondary face shown as effect text — which
            # face's cost applies isn't resolvable from the SA text alone
            return {"verdict": "uncertain", "why": "multiface_mode", "card": name}
        else:
            cost = card.cost  # non-permanent spell displayed as effect text
    if cost.uncertain:
        return {"verdict": "uncertain", "why": cost.uncertain, "card": name}

    # commander tax: cast from the command zone — optimistic: min cmdcast
    extra = 0
    if zone == "command":
        try:
            extra = 2 * min(obs["players"][seat]["cmdcast"])
        except (KeyError, IndexError, TypeError, ValueError):
            extra = 0

    views = source_views(obs, seat, table)
    src_now, src_cond, src_full = views.now, views.cond, views.full
    chained_avail, var_amount_avail = views.chained, views.var_amount
    unknown_untapped = views.unknown_untapped

    # cost-modifying statics anywhere on the battlefield (tapped ones too)
    raise_total, raise_unq, reduce_present = 0, False, False
    if kind != "ability" and card is not None:
        for e in obs.get("ents", []):
            if e.get("z") != "battlefield":
                continue
            info = table.get(e.get("n", ""))
            if info is None:
                continue
            for amt, valid, act in info.raises:
                if _static_applies(valid, act, e.get("c"), seat, card):
                    if amt is None:
                        raise_unq = True
                    else:
                        raise_total += amt
            for amt, valid, act in info.reduces:
                if _static_applies(valid, act, e.get("c"), seat, card):
                    reduce_present = True

    if can_pay(cost, src_now, extra):
        # optimistic arithmetic says payable, the engine said unpayable —
        # unpayability has no hidden causes, so attribute to the named
        # public mechanisms in confidence order
        if corroborated and raise_total:
            taxed = Cost(cost.generic + raise_total, cost.pips, cost.twobrid,
                         cost.twobrid_colors, cost.phyrexian, cost.x, cost.snow)
            if not can_pay(taxed, src_now, extra):
                # a visible tax static closes the gap and the engine agrees
                return {"verdict": "knowable", "why": "statics_tax", "card": name}
        if corroborated and (raise_unq or raise_total):
            return {"verdict": "uncertain", "why": "raisecost_unresolved", "card": name}
        if cost.phyrexian:
            # rules-payable via life; the auto-payer refuses — blind-spot family
            return {"verdict": "not_knowable", "why": "autopayer_phyrexian", "card": name}
        if cost.x:
            return {"verdict": "not_knowable", "why": "autopayer_xcost", "card": name}
        return {"verdict": "not_knowable", "why": "obs_says_payable", "card": name}
    if can_pay(cost, src_cond, extra):
        # payable only through spend-restricted / board-cost production —
        # whether the restriction admits THIS cast is unsettleable here
        return {"verdict": "uncertain", "why": "conditional_production", "card": name}
    if reduce_present:
        # a visible cost reducer could make this affordable after all
        return {"verdict": "uncertain", "why": "reducecost_in_play", "card": name}
    if chained_avail:
        return {"verdict": "uncertain", "why": "chained_source_available", "card": name}
    if var_amount_avail:
        return {"verdict": "uncertain", "why": "variable_amount_source", "card": name}
    if unknown_untapped:
        return {"verdict": "uncertain", "why": "unknown_battlefield_card", "card": name}
    if can_pay(cost, src_full, extra):
        # only counting tap-production on summoning-sick hosts rescues it —
        # unaffordable in fact, and the obs sick flags say so (v2)
        return {"verdict": "knowable", "why": "sickness_short", "card": name}
    # knowable — subtag: colorblind arithmetic distinguishes colors- vs
    # generic-short (treat every pip as generic and recheck)
    total_pips = len(cost.pips) + len(cost.twobrid_colors)
    colorblind = Cost(generic=cost.generic + total_pips)
    sub = "colors_short" if can_pay(colorblind, src_full, extra) else "generic_short"
    return {"verdict": "knowable", "why": sub, "card": name}


# ---------------------------------------------------------------- pipelines


def scan_census(worker: Path):
    """One pass over census.jsonl -> (bases, vetoes, accepted).

    Census `s` is CUMULATIVE per worker while obs `s` resets per game; both
    streams enumerate the same event set in order, so the obs step for a
    census record is s - base[g] where base[g] = the game's minimum census s
    over ALL records (not just chooseSpellAbilityToPlay)."""
    bases: dict[int, int] = {}
    vetoes: dict[int, dict[int, dict]] = {}
    accepted: list[dict] = []
    f = worker / "census.jsonl"
    if not f.exists():
        return bases, vetoes, accepted
    for line in open(f):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        g, s = r.get("g"), r.get("s")
        if g is None or s is None:
            continue
        if g not in bases or s < bases[g]:
            bases[g] = s
        if r.get("by") != "bridge" or r.get("m") != "chooseSpellAbilityToPlay":
            continue
        if r.get("veto"):
            vetoes.setdefault(g, {})[s] = r
        elif r.get("pick") != "pass" and not r.get("reask"):
            accepted.append(r)
    return bases, vetoes, accepted


def classify_run_dir(run_dir: Path, table: dict, val_per_worker: int, rng: random.Random):
    """Yields (kind, cen, result) — kind in {veto, val}."""
    for worker in sorted(run_dir.glob("workers/inv-*")):
        bases, vetoes, accepted = scan_census(worker)
        val = rng.sample(accepted, min(val_per_worker, len(accepted)))
        wanted: dict[int, dict[int, tuple[str, dict]]] = {}
        for g, by_s in vetoes.items():
            for s, r in by_s.items():
                wanted.setdefault(g, {})[s] = ("veto", r)
        for r in val:
            wanted.setdefault(r["g"], {}).setdefault(r["s"], ("val", r))
        idx = frame_index(worker)
        for g, by_s in sorted(wanted.items()):
            if g not in idx:
                continue
            off, clen = idx[g]
            try:
                recs = read_frame(worker, off, clen)
            except Exception:
                continue
            decs = {r["s"]: r for r in recs if r.get("k") == "dec"}
            base = bases.get(g, 0)
            for s, (kind, cen) in by_s.items():
                dec = decs.get(s - base)
                if dec is None or dec.get("m") != "chooseSpellAbilityToPlay":
                    yield kind, cen, {"verdict": "uncertain", "why": "dec_missing"}
                    continue
                if kind == "val":
                    cen = dict(cen)
                    cen["veto"] = "unpayable"  # run the affordability path
                    res = classify_window(cen, dec, table, corroborated=False)
                    yield "val", cen, res
                else:
                    yield "veto", cen, classify_window(cen, dec, table)


def cmd_classify(args):
    table = build_card_table()
    print(f"card table: {len(table)} entries", file=sys.stderr)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260819)
    meta = {"instrument": "v2-sick-aware", "pops": {},
            "pin": {"gate": 0.50, "basis": "first-attempt, mana-relevant",
                    "validity_bar": 0.95}}
    with open(out / "windows.jsonl", "w") as wf, open(out / "validation.jsonl", "w") as vf:
        for pop, dirs in args.pops:
            meta["pops"][pop] = dirs
            for d in dirs:
                rd = ROOT / d
                print(f"[{pop}] {rd.name}", file=sys.stderr)
                for kind, cen, res in classify_run_dir(rd, table, args.val_per_worker, rng):
                    rec = {
                        "pop": pop, "run": rd.name, "g": cen.get("g"), "s": cen.get("s"),
                        "t": cen.get("t"), "ph": cen.get("ph"),
                        "reason": cen.get("veto") if kind == "veto" else None,
                        "reask": bool(cen.get("reask")), "pick": (cen.get("pick") or "")[:60],
                        **res,
                    }
                    (wf if kind == "veto" else vf).write(json.dumps(rec) + "\n")
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"wrote {out}", file=sys.stderr)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def cmd_report(args):
    out = ROOT / args.out
    windows = [json.loads(x) for x in open(out / "windows.jsonl")]
    vals = [json.loads(x) for x in open(out / "validation.jsonl")]
    meta = json.loads((out / "meta.json").read_text())
    rep: dict = {"pin": meta["pin"], "pops": {}}
    for pop in meta["pops"]:
        W = [w for w in windows if w["pop"] == pop]
        V = [v for v in vals if v["pop"] == pop]
        # validity bar: accepted casts the arithmetic could settle should be
        # payable; unsettleable ones are reported but don't count against it
        v_settled = [v for v in V if v["verdict"] != "uncertain"]
        v_ok = sum(1 for v in v_settled if v["verdict"] == "not_knowable")
        p: dict = {
            "validation": {
                "n_sampled": len(V), "n_settled": len(v_settled),
                "affordable_ok": v_ok,
                "rate": round(v_ok / max(1, len(v_settled)), 4),
                "uncertain_reasons": dict(Counter(v["why"] for v in V
                                                  if v["verdict"] == "uncertain")),
            },
            "all_reasons": dict(Counter(w["reason"] for w in W)),
        }
        for basis, sel in (("first_attempt", [w for w in W if not w["reask"]]),
                           ("all_attempts", W)):
            mr = [w for w in sel if w["reason"] in MANA_RELEVANT]
            k = sum(1 for w in mr if w["verdict"] == "knowable")
            lo, hi = wilson(k, len(mr))
            p[basis] = {
                "n_mana_relevant": len(mr), "knowable": k,
                "fraction": round(k / max(1, len(mr)), 4),
                "ci95": [round(lo, 4), round(hi, 4)],
                "verdicts": dict(Counter(w["verdict"] for w in mr)),
                "taxonomy": dict(Counter(f"{w['verdict']}:{w['why']}" for w in mr)),
            }
        f = p["first_attempt"]
        p["gate"] = {
            "threshold": meta["pin"]["gate"],
            "fraction": f["fraction"], "ci95": f["ci95"],
            "pass": f["fraction"] >= meta["pin"]["gate"],
        }
        rep["pops"][pop] = p
    (out / "report.json").write_text(json.dumps(rep, indent=1))
    for pop, p in rep["pops"].items():
        f = p["first_attempt"]
        v = p["validation"]
        print(f"== {pop} ==")
        print(f"  validity bar: {v['rate']:.4f} affordable on {v['n_settled']} settled "
              f"accepted casts (bar >= {meta['pin']['validity_bar']}) "
              f"{'OK' if v['rate'] >= meta['pin']['validity_bar'] else 'FAIL'}")
        print(f"  first-attempt mana-relevant: n={f['n_mana_relevant']} "
              f"knowable={f['fraction']:.4f} CI95=[{f['ci95'][0]:.4f},{f['ci95'][1]:.4f}] "
              f"gate>=0.50 {'PASS' if p['gate']['pass'] else 'FAIL'}")
        print(f"  verdicts: {f['verdicts']}")
        print(f"  taxonomy: {json.dumps(f['taxonomy'], indent=4)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def pop_arg(s: str):
        name, _, dirs = s.partition("=")
        return (name, [d for d in dirs.split(",") if d])

    c = sub.add_parser("classify")
    c.add_argument("--pop", dest="pops", action="append", type=pop_arg, required=True,
                   metavar="NAME=DIR[,DIR...]")
    c.add_argument("--out", required=True)
    c.add_argument("--val-per-worker", type=int, default=60,
                   help="accepted-cast validation sample per worker")
    c.set_defaults(func=cmd_classify)

    r = sub.add_parser("report")
    r.add_argument("--out", required=True)
    r.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
