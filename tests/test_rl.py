"""V-trace target math + ADR-0017 guard/hinge units (M2 D6) — pure unit
tests, no local data needed."""

import pytest
import torch

from anvil.training.rl import entropy_hinge, vtrace_targets
from anvil.training.selfplay import guard_flags


def test_on_policy_reduces_to_monte_carlo():
    """rho == c == 1, gamma 1, terminal-only reward: vs telescopes to the
    return at every step; advantage sign follows (return - V)."""
    v = torch.tensor([0.5, 0.6, 0.7])
    lp = torch.zeros(3)
    vs, adv, rho = vtrace_targets(v, lp, lp, reward=1.0)
    assert torch.allclose(vs, torch.ones(3))
    assert torch.allclose(rho, torch.ones(3))
    assert (adv > 0).all()
    vs0, adv0, _ = vtrace_targets(v, lp, lp, reward=0.0)
    assert torch.allclose(vs0, torch.zeros(3))
    assert (adv0 < 0).all()


def test_calibrated_values_zero_advantage():
    lp = torch.zeros(3)
    _, adv, _ = vtrace_targets(torch.ones(3), lp, lp, reward=1.0)
    assert adv.abs().max() < 1e-6
    _, adv0, _ = vtrace_targets(torch.zeros(3), lp, lp, reward=0.0)
    assert adv0.abs().max() < 1e-6


def test_off_policy_clipping_shrinks_corrections():
    """pi far below mu: rho ~ 0 — targets stay near V (no correction is
    trusted), never explode."""
    v = torch.tensor([0.5, 0.6, 0.7])
    lp = torch.zeros(3)
    vs, _, rho = vtrace_targets(v, lp - 3.0, lp, reward=1.0)
    assert (rho < 0.06).all()
    assert (vs - v).abs().max() < 0.2


def test_rho_clipped_at_rho_bar():
    v = torch.full((4,), 0.5)
    lp = torch.zeros(4)
    _, _, rho = vtrace_targets(v, lp + 2.0, lp, reward=1.0, rho_bar=1.0)
    assert torch.allclose(rho, torch.ones(4))


def test_entropy_hinge_zero_gradient_above_floor():
    """ADR-0017: entropy above the floor must contribute exactly zero loss
    AND zero gradient — the always-on bonus's constant upward pressure was
    run-2's root cause. A sign error here recreates the runaway."""
    ent = torch.tensor([0.15, 0.20, 0.25], requires_grad=True)
    pen = entropy_hinge(ent, floor=0.08, b=3, t_len=3)
    assert pen.item() == 0.0
    pen.backward()
    assert torch.all(ent.grad == 0)


def test_entropy_hinge_pushes_up_below_floor():
    """Below the floor the penalty is positive and its gradient DECREASES
    with entropy (d pen / d ent < 0), i.e. gradient DESCENT on the loss
    raises entropy — the collapse-guard direction."""
    ent = torch.tensor([0.01, 0.02], requires_grad=True)
    pen = entropy_hinge(ent, floor=0.08, b=2, t_len=2)
    assert pen.item() > 0
    pen.backward()
    assert torch.all(ent.grad < 0)


def _rl_of(kl, ent):
    return {"mean": {"kl_mu": kl, "ent": ent}}


BASE = {"ent": 0.18, "veto_rate": 0.237}  # run-2's actual iter-0 point


def test_guards_quiet_on_healthy_iterations():
    """run-2 iters 0-2 shaped inputs: no guard fires (kl <= 0.019,
    ent/veto within multiples)."""
    assert guard_flags({"veto_rate": 0.31}, _rl_of(0.019, 0.218), BASE) == []
    assert guard_flags({"veto_rate": 0.237}, _rl_of(0.009, 0.183), None) == []


def test_guards_would_have_halted_run2():
    """run-2's actual iter-3 and iter-4 monitor numbers: iter 3 almost trips
    kl (0.047 < 0.05 — the drift was one iteration from the line); iter 4
    trips all three."""
    assert guard_flags({"veto_rate": 0.345}, _rl_of(0.047, 0.254), BASE) == []
    flags = guard_flags({"veto_rate": 0.613}, _rl_of(1.067, 0.86), BASE)
    assert len(flags) == 3, flags


