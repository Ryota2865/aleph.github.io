"""詩学第1版リフレクション（0.7.19-2/-13）の回帰テスト.

reflect() の extra_inputs 経路: 初回改訂に限り DECLARATION_2024.md を入力として
与える配線の契約。恒久注入ではないこと（未指定時はプロンプトに現れないこと）を固定する。
"""
from __future__ import annotations

import pytest

from aleph.meta.poetics import reflect

pytestmark = pytest.mark.m5


class _FakeWork:
    def __init__(self, tmp_path):
        self.dir = tmp_path / "works" / "wX"
        self.dir.mkdir(parents=True)
        (self.dir / "intent.md").write_text("志向", encoding="utf-8")


def test_reflect_passes_extra_inputs_to_both_prompts(tmp_path):
    poetics_dir = tmp_path / "poetics"
    poetics_dir.mkdir()
    (poetics_dir / "poetics.md").write_text("# 詩学第0版", encoding="utf-8")

    prompts: dict[str, str] = {}

    def author(prompt: str) -> str:
        prompts["author"] = prompt
        return '{"revised": "# 詩学第1版", "diff_reason": "宣言に応答した"}'

    def adversary(prompt: str) -> str:
        prompts["adversary"] = prompt
        return '{"rebutted": false, "rationale": "整合する"}'

    result = reflect(
        poetics_dir,
        _FakeWork(tmp_path),
        author,
        adversary,
        extra_inputs={"2024年の宣言": "確かに、AIは人間とは異なる知覚を持つ。"},
    )

    assert result["applied"] is True
    for role in ("author", "adversary"):
        assert "追加入力文書" in prompts[role]
        assert "2024年の宣言" in prompts[role]
        assert "確かに、AIは人間とは異なる知覚を持つ。" in prompts[role]
    assert (poetics_dir / "poetics.md").read_text(encoding="utf-8") == "# 詩学第1版"
    assert (poetics_dir / "history.jsonl").exists()


def test_reflect_without_extra_inputs_keeps_prompts_clean(tmp_path):
    poetics_dir = tmp_path / "poetics"
    poetics_dir.mkdir()
    (poetics_dir / "poetics.md").write_text("# 詩学第0版", encoding="utf-8")

    prompts: dict[str, str] = {}

    def author(prompt: str) -> str:
        prompts["author"] = prompt
        return '{"revised": "# 詩学第0版", "diff_reason": "変更なし"}'

    def adversary(prompt: str) -> str:
        prompts["adversary"] = prompt
        return '{"rebutted": true, "rationale": "改訂の根拠がない"}'

    result = reflect(poetics_dir, _FakeWork(tmp_path), author, adversary)

    assert result["applied"] is False
    for role in ("author", "adversary"):
        assert "追加入力文書" not in prompts[role]
