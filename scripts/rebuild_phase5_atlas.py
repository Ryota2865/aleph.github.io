#!/usr/bin/env python3
"""Rebuild the Phase 5C Atlas locally and issue its first full identity.

The source Atlas is read-only.  This command copies only the frozen plain-index
inputs into a new directory, rebuilds PCA/HDBSCAN/kNN/style artifacts, and writes
identity.json last as the completion marker.  It performs no provider calls.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np

from aleph.explore.atlas import Atlas, build_atlas
from aleph.explore.atlas_identity import AtlasIdentity


INDEX_INPUTS = ("manifest.json", "chunks.jsonl", "embeddings.npy")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _logical_ref(path: Path, repository_root: Path, fallback: str) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return fallback


def build_spec(
    *,
    repository_root: Path,
    source_index: Path,
    corpus_source: Path,
    license_manifest: Path,
    embedder_artifact: Path,
    code_version: str,
    knn_k: int = 16,
    pca_dims: int = 64,
    min_cluster_size: int = 40,
    pca_random_state: int = 42,
) -> dict[str, Any]:
    repository_root = Path(repository_root)
    source_index = Path(source_index)
    manifest = json.loads((source_index / "manifest.json").read_text(encoding="utf-8"))
    dimension = int(manifest["dim"])
    source_index_hashes = {name: _sha256(source_index / name) for name in INDEX_INPUTS}
    return {
        "corpus": {
            "snapshot": "aozora-16950-phase5c-v1",
            "source_ref": _logical_ref(corpus_source, repository_root, "external:aozora/works.jsonl"),
            "source_sha256": _sha256(corpus_source),
            "license_manifest_ref": _logical_ref(
                license_manifest, repository_root, "external:corpus-license-manifest"
            ),
            "licenses_hash": _sha256(license_manifest),
            "index_input_hashes": source_index_hashes,
            "n_works": int(manifest["n_works"]),
            "n_chunks": int(manifest["n_chunks"]),
        },
        "chunker": {
            "version": "aleph.explore.corpus.chunk_text@v1",
            "schema": "chunks-jsonl-v1",
            "settings": {"target_chars": 2000, "max_chunks_per_work": 30},
        },
        "embedder": {
            "model_revision": "bge-m3-local-gguf-by-content",
            "tokenizer": "embedded-in-gguf",
            "quantization": "f16",
            "dimension": dimension,
            "normalization": "provider-output; no post-normalization",
            "artifact_sha256": _sha256(embedder_artifact),
        },
        "atlas": {
            "schema_version": 1,
            "pca": {
                "implementation": "sklearn.decomposition.PCA",
                "version": version("scikit-learn"),
                "params": {"n_components": pca_dims, "random_state": pca_random_state},
            },
            "hdbscan": {
                "implementation": "sklearn.cluster.HDBSCAN",
                "version": version("scikit-learn"),
                "params": {"min_cluster_size": min_cluster_size, "cluster_selection_method": "eom"},
            },
            "knn": {
                "implementation": "sklearn.neighbors.NearestNeighbors",
                "version": version("scikit-learn"),
                "params": {"n_neighbors": knn_k, "metric": "euclidean-on-pca"},
            },
            "style_features": "aleph.explore.atlas.STYLE_FEATURES@v1",
            "numpy_version": np.__version__,
        },
        "code": {
            "version": code_version,
            "atlas_py_sha256": _sha256(repository_root / "aleph/explore/atlas.py"),
            "atlas_identity_py_sha256": _sha256(
                repository_root / "aleph/explore/atlas_identity.py"
            ),
        },
    }


def rebuild_atlas(
    *,
    source_index: Path,
    output_dir: Path,
    build_spec_payload: dict[str, Any],
    knn_k: int = 16,
    pca_dims: int = 64,
    min_cluster_size: int = 40,
    pca_random_state: int = 42,
) -> AtlasIdentity:
    atlas_spec = build_spec_payload.get("atlas", {})
    expected = {
        "knn_k": atlas_spec.get("knn", {}).get("params", {}).get("n_neighbors"),
        "pca_dims": atlas_spec.get("pca", {}).get("params", {}).get("n_components"),
        "min_cluster_size": atlas_spec.get("hdbscan", {})
        .get("params", {})
        .get("min_cluster_size"),
        "pca_random_state": atlas_spec.get("pca", {}).get("params", {}).get("random_state"),
    }
    actual = {
        "knn_k": knn_k,
        "pca_dims": pca_dims,
        "min_cluster_size": min_cluster_size,
        "pca_random_state": pca_random_state,
    }
    mismatches = [name for name in actual if expected.get(name) != actual[name]]
    if mismatches:
        raise ValueError(
            "Atlas build arguments do not match build_spec: " + ", ".join(sorted(mismatches))
        )
    source_index = Path(source_index).resolve()
    output_dir = Path(output_dir).resolve()
    if source_index == output_dir:
        raise ValueError("source and output Atlas directories must be different")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite Atlas directory: {output_dir}")
    staging = output_dir.parent / f".{output_dir.name}.building"
    if staging.exists():
        raise FileExistsError(f"staging directory already exists: {staging}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    for name in INDEX_INPUTS:
        source = source_index / name
        if not source.is_file():
            raise FileNotFoundError(f"source Atlas input is missing: {name}")
        shutil.copyfile(source, staging / name)

    build_atlas(
        staging,
        knn_k=knn_k,
        pca_dims=pca_dims,
        min_cluster_size=min_cluster_size,
        pca_random_state=pca_random_state,
    )
    identity = AtlasIdentity.build(staging, build_spec=build_spec_payload)
    identity.verify(staging)
    Atlas.load(staging)
    staging.replace(output_dir)
    loaded = AtlasIdentity.load(output_dir)
    loaded.verify(output_dir)
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", type=Path, default=Path("state/atlas"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("state/atlases/phase5c-pca64-hdbscan40-aozora-v1"),
    )
    parser.add_argument("--corpus", type=Path, default=Path("corpus/aozora/works.jsonl"))
    parser.add_argument("--license-manifest", type=Path, default=Path("corpus/README.md"))
    parser.add_argument(
        "--embedder-artifact",
        type=Path,
        default=Path("/home/ryota_tanaka/models/embeddings/bge-m3/bge-m3-f16.gguf"),
    )
    parser.add_argument("--code-version", default="phase5c-step10-v1")
    args = parser.parse_args()

    root = args.root.resolve()
    source = args.source if args.source.is_absolute() else root / args.source
    output = args.output if args.output.is_absolute() else root / args.output
    corpus = args.corpus if args.corpus.is_absolute() else root / args.corpus
    license_manifest = (
        args.license_manifest
        if args.license_manifest.is_absolute()
        else root / args.license_manifest
    )
    spec = build_spec(
        repository_root=root,
        source_index=source,
        corpus_source=corpus,
        license_manifest=license_manifest,
        embedder_artifact=args.embedder_artifact,
        code_version=args.code_version,
    )
    identity = rebuild_atlas(
        source_index=source,
        output_dir=output,
        build_spec_payload=spec,
    )
    print(json.dumps({"atlas_dir": str(output), "identity": identity.hash}, sort_keys=True))


if __name__ == "__main__":
    main()
