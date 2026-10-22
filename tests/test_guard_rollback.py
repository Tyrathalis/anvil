"""10-21: the rolling-back guard's decision logic (selfplay.guard_decision) —
a pure function over the guard outcome, the rollback window and the lr
multiplier. The design note is in the m12 running record (10-21); the halt
stays the registered response (ADR-0118 / ADR-0123)."""

from anvil.training.selfplay import guard_decision

BREACH = ["guard: kl_mu 0.072 > 0.06"]


def _d(guards=BREACH, action="rollback", it=10, last=None, window=5, lr=1e-5, lr_mult=1.0,
       mult=0.5, floor=1e-7):
    return guard_decision(guards, action, it, last, window, lr, lr_mult, mult, floor)


def test_no_breach_accepts_and_keeps_the_multiplier():
    assert _d(guards=[]) == ("accept", 1.0, None)
    assert _d(guards=[], lr_mult=0.25) == ("accept", 0.25, None)


def test_halt_is_the_default_response():
    assert _d(action="halt") == ("halt", 1.0, None)


def test_a_breach_rolls_back_and_cuts_the_lr():
    kind, m, entry = _d()
    assert kind == "rollback" and m == 0.5
    assert entry == {"iteration": 10, "rule": BREACH[0], "lr_before": 1e-5, "lr_after": 5e-6, "lr_mult": 0.5}


def test_the_cut_compounds_and_the_rule_lists_every_guard():
    kind, m, entry = _d(guards=["guard: a", "guard: b"], lr_mult=0.5)
    assert kind == "rollback" and m == 0.25
    assert entry["rule"] == "guard: a; guard: b"
    assert entry["lr_before"] == 5e-6 and abs(entry["lr_after"] - 2.5e-6) < 1e-15


def test_a_second_breach_inside_the_window_halts_and_outside_rolls_back():
    assert _d(it=15, last=10, window=5)[0] == "halt"      # the window's edge halts
    assert _d(it=11, last=10, window=5)[0] == "halt"
    assert _d(it=16, last=10, window=5)[0] == "rollback"  # one past the window
    assert _d(it=12, last=10, window=1)[0] == "rollback"


def test_the_floor_clamps_the_lr_and_never_raises_it():
    kind, m, entry = _d(lr=1e-5, lr_mult=1 / 64, mult=0.5, floor=1e-7)   # 1.56e-7 -> would be 7.8e-8
    assert kind == "rollback"
    assert abs(entry["lr_after"] - 1e-7) < 1e-18 and abs(m - 0.01) < 1e-12
    # already at the floor: the rollback still rejects the iteration, the lr stays
    kind, m2, entry = _d(lr=1e-5, lr_mult=0.01, mult=0.5, floor=1e-7)
    assert kind == "rollback" and abs(m2 - 0.01) < 1e-12 and abs(entry["lr_before"] - entry["lr_after"]) < 1e-18
    # floor 0 = no floor
    assert _d(lr=1e-5, lr_mult=0.01, mult=0.5, floor=0)[1] == 0.005
