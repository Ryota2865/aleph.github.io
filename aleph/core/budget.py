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

import hashlib
import json
import math
import re
import time
import uuid
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping

import fcntl

LEDGERS = ("api", "harness", "local")
POOLS = ("player", "held_out", "closing")
_AMOUNT_EPSILON = 1e-9

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


class BudgetUnreconciled(RuntimeError):
    """A completed provider call has been recorded but cannot yet be reconciled."""


class ReservationConflict(ValueError):
    """An idempotency key was reused for a different reservation operation."""


class BatchLookupError(ValueError):
    """No batch (or multiple batches) matched the requested phase+role pair."""


@dataclass(frozen=True)
class BatchSpec:
    batch_id: str
    ledger: str
    charged_to: str
    pool: str
    role: str
    max_amount: float
    work_id: str | None = None
    expected_slots: tuple[str, ...] = ()
    phases: tuple[str, ...] = ()
    input_manifest_hash: str = ""
    semantic_retries: int = 0
    atomic_projection: bool = True
    protected_definition_version: str = "phase5-v1"

    def canonical(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "ledger": self.ledger,
            "charged_to": self.charged_to,
            "pool": self.pool,
            "role": self.role,
            "max_amount": float(self.max_amount),
            "work_id": self.work_id,
            "expected_slots": list(self.expected_slots),
            "phases": list(self.phases),
            "input_manifest_hash": self.input_manifest_hash,
            "semantic_retries": self.semantic_retries,
            "atomic_projection": self.atomic_projection,
            "protected_definition_version": self.protected_definition_version,
        }


