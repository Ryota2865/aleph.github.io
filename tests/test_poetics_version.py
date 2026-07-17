"""詩学バージョンの刻印（PLAN_CHANGELOG 0.7.18-1、Fable5審査 問7-1）.

reflect()の改訂履歴（history.jsonl）の行数がそのままバージョン番号になる。
RealDeps.choose_intentが呼ばれるたび、その時点のバージョンをL1決定へ刻印する
（改訂後の棚を縦断比較可能にするため）。

実行: pytest -m m5 / m6
"""
from __future__ import annotations

import json

import pytest

from aleph.core.artifacts import Work

pytestmark = pytest.mark.m5


def test_current_version_is_zero_before_any_revision(tmp_path):
    from aleph.meta.poetics import current_version

    poetics_dir = tmp_path / "poetics"
    poetics_dir.mkdir()
    (poetics_dir / "poetics.md").write_text("# 第0版", encoding="utf-8")
    assert current_version(poetics_dir) == 0


def test_current_version_increments_with_applied_revisions(tmp_path):
    from aleph.meta.poetics import current_version

    poetics_dir = tmp_path / "poetics"
    poetics_dir.mkdir()
    history = poetics_dir / "history.jsonl"
    history.write_text(
        json.dumps({"ts": "x", "diff_reason": "a", "rebutted": False}) + "\n",
        encoding="utf-8",
    )
    assert current_version(poetics_dir) == 1
    with open(history, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": "y", "diff_reason": "b", "rebutted": False}) + "\n")
    assert current_version(poetics_dir) == 2


@pytest.mark.m6
def test_real_deps_stamps_poetics_version_on_choose_intent(tmp_path, monkeypatch):
    """RealDeps.choose_intentが、その時点のpoetics_versionをL1決定へ刻印する."""
    from aleph.pipeline import RealDeps

    poetics_dir = tmp_path / "poetics"
    poetics_dir.mkdir()
    (poetics_dir / "poetics.md").write_text("# 第1版\n断絶を美とする。", encoding="utf-8")
    (poetics_dir / "history.jsonl").write_text(
        json.dumps({"ts": "x", "diff_reason": "a", "rebutted": False}) + "\n", encoding="utf-8",
    )

    work = Work(tmp_path / "works", "w9301")
    work.create({})

    class FakeRouter:
        def call(self, role, messages, **overrides):
            from aleph.core.llm import LLMResponse, Usage

            return LLMResponse(
                text=json.dumps({"mixture": {"人間": 1.0}, "reasons": {"人間": "テスト"}},
                                 ensure_ascii=False),
                model="fake", provider="fake", usage=Usage(prompt_tokens=1, completion_tokens=1),
                cost_usd=0.0,
            )

    deps = RealDeps(
        work, FakeRouter(), config=type("C", (), {"secrets": {}, "policies": {}})(),
        index_dir=tmp_path / "atlas", search_fn=lambda *a, **k: [], poetics_dir=poetics_dir,
    )
    deps.choose_intent(work)

    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    version_records = [d for d in decisions if d["decision"].startswith("poetics_version:")]
    assert len(version_records) == 1
    assert version_records[0]["decision"] == "poetics_version:1"
