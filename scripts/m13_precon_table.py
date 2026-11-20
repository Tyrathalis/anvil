"""Give a checkpoint a card table that covers cards outside its pool (M13 Build 0 step 5, ADR-0130).

A checkpoint carries its card table: the frozen text rows, the structured features and a learned id
row per pool card (anvil/encoder/cards.py). A card outside the table is served as "no card", the row
hidden cards and tokens use. This script writes the pieces of the held-out read's second arm:

  * an embedding table whose first rows are the base table's, byte-identical and in the base order,
    followed by the new cards' text rows from the same pinned model;
  * a manifest naming every card, for build_net;
  * a copy of the checkpoint whose card buffers are extended to match. Base rows keep the
    checkpoint's own text, features and id rows. A new card gets its text and features and, for its
    id row, either the no-card id (--new-id null) or the mean of the trained id rows (--new-id mean).
    No weight is trained or changed.

    uv run python scripts/m13_precon_table.py --ckpt data/training/big-run/iter-405/train/last.pt \
        --names data/runs/m13-precon/precon-names.txt --tag precon --out-dir data/runs/m13-precon
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def key(name: str) -> str:
    """The name a card's script is indexed by: the first face of a split card."""
    return name.split(" // ")[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--names", required=True, help="one card name per line; names already in the table are skipped")
    ap.add_argument("--tag", default="precon")
    ap.add_argument("--out-dir", required=True, help="where the manifest and the checkpoint copies go")
    ap.add_argument("--batch", type=int, default=32)
    a = ap.parse_args()

    import numpy as np
    import torch
    from safetensors.torch import load_file, save_file

    from anvil.encoder.cardtext import _scan_files, normalize, pool_features, pool_texts

    ckpt = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    base_stem = cfg["embed"]
    base_meta = json.loads(Path(f"{base_stem}.json").read_text())
    base_vecs = load_file(f"{base_stem}.safetensors")["embeddings"]
    base_names = base_meta["names"]
    have = set(base_names)
    files = _scan_files()
    # a deck file marks a foil with a trailing "+"; a split card is "A // B" and its script is found by "A".
    # Both spellings of a split card get a row (the same text), since either may reach the featurizer.
    asked = set()
    for x in open(a.names):
        x = x.strip().rstrip("+")
        if x:
            asked |= {x, key(x)}
    new = sorted({n for n in asked if n not in have and normalize(key(n)) in files})
    no_script = sorted({n for n in asked if n not in have and normalize(key(n)) not in files})
    print(f"[table] base {len(base_names)} cards; asked {len(asked)}; new {len(new)}; no card script {len(no_script)} {no_script[:8]}")

    version = f"{a.tag}-{hashlib.sha256(chr(0).join(base_names + new).encode()).hexdigest()[:8]}"
    stem = REPO / "data" / "embeddings" / f"{version}-qwen3"
    names = base_names + new
    if not Path(f"{stem}.safetensors").exists():
        from sentence_transformers import SentenceTransformer

        from anvil.torch.utils import get_torch_device

        by_key = pool_texts({"pool": {key(n): {} for n in new}})
        texts = {n: by_key[key(n)] for n in new}
        model = SentenceTransformer(base_meta["model"], device=get_torch_device(), model_kwargs={"torch_dtype": torch.float16})
        # the revision check: a sample of base cards re-embedded must match the stored rows
        sample = base_names[:: max(1, len(base_names) // 16)][:16]
        again = model.encode([pool_texts({"pool": {n: {} for n in sample}})[n] for n in sample], batch_size=a.batch,
                             convert_to_tensor=True, normalize_embeddings=True).float().cpu()
        stored = torch.stack([base_vecs[base_names.index(n)] for n in sample]).float()
        cos = torch.nn.functional.cosine_similarity(again, stored, dim=-1)
        print(f"[table] revision check on {len(sample)} base cards: min cosine {cos.min():.4f} (the card scripts may have changed since the base table)")
        vecs = model.encode([texts[n] for n in new], batch_size=a.batch, show_progress_bar=True,
                            convert_to_tensor=True, normalize_embeddings=True)
        emb = torch.cat([base_vecs, vecs.to(base_vecs.dtype).cpu()]).contiguous()
        save_file({"embeddings": emb}, f"{stem}.safetensors")
        Path(f"{stem}.json").write_text(json.dumps({
            "pool_version": version, "base": str(base_stem), "model": base_meta["model"],
            "model_revision": base_meta.get("model_revision"), "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "dim": emb.shape[1], "count": emb.shape[0], "dtype": str(emb.dtype).split(".")[-1], "normalized": True,
            "base_count": len(base_names), "min_cosine_revision_check": float(cos.min()), "names": names,
        }, indent=1) + "\n")
        del model
    emb = load_file(f"{stem}.safetensors")["embeddings"]
    assert emb.shape[0] == len(names) and torch.equal(emb[: len(base_names)], base_vecs)

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / f"pool-{version}.json"
    manifest.write_text(json.dumps({"pool_version": version, "pool": {n: {} for n in names}}) + "\n")

    sd = ckpt["model"]
    n = len(base_names)
    assert sd["cards.text"].shape[0] == n and sd["cards.id_emb.weight"].shape[0] == n + 1
    new_feats = torch.from_numpy(pool_features({}, [key(n) for n in new]))
    fresh_base = torch.from_numpy(pool_features({}, base_names))
    drift = int((fresh_base - sd["cards.feats"]).abs().sum(dim=1).gt(1e-6).sum())
    print(f"[table] base feature rows that differ from today's card scripts: {drift} of {n} (the checkpoint's rows are kept)")
    ids = sd["cards.id_emb.weight"]
    for mode in ("null", "mean"):
        new_id = ids[n] if mode == "null" else ids[:n].mean(dim=0)
        m = dict(sd)
        m["cards.text"] = torch.cat([sd["cards.text"], emb[n:].float()])
        m["cards.feats"] = torch.cat([sd["cards.feats"], new_feats.float()])
        m["cards.id_emb.weight"] = torch.cat([ids[:n], new_id.expand(len(new), -1), ids[n:]])
        c = dict(ckpt, model=m, config=dict(cfg, embed=str(stem), pool_manifest=str(manifest.resolve()),
                                             card_table_base=str(a.ckpt), card_table_new_id=mode))
        dst = out / f"ckpt-{version}-id{mode}.pt"
        torch.save(c, dst)
        print(f"[table] {dst}: {len(names)} cards, new-card id = {mode}")
    np.savetxt(out / f"{version}-new-names.txt", new, fmt="%s")


if __name__ == "__main__":
    main()
