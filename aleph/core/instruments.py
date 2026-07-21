"""Registered measurement records and comparison guards (Phase 5A).

This module deliberately records measurements; it does not calculate any domain
metric.  Individual domains own cosine, classifier, logprob, and other work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping

import yaml


class InstrumentError(ValueError):
    """A record or registry violates the instrument ledger contract."""


@dataclass(frozen=True)
class MeasurementContext:
    """Provenance supplied by the domain measurement implementation."""

    input_refs: tuple[Mapping[str, str], ...]
    model_ref: str
    prompt_ref: str
    prompt_hash: str
    identities: Mapping[str, str]
    confidence: Mapping[str, Any]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class InstrumentRecord:
    instrument_id: str
    instrument_version: str
    registry_hash: str
    status: str
    measurement_id: str
    subject_ref: str
    value: Any
    unit: str
    direction: str
    input_refs: tuple[Mapping[str, str], ...]
    model_ref: str
    prompt_ref: str
    prompt_hash: str
    identities: Mapping[str, str]
    confidence: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    measured_at: str
    measurement_status: str = "observed"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecordComparison:
    comparable: bool
    delta: float | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class InstrumentDefinition:
    instrument_id: str
    version: str
    status: str
    claim: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    calibration_date: str
    known_counterexamples: tuple[str, ...]
    blind_spots: tuple[str, ...]
    next_calibration_condition: str
    unit: str
    direction: str
    comparability_keys: tuple[str, ...]
    required_identities: tuple[str, ...]


_LEDGER_STATUSES = {"provisional", "calibrated_limited", "retired"}
_MEASUREMENT_STATUSES = {"observed", "missing", "invalid", "unclassified"}


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise InstrumentError(f"instrument data is not canonical JSON: {exc}") from exc


def _lookup(record: InstrumentRecord, key: str) -> Any:
    if key.startswith("identities."):
        return record.identities.get(key.removeprefix("identities."))
    return getattr(record, key, None)


class InstrumentRegistry:
    """The single registry authority for record validation and comparison."""

    def __init__(self, definitions: Mapping[str, InstrumentDefinition], registry_hash: str):
        self._definitions = dict(definitions)
        self.registry_hash = registry_hash

    @classmethod
    def load(cls, path: Path) -> "InstrumentRegistry":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise InstrumentError("instruments registry requires schema_version: 1")
        instruments = payload.get("instruments")
        if not isinstance(instruments, list) or not instruments:
            raise InstrumentError("instruments registry requires a non-empty instruments list")
        definitions: dict[str, InstrumentDefinition] = {}
        required = ("id", "version", "status", "claim", "inputs", "outputs", "calibration_date",
                    "known_counterexamples", "blind_spots", "next_calibration_condition", "unit",
                    "direction", "comparability_keys", "required_identities")
        for item in instruments:
            if not isinstance(item, dict) or any(name not in item for name in required):
                raise InstrumentError("each instrument must contain all ledger fields")
            instrument_id = item["id"]
            if not isinstance(instrument_id, str) or instrument_id in definitions:
                raise InstrumentError(f"invalid or duplicate instrument id: {instrument_id!r}")
            if item["status"] not in _LEDGER_STATUSES:
                raise InstrumentError(f"{instrument_id}: invalid ledger status")
            for name in ("inputs", "outputs", "known_counterexamples", "blind_spots", "comparability_keys", "required_identities"):
                if not isinstance(item[name], list) or not item[name]:
                    raise InstrumentError(f"{instrument_id}: {name} must be a non-empty list")
            definitions[instrument_id] = InstrumentDefinition(
                instrument_id=instrument_id, version=str(item["version"]), status=item["status"],
                claim=item["claim"], inputs=tuple(item["inputs"]), outputs=tuple(item["outputs"]),
                calibration_date=str(item["calibration_date"]),
                known_counterexamples=tuple(item["known_counterexamples"]), blind_spots=tuple(item["blind_spots"]),
                next_calibration_condition=item["next_calibration_condition"], unit=item["unit"],
                direction=item["direction"], comparability_keys=tuple(item["comparability_keys"]),
                required_identities=tuple(item["required_identities"]),
            )
        return cls(definitions, sha256(_canonical_json(payload).encode()).hexdigest())

    def definition(self, instrument_id: str) -> InstrumentDefinition:
        try:
            return self._definitions[instrument_id]
        except KeyError as exc:
            raise InstrumentError(f"unregistered instrument: {instrument_id}") from exc

    @property
    def instrument_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def record(self, *, instrument_id: str, subject_ref: str, value: Any,
               context: MeasurementContext, evidence_refs: tuple[str, ...],
               measurement_status: str = "observed", measured_at: str | None = None) -> InstrumentRecord:
        definition = self.definition(instrument_id)
        if definition.status == "retired":
            raise InstrumentError(f"retired instrument cannot create records: {instrument_id}")
        if measurement_status not in _MEASUREMENT_STATUSES:
            raise InstrumentError(f"invalid measurement status: {measurement_status}")
        if not subject_ref or not evidence_refs:
            raise InstrumentError("subject_ref and evidence_refs are required")
        if not context.model_ref or not context.prompt_ref or not context.prompt_hash:
            raise InstrumentError("model_ref, prompt_ref, and prompt_hash are required")
        if not context.input_refs or any(not ref.get("ref") or not ref.get("hash") for ref in context.input_refs):
            raise InstrumentError("input_refs must preserve both ref and hash")
        if not context.confidence:
            raise InstrumentError("confidence provenance is required")
        missing = [key for key in definition.required_identities if not context.identities.get(key)]
        if missing:
            raise InstrumentError(f"{instrument_id}: missing required identities: {', '.join(missing)}")
        if measurement_status == "observed" and value is None:
            raise InstrumentError("observed measurement requires a value; missing is not zero")
        if measurement_status != "observed" and value is not None:
            raise InstrumentError("missing, invalid, and unclassified measurements must not carry a value")
        now = measured_at or datetime.now(UTC).isoformat()
        input_refs = tuple(dict(ref) for ref in context.input_refs)
        identities = dict(context.identities)
        confidence = dict(context.confidence)
        material = {"instrument_id": instrument_id, "version": definition.version, "subject_ref": subject_ref,
                    "value": value, "context": {"input_refs": input_refs, "identities": identities},
                    "evidence_refs": evidence_refs, "measured_at": now}
        return InstrumentRecord(instrument_id, definition.version, self.registry_hash, definition.status,
            sha256(_canonical_json(material).encode()).hexdigest(), subject_ref, value, definition.unit,
            definition.direction, input_refs, context.model_ref, context.prompt_ref, context.prompt_hash,
            identities, confidence, evidence_refs, now, measurement_status, context.warnings)

    def decision_value(self, record: InstrumentRecord) -> Any:
        """Return a value only when the ledger permits automatic decisions."""
        definition = self.definition(record.instrument_id)
        if record.registry_hash != self.registry_hash or record.instrument_version != definition.version:
            raise InstrumentError("record does not belong to this registry version")
        if definition.status != "calibrated_limited":
            raise InstrumentError(f"{record.instrument_id} is {definition.status}, not decision-eligible")
        if record.measurement_status != "observed":
            raise InstrumentError("only observed measurements are decision-eligible")
        return record.value

    def compare(self, left: InstrumentRecord, right: InstrumentRecord) -> RecordComparison:
        warnings: list[str] = []
        if left.instrument_id != right.instrument_id or left.instrument_version != right.instrument_version:
            warnings.append("instrument id or version differs")
        if left.registry_hash != right.registry_hash:
            warnings.append("registry hash differs")
        if left.measurement_status != "observed" or right.measurement_status != "observed":
            warnings.append("missing, invalid, or unclassified records are not comparable")
        if warnings:
            return RecordComparison(False, None, tuple(warnings))
        definition = self.definition(left.instrument_id)
        for key in definition.comparability_keys:
            a, b = _lookup(left, key), _lookup(right, key)
            if not a or not b:
                warnings.append(f"comparability key missing: {key}")
            elif a != b:
                warnings.append(f"comparability key differs: {key}")
        if warnings:
            return RecordComparison(False, None, tuple(warnings))
        if (
            isinstance(left.value, bool)
            or isinstance(right.value, bool)
            or not isinstance(left.value, (int, float))
            or not isinstance(right.value, (int, float))
            or not math.isfinite(float(left.value))
            or not math.isfinite(float(right.value))
        ):
            return RecordComparison(False, None, ("values are not scalar numeric measurements",))
        return RecordComparison(True, right.value - left.value)
