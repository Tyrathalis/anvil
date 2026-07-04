"""Deck-pair schedule (anvil/bridge/harness/pairs.py): the D3 corpus schedule
must be a pure function of (deck list, n_pairs, seed) — manifests pin those
three and nothing else."""

import collections

from anvil.bridge.harness.pairs import pair_schedule

DECKS = [f"deck-{i:02d}.dck" for i in range(11)]  # odd count on purpose


def test_deterministic():
    assert pair_schedule(DECKS, 40, 123) == pair_schedule(DECKS, 40, 123)


def test_seed_changes_schedule():
    assert pair_schedule(DECKS, 40, 123) != pair_schedule(DECKS, 40, 124)


def test_count_and_shape():
    pairs = pair_schedule(DECKS, 37, 7)
    assert len(pairs) == 37
    assert all(len(p) == 2 and p[0] != p[1] for p in pairs)


def test_within_pass_no_repeats():
    # first pass = floor(11/2) = 5 pairs, each deck at most once
    pairs = pair_schedule(DECKS, 5, 99)
    used = [d for p in pairs for d in p]
    assert len(used) == len(set(used))


def test_every_deck_covered_over_passes():
    # 40 pairs = 8 passes over 11 decks; the odd-one-out rotates randomly,
    # so full coverage is overwhelmingly certain by then
    pairs = pair_schedule(DECKS, 40, 5)
    counts = collections.Counter(d for p in pairs for d in p)
    assert set(counts) == set(DECKS)
    # near-uniform: no deck hogging or starving beyond the odd-deck wobble
    assert max(counts.values()) - min(counts.values()) <= 8
