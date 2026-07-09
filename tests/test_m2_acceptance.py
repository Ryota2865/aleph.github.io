"""M2 受入基準（PLAN §10 M2・§5）— 施工対象。施工完了時に全て緑になること.

実行: pytest -m m2
設計: PLAN_CHANGELOG 0.7.3。偽LLM・偽埋め込みでロジック契約を固定する。
「上位50対の目視7/10非自明」「実母材からの生成」の質的判定は実ラン+監査で行う。
テストを弱める変更（assertの削除・skip追加）は監査で不合格となる。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.m2

FIXTURES = Path(__file__).parent / "fixtures" / "nonliterary"
DIM = 8


# ---------------------------------------------------------------- ヘルパ
def write_index(tmp_path: Path, rows: list[dict], vectors: np.ndarray) -> Path:
    """M1形式のプレーン索引（PLAN_CHANGELOG 0.7.2-1）を直接構築する."""
    out = tmp_path / "atlas"
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "embeddings.npy", vectors.astype(np.float32))
    with open(out / "chunks.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "manifest.json").write_text(
        json.dumps({"n_works": len({r["work_id"] for r in rows}), "n_chunks": len(rows), "dim": vectors.shape[1]}),
        encoding="utf-8",
    )
    return out


def row(cid, wid, title, author, text, era="1900"):
    return {
        "chunk_id": cid, "work_id": wid, "title": title, "author": author,
        "seq": 0, "text": text, "char_len": len(text), "meta": {"era": era},
    }


# ---------------------------------------------------------------- 隠れた類似性
def test_hidden_pairs_prefer_surface_far_deep_near(tmp_path):
    """表層遠・深層近（PLAN §5.1）: 埋め込みが近く、著者・語彙が遠い対が上位に来る."""
    from aleph.materia.similarity import find_hidden_pairs

    v = np.zeros(DIM); v[0] = 1.0
    rows = [
        # 対A: 同一クラスタ・別著者・別時代・語彙も別 → 理想の「隠れた類似」
        row("a1", "w1", "熱力学講義", "理学者A", "エントロピーは不可逆過程において増大する。", era="1950"),
        row("a2", "w2", "失恋記", "小説家B", "あの日から、心は戻らない方向へだけ動いた。", era="1890"),
        # 対B: 同一クラスタだが同著者・語彙もほぼ同一 → 自明な類似
        row("b1", "w3", "随筆一", "随筆家C", "春の朝に庭を歩くのは楽しい。", era="1920"),
        row("b2", "w4", "随筆二", "随筆家C", "春の朝に庭を歩くのは楽しいものだ。", era="1921"),
        # 同一作品内の対は候補にしない
        row("c1", "w5", "長編", "作家D", "第一章の文章。", era="1930"),
        row("c2", "w5", "長編", "作家D", "第二章の文章。", era="1930"),
    ]
    vecs = np.stack([v, v * 0.98, v * 1.02, v, v, v * 1.01])
    index = write_index(tmp_path, rows, vecs)

    pairs = find_hidden_pairs(index, top_n=10)
    assert pairs, "対が1件も出力されない"
    ids = [{p["chunk_a"], p["chunk_b"]} for p in pairs]
    assert {"c1", "c2"} not in ids, "同一作品内の対が混入している"
    ia = ids.index({"a1", "a2"}) if {"a1", "a2"} in ids else 99
    ib = ids.index({"b1", "b2"}) if {"b1", "b2"} in ids else 99
    assert ia < ib, "表層が遠い対が、自明な対より上位に来ていない"
    for p in pairs:
        for field in ("chunk_a", "chunk_b", "deep_sim", "surface_dist", "score"):
            assert field in p


def test_pairs_become_material_cards(tmp_path):
    """発見対は素材カード（PLAN §5冒頭のスキーマ）に統一される."""
    from aleph.materia.similarity import to_material_cards

    pairs = [{
        "chunk_a": "a1", "chunk_b": "a2", "work_a": "w1", "work_b": "w2",
        "title_a": "熱力学講義", "title_b": "失恋記",
        "text_a": "エントロピーは増大する。", "text_b": "心は戻らない。",
        "deep_sim": 0.95, "surface_dist": 0.9, "score": 0.85,
        "note": "不可逆性という骨格の同型",
    }]
    cards = to_material_cards(pairs)
    card = cards[0]
    for field in ("content", "source", "method", "tags"):
        assert field in card
    assert card["method"] == "similarity"


# ---------------------------------------------------------------- 結合術
def test_combinator_emits_only_unseen_cells():
    """組合せ表の空きセルだけを生成する（PLAN §5.2: ランダムではなく空きセルから引く）."""
    from aleph.materia.combinator import generate_combinations

    axes = {"主題": ["喪失", "変態"], "形式": ["書簡体", "規約文"], "視点": ["二人称"]}
    existing = {("喪失", "書簡体", "二人称")}
    combos = generate_combinations(axes, existing)
    tuples = {tuple(c[a] for a in axes) for c in combos}
    assert ("喪失", "書簡体", "二人称") not in tuples
    assert len(tuples) == 3  # 2*2*1 - 1


def test_combinator_assessment_attaches_scores():
    from aleph.materia.combinator import assess

    def fake_scout(prompt: str) -> str:
        return json.dumps({"feasibility": 0.7, "interest": 0.8, "rationale": "見立て"}, ensure_ascii=False)

    combos = [{"主題": "変態", "形式": "規約文", "視点": "二人称"}]
    assessed = assess(combos, fake_scout)
    assert assessed[0]["feasibility"] == 0.7 and assessed[0]["interest"] == 0.8


# ---------------------------------------------------------------- 換骨奪胎
def test_distance_band_rejects_parody_and_unrelated():
    """母材への距離帯域（PLAN §5.3-3）: 近すぎ=パロディ、遠すぎ=無関係、を弾く."""
    from aleph.materia.transmute import distance_band_check

    class FakeEmb:
        def __init__(self, cos): self.cos = cos
        def __call__(self, texts):
            a = np.zeros(DIM); a[0] = 1.0
            b = np.zeros(DIM); b[0] = self.cos; b[1] = float(np.sqrt(max(0.0, 1 - self.cos**2)))
            return np.stack([a, b]).astype(np.float32)

    ok_near, cos_near = distance_band_check("母材", "ほぼ写し", FakeEmb(0.97))
    ok_band, cos_band = distance_band_check("母材", "適度な距離", FakeEmb(0.6))
    ok_far, cos_far = distance_band_check("母材", "無関係", FakeEmb(0.05))
    assert not ok_near and ok_band and not ok_far
    assert abs(cos_band - 0.6) < 0.05


def test_transmute_iterates_into_band_and_records_provenance():
    """帯域に入るまで反復し、母材の書誌と反復回数を素材カードに残す（PLAN §5.3・§8系譜）."""
    from aleph.materia.transmute import transmute

    source = (FIXTURES / "law_style.txt").read_text(encoding="utf-8")
    calls = {"n": 0}

    def fake_llm(prompt: str) -> str:
        calls["n"] += 1
        if "骨格" in prompt and "抽出" in prompt:
            return json.dumps({"skeleton": "条文構造: 目的/定義/禁止/罰則/附則"}, ensure_ascii=False)
        return f"第{calls['n']}稿の文学的テキスト"

    cos_seq = iter([0.95, 0.92, 0.6])

    class SeqEmb:
        def __call__(self, texts):
            c = next(cos_seq)
            a = np.zeros(DIM); a[0] = 1.0
            b = np.zeros(DIM); b[0] = c; b[1] = float(np.sqrt(max(0.0, 1 - c**2)))
            return np.stack([a, b]).astype(np.float32)

    card = transmute(source, "喪失についての文学", fake_llm, SeqEmb(), source_biblio={"title": "規程様式", "kind": "law"})
    assert card["method"] == "transmute"
    assert card["provenance"]["source"]["title"] == "規程様式"  # 系譜の透明性（PLAN §8）
    assert card["provenance"]["iterations"] == 3
    assert 0.3 <= card["provenance"]["final_cos"] <= 0.85


def test_three_nonliterary_fixtures_exist_and_differ():
    """非文学母材3種（PLAN §10 M2受入）: RFC様式・法令様式・コミットログ様式."""
    texts = [(FIXTURES / n).read_text(encoding="utf-8") for n in
             ("rfc_style.txt", "law_style.txt", "commitlog_style.txt")]
    assert all(len(t) > 200 for t in texts)
    assert len({t[:50] for t in texts}) == 3


# ---------------------------------------------------------------- AI固有表現
def make_fake_llm_with_logprobs(candidates):
    """(text, mean_logprob) のリストから偽LLM応答列を作る."""
    from aleph.core.llm import LLMResponse, TokenLogprob, Usage

    responses = [
        LLMResponse(
            text=text, model="fake", provider="fake",
            usage=Usage(prompt_tokens=1, completion_tokens=5), cost_usd=0.0,
            logprobs=tuple(TokenLogprob(token=f"t{i}", logprob=lp) for i in range(5)),
        )
        for text, lp in candidates
    ]
    it = iter(responses)
    return lambda messages, **kw: next(it)


def test_anti_cliche_picks_surprising_but_coherent():
    """反クリシェ生成（PLAN §5.4）: 高確率（陳腐）候補を避け、意外かつ整合的な候補を選ぶ.
    クリシェ候補は provenance として記録される（何を避けたかも作品の一部）."""
    from aleph.materia.ai_native import anti_cliche

    llm = make_fake_llm_with_logprobs([
        ("よくある続き", -0.1),      # 最高確率 = クリシェ
        ("意外だが破綻した続き", -8.0),
        ("意外で整合的な続き", -4.0),
    ])

    def fake_scout(prompt: str) -> str:
        coherent = "破綻" not in prompt
        return json.dumps({"coherent": coherent, "rationale": "審査"}, ensure_ascii=False)

    card = anti_cliche("書き出し文", llm, fake_scout, n_candidates=3)
    assert card["content"] == "意外で整合的な続き"
    assert card["provenance"]["rejected_cliche"] == "よくある続き"
    assert card["method"] == "anti_cliche"


def test_perplexity_curve_per_section():
    """perplexity設計（PLAN §5.4）: 節ごとの平均logprobの曲線が計測・記録される."""
    from aleph.materia.ai_native import perplexity_curve

    llm = make_fake_llm_with_logprobs([("節1", -1.0), ("節2", -5.0), ("節3", -2.0)])
    curve = perplexity_curve(["節1計画", "節2計画", "節3計画"], llm)
    assert len(curve) == 3
    assert curve[1] < curve[0]  # 節2が最も意外（logprobが低い）
    assert curve[1] < curve[2]


def test_token_poetics_reports_boundary_structure():
    """トークン層の詩学（PLAN §5.4）: tokenizer境界の構造を素材カード化する."""
    from aleph.materia.ai_native import token_poetics

    def fake_tokenizer(text: str) -> list[str]:
        return [text[i : i + 3] for i in range(0, len(text), 3)]

    card = token_poetics("山路を登りながらこう考えた", fake_tokenizer)
    assert card["method"] == "token_poetics"
    assert card["provenance"]["n_tokens"] == len(fake_tokenizer("山路を登りながらこう考えた"))
    assert "boundaries" in card["provenance"]


def test_technique_registry_has_three_with_logprobs():
    """技法カタログ（PLAN §10 M2受入）: 最低3技法、うち1つ以上がlogprobs技法."""
    from aleph.materia.ai_native import TECHNIQUES

    assert len(TECHNIQUES) >= 3
    assert any(t.get("requires") == "logprobs" for t in TECHNIQUES.values())
    for t in TECHNIQUES.values():
        assert "run" in t and callable(t["run"])


def test_ai_nativeness_grading():
    """各技法は「人間にも可能か」の審査で等級づけされる（PLAN §5.4末尾）."""
    from aleph.materia.ai_native import grade_ai_nativeness

    def fake_scout(prompt: str) -> str:
        return json.dumps({"human_feasible": False, "grade": "S", "rationale": "logprobs参照は人間に不可能"}, ensure_ascii=False)

    card = {"content": "x", "method": "anti_cliche", "source": {}, "tags": []}
    graded = grade_ai_nativeness(card, fake_scout)
    assert graded["ai_nativeness"]["grade"] == "S"
    assert graded["ai_nativeness"]["human_feasible"] is False
