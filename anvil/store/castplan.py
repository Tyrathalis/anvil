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

    host: int | None            # host card entity id ("e")
    sa: str                     # debug/join string, truncated at 120
    kind: str                   # "land" | "spell" | "ability" | "other"
    targets: list[dict[str, Any]]        # {"e":id} | {"pi":seat} | {"e":id,"stk":1}
    x: int | None
    alt: str | None             # AlternativeCost enum name
    optional_costs: list[str]   # OptionalCost enum names
    multikicker: int
    modes: list["CastPlan"]     # only when bound at decision time
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
    windows: int = 0            # priority decisions seen
    passes: int = 0             # null rets
    casts: int = 0              # CastPlan labels
    with_targets: int = 0
    with_x: int = 0
    with_opt_costs: int = 0
    windows_with_opts: int = 0  # decs that logged structured options
    obs_null: int = 0           # dec had no observation (serializer error)
    winner_mismatch: int = 0    # end.winner != games.jsonl winner (fork 06dd428313)
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
        if self.obs_null:
            lines.append(f"WARNING: {self.obs_null} windows had obs:null")
        if self.winner_mismatch:
            lines.append(f"WARNING: {self.winner_mismatch} games where end.winner "
                         "!= games.jsonl winner — pre-06dd428313 store (readers "
                         "must use winner_seat()) or a regressed fork")
        if self.undecodable:
            lines.append(f"QUARANTINED: {len(self.undecodable)} undecodable frame(s) "
                         "excluded from the corpus:")
            lines.extend("  " + u for u in self.undecodable[:10])
        lines.append("OK" if self.ok else f"{len(self.errors)} ERRORS")
        lines.extend("  " + e for e in self.errors[:50])
        if len(self.errors) > 50:
            lines.append(f"  ... {len(self.errors) - 50} more")
        return "\n".join(lines)


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
        structured = (opts is not None and (not opts or isinstance(opts[0], dict)))
        if structured:
            report.windows_with_opts += 1

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
            pending_play.setdefault(dec.get("p"), []).append((seq, plan))

    for queue in pending_play.values():
        # end-of-game abandonment (hard cap, concession) can strand a tail
        # entry; more than one stranded per seat is a join bug
        if len(queue) > 1:
            report.error(g, queue[0][0],
                         f"{len(queue)} cast labels never matched a {PLAY_METHOD} window")


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
