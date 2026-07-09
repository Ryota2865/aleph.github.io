"""M5 受入基準（PLAN §10 M5・§7.3-7.4）— 施工対象。施工完了時に全て緑になること.

実行: pytest -m m5
擱筆判断の3経路（収束/完成宣言/過剰彫琢警報）、人間協働・公開の判断記録、
詩学の自己更新（第0版は人間の種文なし=潜在空間から。§14.3-10）を偽LLMで固定する。
テストを弱める変更（assertの削除・skip追加）は監査で不合格となる。
"""
from __future__ import annotations

import json

import pytest

from aleph.core.artifacts import Work

pytestmark = pytest.mark.m5


def traj(scores, novelty=None):
    out = []
    for i, s in enumerate(scores):
        rec = {"version": i + 1, "mean_score": s, "disagreement": 1.0}
        if novelty:
            rec["novelty_dist"] = novelty[i]
        out.append(rec)
    return out


@pytest.fixture
def work(tmp_path):
    w = Work(tmp_path, "w3000")
    w.create({})
    return w


# ---------------------------------------------------------------- 擱筆3経路
def test_stop_by_convergence():
    """経路1: 直近k版でスコア改善がε未満かつ改稿指摘が循環（PLAN §7.3a）."""
    from aleph.meta.stopping import decide_stop

    result = decide_stop(
        trajectory=traj([6.0, 7.0, 7.01, 7.02]),
        instructions_history=[["附則を短く"], ["附則を短く", "反復に変奏を"], ["附則を短く"]],
        k=3, epsilon=0.05,
    )
    assert result["stop"] is True and result["path"] == "convergence"
    assert result["reason"]


def test_no_stop_while_improving():
    from aleph.meta.stopping import decide_stop

    result = decide_stop(
        trajectory=traj([5.0, 6.5, 8.0]),
        instructions_history=[["a"], ["b"], ["c"]],
        k=3, epsilon=0.05,
    )
    assert result["stop"] is False


def test_stop_by_completion_declaration():
    """経路2: authorの完成宣言に敵対的査読者が反駁できなければ完成（PLAN §7.3a）."""
    from aleph.meta.stopping import completion_declaration

    def author(p):
        return "反復が変奏に達し、これ以上の彫琢は温度を下げる。ゆえに完成である。"

    def adversary_ok(p):
        return json.dumps({"rebutted": False, "rationale": "反駁不能"}, ensure_ascii=False)

    def adversary_ng(p):
        return json.dumps({"rebutted": True, "rationale": "第三条が未回収"}, ensure_ascii=False)

    done = completion_declaration("草稿全文", author, adversary_ok)
    assert done["completed"] is True and "完成" in done["declaration"]
    not_done = completion_declaration("草稿全文", author, adversary_ng)
    assert not_done["completed"] is False and "第三条" in not_done["rebuttal"]


def test_stop_by_over_polish_alarm():
    """経路3: スコア上昇かつ新奇性距離の縮小（無難化）→ 警報つき即時擱筆推奨（PLAN §7.3a・§16.4）."""
    from aleph.meta.stopping import decide_stop

    result = decide_stop(
        trajectory=traj([6.0, 7.0, 8.0], novelty=[0.9, 0.6, 0.3]),
        instructions_history=[["a"], ["b"], ["c"]],
        k=3, epsilon=0.05,
    )
    assert result["stop"] is True and result["path"] == "over_polish"
    assert result.get("alarm") is True


# ---------------------------------------------------------------- 人間協働・記録
def test_collaboration_triggers_and_records(work):
    """倫理リスクで人間を呼び、呼ぶ/呼ばない判断がどちらも根拠つきで記録される（PLAN §7.3b）."""
    from aleph.meta.collaboration import decide_collaboration

    hit = decide_collaboration(work, {"ethical_flags": ["実在人物への言及"]}, decided_by="L7-test")
    assert hit["call_human"] is True
    miss = decide_collaboration(work, {"ethical_flags": []}, decided_by="L7-test")
    assert miss["call_human"] is False

    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    collab = [d for d in decisions if d["layer"] == "L7"]
    assert len(collab) == 2                      # 呼ばない判断も記録される
    assert all(d["reason"] for d in collab)


# ---------------------------------------------------------------- 公開判断
def make_gate_author(prompt_log):
    def author(p):
        prompt_log.append(p)
        return "棚の既公開作と比べ、本作は形式の必然性が一段深い。ゆえに公開に値する。"
    return author