@dataclass(frozen=True)
class BatchReservation:
    id: str
    command_id: str
    manifest_hash: str
    spec: Mapping[str, Any]
    allocations: Mapping[str, float]
    charged: float
    status: str
    period_key: str


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
        self._charge_events: list[dict] = []
        self._scope_limits: dict[str, tuple[str, float]] = {}
        self._pool_limits: dict[str, dict[str, float]] = {}
        self._reservations: dict[str, dict[str, Any]] = {}
        self._reservation_commands: dict[str, str] = {}
        self._unreconciled_charge_ids: set[str] = set()
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

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        if self.state_path is None:
            yield
            return
        lock_path = self.state_path.with_name(self.state_path.name + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if self.state_path.exists():
                self._load(reset=True)
            try:
                yield
                self._save()
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _roll_if_needed(self, name: str) -> None:
        ledger = self._ledgers[name]
        current = _period_key(ledger.period)
        if current != self._period_keys.get(name):
            ledger.spent = 0.0
            ledger.events.clear()
            for reservation in self._reservations.values():
                if (
                    reservation.get("status") == "active"
                    and reservation.get("spec", {}).get("ledger") == name
                ):
                    reservation["status"] = "expired"
            self._period_keys[name] = current

    def register_scope_limit(self, charged_to: str, *, ledger: str, limit: float) -> None:
        """Register an immutable sub-envelope such as one complete experiment cap."""
        if ledger not in LEDGERS or limit <= 0:
            raise ValueError("scope limit requires a known ledger and positive limit")
        with self._transaction():
            self._register_scope_limit_locked(charged_to, ledger=ledger, limit=limit)

    def _register_scope_limit_locked(
        self, charged_to: str, *, ledger: str, limit: float
    ) -> None:
        existing = self._scope_limits.get(charged_to)
        value = (ledger, float(limit))
        if existing is not None and existing != value:
            raise ValueError(f"scope limit is immutable: {charged_to}")
        self._scope_limits[charged_to] = value

    def register_pool_limits(
        self,
        charged_to: str,
        *,
        ledger: str,
        player: float,
        held_out: float,
        closing: float,
    ) -> None:
        """Fix pool amounts for a scope; the borrowing matrix remains code-owned."""
        limits = {"player": float(player), "held_out": float(held_out), "closing": float(closing)}
        if any(not math.isfinite(value) or value < 0 for value in limits.values()):
            raise ValueError("pool limits must be finite and non-negative")
        with self._transaction():
            self._register_pool_limits_locked(charged_to, ledger=ledger, limits=limits)

    def _register_pool_limits_locked(
        self, charged_to: str, *, ledger: str, limits: Mapping[str, float]
    ) -> None:
        normalized = {pool: float(limits[pool]) for pool in POOLS}
        scope = self._scope_limits.get(charged_to)
        if scope is None or scope[0] != ledger:
            raise ValueError(f"scope {charged_to} must first be registered for {ledger}")
        if sum(normalized.values()) > scope[1] + _AMOUNT_EPSILON:
            raise ValueError("pool limits exceed the registered scope limit")
        existing = self._pool_limits.get(charged_to)
        if existing is not None and existing != normalized:
            raise ValueError(f"pool limits are immutable: {charged_to}")
        self._pool_limits[charged_to] = normalized

    @staticmethod
    def _validate_amount(amount: float) -> float:
        value = float(amount)
        if not math.isfinite(value) or value < 0:
            raise ValueError("budget amount must be finite and non-negative")
        return value

    def _active_commitments(
        self,
        *,
        ledger: str | None = None,
        charged_to: str | None = None,
        work_id: str | None = None,
        exclude: str | None = None,
    ) -> float:
        total = 0.0
        for reservation_id, reservation in self._reservations.items():
            if reservation_id == exclude or reservation.get("status") != "active":
                continue
            spec = reservation["spec"]
            if ledger is not None and spec.get("ledger") != ledger:
                continue
            if charged_to is not None and spec.get("charged_to") != charged_to:
                continue
            if work_id is not None and spec.get("work_id") != work_id:
                continue
            total += max(0.0, float(spec["max_amount"]) - float(reservation.get("charged", 0.0)))
        return total

    def _assert_reconciled(self) -> None:
        if self._unreconciled_charge_ids:
            raise BudgetUnreconciled(
                "budget has unreconciled completed calls: "
                + ", ".join(sorted(self._unreconciled_charge_ids))
            )

    def precheck(
        self,
        ledger: str,
        amount: float,
        work_id: str | None = None,
        charged_to: str | None = None,
        reservation_id: str | None = None,
        role: str | None = None,
    ) -> None:
        """消費前の照会。超過が予見されれば BudgetExceeded を送出し、消費しない."""
        amount = self._validate_amount(amount)
        self._assert_reconciled()
        self._roll_if_needed(ledger)
        l = self._ledgers[ledger]
        if reservation_id is not None:
            reservation = self._reservations.get(reservation_id)
            if reservation is None or reservation.get("status") != "active":
                raise ValueError(f"reservation is not active: {reservation_id}")
            spec = reservation["spec"]
            if spec.get("ledger") != ledger:
                raise ValueError("reservation ledger does not match precheck")
            if role is not None and spec.get("role") != role:
                raise ValueError("reservation role does not match precheck")
            remaining = float(spec["max_amount"]) - float(reservation.get("charged", 0.0))
            if amount > remaining + 1e-12:
                raise BudgetExceeded(f"reservation:{reservation_id}", remaining, 0.0, amount)
            return
        committed = self._active_commitments(ledger=ledger)
        if l.spent + committed + amount > l.limit:
            raise BudgetExceeded(ledger, l.limit, l.spent + committed, amount)
        if ledger == "api" and work_id and self._work_limit is not None:
            spent = self._work_spent.get(work_id, 0.0)
            work_committed = self._active_commitments(ledger=ledger, work_id=work_id)
            if spent + work_committed + amount > self._work_limit:
                raise BudgetExceeded(
                    f"api:{work_id}", self._work_limit, spent + work_committed, amount
                )
        scope = self._scope_limits.get(charged_to or "")
        if scope is not None:
            scope_ledger, scope_limit = scope
            if scope_ledger != ledger:
                raise ValueError(f"scope {charged_to} is registered for {scope_ledger}, not {ledger}")
            spent = sum(
                float(event.get("amount", 0.0))
                for event in self._charge_events
                if event.get("ledger") == ledger
                and event.get("charged_to") == charged_to
            )
            scope_committed = self._active_commitments(ledger=ledger, charged_to=charged_to)
            if spent + scope_committed + amount > scope_limit:
                raise BudgetExceeded(
                    str(charged_to), scope_limit, spent + scope_committed, amount
                )

    def _pool_spent(self, charged_to: str, pool: str) -> float:
        return sum(
            float((event.get("pool_allocations") or {}).get(pool, 0.0))
            for event in self._charge_events
            if event.get("charged_to") == charged_to
        )

    def _pool_committed(self, charged_to: str, pool: str) -> float:
        return sum(
            float((reservation.get("remaining_allocations") or {}).get(pool, 0.0))
            for reservation in self._reservations.values()
            if reservation.get("status") == "active"
            and reservation.get("spec", {}).get("charged_to") == charged_to
        )

    def reserve_batch(self, spec: BatchSpec, *, command_id: str) -> BatchReservation:
        if not isinstance(spec, BatchSpec):
            raise TypeError("spec must be BatchSpec")
        if (
            not command_id
            or not spec.batch_id
            or not spec.role
            or not spec.input_manifest_hash
            or spec.ledger not in LEDGERS
        ):
            raise ValueError("reservation requires command, batch, role, and known ledger")
        if spec.pool not in POOLS:
            raise ValueError(f"unknown protected pool: {spec.pool}")
        amount = self._validate_amount(spec.max_amount)
        if amount <= 0 or spec.semantic_retries < 0 or not spec.atomic_projection:
            raise ValueError("reservation requires positive amount, retries >= 0, and atomic projection")
        canonical = spec.canonical()
        manifest_hash = _canonical_hash(canonical)
        with self._transaction():
            return self._reserve_batch_locked(
                spec,
                command_id=command_id,
                amount=amount,
                canonical=canonical,
                manifest_hash=manifest_hash,
            )

    def _reserve_batch_locked(
        self,
        spec: BatchSpec,
        *,
        command_id: str,
        amount: float,
        canonical: Mapping[str, Any],
        manifest_hash: str,
    ) -> BatchReservation:
        self._assert_reconciled()
        existing_id = self._reservation_commands.get(command_id)
        if existing_id is not None:
            existing = self._reservations[existing_id]
            if existing.get("manifest_hash") != manifest_hash:
                raise ReservationConflict(f"command_id reused with different manifest: {command_id}")
            return self._public_reservation(existing)
        scope = self._scope_limits.get(spec.charged_to)
        pools = self._pool_limits.get(spec.charged_to)
        if scope is None or scope[0] != spec.ledger or pools is None:
            raise ValueError("protected reservation requires registered scope and pool limits")
        self.precheck(
            spec.ledger,
            amount,
            work_id=spec.work_id,
            charged_to=spec.charged_to,
        )
        own_available = max(
            0.0,
            pools[spec.pool]
            - self._pool_spent(spec.charged_to, spec.pool)
            - self._pool_committed(spec.charged_to, spec.pool),
        )
        allocations: dict[str, float] = {spec.pool: min(amount, own_available)}
        shortage = amount - allocations[spec.pool]
        if shortage > 1e-12 and spec.pool == "held_out":
            player_available = max(
                0.0,
                pools["player"]
                - self._pool_spent(spec.charged_to, "player")
                - self._pool_committed(spec.charged_to, "player"),
            )
            borrowed = min(shortage, player_available)
            allocations["player"] = borrowed
            shortage -= borrowed
        if shortage > 1e-12:
            pool_spent = pools[spec.pool] - own_available
            raise BudgetExceeded(
                f"pool:{spec.charged_to}:{spec.pool}", pools[spec.pool], pool_spent, amount
            )
        reservation_id = str(uuid.uuid4())
        reservation = {
            "id": reservation_id,
            "command_id": command_id,
            "manifest_hash": manifest_hash,
            "spec": dict(canonical),
            "allocations": allocations,
            "remaining_allocations": dict(allocations),
            "charged": 0.0,
            "status": "active",
            "period_key": self._period_keys[spec.ledger],
            "settlement": None,
        }
        self._reservations[reservation_id] = reservation
        self._reservation_commands[command_id] = reservation_id
        return self._public_reservation(reservation)

    def admit_run_plan(self, plan: "RunBudgetPlan") -> dict[str, BatchReservation]:
        """Atomically register and reserve every batch in a normal-run plan."""
        if not isinstance(plan, RunBudgetPlan):
            raise TypeError("plan must be RunBudgetPlan")
        snapshot = None
        with self._transaction():
            snapshot = (
                deepcopy(self._scope_limits),
                deepcopy(self._pool_limits),
                deepcopy(self._reservations),
                deepcopy(self._reservation_commands),
            )
            try:
                self._register_scope_limit_locked(
                    plan.charged_to, ledger="api", limit=plan.cap_amount
                )
                self._register_pool_limits_locked(
                    plan.charged_to,
                    ledger="api",
                    limits=dict(plan.pool_limits),
                )
                admitted: dict[str, BatchReservation] = {}
                for spec in plan.batches:
                    canonical = spec.canonical()
                    admitted[spec.batch_id] = self._reserve_batch_locked(
                        spec,
                        command_id=f"{plan.charged_to}:reserve:{spec.batch_id}",
                        amount=self._validate_amount(spec.max_amount),
                        canonical=canonical,
                        manifest_hash=_canonical_hash(canonical),
                    )
                return admitted
            except Exception:
                (
                    self._scope_limits,
                    self._pool_limits,
                    self._reservations,
                    self._reservation_commands,
                ) = snapshot
                raise

    def load_run_plan_reservations(
        self, plan: "RunBudgetPlan"
    ) -> dict[str, BatchReservation]:
        """Rehydrate an admitted run without invoking admission or reconciliation gates."""
        if not isinstance(plan, RunBudgetPlan):
            raise TypeError("plan must be RunBudgetPlan")
        reservations: dict[str, BatchReservation] = {}
        for spec in plan.batches:
            command_id = f"{plan.charged_to}:reserve:{spec.batch_id}"
            reservation_id = self._reservation_commands.get(command_id)
            if reservation_id is None:
                raise ValueError(f"run batch was not admitted: {spec.batch_id}")
            reservation = self._reservations.get(reservation_id)
            expected_hash = _canonical_hash(spec.canonical())
            if reservation is None or reservation.get("manifest_hash") != expected_hash:
                raise ReservationConflict(
                    f"admitted run batch identity mismatch: {spec.batch_id}"
                )
            reservations[spec.batch_id] = self._public_reservation(reservation)
        return reservations

    @staticmethod
    def _public_reservation(reservation: Mapping[str, Any]) -> BatchReservation:
        return BatchReservation(
            id=str(reservation["id"]),
            command_id=str(reservation["command_id"]),
            manifest_hash=str(reservation["manifest_hash"]),
            spec=dict(reservation["spec"]),
            allocations=dict(reservation.get("allocations", {})),
            charged=float(reservation.get("charged", 0.0)),
            status=str(reservation["status"]),
            period_key=str(reservation["period_key"]),
        )

    def work_remaining(self, work_id: str) -> float | None:
        """作品別上限(usd_per_work)の残額。上限未宣言なら None."""
        if self._work_limit is None:
            return None
        return self._work_limit - self._work_spent.get(work_id, 0.0) - self._active_commitments(
            ledger="api", work_id=work_id
        )

    def scope_remaining(self, charged_to: str) -> float | None:
        """登録済みsub-envelopeの残量。未登録なら None.

        停止判断が provider precheck と同じ全phase包絡を参照するための
        read-only query であり、台帳やscope定義は変更しない。
        """
        scope = self._scope_limits.get(charged_to)
        if scope is None:
            return None
        ledger, limit = scope
        spent = sum(
            float(event.get("amount", 0.0))
            for event in self._charge_events
            if event.get("ledger") == ledger
            and event.get("charged_to") == charged_to
        )
        return limit - spent - self._active_commitments(ledger=ledger, charged_to=charged_to)

    def reservation_status(self, reservation_id: str) -> str | None:
        reservation = self._reservations.get(reservation_id)
        return str(reservation["status"]) if reservation is not None else None

    def reservation_remaining(self, reservation_id: str) -> float | None:
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            return None
        return max(
            0.0,
            float(reservation["spec"]["max_amount"]) - float(reservation.get("charged", 0.0)),
        )

    def reservation_settlement_command(self, reservation_id: str) -> str | None:
        reservation = self._reservations.get(reservation_id)
        settlement = reservation.get("settlement") if reservation is not None else None
        if not isinstance(settlement, Mapping):
            return None
        command_id = settlement.get("command_id")
        return str(command_id) if command_id is not None else None

    def charge(
        self,
        ledger: str,
        amount: float,
        meta: dict | None = None,
        work_id: str | None = None,
    ) -> dict:
        amount = self._validate_amount(amount)
        details = dict(meta or {})
        charge_id = str(details.pop("charge_id", "") or uuid.uuid4())
        with self._transaction():
            existing = next(
                (event for event in self._charge_events if event.get("charge_id") == charge_id), None
            )
            if existing is not None:
                return dict(existing)
            self._roll_if_needed(ledger)
            l = self._ledgers[ledger]
            reservation_id = details.get("reservation_id")
            pool_allocations: dict[str, float] = {}
            billing_status = "charged"
            if reservation_id:
                reservation = self._reservations.get(str(reservation_id))
                if reservation is None:
                    billing_status = "unreconciled"
                else:
                    spec = reservation["spec"]
                    if spec.get("ledger") != ledger:
                        raise ValueError("reservation ledger does not match charge")
                    if details.get("charged_to") not in (None, spec.get("charged_to")):
                        raise ValueError("reservation scope does not match charge")
                    if details.get("role") not in (None, spec.get("role")):
                        raise ValueError("reservation role does not match charge")
                    if work_id not in (None, spec.get("work_id")):
                        raise ValueError("reservation work does not match charge")
                    details["charged_to"] = spec.get("charged_to")
                    details["pool"] = spec.get("pool")
                    remaining = max(0.0, float(spec["max_amount"]) - float(reservation["charged"]))
                    covered = min(amount, remaining)
                    to_allocate = covered
                    remaining_allocations = reservation.get("remaining_allocations", {})
                    for pool in dict.fromkeys((spec.get("pool"), "player")):
                        if pool not in remaining_allocations or to_allocate <= 1e-12:
                            continue
                        used = min(float(remaining_allocations[pool]), to_allocate)
                        if used:
                            pool_allocations[str(pool)] = used
                            remaining_allocations[pool] = float(remaining_allocations[pool]) - used
                            to_allocate -= used
                    reservation["charged"] = float(reservation["charged"]) + amount
                    if amount > remaining + 1e-12 or reservation.get("status") != "active":
                        billing_status = "unreconciled"
                        reservation["status"] = "unreconciled"
            else:
                self.precheck(
                    ledger,
                    amount,
                    work_id=None,
                    charged_to=str(details.get("charged_to")) if details.get("charged_to") else None,
                )
            event = {
                "charge_id": charge_id,
                "ledger": ledger,
                "amount": amount,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "period_key": self._period_keys[ledger],
                "billing_status": billing_status,
                **details,
            }
            if pool_allocations:
                event["pool_allocations"] = pool_allocations
            l.spent += amount
            l.events.append(event)
            self._charge_events.append(event)
            if ledger == "api" and work_id:
                self._work_spent[work_id] = self._work_spent.get(work_id, 0.0) + amount
            if billing_status == "unreconciled":
                self._unreconciled_charge_ids.add(charge_id)
            return event

    def settle_batch(self, reservation_id: str, *, command_id: str) -> dict[str, Any]:
        if not command_id:
            raise ValueError("settlement command_id is required")
        with self._transaction():
            reservation = self._reservations.get(reservation_id)
            if reservation is None:
                raise ValueError(f"unknown reservation: {reservation_id}")
            settlement = reservation.get("settlement")
            if settlement is not None:
                if settlement.get("command_id") != command_id:
                    raise ReservationConflict("reservation already settled by another command")
                return dict(settlement)
            if reservation.get("status") == "unreconciled":
                raise BudgetUnreconciled(f"reservation is unreconciled: {reservation_id}")
            released = max(
                0.0,
                float(reservation["spec"]["max_amount"]) - float(reservation.get("charged", 0.0)),
            )
            settlement = {
                "reservation_id": reservation_id,
                "command_id": command_id,
                "charged": float(reservation.get("charged", 0.0)),
                "released": released,
                "status": "settled",
            }
            reservation["status"] = "settled"
            reservation["remaining_allocations"] = {
                pool: 0.0 for pool in reservation.get("remaining_allocations", {})
            }
            reservation["settlement"] = settlement
            return dict(settlement)

    def status(self) -> dict:
        """`aleph status` の表示元。3系統の残量を返す."""
        out: dict[str, dict] = {}
        for name in LEDGERS:
            self._roll_if_needed(name)
            l = self._ledgers[name]
            out[name] = {
                "spent": l.spent,
                "committed": self._active_commitments(ledger=name),
                "limit": l.limit,
                "period": l.period,
            }
        out["reservations"] = {
            "active_count": sum(
                reservation.get("status") == "active"
                for reservation in self._reservations.values()
            ),
            "unreconciled": bool(self._unreconciled_charge_ids),
        }
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
            "charge_events": self._charge_events,
            "scope_limits": {
                name: {"ledger": value[0], "limit": value[1]}
                for name, value in self._scope_limits.items()
            },
            "pool_limits": self._pool_limits,
            "reservations": self._reservations,
            "reservation_commands": self._reservation_commands,
            "unreconciled_charge_ids": sorted(self._unreconciled_charge_ids),
        }
        temporary = self.state_path.with_name(self.state_path.name + ".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(self.state_path)

    def _load(self, *, reset: bool = False) -> None:
        assert self.state_path is not None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if reset:
            for ledger in self._ledgers.values():
                ledger.spent = 0.0
                ledger.events.clear()
            self._work_spent.clear()
            self._charge_events.clear()
            self._scope_limits.clear()
            self._pool_limits.clear()
            self._reservations.clear()
            self._reservation_commands.clear()
            self._unreconciled_charge_ids.clear()
        for name, data in payload.get("ledgers", {}).items():
            if name in self._ledgers:
                self._ledgers[name].spent = data.get("spent", 0.0)
                self._period_keys[name] = data.get("period_key", self._period_keys[name])
        self._work_spent.update(payload.get("work_spent", {}))
        events = payload.get("charge_events", [])
        if isinstance(events, list):
            self._charge_events.extend(event for event in events if isinstance(event, dict))
            for event in self._charge_events:
                ledger = event.get("ledger")
                if ledger in self._ledgers and event.get("period_key") == self._period_keys[ledger]:
                    self._ledgers[ledger].events.append(event)
        scopes = payload.get("scope_limits", {})
        if isinstance(scopes, dict):
            for name, value in scopes.items():
                if isinstance(value, dict) and value.get("ledger") in LEDGERS:
                    self._scope_limits[str(name)] = (
                        str(value["ledger"]), float(value["limit"])
                    )
        pools = payload.get("pool_limits", {})
        if isinstance(pools, dict):
            for scope, values in pools.items():
                if isinstance(values, dict) and set(values) == set(POOLS):
                    self._pool_limits[str(scope)] = {
                        pool: float(values[pool]) for pool in POOLS
                    }
        reservations = payload.get("reservations", {})
        if isinstance(reservations, dict):
            self._reservations.update(
                (str(key), value) for key, value in reservations.items() if isinstance(value, dict)
            )
        commands = payload.get("reservation_commands", {})
        if isinstance(commands, dict):
            self._reservation_commands.update(
                (str(key), str(value)) for key, value in commands.items()
            )
        unreconciled = payload.get("unreconciled_charge_ids", [])
        if isinstance(unreconciled, list):
            self._unreconciled_charge_ids.update(str(value) for value in unreconciled)


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Phase 5 — RunBudgetPlan: strict manifest parsing
# ---------------------------------------------------------------------------

_VALID_PHASES = frozenset({"L1", "L2", "L3", "L4-L5", "L6", "L7"})
_MANIFEST_TOP_KEYS = frozenset({"version", "cap_amount", "pools", "batches"})
_BATCH_KEYS = frozenset(
    {
        "batch_id",
        "pool",
        "role",
        "max_amount",
        "phases",
        "expected_slots",
        "input_manifest_hash",
        "semantic_retries",
    }
)


@dataclass(frozen=True)
class RunBudgetPlan:
    """Parsed and validated protected-budget manifest for a single run."""

    charged_to: str
    cap_amount: float
    pool_limits: tuple[tuple[str, float], ...]
    batches: tuple[BatchSpec, ...]

    def batch_for(self, phase: str, role: str) -> BatchSpec:
        """Return the unique BatchSpec for *phase* + *role*, or raise."""
        matches = [b for b in self.batches if phase in b.phases and b.role == role]
        if not matches:
            raise BatchLookupError(
                f"no batch covers phase={phase!r} role={role!r}"
            )
        if len(matches) > 1:
            raise BatchLookupError(
                f"ambiguous: {len(matches)} batches cover phase={phase!r} role={role!r}"
            )
        return matches[0]

    @classmethod
    def from_manifest(
        cls, raw_manifest: Mapping[str, Any], *, work_id: str
    ) -> "RunBudgetPlan":
        """Validate an already-decoded seed JSON budget manifest (version 1)."""
        if not isinstance(raw_manifest, Mapping):
            raise ValueError("manifest must be a mapping at top level")
        if not isinstance(work_id, str) or not work_id.strip():
            raise ValueError("work_id must be a non-empty string")
        data = dict(raw_manifest)

        if any(not isinstance(key, str) for key in data):
            raise ValueError("manifest keys must be strings")

        # --- top-level key check ---
        unknown_top = set(data.keys()) - _MANIFEST_TOP_KEYS
        if unknown_top:
            raise ValueError(f"unknown manifest keys: {sorted(unknown_top)}")
        missing_top = _MANIFEST_TOP_KEYS - set(data.keys())
        if missing_top:
            raise ValueError(f"missing manifest keys: {sorted(missing_top)}")

        # --- version ---
        version = data["version"]
        if not isinstance(version, int) or isinstance(version, bool) or version != 1:
            raise ValueError(f"manifest version must be integer 1, got {version!r}")

        # --- cap_amount ---
        cap_amount = data["cap_amount"]
        if isinstance(cap_amount, bool) or not isinstance(cap_amount, (int, float)):
            raise ValueError(f"cap_amount must be a number, got {type(cap_amount).__name__}")
        cap_amount = float(cap_amount)
        if not math.isfinite(cap_amount) or cap_amount <= 0:
            raise ValueError(f"cap_amount must be finite and >0, got {cap_amount}")

        # --- pools ---
        pools_raw = data["pools"]
        if not isinstance(pools_raw, Mapping):
            raise ValueError("pools must be a mapping")
        if any(not isinstance(key, str) for key in pools_raw):
            raise ValueError("pool keys must be strings")
        pool_keys = set(pools_raw.keys())
        if pool_keys != set(POOLS):
            extra = pool_keys - set(POOLS)
            missing = set(POOLS) - pool_keys
            raise ValueError(
                f"pools must contain exactly {{player, held_out, closing}}; "
                f"extra={extra}, missing={missing}"
            )
        pool_values: dict[str, float] = {}
        for p in POOLS:
            v = pools_raw[p]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"pool {p} value must be a number, got {type(v).__name__}")
            fv = float(v)
            if not math.isfinite(fv) or fv < 0:
                raise ValueError(f"pool {p} must be finite and non-negative, got {fv}")
            pool_values[p] = fv
        if abs(sum(pool_values.values()) - cap_amount) > _AMOUNT_EPSILON:
            raise ValueError(
                f"pool values sum ({sum(pool_values.values())}) must equal "
                f"cap_amount ({cap_amount}) within 1e-9"
            )

        # --- batches ---
        batches_raw = data["batches"]
        if not isinstance(batches_raw, list) or len(batches_raw) == 0:
            raise ValueError("batches must be a non-empty list")

        seen_batch_ids: set[str] = set()
        phase_role_map: dict[tuple[str, str], str] = {}
        pool_batch_sums: dict[str, float] = {p: 0.0 for p in POOLS}
        has_closing_l7 = False
        batch_specs: list[BatchSpec] = []

        for idx, item in enumerate(batches_raw):
            prefix = f"batches[{idx}]"

            if not isinstance(item, Mapping):
                raise ValueError(f"{prefix}: must be a mapping")
            if any(not isinstance(key, str) for key in item):
                raise ValueError(f"{prefix}: keys must be strings")
            unknown_batch = set(item.keys()) - _BATCH_KEYS
            if unknown_batch:
                raise ValueError(f"{prefix}: unknown keys: {sorted(unknown_batch)}")
            missing_batch = _BATCH_KEYS - set(item.keys())
            if missing_batch:
                raise ValueError(f"{prefix}: missing keys: {sorted(missing_batch)}")

            # batch_id
            batch_id = item["batch_id"]
            if not isinstance(batch_id, str) or not batch_id.strip():
                raise ValueError(f"{prefix}: batch_id must be a non-empty string")
            if batch_id in seen_batch_ids:
                raise ValueError(f"{prefix}: duplicate batch_id {batch_id!r}")
            seen_batch_ids.add(batch_id)

            # pool
            pool = item["pool"]
            if not isinstance(pool, str) or pool not in POOLS:
                raise ValueError(f"{prefix}: pool must be one of {POOLS}, got {pool!r}")

            # role
            role = item["role"]
            if not isinstance(role, str) or not role.strip():
                raise ValueError(f"{prefix}: role must be a non-empty string")

            # max_amount
            max_amount = item["max_amount"]
            if isinstance(max_amount, bool) or not isinstance(max_amount, (int, float)):
                raise ValueError(
                    f"{prefix}: max_amount must be a number, got {type(max_amount).__name__}"
                )
            max_amount = float(max_amount)
            if not math.isfinite(max_amount) or max_amount <= 0:
                raise ValueError(f"{prefix}: max_amount must be finite and >0, got {max_amount}")

            # phases
            phases = item["phases"]
            if not isinstance(phases, list) or len(phases) == 0:
                raise ValueError(f"{prefix}: phases must be a non-empty list")
            if len(phases) != len(set(phases)):
                raise ValueError(f"{prefix}: phases must be unique")
            for ph in phases:
                if not isinstance(ph, str) or ph not in _VALID_PHASES:
                    raise ValueError(
                        f"{prefix}: phase {ph!r} not in allowed {_VALID_PHASES}"
                    )

            # expected_slots
            expected_slots = item["expected_slots"]
            if not isinstance(expected_slots, list) or len(expected_slots) == 0:
                raise ValueError(f"{prefix}: expected_slots must be a non-empty list")
            if len(expected_slots) != len(set(expected_slots)):
                raise ValueError(f"{prefix}: expected_slots must be unique")
            for slot in expected_slots:
                if not isinstance(slot, str) or not slot:
                    raise ValueError(f"{prefix}: each expected_slot must be a non-empty string")

            # input_manifest_hash
            imh = item["input_manifest_hash"]
            if not isinstance(imh, str) or not re.fullmatch(r"[0-9a-f]{64}", imh):
                raise ValueError(
                    f"{prefix}: input_manifest_hash must be exactly 64 lowercase hex chars"
                )

            # semantic_retries
            sr = item["semantic_retries"]
            if isinstance(sr, bool) or not isinstance(sr, int):
                raise ValueError(
                    f"{prefix}: semantic_retries must be an integer >=0, "
                    f"got {type(sr).__name__}"
                )
            if sr < 0:
                raise ValueError(f"{prefix}: semantic_retries must be >=0, got {sr}")

            # Pool overflow check
            pool_batch_sums[pool] += max_amount

            # Phase+role uniqueness
            for ph in phases:
                key = (ph, role)
                if key in phase_role_map:
                    raise ValueError(
                        f"{prefix}: phase={ph!r} + role={role!r} already covered by "
                        f"batch {phase_role_map[key]!r}"
                    )
                phase_role_map[key] = batch_id

            # Closing L7 check
            if pool == "closing" and "L7" in phases:
                has_closing_l7 = True

            charged_to = f"run:{work_id}"
            spec = BatchSpec(
                batch_id=batch_id,
                ledger="api",
                charged_to=charged_to,
                pool=pool,
                role=role,
                max_amount=max_amount,
                work_id=work_id,
                expected_slots=tuple(expected_slots),
                phases=tuple(phases),
                input_manifest_hash=imh,
                semantic_retries=sr,
                atomic_projection=True,
                protected_definition_version="phase5-v1",
            )
            batch_specs.append(spec)

        # Pool overflow final check
        for pool in POOLS:
            if pool_batch_sums[pool] > pool_values[pool] + 1e-9:
                raise ValueError(
                    f"batch max_amounts for pool {pool} sum to "
                    f"{pool_batch_sums[pool]}, exceeding pool limit {pool_values[pool]}"
                )

        # Closing L7 requirement
        if not has_closing_l7:
            raise ValueError(
                "manifest must include at least one closing-pool batch covering phase L7"
            )

        return cls(
            charged_to=charged_to,
            cap_amount=cap_amount,
            pool_limits=tuple((p, pool_values[p]) for p in POOLS),
            batches=tuple(batch_specs),
        )
