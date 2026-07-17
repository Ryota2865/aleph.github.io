"""クラスタ属性注釈の永続化（PLAN_CHANGELOG 0.7.18 問4・designs/corpus-expansion.md C-1）.

sol指摘（§4.1）: scoutの属性ラベリング（theme/form/viewpoint/era）は`aleph explore`の
実行毎に再計算され、一度も永続化されない。Fable5審査 問4: 単一注釈器の分類であることを
注釈モデル・prompt版・信頼度つきで明示すべき。本ファイルは
`annotate_clusters`/`load_cluster_annotations`（永続化・読み出し）と、
`niche._cell_candidates`が永続化済み注釈を優先し、無ければ従来どおりscoutへ
その場ラベリングする後方互換フォールバックを固定する。

実行: pytest -m m1
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

pytestmark = pytest.mark.m1


@dataclass
class _FakeAtlas:
    index_dir: Path
    chunks: list[dict] = field(default_factory=list)
    cluster_meta_value: list[dict] = field(default_factory=list)

    @property
    def cluster_meta(self):
        return self.cluster_meta_value


def _make_atlas(tmp_path: Path) -> _FakeAtlas:
    chunks = [
        {"chunk_id": "c1", "text": "第一条 目的を定める規程の抜粋"},
        {"chunk_id": "c2", "text": "MUST は絶対的要件を意味する"},
    ]
    clusters = [
        {"label": 0, "size": 12, "exemplars": ["c1"], "mean_density": 0.1},
        {"label": 1, "size": 8, "exemplars": ["c2"], "mean_density": 0.2},
    ]
    return _FakeAtlas(index_dir=tmp_path, chunks=chunks, cluster_meta_value=clusters)


def test_annotate_clusters_persists_annotator_and_confidence(tmp_path):
    from aleph.explore.atlas import annotate_clusters, load_cluster_annotations

    atlas = _make_atlas(tmp_path)
    calls = {"n": 0}

    def fake_scout(prompt: str) -> str:
        calls["n"] += 1
        return json.dumps(
            {"theme": f"主題{calls['n']}", "form": "散文", "viewpoint": "三人称", "era": "現代",
             "confidence": 0.7},
            ensure_ascii=False,
        )

    result = annotate_clusters(atlas, fake_scout, annotator_model="test-scout")
    assert len(result) == 2
    assert all(r["annotator_model"] == "test-scout" for r in result)
    assert all(r["confidence"] == 0.7 for r in result)
    assert all(r["attributes"]["form"] == "散文" for r in result)

    path = tmp_path / "cluster_annotations.json"
    assert path.exists()
    reloaded = load_cluster_annotations(tmp_path)
    assert len(reloaded) == 2
    assert reloaded[0]["prompt_version"] == "v1"


def test_annotate_clusters_records_none_on_unparsable_response(tmp_path):
    """scoutの応答がJSONとして解釈不能でも、attributes=None・confidence=Noneで
    記録する（黙って除外しない。測定できなかったこと自体を残す）."""
    from aleph.explore.atlas import annotate_clusters

    atlas = _make_atlas(tmp_path)
    result = annotate_clusters(atlas, lambda p: "解釈不能な応答", annotator_model="test-scout")
    assert all(r["attributes"] is None for r in result)
    assert all(r["confidence"] is None for r in result)


def test_load_cluster_annotations_returns_empty_when_not_yet_run(tmp_path):
    from aleph.explore.atlas import load_cluster_annotations

    assert load_cluster_annotations(tmp_path) == []


def test_cell_candidates_prefers_persisted_annotations_over_scout(tmp_path):
    """永続化済み注釈があれば、_cell_candidatesはscoutを呼ばずそれを使う."""
    from aleph.explore.atlas import annotate_clusters
    from aleph.explore.niche import _cell_candidates

    atlas = _make_atlas(tmp_path)

    def annotate_scout(prompt: str) -> str:
        # 2クラスタに異なる属性をつけ、空セルの組み合わせが生まれるようにする
        if "c1" in prompt or "目的を定める" in prompt:
            return json.dumps({"theme": "規範", "form": "法令", "viewpoint": "三人称", "era": "近代",
                                "confidence": 0.8}, ensure_ascii=False)
        return json.dumps({"theme": "要件", "form": "規格", "viewpoint": "無人称", "era": "現代",
                            "confidence": 0.6}, ensure_ascii=False)

    annotate_clusters(atlas, annotate_scout, annotator_model="test-scout")

    def failing_scout(prompt: str) -> str:
        raise AssertionError("永続化済み注釈があるのにscoutが呼ばれた")

    candidates = _cell_candidates(atlas, failing_scout, top_n=5, context="")
    assert len(candidates) > 0
    assert all(c["kind"] == "empty_cell" for c in candidates)


def test_cell_candidates_falls_back_to_scout_when_not_annotated(tmp_path):
    """永続化済み注釈が無ければ、従来どおりscoutへその場ラベリングを依頼する（後方互換）."""
    from aleph.explore.niche import _cell_candidates

    atlas = _make_atlas(tmp_path)
    calls = {"n": 0}

    def fake_scout(prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            attrs = {"theme": "規範", "form": "法令", "viewpoint": "三人称", "era": "近代"}
        else:
            attrs = {"theme": "要件", "form": "規格", "viewpoint": "無人称", "era": "現代"}
        return json.dumps(attrs, ensure_ascii=False)

    candidates = _cell_candidates(atlas, fake_scout, top_n=5, context="")
    assert calls["n"] == 2, "永続化注釈が無いのにscoutが呼ばれなかった"
    assert len(candidates) > 0
