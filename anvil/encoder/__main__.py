"""CLI: uv run python -m anvil.encoder texts|embed|abilities ...

  abilities --dump <AnvilRun -abilities jsonl> [--stores <dir>...] [--field all|D]
        # -> data/embeddings/abil-<text sha8>[-D]-<model>.safetensors (+ .json, -texts.json)
        # the ability table (ADR-0105): one row per ability KEY (the fork's
        # canonical-text hash), shared by every consumer of ability text

  texts [--manifest PATH] [--format dc]            # dump {name: embedding text} JSON (debug artifact)
  embed --model qwen3|bge-m3 [--manifest PATH] [--format dc] [--batch 32]
        # -> data/embeddings/<pool_version>-<key>.safetensors (+ .json manifest)

--format selects which pool's CURRENT pin to resolve when --manifest is
omitted (dc, pauper, allcards, ...); ignored if --manifest is given.

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
from pathlib import Path

from anvil.encoder.cardtext import pool_texts
from anvil.pool.forge_db import fork_commit

REPO = Path(__file__).parents[1]
EMBED_DIR = REPO.parent / "data/embeddings"

MODELS = {
    "qwen3": "Qwen/Qwen3-Embedding-4B",
    "bge-m3": "BAAI/bge-m3",
}


def _latest_manifest(format: str = "dc") -> Path:
    # data/pool/<format>/CURRENT pin (2026-08-03 for dc; was newest-mtime)
    from anvil.pool import current_manifest_path

    return current_manifest_path(format)


def _load(manifest_path: Path) -> tuple[dict, dict[str, str]]:
    manifest = json.loads(manifest_path.read_text())
    return manifest, pool_texts(manifest)


def cmd_texts(a) -> None:
    manifest, texts = _load(a.manifest or _latest_manifest(a.format))
    out = EMBED_DIR / f"{manifest['pool_version']}-texts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(texts, indent=1, ensure_ascii=False) + "\n")
    print(f"[encoder] {len(texts)} texts -> {out}")


def cmd_embed(a) -> None:
    import torch
    from safetensors.torch import save_file
    from sentence_transformers import SentenceTransformer

    manifest, texts = _load(a.manifest or _latest_manifest(a.format))
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
    vecs = model.encode(
        corpus,
        batch_size=a.batch,
        show_progress_bar=True,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )
    emb = vecs.to(torch.float16).cpu().contiguous()

    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{manifest['pool_version']}-{a.model}"
    save_file({"embeddings": emb}, EMBED_DIR / f"{stem}.safetensors")
    (EMBED_DIR / f"{stem}.json").write_text(
        json.dumps(
            {
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
            },
            indent=1,
        )
        + "\n"
    )
    print(
        f"[encoder] {emb.shape[0]} cards x {emb.shape[1]}d ({a.model}, rev {revision[:12]}) "
        f"-> {EMBED_DIR / (stem + '.safetensors')}"
    )


def _load_abilities(dumps: list[Path], stores: list[Path]) -> dict[str, dict]:
    """{key: {host, kind, txt}} from AnvilRun -abilities dumps (one JSON per
    ability; miss/err rows skipped) and store side tables (the "abil" lists on
    dec records, sv=3, ADR-0105). Keys are the fork's SHA-256/16-hex of the
    canonical text; the same key from two sources is the same text."""
    out: dict[str, dict] = {}
    miss = err = 0
    for d in dumps:
        for line in open(d, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if "miss" in r:
                miss += 1
                continue
            if "err" in r:
                err += 1
                continue
            out.setdefault(r["h"], {"host": r["host"], "kind": r["kind"], "txt": r["txt"]})
    n_store = 0
    if stores:
        from anvil.store.trajectories import open_store

        for sd in stores:
            st = open_store(str(sd))
            for traj in st:
                for dec in traj.decisions:
                    for r in dec.get("abil") or []:
                        if r["h"] not in out:
                            out[r["h"]] = {"host": r["host"], "kind": r["kind"], "txt": r["txt"]}
                            n_store += 1
    print(f"[encoder] abilities: {len(out)} keys ({miss} pool misses, {err} errors, {n_store} store-only)")
    return out


def cmd_abilities(a) -> None:
    """The ability table (ADR-0105): one row per ability KEY, the pinned LLM
    embedding of the canonical engine text (script parameters + description).
    --field D embeds the description line only (the Oracle-only control for
    the ADR-0049 frozen probe). Output: data/embeddings/abil-<text sha8>[-D]-<model>."""
    import torch
    from safetensors.torch import save_file
    from sentence_transformers import SentenceTransformer

    table = _load_abilities(a.dump, a.stores)
    keys = sorted(table)

    def text_of(k: str) -> str:
        t = table[k]["txt"]
        if a.field == "D":
            d = [ln[2:] for ln in t.split("\n") if ln.startswith("D:")]
            return d[0] if d else t
        return t

    corpus = [text_of(k) for k in keys]
    text_hash = hashlib.sha256("\x00".join(corpus).encode()).hexdigest()
    model_id = MODELS[a.model]
    kwargs = {"torch_dtype": torch.float16} if a.model == "qwen3" else {}
    model = SentenceTransformer(model_id, device="cuda", model_kwargs=kwargs)
    revision = getattr(getattr(model[0], "auto_model", None), "config", None)
    revision = getattr(revision, "_commit_hash", None) or "unknown"
    vecs = model.encode(
        corpus,
        batch_size=a.batch,
        show_progress_bar=True,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )
    emb = vecs.to(torch.float16).cpu().contiguous()
    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"abil-{text_hash[:8]}{'-D' if a.field == 'D' else ''}-{a.model}"
    if a.out:
        stem = a.out
    save_file({"embeddings": emb}, EMBED_DIR / f"{stem}.safetensors")
    (EMBED_DIR / f"{stem}.json").write_text(
        json.dumps(
            {
                "kind": "abilities",
                "field": a.field,
                "fork_commit": fork_commit(),
                "model": model_id,
                "model_revision": revision,
                "created": _dt.datetime.now().isoformat(timespec="seconds"),
                "dim": emb.shape[1],
                "count": emb.shape[0],
                "dtype": "float16",
                "normalized": True,
                "text_sha256": text_hash,
                "sources": [str(p) for p in a.dump] + [str(p) for p in a.stores],
                "keys": keys,
                "hosts": [table[k]["host"] for k in keys],
                "kinds": [table[k]["kind"] for k in keys],
            },
            indent=1,
        )
        + "\n"
    )
    (EMBED_DIR / f"{stem}-texts.json").write_text(
        json.dumps({k: table[k]["txt"] for k in keys}, indent=1, ensure_ascii=False) + "\n"
    )
    print(
        f"[encoder] {emb.shape[0]} abilities x {emb.shape[1]}d ({a.model}, field {a.field}, rev {revision[:12]}) "
        f"-> {EMBED_DIR / (stem + '.safetensors')}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(prog="anvil.encoder")
    sub = ap.add_subparsers(dest="verb", required=True)
    t = sub.add_parser("texts")
    t.add_argument("--manifest", type=Path, default=None)
    t.add_argument(
        "--format",
        default="dc",
        help="pool format if --manifest omitted (dc, pauper, allcards, ...)",
    )
    e = sub.add_parser("embed")
    e.add_argument("--model", choices=sorted(MODELS), required=True)
    e.add_argument("--manifest", type=Path, default=None)
    e.add_argument(
        "--format",
        default="dc",
        help="pool format if --manifest omitted (dc, pauper, allcards, ...)",
    )
    e.add_argument("--batch", type=int, default=32)

    ab = sub.add_parser("abilities", help="the ability table (ADR-0105)")
    ab.add_argument("--model", choices=sorted(MODELS), default="qwen3")
    ab.add_argument("--dump", type=Path, nargs="*", default=[], help="AnvilRun -abilities jsonl file(s)")
    ab.add_argument("--stores", type=Path, nargs="*", default=[], help="store dirs whose abil side tables to add")
    ab.add_argument("--field", choices=("all", "D"), default="all", help="all = canonical text; D = description only")
    ab.add_argument("--batch", type=int, default=16)
    ab.add_argument("--out", default=None, help="output stem override (default abil-<sha8>[-D]-<model>)")

    a = ap.parse_args()
    if a.verb == "texts":
        cmd_texts(a)
    elif a.verb == "abilities":
        cmd_abilities(a)
    else:
        cmd_embed(a)


if __name__ == "__main__":
    main()