def test_guard_kl_is_absolute_no_baseline_needed():
    flags = guard_flags({}, _rl_of(0.06, None), None)
    assert len(flags) == 1 and "kl_mu" in flags[0]


def test_guard_seq_share():
    """d6-run14 guard: the seq term's share of PG mass vs the ADR-0054
    calibration target. Absolute like kl (no baseline); quiet when the
    share is absent (seq off) or the guard is unset."""

    def rl_share(ss):
        return {"mean": {"kl_mu": 0.01, "seq_share": ss}}

    assert guard_flags({}, rl_share(0.15), None, seq_share_max=0.3) == []
    flags = guard_flags({}, rl_share(0.45), None, seq_share_max=0.3)
    assert len(flags) == 1 and "seq_share" in flags[0]
    assert guard_flags({}, _rl_of(0.01, None), None, seq_share_max=0.3) == []
    assert guard_flags({}, rl_share(0.45), None) == []


def test_rl_summary_surfaces_plan_share(tmp_path):
    """M10 build regression (2026-08-27): _rl_summary's mean key list
    omitted plan_share, so guard_flags read None and the ADR-0057
    plan-share guard was dead across run20. The summary must surface it
    end-to-end so the guard can fire."""
    import json

    from anvil.training.selfplay import _rl_summary

    with open(tmp_path / "metrics.jsonl", "w") as f:
        f.write(json.dumps({"step": 10, "kl_mu": 0.01, "plan_share": 0.45,
                            "plan_act": 0.5, "plan_delta": 0.3}) + "\n")
    rl = _rl_summary(tmp_path)
    assert rl["mean"]["plan_share"] == 0.45
    flags = guard_flags({}, rl, None, plan_share_max=0.3)
    assert len(flags) == 1 and "plan_share" in flags[0]
    assert guard_flags({}, rl, None) == []  # unset guard stays quiet


def test_draw_scores_zero_for_both_seats():
    """§3d cap-aware rule as used by the loader: draw/cap reward is 0 — the
    stalling leader's vs targets sink toward 0, same as a loss."""
    v = torch.tensor([0.9, 0.9])  # a 'winning' board that stalls out
    lp = torch.zeros(2)
    vs, adv, _ = vtrace_targets(v, lp, lp, reward=0.0)
    assert torch.allclose(vs, torch.zeros(2))
    assert (adv < 0).all()


def test_census_first_attempt_veto_basis(tmp_path):
    """M3 D1: first_veto_rate counts one attempt per window (no reask field),
    so re-ask chains inflate veto_rate but not the first-attempt basis."""
    import json as _json

    from anvil.training.selfplay import _census_tallies

    wd = tmp_path / "workers" / "inv-000"
    wd.mkdir(parents=True)
    m = "chooseSpellAbilityToPlay"
    lines = [
        # window A: clean first-attempt cast
        {"by": "bridge", "m": m, "pick": "Bolt"},
        # window B: first attempt vetoed, rescued on attempt 2 (chain of 3)
        {"by": "bridge", "m": m, "pick": "Ertai", "veto": "unpayable"},
        {"by": "bridge", "m": m, "pick": "Ertai", "veto": "unpayable", "reask": 1},
        {"by": "bridge", "m": m, "pick": "Ring", "reask": 2},
        # window C: model-chosen pass on first attempt
        {"by": "bridge", "m": m, "pick": "pass"},
    ]
    (wd / "census.jsonl").write_text("\n".join(_json.dumps(r) for r in lines) + "\n")

    c = _census_tallies(tmp_path)
    assert c["veto"] == 2 and c["cast"] == 2 and c["reask_rescued"] == 1
    assert c["veto_rate"] == 0.5  # chain-inflated: 2/(2+2)
    assert c["first_veto"] == 1 and c["first_cast"] == 1
    assert c["first_veto_rate"] == 0.5  # here equal by construction...

    # ...but a longer re-veto chain moves ONLY the chain-inflated rate
    lines += [
        {"by": "bridge", "m": m, "pick": "X", "veto": "no-fit", "reask": k} for k in range(1, 5)
    ]
    (wd / "census.jsonl").write_text("\n".join(_json.dumps(r) for r in lines) + "\n")
    c2 = _census_tallies(tmp_path)
    assert c2["veto_rate"] == 0.75  # 6/(6+2)
    assert c2["first_veto_rate"] == 0.5  # unchanged


