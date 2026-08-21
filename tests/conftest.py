"""Shared test helpers."""

import pytest


def era_store(path):
    """Open a trajectory store, skipping the calling test when the store
    predates the current obs schema. Fixture stores are era-scoped assets
    (never read across a dataset boundary): a skip here means the pinned
    fixture store must be regenerated on the current jar and the STORE
    path repointed — the skip reason is the reminder, not the resolution.
    """
    from anvil.store.trajectories import open_store

    store = open_store(str(path))
    idx = store.game_indices()
    if idx:
        try:
            store.game(idx[0])
        except ValueError as e:
            if "schema version" in str(e):
                pytest.skip(f"era-scoped fixture store {path}: {e}")
            raise
    return store
