"""C-1属性被覆マップの集計ロジック（designs/corpus-expansion.md C-1）.

実行: pytest -m m1
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.m1


def test_compute_coverage_counts_axis_values_and_occupied_combinations():
    from scripts.corpus_coverage import compute_coverage

    annotations = [
        {"label": 0, "attributes": {"theme": "喪失", "form": "書簡", "viewpoint": "一人称", "era": "近代"},
         "confidence": 0.9},
        {"label": 1, "attributes": {"theme": "喪失", "form": "戯曲", "viewpoint": "三人称", "era": "現代"},
         "confidence": 0.8},
        {"label": 2, "attributes": None, "confidence": None},
    ]
    coverage = compute_coverage(annotations)
    assert coverage["total_clusters"] == 3
    assert coverage["annotated_clusters"] == 2
    assert coverage["unannotated_clusters"] == 1
    assert coverage["axis_values"]["theme"] == {"喪失": 2}
    assert coverage["axis_values"]["form"] == {"書簡": 1, "戯曲": 1}
    assert len(coverage["occupied_combinations"]) == 2
    # theme=1種 x form=2種 x viewpoint=2種 x era=2種 = 8通りのうち2つが占有
    assert coverage["possible_combinations"] == 8
    assert coverage["coverage_ratio"] == pytest.approx(2 / 8)


def test_compute_coverage_flags_low_confidence():
    from scripts.corpus_coverage import compute_coverage

    annotations = [
        {"label": 0, "attributes": {"theme": "a", "form": "b", "viewpoint": "c", "era": "d"},
         "confidence": 0.2},
        {"label": 1, "attributes": {"theme": "a", "form": "b", "viewpoint": "c", "era": "e"},
         "confidence": 0.9},
    ]
    coverage = compute_coverage(annotations)
    assert coverage["low_confidence_clusters"] == 1


def test_compute_coverage_handles_empty_annotations():
    from scripts.corpus_coverage import compute_coverage

    coverage = compute_coverage([])
    assert coverage["total_clusters"] == 0
    assert coverage["possible_combinations"] == 1
    assert coverage["coverage_ratio"] == 0.0
