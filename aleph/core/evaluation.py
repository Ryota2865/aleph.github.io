"""One immutable evaluation context shared by ALEPH L4-L7."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aleph.core.constraints import Amendment, Constraint, ConstraintError, resolve_constraints
from aleph.core.work_snapshot import WorkSnapshot


class EvaluationPacketError(ValueError):
    """The evaluation context is missing, ambiguous, stale, or corrupt."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationPacketError(f"cannot read {path}: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise EvaluationPacketError(f"{path} must contain an object")
    return value


@dataclass(frozen=True)
class EvaluationPacket:
    work_id: str
    draft_version: int
    intent: str
    criteria: str
    base_constraints: tuple[Constraint, ...]
    amendments: tuple[Amendment, ...]
    effective_constraints: tuple[str, ...]
    revoked_constraints: tuple[str, ...]
    poetics_version: int | None
    atlas_identity: dict[str, Any] | None
    draft_ref: str
    provenance: dict[str, tuple[str, ...]]
    effective_constraints_hash: str
    packet_hash: str = field(repr=False)

    @property
    def hash(self) -> str:
        return self.packet_hash

    @classmethod
    def for_draft(
        cls,
        snapshot: WorkSnapshot,
        draft_version: int,
        *,
        at: datetime | None = None,
        _require_draft: bool = True,
    ) -> "EvaluationPacket":
        work_dir = Path(snapshot.work_dir)
        seed = _read_json(work_dir / "seed.json")
        experiment = seed.get("experiment")
        experiment = experiment if isinstance(experiment, dict) else {}
        now = at or datetime.now(timezone.utc)

        try:
            resolution = resolve_constraints(experiment, at=now)
        except ConstraintError as exc:
            raise EvaluationPacketError(str(exc)) from exc

        draft_path = work_dir / "drafts" / f"v{draft_version}.md"
        if _require_draft and not draft_path.exists():
            raise EvaluationPacketError(f"draft v{draft_version} is missing")
        intent_path = work_dir / "intent.md"
        criteria_path = work_dir / "compositions" / "criteria.md"
        intent = intent_path.read_text(encoding="utf-8") if intent_path.exists() else (snapshot.audience or "")
        criteria = criteria_path.read_text(encoding="utf-8") if criteria_path.exists() else ""
        effective = tuple(item.text for item in resolution.effective)
        effective_hash = _canonical_hash(effective)
        provenance = dict(snapshot.provenance)
        provenance["evaluation_packet"] = (
            "seed.json#experiment", "intent.md", "compositions/criteria.md", str(draft_path)
        )
        values = {
            "work_id": snapshot.work_id,
            "draft_version": draft_version,
            "intent": intent,
            "criteria": criteria,
            "base_constraints": resolution.base,
            "amendments": resolution.amendments,
            "effective_constraints": effective,
            "revoked_constraints": resolution.revoked,
            "poetics_version": snapshot.poetics_version,
            "atlas_identity": snapshot.atlas_identity,
            "draft_ref": str(draft_path),
            "provenance": provenance,
            "effective_constraints_hash": effective_hash,
        }
        packet_hash = _canonical_hash(cls._hash_payload(values))
        return cls(**values, packet_hash=packet_hash)

    @classmethod
    def for_planned_draft(
        cls, snapshot: WorkSnapshot, draft_version: int, *, at: datetime | None = None
    ) -> "EvaluationPacket":
        return cls.for_draft(
            snapshot, draft_version, at=at, _require_draft=False
        )

    @staticmethod
    def _hash_payload(values: dict[str, Any]) -> dict[str, Any]:
        payload = dict(values)
        payload["base_constraints"] = [asdict(item) for item in values["base_constraints"]]
        payload["amendments"] = [asdict(item) for item in values["amendments"]]
        return payload

    def recompute_hash(self) -> str:
        values = asdict(self)
        values.pop("packet_hash")
        return _canonical_hash(values)

    def validate(self) -> None:
        if self.hash != self.recompute_hash():
            raise EvaluationPacketError("evaluation packet hash disagreement")
        if self.effective_constraints_hash != _canonical_hash(self.effective_constraints):
            raise EvaluationPacketError("effective constraints hash disagreement")

    def render_for(self, layer: str) -> str:
        if layer not in {"L4", "L5", "L6", "L7"}:
            raise EvaluationPacketError(f"unknown evaluation layer: {layer}")
        active = [
            item.text
            for item in sorted(
                (
                    item for item in self.base_constraints
                    if item.text in self.effective_constraints and layer in item.scope
                ),
                key=lambda item: (item.priority, item.id),
            )
        ]
        # Added/replaced constraints are already canonical in effective_constraints. Include any
        # that are not represented by a surviving base constraint.
        active.extend(
            amendment.text
            for amendment in self.amendments
            if amendment.applied
            and amendment.action in {"add", "replace"}
            and amendment.text in self.effective_constraints
            and layer in amendment.scope
            and amendment.text not in active
        )
        lines = [f"Evaluation packet: {self.hash}", f"Intent:\n{self.intent}", f"Criteria:\n{self.criteria}"]
        if active:
            lines.append("有効な制約:\n" + "\n".join(f"- {item}" for item in active))
        if self.revoked_constraints:
            lines.append(
                "解除・失効済みの制約（遵守不足として減点してはならない）:\n"
                + "\n".join(f"- {item}" for item in self.revoked_constraints)
            )
        return "\n\n".join(lines)
