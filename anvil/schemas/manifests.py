from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class RunManifest(BaseModel):
    """run.json schema (anvil.bridge.harness launch)."""

    model_config = {"extra": "allow"}  # additive fields (obs_schema, drill_*)

    run_id: str
    purpose: str
    created: str  # ISO datetime string
    fork_commit: str
    fork_dirty: bool
    anvil_commit: str
    jar: str
    jar_sha256: str
    protocol_version: int
    decks: list[str] | None = None
    format: str
    seed_base: int
    games: int
    chunk: int
    start_index: int
    workers: int
    heap: str
    jvm_opts: list[str]
    bridge: str
    tags: str = ""
    nice: bool
    obs: bool = False
    obs_schema: int | None = None
    census: bool = False
    bridge_seats: int | None = None
    reask: bool = False
    rollout_k: int | None = None
    rollout_points: int | None = None
    drill_file: str | None = None
    drill_source: str | None = None
    drill_stop: bool = False
    fork_obs: bool = False
    pairs_file: str | None = None
    pairs_source: str | None = None
    pairs_sha256: str | None = None
    n_pairs: int | None = None
    games_per_pair: int | None = None
    pool_version: str | None = None

    @field_validator("created")
    @classmethod
    def _created_iso(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v


class StoreRunMeta(BaseModel):
    """Nested run provenance inside store manifest.json."""

    model_config = {"extra": "allow", "validate_default": True}
    run_id: str
    fork_commit: str = ""
    jar_sha256: str = ""
    anvil_commit: str = ""
    protocol_version: int = 0
    seed_base: int = 0
    games: int = 0
    format: str = ""
    decks: list[str] | None = None
    chunk: int = 200
    workers: int = 1


class StoreManifest(BaseModel):
    """trajectory store manifest.json schema."""

    model_config = {"extra": "allow"}
    source: str
    run: StoreRunMeta
    pool_version: str
    obs_schema: int
    created: str | None = None
    games: int | None = None
    decisions: int | None = None
    raw_bytes: int | None = None
    compressed_bytes: int | None = None
    drill: dict[str, Any] | None = None


class IndexEntry(BaseModel):
    """One index.jsonl row."""

    file: str
    g: int
    off: int
    clen: int
    rlen: int
    seed: int
    recs: int | None = None


class GameOutcome(BaseModel):
    """games.jsonl outcome row."""

    model_config = {"extra": "allow"}
    i: int
    status: str
    winner: str | None = None
    turns: int | None = None
    seed: int | None = None
    ms: int | None = None
    fork: dict[str, Any] | None = None


class PoolEntry(BaseModel):
    sources: list[str | int]
    first_seen: str | None = None


class DeckEntry(BaseModel):
    deck_id: int
    commanders: list[str]
    file: str
    event_title: str | None = None
    event_date: str | None = None
    source_url: str | None = None


class ExcludedDeck(BaseModel):
    deck_id: int | None = None
    reason: str
    url: str | None = None


class PoolManifest(BaseModel):
    """data/pool/pool-*.json schema."""

    format: str
    pool_version: str
    banlist: dict[str, Any]
    fork_commit: str
    decks: list[DeckEntry]
    pool: dict[str, PoolEntry]
    counts: dict[str, int]
    excluded: list[ExcludedDeck]


class TrainConfig(BaseModel):
    """Subset of checkpoint config that downstream tools consume."""

    model_config = {"extra": "allow"}
    store: str
    embed: str
    pool_manifest: str
    batch: int = 256
    lr: float = 3e-4
    warmup: int = 500
    steps: int = 20000
    pass_weight: float = 0.1
    methods_version: int = 1
    sa_vocab_version: int = 1
    sa_vocab_size: int = 0
    transform_version: int
    embed_meta: dict[str, Any]
    params: int | None = None
    max_games: int | None = None
    eval_every: int = 1000
    eval_batches: int = 60
    final_eval_batches: int = 600
    seed: int = 0
    workers: int = 8
    null_text: bool = False