def test_vtrace_step_rewards_shift_targets():
    """§6c: per-step penalties enter r_t; terminal reward adds to the last
    step. With rho=1, gamma=1, values=0: vs[t] = sum of rewards from t on."""
    from anvil.training.rl import vtrace_targets

    z = torch.zeros(3)
    lam = 0.02
    step_r = torch.tensor([-lam, 0.0, 0.0])
    vs, pg_adv, _ = vtrace_targets(z.clone(), z.clone(), z.clone(), reward=1.0, step_r=step_r)
    assert vs.tolist() == pytest.approx([1.0 - lam, 1.0, 1.0])
    # without step_r: unchanged legacy behavior
    vs0, _, _ = vtrace_targets(z.clone(), z.clone(), z.clone(), reward=1.0)
    assert vs0.tolist() == pytest.approx([1.0, 1.0, 1.0])


def test_rejected_events_priority_and_combat():
    from anvil.training.rl import rejected_events

    # priority: cast intent + no realized SA = veto; pass / realized = 0
    dec_v = {"ret": None}
    assert rejected_events([], 0, dec_v, {"task": "priority", "c": 3}, {}) == 1
    assert rejected_events([], 0, dec_v, {"task": "priority", "c": 0}, {}) == 0
    dec_ok = {"ret": [{"e": 5, "sa": "x"}]}
    assert rejected_events([], 0, dec_ok, {"task": "priority", "c": 3}, {}) == 0

    # attack: declared 2 attackers, engine realized 1 -> 1 dropped
    ents = [
        {"e": 1, "n": "A", "z": "battlefield", "c": 0, "pt": [2, 2]},
        {"e": 2, "n": "B", "z": "battlefield", "c": 0, "pt": [3, 3]},
    ]
    dec_a = {"m": "declareAttackers", "p": 0, "obs": {"glob": {"turn": 5}, "ents": ents}}
    later = {
        "m": "x",
        "obs": {
            "glob": {"turn": 5},
            "ents": [
                {"e": 1, "n": "A", "z": "battlefield", "c": 0, "pt": [2, 2], "atk": {"pi": 1}}
            ],
        },
    }
    aux = {"cmb_rows": [0, 1], "cmb_members": {0: [1], 1: [2]}, "blk_atk_rows": []}
    rec = {"task": "attack", "atk": [1, 1], "cnt": [1, 1], "atgt": [0, 0]}
    assert rejected_events([dec_a, later], 0, dec_a, rec, aux) == 1
    # both realized -> 0
    later2 = {
        "m": "x",
        "obs": {
            "glob": {"turn": 5},
            "ents": [
                dict(later["obs"]["ents"][0]),
                {"e": 2, "n": "B", "z": "battlefield", "c": 0, "pt": [3, 3], "atk": {"pi": 1}},
            ],
        },
    }
    assert rejected_events([dec_a, later2], 0, dec_a, rec, aux) == 0

    # block: declared a block that got dropped + a forced block appears
    atk_ent = {"e": 9, "n": "Foe", "z": "battlefield", "c": 1, "pt": [4, 4], "atk": {"pi": 0}}
    bents = ents + [atk_ent]
    dec_b = {"m": "declareBlockers", "p": 0, "obs": {"glob": {"turn": 5}, "ents": bents}}
    # answered: row0 blocks attacker slot 0, row1 answers none (class = 1 atk row -> none = 1)
    rec_b = {"task": "block", "blk": [0, 1], "cnt": [1, 1]}
    exb = {"cmb_rows": [0, 1], "cmb_members": {0: [1], 1: [2]}, "blk_atk_rows": [2]}
    # realized: e1's block dropped; e2 force-added
    later_b = {
        "m": "x",
        "obs": {
            "glob": {"turn": 5},
            "ents": [{"e": 2, "n": "B", "z": "battlefield", "c": 0, "pt": [3, 3], "blk": [9]}],
        },
    }
    assert rejected_events([dec_b, later_b], 0, dec_b, rec_b, exb) == 2


