"""L2 コーパス取り込み（PLAN §4.1）— PD全文をプレーン索引へ変換する."""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

import httpx
import numpy as np


@dataclass(frozen=True)
class IngestStats:
    n_works: int
    n_chunks: int
    dim: int


def _split_long_paragraph(paragraph: str, target_chars: int) -> list[str]:
    """極端に長い段落だけを、句点を保持した文のまとまりへ分ける."""
    if len(paragraph) <= 2 * target_chars:
        return [paragraph]
    sentences = [part for part in re.split(r"(?<=[。！？.!?])", paragraph) if part]
    if len(sentences) <= 1:
        return [paragraph]
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > target_chars:
            parts.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        parts.append(current)
    return parts


def chunk_text(text: str, target_chars: int = 2000, max_chunks: int | None = None) -> list[str]:
    """段落境界を保って目安サイズへ詰め、必要なら作品全体から均等抽出する."""
    if target_chars <= 0:
        raise ValueError("target_chars must be positive")
    if max_chunks is not None and max_chunks < 0:
        raise ValueError("max_chunks must be non-negative")

    paragraphs: list[str] = []
    for paragraph in text.splitlines():
        if paragraph:
            paragraphs.extend(_split_long_paragraph(paragraph, target_chars))

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        added_len = len(paragraph) + (1 if current else 0)
        if current and current_len + added_len > target_chars:
            chunks.append("\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len += added_len
    if current:
        chunks.append("\n".join(current))

    if max_chunks is not None and len(chunks) > max_chunks:
        if max_chunks == 0:
            return []
        indices = np.linspace(0, len(chunks) - 1, num=max_chunks, dtype=int)
        return [chunks[int(i)] for i in indices]
    return chunks


def iter_works(path: str | Path) -> Iterator[dict]:
    """1行1作品のJSONLを入力順に読む."""
    with open(path, encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            work = json.loads(line)
            missing = {"id", "title", "author", "text", "meta"} - work.keys()
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(f"{path}:{line_number}: missing fields: {names}")
            yield work


def ingest(
    corpus_path: str | Path,
    out_dir: str | Path,
    embedder: Callable[[list[str]], np.ndarray],
    *,
    target_chars: int = 2000,
    max_chunks_per_work: int = 30,
    limit: int | None = None,
) -> IngestStats:
    """コーパスを埋め込み行列と対応するJSONLメタデータへ取り込む."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    embedding_batches: list[np.ndarray] = []
    pending_texts: list[str] = []
    n_works = 0

    def embed_pending() -> None:
        if not pending_texts:
            return
        batch = np.asarray(embedder(list(pending_texts)), dtype=np.float32)
        if batch.ndim != 2 or batch.shape[0] != len(pending_texts):
            raise ValueError("embedder must return a 2D array with one row per text")
        embedding_batches.append(batch)
        pending_texts.clear()

    for work in iter_works(corpus_path):
        if limit is not None and n_works >= limit:
            break
        chunks = chunk_text(
            work["text"],
            target_chars=target_chars,
            max_chunks=max_chunks_per_work,
        )
        for seq, text in enumerate(chunks):
            records.append(
                {
                    "chunk_id": f"{work['id']}:{seq:04d}",
                    "work_id": work["id"],
                    "title": work["title"],
                    "author": work["author"],
                    "seq": seq,
                    "text": text,
                    "char_len": len(text),
                }
            )
            pending_texts.append(text)
            if len(pending_texts) >= 64:
                embed_pending()
        n_works += 1
        if n_works % 1000 == 0:
            print(f"ingest: {n_works} works, {len(records)} chunks", file=sys.stderr)
    embed_pending()

    if embedding_batches:
        dim = int(embedding_batches[0].shape[1])
        if any(batch.shape[1] != dim for batch in embedding_batches):
            raise ValueError("embedder returned inconsistent dimensions")
        embeddings = np.vstack(embedding_batches).astype(np.float32, copy=False)
    else:
        dim = int(getattr(embedder, "dim", 0))
        embeddings = np.empty((0, dim), dtype=np.float32)

    np.save(out_dir / "embeddings.npy", embeddings)
    with open(out_dir / "chunks.jsonl", "w", encoding="utf-8") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest = {
        "n_works": n_works,
        "n_chunks": len(records),
        "dim": dim,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return IngestStats(n_works=n_works, n_chunks=len(records), dim=dim)


class LlamaServerEmbedder:
    """llama-serverのOpenAI互換embeddings APIをバッチ呼び出しする."""

    def __init__(
        self,
        base_url: str,
        model: str,
        batch_size: int = 64,
        timeout: float = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size
        self.timeout = timeout

    def __call__(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        endpoint = (
            f"{self.base_url}/embeddings"
            if self.base_url.endswith("/v1")
            else f"{self.base_url}/v1/embeddings"
        )
        batches: list[np.ndarray] = []
        for start in range(0, len(texts), self.batch_size):
            inputs = texts[start : start + self.batch_size]
            for attempt in range(3):
                try:
                    response = httpx.post(
                        endpoint,
                        json={"model": self.model, "input": inputs},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    data = sorted(response.json()["data"], key=lambda item: item.get("index", 0))
                    batch = np.asarray([item["embedding"] for item in data], dtype=np.float32)
                    if batch.ndim != 2 or batch.shape[0] != len(inputs):
                        raise ValueError("embedding response size does not match input")
                    batches.append(batch)
                    break
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                    if attempt == 2:
                        raise RuntimeError("llama-server embedding request failed") from exc
                    time.sleep(2**attempt)
        return np.vstack(batches).astype(np.float32, copy=False)
