"""L3 換骨奪胎（PLAN §5.3）— 母材の形式的骨格を保存し内容を入替。パロディと無関係の間の帯域に入るまで反復

思いがけない素材（非文学テキスト）から構造を奪い、内容を入れ替える:
1. 母材の形式的骨格を抽出
2. 骨格を保存したまま文学的内容を注入
3. 元素材への距離を測り、帯域（近すぎ=パロディ、遠すぎ=無関係、の間）に入るまで反復

施工: M2. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

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
) -> dict:
    """骨格を抽出し、帯域に入るまで反復して素材カードを生成する（PLAN §5.3・§8系譜）."""
    skeleton = extract_skeleton(source_text, llm)

    feedback = ""
    result_text = ""
    cos = 0.0
    iterations = 0
    for iterations in range(1, max_iters + 1):
        prompt = (
            f"次の骨格を保存したまま、内容を「{theme}」へ入れ替えた文学的な文章を書いてください。"
            f"骨格: {skeleton}{feedback}"
        )
        result_text = llm(prompt)
        ok, cos = distance_band_check(source_text, result_text, embedder, near=near, far=far)
        if ok:
            break
        if cos > near:
            feedback = (
                "\n前回の出力は母材に近すぎ、単なるパロディになっていました。"
                "骨格の型は保ちつつ、内容の距離をさらに離してください。"
            )
        else:
            feedback = (
                "\n前回の出力は母材から遠すぎ、無関係になっていました。"
                "骨格の型をもっと保ってください。"
            )

    return {
        "content": result_text,
        "source": source_biblio or {},
        "method": "transmute",
        "tags": ["transmutation"],
        "provenance": {
            "source": source_biblio or {},
            "iterations": iterations,
            "final_cos": cos,
            "skeleton": skeleton,
        },
    }
