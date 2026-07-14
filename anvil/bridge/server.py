"""Anvil decision server (M0 echo/random + M1 model): answers DecisionBridge sessions.

Modes:
- echo   -- echo the worker's pre-drawn answer back (bridge-tax instrument:
            gRPC-arm games are bit-identical to local-arm games, so the
            throughput delta isolates serialization + transport).
- random -- answer uniformly at random server-side, seeded per game from
            GameStart.seed (deterministic per seed; the M1-shaped mode).
- model  -- M1 D8: featurize the wire observation (same code path as the
            training loader), run AnvilNet.act, answer CastPlans + one-field
            tags. --ckpt required; --pass-delta is the calibration arm knob
            (pass_calibration.json "delta"). mtg.mulligan_tuck stays
            heuristic-fallback at D8 (SELECT_K answer mapping deferred).

Run: uv run python -m anvil.bridge.server [--port 50051] [--mode echo]
     [--tags mtg.priority,mtg.mulligan_keep,...]
     [--ckpt data/training/d7-ep3/last.pt --pass-delta 0.0]

One bidirectional stream per worker; one outstanding request per stream by
construction (the worker's game thread blocks), so the servicer is a plain
loop. Model inference is batch-1 behind a lock at first light — micro-batching
across streams is the known lever if the w=16 arms want it. Stats print on
Ctrl-C.
"""

from __future__ import annotations

import argparse
import json
import random
import threading
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
MODEL_TAGS = "mtg.priority,mtg.mulligan_keep,mtg.trigger,mtg.binary,mtg.number"


class ModelBackend:
    """Loads a D7 checkpoint and answers decisions. Import of torch/model
    machinery is deferred to here so echo/random sessions stay lightweight."""

    def __init__(self, ckpt_path: str, pass_delta: float, device: str = "cuda"):
        import torch

        from anvil.bridge.featurize import Featurizer
        from anvil.training.dataset import default_methods
        from anvil.training.train import build_net

        self.torch = torch
        ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
        cfg = ckpt["config"]
        # sa_vocab_size absent = pre-D2 host-level checkpoint: the model has
        # no SA descriptor and answers host_level=True (Java runs the full
        # disambiguation ladder). D2+ checkpoints name the SA themselves.
        self.n_sa = cfg.get("sa_vocab_size", 0)
        self.net = build_net(cfg["embed"], cfg["pool_manifest"],
                             len(default_methods()), n_sa=self.n_sa).to(device)
        self.net.load_compat(ckpt["model"])
        self.net.eval()
        self.feat = Featurizer(cfg["embed"], default_methods())
        if self.n_sa and self.n_sa != len(self.feat.sa_vocab):
            raise ValueError(
                f"checkpoint sa_vocab_size {self.n_sa} != pinned sa_vocab "
                f"{len(self.feat.sa_vocab)} — serve/train vocab skew")
        self.pass_delta = pass_delta
        self.device = device
        self.lock = threading.Lock()
        self.counts: Counter[str] = Counter()
        print(f"[server] model {ckpt_path} step={ckpt.get('step')} "
              f"pass_delta={pass_delta} device={device}")

    def answer(self, req: pb.DecisionRequest, header: dict | None) -> pb.DecisionResponse | None:
        """None = decline (worker falls back, tagged). Any exception is the
        caller's to turn into a loud decline — silence would poison an arm."""
        from anvil.bridge.featurize import TAG_TASK
        from anvil.training.dataset import collate

        task = TAG_TASK.get(req.decision_tag)
        if task is None or not req.observation or header is None:
            return None
        dec = json.loads(req.observation)
        ex, aux = self.feat.example(dec, header, task)
        batch = {k: v.to(self.device) for k, v in collate([ex]).items()}
        delta = self.pass_delta if task == "priority" else 0.0
        with self.lock, self.torch.autocast(self.device, dtype=self.torch.bfloat16):
            out = self.net.act(batch, pass_delta=delta)
        resp = pb.DecisionResponse(decision_seq=req.decision_seq)
        if task == "priority":
            resp.construct.cast_plan.CopyFrom(self._castplan(out, aux))
        elif task in ("mull_keep", "trigger", "binary"):
            resp.flag = bool(out["bool"][0])
        elif task == "number":
            n = int(out["num"][0])
            if req.shape == pb.SELECT_ONE:
                # list-variant chooseNumber: labels are the values; nearest wins
                try:
                    vals = [int(o.label) for o in req.options]
                except ValueError:
                    return None
                resp.index = min(range(len(vals)), key=lambda i: abs(vals[i] - n))
            else:
                c = req.constraints
                v = max(int(c.min), min(n, int(c.max))) if c.max > c.min else int(c.min)
                if v != n:
                    self.counts["num_clamped"] += 1
                resp.value = v
        return resp

    def _castplan(self, out: dict, aux: dict) -> pb.CastPlan:
        cp = pb.CastPlan()
        choice = int(out["choice"][0])
        if choice == 0:
            self.counts["pass"] += 1
            return cp  # spell_option 0 = pass (label-space convention)
        cp.spell_option = aux["cand_first_opt"][choice] + 1
        # SA-level model (D2+): the option index IS the chosen SA — the Java
        # ladder skips its kind/order rungs (shape->pay only). Host-level
        # checkpoints keep the full ladder.
        cp.host_level = self.n_sa == 0
        n_ent, stop = int(out["n_ent"]), int(out["stop_idx"])
        for t in range(out["tgt_picks"].shape[1]):
            pick = int(out["tgt_picks"][0, t])
            if pick == stop:
                break
            ref = cp.target_refs.add()
            if pick < n_ent:
                # dedup-group row -> deterministic representative (lowest id)
                eid = aux["row_min_id"].get(pick, -1)
                ref.entity = eid
                if eid in aux["stack_ids"]:
                    ref.ns = 1
            else:
                ref.player = pick - n_ent  # registered index (label convention)
        x = int(out["x_cls"][0])
        cp.has_x = True
        # class 17 = ">16" overflow bucket; clamp + count (decision 2026-07-10)
        cp.x_value = min(x, 16)
        if x >= 17:
            self.counts["x_overflow_clamped"] += 1
        self.counts["cast"] += 1
        return cp


