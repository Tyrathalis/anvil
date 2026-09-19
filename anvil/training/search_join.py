"""M12 Build 4½ pre-work — the loop wiring (ADR-0113): the search directive's
rows joined to a trajectory store's priority decs, and the ACTED-WINDOW
RECORD the RL loader trains on.

The facts this encodes (read at the 09-18 review of the b4post act arm):

- On a searched mainline window the engine writes TWO dec records and two
  behavior (mu) records when the acting rule fires: the NATURAL ask over the
  full option list (the policy's own sample, `ret` set as if realized — it was
  computed, never played) and the FORCED single-option ask that plays the
  search's pick (`by: "search"`, the pass logit masked at serve, the model's
  plan for that option). The behavior policy at that window is the search's
  leaf-value softmax (the row's `p` over its options), not the policy's.
- The search row carries the pick (`act_o`), the distribution (`p`), the
  natural line (`nat`), the margin and the applied class: `act` (the forced
  ask realized), `pass` (the search chose the pass option), `act_void` (the
  forced ask was vetoed / voided — the natural line played), `natural` (below
  the bar, or the sample equalled the natural).

The MERGE (the user's decision, 09-18): one training window per decision —
the natural dec's full option set with the choice rewritten to the acted
candidate, the choice's behavior probability = the search's mass on that
candidate (the row's `p` summed over the wire options the featurizer
collapses onto it), the plan factors (targets, X) and their log-probs from
the forced ask's mu record; the forced dec itself is dropped. An acted pass
joins the class with candidate 0. An act_void window played the natural
line: its behavior probability is the mass on the natural candidate plus the
mass on the voided pick (the two paths that realize the natural). A natural
window that carries `p` (the rule fired and sampled the natural) takes the
search's mass on the natural. Un-searched and below-the-bar windows keep
their recorded mu untouched — the acting rule plays the current policy there.

Every function here is pure over dicts; the loader (rl.game_trajectories)
owns the featurizer and the store.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

PRIORITY = "chooseSpellAbilityToPlay"
FORCED_BY = "search"  # Obs.decPriority(..., "search", ...) on the forced re-ask
ACTED = ("act", "pass")  # the applied classes whose realized pick is the search's
SEARCH_PHASES = ("MAIN1", "MAIN2")


def candidate_window(dec: dict, seat: int) -> bool:
    """The search directive's candidate rule (AnvilRun: the active bridged
    seat's QUIESCENT MAIN1 / MAIN2 windows), read from the dec's own obs:
    the phase, an empty stack, the seat is the active player. Windows that
    fail it carry no search row, and an earlier such window with the same
    option list would otherwise take a later row (09-18: the second pairing
    class on the tgtlab pool)."""
    if dec.get("ph") not in SEARCH_PHASES:
        return False
    obs = dec.get("obs") or {}
    if obs.get("stack"):
        # the obs's stack entries (Build 4's stack fields; present only on a
        # non-empty stack) — an entity's z == "stack" lingers after resolution
        return False
    ap = (obs.get("glob") or {}).get("ap")
    return ap is None or int(ap) == int(seat)


def _label_matches(label: str | None, sa: str | None) -> bool:
    if not label or not sa:
        return False
    n = min(len(label), len(sa))
    return n > 0 and label[:n] == sa[:n]


def align(labels: list[str], opts: list[dict]) -> list[int] | None:
    """The row's non-pass options (the SEARCHED list: contiguous, the mana
    abilities the search skips removed) aligned in order against the dec's
    option list (the mask: mana abilities included) by render prefix; None
    when a label finds no later option. (search_distill.align, verbatim.)"""
    out: list[int] = []
    j = 0
    for lab in labels:
        found = -1
        while j < len(opts):
            sa = opts[j].get("sa") or ""
            j += 1
            n = min(len(str(lab)), len(sa))
            if n > 0 and str(lab)[:n] == sa[:n]:
                found = j - 1
                break
        if found < 0:
            return None
        out.append(found)
    return out


def match_rows(decs: list[dict], rows: list[dict]) -> tuple[list[tuple[int, dict, dict]], Counter]:
    """(dec index, row, row option index -> dec option index) per matched
    `ev: search` row: rows in sw order, decs in seq order, one pointer per
    seat; a row takes the first later priority dec of its seat at its
    (t, ph) with the row's option count whose option list aligns with the
    row's labels. Decs tagged
    `by: search` (the forced re-ask) never match — a one-option row of a
    later window could otherwise land on the forced ask left behind."""
    out: list[tuple[int, dict, dict]] = []
    counts: Counter = Counter()
    ptr: dict[int, int] = defaultdict(int)
    for r in rows:
        if r.get("ev") != "search" or not r.get("opts"):
            continue
        counts["rows"] += 1
        seat = int(r["seat"])
        row_opts = [o for o in r["opts"] if int(o.get("o", 0)) != 0]
        labels = [o["label"] for o in row_opts]
        j = ptr[seat]
        found = -1
        o_to_dec: dict[int, int] = {}
        n_opts = r.get("n_opts")

        def fits(d: dict) -> list[int] | None:
            if d.get("m") != PRIORITY or d.get("p") != seat or d.get("by") == FORCED_BY:
                return None
            if d.get("t") != r["t"] or d.get("ph") != r["ph"] or not candidate_window(d, seat):
                return None
            if n_opts is not None and len(d.get("opts") or []) != int(n_opts):
                # the row's n_opts is the scan's option count (mana abilities
                # included) = the natural ask's; an earlier window of the
                # same phase (a superset, before a cast) or a re-ask chain
                # dec (a subset, after a veto) aligns by prefix but is not
                # this window (09-18: 71/452 acted rows paired wrong without it)
                return None
            return align(labels, d.get("opts") or [])

        if r.get("applied") in ("act", "act_void") and r.get("act"):
            # an acted row anchors on its forced re-ask (the single-option
            # `by: search` dec rendering the acted label): the natural ask
            # is the nearest fitting dec before it (09-18: the walk alone
            # landed 12/1,511 acted rows one candidate window early)
            f = -1
            k = j
            while k < len(decs):
                d = decs[k]
                if d.get("t", 0) > r["t"]:
                    break
                if (d.get("m") == PRIORITY and d.get("p") == seat and d.get("by") == FORCED_BY
                        and d.get("t") == r["t"] and d.get("ph") == r["ph"]
                        and len(d.get("opts") or []) == 1
                        and _label_matches(r.get("act"), d["opts"][0].get("sa"))):
                    f = k
                    break
                k += 1
            if f >= 0:
                for k in range(f - 1, j - 1, -1):
                    al = fits(decs[k])
                    if al is not None:
                        found = k
                        o_to_dec = {int(o["o"]): di for o, di in zip(row_opts, al)}
                        counts["row_anchored"] += 1
                        break
        if found < 0:
            while j < len(decs):
                d = decs[j]
                j += 1
                if d.get("t", 0) > r["t"]:
                    break
                al = fits(d)
                if al is None:
                    continue
                found = j - 1
                o_to_dec = {int(o["o"]): di for o, di in zip(row_opts, al)}
                break
        if found < 0:
            counts["row_unmatched"] += 1
            continue
        ptr[seat] = found + 1
        counts["row_matched"] += 1
        out.append((found, r, o_to_dec))
    return out, counts


def natural_before(decs: list[dict], f: int, lookback: int = 60) -> int | None:
    """The natural ask's dec index for a forced re-ask at f: the EARLIEST
    dec of the contiguous run of same-seat, same-(t, ph), non-forced
    priority decs before it (the natural ask and its re-ask chain), walking
    back past the natural line's setup (the inverse of forced_after, for
    orphaned forced decs)."""
    d0 = decs[f]
    seat = d0.get("p")
    first = None
    for j in range(f - 1, max(-1, f - 1 - lookback), -1):
        d = decs[j]
        if d.get("m") != PRIORITY:
            continue
        if d.get("t") != d0.get("t") or d.get("ph") != d0.get("ph") or d.get("p") != seat:
            break
        if d.get("by") == FORCED_BY:
            break
        first = j  # the earliest dec of the chain = the natural ask
    return first


def chain_between(decs: list[dict], i: int, f: int) -> list[int]:
    """The natural ask's re-ask chain on an acted window: the priority decs
    of the same seat strictly between the natural ask at i and the forced
    re-ask at f. Each attempt carries its own behavior record and would
    otherwise train as a played decision; the acted window's realized pick
    replaced them all."""
    seat = decs[i].get("p")
    return [j for j in range(i + 1, f) if decs[j].get("m") == PRIORITY and decs[j].get("p") == seat]


def forced_after(decs: list[dict], i: int, label: str | None = None, lookahead: int = 60) -> int | None:
    """The forced ask's dec index for the natural dec at i: the first later
    priority dec tagged `by: search` with a single option whose render
    matches `label` (the row's acted option), before any OTHER seat's
    priority dec or a new (t, ph). The natural line's discarded setup
    (optional costs, delve, …) and the natural ask's own re-ask chain (the
    same seat, `by` not search, fewer options) sit between and are walked
    past. None when absent (the window was not acted, or the pick was
    realized without a bridge ask — the control arm)."""
    d0 = decs[i]
    seat = d0.get("p")
    for j in range(i + 1, min(len(decs), i + 1 + lookahead)):
        d = decs[j]
        if d.get("m") != PRIORITY:
            continue
        if d.get("t") != d0.get("t") or d.get("ph") != d0.get("ph") or d.get("p") != seat:
            return None
        if d.get("by") == FORCED_BY:
            opts = d.get("opts") or []
            if len(opts) == 1 and (label is None or _label_matches(label, opts[0].get("sa"))):
                return j
            return None
        # the natural ask's re-ask chain: walk past
    return None


def cand_of_options(dec: dict, aux: dict) -> dict[int, int]:
    """Wire option index -> the featurizer's candidate index. The featurizer
    collapses options with an identical (host row, normalized sa) key onto
    one candidate (aux["cand_first_opt"] keeps the FIRST option per
    candidate); this is the inverse over every option of the dec."""
    from anvil.bridge.featurize import norm_sa

    row_of = aux["row_of"]
    opts = dec.get("opts") or []
    key_of: dict[tuple, int] = {}
    for c, fo in enumerate(aux["cand_first_opt"]):
        if fo < 0 or fo >= len(opts):
            continue
        o = opts[fo]
        key_of[(row_of.get(o.get("e")), norm_sa(o.get("sa", "")))] = c
    out: dict[int, int] = {}
    for i, o in enumerate(opts):
        r = row_of.get(o.get("e"))
        if r is None:
            continue
        c = key_of.get((r, norm_sa(o.get("sa", ""))))
        if c is not None:
            out[i] = c
    return out


def behavior_mass(row: dict, o_to_dec: dict[int, int], opt_to_cand: dict[int, int]) -> dict[int, float]:
    """Candidate index -> the search's behavior probability mass: the row's
    `p` (over its option list, position = the option's `o`; index 0 = pass)
    summed onto the collapsed candidates. Empty when the row carries no
    distribution (the rule did not fire)."""
    p = row.get("p")
    if not p:
        return {}
    mass: dict[int, float] = defaultdict(float)
    for pos, o in enumerate(row.get("opts") or []):
        oi = int(o.get("o", pos))
        if oi >= len(p):
            continue
        if oi == 0:
            c = 0
        else:
            di = o_to_dec.get(oi)
            c = opt_to_cand.get(di) if di is not None else None
            if c is None:
                continue
        mass[c] += float(p[oi])
    return dict(mass)


def _cand_of_row_option(oi: int, o_to_dec: dict[int, int], opt_to_cand: dict[int, int]) -> int | None:
    if oi == 0:
        return 0
    di = o_to_dec.get(oi)
    return opt_to_cand.get(di) if di is not None else None


def acted_override(
    row: dict,
    rec: dict,
    o_to_dec: dict[int, int],
    opt_to_cand: dict[int, int],
    forced_rec: dict | None,
    floor: float = 1e-6,
) -> tuple[dict | None, str]:
    """The merged behavior record for one searched priority window and its
    class. Returns (record, class); a None record with a class naming the
    failure means the loader DROPS the window (never trains a wrong mu).

      act          c = cand(act_o), lp.choice = log mass[c], tgt/x + their
                   lps from the forced ask's record
      pass         c = 0, lp.choice = log mass[0]
      act_void     c = the natural (recorded), lp.choice = log(mass[nat] +
                   mass[cand(act_o)]) — the natural line played
      natural      `p` present: lp.choice = log mass[c_nat]; absent: the
                   record untouched (class "natural")
    """
    applied = row.get("applied")
    mass = behavior_mass(row, o_to_dec, opt_to_cand)
    if applied not in ACTED and applied != "act_void":
        if not mass:
            return rec, "natural"
        c = int(rec["c"])
        if c not in mass or mass[c] <= 0:
            return rec, "natural_unmassed"
        rec2 = dict(rec)
        lp = dict(rec.get("lp") or {})
        lp["choice"] = math.log(max(mass[c], floor))
        rec2["lp"] = lp
        rec2["logp"] = float(sum(lp.values()))
        rec2["acted"] = False
        rec2["search_mu"] = True
        return rec2, "natural_sampled"
    if not mass:
        return None, f"{applied}_no_p"
    if applied == "act_void":
        c_nat = int(rec["c"])
        c_act = _cand_of_row_option(int(row.get("act_o", -1)), o_to_dec, opt_to_cand)
        m = mass.get(c_nat, 0.0) + (mass.get(c_act, 0.0) if c_act is not None and c_act != c_nat else 0.0)
        if m <= 0:
            return None, "act_void_no_mass"
        rec2 = dict(rec)
        lp = dict(rec.get("lp") or {})
        lp["choice"] = math.log(max(m, floor))
        rec2["lp"] = lp
        rec2["logp"] = float(sum(lp.values()))
        rec2["acted"] = False
        rec2["search_mu"] = True
        return rec2, "act_void"
    # act / pass: the realized pick is the search's
    if applied == "pass":
        c = 0
    else:
        c = _cand_of_row_option(int(row.get("act_o", -1)), o_to_dec, opt_to_cand)
        if c is None:
            return None, "act_no_cand"
    m = mass.get(c, 0.0)
    if m <= 0:
        return None, f"{applied}_no_mass"
    rec2 = {k: v for k, v in rec.items() if k not in ("c", "tgt", "x", "lp", "logp", "ent")}
    rec2["c"] = c
    lp = {"choice": math.log(max(m, floor))}
    if c > 0:
        if forced_rec is None or forced_rec.get("task") != "priority" or int(forced_rec.get("c", 0)) <= 0:
            return None, "act_no_forced"
        rec2["tgt"] = list(forced_rec.get("tgt", []))
        rec2["x"] = int(forced_rec.get("x", 0))
        flp = forced_rec.get("lp") or {}
        lp["tgt"] = float(flp.get("tgt", 0.0))
        lp["x"] = float(flp.get("x", 0.0))
    rec2["lp"] = lp
    rec2["logp"] = float(sum(lp.values()))
    rec2["ent"] = dict(rec.get("ent") or {})
    rec2["acted"] = True
    rec2["search_mu"] = True
    return rec2, applied


def alloc_fields(row: dict, bar: float, floor: float = 0.1) -> tuple[int, float]:
    """(the allocation label: the search's margin at this window >= the
    acting bar, the window's population weight). Under the head the searched
    windows are {p >= tau} plus a uniform `floor` draw of the rejected
    region, so a floor window stands for 1 / floor rejected windows and a
    head window for itself; the uniform rate (no head, unserved) weights 1.
    The tau derivation and its recall are weighted — the floor sample alone
    is NOT an unbiased sample of all candidate windows (it never contains a
    p >= tau window; 09-18 smoke: the previous tau's recall read 0 on it)."""
    margin = row.get("margin")
    label = 1 if (margin is not None and float(margin) >= bar) else 0
    by = (row.get("alloc") or {}).get("by")
    weight = (1.0 / floor) if (by == "floor" and floor > 0) else 1.0
    return label, weight


def derive_tau(p: list[float], y: list[int], recall: float, w: "list[float] | None" = None) -> dict:
    """The head's threshold at the (weighted) recall target over the searched
    windows: the p at which `recall` of the positives' weight sits at or
    above it, plus the AUC on the sample and the weighted recall / windows
    share at that tau. `w` = the population weights (alloc_fields)."""
    n = len(p)
    w = list(w) if w is not None else [1.0] * n
    pos = sorted(((pi, wi) for pi, yi, wi in zip(p, y, w) if yi), key=lambda t: t[0])
    out = {"n": n, "n_pos": len(pos), "recall_pin": recall}
    if not pos:
        out["tau"] = None
        return out
    total = sum(wi for _, wi in pos)
    # the highest tau keeping `recall` of the positive weight at or above it
    acc = 0.0
    tau = pos[0][0]
    for pi, wi in pos:
        if (total - acc) / total < recall:
            break
        tau = pi
        acc += wi
    out["tau"] = round(float(tau), 5)
    sel = [pi >= tau for pi in p]
    out["recall"] = round(sum(wi for s, yi, wi in zip(sel, y, w) if s and yi) / total, 4)
    out["windows_share"] = round(sum(wi for s, wi in zip(sel, w) if s) / sum(w), 4)
    # AUC by rank (ties averaged)
    order = sorted(range(n), key=lambda i: p[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and p[order[j + 1]] == p[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k2 in range(i, j + 1):
            ranks[order[k2]] = r
        i = j + 1
    n_pos = len(pos)
    n_neg = n - n_pos
    if n_neg:
        rs = sum(ranks[i] for i in range(n) if y[i])
        out["auc"] = round((rs - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg), 4)
    return out
