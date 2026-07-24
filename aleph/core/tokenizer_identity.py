"""Deterministic reader-tokenizer identity derived from GGUF metadata."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

TOKENIZER_SCALAR_KEYS = (
    "tokenizer.ggml.model",
    "tokenizer.ggml.pre",
    "tokenizer.ggml.eos_token_id",
    "tokenizer.ggml.padding_token_id",
    "tokenizer.ggml.bos_token_id",
    "tokenizer.ggml.add_bos_token",
    "tokenizer.chat_template",
)
TOKENIZER_ARRAY_KEYS = (
    "tokenizer.ggml.tokens",
    "tokenizer.ggml.token_type",
    "tokenizer.ggml.merges",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def summarize_sequence(values: Iterable[Any], *, item_type: str) -> dict[str, Any]:
    """Hash an ordered typed sequence without retaining the whole sequence."""
    if not isinstance(item_type, str) or not item_type:
        raise ValueError("item_type must be a non-empty string")
    digest = hashlib.sha256()
    count = 0
    for value in values:
        encoded = _canonical_bytes({"type": item_type, "value": value})
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1
    return {"item_type": item_type, "count": count, "sha256": digest.hexdigest()}


@dataclass(frozen=True)
class TokenizerIdentity:
    payload: Mapping[str, Any]
    hash: str

    @classmethod
    def create(
        cls,
        *,
        model_ref: str,
        scalars: Mapping[str, Any],
        arrays: Mapping[str, Mapping[str, Any]],
        llama_cpp_revision: str,
    ) -> "TokenizerIdentity":
        if not isinstance(model_ref, str) or not model_ref.strip():
            raise ValueError("model_ref must be a non-empty string")
        if (
            not isinstance(llama_cpp_revision, str)
            or len(llama_cpp_revision) != 40
            or any(ch not in "0123456789abcdef" for ch in llama_cpp_revision)
        ):
            raise ValueError("llama_cpp_revision must be 40 lowercase hex characters")
        missing_scalars = set(TOKENIZER_SCALAR_KEYS) - set(scalars)
        missing_arrays = set(TOKENIZER_ARRAY_KEYS) - set(arrays)
        if missing_scalars or missing_arrays:
            raise ValueError(
                "tokenizer metadata incomplete; "
                f"missing_scalars={sorted(missing_scalars)}, "
                f"missing_arrays={sorted(missing_arrays)}"
            )
        if set(scalars) != set(TOKENIZER_SCALAR_KEYS):
            raise ValueError("scalar tokenizer metadata keys must match the registered schema")
        if set(arrays) != set(TOKENIZER_ARRAY_KEYS):
            raise ValueError("array tokenizer metadata keys must match the registered schema")

        normalized_arrays: dict[str, dict[str, Any]] = {}
        for key in TOKENIZER_ARRAY_KEYS:
            summary = arrays[key]
            if not isinstance(summary, Mapping) or set(summary) != {
                "item_type",
                "count",
                "sha256",
            }:
                raise ValueError(f"{key}: invalid array summary")
            item_type = summary["item_type"]
            count = summary["count"]
            sha256 = summary["sha256"]
            if not isinstance(item_type, str) or not item_type:
                raise ValueError(f"{key}: item_type must be non-empty")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"{key}: count must be an integer >=0")
            if (
                not isinstance(sha256, str)
                or len(sha256) != 64
                or any(ch not in "0123456789abcdef" for ch in sha256)
            ):
                raise ValueError(f"{key}: sha256 must be 64 lowercase hex characters")
            normalized_arrays[key] = {
                "item_type": item_type,
                "count": count,
                "sha256": sha256,
            }

        payload = {
            "schema_version": 1,
            "model_ref": model_ref,
            "tokenizer_metadata": {
                "scalars": {key: scalars[key] for key in TOKENIZER_SCALAR_KEYS},
                "arrays": normalized_arrays,
            },
            "tokenize_implementation": {
                "name": "llama.cpp",
                "revision": llama_cpp_revision,
            },
        }
        return cls(payload=payload, hash=canonical_hash(payload))

    def write(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        document = dict(self.payload)
        document["identity_sha256"] = self.hash
        target.write_text(
            json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "TokenizerIdentity":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("tokenizer identity must be a JSON object")
        claimed = raw.pop("identity_sha256", None)
        actual = canonical_hash(raw)
        if claimed != actual:
            raise ValueError("tokenizer identity hash mismatch")
        # Re-run schema validation instead of accepting a correctly hashed unknown shape.
        metadata = raw.get("tokenizer_metadata")
        implementation = raw.get("tokenize_implementation")
        if (
            set(raw) != {
                "schema_version",
                "model_ref",
                "tokenizer_metadata",
                "tokenize_implementation",
            }
            or raw.get("schema_version") != 1
            or not isinstance(metadata, Mapping)
            or set(metadata) != {"scalars", "arrays"}
            or not isinstance(implementation, Mapping)
            or set(implementation) != {"name", "revision"}
            or implementation.get("name") != "llama.cpp"
        ):
            raise ValueError("unsupported tokenizer identity schema")
        rebuilt = cls.create(
            model_ref=raw["model_ref"],
            scalars=metadata["scalars"],
            arrays=metadata["arrays"],
            llama_cpp_revision=implementation["revision"],
        )
        if rebuilt.hash != claimed:
            raise ValueError("tokenizer identity canonical reconstruction mismatch")
        return rebuilt
