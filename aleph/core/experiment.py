"""Append-only experiment identity, ordering, blind selection, and reconciliation."""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class ExperimentError(RuntimeError):
    """An experiment invariant would be violated."""


@dataclass(frozen=True)
class BlindCandidate:
    label: str
    text: str
    technical_floor: dict[str, Any]


@dataclass(frozen=True)
class BlindSelection:
    choice: str
    chosen_arm: str
    rationale: str
    event_id: str


_JURY_SLOT_STATUSES = {"valid", "parse_invalid", "call_failed"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _normalize_budget_envelope(raw: Any, *, cap: float) -> dict[str, float] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or not raw:
        raise ExperimentError("budget_envelope must be a non-empty mapping")
    normalized: dict[str, float] = {}
    for key, value in raw.items():
        phase = str(key).strip() if isinstance(key, str) else ""
        if not phase:
            raise ExperimentError("budget_envelope phase keys must be non-empty strings")
        if type(value) not in (int, float) or float(value) <= 0:
            raise ExperimentError("budget_envelope allocations must be positive numbers")
        normalized[phase] = float(value)
    if abs(sum(normalized.values()) - cap) > 1e-9:
        raise ExperimentError("budget_envelope allocations must sum to budget_cap_usd")
    return normalized


def _normalize_protected_pools(raw: Any, *, cap: float) -> dict[str, float] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or set(raw) != {"player", "held_out", "closing"}:
        raise ExperimentError("protected_pools must define player, held_out, and closing exactly")
    normalized: dict[str, float] = {}
    for pool in ("player", "held_out", "closing"):
        value = raw[pool]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise ExperimentError("protected pool allocations must be finite non-negative numbers")
        normalized[pool] = float(value)
    if abs(sum(normalized.values()) - cap) > 1e-9:
        raise ExperimentError("protected pool allocations must sum to budget_cap_usd")
    return normalized


class ExperimentRun:
    """Deep module for the minimum adopted experiment lifecycle."""

    def __init__(self, work_dir: Path, manifest: dict[str, Any]) -> None:
        self.work_dir = Path(work_dir)
        self.experiment_dir = self.work_dir / "experiment"
        self.manifest_path = self.experiment_dir / "manifest.json"
        self.events_path = self.experiment_dir / "events.jsonl"
        self.manifest = manifest

    @classmethod
    def open(cls, work_dir: Path) -> "ExperimentRun":
        work_dir = Path(work_dir)
        seed_path = work_dir / "seed.json"
        try:
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperimentError(f"cannot read experiment seed: {type(exc).__name__}") from exc
        raw = seed.get("experiment") if isinstance(seed, dict) else None
        if not isinstance(raw, dict):
            raise ExperimentError("seed.json has no experiment manifest")
        required = ("id", "hypothesis", "intervention", "control", "observations")
        missing = [key for key in required if not raw.get(key)]
        if missing:
            raise ExperimentError("experiment manifest is missing: " + ", ".join(missing))
        ablation = seed.get("material_ablation", {}) if isinstance(seed, dict) else {}
        cap = raw.get("budget_cap_usd", ablation.get("budget_cap_usd"))
        if type(cap) not in (int, float) or float(cap) <= 0:
            raise ExperimentError("experiment manifest requires a positive budget_cap_usd")
        envelope = _normalize_budget_envelope(raw.get("budget_envelope"), cap=float(cap))
        protected_pools = _normalize_protected_pools(raw.get("protected_pools"), cap=float(cap))
        normalized = {
            "experiment_id": str(raw["id"]),
            "manifest_version": int(raw.get("version", 1)),
            "hypothesis": str(raw["hypothesis"]),
            "intervention": raw["intervention"],
            "control": raw["control"],
            "observations": raw["observations"],
            "budget_cap_usd": float(cap),
            **({"budget_envelope": envelope} if envelope is not None else {}),
            **({"protected_pools": protected_pools} if protected_pools is not None else {}),
            "arms": list(ablation.get("arms", raw.get("arms", []))),
            "blind": raw.get("blind", {}),
            "constraints": raw.get("constraints", []),
            "amendments": raw.get("amendments", []),
            "legacy_criteria_constraints": raw.get("criteria_constraints"),
        }
        run = cls(work_dir, normalized)
        run.experiment_dir.mkdir(parents=True, exist_ok=True)
        if run.manifest_path.exists():
            try:
                existing = json.loads(run.manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ExperimentError("normalized experiment manifest is unreadable") from exc
            if existing != normalized:
                raise ExperimentError("normalized experiment manifest is immutable")
        else:
            run.manifest_path.write_text(
                json.dumps(normalized, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        run.events_path.touch(exist_ok=True)
        return run

    @property
    def experiment_id(self) -> str:
        return str(self.manifest["experiment_id"])

    def events(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        previous_hash: str | None = None
        for position, line in enumerate(self.events_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ExperimentError(f"experiment event {position} is invalid JSON") from exc
            supplied_hash = row.pop("event_hash", None)
            if row.get("previous_hash") != previous_hash or supplied_hash != _hash(row):
                raise ExperimentError(f"experiment event {position} breaks the hash chain")
            row["event_hash"] = supplied_hash
            rows.append(row)
            previous_hash = supplied_hash
        return rows

    def bind_budget(self, budget: Any) -> None:
        """Register the complete experiment envelope with the budget ledger."""
        budget.register_scope_limit(
            f"experiment:{self.experiment_id}",
            ledger="api",
            limit=float(self.manifest["budget_cap_usd"]),
        )
        pools = self.manifest.get("protected_pools")
        if pools is not None:
            budget.register_pool_limits(
                f"experiment:{self.experiment_id}",
                ledger="api",
                player=float(pools["player"]),
                held_out=float(pools["held_out"]),
                closing=float(pools["closing"]),
            )

    def _append(self, event_type: str, **payload: Any) -> dict[str, Any]:
        rows = self.events()
        event = {
            "event_id": f"{self.experiment_id}:{len(rows) + 1:06d}",
            "experiment_id": self.experiment_id,
            "type": event_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            "previous_hash": rows[-1]["event_hash"] if rows else None,
            **payload,
        }
        event["event_hash"] = _hash(event)
        with self.events_path.open("a", encoding="utf-8") as target:
            target.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            target.flush()
        return event

    def register_arm(self, arm: str, *, work_id: str) -> dict[str, Any]:
        declared = self.manifest.get("arms", [])
        if declared and arm not in declared:
            raise ExperimentError(f"arm is not declared by the manifest: {arm}")
        registrations = [event for event in self.events() if event["type"] == "arm_registered"]
        for event in registrations:
            if event.get("arm") == arm:
                if event.get("work_id") == work_id:
                    return event
                raise ExperimentError(f"arm {arm} is already bound to another work")
            if event.get("work_id") == work_id:
                raise ExperimentError(f"work {work_id} is already bound to another arm")
        return self._append("arm_registered", arm=arm, work_id=work_id)

    def record_deviation(
        self,
        *,
        reason: str,
        preregistration: str,
        decided_by: str,
    ) -> dict[str, Any]:
        if not reason.strip() or not preregistration.strip():
            raise ExperimentError("deviation requires its reason and preregistered rule")
        return self._append(
            "deviation",
            reason=reason,
            preregistration=preregistration,
            decided_by=decided_by,
        )

    def select_blind(
        self,
        candidates: Mapping[str, Mapping[str, Any]],
        *,
        selector: Callable[[Sequence[BlindCandidate]], Mapping[str, Any]],
        decided_by: str,
    ) -> BlindSelection:
        if any(row["type"] == "blind_selection" for row in self.events()):
            raise ExperimentError("blind selection already exists")
        if len(candidates) < 2:
            raise ExperimentError("blind selection requires at least two candidates")
        declared = self.manifest.get("arms", [])
        if declared:
            registered = {
                str(event["arm"])
                for event in self.events()
                if event["type"] == "arm_registered"
            }
            missing = set(candidates) - registered
            if missing:
                raise ExperimentError(
                    "blind candidates are not registered arms: " + ", ".join(sorted(missing))
                )
        arms = list(candidates)
        labels = [chr(ord("A") + index) for index in range(len(arms))]
        seed = int(self.manifest.get("blind", {}).get("seed", 0))
        random.Random(seed).shuffle(labels)
        mapping = dict(zip(arms, labels, strict=True))
        label_to_arm = {label: arm for arm, label in mapping.items()}
        view = tuple(
            BlindCandidate(
                label=label,
                text=str(candidates[label_to_arm[label]].get("text", "")),
                technical_floor=dict(
                    candidates[label_to_arm[label]].get("technical_floor", {})
                ),
            )
            for label in sorted(label_to_arm)
        )
        result = selector(view)
        choice = str(result.get("choice", "")).strip().upper()
        if choice not in label_to_arm:
            raise ExperimentError(f"selector returned an invalid blind label: {choice!r}")
        event = self._append(
            "blind_selection",
            decided_by=decided_by,
            choice=choice,
            chosen_arm=label_to_arm[choice],
            rationale=str(result.get("rationale", "")),
            label_mapping=mapping,
        )
        return BlindSelection(
            choice=choice,
            chosen_arm=label_to_arm[choice],
            rationale=str(result.get("rationale", "")),
            event_id=event["event_id"],
        )

    def reveal_jury(
        self, rows: Sequence[Mapping[str, Any]], *, decided_by: str
    ) -> dict[str, Any]:
        events = self.events()
        selections = [event for event in events if event["type"] == "blind_selection"]
        if not selections:
            raise ExperimentError("jury reveal requires a durable blind selection event")
        if any(event["type"] == "jury_reveal" for event in events):
            raise ExperimentError("jury reveal already exists")
        arms = set(selections[-1]["label_mapping"])
        normalized: list[dict[str, Any]] = []
        for position, row in enumerate(rows):
            arm = str(row.get("arm", ""))
            if arm not in arms:
                raise ExperimentError(f"jury row {position} has unknown arm")
            scores = row.get("scores")
            if not isinstance(scores, list) or not all(type(score) in (int, float) for score in scores):
                raise ExperimentError(f"jury row {position} has invalid scores")
            normalized.append({"arm": arm, "scores": scores})
        return self._append("jury_reveal", decided_by=decided_by, rows=normalized)

    def register_jury_batch(
        self,
        *,
        batch_id: str,
        expected_slots: Sequence[str],
        packet_hash: str,
        reservation_id: str,
        semantic_retries: int,
        decided_by: str,
    ) -> dict[str, Any]:
        """Pre-register the atomic jury boundary before any provider call."""
        slots = tuple(str(slot).strip() for slot in expected_slots)
        if (
            not batch_id.strip()
            or not slots
            or any(not slot for slot in slots)
            or len(set(slots)) != len(slots)
            or not packet_hash.strip()
            or not reservation_id.strip()
            or semantic_retries < 0
        ):
            raise ExperimentError("jury batch registration is incomplete or invalid")
        payload = {
            "batch_id": batch_id,
            "expected_slots": list(slots),
            "packet_hash": packet_hash,
            "reservation_id": reservation_id,
            "semantic_retries": semantic_retries,
            "atomic_projection": True,
            "decided_by": decided_by,
        }
        existing = [
            event
            for event in self.events()
            if event["type"] == "jury_batch_registered" and event.get("batch_id") == batch_id
        ]
        if existing:
            comparable = {key: existing[-1].get(key) for key in payload}
            if comparable == payload:
                return existing[-1]
            raise ExperimentError(f"jury batch manifest is immutable: {batch_id}")
        return self._append("jury_batch_registered", **payload)

    def record_jury_slot(
        self,
        *,
        batch_id: str,
        slot_id: str,
        attempt: int,
        status: str,
        call_id: str,
        charge_id: str,
        raw_response_hash: str,
        parsed: Mapping[str, Any] | None,
        decided_by: str,
    ) -> dict[str, Any]:
        """Append one call/charge/parse result immediately; never regenerate prior evidence."""
        events = self.events()
        registrations = [
            event
            for event in events
            if event["type"] == "jury_batch_registered" and event.get("batch_id") == batch_id
        ]
        if not registrations:
            raise ExperimentError(f"jury batch is not registered: {batch_id}")
        registration = registrations[-1]
        if slot_id not in registration["expected_slots"]:
            raise ExperimentError(f"jury slot is not preregistered: {slot_id}")
        if status not in _JURY_SLOT_STATUSES or attempt < 1:
            raise ExperimentError("jury slot status or attempt is invalid")
        if attempt > int(registration["semantic_retries"]) + 1:
            raise ExperimentError("jury slot exceeds preregistered semantic retries")
        if not call_id or not charge_id or not raw_response_hash:
            raise ExperimentError("jury slot must preserve call, charge, and raw response evidence")
        normalized: dict[str, Any] | None = None
        if status == "valid":
            if not isinstance(parsed, Mapping):
                raise ExperimentError("valid jury slot requires a parsed object")
            score = parsed.get("score")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
            ):
                raise ExperimentError("valid jury slot requires a finite numeric score")
            normalized = dict(parsed)
            normalized["score"] = float(score)
        elif parsed is not None:
            raise ExperimentError("invalid jury slot must not carry a parsed projection")
        payload = {
            "batch_id": batch_id,
            "slot_id": slot_id,
            "attempt": attempt,
            "status": status,
            "call_id": call_id,
            "charge_id": charge_id,
            "raw_response_hash": raw_response_hash,
            "parsed": normalized,
            "decided_by": decided_by,
        }
        existing = [
            event
            for event in events
            if event["type"] == "jury_slot_recorded"
            and event.get("batch_id") == batch_id
            and event.get("slot_id") == slot_id
            and event.get("attempt") == attempt
        ]
        if existing:
            comparable = {key: existing[-1].get(key) for key in payload}
            if comparable == payload:
                return existing[-1]
            raise ExperimentError("jury slot attempt already has different evidence")
        if any(
            event["type"] == "jury_batch_projection" and event.get("batch_id") == batch_id
            for event in events
        ):
            raise ExperimentError("jury batch is already projected")
        return self._append("jury_slot_recorded", **payload)

    def project_jury_batch(self, batch_id: str, *, decided_by: str) -> dict[str, Any]:
        """Project numeric aggregates only after every preregistered slot is valid."""
        events = self.events()
        prior = [
            event
            for event in events
            if event["type"] == "jury_batch_projection" and event.get("batch_id") == batch_id
        ]
        if prior:
            return prior[-1]
        registrations = [
            event
            for event in events
            if event["type"] == "jury_batch_registered" and event.get("batch_id") == batch_id
        ]
        if not registrations:
            raise ExperimentError(f"jury batch is not registered: {batch_id}")
        expected = tuple(registrations[-1]["expected_slots"])
        latest: dict[str, dict[str, Any]] = {}
        for event in events:
            if event["type"] == "jury_slot_recorded" and event.get("batch_id") == batch_id:
                current = latest.get(str(event["slot_id"]))
                if current is None or int(event["attempt"]) > int(current["attempt"]):
                    latest[str(event["slot_id"])] = event
        missing = [slot for slot in expected if slot not in latest]
        invalid = [slot for slot in expected if slot in latest and latest[slot]["status"] != "valid"]
        common = {
            "batch_id": batch_id,
            "expected_slots": list(expected),
            "valid_slots": [slot for slot in expected if slot in latest and latest[slot]["status"] == "valid"],
            "invalid_slots": invalid,
            "missing_slots": missing,
            "decided_by": decided_by,
        }
        if missing or invalid:
            call_failed = any(
                slot in latest and latest[slot]["status"] == "call_failed" for slot in expected
            )
            status = "INCOMPLETE_CALL" if missing or call_failed else "INCOMPLETE_PARSE"
            return self._append("jury_batch_projection", status=status, **common)
        scores = [float(latest[slot]["parsed"]["score"]) for slot in expected]
        return self._append(
            "jury_batch_projection",
            status="COMPLETE",
            scores=scores,
            mean_score=statistics.fmean(scores),
            disagreement_stddev=statistics.pstdev(scores),
            **common,
        )

    def promote(
        self,
        arm: str,
        *,
        work_id: str,
        command_id: str,
        decided_by: str,
    ) -> dict[str, Any]:
        events = self.events()
        selections = [event for event in events if event["type"] == "blind_selection"]
        if not selections:
            raise ExperimentError("canonical promotion requires blind selection")
        if selections[-1].get("chosen_arm") != arm:
            raise ExperimentError("canonical promotion must use the selected arm")
        if not any(event["type"] == "jury_reveal" for event in events):
            raise ExperimentError("canonical promotion requires the recorded jury reveal")
        promotions = [event for event in events if event["type"] == "canonical_promotion"]
        if promotions:
            existing = promotions[-1]
            if existing.get("arm") == arm and existing.get("work_id") == work_id:
                return existing
            raise ExperimentError("a different canonical promotion already exists")
        return self._append(
            "canonical_promotion",
            arm=arm,
            work_id=work_id,
            command_id=command_id,
            decided_by=decided_by,
        )

    def reconcile(
        self,
        *,
        calls_path: Path | Sequence[Path],
        charge_events: Sequence[Mapping[str, Any]],
        provider_charges: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Reconcile one experiment scope without inventing missing provenance."""
        scope = f"experiment:{self.experiment_id}"
        issues: list[str] = []
        calls: list[dict[str, Any]] = []
        paths = [calls_path] if isinstance(calls_path, (str, Path)) else list(calls_path)
        lines: list[str] = []
        for path in paths:
            try:
                lines.extend(Path(path).read_text(encoding="utf-8").splitlines())
            except OSError as exc:
                issues.append(f"calls are unreadable ({path}): {type(exc).__name__}")
        required = (
            "call_id", "charge_id", "command_id", "work_id", "experiment_id",
            "phase", "arm", "charged_to",
        )
        for position, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"call row {position} is invalid JSON")
                continue
            if not isinstance(row, dict):
                issues.append(f"call row {position} is not an object")
                continue
            if row.get("experiment_id") not in (None, self.experiment_id) and row.get("charged_to") != scope:
                continue
            missing = [field for field in required if row.get(field) in (None, "")]
            if missing:
                issues.append(f"call row {position} missing provenance: {', '.join(missing)}")
                continue
            if row["experiment_id"] != self.experiment_id or row["charged_to"] != scope:
                continue
            if type(row.get("cost_usd")) not in (int, float):
                issues.append(f"call row {position} has invalid cost_usd")
                continue
            calls.append(row)

        scoped_charges = [
            dict(event)
            for event in charge_events
            if event.get("charged_to") == scope or event.get("experiment_id") == self.experiment_id
        ]
        charge_by_id: dict[str, dict[str, Any]] = {}
        for event in scoped_charges:
            charge_id = str(event.get("charge_id", ""))
            if not charge_id:
                issues.append("charge event missing charge_id")
            elif charge_id in charge_by_id:
                issues.append(f"duplicate charge_id: {charge_id}")
            else:
                charge_by_id[charge_id] = event

        call_ids: set[str] = set()
        provider_by_call: dict[str, dict[str, Any]] = {}
        for row in provider_charges:
            if row.get("charged_to") != scope:
                continue
            call_id = str(row.get("call_id", ""))
            if not call_id:
                issues.append("provider charge missing call_id")
            elif call_id in provider_by_call:
                issues.append(f"duplicate provider call_id: {call_id}")
            else:
                provider_by_call[call_id] = dict(row)

        provenance_fields = (
            "call_id", "command_id", "work_id", "experiment_id", "phase", "arm", "charged_to"
        )
        for call in calls:
            call_id = str(call["call_id"])
            if call_id in call_ids:
                issues.append(f"duplicate call_id: {call_id}")
            call_ids.add(call_id)
            charge = charge_by_id.get(str(call["charge_id"]))
            if charge is None:
                issues.append(f"call {call_id} has no linked charge event")
            else:
                for field in provenance_fields:
                    if charge.get(field) != call.get(field):
                        issues.append(f"call {call_id} charge {field} mismatch")
                if charge.get("ledger") != "api" or abs(
                    float(charge.get("amount", float("nan"))) - float(call["cost_usd"])
                ) > 1e-9:
                    issues.append(f"call {call_id} charge amount mismatch")
            provider = provider_by_call.get(call_id)
            if provider is None:
                issues.append(f"call {call_id} has no provider charge")
            elif type(provider.get("amount_usd")) not in (int, float) or abs(
                float(provider["amount_usd"]) - float(call["cost_usd"])
            ) > 1e-9:
                issues.append(f"call {call_id} provider amount mismatch")

        for charge_id, charge in charge_by_id.items():
            if not any(str(call["charge_id"]) == charge_id for call in calls):
                issues.append(f"charge {charge_id} has no linked call")
        for call_id in provider_by_call:
            if call_id not in call_ids:
                issues.append(f"provider charge {call_id} has no linked call")
        if not calls:
            issues.append("scope has no fully provenanced calls")

        call_total = sum(float(row["cost_usd"]) for row in calls)
        ledger_total = sum(
            float(row.get("amount", 0.0))
            for row in scoped_charges
            if row.get("ledger") == "api"
        )
        provider_total = sum(
            float(row.get("amount_usd", 0.0)) for row in provider_by_call.values()
        )
        if not (abs(call_total - ledger_total) <= 1e-9 and abs(call_total - provider_total) <= 1e-9):
            issues.append("scope totals disagree")
        unique_issues = list(dict.fromkeys(issues))
        return {
            "experiment_id": self.experiment_id,
            "charged_to": scope,
            "status": "matched" if not unique_issues else "unreconciled",
            "calls": {"count": len(calls), "total_usd": call_total},
            "ledger": {"count": len(scoped_charges), "total_usd": ledger_total},
            "provider": {"count": len(provider_by_call), "total_usd": provider_total},
            "issues": unique_issues,
        }
