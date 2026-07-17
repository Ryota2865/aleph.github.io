"""配線棚卸し契約（PLAN_CHANGELOG 0.7.19 第三部9）.

「作成済み・未接続」はこのリポジトリで最も再現性の高い失敗様式である
（reflect()/fixation_check・annotate_failure・perplexity実測・form_fidelityゲート・
vault.py が、いずれも「関数は緑、実ランの経路は不通」の期間を持った。
reports/CLAUDE_REPO_INSIGHTS_20260717.md §2）。契約テストは関数を検証するが
配線を検証しない、という構造的盲点を、本ファイルが機械的に塞ぐ:

1. pipeline が getattr で呼ぶ全ての任意フックを RealDeps が実装していること。
2. 意図的な未配線は、理由と**失効日**つきの許可リストに載っていること。
   失効日を過ぎたら本テストは落ちる——配線するか、理由を書き直して延長するかを
   強制する（Fable5審査: 失効日のない許可リストは次の「未接続の墓場」になる）。
3. 許可リストの項目が実際には配線済みになったら、項目の削除を強制する
   （リストの腐敗防止）。

実行: pytest -m m6
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.m6

_ROOT = Path(__file__).resolve().parents[1]

# 意図的にRealDeps未実装のままにする任意フック。キー=フック名。
# 各項目に reason と expires（YYYY-MM-DD）が必須。失効日を過ぎると本テストが落ちる。
ALLOWED_UNWIRED_HOOKS: dict[str, dict] = {}

# 「モジュールは実装済みだが、実行経路のどこからも import されていない」ことを
# 意図的に許容するコンポーネント。値の unwired が真である限り、実際に未配線で
# あることも検査する（配線されたら項目を消すこと）。
ALLOWED_UNWIRED_COMPONENTS: dict[str, dict] = {
    "aleph.explore.vault": {
        "reason": (
            "PLAN §4.5 の参照知識リーダー。作品が実際にWiki知識を要するまで"
            "投機的な配線をしない（オーナー方針 2026-07-17: 変更は観測された"
            "失敗への応答のみ。想定される初配線は MATERIA 段での素材カード化）"
        ),
        "expires": "2026-09-30",
    },
}


def _pipeline_optional_hooks() -> set[str]:
    source = (_ROOT / "aleph" / "pipeline.py").read_text(encoding="utf-8")
    return set(re.findall(r'getattr\(\s*deps\s*,\s*"(\w+)"', source))


def _real_deps_instance():
    from aleph.pipeline import RealDeps

    work = SimpleNamespace(work_id="wtest")
    return RealDeps(
        work,
        router=None,
        config=SimpleNamespace(),
        index_dir=_ROOT / "state" / "atlas",
        search_fn=None,
    )


def _module_is_imported_outside_itself(module: str) -> bool:
    short = module.rsplit(".", 1)[-1]
    own_file = Path(*module.split(".")).with_suffix(".py")
    patterns = (f"from {module}", f"import {module}", f"from aleph.explore import {short}")
    for base in ("aleph", "scripts"):
        for path in (_ROOT / base).rglob("*.py"):
            if path.relative_to(_ROOT) == own_file:
                continue
            text = path.read_text(encoding="utf-8")
            if any(p in text for p in patterns):
                return True
    return False


def test_every_optional_pipeline_hook_is_wired_or_allowlisted():
    hooks = _pipeline_optional_hooks()
    assert hooks, "pipeline.py から getattr(deps, ...) フックを1件も検出できなかった（抽出正規表現の退行を疑え）"
    deps = _real_deps_instance()
    missing = {h for h in hooks if not hasattr(deps, h)} - set(ALLOWED_UNWIRED_HOOKS)
    assert not missing, (
        f"RealDeps が未実装の任意フック: {sorted(missing)}。"
        "配線するか、理由と失効日つきで ALLOWED_UNWIRED_HOOKS に載せること。"
    )


def test_allowlisted_hooks_are_actually_missing_and_not_expired():
    deps = _real_deps_instance()
    today = date.today()
    for hook, entry in ALLOWED_UNWIRED_HOOKS.items():
        assert entry.get("reason"), f"{hook}: reason が空の許可は無効"
        expires = date.fromisoformat(entry["expires"])
        assert today <= expires, (
            f"{hook}: 許可が {expires} に失効した。配線するか、理由を更新して延長すること。"
        )
        assert not hasattr(deps, hook), (
            f"{hook}: 既に配線済み。許可リストから項目を削除すること（リストの腐敗防止）。"
        )


def test_allowlisted_components_are_actually_unwired_and_not_expired():
    today = date.today()
    for module, entry in ALLOWED_UNWIRED_COMPONENTS.items():
        assert entry.get("reason"), f"{module}: reason が空の許可は無効"
        expires = date.fromisoformat(entry["expires"])
        assert today <= expires, (
            f"{module}: 許可が {expires} に失効した。配線するか、理由を更新して延長すること。"
        )
        assert not _module_is_imported_outside_itself(module), (
            f"{module}: 既にどこかから import されている。許可リストから項目を削除すること。"
        )
