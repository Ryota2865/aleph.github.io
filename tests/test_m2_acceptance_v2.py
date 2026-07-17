"""M2 受入基準 v2 — transmute()ゲートの契約範囲（PLAN_CHANGELOG 0.7.18-1、Fable 5審査 問5）.

旧v1（tests/test_m2_acceptance.py::test_transmute_iterates_into_band_and_records_provenance）
は、骨格の形式的特徴を含まないフィクスチャを使うため、distance帯域のみの契約として
明示的に範囲を縮小した（同ファイルの docstring 参照）。本ファイルが、
`min_form_fidelity` の新しい既定値（骨格保存も含めてゲートする）を実際に検証する
「transmuteゲート範囲の担保」を引き継ぐ。

Fable 5の指摘: 「変更不可の契約フィクスチャが骨格特徴を欠くから既定で有効化できない、
は因果が逆である。契約テストの不変性は『旧契約を書き換えない』ことであって『旧契約が
新しい既定を永久に拘束する』ことではない」。S-2パイロット（reports/EXP_transmute_pilot_
20260717.md）がcontent_distance単独ゲートと骨格保存の相関がほぼ無い（r=0.18）ことを
実証した以上、既定は安全側（骨格保存も検証する）であるべき、という設計判断。

実行: pytest -m m2
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import pytest

pytestmark = pytest.mark.m2

FIXTURES = Path(__file__).parent / "fixtures" / "nonliterary"
DIM = 8


class _AlwaysInBandEmbedder:
    """content_distanceは常に帯域内(cos=0.6)を返す—form_fidelityだけで足踏みさせるため."""

    def __call__(self, texts):
        a = np.zeros(DIM)
        a[0] = 1.0
        b = np.zeros(DIM)
        b[0] = 0.6
        b[1] = float(np.sqrt(max(0.0, 1 - 0.6**2)))
        return np.stack([a, b]).astype(np.float32)


def test_default_gate_now_requires_structural_fidelity_for_registered_kinds():
    """既定（min_form_fidelity未指定）で、法令kindの骨格喪失出力は再生成される.

    distanceは常に帯域内(cos=0.6)を返すフェイク埋め込みを使うため、旧v1のように
    distanceだけを理由に1回で終わることはない——骨格が揃うまで反復するのが
    新しい既定である。
    """
    from aleph.materia.transmute import transmute

    source = (FIXTURES / "law_style.txt").read_text(encoding="utf-8")
    calls = {"n": 0}

    def fake_llm(prompt: str) -> str:
        calls["n"] += 1
        if "骨格" in prompt and "抽出" in prompt:
            return json.dumps({"skeleton": "条文構造: 目的/定義/禁止/罰則/附則"}, ensure_ascii=False)
        if calls["n"] <= 2:
            return "何の構造も持たない散文です。"
        return (
            "第一条　この作品において「記憶」とは、薄明に残る像をいう。\n"
            "ただし、火は消えない。"
        )

    card = transmute(
        source, "喪失についての文学", fake_llm, _AlwaysInBandEmbedder(),
        source_biblio={"title": "規程様式", "kind": "law"},
    )
    assert card["provenance"]["iterations"] >= 2, (
        "既定で骨格喪失出力を1回で受理してしまった——min_form_fidelityの既定がNoneに"
        "戻っていないか確認"
    )
    assert card["provenance"]["form_fidelity"] is not None
    assert card["provenance"]["form_fidelity"] > 0.0


def test_default_gate_accepts_immediately_when_structure_and_distance_both_pass():
    """骨格を保った生成文は、既定のゲートでも1回で通過する（過剰な反復を強制しない）."""
    from aleph.materia.transmute import transmute

    source = (FIXTURES / "law_style.txt").read_text(encoding="utf-8")

    def fake_llm(prompt: str) -> str:
        if "骨格" in prompt and "抽出" in prompt:
            return json.dumps({"skeleton": "条文構造: 目的/定義/禁止/罰則/附則"}, ensure_ascii=False)
        return (
            "第一条　この作品において「記憶」とは、薄明に残る像をいう。\n"
            "ただし、火は消えない。"
        )

    card = transmute(
        source, "喪失についての文学", fake_llm, _AlwaysInBandEmbedder(),
        source_biblio={"title": "規程様式", "kind": "law"},
    )
    assert card["provenance"]["iterations"] == 1
    assert card["provenance"]["form_fidelity"] > 0.0


def test_default_gate_still_skips_unregistered_kinds():
    """kind未登録（detector無し）では、既定のままでも計測不能を理由に足踏みしない."""
    from aleph.materia.transmute import transmute

    def fake_llm(prompt: str) -> str:
        if "骨格" in prompt and "抽出" in prompt:
            return json.dumps({"skeleton": "自由詩"}, ensure_ascii=False)
        return "何の構造も持たない文章"

    card = transmute(
        "何かの詩", "任意のテーマ", fake_llm, _AlwaysInBandEmbedder(),
        source_biblio={"kind": "poem"},
    )
    assert card["provenance"]["iterations"] == 1
    assert card["provenance"]["form_fidelity"] is None