class DecisionServicer(pb_grpc.DecisionBridgeServicer):
    def __init__(self, mode: str, bridged_tags: list[str], deadline_ms: int = 5000,
                 backend: ModelBackend | None = None):
        self.mode = mode
        self.bridged_tags = bridged_tags
        self.deadline_ms = deadline_ms
        self.backend = backend
        self.requests_by_tag: Counter[str] = Counter()
        self.fallbacks: Counter[str] = Counter()
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
        header: dict | None = None
        for msg in request_iterator:
            kind = msg.WhichOneof("msg")
            if kind == "hello":
                worker = msg.hello.worker_id
                yield pb.ServerMsg(hello=pb.ServerHello(
                    protocol_version=PROTOCOL_VERSION,
                    bridged_tags=self.bridged_tags,
                    default_deadline_ms=self.deadline_ms,
                    one_shot_cast=self.mode == "model",
                ))
            elif kind == "game_start":
                self.games += 1
                rng = random.Random(msg.game_start.seed)
                header = None
                if msg.game_start.header:
                    try:
                        header = json.loads(msg.game_start.header)
                    except ValueError:
                        print(f"[server] worker={worker}: unparseable game header")
            elif kind == "request":
                self.requests_by_tag[msg.request.decision_tag] += 1
                if self.mode == "model":
                    yield pb.ServerMsg(response=self._model_answer(msg.request, header))
                else:
                    yield pb.ServerMsg(response=self._answer(msg.request, rng))
            elif kind == "game_end":
                pass  # worker-side logs are authoritative at M0
            elif kind == "ping":
                yield pb.ServerMsg(ping=msg.ping)
        print(f"[server] stream closed: worker={worker}")

    def _model_answer(self, req: pb.DecisionRequest, header: dict | None) -> pb.DecisionResponse:
        try:
            resp = self.backend.answer(req, header)
        except Exception as e:  # loud decline; a silent wrong answer poisons the arm
            print(f"[server] MODEL ERROR on {req.decision_tag} seq={req.decision_seq}: {e!r}")
            resp = None
        if resp is None:
            self.fallbacks[req.decision_tag] += 1
            return pb.DecisionResponse(decision_seq=req.decision_seq, fallback=True)
        return resp

    def stats(self) -> str:
        dt = time.monotonic() - self.t0
        total = sum(self.requests_by_tag.values())
        lines = [f"{self.games} games, {total} requests in {dt:.0f}s ({total / dt:.0f} rps)"]
        lines += [f"  {t}: {n}" for t, n in self.requests_by_tag.most_common()]
        if self.fallbacks:
            lines += [f"  FALLBACK {t}: {n}" for t, n in self.fallbacks.most_common()]
        if self.backend is not None:
            lines += [f"  model {k}: {n}" for k, n in self.backend.counts.most_common()]
        return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=50051)
    ap.add_argument("--mode", choices=["echo", "random", "model"], default="echo")
    ap.add_argument("--tags", default=None,
                    help=f"default: {DEFAULT_TAGS} (echo/random) or {MODEL_TAGS} (model)")
    ap.add_argument("--ckpt", default="data/training/d7-ep3/last.pt")
    ap.add_argument("--pass-delta", type=float, default=0.0,
                    help="PASS-logit offset (pass_calibration.json delta; arm knob)")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    backend = None
    if args.mode == "model":
        backend = ModelBackend(args.ckpt, args.pass_delta, args.device)
    tags = args.tags if args.tags is not None else (
        MODEL_TAGS if args.mode == "model" else DEFAULT_TAGS)
    servicer = DecisionServicer(args.mode, tags.split(","), backend=backend)
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
