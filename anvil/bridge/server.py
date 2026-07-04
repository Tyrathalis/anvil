"""Anvil decision server (M0): answers DecisionBridge sessions.

Modes:
- echo   -- echo the worker's pre-drawn answer back (bridge-tax instrument:
            gRPC-arm games are bit-identical to local-arm games, so the
            throughput delta isolates serialization + transport).
- random -- answer uniformly at random server-side, seeded per game from
            GameStart.seed (deterministic per seed; the M1-shaped mode).

Run: uv run python -m anvil.bridge.server [--port 50051] [--mode echo]
     [--tags mtg.priority,mtg.mulligan_keep,...]

One bidirectional stream per worker; one outstanding request per stream by
construction (the worker's game thread blocks), so the servicer is a plain
loop. Stats print on Ctrl-C.
"""

from __future__ import annotations

import argparse
import random
import time
from collections import Counter
from concurrent import futures

import grpc

from anvil.bridge.pb import anvil_bridge_pb2 as pb
from anvil.bridge.pb import anvil_bridge_pb2_grpc as pb_grpc

PROTOCOL_VERSION = 0
DEFAULT_TAGS = (
    "mtg.priority,mtg.mulligan_keep,mtg.mulligan_tuck,mtg.trigger,mtg.binary,mtg.number"
)


class DecisionServicer(pb_grpc.DecisionBridgeServicer):
    def __init__(self, mode: str, bridged_tags: list[str], deadline_ms: int = 5000):
        self.mode = mode
        self.bridged_tags = bridged_tags
        self.deadline_ms = deadline_ms
        self.requests_by_tag: Counter[str] = Counter()
        self.games = 0
        self.t0 = time.monotonic()

    def _answer(self, req: pb.DecisionRequest, rng: random.Random) -> pb.DecisionResponse:
        if self.mode == "echo" and req.HasField("echo_answer"):
            resp = pb.DecisionResponse()
            resp.CopyFrom(req.echo_answer)
            resp.decision_seq = req.decision_seq
            return resp
        resp = pb.DecisionResponse(decision_seq=req.decision_seq)
        n = len(req.options)
        c = req.constraints
        if req.shape == pb.SELECT_ONE:
            resp.index = rng.randrange(n) if n > 1 else 0
        elif req.shape == pb.SELECT_K:
            k = min(c.k or c.min, n)
            resp.indices.indices.extend(sorted(rng.sample(range(n), int(k))))
        elif req.shape == pb.INT_IN_RANGE:
            resp.value = rng.randint(c.min, c.max) if c.max > c.min else c.min
        elif req.shape == pb.BOOL:
            resp.flag = rng.random() < 0.5
        elif req.shape == pb.ORDER_N:
            order = list(range(n))
            rng.shuffle(order)
            resp.ordering.indices.extend(order)
        else:
            resp.fallback = True  # CONSTRUCT not answered at M0
        return resp

    def Session(self, request_iterator, context):
        rng = random.Random(0)
        worker = "?"
        for msg in request_iterator:
            kind = msg.WhichOneof("msg")
            if kind == "hello":
                worker = msg.hello.worker_id
                yield pb.ServerMsg(hello=pb.ServerHello(
                    protocol_version=PROTOCOL_VERSION,
                    bridged_tags=self.bridged_tags,
                    default_deadline_ms=self.deadline_ms,
                ))
            elif kind == "game_start":
                self.games += 1
                rng = random.Random(msg.game_start.seed)
            elif kind == "request":
                self.requests_by_tag[msg.request.decision_tag] += 1
                yield pb.ServerMsg(response=self._answer(msg.request, rng))
            elif kind == "game_end":
                pass  # worker-side logs are authoritative at M0
            elif kind == "ping":
                yield pb.ServerMsg(ping=msg.ping)
        print(f"[server] stream closed: worker={worker}")

    def stats(self) -> str:
        dt = time.monotonic() - self.t0
        total = sum(self.requests_by_tag.values())
        lines = [f"{self.games} games, {total} requests in {dt:.0f}s ({total / dt:.0f} rps)"]
        lines += [f"  {t}: {n}" for t, n in self.requests_by_tag.most_common()]
        return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=50051)
    ap.add_argument("--mode", choices=["echo", "random"], default="echo")
    ap.add_argument("--tags", default=DEFAULT_TAGS)
    args = ap.parse_args()

    servicer = DecisionServicer(args.mode, args.tags.split(","))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=32))
    pb_grpc.add_DecisionBridgeServicer_to_server(servicer, server)
    server.add_insecure_port(f"127.0.0.1:{args.port}")
    server.start()
    print(f"[server] mode={args.mode} port={args.port} tags={servicer.bridged_tags}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n[server] " + servicer.stats())
        server.stop(grace=1)


if __name__ == "__main__":
    main()
