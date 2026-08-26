"""M10 planning-ceiling launch pins — PINNED PRE-DATA 2026-08-25 (session 4,
the launch commit; m10-ceiling-spec.md "Launch commit" section is the prose
record, THIS module is the executable single source — the sweep planner and
the read script import from here and must not redefine).

The R1/ratesweep discipline: these values are set before any census or
sweep data exists and are not tuned afterward; they may be invalidated
only by demonstrated instrument error at the model-serve smoke, and any
change re-pins loudly in both places.
"""

# ---------------------------------------------------------------- seeds
# Census seed base — the 2052xxxx block named in the pre-registration
# (suffix = launch date). Harness -seedbase convention (splitmix per-game).
CENSUS_SEED_BASE = 20520825
CENSUS_GAMES = 500  # paygoals2 pair list: 100 pairs x gpp 5

# Sampling rng seed — one seed, DOCUMENTED DRAW ORDER (order is part of
# the pin; re-running the planner reproduces the sample byte-identically):
#   draw 1: uniform 600 eligible turn-groups (sorted (store, g, t) order)
#   draw 2: 200-turn marginal-stratum subset of the 600
#   draw 3: 100-turn h4 side-sample of the 600
# Draws 2 and 3 are independent subsets of the 600; overlap is allowed
# (orthogonal purposes: payment attribution vs horizon sensitivity).
SAMPLE_RNG_SEED = 20520825

def arm_fill_seed(g: int, t: int) -> int:
    """Per-turn child seed for the n>=4 seeded-random ordered-subset arm
    fill — iteration-order-independent, so a partial replan reproduces
    any turn's arms without replaying the global rng stream."""
    return SAMPLE_RNG_SEED * 1_000_003 + g * 1_009 + t

# ---------------------------------------------------------- stage 1: theta
# Certification margin on the schedule composite, descended from the
# payment_certify precedent (MARGIN default 2.0, CONSISTENT 0.75). The
# select/score split is structural (spec): arms selected on rolls 0-3 by
# mean composite, positivity scored on rolls 4-7 only.
THETA = 2.0
CONSISTENT = 0.75          # fraction of scoring rolls sign-agreeing with the mean
SELECT_ROLLS = (0, 1, 2, 3)
SCORE_ROLLS = (4, 5, 6, 7)
# Validity: a roll-pair counts only if both the arm row and the paired
# NATURAL row are non-crash; an arm is a candidate only if non-void
# (hold-all is always non-void) with >= MIN_VALID select and score pairs.
# Degraded-but-partially-executed arms REMAIN candidates (divergence is
# part of the measured policy, fork-5).
MIN_VALID_ROLLS = 2

def composite(arm_axes: dict, nat_axes: dict) -> float:
    """Schedule h2 composite, payer perspective, paired vs NATURAL —
    the payment_certify axes reused in one blend: color_hold's
    development core + blocker_pressure's life/power terms at half
    weight + the shared won-weight 3. dev = creatures + lands - hand."""
    d = {k: arm_axes[k] - nat_axes[k] for k in arm_axes}
    return d["dev"] + 0.5 * d["life"] + 0.5 * d["power"] + 3 * d["won"]

def axes(row: dict, seat: int) -> dict:
    """Certify-axes extraction from a sched labels row's snap (the
    payment_certify._axes shape; seat = the directed seat, known from
    the schedfile — no name inference)."""
    s = row["snap"]
    o = 1 - seat
    return {
        "life": s["life"][seat] - s["life"][o],
        "creatures": s["creatures"][seat],
        "power": s["power"][seat],
        "dev": s["creatures"][seat] + s["lands"][seat] - s["hand"][seat],
        "won": 1 if row.get("winner") == seat
               else (-1 if row.get("winner") == o else 0),
    }

# ------------------------------------------------- stage 1b: h4 threshold
# The 1b flag fires iff BOTH hold on the 100 shared side-sample turns:
# ratio (>= 25% relative more turns certify at h4) guards the ADR-0053
# compounding direction; the absolute floor guards small-n noise. On
# fire: the rate carries an h4-informed correction band and the
# conversion population is revisited at the read session (amendment).
H4_RATIO = 1.25
H4_MIN_NET = 3

# -------------------------------------------------------- frame constants
SAMPLE_N = 600
MARGINAL_N = 200
H4_N = 100
ARM_CAP = 16          # directed arms per turn (natural excluded)
K_ROLLS = 8
HORIZON_H2 = 2
HORIZON_H4 = 4
