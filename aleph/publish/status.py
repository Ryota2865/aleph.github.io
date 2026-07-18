"""Authoritative publication status derived from a work's decision history."""
from __future__ import annotations

import json
from pathlib import Path

from aleph.core.loop import State
from aleph.core.transition_commit import ReplayError, SCHEMA_VERSION, strict_replay


def is_published(work_dir: Path) -> bool:
    """Return whether a work is publishable according to its L0 history.

    Modern streams are replayed strictly. Historical streams without schema metadata
    retain compatibility through their last lifecycle publication decision. Invalid or
    ambiguous history fails closed.
    """
    work_dir = Path(work_dir)
    decisions = work_dir / "decisions.jsonl"
    if not decisions.exists():
        return False

    rows: list[dict] = []
    try:
        for line in decisions.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict) and row.get("layer") == "L0":
                rows.append(row)
    except (OSError, json.JSONDecodeError):
        return False

    modern = [
        row
        for row in rows
        if type(row.get("schema_version")) is int
        and row.get("schema_version") == SCHEMA_VERSION
    ]
    if modern:
        try:
            checkpoint = strict_replay(work_dir.name, decisions)
        except ReplayError:
            return False
        return (
            checkpoint.state == State.PUBLISH
            or (
                checkpoint.state == State.SHELVE
                and checkpoint.payload.get("publication_disposition") == "PUBLISH"
            )
        )

    if any("schema_version" in row for row in rows):
        return False

    for row in reversed(rows):
        decision = row.get("decision")
        if decision in {"FINISH->PUBLISH", "FINISH->SHELVE", "FINISH->DISCARD"}:
            return decision == "FINISH->PUBLISH"
    return False
