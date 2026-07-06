"""予算管理（PLAN §2.1・§11・§14.1）— 3系統を別々に計上する.

- "api":     USD。上限は config/budgets.yaml（$10/月、オーナー決定 §14-3）
- "harness": 呼び出し回数/日。控えめ運用が規約適合の作業前提（PLAN §15-1）
- "local":   GPU時間。無料だが有限

不変条件:
- 超過が予見される消費は実行前に BudgetExceeded を送出する（事前計上）。
- 超過イベントはL7へ渡り、擱筆判断を強制起動する（PLAN §7.3）。
- 消費記録は works/<id>/calls.jsonl と集計台帳の両方から復元可能であること。
"""
from __future__ import annotations

from dataclasses import dataclass, field

LEDGERS = ("api", "harness", "local")


class BudgetExceeded(Exception):
    """予算超過。呼び出しは実行されていないことを保証する."""

    def __init__(self, ledger: str, limit: float, spent: float, requested: float) -> None:
        self.ledger = ledger
        self.limit = limit
        self.spent = spent
        self.requested = requested
        super().__init__(
            f"budget exceeded: ledger={ledger} limit={limit} spent={spent} requested={requested}"
        )


@dataclass
class Ledger:
    name: str
    limit: float
    period: str  # "month" | "day" | "work"
    spent: float = 0.0
    events: list[dict] = field(default_factory=list)


class Budget:
    """施工: M0（受入テスト: tests/test_m0_acceptance.py::test_budget_exceeded_raises）.

    台帳の永続化は works/ 外のシステム領域（例: state/budget.jsonl）に行い、
    作品別の内訳は calls.jsonl から導出する。
    """

    def __init__(self, config) -> None:
        self.config = config

    def precheck(self, ledger: str, amount: float) -> None:
        """消費前の照会。超過が予見されれば BudgetExceeded を送出し、消費しない."""
        raise NotImplementedError("M0: 施工対象")

    def charge(self, ledger: str, amount: float, meta: dict | None = None) -> None:
        raise NotImplementedError("M0: 施工対象")

    def status(self) -> dict:
        """`aleph status` の表示元。3系統の残量を返す."""
        raise NotImplementedError("M0: 施工対象")
