"""設定と秘密情報の読み込み（PLAN §2.1・§14.2）— 実装済み.

- config/*.yaml を読み、役割宣言を検証する。
- .env を読み、秘密辞書を作る。秘密は Config.secrets にのみ存在し、
  repr にも str にも出ない。ログ書き出しは scrub_secrets（core.llm）を通す。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REQUIRED_ROLES = (
    "author_primary",
    "critic_jury",
    "reader_model",
    "scout",
    "embedder",
)

CONFIG_FILES = ("models.yaml", "budgets.yaml", "policies.yaml", "publish.yaml")


class ConfigError(Exception):
    pass


@dataclass
class Config:
    root: Path
    models: dict
    budgets: dict
    policies: dict
    publish: dict
    secrets: dict = field(default_factory=dict, repr=False)

    def __str__(self) -> str:  # 秘密の漏出防止
        return f"Config(root={self.root}, roles={sorted(self.models.get('roles', {}))})"

    __repr__ = __str__


def load_env(path: Path) -> dict:
    """KEY=VALUE 形式の .env を読む（依存なしの最小実装）."""
    secrets: dict[str, str] = {}
    if not path.exists():
        return secrets
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        secrets[key.strip()] = value.strip().strip("'\"")
    return secrets


def load_config(root: Path) -> Config:
    root = Path(root)
    docs: dict[str, dict] = {}
    for name in CONFIG_FILES:
        p = root / "config" / name
        if not p.exists():
            raise ConfigError(f"missing config file: {p}")
        with open(p, encoding="utf-8") as f:
            docs[name] = yaml.safe_load(f) or {}

    models = docs["models.yaml"]
    roles = models.get("roles", {})
    for role in REQUIRED_ROLES:
        if role not in roles:
            raise ConfigError(f"required role missing in models.yaml: {role}")

    providers = models.get("providers", {})
    for role, decl in roles.items():
        decls = decl if isinstance(decl, list) else [decl]
        for d in decls:
            prov = d.get("provider")
            if prov not in providers and prov != "local":
                raise ConfigError(f"role {role}: unknown provider {prov!r}")

    return Config(
        root=root,
        models=models,
        budgets=docs["budgets.yaml"],
        policies=docs["policies.yaml"],
        publish=docs["publish.yaml"],
        secrets=load_env(root / ".env"),
    )
