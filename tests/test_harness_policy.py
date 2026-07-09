"""harness既定オフガードのテスト（PLAN §15-1 / PLAN_CHANGELOG 0.7）.

Codexクロス監査（reports/CODEX_AUDIT_20260708_094819.md finding 2）と、それを受けた
サブエージェントのWeb一次情報調査（Anthropic Consumer ToS・Claude Code公式ドキュメント・
OpenAI Codex CLI公式ドキュメント）を踏まえ、harness（claude-code / codex の非対話CLI
自動実行）は「人間が規約を確認し明示的に有効化するまで既定で拒否する」運用に倒した。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aleph.core.config import load_config
from aleph.core.llm import RouterError, build_provider

pytestmark = pytest.mark.m0

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg():
    return load_config(ROOT)


def test_harness_flags_match_design_decisions(cfg):
    """PLAN_CHANGELOG 0.7.4: オーナーの明示的許可（2026-07-09）により claude-code のみ有効。
    **codex は公開リポジトリである限り false を維持**（0.7.1の条件。これは不変条件）."""
    assert cfg.policies["harness"]["enabled"] is True
    assert cfg.policies["harness"]["cli_tos_ack"]["claude-code"] is True
    assert cfg.policies["harness"]["cli_tos_ack"]["codex"] is False


def test_harness_provider_rejected_when_disabled(cfg):
    """無効化時の拒否メカニズム自体は設定値と独立に維持される（PLAN_CHANGELOG 0.7）."""
    cfg.policies["harness"]["enabled"] = False
    with pytest.raises(RouterError):
        build_provider("harness", {"provider": "harness", "cli": "claude-code"}, cfg)


def test_harness_provider_rejected_without_per_cli_ack(cfg):
    cfg.policies["harness"]["enabled"] = True  # 全体は有効化したが、cli個別のackがまだ無い
    with pytest.raises(RouterError):
        build_provider("harness", {"provider": "harness", "cli": "codex"}, cfg)


def test_harness_provider_allowed_when_explicitly_enabled(cfg):
    cfg.policies["harness"]["enabled"] = True
    cfg.policies["harness"]["cli_tos_ack"]["claude-code"] = True
    provider = build_provider("harness", {"provider": "harness", "cli": "claude-code"}, cfg)
    assert provider.name == "harness"


def test_no_harness_credentials_tracked_in_repo():
    """OpenAI公式ガイドの警告（公開リポジトリへの認証情報混入を避けよ）への直接対応."""
    patterns = ("**/.codex/auth.json", "**/.claude/**/credentials*.json", "**/.claude/**/*.credentials.json")
    offenders = [str(p.relative_to(ROOT)) for pat in patterns for p in ROOT.glob(pat)]
    assert not offenders, f"harness認証情報らしきファイルがリポジトリ配下にある: {offenders}"
