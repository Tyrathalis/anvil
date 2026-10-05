"""CastPlan label parsing + validation (M1 D2, observation-schema-v1 amendment).

The Java worker serializes the heuristic's chosen SpellAbility into a
CastPlan-shaped ret record on every priority window (and any other callback
that answers with a SpellAbility). This module is the Python contract for that
shape: a parser into a dataclass and a validator that checks each label
against its own decision record — the D2 sanity gate.

Validator checks, per priority decision:
  1. parse       — a non-null ret parses as a list of CastPlan objects.
  2. host        — each plan's host entity appears in the decision's own
                   observation (ents or stack).
  3. targets     — every {"e"} target ref is an observed entity/stack host id;
                   every {"pi"} ref is a valid seat index.
  4. opts        — when structured opts were logged, the chosen host id is one
                   of the option host ids (pass = null ret is always valid;
                   options are base SAs, so matching is at host-entity level —
                   an optional-cost copy keeps its host). Options are
                   TIMING-LEGAL CANDIDATES, not payable actions (M1 D3:
                   payability needs target/X context the scan can't have —
                   the set is a superset of the expert's castable actions by
                   construction; affordability is learned, and the gate
                   metric's single-legal-option exclusion is defined on this
                   candidate basis).
  5. play match  — the next playChosenSpellAbility window for the same seat
                   names the same SA (string prefix match; the census arg is
                   truncated at 60 chars, the label at 120).

Everything here is read-only over a TrajectoryStore; Magic stays data (kind
strings, cost names are opaque vocabularies per the schema's hygiene rule).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Iterator

from anvil.store.trajectories import GameTrajectory, TrajectoryStore

PRIORITY_METHOD = "chooseSpellAbilityToPlay"
PLAY_METHOD = "playChosenSpellAbility"


@dataclasses.dataclass
class CastPlan:
    """One chosen SpellAbility, decision-time state read off the SA."""

    host: int | None  # host card entity id ("e")
    sa: str  # debug/join string, truncated at 120
    kind: str  # "land" | "spell" | "ability" | "other"
    targets: list[dict[str, Any]]  # {"e":id} | {"pi":seat} | {"e":id,"stk":1}
    x: int | None
    alt: str | None  # AlternativeCost enum name
    optional_costs: list[str]  # OptionalCost enum names
    multikicker: int
    modes: list["CastPlan"]  # only when bound at decision time
    subs: list[dict[str, Any]]  # [{"i":chain_index,"tgt":[...]}]

    @property
    def all_target_refs(self) -> Iterator[dict[str, Any]]:
        yield from self.targets
        for s in self.subs:
            yield from s.get("tgt", [])
        for m in self.modes:
            yield from m.all_target_refs


def parse_plan(v: dict[str, Any]) -> CastPlan:
    return CastPlan(
        host=v.get("e"),
        sa=v.get("sa", ""),
        kind=v.get("kind", "other"),
        targets=v.get("tgt", []),
        x=v.get("x"),
        alt=v.get("alt"),
        optional_costs=v.get("opt", []),
        multikicker=v.get("mk", 0),
        modes=[parse_plan(m) for m in v.get("modes", [])],
        subs=v.get("sub", []),
    )


def parse_ret(ret: Any) -> list[CastPlan] | None:
    """A priority ret: None = pass; else the chosen SA list (usually one)."""
    if ret is None:
        return None
    if isinstance(ret, dict):  # defensive: a bare object instead of a list
        ret = [ret]
    if not isinstance(ret, list):
        raise ValueError(f"priority ret is neither null nor a list: {ret!r}")
    return [parse_plan(v) for v in ret]


@dataclasses.dataclass
class ValidationReport:
    games: int = 0
    windows: int = 0  # priority decisions seen
    passes: int = 0  # null rets
    casts: int = 0  # CastPlan labels
    with_targets: int = 0
    with_x: int = 0
    with_opt_costs: int = 0
    windows_with_opts: int = 0  # decs that logged structured options
    obs_null: int = 0  # dec had no observation (serializer error)
    winner_mismatch: int = 0  # end.winner != games.jsonl winner (fork 06dd428313)
    # ADR-0122 — the union target mask's AGREEMENT CHECK (the go/no-go): every
    # heuristic-chosen target must lie inside its option's listed set. An
    # outside target is an error (the gate is exactly zero); an option the
    # fork declined to enumerate ("tg":null) is counted, not checked.
    mask_opts_masked: int = 0
    mask_opts_unmasked: int = 0
    mask_opts_legacy: int = 0  # options without the field (pre-mask records)
    mask_targets_checked: int = 0
    mask_targets_outside: int = 0
    mask_unfit_chosen: int = 0  # a cast on an option the fork flagged unfit
    mask_mode_targets_unchecked: int = 0  # mode targets live outside the decoder's label space
    # a label ref on an option the engine says targets nothing ("tg":[] with
    # "tn":0): a stale TargetChoices on the heuristic's SA, not a legal target
    # the mask excluded — counted apart (a label-side defect), not an error
    mask_refs_on_nontargeting: int = 0
    # a label ref the ENGINE refused at record time ("ill":1 on the ref: the
    # fork's canTarget verdict): the heuristic's own illegal pick (Explore
    # onto a shrouded creature, divided damage at a hexproof player) — not a
    # legal target the mask excluded; counted apart, listed by ability
    mask_label_illegal: int = 0
    mask_label_illegal_by_sa: dict = dataclasses.field(default_factory=dict)
    mask_unmasked_reasons: dict = dataclasses.field(default_factory=dict)
    mask_outside_by_sa: dict = dataclasses.field(default_factory=dict)
    errors: list[str] = dataclasses.field(default_factory=list)
    # frames that fail to decode (e.g. a hard-capped game killed mid-write):
    # quarantined — excluded from the corpus, reported loudly, but not label
    # errors (an unreadable frame can't poison training; it can't be read)
    undecodable: list[str] = dataclasses.field(default_factory=list)

    def error(self, game: int, seq: int, msg: str) -> None:
        self.errors.append(f"game {game} s={seq}: {msg}")

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        lines = [
            f"{self.games} games, {self.windows} priority windows: "
            f"{self.passes} pass, {self.casts} cast labels "
            f"({self.with_targets} targeted, {self.with_x} with X, "
            f"{self.with_opt_costs} with optional costs); "
            f"{self.windows_with_opts} windows logged options",
        ]
        if self.mask_opts_masked or self.mask_opts_unmasked:
            lines.append(
                f"target mask (ADR-0122): {self.mask_opts_masked} options masked, "
                f"{self.mask_opts_unmasked} unmasked {dict(sorted(self.mask_unmasked_reasons.items()))}, "
                f"{self.mask_opts_legacy} legacy; {self.mask_targets_checked} chosen targets checked, "
                f"{self.mask_targets_outside} OUTSIDE the mask, {self.mask_unfit_chosen} casts on unfit "
                f"options, {self.mask_mode_targets_unchecked} mode targets not in the label space, "
                f"{self.mask_refs_on_nontargeting} label refs on non-targeting options (label-side), "
                f"{self.mask_label_illegal} label refs the engine itself refused (the heuristic's illegal picks)"
            )
            if self.mask_label_illegal_by_sa:
                top = sorted(self.mask_label_illegal_by_sa.items(), key=lambda kv: -kv[1])[:10]
                lines.append("  engine-illegal labels by ability: " + "; ".join(f"{k!r} x{v}" for k, v in top))
            if self.mask_outside_by_sa:
                top = sorted(self.mask_outside_by_sa.items(), key=lambda kv: -kv[1])[:15]
                lines.append("  outside by ability: " + "; ".join(f"{k!r} x{v}" for k, v in top))
        if self.obs_null:
            lines.append(f"WARNING: {self.obs_null} windows had obs:null")
        if self.winner_mismatch:
            lines.append(
                f"WARNING: {self.winner_mismatch} games where end.winner "
                "!= games.jsonl winner — pre-06dd428313 store (readers "
                "must use winner_seat()) or a regressed fork"
            )
        if self.undecodable:
            lines.append(
                f"QUARANTINED: {len(self.undecodable)} undecodable frame(s) "
                "excluded from the corpus:"
            )
            lines.extend("  " + u for u in self.undecodable[:10])
        lines.append("OK" if self.ok else f"{len(self.errors)} ERRORS")
        lines.extend("  " + e for e in self.errors[:50])
        if len(self.errors) > 50:
            lines.append(f"  ... {len(self.errors) - 50} more")
        return "\n".join(lines)


def _chosen_option(dec: dict[str, Any], opts: list, plan: CastPlan) -> dict[str, Any] | None:
    """The option entry the plan realized: the exact "oi" when logged, else
    the host's single option, else the host option whose text prefixes the
    plan's (the loader's join order)."""
    oi = dec.get("oi")
    if oi is not None and 0 <= oi < len(opts) and isinstance(opts[oi], dict):
        return opts[oi]
    same = [o for o in opts if isinstance(o, dict) and o.get("e") == plan.host]
    if len(same) == 1:
        return same[0]
    psa = plan.sa or ""
    for o in same:
        osa = o.get("sa") or ""
        n = min(len(osa), len(psa))
        if n and osa[:n] == psa[:n]:
            return o
    return None


def _tally_mask_options(report: ValidationReport, opts: list) -> None:
    for o in opts:
        if not isinstance(o, dict) or "tg" not in o:
            report.mask_opts_legacy += 1
        elif o["tg"] is None:
            report.mask_opts_unmasked += 1
            why = str(o.get("tu", "?"))
            report.mask_unmasked_reasons[why] = report.mask_unmasked_reasons.get(why, 0) + 1
        else:
            report.mask_opts_masked += 1


def _check_mask(report: ValidationReport, g: int, seq: int, opt: dict[str, Any], plan: CastPlan) -> None:
    """ADR-0122: the plan's root-chain targets (tgt + subs — the decoder's
    label space; mode targets are counted, not checked) against the option's
    union. Only called for an option that carries a non-null "tg"."""
    tg = opt.get("tg") or []
    ents = {r["e"] for r in tg if isinstance(r, dict) and "e" in r}
    seats = {r["pi"] for r in tg if isinstance(r, dict) and "pi" in r}
    label = (opt.get("sa") or plan.sa or "")[:60]
    refs = list(plan.targets)
    for sb in plan.subs:
        refs.extend(sb.get("tgt") or [])
    if not tg and not opt.get("tn") and not opt.get("tz") and refs:
        # the engine found no targeting node at all: the label's refs are
        # stale TargetChoices (the realizer refuses any ref here), not targets
        report.mask_refs_on_nontargeting += len(refs)
        report.mask_mode_targets_unchecked += sum(len(m.targets) for m in plan.modes)
        return
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        if ref.get("ill"):
            report.mask_label_illegal += 1
            report.mask_label_illegal_by_sa[label] = report.mask_label_illegal_by_sa.get(label, 0) + 1
            continue
        if "e" in ref:
            ok = ref["e"] in ents
        elif "pi" in ref:
            ok = ref["pi"] in seats
        else:
            continue  # "str" refs: unpointable, skipped by the label path too
        report.mask_targets_checked += 1
        if not ok:
            report.mask_targets_outside += 1
            report.mask_outside_by_sa[label] = report.mask_outside_by_sa.get(label, 0) + 1
            report.error(g, seq, f"target {ref} outside the mask of {label!r} ({len(tg)} refs)")
    report.mask_mode_targets_unchecked += sum(len(m.targets) for m in plan.modes)
    if opt.get("tz"):
        # an unfit option (a required node with no legal candidate) cast with
        # targets the engine itself refused CONFIRMS the flag — the heuristic's
        # illegal pick (counted above); cast with a target the engine accepts,
        # the flag was wrong: an error of the outside-target rank
        checked = [r for r in refs if isinstance(r, dict) and ("e" in r or "pi" in r)]
        if checked and all(r.get("ill") for r in checked):
            return
        report.mask_unfit_chosen += 1
        report.error(g, seq, f"cast on an option the fork flagged unfit: {label!r}")


def _observed_ids(obs: dict[str, Any]) -> set[int]:
    ids = {e["e"] for e in obs.get("ents", [])}
    ids.update(s["e"] for s in obs.get("stack", []) if "e" in s)
    return ids


def validate_game(traj: GameTrajectory, report: ValidationReport) -> None:
    g = traj.game_index
    n_players = len(traj.header.get("players", []))
    # per-seat queues of (seq, plan) awaiting their playChosenSpellAbility
    # window (both seats' windows interleave in the record stream)
    pending_play: dict[int, list[tuple[int, CastPlan]]] = {}

    for dec in traj.decisions:
        if dec["m"] == PLAY_METHOD:
            queue = pending_play.get(dec.get("p"))
            if queue:  # a playChosen with no pending label is another play path
                seq, plan = queue.pop(0)
                played = (dec.get("args") or {}).get("sa") or ""
                n = min(len(played), len(plan.sa))
                if n and played[:n] != plan.sa[:n]:
                    report.error(g, seq, f"label {plan.sa[:60]!r} != played {played[:60]!r}")
            continue
        if dec["m"] != PRIORITY_METHOD:
            continue

        report.windows += 1
        seq = dec["s"]
        obs = dec.get("obs")
        if obs is None:
            report.obs_null += 1
        opts = dec.get("opts")
        structured = opts is not None and (not opts or isinstance(opts[0], dict))
        if structured:
            report.windows_with_opts += 1
            _tally_mask_options(report, opts)

        try:
            plans = parse_ret(dec.get("ret"))
        except ValueError as e:
            report.error(g, seq, str(e))
            continue
        if plans is None:
            report.passes += 1
            continue

        for plan in plans:
            report.casts += 1
            if plan.targets or plan.subs:
                report.with_targets += 1
            if plan.x is not None:
                report.with_x += 1
            if plan.optional_costs or plan.multikicker:
                report.with_opt_costs += 1

            if obs is not None:
                ids = _observed_ids(obs)
                if plan.host is not None and plan.host not in ids:
                    report.error(g, seq, f"host e={plan.host} not in observation")
                for ref in plan.all_target_refs:
                    if "e" in ref and ref["e"] not in ids:
                        report.error(g, seq, f"target e={ref['e']} not in observation")
                    if "pi" in ref and not (0 <= ref["pi"] < n_players):
                        report.error(g, seq, f"target pi={ref['pi']} out of range")
            if structured and plan.host is not None:
                if plan.host not in {o.get("e") for o in opts}:
                    report.error(g, seq, f"chosen e={plan.host} not among {len(opts)} options")
                opt = _chosen_option(dec, opts, plan)
                if opt is not None and opt.get("tg") is not None:
                    _check_mask(report, g, seq, opt, plan)
            pending_play.setdefault(dec.get("p"), []).append((seq, plan))

    for queue in pending_play.values():
        # end-of-game abandonment (hard cap, concession) can strand a tail
        # entry; more than one stranded per seat is a join bug
        if len(queue) > 1:
            report.error(
                g, queue[0][0], f"{len(queue)} cast labels never matched a {PLAY_METHOD} window"
            )


def validate(store: TrajectoryStore, limit: int | None = None) -> ValidationReport:
    report = ValidationReport()
    for g in store.game_indices():
        try:
            traj = store.game(g)
        except Exception as e:  # truncated/corrupt frame: quarantine, keep going
            report.undecodable.append(f"game {g}: {type(e).__name__}: {str(e)[:80]}")
            continue
        validate_game(traj, report)
        # winner cross-check (2026-07-11 lesson: two records encoding the same
        # fact must be compared somewhere). Pre-fix stores fail this ~50% of
        # games (end.winner from the post-elimination live list — fork
        # 06dd428313); readers must use winner_seat(), so a mismatch is an
        # error only for stores generated after the fix would exist — flag all,
        # loudly, so a regressed fork can't ship a poisoned corpus again.
        w_true = store.winner_seat(g)
        w_end = (traj.end or {}).get("winner", -1)
        if w_true is not None and w_end != w_true:
            report.winner_mismatch += 1
        report.games += 1
        if limit is not None and report.games >= limit:
            break
    return report
