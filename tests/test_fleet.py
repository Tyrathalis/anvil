"""The model-server fleet (the throughput week, 09-14): N servers on
consecutive ports, per-child output parts, the shutdown merge."""

import json

from anvil.bridge.fleet import (
    bridge_addrs,
    child_argv,
    merge_outputs,
    output_paths,
    servers_for,
)


def test_servers_for_default_is_one_per_eight_workers():
    assert servers_for(8) == 1
    assert servers_for(9) == 2
    assert servers_for(16) == 2
    assert servers_for(24) == 3
    assert servers_for(1) == 1
    assert servers_for(16, servers=1) == 1  # explicit wins
    assert servers_for(4, servers=3) == 3


def test_bridge_addrs_consecutive_ports():
    assert bridge_addrs(50065, 1) == "grpc:localhost:50065"
    assert bridge_addrs(50065, 3) == "grpc:localhost:50065,grpc:localhost:50066,grpc:localhost:50067"


def test_child_argv_rewrites_port_and_output_paths_and_drops_servers():
    argv = ["--mode", "model", "--ckpt", "c.pt", "--port", "50063", "--servers", "3",
            "--sample", "--mu-out", "it/mu.jsonl", "--bind-trace=it/bind.jsonl", "--pass-delta", "0"]
    c2 = child_argv(argv, 2, 50063)
    assert "--servers" not in c2
    assert c2[c2.index("--port") + 1] == "50065"
    assert c2[c2.index("--mu-out") + 1] == "it/mu.jsonl.s2"
    assert "--bind-trace=it/bind.jsonl.s2" in c2
    assert c2[-2:] == ["--pass-delta", "0"]
    # child 0 keeps the base port
    assert child_argv(argv, 0, 50063)[argv.index("--port") + 1] == "50063"


def test_output_paths_default_counts_beside_mu():
    argv = ["--mu-out", "x/mu.jsonl"]
    assert output_paths(argv) == {"--mu-out": "x/mu.jsonl", "--counts-out": "x/mu.jsonl.counts.json"}
    argv = ["--counts-out", "y/c.json"]
    assert output_paths(argv) == {"--counts-out": "y/c.json"}


def test_merge_outputs_appends_jsonl_and_sums_counts(tmp_path):
    mu = tmp_path / "mu.jsonl"
    mu.write_text('{"g": 0}\n')  # an earlier fleet's rows (the append contract)
    (tmp_path / "mu.jsonl.s0").write_text('{"g": 1}\n{"g": 2}')  # no trailing newline
    (tmp_path / "mu.jsonl.s1").write_text('{"g": 3}\n')
    (tmp_path / "mu.jsonl.s0.counts.json").write_text(
        json.dumps({"cast": 3, "gpu_batch_1": 5, "fallbacks": {"mtg.pay": 1}, "mode": "x"})
    )
    (tmp_path / "mu.jsonl.s1.counts.json").write_text(
        json.dumps({"cast": 4, "gpu_batch_2": 1, "fallbacks": {"mtg.pay": 2, "mtg.mode": 1}})
    )
    argv = ["--mu-out", str(mu)]
    folded = merge_outputs(argv, 2)
    assert folded == {str(mu): 2, str(mu) + ".counts.json": 2}
    rows = [json.loads(l) for l in mu.read_text().splitlines()]
    assert [r["g"] for r in rows] == [0, 1, 2, 3]
    counts = json.loads((tmp_path / "mu.jsonl.counts.json").read_text())
    assert counts["cast"] == 7
    assert counts["gpu_batch_1"] == 5 and counts["gpu_batch_2"] == 1
    assert counts["fallbacks"] == {"mtg.pay": 3, "mtg.mode": 1}
    assert counts["mode"] == "x"
    assert counts["servers"] == 2
    assert not (tmp_path / "mu.jsonl.s0").exists()
    assert not (tmp_path / "mu.jsonl.s1.counts.json").exists()


def test_merge_outputs_explicit_counts_path(tmp_path):
    c = tmp_path / "server.counts.json"
    (tmp_path / "server.counts.json.s0").write_text(json.dumps({"a": 1}))
    (tmp_path / "server.counts.json.s1").write_text(json.dumps({"a": 2, "b": 1}))
    merge_outputs(["--counts-out", str(c)], 2)
    assert json.loads(c.read_text()) == {"a": 3, "b": 1, "servers": 2}