def test_iteration_batches_and_replay_mixture():
    """§6d: batch plan splits games with disjoint start-index slices; the
    replay window is measured in iteration GROUPS, not stores."""
    from anvil.training.selfplay import iteration_batches, replay_mixture

    b = iteration_batches("r6", 3, 480, 0.5)
    assert [(p, n, off) for p, n, off, _ in b] == [
        ("r6-i003", 240, 0),
        ("r6-i003h0", 120, 240),
        ("r6-i003h1", 120, 360),
    ]
    assert [seats for *_, seats in b] == [None, 0, 1]
    assert sum(n for _, n, _, _ in b) == 480
    # pure mirror: single batch, unchanged semantics
    assert iteration_batches("r6", 0, 480, 0.0) == [("r6-i000", 480, 0, None)]

    groups = [
        ["a1", "a2", "a3"],
        ["b1", "b2", "b3"],
        ["c1", "c2", "c3"],
        ["d1", "d2", "d3"],
        ["e1", "e2", "e3"],
    ]
    stores, weights = replay_mixture(groups, replay=4, fresh_weight=1.0, replay_weight=0.33)
    assert stores == ["b1", "b2", "b3", "c1", "c2", "c3", "d1", "d2", "d3", "e1", "e2", "e3"]
    assert weights == [0.33] * 9 + [1.0] * 3
    # legacy flat chains load as singleton groups upstream; a mixed history
    # (old flat run resumed with heur-frac on) still weights by group
    stores2, weights2 = replay_mixture(
        [["x"], ["y"], ["z1", "z2", "z3"]], replay=4, fresh_weight=1.0, replay_weight=0.33
    )
    assert stores2 == ["x", "y", "z1", "z2", "z3"]
    assert weights2 == [0.33, 0.33, 1.0, 1.0, 1.0]


def test_batch_chunk_guarantees_two_rounds():
    """Chunk-tail hazard (2026-08-03 retraction): a batch with fewer than two
    chunks per worker is paced by its slowest worker's contiguous block. Each
    generation batch clamps args.chunk so every worker sees >=2 refills."""
    from anvil.training.selfplay import batch_chunk

    assert batch_chunk(240, 16, 30) == 7  # w=16 mirror batch at heur_frac .5
    assert batch_chunk(120, 16, 30) == 3  # w=16 heur seat batch
    assert batch_chunk(240, 8, 30) == 15  # the standard recipe de-tails too
    assert batch_chunk(480, 8, 30) == 30  # big pool: the ceiling holds
    assert batch_chunk(10, 16, 30) == 1  # tiny batch floors at 1, never 0


def test_drill_slice_rotates_and_wraps():
    from anvil.training.selfplay import drill_slice

    rows = [{"g": i} for i in range(7)]
    # ppi 3 over 7 rows: iterations tile the list, wrapping without dupes
    s0 = drill_slice(rows, 0, 3)
    s1 = drill_slice(rows, 1, 3)
    s2 = drill_slice(rows, 2, 3)
    assert [r["g"] for r in s0] == [0, 1, 2]
    assert [r["g"] for r in s1] == [3, 4, 5]
    assert [r["g"] for r in s2] == [6, 0, 1]
    assert all(len({r["g"] for r in s}) == 3 for s in (s0, s1, s2))
    # ppi >= n: one full pass, no duplicates
    assert [r["g"] for r in drill_slice(rows, 4, 10)] == [5, 6, 0, 1, 2, 3, 4][:7]


def test_drill_eval_phase_idempotent_and_picks_new_report(tmp_path, monkeypatch):
    import argparse
    import json as _json

    from anvil.training import selfplay

    es = tmp_path / "evalset"
    es.mkdir()
    it_dir = tmp_path / "iter-009"
    it_dir.mkdir()
    # a pre-existing report from an earlier (baseline) eval must NOT be
    # mistaken for this phase's output
    (es / "eval-20260101-000000.json").write_text("{}")
    rep = {
        "winrate": 0.42,
        "baseline": 0.36,
        "per_bin": {"lost": {"winrate": 0.12, "baseline": 0.05}},
    }
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        (es / "eval-20260102-000000.json").write_text(_json.dumps(rep))

    monkeypatch.setattr(selfplay, "_run", fake_run)
    monkeypatch.setattr(selfplay, "_notify", lambda *a, **k: None)
    args = argparse.Namespace(drill_eval_set=str(es), port=1, workers=2, name="t")
    state = {"ckpt": "ckpt.pt"}

    selfplay._drill_eval_phase(args, state, 9, it_dir)
    assert len(calls) == 1 and "ckpt.pt" in calls[0]
    saved = _json.loads((it_dir / "drill-eval.json").read_text())
    assert saved["per_bin"]["lost"]["winrate"] == 0.12

    # resume-idempotent: existing drill-eval.json short-circuits
    selfplay._drill_eval_phase(args, state, 9, it_dir)
    assert len(calls) == 1


