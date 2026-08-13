"""Standing post-run analysis battery (docs/design/run-analysis-protocol.md).

Battery v1 (2026-08-12) = the ADR-0049 attribution instruments
productionized + monitor/eval diagnostics. Two protocol rules govern
everything here: (1) DIAGNOSTIC ONLY — findings are exploratory, run
verdicts come from pre-registered gates and nothing else; (2) MECHANIZED —
the selfplay driver and scripts/final_read.py call this automatically, the
report leads with ANOMALIES, and the same lines ride the completion
notification. Battery failures never block a run: callers go through
emit_* wrappers that catch, narrate, and continue.

Instruments:

- MONITOR CURVES: per-iteration series from monitor.jsonl (ent / kl_mu /
  veto / first-veto / casts-per-game / rej / reward-vs-v0 / gen_s /
  train_s / turns). Encoded anomaly: kl_mu final/first > 3 (the ADR-0049
  read-1 shape), entropy decline > 30%, veto range > 2x median — prompts
  to look, not verdicts (ADR-0017 guards remain the halting layer).

- HOLDING READ (ADR-0049 read 3): store walk, no model. A castable
  instance = a priority window whose opts include a kind=="spell"
  candidate. v1 definitions are CANDIDACY-based, not affordability-based
  (opts are timing-legal per ADR-0005; payability is unknowable from the
  mask), so absolute rates are upper bounds on deliberate holding and the
  instrument is the COMPARATIVE read across iterations/ckpts — the same
  caveat ADR-0049 recorded. Emitted per seat class (mu-covered = model,
  else heuristic): window hold rate; same-turn hold-then-cast rate
  (realized casts whose entity was passed on earlier in the same turn);
  hold-horizon distribution per (game, seat, entity) — turns from first
  candidacy to realized cast (never-cast tracked separately).

- BEHAVIORAL DELTA (ADR-0049 read 2): two ckpts forwarded over the same
  stored multi-candidate priority windows (raw policy logits, no pass
  offset — the RL serve basis). Agreement, cast-changed rate on windows
  where the REFERENCE ckpt casts, cast->pass fraction of those changes,
  KL(ref||new) median/p90. Reference vs itself is the positive-control
  zero (validated on the d3-rebaseline baseline read).

- EVAL READ: headline from the arms report json + seed-half consistency
  (the run12 lesson mechanized: game-index-parity halves disagreeing
  beyond 2x their pooled SE is flagged), turns distribution, status
  census, per-model-deck winrate spread.

CLI (all subcommands also importable):
  uv run python -m anvil.evals.battery holding <store> [<store> ...]
  uv run python -m anvil.evals.battery delta --ref <ckpt> --new <ckpt> --stores <spec>
  uv run python -m anvil.evals.battery eval-read --name X --arm-dirs a,b --report r.json
  uv run python -m anvil.evals.battery run-end --run-dir data/training/<name>
"""

from __future__ import annotations

