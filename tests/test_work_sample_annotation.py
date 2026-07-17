"""C-1後半・層化サンプリング注釈のロジック契約（PLAN_CHANGELOG 0.7.19 問2）.

実行: pytest -m m1
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.m1


def _works(n_per_decade: dict[str, int], authors_cycle: int = 3) -> list[dict]:
    works = []
    i = 0
    for decade, n in n_per_decade.items():
        for _ in range(n):
            works.append({
                "id": f"w{i:04d}",
                "title": f"t{i}",
                "author": f"author{i % authors_cycle}_{decade}",
                "death_decade": decade,
                "noise_share": 1.0 if i % 2 else 0.0,
            })
            i += 1
    return works


def test_stratified_sample_is_proportional_and_deterministic():
    from scripts.annotate_work_sample import stratified_sample

    # 著者を十分に多様にし、著者上限が比例配分を律速しない条件で層化を検証する
    works = _works({"1930s": 80, "1950s": 40, "1880s": 4}, authors_cycle=50)
    sample = stratified_sample(works, n_target=30, seed=42)
    by_decade = {}
    for w in sample:
        by_decade[w["death_decade"]] = by_decade.get(w["death_decade"], 0) + 1
    # 比例配分: 1930s ≈ 2×1950s。最小1により小さい層(1880s)も必ず含まれる
    assert by_decade["1930s"] > by_decade["1950s"]
    assert by_decade.get("1880s", 0) >= 1
    # 決定論: 同じseedで同じ標本
    assert [w["id"] for w in stratified_sample(works, n_target=30, seed=42)] == [
        w["id"] for w in sample
    ]


def test_stratified_sample_caps_works_per_author():
    from scripts.annotate_work_sample import stratified_sample

    # 全80作品が同一著者 → 上限2で標本は2作品に留まる（多作著者の占拠防止）
    works = _works({"1930s": 80}, authors_cycle=1)
    sample = stratified_sample(works, n_target=30, seed=1)
    assert len(sample) == 2


def test_aggregate_sample_reports_unannotated_and_noise_majority():
    from scripts.corpus_coverage_sample import aggregate_sample

    annotations = [
        {"work_id": "a", "death_decade": "1930s", "noise_share": 0.9, "confidence": 0.8,
         "attributes": {"theme": "喪失", "form": "小説", "viewpoint": "三人称"}},
        {"work_id": "b", "death_decade": "1950s", "noise_share": 0.2, "confidence": 0.3,
         "attributes": {"theme": "喪失", "form": "評論", "viewpoint": "一人称"}},
        {"work_id": "c", "death_decade": "1930s", "noise_share": 1.0, "confidence": None,
         "attributes": None},
    ]
    stats = aggregate_sample(annotations)
    assert stats["total_works"] == 3
    assert stats["annotated_works"] == 2
    assert stats["unannotated_works"] == 1
    assert stats["low_confidence_works"] == 1
    assert stats["noise_majority_works"] == 2
    assert stats["axis_values"]["theme"] == {"喪失": 2}
    assert len(stats["occupied_combinations"]) == 2
    assert stats["era_theme"]["1930s / 喪失"] == 1