def test_publication_respects_monthly_cap(work):
    """公開上限（月4作。PLAN §7.3d・§14.3-7）到達時は PUBLISH しない."""
    from aleph.meta.publication_gate import decide_publication

    result = decide_publication(
        work, audience="人間 0.9 / 自分 0.1", quality_floor_passed=True,
        monthly_published=4, max_per_month=4,
        shelf_summaries=["既公開A"], author=make_gate_author([]), decided_by="L7-test",
    )
    assert result["decision"] in ("SHELVE", "DISCARD")
    assert "上限" in result["reason"] or "cap" in result["reason"].lower()


def test_publication_compares_against_shelf(work):
    """公開には「なぜ公開に値するか」の棚との比較論述が必要（PLAN §7.3d）."""
    from aleph.meta.publication_gate import decide_publication

    prompts: list[str] = []
    result = decide_publication(
        work, audience="人間 0.9 / 自分 0.1", quality_floor_passed=True,
        monthly_published=1, max_per_month=4,
        shelf_summaries=["既公開A: 規約文学", "既公開B: 書簡体"],
        author=make_gate_author(prompts), decided_by="L7-test",
    )
    assert result["decision"] == "PUBLISH"
    assert "既公開A" in "\n".join(prompts)       # 棚の中身と比較させている
    assert result["comparison"]
    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    assert any(d["layer"] == "L7" and "PUBLISH" in d["decision"] for d in decisions)


def test_self_audience_defaults_to_shelve(work):
    """「自分のため」の作品は公開を前提としない（PLAN §3・§7.3d）."""
    from aleph.meta.publication_gate import decide_publication

    result = decide_publication(
        work, audience="自分 0.9 / 人間 0.1", quality_floor_passed=True,
        monthly_published=0, max_per_month=4,
        shelf_summaries=[], author=make_gate_author([]), decided_by="L7-test",
    )
    assert result["decision"] == "SHELVE"


# ---------------------------------------------------------------- 詩学
def test_poetics_zeroth_version_has_no_human_seed(tmp_path):
    """第0版は潜在空間由来の素材のみから生成し、人間の種文を受け取るAPI自体を持たない
    （PLAN §7.4・§14.3-10）。§16.12の未解決の緊張を最初の問いとして注入する."""
    from aleph.meta.poetics import generate_zeroth
    import inspect

    sig = inspect.signature(generate_zeroth)
    assert "seed_text" not in sig.parameters and "human_seed" not in sig.parameters

    prompts: list[str] = []
    def author(p):
        prompts.append(p)
        return "# 詩学 第0版\n複製の器で複製でないものを試みる。"

    def noise_fragments(n):
        return [f"ノイズ断片{i}" for i in range(n)]

    path = generate_zeroth(tmp_path / "poetics", author, noise_fragments)
    assert path.exists() and "詩学" in path.read_text(encoding="utf-8")
    joined = "\n".join(prompts)
    assert "ノイズ断片0" in joined              # 潜在空間由来の素材が種
    assert "模倣" in joined and "自律" in joined  # §16.12の緊張を第0版の問いとして指定


def test_poetics_reflection_requires_adversary_and_records_diff(tmp_path, work):
    """作品完了後のリフレクション: 改訂は敵対的査読の反駁を経て、差分と理由が残る（PLAN §7.4）."""
    from aleph.meta.poetics import reflect

    poetics_dir = tmp_path / "poetics"
    poetics_dir.mkdir()
    (poetics_dir / "poetics.md").write_text("# 詩学 第0版\n簡潔を美とする。", encoding="utf-8")

    def author(p):
        return json.dumps({"revised": "# 詩学 第1版\n簡潔と断絶を美とする。",
                           "diff_reason": "w3000で断絶の価値を発見した"}, ensure_ascii=False)

    def adversary(p):
        return json.dumps({"rebutted": False, "rationale": "改訂は制作記録と整合"}, ensure_ascii=False)

    result = reflect(poetics_dir, work, author, adversary)
    assert result["applied"] is True
    text = (poetics_dir / "poetics.md").read_text(encoding="utf-8")
    assert "第1版" in text
    history = (poetics_dir / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert any("断絶の価値" in l for l in history)  # 差分理由の記録


def test_poetics_fixation_monitor():
    """改訂履歴の自己類似度が高止まりしたら固着として検出する（PLAN §7.4）."""
    from aleph.meta.poetics import fixation_check

    stuck = ["簡潔を美とする。" for _ in range(4)]
    moving = ["簡潔を美とする。", "断絶を加える。", "参照密度を試す。", "多声性を疑う。"]
    assert fixation_check(stuck) is True
    assert fixation_check(moving) is False
