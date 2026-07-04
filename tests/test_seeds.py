"""Pin the Java/Python seed-derivation lockstep (AnvilRun.splitmix64 <-> seeds.py).

The pinned value was produced by the Java worker (fork, AnvilRun):
  forge anvil ... -range 5 1 -seedbase 12345  ->  game 5 seed=6217189988962137646
If this test fails, the two implementations have drifted and every manifest's
replay guarantee is void — fix before running anything.
"""

from anvil.bridge.harness.seeds import game_seed, splitmix64


def test_java_lockstep_pin():
    assert game_seed(12345, 5) == 6217189988962137646


def test_signed_range():
    for base, i in [(0, 0), (1 << 61, 999), (20260704, 123456)]:
        s = game_seed(base, i)
        assert -(1 << 63) <= s < (1 << 63)


def test_distinct_across_nearby_bases():
    # The reason for SplitMix64 over base+i: nearby bases must not collide.
    a = {game_seed(1000, i) for i in range(1000)}
    b = {game_seed(1001, i) for i in range(1000)}
    assert not a & b


def test_splitmix64_reference():
    # SplitMix64 reference vector (seed 0 first output).
    assert splitmix64(0) == 0xE220A8397B1DCDAF
