"""M10 v2 schedule-target construction + discrete-carry reconstruction
(m10-build-spec §1/§4).

Targets are trajectory-derived at birth (era-labels join later): the decode
target is the turn's realized schedulable actions in order, matched to the
emission window's candidates by (wire entity id, normalized SA); E is the
end-of-turn resource summary at the turn's last own obs-bearing window; R is
the running ledger (untapped/affordable-hand) at the next own obs-bearing
window after each realized non-land slot. Axis conventions are IMPORTED from
the pinned instrument scripts (schedule_census.resolve_cost,
veto_knowability.source_views/can_pay — the census conventions the
veto-knowability v2 instrument and v2_target_probe share); duplication would
drift, so scripts/ joins sys.path here the way the scripts themselves join
anvil.

The discrete carry (conditioning) is read VERBATIM from the mu record's
`sched` field — serve serializes slot ids, statuses, afford bits, pay
classes; the loader never derives them (bit-exact by construction, the
ingestion fork's deciding argument 3). Stores generated before the serve
surface simply carry no conditioning; targets still build.
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from anvil.training.dataset import (  # noqa: E402
    SCHED_CAP,
    SCHED_PAY_NONE,
    SCHED_PAY_UNRESOLVED,
    norm_sa,
)

E_AXES = (
    "untapped_total",
    "chained",
    "untapped_W",
    "untapped_U",
    "untapped_B",
    "untapped_R",
    "untapped_G",
)
SCHED_AXIS_CLAMP = 30.0  # clips at birth (ADR-0056 genre; E/R are counts)
COLORS = "WUBRG"
PRIORITY = "chooseSpellAbilityToPlay"

_TABLE = None


def card_table():
    global _TABLE
    if _TABLE is None:
        from veto_knowability import build_card_table

        _TABLE = build_card_table()
    return _TABLE


def _cmd_extra(obs: dict, seat: int) -> int:
    try:
        return 2 * min(obs["players"][seat]["cmdcast"])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0


def e_axes(obs: dict, seat: int) -> list[float]:
    """The 7 EOT resource axes (v2_target_probe._e_axes verbatim), clamped."""
    from veto_knowability import source_views

    views = source_views(obs, seat, card_table())
    ax = [float(len(views.now)), float(views.chained)]
    ax += [float(sum(1 for s in views.now if c in s)) for c in COLORS]
    return [min(a, SCHED_AXIS_CLAMP) for a in ax]


def afford_count_dec(dec: dict, seat: int) -> tuple[float, float]:
    """Census-convention (affordable-hand count, untapped count) at a stored
    decision window — v2_target_probe._afford_count with opts from the dec."""
    from schedule_census import resolve_cost
    from veto_knowability import can_pay, source_views

    obs = dec["obs"]
    table = card_table()
    ents = {e["e"]: e for e in obs.get("ents", [])}
    views = source_views(obs, seat, table)
    extra_cmd = _cmd_extra(obs, seat)
    seen: set[tuple] = set()
    afford = 0
    for opt in dec.get("opts") or []:
        key = (opt.get("e"), str(opt.get("sa") or "")[:60])
        if key in seen:
            continue
        seen.add(key)
        bucket, cost, extra, _ = resolve_cost(opt, ents, table)
        if bucket == "spell" and ents.get(opt.get("e"), {}).get("z") == "command":
            extra = extra_cmd
        if bucket not in ("spell", "ability") or cost is None:
            continue
        afford += int(can_pay(cost, views.now, extra))
    return (
        min(float(afford), SCHED_AXIS_CLAMP),
        min(float(len(views.now)), SCHED_AXIS_CLAMP),
    )


def pay_summary_class(opt: dict, obs: dict) -> int:
    """Slot payment SUMMARY (m10-build-spec §1): amount bucket 0-4+ ×
    colorless-only/colored (10 classes) + none (free/land) + unresolvable."""
    from schedule_census import cmc, resolve_cost

    ents = {e["e"]: e for e in obs.get("ents", [])}
    bucket, cost, extra, _ = resolve_cost(opt, ents, card_table())
    if bucket not in ("spell", "ability") or cost is None:
        return SCHED_PAY_UNRESOLVED if bucket == "unknown" else SCHED_PAY_NONE
    total = cmc(cost, extra)
    if total >= 10**5:  # the resolve_cost "unparsed" sentinel
        return SCHED_PAY_UNRESOLVED
    if total == 0:
        return SCHED_PAY_NONE
    colored = bool(cost.pips or cost.twobrid)
    return min(total, 4) * 2 + int(colored)


def afford_bit(opt: dict, obs: dict, seat: int) -> float:
    """Per-slot afford bit at a window (census conventions; serve computes,
    serializes into the mu sched field; the loader reads verbatim)."""
    from schedule_census import resolve_cost
    from veto_knowability import can_pay, source_views

    ents = {e["e"]: e for e in obs.get("ents", [])}
    table = card_table()
    bucket, cost, extra, _ = resolve_cost(opt, ents, table)
    if bucket == "spell" and ents.get(opt.get("e"), {}).get("z") == "command":
        extra = _cmd_extra(obs, seat)
    if bucket not in ("spell", "ability") or cost is None:
        return 0.0
    return float(can_pay(cost, source_views(obs, seat, table).now, extra))


def _chosen(dec: dict, rec: dict, aux: dict) -> "tuple[int, str, dict] | None":
    """(wire entity id, normalized sa, wire opt) of the mu-chosen candidate
    at a priority window; None for PASS / unmapped."""
    c = rec.get("c")
    if not c or c <= 0:
        return None
    first_opt = aux["cand_first_opt"]
    if c >= len(first_opt) or first_opt[c] < 0:
        return None
    opt = (dec.get("opts") or [None] * (first_opt[c] + 1))[first_opt[c]]
    if opt is None:
        return None
    return opt.get("e"), norm_sa(opt.get("sa", "")), opt


def sched_annotate(traj, by_seat: dict, counters: dict) -> None:
    """Attach the v2 targets to emission windows (m10-build-spec §4).

    by_seat items are (ex, rec, rej, ex_fv) with loader-private keys already
    on ex: _sched_turn, _dec_idx, _aux. The emission window = the first own
    MAIN1 priority window with obs of the turn (the fork-consistent MAIN1
    rule — the probe's emission point and the sweep's fork window); turns
    without one carry no schedule targets."""
    decs = traj.decisions
    for p, items in by_seat.items():
        by_turn: dict[int, list] = {}
        for ex, rec, _rej, _fv in items:
            by_turn.setdefault(ex["_sched_turn"], []).append((ex, rec))
        for t, wins in by_turn.items():
            emis = next(
                (
                    (ex, rec)
                    for ex, rec in wins
                    if ex["_task_name"] == "priority"
                    and decs[ex["_dec_idx"]]["obs"].get("glob", {}).get("ph") == "MAIN1"
                    and decs[ex["_dec_idx"]]["obs"].get("glob", {}).get("ap") == p
                ),
                None,
            )
            if emis is None:
                continue
            ex_e, _rec_e = emis
            ex_e["_sched_emit"] = True
            emis_idx = ex_e["_dec_idx"]
            emis_dec = decs[emis_idx]
            # emission candidate map: (e, norm_sa) -> candidate index
            cand_of: dict[tuple, int] = {}
            for j, fo in enumerate(ex_e["_aux"]["cand_first_opt"]):
                if j == 0 or fo < 0:
                    continue
                opt = emis_dec["opts"][fo]
                cand_of.setdefault((opt.get("e"), norm_sa(opt.get("sa", ""))), j)
            # realized schedule: chosen actions at own priority windows from
            # the emission window onward, this turn
            slots = []  # (cand_idx or None, is_land, dec_idx)
            for ex, rec in wins:
                if ex["_task_name"] != "priority" or ex["_dec_idx"] < emis_idx:
                    continue
                ch = _chosen(decs[ex["_dec_idx"]], rec, ex["_aux"])
                if ch is None:
                    continue
                e, sa, opt = ch
                j = cand_of.get((e, sa))
                if j is None:
                    counters["unmatched"] = counters.get("unmatched", 0) + 1
                    continue
                slots.append((j, opt.get("kind") == "land", ex["_dec_idx"]))
            tgt = torch.full((SCHED_CAP + 1,), -1, dtype=torch.int64)
            for k, (j, _l, _d) in enumerate(slots[:SCHED_CAP]):
                tgt[k] = j
            if len(slots) < SCHED_CAP:
                tgt[len(slots)] = 0  # STOP
            ex_e["_sched_tgt"] = tgt
            counters["emit"] = counters.get("emit", 0) + 1
            counters["slots"] = counters.get("slots", 0) + len(slots)
            # E: last own obs-bearing dec of the turn
            eot = next(
                (
                    d
                    for d in reversed(decs)
                    if d.get("p") == p and d.get("t") == t and d.get("obs")
                ),
                None,
            )
            if eot is not None:
                ex_e["_sched_e_tgt"] = e_axes(eot["obs"], p)
            # R: ledger at the next own obs-bearing dec after each realized
            # non-land slot (v2_target_probe convention)
            r_tgt = torch.zeros(SCHED_CAP, 2)
            r_valid = torch.zeros(SCHED_CAP, dtype=torch.bool)
            for k, (_j, is_land, didx) in enumerate(slots[:SCHED_CAP]):
                if is_land:
                    continue
                nxt = next(
                    (
                        d
                        for d in decs[didx + 1 :]
                        if d.get("p") == p and d.get("obs")
                    ),
                    None,
                )
                if nxt is None:
                    continue
                afford, untapped = afford_count_dec(nxt, p)
                r_tgt[k, 0] = untapped
                r_tgt[k, 1] = afford
                r_valid[k] = True
            ex_e["_sched_r_tgt"] = r_tgt
            ex_e["_sched_r_valid"] = r_valid


def sched_cond_tensors(sched: dict, row_of: dict) -> dict:
    """Discrete-carry conditioning tensors from a mu record's `sched` field,
    verbatim (rows resolved through the window's own entity join)."""
    from anvil.training.dataset import SCHED_STATUS  # noqa: F401  (doc anchor)

    n = len(sched.get("slots") or [])
    rows = torch.full((SCHED_CAP,), -1, dtype=torch.int64)
    sa = torch.full((SCHED_CAP,), -1, dtype=torch.int64)
    status = torch.zeros(SCHED_CAP, dtype=torch.int64)
    afford = torch.zeros(SCHED_CAP)
    pay = torch.full((SCHED_CAP,), SCHED_PAY_NONE, dtype=torch.int64)
    mask = torch.zeros(SCHED_CAP, dtype=torch.bool)
    st = sched.get("st") or ""
    st_of = {"p": 0, "n": 1, "d": 2, "f": 3}
    for k, (e, sa_id) in enumerate((sched.get("slots") or [])[:SCHED_CAP]):
        rows[k] = row_of.get(e, -1)
        sa[k] = sa_id
        status[k] = st_of.get(st[k] if k < len(st) else "p", 0)
        mask[k] = True
    for k, a in enumerate((sched.get("afford") or [])[:SCHED_CAP]):
        afford[k] = float(a)
    for k, pc in enumerate((sched.get("pay") or [])[:SCHED_CAP]):
        pay[k] = int(pc)
    return {
        "sched_rows": rows,
        "sched_sa": sa,
        "sched_status": status,
        "sched_afford": afford,
        "sched_pay": pay,
        "sched_mask": mask if n else torch.zeros(SCHED_CAP, dtype=torch.bool),
    }
