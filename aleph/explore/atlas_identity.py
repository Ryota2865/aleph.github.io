"""Deterministic identity for a completed Atlas artifact set."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


IDENTITY_SCHEMA_VERSION = 1
IDENTITY_FILENAME = "identity.json"
REQUIRED_BUILD_SECTIONS = frozenset({"corpus", "chunker", "embedder", "atlas", "code"})
DEFAULT_ARTIFACTS = (
    "manifest.json",
    "chunks.jsonl",
    "embeddings.npy",
    "labels.npy",
    "density.npy",
    "style.npy",
    "atlas_meta.json",
)


class AtlasIdentityError(ValueError):
    """The Atlas cannot make a full, verified identity claim."""


@dataclass(frozen=True)
class AtlasComparison:
    comparable: bool
    reasons: tuple[str, ...]


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AtlasIdentityError(f"identity payload is not canonical JSON: {exc}") from exc
    return encoded.encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise AtlasIdentityError(f"cannot hash Atlas artifact {path.name}: {exc}") from exc
    return digest.hexdigest()


def _normalise_build_spec(build_spec: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(build_spec, Mapping):
        raise AtlasIdentityError("build_spec must be a mapping")
    missing = sorted(REQUIRED_BUILD_SECTIONS - set(build_spec))
    if missing:
        raise AtlasIdentityError(f"build_spec missing required sections: {', '.join(missing)}")
    normalised = json.loads(_canonical_bytes(build_spec).decode("utf-8"))
    _reject_unstable_build_fields(normalised)
    return normalised


def _reject_unstable_build_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"created", "timestamp", "absolute_path", "index_dir"}:
                raise AtlasIdentityError(f"build_spec must not include unstable field: {key}")
            if "path" in key and isinstance(item, str) and Path(item).is_absolute():
                raise AtlasIdentityError(f"build_spec must not include an absolute path: {key}")
            _reject_unstable_build_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_unstable_build_fields(item)


def _artifact_path(directory: Path, name: str) -> Path:
    relative = Path(name)
    if not name or relative.is_absolute() or ".." in relative.parts or name == IDENTITY_FILENAME:
        raise AtlasIdentityError(f"invalid Atlas artifact name: {name!r}")
    return directory / relative


@dataclass(frozen=True)
class AtlasIdentity:
    """A content identity; equality means reuse of bit-identical Atlas artifacts."""

    hash: str
    payload: dict[str, Any]

    @classmethod
    def build(
        cls,
        index_dir: str | Path,
        *,
        build_spec: Mapping[str, Any],
        artifact_names: tuple[str, ...] = DEFAULT_ARTIFACTS,
    ) -> "AtlasIdentity":
        directory = Path(index_dir)
        spec = _normalise_build_spec(build_spec)
        names = tuple(dict.fromkeys(artifact_names))
        if not names:
            raise AtlasIdentityError("artifact_names must be non-empty")
        paths = {name: _artifact_path(directory, name) for name in names}
        missing = [name for name, path in paths.items() if not path.is_file()]
        if missing:
            raise AtlasIdentityError(f"Atlas artifacts are missing: {', '.join(missing)}")
        payload = {
            "schema_version": IDENTITY_SCHEMA_VERSION,
            "build_spec": spec,
            "artifacts": {name: _sha256_file(paths[name]) for name in sorted(names)},
        }
        identity = cls(hash=_sha256_bytes(_canonical_bytes(payload)), payload=payload)
        identity._write(directory)
        return identity

    @classmethod
    def load(cls, index_dir: str | Path) -> "AtlasIdentity":
        path = Path(index_dir) / IDENTITY_FILENAME
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AtlasIdentityError(f"identity.json is unreadable: {exc}") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("payload"), dict):
            raise AtlasIdentityError("identity.json must contain an object payload")
        claimed = raw.get("hash")
        actual = _sha256_bytes(_canonical_bytes(raw["payload"]))
        if not isinstance(claimed, str) or claimed != actual:
            raise AtlasIdentityError("identity.json hash does not match its canonical payload")
        return cls(hash=claimed, payload=raw["payload"])

    def verify(self, index_dir: str | Path) -> bool:
        directory = Path(index_dir)
        if _sha256_bytes(_canonical_bytes(self.payload)) != self.hash:
            raise AtlasIdentityError("in-memory identity hash does not match payload")
        if self.payload.get("schema_version") != IDENTITY_SCHEMA_VERSION:
            raise AtlasIdentityError("unsupported Atlas identity schema_version")
        build_spec = self.payload.get("build_spec")
        if not isinstance(build_spec, dict):
            raise AtlasIdentityError("identity payload has no build_spec")
        _normalise_build_spec(build_spec)
        artifacts = self.payload.get("artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            raise AtlasIdentityError("identity payload has no artifacts")
        for name, expected in artifacts.items():
            if not isinstance(name, str) or not isinstance(expected, str):
                raise AtlasIdentityError("identity artifact map is invalid")
            actual = _sha256_file(_artifact_path(directory, name))
            if actual != expected:
                raise AtlasIdentityError(f"Atlas artifact hash mismatch: {name}")
        return True

    def compare(self, other: "AtlasIdentity") -> AtlasComparison:
        if not isinstance(other, AtlasIdentity):
            return AtlasComparison(False, ("other identity is missing or invalid",))
        if self.hash != other.hash:
            return AtlasComparison(False, ("Atlas identity hashes differ",))
        return AtlasComparison(True, ())

    def _write(self, directory: Path) -> None:
        path = directory / IDENTITY_FILENAME
        temporary = directory / f".{IDENTITY_FILENAME}.tmp"
        document = {"hash": self.hash, "payload": self.payload}
        try:
            temporary.write_text(
                json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            raise AtlasIdentityError(f"cannot write identity.json: {exc}") from exc
