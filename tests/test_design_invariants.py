"""設計不変条件テスト — 現時点で緑。以後も緑でなければならない.

これらはPLANの決定をコードとして固定したもの。赤にする変更は設計変更であり、
PLAN_CHANGELOG への記録と設計者の審査が必要（PLAN §12）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from aleph.core.config import REQUIRED_ROLES, ConfigError, load_config
from aleph.core.llm import scrub_secrets, sha256_text
from aleph.core.loop import ALLOWED_TRANSITIONS, TERMINAL_STATES, State, validate_transition
from aleph.explore.vault import VaultAccessError, check_vault_access

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- 設定
def test_config_loads_and_required_roles_exist():
    cfg = load_config(ROOT)
    for role in REQUIRED_ROLES:
        assert role in cfg.models["roles"]


def test_no_hardcoded_model_names_outside_config():
    """不変条件（PLAN §2.1）: コードはモデル名を直接書かない。役割名のみ."""
    cfg = load_config(ROOT)
    names: set[str] = set()
    roles = cfg.models["roles"]
    for decl in roles.values():
        for d in decl if isinstance(decl, list) else [decl]:
            if "model" in d:
                names.add(d["model"])
    offenders = []
    for py in (ROOT / "aleph").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for name in names:
            if name in text:
                offenders.append((py.name, name))
    assert not offenders, f"モデル名がコードに直書きされている: {offenders}"


def test_budget_declares_owner_decisions():
    cfg = load_config(ROOT)
    assert cfg.budgets["api"]["usd_per_month"] == 10.0  # PLAN §14-3
    assert cfg.budgets["publish"]["max_per_month"] == 4  # PLAN §14.3-7


def test_policies_declare_critical_decisions():
    cfg = load_config(ROOT)
    c = cfg.policies["critique"]
    assert c["score_is_information_not_objective"] is True  # PLAN §7.1 Goodhart回避
    assert c["external_anchor"] == "on_collaboration_only"  # PLAN §14.3-6
    assert cfg.policies["poetics"]["seed_from_human"] is False  # PLAN §14.3-10
    assert cfg.policies["vault"]["readonly"] is True  # PLAN §4.5
    assert cfg.policies["publication"]["signature"] == "model-credits"  # PLAN §14.3-9


# ---------------------------------------------------------------- 状態機械
def test_finish_is_not_publish():
    """完成≠公開（PLAN §7.3d）: FINISHからSHELVE/DISCARDにも行ける."""
    assert ALLOWED_TRANSITIONS[State.FINISH] == {State.PUBLISH, State.SHELVE, State.DISCARD}


def test_opportunistic_edges_exist():
    """機会的エッジ（PLAN §2.4）: 執筆・批評から探索・質料へ再入できる."""
    assert State.EXPLORE in ALLOWED_TRANSITIONS[State.DRAFT]
    assert State.MATERIA in ALLOWED_TRANSITIONS[State.DRAFT]
    assert State.EXPLORE in ALLOWED_TRANSITIONS[State.CRITIQUE]


def test_revise_can_go_back_to_composition():
    """改稿は構成に遡れる（PLAN §7.2）."""
    assert State.COMPOSE in ALLOWED_TRANSITIONS[State.REVISE]


def test_terminal_states_have_no_exit():
    for s in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[s] == frozenset()


def test_invalid_transition_rejected():
    assert not validate_transition(State.SEEDED, State.PUBLISH)


# ---------------------------------------------------------------- Vault規約
def test_vault_write_forbidden(tmp_path):
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    with pytest.raises(VaultAccessError):
        check_vault_access(vault / "wiki" / "index.md", vault, mode="w")


def test_grail_read_forbidden(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(VaultAccessError):
        check_vault_access(vault / "grail.md", vault, mode="r")


def test_llm_grail_read_allowed(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    check_vault_access(vault / "llm-grail.md", vault, mode="r")  # 例外が出ないこと


def test_outside_vault_rejected(tmp_path):
    with pytest.raises(VaultAccessError):
        check_vault_access(tmp_path / "elsewhere.md", tmp_path / "vault", mode="r")


# ---------------------------------------------------------------- 秘密情報
def test_scrub_secrets():
    secret = "BSA_example_secret_0123456789"
    out = scrub_secrets(f"key={secret} ok", [secret])
    assert secret not in out and "[REDACTED]" in out


def test_scrub_ignores_short_values():
    """短い値（誤爆リスク）は置換しない."""
    assert scrub_secrets("a=1", ["1"]) == "a=1"


def test_no_env_secrets_in_tracked_files():
    """不変条件（PLAN §14.2）: .env の秘密値がコミット対象ファイルに現れない."""
    from aleph.core.config import load_env

    secrets = [v for v in load_env(ROOT / ".env").values() if len(v) >= 8]
    if not secrets:
        pytest.skip("no secrets in .env")
    tracked = (
        list(ROOT.glob("*.md"))
        + list(ROOT.glob("*.toml"))
        + list((ROOT / "config").glob("*.yaml"))
        + list((ROOT / "aleph").rglob("*.py"))
        + list((ROOT / "tests").rglob("*.py"))
    )
    offenders = []
    for f in tracked:
        text = f.read_text(encoding="utf-8", errors="replace")
        for s in secrets:
            if s in text:
                offenders.append(str(f.relative_to(ROOT)))
    assert not offenders, f"秘密値が平文で含まれる: {offenders}"


def test_sha256_deterministic():
    assert sha256_text("aleph") == sha256_text("aleph")
    assert len(sha256_text("aleph")) == 64
