"""詩学リフレクションの非対称な改訂周期・初回承認ゲート
（PLAN_CHANGELOG 0.7.18-1、Fable5審査 問7-1・問7-3）.

「導く腕（詩学の注入）は毎作、疑う腕（改訂の検討）はN作ごと」という非対称設計と、
「reflect()の出力は設計変更であり、初回はfirst_publish_ackと同型の人間承認ゲートを
要する」という指摘を、RealDeps.reflect_poeticsのゲートロジックとして固定する。

実行: pytest -m m6
"""
from __future__ import annotations

import json

import pytest

from aleph.core.artifacts import Work
from aleph.core.llm import LLMResponse, Usage

pytestmark = pytest.mark.m6


class _FakeRouter:
    def __init__(self, response_text: str = "{}"):
        self.response_text = response_text
        self.calls = 0

    def call(self, role, messages, **overrides):
        self.calls += 1
        return LLMResponse(
            text=self.response_text, model="fake", provider="fake",
            usage=Usage(prompt_tokens=1, completion_tokens=1), cost_usd=0.0,
        )


def _make_deps(tmp_path, *, policies: dict, response_text: str = "{}"):
    from aleph.pipeline import RealDeps

    poetics_dir = tmp_path / "poetics"
    poetics_dir.mkdir()
    (poetics_dir / "poetics.md").write_text("# 第0版", encoding="utf-8")
    work = Work(tmp_path / "works", "w9401")
    work.create({})
    config = type("C", (), {"secrets": {}, "policies": {"poetics": policies}})()
    router = _FakeRouter(response_text)
    deps = RealDeps(
        work, router, config=config, index_dir=tmp_path / "atlas",
        search_fn=lambda *a, **k: [], poetics_dir=poetics_dir,
    )
    return deps, work, router


def test_cadence_gate_skips_reflection_below_threshold(tmp_path):
    """revision_cadence_works=3 のとき、1・2作目はスキップされ、3作目で初めて実行される."""
    deps, work, router = _make_deps(
        tmp_path, policies={"revision_cadence_works": 3, "first_revision_requires_human_ack": True},
    )
    first = deps.reflect_poetics(work)
    assert first["applied"] is False
    assert "周期" in first["diff_reason"]
    assert router.calls == 0

    second = deps.reflect_poetics(work)
    assert second["applied"] is False
    assert router.calls == 0

    # 3作目でreflect()が実際に呼ばれる（fake routerはJSON空応答なのでapplied自体はFalseだが、
    # スキップ理由の文言が変わることでreflect()実行経路に入ったことを確認できる）
    third = deps.reflect_poetics(work)
    assert "周期" not in (third.get("diff_reason") or "")
    assert router.calls > 0


def test_first_revision_requires_ack_blocks_zeroth_version_revision(tmp_path):
    """詩学が第0版のままかつfirst_revision_requires_human_ack=falseなら、
    周期条件を満たしてもreflect()は呼ばれず、理由が記録される."""
    deps, work, router = _make_deps(
        tmp_path,
        policies={"revision_cadence_works": 1, "first_revision_requires_human_ack": False},
    )
    result = deps.reflect_poetics(work)
    assert result["applied"] is False
    assert "人間承認待ち" in result["diff_reason"]
    assert router.calls == 0


def test_first_revision_ack_true_allows_reflection_to_run(tmp_path):
    """first_revision_requires_human_ack=trueなら、周期条件を満たした時点でreflect()が
    実際に呼ばれる（承認ゲートが解除されている）."""
    response = json.dumps(
        {"revised": "# 第1版", "diff_reason": "テスト改訂"}, ensure_ascii=False,
    )
    deps, work, router = _make_deps(
        tmp_path,
        policies={"revision_cadence_works": 1, "first_revision_requires_human_ack": True},
        response_text=response,
    )
    result = deps.reflect_poetics(work)
    assert router.calls > 0
    # fake routerは author/adversary 両方に同じ応答を返すため rebutted のJSON解釈は失敗し
    # rebutted=False（既定）扱いになる＝適用される
    assert result["applied"] is True
