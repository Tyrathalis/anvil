"""M10 v2 serve-side schedule carry — revise-on-trigger (m10-build-spec §3).

One SchedServe per ModelBackend. Per (g, seat) it holds the live discrete
schedule for the CURRENT own turn: slots decoded by the model's emission
head at the first own MAIN1 priority window, statuses advanced as answers
execute, revisions ONLY at the four engine-detectable triggers
(1 veto/`retry_of`, 2 ANY opponent action resolved during our turn,
3 END_OF_TURN entry, 4 schedule exhausted — user pins 2026-08-27).
Unprovoked revision is structurally impossible: the decode runs only when
`decode` was set by emission-or-trigger logic.

Serve/loader parity: whatever conditioning is FED here is serialized
verbatim into the mu row's `sched` field (slots, statuses, afford bits,
pay classes, rev) — the loader reconstructs bit-exactly and never derives.
Emission/revision rows additionally record the NEWLY decoded schedule
(`new`, `trigger`); the fed part is what conditioning reconstruction uses.

Trigger detectors are honest approximations where the wire is (recorded in
the spec): trigger 2 reads the K=8 rolling wire-history's non-self
signature (missed-trigger residual = the canonical-register instrument's
territory); trigger 1 rides the bridge's `retry_of` re-ask marker.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field

import torch

from anvil.training.dataset import (
    SCHED_CAP,
    SCHED_PAY_NONE,
    norm_sa,
)

ST_CHR = {0: "p", 1: "n", 2: "d", 3: "f"}
CHR_ST = {v: k for k, v in ST_CHR.items()}
END_PHASE = "END_OF_TURN"


@dataclass
class _Slot:
    e: int
    sa_id: int
    sa: str
    opt: dict
    pay: int
    st: str = "p"  # p/n/d/f


@dataclass
class _State:
    turn: int
    slots: list = field(default_factory=list)
    rev: int = 0
    opp_sig: tuple = ()
    awaiting: "int | None" = None  # slot idx our last answer executed
    pending_revise: "str | None" = None
    eot_fired: bool = False
    exhaust_fired: bool = False

    def next_idx(self) -> "int | None":
        return next((i for i, s in enumerate(self.slots) if s.st == "n"), None)

    def advance_next(self) -> None:
        if self.next_idx() is None:
            for s in self.slots:
                if s.st == "p":
                    s.st = "n"
                    return


class SchedServe:
    def __init__(self, feat):
        self.feat = feat
        self.states: dict[tuple, _State] = {}
        self.lock = threading.Lock()
        self.counts: Counter = Counter()
        self._cap = 4096

    # ---------------------------------------------------------------- inject

    def inject(self, ex: dict, aux: dict, dec: dict, header: dict, task: str) -> "dict | None":
        """Pre-forward hook: status updates, trigger latching, conditioning
        feed. Returns a ctx dict (or None when the schedule surface is idle
        at this window — off-turn, no obs, dead turn)."""
        obs = dec.get("obs")
        if not obs:
            return None
        p = dec.get("p", -1)
        glob = obs.get("glob", {})
        if glob.get("ap") != p:
            return None  # off-turn: the hold-set's territory, no schedule
        key = (header["g"], p)
        turn = dec.get("t", 0)
        with self.lock:
            st = self.states.get(key)
        if st is not None and st.turn != turn:
            st = None  # within-turn object; a new turn starts fresh
        ph = glob.get("ph")

        if st is not None:
            # -- status advance for the previously answered scheduled slot
            if st.awaiting is not None:
                if dec.get("retry_of") or ex.get("_retry"):
                    st.slots[st.awaiting].st = "f"
                    st.pending_revise = st.pending_revise or "veto"
                    self.counts["sched_slot_failed"] += 1
                else:
                    st.slots[st.awaiting].st = "d"
                    st.advance_next()
                    self.counts["sched_slot_done"] += 1
                st.awaiting = None
            # -- trigger 2: ANY opponent action resolved during our turn.
            # An opponent PRIORITY entry with no host is their PASS answer —
            # not an action (the serve smoke measured 485 pass-driven fires
            # in 4 games before this filter); real opponent actions are
            # priority entries WITH a host (casts/activations) and any
            # non-priority method (blocks, triggers, ...).
            from anvil.bridge.featurize import PRIORITY as _PRIO
            from anvil.bridge.featurize import wire_history

            sig = tuple(
                (h["m"], h["e"])
                for h in wire_history(dec.get("hist"), p)
                if not h["self"] and not (h["m"] == _PRIO and h["e"] < 0)
            )
            if sig != st.opp_sig:
                if st.opp_sig or sig:
                    st.pending_revise = st.pending_revise or "opp"
                st.opp_sig = sig
            # -- trigger 3: end-step entry (once per turn)
            if ph == END_PHASE and not st.eot_fired:
                st.eot_fired = True
                st.pending_revise = st.pending_revise or "eot"
            # -- trigger 4: schedule exhausted (once per exhaustion)
            if (
                st.slots
                and all(s.st in ("d", "f") for s in st.slots)
                and not st.exhaust_fired
            ):
                st.exhaust_fired = True
                st.pending_revise = st.pending_revise or "exhaust"

        decode = False
        trigger = None
        if task == "priority":
            if st is None and ph == "MAIN1":
                decode, trigger = True, "emit"
            elif st is not None and st.pending_revise:
                decode, trigger = True, st.pending_revise

        fed = None
        mark = None
        if st is not None:
            fed = self._feed(ex, aux, dec, p, st)
            if task == "pay_class":
                mark = self._pay_mark(ex, dec, p, st)
                if mark is not None:
                    fed["mark"] = mark
        return {
            "key": key,
            "state": st,
            "fed": fed,
            "decode": decode,
            "trigger": trigger,
            "turn": turn,
            "p": p,
            "mark": mark,
        }

    def _pay_mark(self, ex: dict, dec: dict, p: int, st: _State) -> "int | None":
        """The schedule-consistent goal option (actuation pin 1): the
        explicit option maximizing how many remaining scheduled slots stay
        affordable after its taps, tie-broken most-flexible-spare (most
        untapped sources left). Marked as a candidate FEATURE — the pay
        head keeps authority; follow/deviate is telemetry. None when the
        schedule has no remaining slots or no explicit options exist."""
        import json as _json

        import torch

        from anvil.training.sched_targets import slot_afford, source_views_of

        remaining = [s for s in st.slots if s.st in ("p", "n")]
        if not remaining:
            return None
        obs = dec["obs"]
        opts = dec.get("opts") or []
        best = None  # (feasible, spare, -idx)
        for i, lab in enumerate(opts):
            if i == 0:
                continue  # option 0 = auto: the default, never the mark
            try:
                o = _json.loads(lab) if isinstance(lab, str) else (lab or {})
            except ValueError:
                o = {}
            tapped = set(o.get("ents") or [])
            obs_after = {**obs, "ents": [e for e in obs.get("ents", [])
                                         if e.get("e") not in tapped]}
            views = source_views_of(obs_after, p)
            feasible = sum(
                int(slot_afford(s.opt, obs_after, p, views)) for s in remaining
            )
            key = (feasible, len(views.now), -i)
            if best is None or key > best[0]:
                best = (key, i)
        if best is None:
            return None
        idx = best[1]
        cw = ex["cand_rows"].shape[0]
        if idx >= cw:
            return None
        pm = torch.zeros(cw)
        pm[idx] = 1.0
        ex["cand_paymark"] = pm
        self.counts["sched_paymark_set"] += 1
        return idx

    def _feed(self, ex: dict, aux: dict, dec: dict, p: int, st: _State) -> dict:
        """Fill ex's sched_* keys from the live state; return the verbatim
        mu serialization of what was fed (bit-exact loader contract)."""
        from anvil.training.sched_targets import slot_afford, source_views_of

        views = source_views_of(dec["obs"], p)
        row_of = aux["row_of"]
        rows = torch.full((SCHED_CAP,), -1, dtype=torch.int64)
        sa = torch.full((SCHED_CAP,), -1, dtype=torch.int64)
        status = torch.zeros(SCHED_CAP, dtype=torch.int64)
        afford = torch.zeros(SCHED_CAP)
        pay = torch.full((SCHED_CAP,), SCHED_PAY_NONE, dtype=torch.int64)
        mask = torch.zeros(SCHED_CAP, dtype=torch.bool)
        aff_list = []
        for k, s in enumerate(st.slots[:SCHED_CAP]):
            rows[k] = row_of.get(s.e, -1)
            sa[k] = s.sa_id
            status[k] = CHR_ST[s.st]
            a = slot_afford(s.opt, dec["obs"], p, views)
            afford[k] = a
            aff_list.append(int(a))
            pay[k] = s.pay
            mask[k] = True
        ex.update(
            sched_rows=rows,
            sched_sa=sa,
            sched_status=status,
            sched_afford=afford,
            sched_pay=pay,
            sched_mask=mask,
        )
        return {
            "slots": [[s.e, s.sa_id] for s in st.slots[:SCHED_CAP]],
            "st": "".join(s.st for s in st.slots[:SCHED_CAP]),
            "afford": aff_list,
            "pay": [s.pay for s in st.slots[:SCHED_CAP]],
            "rev": st.rev,
        }

    # ----------------------------------------------------------------- after

    def after(self, ctx: dict, out: dict, aux: dict, dec: dict) -> "dict | None":
        """Post-forward hook: consume the decode at emission/revision
        windows, track the answered action vs the NEXT slot, and return the
        mu `sched` row (fed part + emission record)."""
        if ctx is None:
            return None
        st = ctx["state"]
        row = dict(ctx["fed"]) if ctx["fed"] else {}
        if ctx["decode"] and "sched_picks" in out:
            new_slots = self._decode_slots(out, aux, dec, ctx["p"])
            noop = st is not None and [(s.e, s.sa_id) for s in new_slots] == [
                (s.e, s.sa_id) for s in st.slots if s.st in ("p", "n")
            ]
            rev = (st.rev + 1) if st is not None else 0
            ns = _State(turn=ctx["turn"], slots=new_slots, rev=rev)
            if new_slots:
                new_slots[0].st = "n"
            ns.opp_sig = st.opp_sig if st is not None else ()
            ns.eot_fired = st.eot_fired if st is not None else False
            with self.lock:
                self.states[ctx["key"]] = ns
                while len(self.states) > self._cap:
                    self.states.pop(next(iter(self.states)))
            st = ns
            ctx["state"] = ns
            row.update(
                emit=1,
                rev=rev,
                trigger=ctx["trigger"],
                new=[[s.e, s.sa_id] for s in new_slots],
            )
            self.counts["sched_emit"] += 1
            self.counts[f"sched_rev_{ctx['trigger']}"] += 1
            if noop:
                self.counts["sched_noop_rev"] += 1
            self.counts["sched_len_" + str(len(new_slots))] += 1
            if not new_slots:
                self.counts["sched_pure_hold"] += 1
        elif row:
            row["emit"] = 0

        # -- marked-candidate follow telemetry (pay windows)
        if ctx.get("mark") is not None and "choice" in out:
            if int(out["choice"][0]) == ctx["mark"]:
                self.counts["sched_paymark_follow"] += 1
            else:
                self.counts["sched_paymark_deviate"] += 1

        # -- answered action vs the plan (priority windows with a live state)
        if st is not None and "choice" in out and dec.get("m") == "chooseSpellAbilityToPlay":
            c = int(out["choice"][0])
            if c > 0:
                first_opt = aux["cand_first_opt"]
                opt = (
                    dec["opts"][first_opt[c]]
                    if c < len(first_opt) and first_opt[c] >= 0
                    else None
                )
                if opt is not None:
                    ekey = (opt.get("e"), norm_sa(opt.get("sa", "")))
                    ni = st.next_idx()
                    if ni is not None and ekey == (st.slots[ni].e, st.slots[ni].sa):
                        st.awaiting = ni
                        self.counts["sched_follow"] += 1
                    elif any(
                        s.st == "p" and ekey == (s.e, s.sa) for s in st.slots
                    ):
                        self.counts["sched_dev_later_slot"] += 1
                    else:
                        self.counts["sched_dev_off_plan"] += 1
        return row or None

    def _decode_slots(self, out: dict, aux: dict, dec: dict, p: int) -> list:
        from anvil.training.sched_targets import pay_summary_class

        picks = out["sched_picks"][0].tolist()
        first_opt = aux["cand_first_opt"]
        slots: list[_Slot] = []
        for c in picks:
            if c == 0:
                break
            if c >= len(first_opt) or first_opt[c] < 0:
                continue
            opt = dec["opts"][first_opt[c]]
            sa = norm_sa(opt.get("sa", ""))
            slots.append(
                _Slot(
                    e=opt.get("e", -1),
                    sa_id=self.feat.sa_vocab.id(sa),
                    sa=sa,
                    opt=opt,
                    pay=pay_summary_class(opt, dec["obs"]),
                )
            )
        return slots
