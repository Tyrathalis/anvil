"""Type stubs for anvil_bridge_pb2.

The protobuf-generated module builds message classes dynamically, which
current static analysis tools cannot see. These stubs provide enough shape
for pyright to reason about the production call sites. They are intentionally
structural, not exhaustive: add fields only when a checker or reader needs them.
"""

from typing import Any, Generic, TypeVar

from google.protobuf.message import Message

_T = TypeVar("_T", bound=Message)

class RepeatedCompositeFieldContainer(Generic[_T]):
    def add(self) -> _T: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Any: ...

class WorkerHello(Message):
    protocol_version: int
    worker_id: str
    engine_commit: str
    fork_commit: str
    capabilities: list[str]

class ServerHello(Message):
    protocol_version: int
    bridged_tags: list[str]
    one_shot_cast: bool
    default_deadline_ms: int
    def __init__(self, *, bridged_tags: list[str] | None = None, **kwargs: Any) -> None: ...

class DeckRef(Message):
    name: str
    content_hash: str

class GameStart(Message):
    game_id: str
    seed: int
    format_tag: str
    decks: list[DeckRef]
    provenance: str
    header: bytes

class Option(Message):
    id: int
    label: str
    features: bytes

class Constraints(Message):
    min: int
    max: int
    k: int

class DecisionRequest(Message):
    game_id: str
    decision_seq: int
    decision_tag: str
    shape: int
    options: list[Option]
    constraints: Constraints
    context: bytes
    observation: bytes
    retry_of: int
    deadline_ms: int
    echo_answer: DecisionResponse

class IndexList(Message):
    indices: list[int]

class CastPlan(Message):
    spell_option: int
    mode_options: list[int]
    x_value: int
    targets: TargetPlan
    optional_cost_options: list[int]
    payment_class_options: list[int]
    target_refs: RepeatedCompositeFieldContainer[EntityRef]
    has_x: bool
    host_level: bool

class AttackMap(Message):
    class Assignment(Message):
        attacker: EntityRef
        defender: EntityRef

    assignments: RepeatedCompositeFieldContainer[Assignment]

class BlockMap(Message):
    class Assignment(Message):
        blocker: EntityRef
        attacker: EntityRef

    assignments: RepeatedCompositeFieldContainer[Assignment]

class TargetPlan(Message):
    class Requirement(Message):
        candidate_options: list[int]

    requirements: list[Requirement]

class Construct(Message):
    attack_map: AttackMap
    block_map: BlockMap
    target_plan: TargetPlan
    cast_plan: CastPlan

class DecisionResponse(Message):
    decision_seq: int
    index: int
    indices: IndexList
    value: int
    flag: bool
    ordering: IndexList
    construct: Construct
    fallback: bool
    yield_directive: bytes

class EntityRef(Message):
    entity: int
    player: int
    ns: int

class GameEnd(Message):
    game_id: str
    winner: str
    turns: int
    wall_ms: int
    fallback_count: int
    fallback_reasons: list[str]
    draw_clock_hit: bool

class Ping(Message):
    nonce: int

class Drain(Message):
    reason: str

class WorkerMsg(Message):
    hello: WorkerHello
    game_start: GameStart
    request: DecisionRequest
    game_end: GameEnd
    ping: Ping

class ServerMsg(Message):
    hello: ServerHello
    response: DecisionResponse
    drain: Drain
    ping: Ping

SELECT_ONE: int
SELECT_K: int
INT_IN_RANGE: int
BOOL: int
ORDER_N: int
CONSTRUCT: int
