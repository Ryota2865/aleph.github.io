"""M2後の追補契約: transmute()のゲートへdetectorベースの二次基準（骨格の形式的特徴の
残存率 = form_fidelity）を追加する。S-2パイロット（reports/EXP_transmute_pilot_20260717.md）が
content_distance単独ゲートと骨格保存の相関がほぼ無い（Pearson r=0.18, n=40）ことを実証した
ことを受けた追加。

既定（min_form_fidelity未指定）ではdistance帯域のみで判定し、M2契約
（tests/test_m2_acceptance.py）の挙動を一切変えない（オプトイン設計）。

実行: pytest -m m2
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.m2

FIXTURES = Path(__file__).parent / "fixtures" / "nonliterary"
DIM = 8


class _AlwaysInBandEmbedder:
    """content_distanceは常に帯域内(cos=0.6)を返す—fidelityだけで足踏みさせるため."""

    def __call__(self, texts):
        a = np.zeros(DIM)
        a[0] = 1.0
        b = np.zeros(DIM)
        b[0] = 0.6
        b[1] = float(np.sqrt(max(0.0, 1 - 0.6**2)))
        return np.stack([a, b]).astype(np.float32)


def test_min_form_fidelity_explicit_none_disables_gate():
    """明示的にmin_form_fidelity=Noneを渡すとform_fidelityは計測されるがゲートしない。
    0.7.18-1でtransmute()の既定は0.4へ反転したため、無効化には明示指定が必要になった
    （tests/test_m2_acceptance.py の旧v1フィクスチャが使う経路）。
    test_m2_acceptance.py::test_transmute_iterates_into_band_and_records_provenance と
    同じ入力(骨格特徴を含まない生成文)を使い、distanceのみで通ることを確認する。"""
    from aleph.materia.transmute import transmute

    source = (FIXTURES / "law_style.txt").read_text(encoding="utf-8")
    calls = {"n": 0}

    def fake_llm(prompt: str) -> str:
        calls["n"] += 1
        if "骨格" in prompt and "抽出" in prompt:
            return '{"skeleton": "条文構造: 目的/定義/禁止/罰則/附則"}'
        return f"第{calls['n']}稿の文学的テキスト"  # 骨格の形式的特徴を一切含まない

    cos_seq = iter([0.95, 0.92, 0.6])

    class SeqEmb:
        def __call__(self, texts):
            c = next(cos_seq)
            a = np.zeros(DIM)
            a[0] = 1.0
            b = np.zeros(DIM)
            b[0] = c
            b[1] = float(np.sqrt(max(0.0, 1 - c**2)))
            return np.stack([a, b]).astype(np.float32)

    card = transmute(
        source, "喪失についての文学", fake_llm, SeqEmb(),
        source_biblio={"title": "規程様式", "kind": "law"}, min_form_fidelity=None,
    )
    assert card["provenance"]["iterations"] == 3
    assert 0.3 <= card["provenance"]["final_cos"] <= 0.85
    assert card["provenance"]["form_fidelity"] == 0.0  # 計測はされるがゲートには使われない


def test_low_form_fidelity_output_is_retried_when_gate_enabled():
    """min_form_fidelity指定時: 骨格の形式的特徴を欠く生成文はdistanceが帯域内でも
    再生成される。特徴が揃った時点で終了し、form_fidelityがしきい値以上で記録される。"""
    from aleph.materia.transmute import transmute

    source = (FIXTURES / "law_style.txt").read_text(encoding="utf-8")
    calls = {"n": 0}

    def fake_llm(prompt: str) -> str:
        calls["n"] += 1
        if "骨格" in prompt and "抽出" in prompt:
            return '{"skeleton": "条文構造: 目的/定義/禁止/罰則/附則"}'
        if calls["n"] <= 2:
            return "何の構造も持たない散文です。"
        return (
            "第一条　この作品において「記憶」とは、薄明に残る像をいう。\n"
            "ただし、火は消えない。"
        )

    card = transmute(
        source, "喪失についての文学", fake_llm, _AlwaysInBandEmbedder(),
        source_biblio={"title": "規程様式", "kind": "law"},
        min_form_fidelity=0.4,
    )
    assert card["provenance"]["iterations"] >= 2  # 低fidelityの出力(1回目)では終わらない
    assert card["provenance"]["form_fidelity"] is not None
    assert card["provenance"]["form_fidelity"] >= 0.4


def test_unregistered_kind_skips_fidelity_gate_even_when_requested():
    """detectorが存在しないkind（未登録・空文字）では、min_form_fidelityを指定しても
    ゲートされない（測定不能なものを理由に足踏みさせない、fail-openの設計）。"""
    from aleph.materia.transmute import transmute

    def fake_llm(prompt: str) -> str:
        if "骨格" in prompt and "抽出" in prompt:
            return '{"skeleton": "自由詩"}'
        return "何の構造も持たない文章"

    card = transmute(
        "何かの詩", "任意のテーマ", fake_llm, _AlwaysInBandEmbedder(),
        source_biblio={"kind": "poem"},
        min_form_fidelity=0.9,
    )
    assert card["provenance"]["iterations"] == 1
    assert card["provenance"]["form_fidelity"] is None
