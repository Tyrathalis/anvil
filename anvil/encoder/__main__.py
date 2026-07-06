"""CLI: uv run python -m anvil.encoder texts|embed ...

  texts [--manifest PATH]            # dump {name: embedding text} JSON (debug artifact)
  embed --model qwen3|bge-m3 [--manifest PATH] [--batch 32]
        # -> data/embeddings/<pool_version>-<key>.safetensors (+ .json manifest)

The cache is fp16, keyed by canonical pool name, pinned to (pool_version,
fork_commit, HF model revision, text content hash) — ADR-0004's "exact HF
revision in the run manifest". Rebuildable in minutes; never regenerated
implicitly (a changed pin is a new file).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

from anvil.encoder.cardtext import pool_texts
from anvil.pool.forge_db import fork_commit

REPO = Path(__file__).parents[1]
EMBED_DIR = REPO.parent / "data/embeddings"

MODELS = {
    "qwen3": "Qwen/Qwen3-Embedding-4B",
    "bge-m3": "BAAI/bge-m3",
}


def _latest_manifest() -> Path:
    pool_dir = REPO.parent / "data/pool"
    manifests = sorted(pool_dir.glob("pool-*.json"), key=lambda p: p.stat().st_mtime)
    if not manifests:
        sys.exit("no pool manifest — run `python -m anvil.pool build` first")
    return manifests[-1]


def _load(manifest_path: Path) -> tuple[dict, dict[str, str]]:
    manifest = json.loads(manifest_path.read_text())
    return manifest, pool_texts(manifest)


def cmd_texts(a) -> None:
    manifest, texts = _load(a.manifest or _latest_manifest())
    out = EMBED_DIR / f"{manifest['pool_version']}-texts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(texts, indent=1, ensure_ascii=False) + "\n")
    print(f"[encoder] {len(texts)} texts -> {out}")


def cmd_embed(a) -> None:
    import torch
    from safetensors.torch import save_file
    from sentence_transformers import SentenceTransformer

    manifest, texts = _load(a.manifest or _latest_manifest())
    names = sorted(texts)
    corpus = [texts[n] for n in names]
    text_hash = hashlib.sha256("\x00".join(corpus).encode()).hexdigest()

    model_id = MODELS[a.model]
    kwargs = {"torch_dtype": torch.float16} if a.model == "qwen3" else {}
    model = SentenceTransformer(model_id, device="cuda", model_kwargs=kwargs)
    revision = getattr(getattr(model[0], "auto_model", None), "config", None)
    revision = getattr(revision, "_commit_hash", None) or "unknown"
    # Cards are documents: no instruction prefix (Qwen3-Embedding applies
    # instructions on the query side; symmetric use here).
    vecs = model.encode(corpus, batch_size=a.batch, show_progress_bar=True,
                        convert_to_tensor=True, normalize_embeddings=True)
    emb = vecs.to(torch.float16).cpu().contiguous()

    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{manifest['pool_version']}-{a.model}"
    save_file({"embeddings": emb}, EMBED_DIR / f"{stem}.safetensors")
    (EMBED_DIR / f"{stem}.json").write_text(json.dumps({
        "pool_version": manifest["pool_version"],
        "fork_commit": fork_commit(),
        "model": model_id,
        "model_revision": revision,
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "dim": emb.shape[1],
        "count": emb.shape[0],
        "dtype": "float16",
        "normalized": True,
        "text_sha256": text_hash,
        "names": names,
    }, indent=1) + "\n")
    print(f"[encoder] {emb.shape[0]} cards x {emb.shape[1]}d ({a.model}, rev {revision[:12]}) "
          f"-> {EMBED_DIR / (stem + '.safetensors')}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="anvil.encoder")
    sub = ap.add_subparsers(dest="verb", required=True)
    t = sub.add_parser("texts")
    t.add_argument("--manifest", type=Path, default=None)
    e = sub.add_parser("embed")
    e.add_argument("--model", choices=sorted(MODELS), required=True)
    e.add_argument("--manifest", type=Path, default=None)
    e.add_argument("--batch", type=int, default=32)
    a = ap.parse_args()
    if a.verb == "texts":
        cmd_texts(a)
    else:
        cmd_embed(a)


if __name__ == "__main__":
    main()
