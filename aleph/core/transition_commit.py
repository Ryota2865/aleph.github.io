"""Authoritative L0 event commit and checkpoint projection.

The event stream is committed first.  ``checkpoint.json`` is derived from it and
may be repaired after a crash.  See designs/transition-commit.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aleph.core.loop import Checkpoint, State, validate_transition


SCHEMA_VERSION = 1


class TransitionCommitError(RuntimeError):
    """Base error for authoritative transition recording."""


class ReplayError(TransitionCommitError):
    """The authoritative L0 stream cannot be replayed strictly."""


class CommandConflictError(TransitionCommitError):
    """A command id was reused for a different operation."""


class LegacyHistoryError(TransitionCommitError):
    """A legacy L0 stream needs explicit reconciliation before mutation."""


@dataclass(frozen=True)
class TransitionResult:
    event: dict[str, Any]
    checkpoint: Checkpoint
    replayed_snapshot: Checkpoint
    warnings: tuple[str, ...] = ()
    idempotent: bool = False


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReplayError(f"invalid JSON at line {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ReplayError(f"decision at line {line_number} is not an object")
        rows.append(row)
    return rows


def _l0_records(path: Path) -> list[dict[str, Any]]:
    return [row for row in _records(path) if row.get("layer") == "L0"]


def _require_modern_stream(path: Path) -> list[dict[str, Any]]:
    rows = _l0_records(path)
    legacy = [row for row in rows if row.get("schema_version") != SCHEMA_VERSION]
    modern = [row for row in rows if row.get("schema_version") == SCHEMA_VERSION]
    if legacy and not modern:
        raise LegacyHistoryError(
            f"{len(legacy)} legacy L0 event(s) require reconciliation before mutation"
        )
    if legacy:
        first_modern = next(i for i, row in enumerate(rows) if row.get("schema_version") == SCHEMA_VERSION)
        if any(row.get("schema_version") != SCHEMA_VERSION for row in rows[first_modern:]):
            raise LegacyHistoryError("legacy L0 events may not appear after reconciliation")
        if modern[0].get("event_type") != "reconciliation":
            raise LegacyHistoryError("modern suffix after legacy history must start with reconciliation")
        strict_replay("validation", path)
    return modern


def strict_replay(work_id: str, decisions_path) -> Checkpoint:
    """Replay schema-v1 L0 events, rejecting every continuity violation."""
    path = Path(decisions_path)
    all_rows = _l0_records(path)
    if not all_rows:
        return Checkpoint(work_id=work_id, state=State.SEEDED, step=0, payload={})
    legacy = [row for row in all_rows if row.get("schema_version") != SCHEMA_VERSION]
    rows = [row for row in all_rows if row.get("schema_version") == SCHEMA_VERSION]
    if legacy and not rows:
        raise ReplayError(f"legacy stream has no reconciliation ({len(legacy)} L0 events)")
    if legacy:
        first_modern = next(
            i for i, row in enumerate(all_rows) if row.get("schema_version") == SCHEMA_VERSION
        )
        if any(row.get("schema_version") != SCHEMA_VERSION for row in all_rows[first_modern:]):
            raise ReplayError("legacy event appears after the modern replay segment")
        if rows[0].get("event_type") != "reconciliation":
            raise ReplayError("legacy stream must be followed by a reconciliation event")

    state = State.SEEDED
    payload: dict[str, Any] = {}
    seen_commands: set[str] = set()
    initialized = False

    for expected_event_id, row in enumerate(rows, start=1):
        if row.get("schema_version") != SCHEMA_VERSION:
            raise ReplayError(f"event {expected_event_id} is legacy or has unknown schema")
        if row.get("event_id") != expected_event_id:
            raise ReplayError(
                f"event_id must be contiguous: expected {expected_event_id}, got {row.get('event_id')!r}"
            )
        command_id = row.get("command_id")
        if not isinstance(command_id, str) or not command_id:
            raise ReplayError(f"event {expected_event_id} has invalid command_id")
        if command_id in seen_commands:
            raise ReplayError(f"duplicate command_id: {command_id}")
        seen_commands.add(command_id)

        event_type = row.get("event_type")
        before_raw = row.get("state_before")
        after_raw = row.get("state_after")
        try:
            after = State(after_raw)
        except (TypeError, ValueError) as exc:
            raise ReplayError(f"event {expected_event_id} has invalid state_after") from exc

        if event_type in {"initialize", "reconciliation"}:
            if expected_event_id != 1 or before_raw is not None:
                raise ReplayError(
                    f"{event_type} is allowed only as the first modern event with state_before=null"
                )
            state = after
            initialized = True
        else:
            try:
                before = State(before_raw)
            except (TypeError, ValueError) as exc:
                raise ReplayError(f"event {expected_event_id} has invalid state_before") from exc
            if before != state:
                raise ReplayError(
                    f"event {expected_event_id} state_before={before.value} does not match {state.value}"
                )
            if event_type == "transition":
                if not validate_transition(before, after):
                    raise ReplayError(f"invalid transition: {before.value}->{after.value}")
                state = after
            elif event_type == "projection":
                if after != before:
                    raise ReplayError(f"{event_type} must not change lifecycle state")
            else:
                raise ReplayError(f"event {expected_event_id} has invalid event_type={event_type!r}")

        delta = row.get("payload", {})
        if not isinstance(delta, dict):
            raise ReplayError(f"event {expected_event_id} payload must be an object")
        payload.update(delta)

    if initialized and rows[0].get("event_type") not in {"initialize", "reconciliation"}:
        raise ReplayError("invalid initialization")
    return Checkpoint(work_id=work_id, state=state, step=len(rows), payload=payload)


def recover(work) -> Checkpoint:
    """Rebuild and atomically save the checkpoint from a strict modern stream."""
    checkpoint = strict_replay(work.work_id, work.decisions)
    checkpoint.save(work.dir)
    return checkpoint


def _event_signature(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        event.get("event_type"),
        event.get("state_before"),
        event.get("state_after"),
        event.get("decision"),
        event.get("reason"),
        event.get("decided_by"),
        event.get("payload", {}),
        event.get("legacy_event_count"),
        event.get("legacy_warnings", []),
    )


def audit_history(work) -> tuple[str, ...]:
    """Describe legacy continuity/projection mismatches without mutating the work."""
    rows = _l0_records(work.decisions)
    if rows and all(row.get("schema_version") == SCHEMA_VERSION for row in rows):
        try:
            replayed = strict_replay(work.work_id, work.decisions)
        except ReplayError as exc:
            return (str(exc),)
        try:
            checkpoint = Checkpoint.load(work.dir)
        except FileNotFoundError:
            return ("checkpoint is missing",)
        return () if checkpoint == replayed else ("checkpoint differs from strict replay",)

    warnings: list[str] = []
    state = State.SEEDED
    payload: dict[str, Any] = {}
    for position, row in enumerate(rows, start=1):
        decision = str(row.get("decision", ""))
        if "->" not in decision:
            warnings.append(f"L0 event {position} has no transition arrow")
            continue
        before_name, _, after_name = decision.partition("->")
        try:
            before = State(before_name)
            after = State(after_name)
        except ValueError:
            warnings.append(f"L0 event {position} has unknown state: {decision}")
            continue
        if before != state:
            warnings.append(
                f"L0 event {position} source {before.value} does not match replay state {state.value}"
            )
        if not validate_transition(before, after):
            warnings.append(f"L0 event {position} is not a canonical transition: {decision}")
        state = after
        delta = row.get("payload")
        if isinstance(delta, dict):
            payload.update(delta)

    try:
        checkpoint = Checkpoint.load(work.dir)
    except FileNotFoundError:
        warnings.append("checkpoint is missing")
        return tuple(warnings)
    if checkpoint.state != state:
        warnings.append(
            f"checkpoint state {checkpoint.state.value} differs from legacy replay state {state.value}"
        )
    if checkpoint.step != len(rows):
        warnings.append(f"checkpoint step {checkpoint.step} differs from L0 count {len(rows)}")
    if checkpoint.payload != payload:
        warnings.append("checkpoint payload differs from legacy replay payload")
    return tuple(warnings)


def _commit_event(work, candidate: dict[str, Any]) -> TransitionResult:
    rows = _require_modern_stream(work.decisions)
    existing = next(
        (row for row in rows if row.get("command_id") == candidate["command_id"]),
        None,
    )
    if existing is not None:
        if _event_signature(existing) != _event_signature(candidate):
            raise CommandConflictError(
                f"command_id {candidate['command_id']!r} was reused for a different operation"
            )
        checkpoint = recover(work)
        return TransitionResult(
            event=existing,
            checkpoint=checkpoint,
            replayed_snapshot=checkpoint,
            idempotent=True,
        )

    candidate = {
        **candidate,
        "schema_version": SCHEMA_VERSION,
        "event_id": len(rows) + 1,
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": "L0",
    }
    work.append_decision(candidate)
    checkpoint = strict_replay(work.work_id, work.decisions)
    checkpoint.save(work.dir)
    return TransitionResult(
        event=candidate,
        checkpoint=checkpoint,
        replayed_snapshot=checkpoint,
    )


def commit(
    work,
    *,
    command_id: str,
    expected_state: State,
    next_state: State,
    reason: str,
    decided_by: str,
    payload_delta: dict[str, Any] | None = None,
) -> TransitionResult:
    """Commit a validated lifecycle transition."""
    if not validate_transition(expected_state, next_state):
        raise ValueError(f"invalid transition: {expected_state} -> {next_state}")
    candidate = {
        "command_id": command_id,
        "event_type": "transition",
        "state_before": expected_state.value,
        "state_after": next_state.value,
        "decision": f"{expected_state.value}->{next_state.value}",
        "reason": reason,
        "decided_by": decided_by,
        "payload": dict(payload_delta or {}),
        "refs": [],
    }
    rows = _require_modern_stream(work.decisions)
    if any(row.get("command_id") == command_id for row in rows):
        return _commit_event(work, candidate)
    current = strict_replay(work.work_id, work.decisions)
    if current.state != expected_state:
        raise ReplayError(
            f"expected_state={expected_state.value} does not match replayed state={current.state.value}"
        )
    return _commit_event(work, candidate)


def initialize(
    work,
    *,
    command_id: str,
    state: State,
    reason: str,
    decided_by: str,
    payload: dict[str, Any] | None = None,
) -> TransitionResult:
    """Establish an explicit first L0 snapshot for an imported experiment arm."""
    rows = _require_modern_stream(work.decisions)
    if rows and not any(row.get("command_id") == command_id for row in rows):
        raise ReplayError("initialize is allowed only for an empty L0 stream")
    if not rows and work.checkpoint.exists():
        raise ReplayError("initialize refuses an unrecorded existing checkpoint")
    return _commit_event(
        work,
        {
            "command_id": command_id,
            "event_type": "initialize",
            "state_before": None,
            "state_after": state.value,
            "decision": f"initialize:{state.value}",
            "reason": reason,
            "decided_by": decided_by,
            "payload": dict(payload or {}),
            "refs": [],
        },
    )


def reconcile(
    work,
    *,
    command_id: str,
    reason: str,
    decided_by: str,
    warnings: list[str] | tuple[str, ...],
) -> TransitionResult:
    """Append a truthful modern baseline after an immutable legacy L0 prefix."""
    all_rows = _l0_records(work.decisions)
    legacy = [row for row in all_rows if row.get("schema_version") != SCHEMA_VERSION]
    modern = [row for row in all_rows if row.get("schema_version") == SCHEMA_VERSION]
    if not legacy:
        raise LegacyHistoryError("reconciliation requires a legacy L0 prefix")

    checkpoint = Checkpoint.load(work.dir)
    candidate = {
        "command_id": command_id,
        "event_type": "reconciliation",
        "state_before": None,
        "state_after": checkpoint.state.value,
        "decision": f"reconciliation:{checkpoint.state.value}",
        "reason": reason,
        "decided_by": decided_by,
        "payload": dict(checkpoint.payload),
        "refs": [],
        "legacy_event_count": len(legacy),
        "legacy_warnings": list(warnings),
    }
    if modern:
        return _commit_event(work, candidate)

    event = {
        **candidate,
        "schema_version": SCHEMA_VERSION,
        "event_id": 1,
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": "L0",
    }
    work.append_decision(event)
    replayed = strict_replay(work.work_id, work.decisions)
    replayed.save(work.dir)
    return TransitionResult(
        event=event,
        checkpoint=replayed,
        replayed_snapshot=replayed,
        warnings=tuple(warnings),
    )


def project(
    work,
    *,
    command_id: str,
    expected_state: State,
    name: str,
    reason: str,
    decided_by: str,
    payload_delta: dict[str, Any],
) -> TransitionResult:
    """Commit a projection-only event without changing lifecycle state."""
    current = strict_replay(work.work_id, work.decisions)
    if current.state != expected_state:
        raise ReplayError(
            f"expected_state={expected_state.value} does not match replayed state={current.state.value}"
        )
    return _commit_event(
        work,
        {
            "command_id": command_id,
            "event_type": "projection",
            "state_before": expected_state.value,
            "state_after": expected_state.value,
            "decision": f"projection:{name}",
            "reason": reason,
            "decided_by": decided_by,
            "payload": dict(payload_delta),
            "refs": [],
        },
    )
