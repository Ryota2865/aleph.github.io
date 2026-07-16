"""L3 換骨奪胎（PLAN §5.3）— 母材の形式的骨格を保存し内容を入替。パロディと無関係の間の帯域に入るまで反復

思いがけない素材（非文学テキスト）から構造を奪い、内容を入れ替える:
1. 母材の形式的骨格を抽出
2. 骨格を保存したまま文学的内容を注入
3. 元素材への距離を測り、帯域（近すぎ=パロディ、遠すぎ=無関係、の間）に入るまで反復

施工: M2. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

import re

import numpy as np

from aleph.explore.niche import _extract_json_object


def extract_skeleton(source_text: str, llm) -> str:
    """母材の形式的骨格（構造・様式・型であり内容ではない）をllmに抽出させる（PLAN §5.3手順1）."""
    prompt = (
        "次のテキストの形式的な骨格（構造・様式・型）を抽出してください。内容の要約ではなく、"
        '構造だけを述べること。結果は JSON {"skeleton": "..."} だけで返してください。\n'
        f"{source_text[:4000]}"
    )
    response = llm(prompt)
    parsed = _extract_json_object(response)
    if parsed and parsed.get("skeleton"):
        return str(parsed["skeleton"])
    return response.strip()


# ---------------------------------------------------------------- 骨格保存の測定（第二軸）
# S-2パイロット（reports/EXP_transmute_pilot_20260717.md）が、content_distance単独ゲートと
# 骨格の実際の残存率（form_fidelity）の相関がほぼ無い（Pearson r=0.18, n=40）ことを実証。
# detectorはkind別の正規表現ベースで、パイロットで検証済みのものをそのまま採用する。
_LAW_FEATURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("law.article", re.compile(r"(?:第[一二三四五六七八九十百千〇零0-9０-９]+条)")),
    ("law.paragraph", re.compile(r"(?m)^[ \t　]*(?:[0-9０-９]+)[ \t　]")),
    ("law.item", re.compile(r"(?m)^[ \t　]*[一二三四五六七八九十]+[ \t　]")),
    ("law.definition", re.compile(r"「[^」]{1,80}」(?:と|を)は?|「[^」]{1,80}」[^。\n]{0,80}をいう")),
    ("law.proviso", re.compile(r"(?:ただし|但し)")),
)

_RFC_FEATURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rfc.must", re.compile(r"\bMUST(?:\s+NOT)?\b")),
    ("rfc.should", re.compile(r"\bSHOULD(?:\s+NOT)?\b")),
    ("rfc.may", re.compile(r"\bMAY\b")),
    ("rfc.section", re.compile(r"(?m)^\s*\d+(?:\.\d+)*\.\s+\S")),
    ("rfc.abstract", re.compile(r"(?mi)^\s*Abstract\s*$")),
)

STRUCTURE_DETECTORS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "law": _LAW_FEATURE_PATTERNS,
    "rfc": _RFC_FEATURE_PATTERNS,
}


def extract_structure_features(kind: str, text: str) -> set[str]:
    """source_biblio["kind"]別に登録されたdetectorで形式的特徴を検出する（PLAN §5.3-3の第二軸）.

    未登録のkindは空集合を返す（測定不能＝ゲートしない、の判断はtransmute()側の責務）。
    """
    patterns = STRUCTURE_DETECTORS.get(kind)
    if not patterns:
        return set()
    return {name for name, pattern in patterns if pattern.search(text)}


def retained_feature_ratio(source_features, generated_features) -> float:
    """母材の形式的特徴のうち生成文に残った割合. 母材側が空集合（検出不能）なら0.0."""
    source = set(source_features)
    if not source:
        return 0.0
    generated = set(generated_features)
    return len(source & generated) / len(source)


def structural_fidelity(kind: str, source_text: str, generated_text: str) -> float:
    """kindのdetectorで母材と生成文それぞれの形式的特徴を検出し、残存率を返す."""
    source_features = extract_structure_features(kind, source_text)
    generated_features = extract_structure_features(kind, generated_text)
    return retained_feature_ratio(source_features, generated_features)


def distance_band_check(
    source_text: str,
    result_text: str,
    embedder,
    *,
    near: float = 0.85,
    far: float = 0.3,
) -> tuple[bool, float]:
    """母材への距離帯域チェック（PLAN §5.3手順3）.

    cos > near なら近すぎ（パロディ）で不合格、cos < far なら遠すぎ（無関係）で
    不合格、帯域内なら合格。返り値は (ok, cos)。
    """
    vectors = np.asarray(embedder([source_text, result_text]), dtype=np.float64)
    a, b = vectors[0], vectors[1]
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    cos = float(np.dot(a, b) / (na * nb)) if na and nb else 0.0
    ok = far <= cos <= near
    return ok, cos


def transmute(
    source_text: str,
    theme: str,
    llm,
    embedder,
    *,
    max_iters: int = 5,
    source_biblio: dict | None = None,
    near: float = 0.85,
    far: float = 0.3,
    min_form_fidelity: float | None = None,
) -> dict:
    """骨格を抽出し、帯域に入るまで反復して素材カードを生成する（PLAN §5.3・§8系譜）.

    min_form_fidelity: source_biblio["kind"]がSTRUCTURE_DETECTORSに登録されている場合、
    骨格の形式的特徴の残存率（structural_fidelity）がこの値を下回ると再生成させる第二の
    帯域チェック（S-2パイロットが実証した「content_distanceだけでは骨格喪失を検出できない」
    問題への対処）。既定Noneは無効——distance帯域のみで判定する従来の挙動を保つ
    （M2契約 tests/test_m2_acceptance.py の既存フィクスチャとの後方互換のため）。
    kindが未登録、またはNoneのままの場合はform_fidelityを計測のみ行いゲートしない。
    """
    skeleton = extract_skeleton(source_text, llm)
    kind = (source_biblio or {}).get("kind", "")

    feedback = ""
    result_text = ""
    cos = 0.0
    fidelity: float | None = None
    iterations = 0
    for iterations in range(1, max_iters + 1):
        prompt = (
            f"次の骨格を保存したまま、内容を「{theme}」へ入れ替えた文学的な文章を書いてください。"
            f"骨格: {skeleton}{feedback}"
        )
        result_text = llm(prompt)
        ok, cos = distance_band_check(source_text, result_text, embedder, near=near, far=far)

        fidelity_ok = True
        if kind in STRUCTURE_DETECTORS:
            fidelity = structural_fidelity(kind, source_text, result_text)
            if min_form_fidelity is not None:
                fidelity_ok = fidelity >= min_form_fidelity

        if ok and fidelity_ok:
            break

        feedback_parts = []
        if not ok:
            if cos > near:
                feedback_parts.append(
                    "\n前回の出力は母材に近すぎ、単なるパロディになっていました。"
                    "骨格の型は保ちつつ、内容の距離をさらに離してください。"
                )
            else:
                feedback_parts.append(
                    "\n前回の出力は母材から遠すぎ、無関係になっていました。"
                    "骨格の型をもっと保ってください。"
                )
        if not fidelity_ok:
            feedback_parts.append(
                "\n前回の出力は骨格の具体的な形式的特徴（条文番号・箇条書き・キーワード等）を"
                "十分に残していませんでした。骨格の各要素を実際の形式として文章に残してください。"
            )
        feedback = "".join(feedback_parts)

    return {
        "content": result_text,
        "source": source_biblio or {},
        "method": "transmute",
        "tags": ["transmutation"],
        "provenance": {
            "source": source_biblio or {},
            "iterations": iterations,
            "final_cos": cos,
            "form_fidelity": fidelity,
            "skeleton": skeleton,
        },
    }