def test_census_payment_failure_telemetry(tmp_path):
    """M9 D4 recipe pin 6: the payment head's failure channel reaches the
    loop. Denominators are DEVIATIONS, not windows — auto picks never execute
    a directed plan, so counting them would dilute exactly the signal that
    matters. Telemetry only: nothing here is priced or guarded."""
    import json as _json

    from anvil.training.selfplay import _census_tallies

    wd = tmp_path / "workers" / "inv-000"
    wd.mkdir(parents=True)
    m = "payManaCost"
    lines = [
        # two auto picks: counted as windows, invisible to every exec rate
        {"by": "bridge", "m": m, "pick": "auto", "exec": None},
        {"by": "bridge", "m": m, "pick": "auto"},
        # four directed picks: ok / salvage / fail / ok-with-leftover-float
        {"by": "bridge", "m": m, "pick": 1, "exec": "directed_ok", "float_residue": 0},
        {"by": "bridge", "m": m, "pick": 2, "exec": "directed_salvage", "float_residue": 0},
        {"by": "bridge", "m": m, "pick": 1, "exec": "directed_fail", "float_residue": 0},
        {"by": "bridge", "m": m, "pick": 3, "exec": "directed_ok", "float_residue": 2},
    ]
    (wd / "census.jsonl").write_text("\n".join(_json.dumps(r) for r in lines) + "\n")

    c = _census_tallies(tmp_path)
    assert c["pay_windows"] == 6 and c["pay_deviate"] == 4
    assert c["pay_deviation_rate"] == round(4 / 6, 4)
    assert c["pay_directed_ok"] == 2
    assert c["pay_directed_salvage"] == 1 and c["pay_directed_fail"] == 1
    assert c["pay_fail_rate"] == 0.25 and c["pay_salvage_rate"] == 0.25
    # residue is per-deviation too, and carries the mana count for magnitude
    assert c["pay_residue_windows"] == 1 and c["pay_residue_mana"] == 2
    assert c["pay_residue_rate"] == 0.25


def test_pay_head_stats_reads_displacement_from_init(tmp_path):
    """M9 D4 recipe pin 6 (second half): pay_bias starts at +2.0 and
    pay_kind_emb at exactly zero, so both series read as displacement from a
    known origin — that is what separates 'the head moved and it did not
    help' from 'the head never moved' at the read session."""
    from anvil.training.dataset import TASKS
    from anvil.training.selfplay import _pay_head_stats

    ck = tmp_path / "last.pt"
    bias = torch.zeros(len(TASKS))
    bias[TASKS["pay_class"]] = 2.0
    torch.save({"model": {"pay_bias": bias, "pay_kind_emb.weight": torch.zeros(6, 8)}}, ck)
    assert _pay_head_stats(ck) == {"bias": 2.0, "kind_rms": 0.0}

    bias[TASKS["pay_class"]] = 1.25
    torch.save({"model": {"pay_bias": bias, "pay_kind_emb.weight": torch.full((6, 8), 0.5)}}, ck)
    assert _pay_head_stats(ck) == {"bias": 1.25, "kind_rms": 0.5}

    # a checkpoint without the head is diagnostic-empty, never an exception
    torch.save({"model": {}}, ck)
    assert _pay_head_stats(ck) == {}


