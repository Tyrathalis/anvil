"""Extend an ability table with the keys of a newer AnvilRun -abilities dump (ADR-0110
addendum 09-16: the 16 keys the upstream merge added; ADR-0105 for the table itself).

The base table's rows are copied BYTE-IDENTICAL (every served head was fitted on them);
only the keys the base lacks are embedded, with the same pinned model. A sanity read
re-embeds a sample of base keys and reports the min cosine vs the stored rows (the model
revision check). Output: data/embeddings/<out>.{safetensors,json,-texts.json}, the same
manifest shape as `anvil.encoder abilities` plus a "base" field.

    uv run python scripts/extend_ability_table.py --base data/embeddings/abil-cf2ca6ba-b3s2-qwen3 \
        --dump data/runs/build4-abilities/abilities-8137d0c41c.jsonl --out abil-cf2ca6ba-b4-qwen3
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="the table stem to extend")
    ap.add_argument("--dump", nargs="*", default=[], help="AnvilRun -abilities jsonl file(s)")
    ap.add_argument("--stores", nargs="*", default=[], help="ingested store dirs whose abil side tables to fold in (in-play keys)")
    ap.add_argument("--out", required=True, help="output stem (basename under data/embeddings)")
    ap.add_argument("--model", default="qwen3")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--sample", type=int, default=16, help="base keys re-embedded for the revision check")
    a = ap.parse_args()

    import torch
    from safetensors.torch import load_file, save_file
    from sentence_transformers import SentenceTransformer

    from anvil.encoder.__main__ import EMBED_DIR, MODELS, _load_abilities, fork_commit

    base = str(REPO / a.base) if not Path(a.base).is_absolute() else a.base
    meta = json.loads(Path(base + ".json").read_text())
    texts = json.loads(Path(base + "-texts.json").read_text())
    emb = load_file(base + ".safetensors")["embeddings"]
    assert emb.shape[0] == len(meta["keys"]) == len(texts), "base table inconsistent"
    if meta["model"] != MODELS[a.model]:
        raise SystemExit(f"base model {meta['model']} != {MODELS[a.model]}")

    table = _load_abilities([Path(p) for p in a.dump], [Path(p) for p in a.stores])
    have = set(meta["keys"])
    new_keys = sorted(k for k in table if k not in have)
    print(f"[extend] base {len(have)} keys; dump {len(table)} keys; new {len(new_keys)}")
    for k in new_keys:
        print(f"  + {k} {table[k]['host']} {table[k]['kind']}")

    kwargs = {"torch_dtype": torch.float16} if a.model == "qwen3" else {}
    model = SentenceTransformer(MODELS[a.model], device="cuda", model_kwargs=kwargs)
    revision = getattr(getattr(model[0], "auto_model", None), "config", None)
    revision = getattr(revision, "_commit_hash", None) or "unknown"
    if revision != meta.get("model_revision"):
        raise SystemExit(f"model revision {revision} != base {meta.get('model_revision')}")

    def encode(corpus: list[str]) -> torch.Tensor:
        v = model.encode(corpus, batch_size=a.batch, show_progress_bar=False,
                         convert_to_tensor=True, normalize_embeddings=True)
        return v.to(torch.float16).cpu().contiguous()

    # the revision check: a sample of base keys re-embedded vs the stored rows
    step = max(1, len(meta["keys"]) // a.sample)
    idx = list(range(0, len(meta["keys"]), step))[: a.sample]
    re = encode([texts[meta["keys"][i]] for i in idx]).float()
    cos = torch.nn.functional.cosine_similarity(re, emb[idx].float(), dim=1)
    print(f"[extend] revision check: {len(idx)} base keys re-embedded, cosine min {cos.min():.5f} mean {cos.mean():.5f}")
    if cos.min() < 0.995:
        raise SystemExit("re-embedded base rows drift from the stored table; refusing to extend")

    new_emb = encode([table[k]["txt"] for k in new_keys]) if new_keys else emb[:0]
    out_emb = torch.cat([emb, new_emb], 0).contiguous()
    keys = meta["keys"] + new_keys
    hosts = meta["hosts"] + [table[k]["host"] for k in new_keys]
    kinds = meta["kinds"] + [table[k]["kind"] for k in new_keys]
    all_texts = dict(texts)
    all_texts.update({k: table[k]["txt"] for k in new_keys})
    corpus = [all_texts[k] for k in keys]
    text_hash = hashlib.sha256("\x00".join(corpus).encode()).hexdigest()

    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    stem = EMBED_DIR / a.out
    save_file({"embeddings": out_emb}, str(stem) + ".safetensors")
    manifest = {
        **{k: v for k, v in meta.items() if k not in ("keys", "hosts", "kinds", "sources", "created", "count", "text_sha256", "fork_commit")},
        "fork_commit": fork_commit(),
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "count": out_emb.shape[0],
        "text_sha256": text_hash,
        "base": a.base,
        "base_count": int(emb.shape[0]),
        "sources": list(meta.get("sources", [])) + [str(p) for p in a.dump] + [str(p) for p in a.stores],
        "keys": keys,
        "hosts": hosts,
        "kinds": kinds,
    }
    Path(str(stem) + ".json").write_text(json.dumps(manifest, indent=1) + "\n")
    Path(str(stem) + "-texts.json").write_text(json.dumps(all_texts, indent=1, ensure_ascii=False) + "\n")
    # byte-identity of the base rows in the written file
    chk = load_file(str(stem) + ".safetensors")["embeddings"]
    assert torch.equal(chk[: emb.shape[0]], emb), "base rows not byte-identical after write"
    print(f"[extend] {out_emb.shape[0]} keys x {out_emb.shape[1]}d -> {stem}.safetensors (base rows byte-identical)")


if __name__ == "__main__":
    main()
