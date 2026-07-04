"""Game-seed derivation: game i = the i-th output of a SplitMix64 stream
seeded at seed_base, i.e. mix(seed_base + (i+1)*GOLDEN).

Must stay in lockstep with the Java side (AnvilRun.splitmix64); tests pin a
known value. A keyed stream rather than base^i or base+i because both of
those collide structurally across nearby bases (base^1 == (base+1)^0);
distinct streams only collide if bases differ by a multiple of GOLDEN.
"""

MASK = (1 << 64) - 1
GOLDEN = 0x9E3779B97F4A7C15


def splitmix64(z: int) -> int:
    z = (z + GOLDEN) & MASK
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)


def game_seed(seed_base: int, index: int) -> int:
    """The seed for game `index` of a run, as a signed 64-bit value (Java long)."""
    u = splitmix64((seed_base + index * GOLDEN) & MASK)
    return u - (1 << 64) if u >= (1 << 63) else u