import argparse
import json
import statistics
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------- plumbing


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def emit(fn: Callable[..., Any], *args, **kwargs) -> Any:
    """Diagnostics never block the run they describe: catch, narrate, go on."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        print(f"[battery] {fn.__name__} FAILED (run continues):")
        traceback.print_exc()
        return None


def _write_report(out_dir: Path, title: str, anomalies: list[str], sections: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "", "## ANOMALIES", ""]
    lines += [f"- {a}" for a in anomalies] if anomalies else ["- none"]
    for s in sections:
        lines += ["", s]
    (out_dir / "analysis.md").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------- monitor curves

MONITOR_SERIES = [
    ("rl.mean.ent", "entropy"),
    ("rl.mean.kl_mu", "kl_mu"),
    ("census.veto_rate", "veto rate"),
    ("census.first_veto_rate", "first-veto rate"),
    ("census.casts_per_game", "casts/game"),
    ("rl.mean.rej", "rejected/traj"),
    ("rl.mean.reward", "reward"),
    ("rl.mean.v0", "v0"),
    ("games.turns_median", "turns median"),
    ("gen_s", "gen_s"),
    ("campaign_s", "campaign_s"),
    ("train_s", "train_s"),
]


def _get(row: dict, dotted: str):
    cur: Any = row
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def monitor_curves(run_dir: Path) -> tuple[list[str], dict]:
    """Plot every monitor.jsonl series; return (anomalies, numbers)."""
    run_dir = Path(run_dir)
    rows = [json.loads(line) for line in open(run_dir / "monitor.jsonl")]
    if not rows:
        return [], {}
    xs = [r["iteration"] for r in rows]
    series = {label: [_get(r, key) for r in rows] for key, label in MONITOR_SERIES}

    plt = _plt()
    live = [(lab, ys) for lab, ys in series.items() if any(v is not None for v in ys)]
    ncol = 3
    nrow = (len(live) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 2.6 * nrow), squeeze=False)
    for i, (lab, ys) in enumerate(live):
        ax = axes[i // ncol][i % ncol]
        pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=".", lw=1)
        ax.set_title(lab, fontsize=9)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.25)
    for j in range(len(live), nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    fig.suptitle(f"{run_dir.name} monitor ({len(rows)} iterations)", fontsize=11)
    fig.tight_layout()
    out = run_dir / "analysis"
    out.mkdir(exist_ok=True)
    fig.savefig(out / "monitor.png", dpi=110)
    plt.close(fig)

    anomalies: list[str] = []
    numbers: dict = {"iterations": len(rows)}
    if len(rows) >= 3:

        def first_last(lab: str) -> tuple[float, float] | None:
            ys = [y for y in series[lab] if y is not None]
            return (ys[0], ys[-1]) if len(ys) >= 2 else None

        kl = first_last("kl_mu")
        if kl and kl[0] and kl[1] / max(kl[0], 1e-9) > 3:
            anomalies.append(
                f"kl_mu grew {kl[0]:.4g} -> {kl[1]:.4g} ({kl[1] / kl[0]:.1f}x; the "
                "ADR-0049 read-1 shape — the policy is moving; check WHERE with the delta)"
            )
        ent = first_last("entropy")
        if ent and ent[0] and ent[1] < 0.7 * ent[0]:
            anomalies.append(f"entropy fell {ent[0]:.4g} -> {ent[1]:.4g} (>30% decline)")
        vr = [y for y in series["veto rate"] if y is not None]
        if vr and (max(vr) - min(vr)) > 2 * statistics.median(vr):
            anomalies.append(
                f"veto rate range {min(vr):.3f}-{max(vr):.3f} > 2x median "
                "(limit-cycle shape, ADR-0049 read 1)"
            )
        numbers.update(kl_mu=kl, entropy=ent, veto_range=(min(vr), max(vr)) if vr else None)
    return anomalies, numbers


# ------------------------------------------------------------ holding read


def holding_read(store_paths: list[str]) -> dict:
    """ADR-0049 read 3 productionized (candidacy-based v1 — see module doc)."""
    from anvil.store.trajectories import open_store

    out = {
        cls: {
            "spell_windows": 0,
            "held_windows": 0,
            "casts": 0,
            "same_turn_hold_then_cast": 0,
            "horizon": Counter(),  # turns from first candidacy to cast; "never"
        }
        for cls in ("model", "heur")
    }
    games = 0
    for path in store_paths:
        store = open_store(path)
        for g in store.game_indices():
            try:
                traj = store.game(g)
            except Exception:
                continue
            mu = store.mu_for_game(g) or {}
            games += 1
            # Seat class from the header player names ("Anvil(1)-…" vs
            # "Heur(2)-…"): eval arms serve argmax with NO mu.jsonl, so mu
            # coverage alone mislabels every seat heuristic (found on the
            # first baseline read). mu coverage stays as the fallback for
            # stores whose names don't carry the tag.
            players = traj.header.get("players") or []
            seat_cls: dict[int, str] = {}
            for si, p in enumerate(players):
                name = (p or {}).get("name", "")
                if name.startswith("Anvil"):
                    seat_cls[si] = "model"
                elif name.startswith("Heur"):
                    seat_cls[si] = "heur"
            # (seat, entity) -> first turn it appeared as a spell candidate
            first_cand: dict[tuple[int, int], int] = {}
            cast_turn: dict[tuple[int, int], int] = {}
            # (seat, turn) -> entities passed-on earlier this turn
            held_this_turn: dict[tuple[int, int], set[int]] = defaultdict(set)
            for dec in traj.decisions:
                opts = dec.get("opts")
                if not opts:
                    continue
                obs = dec.get("obs")
                turn = obs["glob"].get("turn") if obs else None
                if turn is None:
                    continue
                spells = [o for o in opts if o.get("kind") == "spell" and o.get("e") is not None]
                if not spells:
                    continue
                seat = dec["p"]
                cls = seat_cls.get(seat, "model" if mu.get(dec["s"]) is not None else "heur")
                b = out[cls]
                b["spell_windows"] += 1
                for o in spells:
                    first_cand.setdefault((seat, o["e"]), turn)
                ret = dec.get("ret")
                plan = ret[0] if isinstance(ret, list) and ret else None
                host = plan.get("e") if isinstance(plan, dict) else None
                if host is None:
                    b["held_windows"] += 1
                    for o in spells:
                        held_this_turn[(seat, turn)].add(o["e"])
                else:
                    b["casts"] += 1
                    if host in held_this_turn.get((seat, turn), ()):
                        b["same_turn_hold_then_cast"] += 1
                    key = (seat, host)
                    if key not in cast_turn:
                        cast_turn[key] = turn
                        fc = first_cand.get(key)
                        if fc is not None:
                            b["horizon"][min(turn - fc, 5)] += 1
            # never-cast candidates close out the horizon distribution
            for (seat, e), fc in first_cand.items():
                if (seat, e) not in cast_turn:
                    cls = seat_cls.get(seat)
                    if cls is None:
                        mu_seat = any(
                            mu.get(d["s"]) is not None for d in traj.decisions if d["p"] == seat
                        )
                        cls = "model" if mu_seat else "heur"
                    out[cls]["horizon"]["never"] += 1

    rep: dict = {"games": games}
    for cls, b in out.items():
        h = b["horizon"]
        cast_n = sum(v for k, v in h.items() if k != "never")
        rep[cls] = {
            "spell_windows": b["spell_windows"],
            "hold_rate": round(b["held_windows"] / max(b["spell_windows"], 1), 4),
            "casts": b["casts"],
            "same_turn_hold_then_cast_rate": round(
                b["same_turn_hold_then_cast"] / max(b["casts"], 1), 4
            ),
            "horizon": {str(k): v for k, v in sorted(h.items(), key=lambda kv: str(kv[0]))},
            "cast_at_first_opportunity": round(h.get(0, 0) / max(cast_n, 1), 4),
            "never_cast_frac": round(h.get("never", 0) / max(cast_n + h.get("never", 0), 1), 4),
        }
    return rep


def plot_holding_trajectory(rows: list[dict], out_png: Path) -> None:
    """rows = one holding_read result per iteration (analysis/holding.jsonl)."""
    plt = _plt()
    fig, axes = plt.subplots(1, 3, figsize=(12, 3))
    xs = list(range(len(rows)))
    for cls, color in (("model", "tab:orange"), ("heur", "tab:gray")):
        axes[0].plot(xs, [r[cls]["hold_rate"] for r in rows], marker=".", label=cls, color=color)
        axes[1].plot(
            xs,
            [r[cls]["same_turn_hold_then_cast_rate"] for r in rows],
            marker=".",
            label=cls,
            color=color,
        )
        axes[2].plot(
            xs,
            [r[cls]["cast_at_first_opportunity"] for r in rows],
            marker=".",
            label=cls,
            color=color,
        )
    for ax, t in zip(axes, ("hold rate", "same-turn hold-then-cast", "cast at first opp")):
        ax.set_title(t, fontsize=9)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


# -------------------------------------------------------- behavioral delta


def behavioral_delta(
    ref_ckpt: str, new_ckpt: str, stores: str | list, max_windows: int = 20000, batch: int = 256
) -> dict:
    """ADR-0049 read 2 productionized: ref vs new on shared priority windows."""
    import torch
    from torch.utils.data import DataLoader

    from anvil.torch.utils import get_torch_device
    from anvil.training.dataset import PriorityWindows, collate, default_methods
    from anvil.training.train import build_net

    device = get_torch_device()

    def load(path: str):
        ck = torch.load(path, map_location=device, weights_only=False)
        cfg = ck["config"]
        net = build_net(
            cfg["embed"],
            cfg["pool_manifest"],
            len(default_methods()),
            n_sa=cfg.get("sa_vocab_size", 0),
        ).to(device)
        net.load_compat(ck["model"])
        net.eval()
        return net, cfg

    net_a, cfg = load(ref_ckpt)
    net_b, _ = load(new_ckpt)

    ds = PriorityWindows(
        stores,
        cfg["embed"],
        default_methods(),
        split=None,
        shuffle_games=False,
        tasks={"priority"},
    )
    loader = DataLoader(ds, batch_size=batch, collate_fn=collate, num_workers=4)

    n = n_multi = agree = a_casts = changed = to_pass = 0
    kls: list[float] = []
    with torch.no_grad():
        for b in loader:
            if n >= max_windows:
                break
            b = {k: v.to(device) for k, v in b.items()}
            with torch.autocast(device, dtype=torch.bfloat16):
                la = net_a(b)["policy_logits"].float()
                lb = net_b(b)["policy_logits"].float()
            multi = b["cand_mask"].sum(1) > 1
            n += int(multi.numel())
            if not bool(multi.any()):
                continue
            la, lb = la[multi], lb[multi]
            pa, pb = la.softmax(1), lb.softmax(1)
            arg_a, arg_b = la.argmax(1), lb.argmax(1)
            n_multi += int(multi.sum())
            agree += int((arg_a == arg_b).sum())
            cast_a = arg_a != 0
            a_casts += int(cast_a.sum())
            ch = cast_a & (arg_b != arg_a)
            changed += int(ch.sum())
            to_pass += int((ch & (arg_b == 0)).sum())
            kl = (pa * ((pa + 1e-9).log() - (pb + 1e-9).log())).sum(1)
            kls.extend(kl.cpu().tolist())
    kls.sort()
    q = lambda p: kls[int(p * (len(kls) - 1))] if kls else None  # noqa: E731
    return {
        "ref": ref_ckpt,
        "new": new_ckpt,
        "windows": n,
        "multi_windows": n_multi,
        "agreement": round(agree / max(n_multi, 1), 4),
        "ref_cast_windows": a_casts,
        "cast_changed_rate": round(changed / max(a_casts, 1), 4),
        "cast_to_pass_frac": round(to_pass / max(changed, 1), 4),
        "kl_median": q(0.5),
        "kl_p90": q(0.9),
    }


# ---------------------------------------------------------------- eval read


def _model_won(row: dict) -> bool | None:
    if row.get("status") != "won" or not row.get("winner"):
        return None
    return row["winner"].startswith("Anvil")


def eval_read(name: str, arm_dirs: list[str], report_json: str | None, out_dir: Path) -> list[str]:
    """Eval battery: headline + seed-half consistency + distributions."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_by_arm: list[list[dict]] = []
    for d in arm_dirs:
        rows = [json.loads(line) for line in open(Path(d) / "games.jsonl")]
        rows_by_arm.append(rows)
    allrows = [r for rows in rows_by_arm for r in rows]
    decided = [(r, _model_won(r)) for r in allrows]
    decided = [(r, w) for r, w in decided if w is not None]

    # seed-half consistency (run12 lesson): game-index-parity halves
    halves = {0: [], 1: []}
    for r, w in decided:
        halves[r["i"] % 2].append(w)

    def wr_se(ws: list[bool]) -> tuple[float, float]:
        n = len(ws)
        p = sum(ws) / max(n, 1)
        return p, (p * (1 - p) / max(n, 1)) ** 0.5

    (w0, se0), (w1, se1) = wr_se(halves[0]), wr_se(halves[1])
    split_gap = abs(w0 - w1)
    split_lim = 2 * (se0**2 + se1**2) ** 0.5
    anomalies: list[str] = []
    if split_gap > split_lim:
        anomalies.append(
            f"seed-half disagreement {w0:.4f} vs {w1:.4f} (gap {split_gap:.4f} > "
            f"2x pooled SE {split_lim:.4f}) — the run12 class; treat the combined "
            "read with suspicion"
        )
    statuses = Counter(r["status"] for r in allrows)
    non_won = sum(v for k, v in statuses.items() if k != "won")
    if non_won > 0.02 * max(len(allrows), 1):
        anomalies.append(f"non-decisive games {dict(statuses)} > 2%")

    # per-model-deck winrate spread (model seat inferred per arm from winner tags)
    deck_w: dict[str, list[bool]] = defaultdict(list)
    for rows in rows_by_arm:
        seats = Counter()
        for r in rows:
            if r.get("winner", "").startswith("Anvil("):
                seats[int(r["winner"][6]) - 1] += 1
        model_seat = seats.most_common(1)[0][0] if seats else 0
        for r in rows:
            w = _model_won(r)
            if w is not None:
                deck_w[r["decks"][model_seat]].append(w)
    per_deck = sorted((sum(ws) / len(ws), d, len(ws)) for d, ws in deck_w.items() if len(ws) >= 8)

    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(9, 3))
    axes[0].hist([r["turns"] for r in allrows], bins=range(0, 61, 2), color="tab:blue", alpha=0.8)
    axes[0].set_title("turns distribution", fontsize=9)
    axes[1].hist([p for p, _, _ in per_deck], bins=20, color="tab:orange", alpha=0.8)
    axes[1].set_title("per-model-deck winrate", fontsize=9)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "eval.png", dpi=110)
    plt.close(fig)

    headline = ""
    if report_json and Path(report_json).exists():
        rep = json.load(open(report_json))
        arm = rep.get(name) or next(iter(rep.values()))
        headline = (
            f"winrate {arm.get('winrate'):.4f} ± {arm.get('se'):.4f} "
            f"({arm.get('games')} games; ante corrected "
            f"{arm.get('ante', {}).get('corrected_winrate')})"
        )
    numbers = {
        "headline": headline,
        "games": len(allrows),
        "statuses": dict(statuses),
        "turns_median": statistics.median(r["turns"] for r in allrows) if allrows else None,
        "seed_halves": {"even": [w0, se0], "odd": [w1, se1], "gap": split_gap, "lim": split_lim},
        "per_deck_extremes": {
            "worst": per_deck[:3],
            "best": per_deck[-3:],
            "spread_sd": round(statistics.pstdev([p for p, _, _ in per_deck]), 4)
            if per_deck
            else None,
        },
    }
    (out_dir / "analysis.json").write_text(json.dumps(numbers, indent=1) + "\n")
    _write_report(
        out_dir,
        f"{name} eval battery",
        anomalies,
        [
            f"**Headline (pre-registered read):** {headline}",
            f"**Seed halves:** even {w0:.4f}±{se0:.4f} / odd {w1:.4f}±{se1:.4f} "
            f"(gap {split_gap:.4f}, flag at {split_lim:.4f})",
            f"**Statuses:** {dict(statuses)} · turns median {numbers['turns_median']}",
            f"**Deck spread (n≥8):** sd {numbers['per_deck_extremes']['spread_sd']} · "
            f"worst {per_deck[:3]} · best {per_deck[-3:]}",
            "![eval](eval.png)",
            "\n## Exploratory\n\nEverything above the gate headline is "
            "hypothesis-generating only (run-analysis-protocol rule 1).",
        ],
    )
    return anomalies


