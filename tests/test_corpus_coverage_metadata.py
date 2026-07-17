"""C-1改訂版・台帳直接計算のロジック（PLAN_CHANGELOG 0.7.19 問2）.

実行: pytest -m m1
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.m1


def test_parse_ndc_maps_language_form_and_juvenile():
    from scripts.corpus_coverage_metadata import parse_ndc

    codes = parse_ndc("NDC 913")
    assert codes == [
        {"code": "913", "juvenile": False, "language": "日本文学", "form": "小説・物語"}
    ]

    juvenile = parse_ndc("NDC K933")
    assert juvenile[0]["juvenile"] is True
    assert juvenile[0]["language"] == "英米文学"

    multi = parse_ndc("NDC 914 915")
    assert [c["form"] for c in multi] == ["評論・随筆", "日記・書簡・紀行"]

    # 9類以外（文学外）は language/form とも None のまま返し、捨てない
    other = parse_ndc("NDC 723")
    assert other[0]["language"] is None and other[0]["form"] is None


def test_parse_first_publication_year_prefers_western_and_converts_era():
    from scripts.corpus_coverage_metadata import parse_first_publication_year

    assert parse_first_publication_year("「新青年」1934（昭和9）年1月") == 1934
    assert parse_first_publication_year("「文藝倶楽部」明治30年4月") == 1897
    assert parse_first_publication_year("大正12年9月") == 1923
    assert parse_first_publication_year("") is None
    assert parse_first_publication_year("初出不明") is None


def test_aggregate_reports_unknowns_explicitly():
    from scripts.corpus_coverage_metadata import aggregate

    rows = [
        {"没年月日": "1927-07-24", "初出": "「新思潮」大正5年", "分類番号": "NDC 913"},
        {"没年月日": "", "初出": "", "分類番号": ""},
    ]
    stats = aggregate(rows)
    assert stats["total_works"] == 2
    assert stats["author_death_decade"] == {"1920s": 1, "unknown": 1}
    assert stats["first_publication_decade"] == {"1910s": 1, "unknown": 1}
    # NDC欄が空の作品は言語軸でも unknown として現れる（黙って落とさない）
    assert stats["language"] == {"日本文学": 1, "unknown": 1}
