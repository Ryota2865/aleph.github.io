from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from aleph.explore.atlas import Atlas
from scripts.rebuild_phase5_atlas import build_spec, rebuild_atlas


ROOT = Path(__file__).resolve().parents[1]


def _source_index(root: Path) -> Path:
    source = root / "legacy"
    source.mkdir()
    chunks = [
        {"chunk_id": f"c{i}", "work_id": f"w{i}", "title": f"t{i}", "text": "本文" * (i + 1)}
        for i in range(12)
    ]
    (source / "manifest.json").write_text(
        json.dumps({"n_works": 12, "n_chunks": 12, "dim": 4}) + "\n",
        encoding="utf-8",
    )
    (source / "chunks.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in chunks),
        encoding="utf-8",
    )
    vectors = np.arange(48, dtype=np.float32).reshape(12, 4)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    np.save(source / "embeddings.npy", vectors)
    return source


def _provenance(root: Path) -> tuple[Path, Path, Path]:
    corpus = root / "works.jsonl"
    corpus.write_text('{"id":"fixture"}\n', encoding="utf-8")
    license_manifest = root / "CORPUS.md"
    license_manifest.write_text("public domain fixture\n", encoding="utf-8")
    embedder = root / "embedder.gguf"
    embedder.write_bytes(b"fixture embedder")
    return corpus, license_manifest, embedder


def test_rebuild_uses_new_directory_and_emits_verified_full_identity_last(tmp_path):
    source = _source_index(tmp_path)
    corpus, license_manifest, embedder = _provenance(tmp_path)
    output = tmp_path / "new-atlas"
    spec = build_spec(
        repository_root=ROOT,
        source_index=source,
        corpus_source=corpus,
        license_manifest=license_manifest,
        embedder_artifact=embedder,
        code_version="test-v1",
        knn_k=3,
        pca_dims=3,
        min_cluster_size=3,
    )

    identity = rebuild_atlas(
        source_index=source,
        output_dir=output,
        build_spec_payload=spec,
        knn_k=3,
        pca_dims=3,
        min_cluster_size=3,
        pca_random_state=42,
    )

    assert output.is_dir()
    assert (output / "identity.json").is_file()
    assert not (output.parent / f".{output.name}.building").exists()
    assert identity.verify(output)
    loaded = Atlas.load(output)
    assert loaded.identity and loaded.identity.hash == identity.hash
    assert spec["corpus"]["source_sha256"] == sha256(corpus.read_bytes()).hexdigest()
    assert spec["embedder"]["artifact_sha256"] == sha256(embedder.read_bytes()).hexdigest()
    assert spec["atlas"]["pca"]["params"]["random_state"] == 42


def test_rebuild_refuses_overwrite_source_or_existing_destination(tmp_path):
    source = _source_index(tmp_path)
    corpus, license_manifest, embedder = _provenance(tmp_path)
    spec = build_spec(
        repository_root=ROOT,
        source_index=source,
        corpus_source=corpus,
        license_manifest=license_manifest,
        embedder_artifact=embedder,
        code_version="test-v1",
    )

    with pytest.raises(ValueError, match="different"):
        rebuild_atlas(source_index=source, output_dir=source, build_spec_payload=spec)

    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        rebuild_atlas(source_index=source, output_dir=output, build_spec_payload=spec)

    with pytest.raises(ValueError, match="do not match build_spec"):
        rebuild_atlas(
            source_index=source,
            output_dir=tmp_path / "mismatch",
            build_spec_payload=spec,
            pca_dims=3,
        )


def test_build_spec_contains_no_absolute_paths_or_timestamps(tmp_path):
    source = _source_index(tmp_path)
    corpus, license_manifest, embedder = _provenance(tmp_path)
    spec = build_spec(
        repository_root=ROOT,
        source_index=source,
        corpus_source=corpus,
        license_manifest=license_manifest,
        embedder_artifact=embedder,
        code_version="test-v1",
    )
    encoded = json.dumps(spec, sort_keys=True)

    assert str(tmp_path) not in encoded
    assert "timestamp" not in encoded
    assert "created" not in encoded