# ------------------------------------------------- driver-facing composites


def per_iteration(run_dir: Path, stores: list[str]) -> list[str]:
    """Cheap battery after each iteration: monitor refresh + holding row."""
    run_dir = Path(run_dir)
    an, _ = monitor_curves(run_dir)
    h = holding_read(stores)
    out = run_dir / "analysis"
    out.mkdir(exist_ok=True)
    with open(out / "holding.jsonl", "a") as f:
        f.write(json.dumps(h) + "\n")
    return an


def run_end(run_dir: Path, delta_windows: int = 20000) -> list[str]:
    """Full battery at run end; writes analysis/analysis.md, returns anomalies."""
    run_dir = Path(run_dir)
    out = run_dir / "analysis"
    out.mkdir(exist_ok=True)
    anomalies, mon_numbers = monitor_curves(run_dir)

    hold_rows = []
    hpath = out / "holding.jsonl"
    if hpath.exists():
        hold_rows = [json.loads(line) for line in open(hpath)]
        if len(hold_rows) >= 2:
            plot_holding_trajectory(hold_rows, out / "holding.png")
            first, last = hold_rows[0]["model"], hold_rows[-1]["model"]
            n0, n1 = hold_rows[0]["model"]["casts"], hold_rows[-1]["model"]["casts"]
            d = last["same_turn_hold_then_cast_rate"] - first["same_turn_hold_then_cast_rate"]
            se = (
                sum(
                    r * (1 - r) / max(n, 1)
                    for r, n in (
                        (first["same_turn_hold_then_cast_rate"], n0),
                        (last["same_turn_hold_then_cast_rate"], n1),
                    )
                )
                ** 0.5
            )
            if abs(d) > 3 * se:
                anomalies.append(
                    f"hold-then-cast rate MOVED {first['same_turn_hold_then_cast_rate']:.3f} -> "
                    f"{last['same_turn_hold_then_cast_rate']:.3f} (|Δ| > 3se — ADR-0049's "
                    "baseline expectation is flat; movement is the notable event either way)"
                )

    delta = None
    cfg_path = run_dir / "loop_config.json"
    state_path = run_dir / "loop_state.json"
    if cfg_path.exists() and state_path.exists():
        cfg = json.loads(cfg_path.read_text())
        state = json.loads(state_path.read_text())
        groups = state.get("stores") or []
        last_group = groups[-1] if groups else None
        if cfg.get("ckpt") and state.get("ckpt") and last_group:
            delta = emit(behavioral_delta, cfg["ckpt"], state["ckpt"], last_group, delta_windows)
            if delta and delta["cast_changed_rate"] > 0.05:
                anomalies.append(
                    f"behavioral delta: {delta['cast_changed_rate']:.1%} of the init ckpt's "
                    f"cast decisions changed ({delta['cast_to_pass_frac']:.0%} cast->pass; "
                    "the ADR-0049 cast-suppression axis — check the sign against the run's "
                    "intent)"
                )

    numbers = {
        "monitor": mon_numbers,
        "holding": hold_rows[-1] if hold_rows else None,
        "behavioral_delta": delta,
    }
    (out / "analysis.json").write_text(json.dumps(numbers, indent=1) + "\n")
    sections = [
        "![monitor](monitor.png)",
        "![holding](holding.png)" if (out / "holding.png").exists() else "",
        f"**Behavioral delta (init -> final):** `{json.dumps(delta)}`"
        if delta
        else "**Behavioral delta:** unavailable (missing config/state/stores)",
        "\n## Exploratory\n\nAll of the above is hypothesis-generating only "
        "(run-analysis-protocol rule 1); the run verdict is the pre-registered gate read.",
    ]
    _write_report(out, f"{run_dir.name} run battery", anomalies, [s for s in sections if s])
    return anomalies


