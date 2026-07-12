"""L3 隠れた類似性（PLAN §5.1）— 表層が遠く深層が近い対の採掘。骨格署名の照合

人間が気づかない類似性 = 表層（語彙・著者・時代）が遠く、深層（埋め込み）が近い対。
M1のプレーン索引（embeddings.npy + chunks.jsonl。PLAN_CHANGELOG 0.7.2-1）を読み、
kNNで近傍対を列挙し、著者・年代・語彙の遠さで重み付けする。

施工: M2. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.neighbors import NearestNeighbors

from aleph.explore.niche import _extract_json_object


def _load_index(index_dir: Path) -> tuple[list[dict], np.ndarray]:
    index_dir = Path(index_dir)
    vectors = np.load(index_dir / "embeddings.npy")
    with open(index_dir / "chunks.jsonl", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return rows, vectors


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _era_value(meta: dict) -> float | None:
    try:
        return float(meta.get("era"))
    except (TypeError, ValueError):
        return None


def _trigrams(text: str) -> set[str]:
    return {text[i : i + 3] for i in range(max(0, len(text) - 2))}


def _jaccard(a: set, b: set) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def find_hidden_pairs(
    index_dir,
    *,
    top_n: int = 50,
    knn_k: int = 10,
    min_chars: int = 0,
    focus_vec: np.ndarray | None = None,
    focus_top_m: int = 2000,
    exclude_pairs: set[tuple[str, str]] | None = None,
) -> list[dict]:
    """表層遠・深層近な対を発見する（PLAN §5.1）.

    M1のプレーン索引をkNNで探索し、同一work_id対を除外した候補のうち
    score（= deep_sim × surface_dist）降順で上位 top_n 件を返す。
    surface_dist は (著者差, 年代差の正規化, 1-語彙3gram Jaccard) の平均。

    min_chars: 本文（strip後）がこの文字数未満のチャンクを候補から除外する。
    章番号だけのチャンク（「一」等）は埋め込みがほぼ同一になり、自明な対で
    上位を占有してしまうため、実運用では 80 程度を渡すこと。
    """
    rows, vectors = _load_index(index_dir)
    n = len(rows)
    if n < 2:
        return []
    substantial = [len((r.get("text") or "").strip()) >= min_chars for r in rows]
    normed = _normalize(vectors.astype(np.float64))
    search_indices = np.arange(n)
    if focus_vec is not None:
        focus = np.asarray(focus_vec, dtype=np.float64).reshape(-1)
        focus_norm = float(np.linalg.norm(focus))
        if focus_norm > 0 and focus.shape[0] == normed.shape[1]:
            eligible = np.flatnonzero(np.asarray(substantial, dtype=bool))
            top_m = min(max(0, int(focus_top_m)), int(eligible.size))
            if top_m == 0:
                return []
            else:
                sims = normed @ (focus / focus_norm)
                search_indices = eligible[np.argsort(sims[eligible], kind="stable")[::-1][:top_m]]
    if len(search_indices) < 2:
        return []

    k = min(knn_k + 1, len(search_indices))  # 自分自身を含むため+1
    nn = NearestNeighbors(n_neighbors=k, metric="cosine")
    search_vectors = normed[search_indices]
    nn.fit(search_vectors)
    _, indices = nn.kneighbors(search_vectors)

    candidate_idx: set[tuple[int, int]] = set()
    for local_i, neighbors in enumerate(indices):
        i = int(search_indices[local_i])
        if not substantial[i]:
            continue
        for local_j in neighbors:
            j = int(search_indices[int(local_j)])
            if j == i:
                continue
            if not substantial[j]:
                continue
            if rows[i]["work_id"] == rows[j]["work_id"]:
                continue
            candidate_idx.add((min(i, j), max(i, j)))

    eras = [_era_value(rows[i].get("meta", {}) or {}) for i in range(n)]
    era_diffs = [
        abs(eras[i] - eras[j])
        for i, j in candidate_idx
        if eras[i] is not None and eras[j] is not None
    ]
    max_era_diff = max(era_diffs) if era_diffs else 0.0

    pairs: list[dict] = []
    excluded = exclude_pairs or set()
    for i, j in candidate_idx:
        ri, rj = rows[i], rows[j]
        chunk_pair = tuple(sorted((str(ri["chunk_id"]), str(rj["chunk_id"]))))
        if chunk_pair in excluded:
            continue
        deep_sim = float(np.dot(normed[i], normed[j]))

        author_component = 0.0 if ri.get("author") == rj.get("author") else 1.0

        ei, ej = eras[i], eras[j]
        if ei is None or ej is None:
            era_component = 0.5
        elif max_era_diff > 0:
            era_component = abs(ei - ej) / max_era_diff
        else:
            era_component = 0.0

        lexical_component = 1.0 - _jaccard(_trigrams(ri.get("text", "")), _trigrams(rj.get("text", "")))

        surface_dist = (author_component + era_component + lexical_component) / 3.0
        score = deep_sim * surface_dist

        pairs.append(
            {
                "chunk_a": ri["chunk_id"],
                "chunk_b": rj["chunk_id"],
                "work_a": ri["work_id"],
                "work_b": rj["work_id"],
                "title_a": ri.get("title", ""),
                "title_b": rj.get("title", ""),
                "text_a": ri.get("text", ""),
                "text_b": rj.get("text", ""),
                "deep_sim": deep_sim,
                "surface_dist": surface_dist,
                "score": score,
            }
        )
    pairs.sort(key=lambda p: p["score"], reverse=True)
    return pairs[:top_n]


def annotate_pairs(pairs: list[dict], scout) -> list[dict]:
    """各対に scout の「この類似は何を意味するか」註を付ける（PLAN §5.1）."""
    annotated = []
    for pair in pairs:
        prompt = (
            "次の2つの断片の間に見つかった類似が何を意味するか、日本語で簡潔に註釈してください。"
            '結果は JSON {"note": "..."} だけで返してください。\n'
            f"断片A（{pair.get('title_a', '')}）: {pair.get('text_a', '')}\n"
            f"断片B（{pair.get('title_b', '')}）: {pair.get('text_b', '')}"
        )
        response = scout(prompt)
        parsed = _extract_json_object(response) or {}
        note = str(parsed.get("note") or response.strip())
        annotated.append({**pair, "note": note})
    return annotated


def to_material_cards(pairs: list[dict]) -> list[dict]:
    """発見対を素材カード（PLAN §5冒頭）に統一する."""
    cards = []
    for pair in pairs:
        content = f"{pair.get('text_a', '')}\n---\n{pair.get('text_b', '')}"
        note = pair.get("note")
        if note:
            content += f"\n[note] {note}"
        card = {
            "content": content,
            "source": {
                "work_a": pair.get("work_a"),
                "work_b": pair.get("work_b"),
                "title_a": pair.get("title_a"),
                "title_b": pair.get("title_b"),
            },
            "method": "similarity",
            "tags": ["hidden_similarity"],
            "provenance": {
                "chunk_a": pair.get("chunk_a"),
                "chunk_b": pair.get("chunk_b"),
                "deep_sim": pair.get("deep_sim"),
                "surface_dist": pair.get("surface_dist"),
                "score": pair.get("score"),
            },
        }
        cards.append(card)
    return cards