def test_share_guard_reads_median_and_spike_trips_own_guard(tmp_path):
    """m10-probe1 halt forensics (ADR-0085): iteration 2's MEAN sched_share
    1.50 was spike-dominated (median 0.18; one step at sched_ce 543.5 vs a
    3.2 median — the decode-confidence blowup). The share guard reads the
    step median so it measures the bulk; the spike trips its own tripline."""
    import json

    from anvil.training.selfplay import _rl_summary

    rows = [
        {"step": i, "kl_mu": 0.01, "sched_share": 0.18, "sched_ce": 3.2}
        for i in range(9)
    ]
    rows.append({"step": 9, "kl_mu": 0.01, "sched_share": 13.4, "sched_ce": 543.5})
    with open(tmp_path / "metrics.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    rl = _rl_summary(tmp_path)
    assert rl["mean"]["sched_share"] > 0.3  # the mean alone would halt
    assert rl["med"]["sched_share"] == 0.18
    # median under the bar: the share guard stays quiet
    flags = guard_flags({}, rl, None, sched_share_max=0.3)
    assert not any("sched_share" in fl for fl in flags), flags
    # the spike trips its own guard at the pinned 100x-median default
    flags = guard_flags({}, rl, None, sched_share_max=0.3, sched_spike_mult=100.0)
    assert len(flags) == 1 and "sched_ce_max" in flags[0], flags
    # pre-0085 rows (mean only, no med dict) still trip the share guard
    flags = guard_flags({}, {"mean": {"kl_mu": 0.01, "sched_share": 0.45}}, None,
                        sched_share_max=0.3)
    assert len(flags) == 1 and "sched_share" in flags[0], flags


def test_seedlab_spike_guard_ported(tmp_path):
    """ADR-0086: with the own-emission decode CE retired, the confidence-
    blowup tripline ports to the surviving CE term — seedlab trains on a
    fixed certified batch, so a max/median blowup there is head divergence.
    The retired sched_ce guard no-ops on post-0086 rows (key absent)."""
    import json

    from anvil.training.selfplay import _rl_summary

    rows = [
        {"step": i, "kl_mu": 0.01, "seedlab_share": 0.09, "seedlab_raw": 2.5}
        for i in range(9)
    ]
    rows.append({"step": 9, "kl_mu": 0.01, "seedlab_share": 0.09, "seedlab_raw": 410.0})
    with open(tmp_path / "metrics.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    rl = _rl_summary(tmp_path)
    assert rl["med"]["seedlab_raw"] == 2.5
    assert rl["spike"]["seedlab_raw_max"] == 410.0
    flags = guard_flags({}, rl, None, seedlab_share_max=0.3,
                        seedlab_spike_mult=100.0, sched_spike_mult=100.0)
    assert len(flags) == 1 and "seedlab_raw_max" in flags[0], flags
    # under the mult: quiet
    rows[-1]["seedlab_raw"] = 40.0
    with open(tmp_path / "metrics.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    assert guard_flags({}, _rl_summary(tmp_path), None, seedlab_share_max=0.3,
                       seedlab_spike_mult=100.0) == []


def test_lab_memorize_guard_fires_on_probe2_numbers(tmp_path):
    """ADR-0088 memorization tripline, re-based twice: to PER-STEP keys after
    the m10-probe3 false halt (the acc[] row values are per-trajectory ÷
    traj_per_step), and to the iteration MEDIAN of windowed per-step raws
    after probe5 (ADR-0092) — a mixed-class batch (paylab) gives auto-heavy
    windows a low MINIMUM by composition, which tripped probe5's iteration 4
    while its holdout sat flat. Regression from the real numbers in per-step
    scale: probe2 iteration 0 ran 2.73 -> ~1.68 -> ... -> ~0.18 (upper median
    0.713 = 0.26x, memorized) — fires at 0.3; probe3 iteration 0 ran 2.68 -> ~2.26
    ... 2.11 (median 0.84x, healthy) — quiet; probe5's paylab windows
    (median 0.54x, min 0.23x) — quiet under the median, would have fired
    under the min."""
    import json

    from anvil.training.selfplay import _rl_summary

    probe2 = [1.683, 1.097, 0.713, 0.449, 0.282, 0.185]  # 4x the row values
    rows = [{"step": 833500 + 20 * i, "kl_mu": 0.01, "seedlab_raw_step": v,
             "paylab_raw_step": 0.9} for i, v in enumerate(probe2)]
    with open(tmp_path / "metrics.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    rl = _rl_summary(tmp_path)
    assert rl["first"]["seedlab_raw_step"] == 1.683
    assert rl["lab_med"]["seedlab_raw_step"] == 0.713  # upper median of 6 (0.26x)
    flags = guard_flags({}, rl, None, lab_memorize_ratio=0.3,
                        seedlab_calib_raw=2.72795, paylab_calib_raw=0.98998)
    assert len(flags) == 1 and "seedlab_raw_step iteration-median" in flags[0], flags
    # probe3 iteration 0, per-step (labs_early mean 2.39; rows x4): quiet
    probe3 = [2.261, 2.221, 2.331, 2.256, 2.155, 2.109]
    # probe5 paylab windows: min 0.227 (auto-heavy window) but median ~0.54
    paylab5 = [0.94, 0.61, 0.227, 0.55, 0.62, 0.48]
    rows = [{"step": 833500 + 20 * i, "kl_mu": 0.01, "seedlab_raw_step": v,
             "paylab_raw_step": p} for i, (v, p) in enumerate(zip(probe3, paylab5))]
    with open(tmp_path / "metrics.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    assert guard_flags({}, _rl_summary(tmp_path), None, lab_memorize_ratio=0.3,
                       seedlab_calib_raw=2.67695, paylab_calib_raw=0.99872) == []
    # the follow term (ADR-0092) rides the same guard + its own share guard
    rows = [{"step": i, "kl_mu": 0.01, "follow_raw_step": 0.1, "follow_share": 0.4}
            for i in range(3)]
    with open(tmp_path / "metrics.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    flags = guard_flags({}, _rl_summary(tmp_path), None, lab_memorize_ratio=0.3,
                        follow_calib_raw=2.0, follow_share_max=0.15)
    assert any("follow_raw_step iteration-median" in fl for fl in flags), flags
    assert any("follow_share" in fl for fl in flags), flags
    # no per-step keys (pre-0088 rows) or no calibration reference: quiet,
    # never a KeyError
    assert not any("iteration-median" in fl
                   for fl in guard_flags({}, {"mean": {"kl_mu": 0.01}}, None,
                                         lab_memorize_ratio=0.3,
                                         seedlab_calib_raw=2.7))


def test_rl_summary_surfaces_sched_live_ce(tmp_path):
    """ADR-0088 staleness instrument: the live-row decode CE (measured
    grad-free on the retired term's target pipeline) must reach the summary
    means or the live-gap read can never happen (the plan_share lesson)."""
    import json

    from anvil.training.selfplay import _rl_summary

    rows = [{"step": i, "kl_mu": 0.01, "sched_live_ce": 2.6 + i * 0.1} for i in range(3)]
    with open(tmp_path / "metrics.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    assert abs(_rl_summary(tmp_path)["mean"]["sched_live_ce"] - 2.7) < 1e-9


def test_chunk_sampler_without_replacement_and_deterministic():
    """ADR-0088: every chunk is visited exactly once per epoch (without
    replacement), epochs reshuffle, and the order is seed-deterministic
    (resume/replay discipline)."""
    from anvil.training.labbatch import ChunkSampler

    segs = [object() for _ in range(5)]
    s = ChunkSampler(segs, seed=7)
    epoch1 = [s.next()[0] for _ in range(5)]
    assert sorted(map(id, epoch1)) == sorted(map(id, segs))  # full coverage
    epoch2 = [s.next()[0] for _ in range(5)]
    assert sorted(map(id, epoch2)) == sorted(map(id, segs))
    # same seed reproduces the exact visit order
    t = ChunkSampler(segs, seed=7)
    assert [id(t.next()[0]) for _ in range(10)] == [id(x) for x in epoch1 + epoch2]
    with pytest.raises(ValueError):
        ChunkSampler([], seed=1)


def test_warmup_scale_ramp():
    """ADR-0088: linear 0->1 over N applied steps; 1.0 when disabled."""
    from anvil.training.labbatch import warmup_scale

    assert warmup_scale(0, 0) == 1.0
    assert warmup_scale(10_000, 0) == 1.0
    assert warmup_scale(0, 100) == pytest.approx(0.01)
    assert warmup_scale(49, 100) == pytest.approx(0.5)
    assert warmup_scale(99, 100) == 1.0
    assert warmup_scale(500, 100) == 1.0
