"""Strict, auditable interpretation of structured model output.

The public seam is :func:`parse_model_output`.  Callers declare the shape they
need and never coerce model-provided booleans, enums, or numbers themselves.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any


Schema = Any


@dataclass(frozen=True)
class StringMap:
    """A JSON object with dynamic string keys and one strict value schema."""

    values: Schema
    allowed_keys: frozenset[str] | None = None


def string_map(values: Schema, *, allowed_keys: frozenset[str] | None = None) -> StringMap:
    return StringMap(values, allowed_keys)


class ModelOutputError(ValueError):
    """Raised when a rejected output is required by an outward operation."""

    def __init__(self, result: "ModelOutput") -> None:
        self.result = result
        super().__init__("; ".join(result.warnings) or "model output was rejected")


class _DuplicateKey(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKey(f"duplicate JSON key: {key}")
        value[key] = item
    return value


@dataclass(frozen=True)
class ModelOutput:
    value: Any | None
    raw: str
    fragment: str | None
    source_span: tuple[int, int] | None
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.value is not None

    def require_value(self) -> Any:
        if self.value is None:
            raise ModelOutputError(self)
        return self.value


def _json_values(text: str) -> tuple[list[tuple[Any, int, int]], list[str]]:
    decoder = json.JSONDecoder(object_pairs_hook=_strict_object)
    values: list[tuple[Any, int, int]] = []
    warnings: list[str] = []
    index = 0
    while index < len(text):
        if text[index] not in "[{":
            index += 1
            continue
        try:
            value, consumed = decoder.raw_decode(text[index:])
        except _DuplicateKey as exc:
            warnings.append(str(exc))
            index += 1
            continue
        except (json.JSONDecodeError, ValueError):
            index += 1
            continue
        end = index + consumed
        values.append((value, index, end))
        index = end
    return values, warnings


def _schema_error(value: Any, schema: Schema, path: str = "$") -> str | None:
    if schema is Any or schema is object:
        return None
    if schema is bool:
        return None if type(value) is bool else f"{path} must be bool, got {type(value).__name__}"
    if schema is int:
        return None if type(value) is int else f"{path} must be int, got {type(value).__name__}"
    if schema is float:
        if type(value) not in (int, float):
            return f"{path} must be number, got {type(value).__name__}"
        return None if math.isfinite(float(value)) else f"{path} must be a finite number"
    if schema is str:
        return None if isinstance(value, str) else f"{path} must be str, got {type(value).__name__}"
    if schema is dict:
        return None if isinstance(value, dict) else f"{path} must be object, got {type(value).__name__}"
    if schema is list:
        return None if isinstance(value, list) else f"{path} must be array, got {type(value).__name__}"
    if isinstance(schema, frozenset):
        if value not in schema or any(type(value) is not type(option) for option in schema if option == value):
            return f"{path} must be one of {sorted(schema, key=str)!r}"
        return None
    if isinstance(schema, StringMap):
        if not isinstance(value, dict):
            return f"{path} must be object, got {type(value).__name__}"
        if not value:
            return f"{path} must contain at least one field"
        if schema.allowed_keys is not None:
            unknown = [key for key in value if key not in schema.allowed_keys]
            if unknown:
                return f"{path} has unknown fields: {unknown}"
        for key, item in value.items():
            error = _schema_error(item, schema.values, f"{path}.{key}")
            if error:
                return error
        return None
    if isinstance(schema, dict):
        if not isinstance(value, dict):
            return f"{path} must be object, got {type(value).__name__}"
        missing = [key for key in schema if key not in value]
        if missing:
            return f"{path} missing required fields: {missing}"
        for key, child_schema in schema.items():
            error = _schema_error(value[key], child_schema, f"{path}.{key}")
            if error:
                return error
        return None
    if isinstance(schema, list) and len(schema) == 1:
        if not isinstance(value, list):
            return f"{path} must be array, got {type(value).__name__}"
        for position, item in enumerate(value):
            error = _schema_error(item, schema[0], f"{path}[{position}]")
            if error:
                return error
        return None
    raise TypeError(f"unsupported model output schema at {path}: {schema!r}")


def parse_model_output(text: str, *, schema: Schema, fail_closed: bool = True) -> ModelOutput:
    """Extract one JSON value and validate it without coercion.

    Prose and markdown fences around a single value are allowed.  Multiple
    independent values are ambiguous and rejected unless ``fail_closed`` is
    explicitly disabled for a non-outward exploratory caller.
    """
    raw = str(text)
    candidates, scan_warnings = _json_values(raw)
    warnings = list(scan_warnings)
    if scan_warnings and fail_closed:
        return ModelOutput(None, raw, None, None, tuple(warnings))
    if not candidates:
        warnings.append("model output contains no valid JSON value")
        return ModelOutput(None, raw, None, None, tuple(warnings))
    if len(candidates) > 1:
        warnings.append(f"model output contains multiple JSON values ({len(candidates)})")
        if fail_closed:
            return ModelOutput(None, raw, None, None, tuple(warnings))

    value, start, end = candidates[0]
    error = _schema_error(value, schema)
    if error:
        warnings.append(error)
        return ModelOutput(None, raw, raw[start:end], (start, end), tuple(warnings))
    return ModelOutput(value, raw, raw[start:end], (start, end), tuple(warnings))
