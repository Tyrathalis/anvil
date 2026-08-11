# pyright: basic
"""Structural checks that Featurizer.example and collate match the typed
Example/Batch contracts defined in anvil.schemas.tensors."""

import torch

from anvil.bridge.featurize import Featurizer
from anvil.schemas.tensors import Batch, Example
from anvil.training.dataset import collate


def _priority_dec():
    return {
        "p": 0,
        "m": "chooseSpellAbilityToPlay",
        "obs": {
            "ents": [
                {"e": 1, "n": "Sol Ring", "z": "hand", "c": 0, "p": 0},
                {"e": 2, "n": "Mountain", "z": "battlefield", "c": 0, "p": 0},
            ],
            "glob": {"turn": 1, "ph": "MAIN1", "ap": 0},
            "players": [{"life": 40, "hand": 7, "lib": 92}, {"life": 40, "hand": 7, "lib": 92}],
        },
        "opts": [
            {"e": 1, "sa": "Sol Ring - cast", "kind": "spell"},
            {"e": 2, "sa": "Mountain - tap for R", "kind": "land"},
        ],
        "ret": None,
    }


def _header():
    return {
        "g": 0,
        "seed": 1,
        "fmt": "Commander",
        "sv": 1,
        "players": [{"name": "P0", "deck": "D0"}, {"name": "P1", "deck": "D1"}],
    }


def _minimal_embed(tmp_path):
    stem = tmp_path / "embed"
    import json

    from safetensors.torch import save_file

    names = ["Sol Ring", "Mountain"]
    meta = {"names": names, "dim": 8}
    (stem.parent).mkdir(parents=True, exist_ok=True)
    save_file(
        {"embeddings": torch.zeros((len(names), meta["dim"]), dtype=torch.float16)},
        str(stem) + ".safetensors",
    )
    stem.with_suffix(".json").write_text(json.dumps(meta))
    return str(stem)


def test_example_matches_typeddict(tmp_path):
    embed = _minimal_embed(tmp_path)
    feat = Featurizer(embed, methods=["chooseSpellAbilityToPlay"])
    ex, _aux = feat.example(_priority_dec(), _header(), "priority")
    assert isinstance(ex, dict)
    for key in Example.__required_keys__:
        assert key in ex, f"missing Example key: {key}"
        assert isinstance(ex[key], torch.Tensor), f"Example[{key}] is not a Tensor"


def test_collate_matches_batch(tmp_path):
    embed = _minimal_embed(tmp_path)
    feat = Featurizer(embed, methods=["chooseSpellAbilityToPlay"])
    ex, _aux = feat.example(_priority_dec(), _header(), "priority")
    batch = collate([ex, ex])
    for key in Batch.__required_keys__:
        assert key in batch, f"missing Batch key: {key}"
        assert isinstance(batch[key], torch.Tensor), f"Batch[{key}] is not a Tensor"
    assert batch["entities"].shape[0] == 2
    assert batch["cand_rows"].shape[0] == 2
