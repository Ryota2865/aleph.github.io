"""L2 潜在空間地図（PLAN §4.2）— 密度、クラスタ、文体素性を構築する."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

from aleph.explore.atlas_identity import AtlasIdentity


STYLE_FEATURES: list[str] = [
    "mean_sentence_len",
    "std_sentence_len",
    "type_token_ratio",
    "kanji_ratio",
    "hiragana_ratio",
    "katakana_ratio",
    "punctuation_density",
    "dialogue_ratio",
    "exclaim_question_rate",
]


def style_vector(text: str) -> np.ndarray:
    """統計的な文体素性を ``STYLE_FEATURES`` の順で返す."""
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[。！？.!?]+", text)
        if sentence.strip()
    ]
    sentence_lengths = np.asarray([len(sentence) for sentence in sentences], dtype=np.float32)
    mean_sentence_len = float(sentence_lengths.mean()) if sentence_lengths.size else 0.0
    std_sentence_len = float(sentence_lengths.std()) if sentence_lengths.size else 0.0

    characters = [char for char in text if not char.isspace()]
    total = len(characters)
    lexical = [char for char in characters if char.isalnum() or "\u3040" <= char <= "\u30ff"]
    type_token_ratio = len(set(lexical)) / len(lexical) if lexical else 0.0

    def ratio(pattern: str) -> float:
        return len(re.findall(pattern, text)) / total if total else 0.0

    dialogue_chars = sum(len(match) for match in re.findall(r"「(.*?)」", text, flags=re.DOTALL))
    values = [
        mean_sentence_len,
        std_sentence_len,
        type_token_ratio,
        ratio(r"[\u3400-\u4dbf\u4e00-\u9fff]"),
        ratio(r"[\u3040-\u309f]"),
        ratio(r"[\u30a0-\u30ff]"),
        ratio(r"[、。！？,.!?「」『』…—]"),
        dialogue_chars / total if total else 0.0,
        ratio(r"[！？!?]"),
    ]
    return np.asarray(values, dtype=np.float32)


def _load_chunks(index_dir: Path) -> list[dict]:
    with open(index_dir / "chunks.jsonl", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


@dataclass
class Atlas:
    """保存済みアトラスと索引メタデータへの軽量な窓口."""

    index_dir: Path
    labels: np.ndarray
    density: np.ndarray
    style: np.ndarray
    chunks: list[dict]
    meta: dict
    identity: AtlasIdentity | None = None

    @property
    def n_clusters(self) -> int:
        return len({int(label) for label in self.labels if int(label) != -1})

    @property
    def cluster_meta(self) -> list[dict]:
        return list(self.meta.get("clusters", []))

    def _nearest_clusters(self, indices: np.ndarray) -> list[int]:
        result: list[int] = []
        embeddings: np.ndarray | None = None
        centroids: dict[int, np.ndarray] = {}
        for index in indices:
            label = int(self.labels[index])
            if label != -1:
                result.append(label)
                continue
            if embeddings is None:
                embeddings = np.load(self.index_dir / "embeddings.npy", mmap_mode="r")
                for cluster in sorted({int(value) for value in self.labels if int(value) != -1}):
                    centroids[cluster] = np.asarray(
                        embeddings[self.labels == cluster].mean(axis=0),
                        dtype=np.float32,
                    )
            if not centroids:
                result.append(-1)
                continue
            nearest = min(
                centroids,
                key=lambda cluster: float(np.linalg.norm(embeddings[index] - centroids[cluster])),
            )
            result.append(nearest)
        return result

    def sparse_regions(self, top_n: int) -> list[dict]:
        """kNN平均距離が大きい順に、疎なチャンクを返す."""
        count = min(max(0, top_n), len(self.chunks))
        indices = np.argsort(self.density, kind="stable")[::-1][:count]
        nearest_clusters = self._nearest_clusters(indices)
        return [
            {
                "chunk_id": self.chunks[int(index)]["chunk_id"],
                "work_id": self.chunks[int(index)]["work_id"],
                "title": self.chunks[int(index)]["title"],
                "knn_dist": float(self.density[int(index)]),
                "nearest_cluster": nearest_cluster,
            }
            for index, nearest_cluster in zip(indices, nearest_clusters, strict=True)
        ]

    @classmethod
    def load(cls, directory: str | Path) -> "Atlas":
        directory = Path(directory)
        identity_path = directory / "identity.json"
        identity = AtlasIdentity.load(directory) if identity_path.exists() else None
        if identity is not None:
            identity.verify(directory)
        return cls(
            index_dir=directory,
            labels=np.load(directory / "labels.npy"),
            density=np.load(directory / "density.npy"),
            style=np.load(directory / "style.npy"),
            chunks=_load_chunks(directory),
            meta=json.loads((directory / "atlas_meta.json").read_text(encoding="utf-8")),
            identity=identity,
        )


def build_atlas(
    index_dir: str | Path,
    *,
    knn_k: int = 16,
    pca_dims: int = 64,
    min_cluster_size: int = 40,
    pca_random_state: int = 42,
) -> Atlas:
    """プレーン索引をPCAで縮約し、HDBSCANとkNN密度を保存する."""
    index_dir = Path(index_dir)
    embeddings = np.load(index_dir / "embeddings.npy", mmap_mode="r")
    chunks = _load_chunks(index_dir)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(chunks):
        raise ValueError("embeddings.npy and chunks.jsonl are not aligned")
    n_samples, dim = embeddings.shape
    if n_samples == 0:
        raise ValueError("cannot build an atlas from an empty index")
    if knn_k <= 0 or pca_dims <= 0 or min_cluster_size < 2:
        raise ValueError("knn_k and pca_dims must be positive; min_cluster_size must be at least 2")

    reduced_dims = min(pca_dims, dim, n_samples)
    reduced = PCA(
        n_components=reduced_dims,
        random_state=pca_random_state,
    ).fit_transform(np.asarray(embeddings))
    if n_samples < min_cluster_size:
        labels = np.full(n_samples, -1, dtype=np.int64)
    else:
        labels = HDBSCAN(min_cluster_size=min_cluster_size, copy=True).fit_predict(reduced).astype(
            np.int64
        )

    neighbor_count = min(knn_k + 1, n_samples)
    distances, _ = NearestNeighbors(n_neighbors=neighbor_count).fit(reduced).kneighbors(reduced)
    density = (
        distances[:, 1:].mean(axis=1).astype(np.float32)
        if neighbor_count > 1
        else np.zeros(n_samples, dtype=np.float32)
    )
    style = np.vstack([style_vector(chunk.get("text", "")) for chunk in chunks]).astype(
        np.float32,
        copy=False,
    )

    clusters: list[dict] = []
    for label in sorted({int(value) for value in labels if int(value) != -1}):
        indices = np.flatnonzero(labels == label)
        centroid = reduced[indices].mean(axis=0)
        order = indices[np.argsort(np.linalg.norm(reduced[indices] - centroid, axis=1))[:3]]
        clusters.append(
            {
                "label": label,
                "size": int(indices.size),
                "exemplars": [chunks[int(index)]["chunk_id"] for index in order],
                "mean_density": float(density[indices].mean()),
            }
        )
    meta = {
        "created": datetime.now(timezone.utc).isoformat(),
        "pca_dims": reduced_dims,
        "knn_k": min(knn_k, max(0, n_samples - 1)),
        "min_cluster_size": min_cluster_size,
        "pca_random_state": pca_random_state,
        "clusters": clusters,
    }

    np.save(index_dir / "labels.npy", labels)
    np.save(index_dir / "density.npy", density)
    np.save(index_dir / "style.npy", style)
    (index_dir / "atlas_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return Atlas(index_dir, labels, density, style, chunks, meta)


_CLUSTER_ANNOTATION_PROMPT_VERSION = "v1"
_CLUSTER_ANNOTATION_AXES = ("theme", "form", "viewpoint", "era")


def annotate_clusters(
    atlas: "Atlas",
    scout,
    *,
    annotator_model: str,
    prompt_version: str = _CLUSTER_ANNOTATION_PROMPT_VERSION,
    max_exemplar_chars: int = 1500,
) -> list[dict]:
    """クラスタ代表例に属性ラベル（theme/form/viewpoint/era）を付け、注釈の出所つきで
    永続化する（PLAN_CHANGELOG 0.7.18 問4・designs/corpus-expansion.md C-1）.

    従来はaleph/explore/niche.py::_cell_candidatesが `aleph explore` の実行毎に
    scoutへ再ラベリングを依頼し、結果を一切保存していなかった（sol §4.1指摘）。
    本関数はその同じラベリングを一度だけ行い、`atlas_dir/cluster_annotations.json`へ
    「単一注釈器による分類である」ことが読み取れる形（annotator_model・prompt_version・
    confidence・ts）で保存する。過剰設計を避けるため、複数注釈器の合議は行わない
    （Q4決定: 単一注釈の品質を実監査してから要否判断）。
    """
    from aleph.core.model_output import parse_model_output

    chunk_by_id = {chunk.get("chunk_id"): chunk for chunk in atlas.chunks}
    annotations: list[dict] = []
    for cluster in atlas.cluster_meta:
        exemplars = cluster.get("exemplars", [])
        excerpts = [chunk_by_id.get(cid, {}).get("text", "")[:max_exemplar_chars] for cid in exemplars]
        response = scout(
            "クラスタ代表例を主題・形式・視点・時代で属性ラベリングしてください。"
            "併せて、この分類にどれだけ自信があるかを0.0〜1.0のconfidenceとして"
            "自己申告してください。"
            'JSON {"theme":"...","form":"...","viewpoint":"...","era":"...",'
            '"confidence":0.0} だけを返してください。\n'
            + "\n---\n".join(excerpts)
        )
        parsed = parse_model_output(response, schema=dict).value or {}
        record = {
            "label": cluster.get("label"),
            "size": cluster.get("size"),
            "annotator_model": annotator_model,
            "prompt_version": prompt_version,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if parsed and all(parsed.get(axis) for axis in _CLUSTER_ANNOTATION_AXES):
            record["attributes"] = {axis: str(parsed[axis]) for axis in _CLUSTER_ANNOTATION_AXES}
            try:
                record["confidence"] = float(parsed.get("confidence"))
            except (TypeError, ValueError):
                record["confidence"] = None
        else:
            record["attributes"] = None
            record["confidence"] = None
        annotations.append(record)

    payload = {
        "prompt_version": prompt_version,
        "annotator_model": annotator_model,
        "created": datetime.now(timezone.utc).isoformat(),
        "annotations": annotations,
    }
    (atlas.index_dir / "cluster_annotations.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return annotations


def load_cluster_annotations(atlas_dir: str | Path) -> list[dict]:
    """永続化済みのクラスタ属性注釈を読む（無ければ空リスト。annotate_clusters未実行の意）."""
    path = Path(atlas_dir) / "cluster_annotations.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("annotations", []))


def annotate_failure(
    atlas_dir: str | Path,
    *,
    work_id: str,
    niche_desc: str,
    reason: str,
) -> None:
    """SHELVE/DISCARDになった座標を否定的地図へ追記する（PLAN §4.3）."""
    atlas_dir = Path(atlas_dir)
    atlas_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "work_id": work_id,
        "niche_desc": niche_desc,
        "reason": reason,
    }
    with open(atlas_dir / "negative.jsonl", "a", encoding="utf-8") as target:
        target.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_failures(atlas_dir: str | Path) -> list[dict]:
    """否定的地図を追記順に読む."""
    path = Path(atlas_dir) / "negative.jsonl"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]
