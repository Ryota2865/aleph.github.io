"""成果物庫（PLAN §2.2）— 1ディレクトリ = 1作品。全中間物をプレーンテキストで残す.

不変条件:
- DBやメモリ上にしかない状態を作らない。すべての決定・版・査読はファイルにある。
- decisions.jsonl の各行: {ts, layer, decision, reason, decided_by(model), refs}
- works/ 以下は公開リポジトリの深層アーカイブになる（PLAN §8 二層構造）。
  秘密情報を書き込まないこと（scrub_secrets 経由で書く）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from aleph.core.llm import scrub_secrets

# 正典のレイアウト（PLAN §2.2）
WORK_LAYOUT = (
    "seed.json",
    "intent.md",
    "niche/",
    "materials/",
    "compositions/",
    "drafts/",
    "reviews/",
    "decisions.jsonl",
    "calls.jsonl",
    "final/",
)

# decisions.jsonl の各行の必須フィールド（refs以外。ファイル冒頭の不変条件）
_REQUIRED_DECISION_FIELDS = ("ts", "layer", "decision", "reason", "decided_by")


class Work:
    """作品ディレクトリへの型付きアクセス。パス計算は純粋関数として実装済み."""

    def __init__(self, root: Path, work_id: str, secrets: Iterable[str] = ()) -> None:
        self.work_id = work_id
        self.dir = Path(root) / work_id
        self._secrets = tuple(secrets)

    # --- パス（実装済み・変更不可） -------------------------------------
    @property
    def seed(self) -> Path:
        return self.dir / "seed.json"

    @property
    def intent(self) -> Path:
        return self.dir / "intent.md"

    @property
    def niche(self) -> Path:
        return self.dir / "niche"

    @property
    def materials(self) -> Path:
        return self.dir / "materials"

    @property
    def compositions(self) -> Path:
        return self.dir / "compositions"

    @property
    def drafts(self) -> Path:
        return self.dir / "drafts"

    @property
    def reviews(self) -> Path:
        return self.dir / "reviews"

    @property
    def decisions(self) -> Path:
        return self.dir / "decisions.jsonl"

    @property
    def calls(self) -> Path:
        return self.dir / "calls.jsonl"

    @property
    def final(self) -> Path:
        return self.dir / "final"

    @property
    def checkpoint(self) -> Path:
        return self.dir / "checkpoint.json"

    def draft_path(self, version: int) -> Path:
        return self.drafts / f"v{version}.md"

    def review_path(self, version: int) -> Path:
        return self.reviews / f"v{version}.md"

    # --- 施工対象（M0） ---------------------------------------------------
    def create(self, seed: dict) -> None:
        """レイアウトを作成し seed.json を書く."""
        self.dir.mkdir(parents=True, exist_ok=True)
        for d in (self.niche, self.materials, self.compositions, self.drafts, self.reviews, self.final):
            d.mkdir(parents=True, exist_ok=True)
        seed_text = scrub_secrets(json.dumps(seed, ensure_ascii=False, indent=2), self._secrets)
        self.seed.write_text(seed_text, encoding="utf-8")
        for f in (self.decisions, self.calls):
            f.touch(exist_ok=True)

    def append_decision(self, record: dict) -> None:
        """decisions.jsonl への追記。スキーマ（ファイル冒頭の不変条件:
        {ts, layer, decision, reason, decided_by(model), refs}）の欠落は拒否する。
        refs のみ省略可（空リストを補う）。"""
        missing = [f for f in _REQUIRED_DECISION_FIELDS if f not in record]
        if missing:
            raise ValueError(f"decisions.jsonl record missing required fields: {missing}")
        payload = {**record}
        payload.setdefault("refs", [])
        self.decisions.parent.mkdir(parents=True, exist_ok=True)
        text = scrub_secrets(json.dumps(payload, ensure_ascii=False), self._secrets)
        existing = self.decisions.read_text(encoding="utf-8") if self.decisions.exists() else ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        tmp_path = self.dir / f".decisions.jsonl.{os.getpid()}.tmp"
        tmp_path.write_text(existing + text + "\n", encoding="utf-8")
        os.replace(tmp_path, self.decisions)

    def latest_draft_version(self) -> int:
        if not self.drafts.is_dir():
            return 0
        versions = []
        for p in self.drafts.glob("v*.md"):
            try:
                versions.append(int(p.stem[1:]))
            except ValueError:
                continue
        return max(versions, default=0)
