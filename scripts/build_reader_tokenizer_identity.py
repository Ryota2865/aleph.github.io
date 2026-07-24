#!/usr/bin/env python3
"""Extract the registered tokenizer metadata from a local GGUF."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from aleph.core.tokenizer_identity import (
    TOKENIZER_ARRAY_KEYS,
    TOKENIZER_SCALAR_KEYS,
    TokenizerIdentity,
    summarize_sequence,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gguf", required=True, type=Path)
    parser.add_argument("--model-ref", required=True)
    parser.add_argument("--llama-cpp-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = _args()
    gguf_py = args.llama_cpp_root / "gguf-py"
    if not args.gguf.is_file() or not gguf_py.is_dir():
        raise SystemExit("GGUF or llama.cpp gguf-py directory is missing")
    sys.path.insert(0, str(gguf_py))
    from gguf import GGUFReader  # type: ignore[import-not-found]

    revision = subprocess.run(
        ["git", "-C", str(args.llama_cpp_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    reader = GGUFReader(str(args.gguf), "r")
    missing = [
        key
        for key in (*TOKENIZER_SCALAR_KEYS, *TOKENIZER_ARRAY_KEYS)
        if key not in reader.fields
    ]
    if missing:
        raise SystemExit(f"required GGUF tokenizer metadata missing: {missing}")

    scalars = {key: reader.fields[key].contents() for key in TOKENIZER_SCALAR_KEYS}
    arrays = {}
    for key in TOKENIZER_ARRAY_KEYS:
        field = reader.fields[key]
        item_type = field.types[-1].name.lower()
        arrays[key] = summarize_sequence(
            (field.contents(i) for i in range(len(field.data))),
            item_type=item_type,
        )
    identity = TokenizerIdentity.create(
        model_ref=args.model_ref,
        scalars=scalars,
        arrays=arrays,
        llama_cpp_revision=revision,
    )
    identity.write(args.output)
    print(identity.hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
