"""Reader tokenizer identity is content-derived and tamper evident."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aleph.core.tokenizer_identity import (
    TOKENIZER_ARRAY_KEYS,
    TOKENIZER_SCALAR_KEYS,
    TokenizerIdentity,
    summarize_sequence,
)
from aleph.pipeline import RealDeps


def _identity(**overrides) -> TokenizerIdentity:
    scalars = {
        "tokenizer.ggml.model": "gpt2",
        "tokenizer.ggml.pre": "qwen35",
        "tokenizer.ggml.eos_token_id": 2,
        "tokenizer.ggml.padding_token_id": 0,
        "tokenizer.ggml.bos_token_id": 1,
        "tokenizer.ggml.add_bos_token": False,
        "tokenizer.chat_template": "{{ messages }}",
    }
    scalars.update(overrides.pop("scalars", {}))
    arrays = {
        "tokenizer.ggml.tokens": summarize_sequence(["a", "b"], item_type="string"),
        "tokenizer.ggml.token_type": summarize_sequence([1, 2], item_type="int32"),
        "tokenizer.ggml.merges": summarize_sequence(["a b"], item_type="string"),
    }
    arrays.update(overrides.pop("arrays", {}))
    return TokenizerIdentity.create(
        model_ref=overrides.pop("model_ref", "Qwen3.6-27B-Q4_K_M"),
        scalars=scalars,
        arrays=arrays,
        llama_cpp_revision=overrides.pop("llama_cpp_revision", "d" * 40),
        **overrides,
    )


def test_identity_changes_with_token_order_and_tokenize_implementation() -> None:
    baseline = _identity()
    reordered = _identity(
        arrays={
            "tokenizer.ggml.tokens": summarize_sequence(["b", "a"], item_type="string")
        }
    )
    new_runtime = _identity(llama_cpp_revision="e" * 40)

    assert baseline.hash != reordered.hash
    assert baseline.hash != new_runtime.hash


def test_round_trip_verifies_canonical_hash(tmp_path) -> None:
    path = tmp_path / "identity.json"
    identity = _identity()
    identity.write(path)

    loaded = TokenizerIdentity.load(path)

    assert loaded.hash == identity.hash
    assert loaded.payload == identity.payload


def test_tampered_identity_is_rejected(tmp_path) -> None:
    path = tmp_path / "identity.json"
    _identity().write(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["tokenizer_metadata"]["scalars"]["tokenizer.ggml.pre"] = "other"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        TokenizerIdentity.load(path)


def test_registered_metadata_is_required_exactly() -> None:
    identity = _identity()
    scalars = dict(identity.payload["tokenizer_metadata"]["scalars"])
    del scalars[TOKENIZER_SCALAR_KEYS[0]]

    with pytest.raises(ValueError, match="metadata incomplete"):
        TokenizerIdentity.create(
            model_ref="reader",
            scalars=scalars,
            arrays=identity.payload["tokenizer_metadata"]["arrays"],
            llama_cpp_revision="d" * 40,
        )

    assert set(identity.payload["tokenizer_metadata"]["arrays"]) == set(
        TOKENIZER_ARRAY_KEYS
    )


def test_runtime_uses_verified_identity_only_for_the_matching_reader(tmp_path) -> None:
    deps = RealDeps.__new__(RealDeps)
    deps._atlas_identity = SimpleNamespace(
        hash="atlas-fixture",
        payload={"build_spec": {"embedder": {"model": "fixture"}}},
    )
    deps.index_dir = tmp_path
    deps.config = SimpleNamespace(
        models={
            "roles": {
                "critic_jury": [],
                "reader_model": {"model": "Qwen3.6-27B-Q4_K_M"},
            }
        }
    )

    metadata = deps._review_instrument_metadata()

    assert metadata["reader_tokenizer"].startswith("gguf-tokenizer:")
    assert metadata["reader_tokenizer"].endswith(
        "af98a8928972c29a99be5604daff1afaff411a1ace658cfae1935500e1e799a0"
    )

    deps.config.models["roles"]["reader_model"]["model"] = "other-reader"
    metadata = deps._review_instrument_metadata()
    assert metadata["reader_tokenizer"] == "provider-default:other-reader:unverified"
