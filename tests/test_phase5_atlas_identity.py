from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from aleph.explore.atlas import Atlas
from aleph.explore.atlas_identity import AtlasIdentity, AtlasIdentityError


def _atlas_files(root: Path) -> None:
    (root / "manifest.json").write_text('{"corpus":"fixture"}\n', encoding="utf-8")
    (root / "chunks.jsonl").write_text(
        json.dumps({"chunk_id": "c1", "work_id": "w1", "title": "t", "text": "x"}) + "\n",
        encoding="utf-8",
    )
    np.save(root / "embeddings.npy", np.ones((1, 2), dtype=np.float32))
    np.save(root / "labels.npy", np.asarray([-1], dtype=np.int64))
    np.save(root / "density.npy", np.asarray([0.0], dtype=np.float32))
    np.save(root / "style.npy", np.zeros((1, 9), dtype=np.float32))
    (root / "atlas_meta.json").write_text('{"clusters":[]}\n', encoding="utf-8")


def _spec() -> dict:
    return {
        "corpus": {"snapshot": "fixture-v1", "licenses_hash": "a" * 64},
        "chunker": {"version": "v1", "schema": "chunks-v1", "settings": {}},
        "embedder": {
            "model_revision": "fixture@1",
            "tokenizer": "fixture",
            "quantization": "none",
            "dimension": 2,
            "normalization": "l2",
        },
        "atlas": {
            "schema_version": 1,
            "pca": {"version": "sklearn", "params": {}, "seed": 0},
            "hdbscan": {"version": "sklearn", "params": {}, "seed": 0},
            "knn": {"version": "sklearn", "params": {}},
        },
        "code": {"version": "fixture-commit"},
    }


def test_identity_is_path_and_time_independent_for_bit_identical_artifacts(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _atlas_files(left)
    _atlas_files(right)

    first = AtlasIdentity.build(left, build_spec=_spec())
    second = AtlasIdentity.build(right, build_spec=_spec())

    assert first.hash == second.hash
    assert first.compare(second).comparable is True
    assert "created" not in first.payload
    assert str(left) not in json.dumps(first.payload)


def test_one_byte_artifact_change_breaks_identity_and_verification(tmp_path):
    _atlas_files(tmp_path)
    identity = AtlasIdentity.build(tmp_path, build_spec=_spec())
    (tmp_path / "atlas_meta.json").write_text('{"clusters":[1]}\n', encoding="utf-8")

    with pytest.raises(AtlasIdentityError, match="hash mismatch"):
        identity.verify(tmp_path)

    rebuilt = AtlasIdentity.build(tmp_path, build_spec=_spec())
    assert identity.compare(rebuilt).comparable is False


def test_atlas_load_fails_closed_when_full_identity_is_corrupt(tmp_path):
    _atlas_files(tmp_path)
    AtlasIdentity.build(tmp_path, build_spec=_spec())
    embeddings = np.load(tmp_path / "embeddings.npy")
    embeddings[0, 0] = 9.0
    np.save(tmp_path / "embeddings.npy", embeddings)

    with pytest.raises(AtlasIdentityError, match="embeddings.npy"):
        Atlas.load(tmp_path)


def test_legacy_atlas_without_full_identity_still_loads_as_unidentified(tmp_path):
    _atlas_files(tmp_path)

    atlas = Atlas.load(tmp_path)

    assert atlas.identity is None


def test_build_spec_rejects_missing_or_unstable_identity_fields(tmp_path):
    _atlas_files(tmp_path)
    incomplete = _spec()
    del incomplete["embedder"]
    with pytest.raises(AtlasIdentityError, match="embedder"):
        AtlasIdentity.build(tmp_path, build_spec=incomplete)

    unstable = _spec() | {"timestamp": "now"}
    with pytest.raises(AtlasIdentityError, match="unstable field"):
        AtlasIdentity.build(tmp_path, build_spec=unstable)

    nested_unstable = _spec()
    nested_unstable["corpus"]["source"] = {"absolute_path": "/private/corpus"}
    with pytest.raises(AtlasIdentityError, match="unstable field"):
        AtlasIdentity.build(tmp_path, build_spec=nested_unstable)

    with pytest.raises(AtlasIdentityError, match="artifact name"):
        AtlasIdentity.build(tmp_path, build_spec=_spec(), artifact_names=("../secret",))
