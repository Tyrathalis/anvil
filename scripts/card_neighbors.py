"""Record each card's k nearest neighbors from a frozen embedding cache.

Usage:
  uv run python scripts/card_neighbors.py \
      data/embeddings/37c3d6d6-bge-m3.safetensors \
      data/neighbors/37c3d6d6-bge-m3-baseline.json \
      -k 5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from safetensors.torch import load_file


def topk_neighbors(emb: np.ndarray, names: list[str], k: int = 5) -> dict[str, list[dict[str, Any]]]:
    """Cosine-similarity top-k neighbors for unit-norm rows."""
    # emb is assumed L2-normalized (cosine = dot)
    sim = emb @ emb.T  # (n, n)
    np.fill_diagonal(sim, -np.inf)  # exclude self
    # argpartition for efficiency, then sort each top-k partition
    n = emb.shape[0]
    k_eff = min(k + 1, n)
    parts = np.argpartition(-sim, k_eff - 1, axis=1)[:, :k_eff]
    out: dict[str, list[dict[str, Any]]] = {}
    for i, name in enumerate(names):
        idx = parts[i]
        scores = sim[i, idx]
        order = np.argsort(-scores)
        neighbors = []
        for j in idx[order]:
            if j == i:
                continue
            if len(neighbors) >= k:
                break
            neighbors.append({"name": names[j], "sim": float(round(sim[i, j], 4))})
        out[name] = neighbors
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("embedding", type=Path, help=".safetensors embedding cache")
    ap.add_argument("output", type=Path, help="output JSON path")
    ap.add_argument("-k", "--k", type=int, default=5, help="neighbors per card")
    a = ap.parse_args()

    meta_path = a.embedding.with_suffix(".json")
    meta = json.loads(meta_path.read_text())
    names: list[str] = meta["names"]
    emb = load_file(a.embedding)["embeddings"].float().numpy()
    if emb.shape[0] != len(names):
        raise ValueError(f"shape/name mismatch: {emb.shape} vs {len(names)}")

    # normalize in float32 before cosine
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    emb = emb / norms

    neighbors = topk_neighbors(emb, names, k=a.k)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps({
        "source": str(a.embedding),
        "meta": {k: v for k, v in meta.items() if k != "names"},
        "k": a.k,
        "count": len(names),
        "names": names,
        "neighbors": neighbors,
    }, indent=1) + "\n")
    print(f"[neighbors] {len(names)} cards x top-{a.k} -> {a.output}")


if __name__ == "__main__":
    main()
