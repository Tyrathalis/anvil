"""The harness side of the fleet (09-14): a comma-list --bridge assigned
round-robin by invocation index, and the unconditional 20 s bridge
deadline on served runs."""

from anvil.bridge.harness.orchestrator import _worker_deadline, bridge_addrs, bridge_for, is_grpc


def _m(bridge, jvm_opts=()):
    return {"bridge": bridge, "jvm_opts": list(jvm_opts)}


def test_single_address_is_the_old_behavior():
    m = _m("grpc:localhost:50065")
    assert bridge_addrs(m) == ["grpc:localhost:50065"]
    assert all(bridge_for(m, i) == "grpc:localhost:50065" for i in range(5))


def test_round_robin_by_invocation():
    m = _m("grpc:localhost:50065, grpc:localhost:50066,grpc:localhost:50067")
    assert [bridge_for(m, i) for i in range(7)] == [
        "grpc:localhost:50065", "grpc:localhost:50066", "grpc:localhost:50067",
        "grpc:localhost:50065", "grpc:localhost:50066", "grpc:localhost:50067",
        "grpc:localhost:50065",
    ]


def test_deadline_raised_on_grpc_unless_pinned():
    assert _worker_deadline(_m("local-random"), []) == []
    assert not is_grpc(_m("local-random"))
    assert _worker_deadline(_m("grpc:localhost:1"), []) == ["-Danvil.bridge.deadline.ms=20000"]
    assert _worker_deadline(_m("grpc:localhost:1"), ["-Danvil.bridge.deadline.ms=9000"]) == []
    assert _worker_deadline(_m("grpc:localhost:1", ["-Danvil.bridge.deadline.ms=9000"]), []) == []


def test_default_chunk_is_four_rounds_per_worker():
    from anvil.bridge.harness.orchestrator import default_chunk

    assert default_chunk(64, 24) == 1
    assert default_chunk(1000, 16) == 16
    assert default_chunk(2000, 8) == 63
    assert default_chunk(3, 16) == 1
