"""Authoritative resolution of experiment constraints and amendments."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class ConstraintError(ValueError):
    pass


@dataclass(frozen=True)
class Constraint:
    id: str
    text: str
    source: str
    scope: tuple[str, ...]
    priority: int


@dataclass(frozen=True)
class Amendment:
    id: str
    action: str
    target: str | None
    text: str | None
    source: str
    scope: tuple[str, ...]
    priority: int
    expires_at: str | None
    order: int
    applied: bool


@dataclass(frozen=True)
class ConstraintResolution:
    base: tuple[Constraint, ...]
    amendments: tuple[Amendment, ...]
    effective: tuple[Constraint, ...]
    revoked: tuple[str, ...]


def _scope(value: Any, *, label: str) -> tuple[str, ...]:
    allowed = {"L4", "L5", "L6", "L7"}
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item in allowed for item in value)
    ):
        raise ConstraintError(f"{label}.scope must be a non-empty subset of L4-L7")
    if len(value) != len(set(value)):
        raise ConstraintError(f"{label}.scope contains duplicates")
    return tuple(value)


def _not_expired(value: str | None, at: datetime) -> bool:
    if value is None:
        return True
    try:
        expires = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConstraintError(f"invalid amendment expiry: {value}") from exc
    if expires.tzinfo is None:
        raise ConstraintError("amendment expiry must include a timezone")
    return at < expires


def resolve_constraints(
    experiment: dict[str, Any] | None, *, at: datetime | None = None
) -> ConstraintResolution:
    manifest = experiment or {}
    now = at or datetime.now(timezone.utc)
    constraints: list[Constraint] = []
    raw_constraints = manifest.get("constraints", [])
    if raw_constraints and not isinstance(raw_constraints, list):
        raise ConstraintError("experiment.constraints must be a list")
    for index, raw in enumerate(raw_constraints):
        if not isinstance(raw, dict):
            raise ConstraintError(f"constraint {index} must be an object")
        try:
            constraint = Constraint(
                id=str(raw["id"]),
                text=str(raw["text"]),
                source=str(raw["source"]),
                scope=_scope(raw.get("scope"), label=f"constraint {index}"),
                priority=int(raw.get("priority", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConstraintError(f"constraint {index} is invalid") from exc
        if not constraint.id or not constraint.text or not constraint.source:
            raise ConstraintError(f"constraint {index} has empty required fields")
        constraints.append(constraint)

    legacy = manifest.get("criteria_constraints")
    if isinstance(legacy, str) and legacy.strip():
        constraints.append(
            Constraint(
                id="legacy.criteria_constraints",
                text=legacy.strip(),
                source="seed.json#experiment.criteria_constraints",
                scope=("L4", "L5", "L6", "L7"),
                priority=0,
            )
        )
    ids = [item.id for item in constraints]
    if len(ids) != len(set(ids)):
        raise ConstraintError("constraint ids must be unique")

    active = {item.id: item for item in constraints}
    revoked: list[str] = []
    amendments: list[Amendment] = []
    raw_amendments = manifest.get("amendments", [])
    if raw_amendments and not isinstance(raw_amendments, list):
        raise ConstraintError("experiment.amendments must be a list")
    ordered: list[tuple[int, int, dict[str, Any]]] = []
    for order, raw in enumerate(raw_amendments):
        if not isinstance(raw, dict):
            raise ConstraintError(f"amendment {order} must be an object")
        try:
            ordered.append((int(raw.get("priority", 0)), order, raw))
        except (TypeError, ValueError) as exc:
            raise ConstraintError(f"amendment {order} has invalid priority") from exc

    for priority, order, raw in sorted(ordered):
        action = str(raw.get("action", ""))
        target = str(raw["target"]) if raw.get("target") is not None else None
        text = str(raw["text"]) if raw.get("text") is not None else None
        scope = _scope(raw.get("scope"), label=f"amendment {order}")
        expires_at = str(raw["expires_at"]) if raw.get("expires_at") is not None else None
        applies = _not_expired(expires_at, now)
        if action not in {"add", "replace", "revoke"}:
            raise ConstraintError(f"amendment {order} has invalid action")
        if action in {"replace", "revoke"} and (not target or target not in active):
            raise ConstraintError(f"amendment {order} targets no active constraint")
        if action in {"replace", "revoke"} and set(scope) != set(active[target].scope):
            raise ConstraintError(
                f"amendment {order} scope differs from its target; split the base constraint first"
            )
        if action in {"add", "replace"} and not text:
            raise ConstraintError(f"amendment {order} requires text")
        amendment = Amendment(
            id=str(raw.get("id", "")),
            action=action,
            target=target,
            text=text,
            source=str(raw.get("source", "")),
            scope=scope,
            priority=priority,
            expires_at=expires_at,
            order=order,
            applied=applies,
        )
        if not amendment.id or not amendment.source:
            raise ConstraintError(f"amendment {order} has empty required fields")
        amendments.append(amendment)
        if not applies:
            continue
        if action == "revoke":
            assert target is not None
            revoked.append(active.pop(target).text)
        elif action == "replace":
            assert target is not None and text is not None
            replaced = active.pop(target)
            active[amendment.id] = Constraint(
                amendment.id, text, amendment.source, scope, priority
            )
            revoked.append(replaced.text)
        else:
            assert text is not None
            if amendment.id in active:
                raise ConstraintError("amendment add id conflicts with a constraint")
            active[amendment.id] = Constraint(
                amendment.id, text, amendment.source, scope, priority
            )

    effective = tuple(sorted(active.values(), key=lambda item: (item.priority, item.id)))
    return ConstraintResolution(
        base=tuple(constraints),
        amendments=tuple(amendments),
        effective=effective,
        revoked=tuple(revoked),
    )
