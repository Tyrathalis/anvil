"""M10 reset Fork 3 — INLINE certification, the Python side (m10-reset-draft
§D.3, adjudicated 2026-09-03; built 2026-09-04 after the day-zero HALT
adjudication: better labels before any training).

The generation worker's rollout monitor asks the bridge at a quiescent MAIN1
fork point: "here are the seat's options — which schedule arms?" (tag
`anvil.certify`, the option labels in the Census.str basis + a peek record
with the window's obs and structured opts). This module answers: the rate
gate (deterministic in (game seed, turn, seat) so a replayed game asks and
answers identically), the eligibility rule and the arm enumeration —
schedule_sweep.eligible_turns / build_arms REUSED verbatim, so an inline arm
set is what the ceiling sweep and the mint would have enumerated at the same
window. Arms come back as ordered OPTION-INDEX lists (armId = position + 1;
the natural line is implicit, arm 0). Empty = no rollouts at this window.

Uniform sampling for probe7 (fresh labels comparable with era zero); the
`weight` hook is where the pivotal-moment head / value-band weighting plug
in later (draft §D.3 "smart sampling is strictly easier inline").
"""

from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

CERTIFY_TAG = "anvil.certify"
MIN_AFFORDABLE = 2  # eligible_turns' rule: a turn with < 2 affordable casts has nothing to schedule


def accept(rate: float, game_seed: int, turn: int, seat: int, salt: int = 0) -> bool:
    """The rate gate: a pure function of (game seed, turn, seat, salt) so the
    decision replays; rate 0 = off, 1 = every eligible window."""
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    h = hashlib.blake2b(f"{game_seed}:{turn}:{seat}:{salt}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") / 2**64 < rate


def window_cands(peek: dict, seat: int, table) -> list[dict]:
    """eligible_turns' per-candidate rows for one window from the peek record
    (obs + structured opts): (label, cmc, afford, mana_producer,
    instant_speed) per distinct spell/ability option; `idx` = the option's
    position in the worker's option list (the wire index)."""
    from schedule_census import cmc, resolve_cost
    from veto_knowability import can_pay, source_views

    obs = peek["obs"]
    ents = {e["e"]: e for e in obs.get("ents", [])}
    try:
        cmd_extra = 2 * min(obs["players"][seat]["cmdcast"])
    except (KeyError, IndexError, TypeError, ValueError):
        cmd_extra = 0
    views = source_views(obs, seat, table)
    seen: set[tuple] = set()
    cands = []
    for idx, opt in enumerate(peek.get("opts") or []):
        key = (opt.get("e"), str(opt.get("sa") or "")[:60])
        if key in seen:
            continue
        seen.add(key)
        bucket, cost, extra, name = resolve_cost(opt, ents, table)
        if bucket == "spell" and ents.get(opt.get("e"), {}).get("z") == "command":
            extra = cmd_extra
        if bucket not in ("spell", "ability") or cost is None:
            continue
        label = str(opt.get("sa") or "")[:60]
        if "\t" in label or "\n" in label:
            continue
        card = table.get(name)
        cands.append({
            "idx": idx,
            "label": label,
            "cmc": cmc(cost, extra),
            "afford": can_pay(cost, views.now, extra),
            "mana_producer": bool(card and card.prod),
            "instant_speed": bool(card and (
                "Instant" in (card.types or "") or "Flash" in (card.keywords or ""))),
        })
    return cands


class Certifier:
    def __init__(self, rate: float, arm_cap: int | None = None, salt: int = 0, table=None):
        import sched_pins as pins

        self.rate = float(rate)
        self.arm_cap = int(arm_cap or pins.ARM_CAP)
        self.salt = salt
        self._table = table
        self.counts: Counter = Counter()

    @property
    def table(self):
        if self._table is None:
            from anvil.training.sched_targets import card_table

            self._table = card_table()
        return self._table

    def arms(self, peek: dict, labels: list[str], game_seed: int) -> list[list[int]]:
        """-> ordered option-index lists (may be empty = no rollouts). `labels`
        = the worker's option labels (Census.str), index-aligned with
        peek['opts']; arms are built in the label basis (build_arms) and
        mapped back to indices first-fit — the executor's own label-match
        convention (ScheduleDirective executes by label)."""
        from schedule_sweep import build_arms

        turn = int(peek.get("t", 0))
        seat = int(peek.get("p", -1))
        self.counts["asked"] += 1
        if not accept(self.rate, game_seed, turn, seat, self.salt):
            self.counts["declined_rate"] += 1
            return []
        cands = window_cands(peek, seat, self.table)
        afford = [c for c in cands if c["afford"]]
        if len(afford) < MIN_AFFORDABLE:
            self.counts["ineligible"] += 1
            return []
        row = {"g": game_seed & 0x7FFFFFFF, "t": turn, "cands": afford}
        seqs = build_arms(row)[: self.arm_cap]
        idx_of: dict[str, int] = {}
        for i, lab in enumerate(labels):
            idx_of.setdefault(str(lab or "")[:60], i)
        out: list[list[int]] = []
        for seq in seqs:
            idxs = []
            for lab in seq:
                i = idx_of.get(lab)
                if i is None:
                    self.counts["label_unmapped"] += 1
                    idxs = None
                    break
                idxs.append(i)
            if idxs is not None:
                out.append(idxs)
        if not out:
            self.counts["no_arms"] += 1
            return []
        self.counts["certified_points"] += 1
        self.counts["arms"] += len(out)
        return out
