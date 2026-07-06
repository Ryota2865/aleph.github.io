"""Obsidian Vault リーダー（PLAN §4.5）— 読み取り専用の参照知識.

Vault側 AGENTS.md の規約をコードで強制する:
- Vault内への書き込みは一切禁止（wiki/ を含む）。
- grail.md は読み取りも禁止（人間所有の発見・孵化層）。
- raw/ と llm-grail.md は読み取りのみ。

このモジュールのガードは実装済みであり、Vaultへの全アクセスは
open_vault_file() を経由しなければならない（直接 open() するコードは監査で不合格）。
"""
from __future__ import annotations

from pathlib import Path

FORBIDDEN_NAMES = ("grail.md",)


class VaultAccessError(Exception):
    pass


def check_vault_access(target: Path, vault_root: Path, mode: str = "r") -> None:
    """Vault規約の検証。違反は VaultAccessError（実装済み・変更不可）."""
    target = Path(target).resolve()
    vault_root = Path(vault_root).resolve()
    try:
        rel = target.relative_to(vault_root)
    except ValueError:
        raise VaultAccessError(f"not inside vault: {target}")
    if any(m not in ("r", "b") for m in mode):
        raise VaultAccessError(f"vault is read-only: mode={mode!r} on {rel}")
    if rel.name in FORBIDDEN_NAMES and rel.parent == Path("."):
        raise VaultAccessError("grail.md is human-owned and must not be read (Vault AGENTS.md rule 4)")


def open_vault_file(target: Path, vault_root: Path, mode: str = "r"):
    check_vault_access(target, vault_root, mode)
    return open(target, mode, encoding="utf-8" if "b" not in mode else None)


class VaultReader:
    """wiki/index.md を起点に必要ページを素材カード化する軽量リーダー。施工: M1."""

    def __init__(self, vault_root: Path) -> None:
        self.root = Path(vault_root)

    def read_index(self) -> str:
        raise NotImplementedError("M1: 施工対象")

    def read_page(self, rel_path: str) -> str:
        raise NotImplementedError("M1: 施工対象")
