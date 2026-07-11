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

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

LEDGERS = ("api", "harness", "local")

# 各台帳の上限をどのbudgets.yamlキーから読むか、およびリセット周期。
_LEDGER_LIMIT_KEY = {
    "api": ("usd_per_month", "month"),
    "harness": ("calls_per_day", "day"),
    "local": ("gpu_hours_per_day", "day"),
}


def _period_key(period: str) -> str:
    now = time.gmtime()
    if period == "day":
        return time.strftime("%Y-%m-%d", now)
    if period == "month":
        return time.strftime("%Y-%m", now)
    return "always"


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

    def __init__(self, config, state_path: Path | None = None) -> None:
        """state_path を指定すると台帳をJSONとして永続化・復元する（PLAN §2.1）.

        未指定（既定）ではプロセス内メモリのみの台帳になる。CLI本体からは
        `state/budget.json` 等、works/ 外のシステム領域を渡すこと。
        """
        self.config = config
        self.state_path = Path(state_path) if state_path else None
        self._ledgers: dict[str, Ledger] = {}
        self._period_keys: dict[str, str] = {}
        for name in LEDGERS:
            key, period = _LEDGER_LIMIT_KEY[name]
            limit = config.budgets[name][key]
            self._ledgers[name] = Ledger(name=name, limit=limit, period=period)
            self._period_keys[name] = _period_key(period)
        # 作品ごとの上限（PLAN §2.1: 作品ごと・日ごとの上限）。api のみ宣言されている。
        self._work_limit = config.budgets.get("api", {}).get("usd_per_work")
        self._work_spent: dict[str, float] = {}
        if self.state_path and self.state_path.exists():
            self._load()

    def _roll_if_needed(self, name: str) -> None:
        ledger = self._ledgers[name]
        current = _period_key(ledger.period)
        if current != self._period_keys.get(name):
            ledger.spent = 0.0
            ledger.events.clear()
            self._period_keys[name] = current

    def precheck(self, ledger: str, amount: float, work_id: str | None = None) -> None:
        """消費前の照会。超過が予見されれば BudgetExceeded を送出し、消費しない."""
        self._roll_if_needed(ledger)
        l = self._ledgers[ledger]
        if l.spent + amount > l.limit:
            raise BudgetExceeded(ledger, l.limit, l.spent, amount)
        if ledger == "api" and work_id and self._work_limit is not None:
            spent = self._work_spent.get(work_id, 0.0)
            if spent + amount > self._work_limit:
                raise BudgetExceeded(f"api:{work_id}", self._work_limit, spent, amount)

    def work_remaining(self, work_id: str) -> float | None:
        """作品別上限(usd_per_work)の残額。上限未宣言なら None."""
        if self._work_limit is None:
            return None
        return self._work_limit - self._work_spent.get(work_id, 0.0)

    def charge(self, ledger: str, amount: float, meta: dict | None = None, work_id: str | None = None) -> None:
        self._roll_if_needed(ledger)
        l = self._ledgers[ledger]
        l.spent += amount
        l.events.append({"ts": _period_key("day"), "amount": amount, "meta": meta or {}})
        if ledger == "api" and work_id:
            self._work_spent[work_id] = self._work_spent.get(work_id, 0.0) + amount
        if self.state_path:
            self._save()

    def status(self) -> dict:
        """`aleph status` の表示元。3系統の残量を返す."""
        out: dict[str, dict] = {}
        for name in LEDGERS:
            self._roll_if_needed(name)
            l = self._ledgers[name]
            out[name] = {"spent": l.spent, "limit": l.limit, "period": l.period}
        return out

    def _save(self) -> None:
        assert self.state_path is not None
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ledgers": {
                name: {"spent": l.spent, "period_key": self._period_keys[name]}
                for name, l in self._ledgers.items()
            },
            "work_spent": self._work_spent,  # 作品ごとの上限（Codex監査 finding 4）
        }
        self.state_path.write_text(json.dumps(payload), encoding="utf-8")

    def _load(self) -> None:
        assert self.state_path is not None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for name, data in payload.get("ledgers", {}).items():
            if name in self._ledgers:
                self._ledgers[name].spent = data.get("spent", 0.0)
                self._period_keys[name] = data.get("period_key", self._period_keys[name])
        self._work_spent.update(payload.get("work_spent", {}))
