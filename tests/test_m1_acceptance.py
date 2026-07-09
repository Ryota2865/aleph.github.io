"""M1 受入基準（PLAN §10 M1・§4）— 施工対象。施工完了時に全て緑になること.

実行: pytest -m m1
設計: PLAN_CHANGELOG 0.7.2（プレーン索引方式・二層検証）。
ここでは偽埋め込み・偽scoutでロジック契約を固定する。「1万文書以上の実取り込みと
上位20件レポート生成」は CLI `aleph explore` の実ランと監査（PLAN §12）で検証する。
テストを弱める変更（assertの削除・skip追加）は監査で不合格となる。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.m1

RNG = np.random.default_rng(20260709)
DIM = 16  # 偽埋め込みの次元。実運用は bge-m3 の1024


# ---------------------------------------------------------------- 偽物
class FakeEmbedder:
    """決定論的な偽埋め込み。テキスト先頭の [cN] マーカーでクラスタ中心を切替える."""

    dim = DIM

    def __init__(self):
        self.centers = {f"c{i}": RNG.normal(size=DIM) * 10 for i in range(8)}

    def __call__(self, texts: list[str]) -> np.ndarray:
        out = []
        for t in texts:
            tag = t[: t.find("]") + 1] if t.startswith("[c") else ""
            center = self.centers.get(tag.strip("[]"), np.zeros(DIM))
            out.append(center + RNG.normal(size=DIM) * 0.5)
        return np.asarray(out, dtype=np.float32)


def make_corpus_jsonl(path: Path, n_works: int = 30, cluster_of=lambda i: f"c{i % 3}") -> None:
    """合成コーパス。各作品は5段落、段落頭にクラスタマーカー."""
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n_works):
            paras = [f"[{cluster_of(i)}] 段落{j}。" + "文章です。" * 40 for j in range(5)]
            f.write(
                json.dumps(
                    {
                        "id": f"w{i:04d}",
                        "title": f"作品{i}",
                        "author": f"著者{i % 5}",
                        "text": "\n".join(paras),
                        "meta": {"文字遣い種別": "新字新仮名"},
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


# ---------------------------------------------------------------- チャンク
def test_chunk_respects_paragraphs_and_length():
    """チャンクは段落境界を跨いで結合され、目安サイズ前後に収まる（PLAN_CHANGELOG 0.7.2-4）."""
    from aleph.explore.corpus import chunk_text

    paras = ["あ" * 300 for _ in range(20)]
    text = "\n".join(paras)
    chunks = chunk_text(text, target_chars=1000)
    assert all(len(c) <= 2000 for c in chunks)
    assert sum(len(c.replace("\n", "")) for c in chunks) == 300 * 20
    # 段落の中身は分割されない（300字の段落が切り刻まれていない）
    for c in chunks:
        for p in c.split("\n"):
            assert len(p) in (0, 300)


def test_chunk_sampling_covers_whole_work():
    """max_chunks制限時は冒頭偏重せず作品全体から抽出する（PLAN_CHANGELOG 0.7.2-4）."""
    from aleph.explore.corpus import chunk_text

    paras = [f"段落{i:03d}。" + "あ" * 500 for i in range(100)]
    chunks = chunk_text("\n".join(paras), target_chars=600, max_chunks=10)
    assert len(chunks) == 10
    positions = [int(c.split("。")[0].replace("段落", "")) for c in chunks]
    assert min(positions) < 20 and max(positions) > 80  # 先頭と末尾の両方に届く


# ---------------------------------------------------------------- 取り込みと索引
def test_ingest_builds_plain_index(tmp_path):
    """索引 = embeddings.npy + chunks.jsonl + manifest.json（PLAN_CHANGELOG 0.7.2-1）."""
    from aleph.explore.corpus import ingest

    corpus = tmp_path / "works.jsonl"
    make_corpus_jsonl(corpus, n_works=30)
    out = tmp_path / "atlas"
    stats = ingest(corpus, out, FakeEmbedder(), target_chars=800, max_chunks_per_work=5)

    emb = np.load(out / "embeddings.npy")
    lines = [json.loads(l) for l in (out / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    assert stats.n_works == 30
    assert emb.shape == (stats.n_chunks, DIM) and emb.dtype == np.float32
    assert len(lines) == stats.n_chunks  # 行と埋め込みは1対1対応
    for rec in lines[:3]:
        for field in ("chunk_id", "work_id", "title", "author", "seq", "text"):
            assert field in rec
    assert manifest["n_chunks"] == stats.n_chunks and manifest["dim"] == DIM


# ---------------------------------------------------------------- 文体素性
def test_style_vector_separates_dialogue_from_narration():
    """文体素性ベクトル（PLAN §4.2）は少なくとも会話率で作品を区別できる."""
    from aleph.explore.atlas import style_vector, STYLE_FEATURES

    dialogue = "「おはよう」と彼は言った。「今日はいい天気だね」「そうね」と彼女は答えた。" * 10
    narration = "山道を登りながら、こう考えた。智に働けば角が立つ。情に棹させば流される。" * 10
    v1, v2 = style_vector(dialogue), style_vector(narration)
    assert v1.shape == v2.shape == (len(STYLE_FEATURES),)
    i = STYLE_FEATURES.index("dialogue_ratio")
    assert v1[i] > v2[i]


# ---------------------------------------------------------------- アトラス
def test_atlas_finds_clusters_and_sparse_points(tmp_path):
    """密度推定とクラスタリング（PLAN §4.2）: 合成3クラスタ+外れ値を検出できる."""
    from aleph.explore.corpus import ingest
    from aleph.explore.atlas import build_atlas

    corpus = tmp_path / "works.jsonl"
    # 29作品は3クラスタ、1作品(w0029)だけ孤立クラスタc7
    make_corpus_jsonl(corpus, n_works=30, cluster_of=lambda i: "c7" if i == 29 else f"c{i % 3}")
    out = tmp_path / "atlas"
    ingest(corpus, out, FakeEmbedder(), target_chars=800, max_chunks_per_work=5)

    atlas = build_atlas(out, knn_k=8, min_cluster_size=10)
    assert atlas.n_clusters >= 2  # 主要クラスタが見つかる
    # 疎領域: 孤立作品のチャンクが上位に来る
    sparse = atlas.sparse_regions(top_n=10)
    assert any(r["work_id"] == "w0029" for r in sparse), "孤立点が疎領域として検出されない"
    # 密度・ラベルは索引と同数
    assert atlas.density.shape[0] == atlas.labels.shape[0]


def test_negative_atlas_annotation(tmp_path):
    """否定的地図（PLAN §4.3・§16.10）: 失敗の座標と理由が追記され、再読できる."""
    from aleph.explore.atlas import annotate_failure, load_failures

    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()
    annotate_failure(atlas_dir, work_id="w9999", niche_desc="実験的な形式X", reason="SHELVE: 深さがなかった")
    annotate_failure(atlas_dir, work_id="w9998", niche_desc="形式Y", reason="DISCARD: 既存作の焼き直し")
    failures = load_failures(atlas_dir)
    assert len(failures) == 2
    assert failures[0]["work_id"] == "w9999" and "reason" in failures[0]


# ---------------------------------------------------------------- ニッチ探索
CANNED_SCOUT = {
    "n1": {"vacancy_type": "未着手型", "depth": "高", "rationale": "誰も試みていないが十分な深さがある"},
    "n2": {"vacancy_type": "空虚型", "depth": "低", "rationale": "つまらないから空いている"},
    "n3": {"vacancy_type": "不可能型", "depth": "中", "rationale": "人間には書けない形式"},
}


def fake_scout(prompt: str) -> str:
    for key, resp in CANNED_SCOUT.items():
        if key in prompt:
            return json.dumps(resp, ensure_ascii=False)
    return json.dumps({"vacancy_type": "未着手型", "depth": "中", "rationale": "既定"}, ensure_ascii=False)


def test_classify_vacancy_three_types():
    """空きの三分類（PLAN §4.3）がパースされ、空虚型は除外フラグを持つ."""
    from aleph.explore.niche import classify_vacancy

    c1 = classify_vacancy(fake_scout("n1 について"))
    c2 = classify_vacancy(fake_scout("n2 について"))
    c3 = classify_vacancy(fake_scout("n3 について"))
    assert c1.vacancy_type == "未着手型" and not c1.excluded
    assert c2.vacancy_type == "空虚型" and c2.excluded  # 空虚型は除外（§4.3・§16.2）
    assert c3.vacancy_type == "不可能型" and c3.ai_native_candidate  # AI固有表現候補フラグ（§5.4連携）


def test_classify_vacancy_survives_sloppy_json():
    """scoutの出力が完全なJSONでなくても頑健にパースする（前後に文が付く等）."""
    from aleph.explore.niche import classify_vacancy

    sloppy = '分析します。\n```json\n{"vacancy_type": "未着手型", "depth": "高", "rationale": "x"}\n```\n以上。'
    c = classify_vacancy(sloppy)
    assert c.vacancy_type == "未着手型"


def test_niche_ranking_is_not_novelty_alone():
    """ニッチは新奇性単独で選抜しない（PLAN §4.3・§16.1）: 三つ組で採点する."""
    from aleph.explore.niche import rank_niches

    high_novelty_unreachable = {
        "id": "nx", "novelty": 1.0, "reachability": 0.05, "interpretability": 0.05,
        "vacancy_type": "未着手型", "excluded": False,
    }
    balanced = {
        "id": "ny", "novelty": 0.6, "reachability": 0.7, "interpretability": 0.7,
        "vacancy_type": "未着手型", "excluded": False,
    }
    empty_kind = {
        "id": "nz", "novelty": 0.9, "reachability": 0.9, "interpretability": 0.9,
        "vacancy_type": "空虚型", "excluded": True,
    }
    ranked = rank_niches([high_novelty_unreachable, balanced, empty_kind])
    ids = [n["id"] for n in ranked]
    assert "nz" not in ids  # 空虚型は選抜されない
    assert ids.index("ny") < ids.index("nx")  # 三つ組の均衡が新奇性単独に勝つ


# ---------------------------------------------------------------- Web照合
def test_web_check_excludes_existing_and_saves_material(tmp_path):
    """Web照合（PLAN §4.3-3・§4.4）: 既存例があれば除外し、先行例は素材カード化.
    保護テキストは引用短片+書誌のみ（全文保存しない）."""
    from aleph.explore.webresearch import web_check, to_material_card

    def fake_search(query, count=5):
        return [
            {"title": "既存の同種作品レビュー", "url": "https://example.com/prior",
             "snippet": "まさにこの形式の作品が2020年に発表されている。" * 20}
        ]

    def confirm_scout(prompt):
        return json.dumps({"exists": True, "rationale": "既存例が確認できる"}, ensure_ascii=False)

    niche = {"id": "n1", "description": "書簡体×化学反応式の中編"}
    result = web_check(niche, fake_search, confirm_scout)
    assert result.excluded is True
    assert len(result.prior_examples) >= 1

    card = to_material_card(fake_search("q")[0])
    assert card["source"]["url"] == "https://example.com/prior"
    assert len(card["content"]) <= 500  # 短片のみ。全文を保存しない（PLAN §4.4）


def test_web_check_keeps_novel_niche():
    from aleph.explore.webresearch import web_check

    def empty_search(query, count=5):
        return []

    def deny_scout(prompt):
        return json.dumps({"exists": False, "rationale": "見つからない"}, ensure_ascii=False)

    result = web_check({"id": "n9", "description": "未知の形式"}, empty_search, deny_scout)
    assert result.excluded is False


# ---------------------------------------------------------------- レポート
def test_report_generation(tmp_path):
    """niche/report.md（PLAN §4.3）: 三分類・深さ・除外理由つきで上位N件を出力."""
    from aleph.explore.niche import report

    niches = [
        {"id": f"n{i}", "kind": "sparse", "description": f"ニッチ{i}", "novelty": 0.5 + i * 0.01,
         "reachability": 0.6, "interpretability": 0.6, "vacancy_type": "未着手型",
         "depth": "高", "rationale": "理由", "excluded": False, "web_check": "clear"}
        for i in range(25)
    ]
    out = tmp_path / "niche" / "report.md"
    report(niches, out, top_n=20)
    text = out.read_text(encoding="utf-8")
    assert text.count("## ") == 20  # 上位20件
    assert "未着手型" in text and "深さ" in text
    assert "ヒューリスティック" in text  # 価値関数ではないという但し書き（§4.3）


# ---------------------------------------------------------------- コアの拡張
def test_llmresponse_surfaces_reasoning_content():
    """PLAN_CHANGELOG 0.7.2-2: 思考モデルの reasoning_content を LLMResponse.reasoning に保存."""
    import httpx

    from aleph.core.llm import Message, OpenAICompatProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "答え", "reasoning_content": "考え中…"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatProvider(base_url="http://test/v1", name="llamacpp", client=client)
    resp = provider.complete("some-model", [Message("user", "q")])
    assert resp.text == "答え"
    assert resp.reasoning == "考え中…"
