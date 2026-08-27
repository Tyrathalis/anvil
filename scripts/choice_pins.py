"""M11 routing-probe launch pins — PINNED PRE-DATA 2026-08-26
(m11-routing-probes-spec.md "Launch pins" is the prose mirror; THIS module
is the executable single source — the planner and the read script import
from here and must not redefine).

The R1/ratesweep discipline: set before any forcing data exists, not tuned
afterward; invalidated only by demonstrated instrument error at the lane
smoke, and any change re-pins loudly in both places.
"""

# ---------------------------------------------------------------- replay
# The m10-ceiling-census configuration verbatim (the mined windows replay
# deterministically to the fork point under these).
CENSUS_SEED_BASE = 20520825
CENSUS_GAMES = 500

# ----------------------------------------------------------------- arms
# Probe T: natural + candidate indices 0..min(ncand, cap)-1, index order =
# the engine's deterministic candidate list (DC pool is singleton, so
# duplicate-name arms are a non-issue — recorded). Probe P: natural +
# force-pay + force-decline.
T_ARM_CAP = 6

# ---------------------------------------------------------------- rolls
# K paired rolls per (point, arm); rollSeeds target-turn-keyed (engine).
# Select/score split for every best-of claim; each-arm-vs-natural pooled
# over all K rolls is the unbiased secondary.
K_ROLLS = 8
SELECT_ROLLS = (0, 1, 2, 3)

# A forced arm's roll pairs against natural's same-roll outcome only when
# the directive FIRED; a point enters the per-window read at >= this many
# fired scoring rolls, else it moves to the coverage denominator.
MIN_FIRED_SCORING = 2

# -------------------------------------------------------------- horizon
HORIZON = 0  # game end — the routing read is win-rate-based, no proxy stage

# ------------------------------------------------------------- routing
# The ADR-0078 threshold scale (adjudicated 2026-08-26): gate-scale point
# >= ROUTING_POINT pp/game => SCHEDULE into M11; CI-lower >= ROUTING_FLOOR
# strengthens; below => re-defer with the number.
ROUTING_POINT = 2.2
ROUTING_FLOOR = 1.1

# Mined per-seat-game window rates (m11_mining.py + the launch-pins
# universe count, 2026-08-26): the FULL mined rate is the gate-scale
# multiplier; the ~15% non-forkable stratum extrapolation is a recorded
# assumption, reported alongside a coverage-discounted row.
RATE_T = 1.078   # 1,078 family events / 1,000 seat-games
RATE_P = 1.656   # 1,656 payCostToPreventEffect events / 1,000 seat-games
FORKABLE_T = 0.86
FORKABLE_P = 0.85

# ---------------------------------------------------------------- lanes
LANES = 12  # quiet-box stage-2 precedent; nice -19, pause/resume by design