# ----------------------------------------------------------------------- CLI


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("holding")
    s.add_argument("stores", nargs="+")
    s.add_argument("--json-out")
    s = sub.add_parser("delta")
    s.add_argument("--ref", required=True)
    s.add_argument("--new", required=True)
    s.add_argument("--stores", required=True, help="store dir / comma-list")
    s.add_argument("--max-windows", type=int, default=20000)
    s = sub.add_parser("eval-read")
    s.add_argument("--name", required=True)
    s.add_argument("--arm-dirs", required=True, help="comma-list of run dirs")
    s.add_argument("--report")
    s.add_argument("--out-dir", required=True)
    s = sub.add_parser("run-end")
    s.add_argument("--run-dir", required=True)
    s = sub.add_parser("monitor")
    s.add_argument("--run-dir", required=True)
    a = ap.parse_args()

    if a.cmd == "holding":
        rep = holding_read(a.stores)
        print(json.dumps(rep, indent=1))
        if a.json_out:
            Path(a.json_out).write_text(json.dumps(rep, indent=1) + "\n")
    elif a.cmd == "delta":
        print(json.dumps(behavioral_delta(a.ref, a.new, a.stores, a.max_windows), indent=1))
    elif a.cmd == "eval-read":
        an = eval_read(a.name, a.arm_dirs.split(","), a.report, Path(a.out_dir))
        print(f"[battery] anomalies: {an or 'none'}")
    elif a.cmd == "run-end":
        an = run_end(Path(a.run_dir))
        print(f"[battery] anomalies: {an or 'none'}")
    elif a.cmd == "monitor":
        an, _ = monitor_curves(Path(a.run_dir))
        print(f"[battery] anomalies: {an or 'none'}")


if __name__ == "__main__":
    main()
