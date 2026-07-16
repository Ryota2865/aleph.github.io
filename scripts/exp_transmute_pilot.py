"""Run the S-2 transmutation measurement pilot.

The pilot keeps aleph.materia.transmute unchanged and measures each generated
card on two axes:

- content_distance: embedding cosine between source and generated text.
- form_fidelity: ratio of source structural features retained in the output.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from aleph.core.budget import Budget
from aleph.core.config import load_config
from aleph.core.llm import CallLogger, Message, Router
from aleph.core.local import LocalRuntime
from aleph.explore.corpus import LlamaServerEmbedder
from aleph.materia.transmute import transmute

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKS = ROOT / "corpus" / "secondary" / "works.jsonl"
WORK_ID = "exp-s2"

LAW_FEATURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("law.article", re.compile(r"(?:第[一二三四五六七八九十百千〇零0-9０-９]+条)")),
    ("law.paragraph", re.compile(r"(?m)^[ \t　]*(?:[0-9０-９]+)[ \t　]")),
    ("law.item", re.compile(r"(?m)^[ \t　]*[一二三四五六七八九十]+[ \t　]")),
    ("law.definition", re.compile(r"「[^」]{1,80}」(?:と|を)は?|「[^」]{1,80}」[^。\n]{0,80}をいう")),
    ("law.proviso", re.compile(r"(?:ただし|但し)")),
)

RFC_FEATURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rfc.must", re.compile(r"\bMUST(?:\s+NOT)?\b")),
    ("rfc.should", re.compile(r"\bSHOULD(?:\s+NOT)?\b")),
    ("rfc.may", re.compile(r"\bMAY\b")),
    ("rfc.section", re.compile(r"(?m)^\s*\d+(?:\.\d+)*\.\s+\S")),
    ("rfc.abstract", re.compile(r"(?mi)^\s*Abstract\s*$")),
)


@dataclass(frozen=True)
class PilotResult:
    work_id: str
    title: str
    form_type: str
    content_distance: float
    form_fidelity: float
    source_features: tuple[str, ...]
    generated_features: tuple[str, ...]
    generated_chars: int
    final_cos: float | None


def extract_structure_features(form_type: str, text: str) -> set[str]:
    """Extract detector feature names for a secondary corpus form type."""
    if form_type == "law":
        patterns = LAW_FEATURE_PATTERNS
    elif form_type == "rfc":
        patterns = RFC_FEATURE_PATTERNS
    else:
        return set()
    return {name for name, pattern in patterns if pattern.search(text)}


def retained_feature_ratio(source_features: Iterable[str], generated_features: Iterable[str]) -> float:
    """Return the share of source structure features that remain in generated text."""
    source = set(source_features)
    if not source:
        return 0.0
    generated = set(generated_features)
    return len(source & generated) / len(source)


def form_fidelity(form_type: str, source_text: str, generated_text: str) -> float:
    """Measure retained structure using the detector for the source form type."""
    source_features = extract_structure_features(form_type, source_text)
    generated_features = extract_structure_features(form_type, generated_text)
    return retained_feature_ratio(source_features, generated_features)


def embedding_cosine(embedder: Callable[[list[str]], np.ndarray], source_text: str, generated_text: str) -> float:
    vectors = np.asarray(embedder([source_text, generated_text]), dtype=np.float64)
    if vectors.ndim != 2 or vectors.shape[0] != 2:
        raise ValueError("embedder must return a 2D array with one row per input text")
    a, b = vectors[0], vectors[1]
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if not norm_a or not norm_b:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def load_works(path: Path, *, limit: int | None = None) -> list[dict]:
    works = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            works.append(json.loads(line))
            if limit is not None and len(works) >= limit:
                break
    return works


def default_llm(root: Path, calls_log: Path, *, work_id: str = WORK_ID) -> Callable[[str], str]:
    config = load_config(root)
    logger = CallLogger(calls_log, secrets=config.secrets.values())
    budget = Budget(config)
    router = Router(config, logger, budget, local_runtime=LocalRuntime(config))

    def scout(prompt: str) -> str:
        return router.call("scout", [Message("user", prompt)], work_id=work_id).text

    return scout


def default_embedder(root: Path) -> LlamaServerEmbedder:
    config = load_config(root)
    provider = config.models["providers"]["llamacpp"]
    embedder_role = config.models["roles"]["embedder"]
    return LlamaServerEmbedder(
        base_url=provider["base_url"],
        model=embedder_role["model"],
    )


def run_pilot(
    works_path: Path,
    *,
    theme: str,
    llm: Callable[[str], str],
    embedder: Callable[[list[str]], np.ndarray],
    limit: int | None = None,
) -> list[PilotResult]:
    results = []
    for work in load_works(works_path, limit=limit):
        source_text = str(work.get("text", ""))
        form_type = str(work.get("form_type", ""))
        source_biblio = {
            "id": work.get("id"),
            "title": work.get("title"),
            "author": work.get("author"),
            "corpus": work.get("corpus"),
            "form_type": form_type,
            "meta": work.get("meta", {}),
        }
        card = transmute(
            source_text,
            theme,
            llm,
            embedder,
            max_iters=1,
            source_biblio=source_biblio,
        )
        generated = str(card.get("content", ""))
        source_features = extract_structure_features(form_type, source_text)
        generated_features = extract_structure_features(form_type, generated)
        results.append(
            PilotResult(
                work_id=str(work.get("id", "")),
                title=str(work.get("title", "")),
                form_type=form_type,
                content_distance=embedding_cosine(embedder, source_text, generated),
                form_fidelity=retained_feature_ratio(source_features, generated_features),
                source_features=tuple(sorted(source_features)),
                generated_features=tuple(sorted(generated_features)),
                generated_chars=len(generated),
                final_cos=_final_cos(card),
            )
        )
    return results


def _final_cos(card: dict) -> float | None:
    value = (card.get("provenance") or {}).get("final_cos")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stats(values: list[float]) -> str:
    if not values:
        return "n/a"
    arr = np.asarray(values, dtype=np.float64)
    return (
        f"n={len(values)}, min={float(np.min(arr)):.4f}, "
        f"median={float(np.median(arr)):.4f}, max={float(np.max(arr)):.4f}"
    )


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    if float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _md_cell(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def write_report(results: list[PilotResult], path: Path, *, source_path: Path, theme: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    distances = [result.content_distance for result in results]
    fidelities = [result.form_fidelity for result in results]
    correlation = _pearson(distances, fidelities)
    correlation_text = "n/a" if correlation is None else f"{correlation:.4f}"

    lines = [
        f"# EXP transmute pilot {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Inputs",
        "",
        f"- works: `{source_path}`",
        f"- theme: {_md_cell(theme)}",
        f"- n: {len(results)}",
        "",
        "## Per-Source Measurements",
        "",
        "| id | form_type | title | content_distance | form_fidelity | source_features | generated_features | generated_chars | notes |",
        "|---|---|---|---:|---:|---|---|---:|---|",
    ]
    for result in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(result.work_id),
                    _md_cell(result.form_type),
                    _md_cell(result.title),
                    f"{result.content_distance:.4f}",
                    f"{result.form_fidelity:.4f}",
                    _md_cell(", ".join(result.source_features)),
                    _md_cell(", ".join(result.generated_features)),
                    str(result.generated_chars),
                    "",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Scatter Summary",
            "",
            f"- content_distance: {_stats(distances)}",
            f"- form_fidelity: {_stats(fidelities)}",
            f"- Pearson r(content_distance, form_fidelity): {correlation_text}",
            "",
            "## Raw Values",
            "",
            "| id | form_type | content_distance | form_fidelity | transmute_final_cos |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for result in results:
        final_cos = "n/a" if result.final_cos is None else f"{result.final_cos:.4f}"
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(result.work_id),
                    _md_cell(result.form_type),
                    f"{result.content_distance:.4f}",
                    f"{result.form_fidelity:.4f}",
                    final_cos,
                ]
            )
            + " |"
        )

    lines.extend(["", "## Findings", "", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    today = datetime.now().strftime("%Y%m%d")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--works", type=Path, default=DEFAULT_WORKS, help="secondary works.jsonl path")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "reports" / f"EXP_transmute_pilot_{today}.md",
        help="output markdown report path",
    )
    parser.add_argument(
        "--calls-log",
        type=Path,
        default=Path("/tmp") / f"aleph_exp_s2_calls_{today}.jsonl",
        help="Router call log path for the scout role",
    )
    parser.add_argument("--theme", default="観測と記憶", help="theme passed to transmute")
    parser.add_argument("--limit", type=int, default=None, help="limit works processed")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    llm = default_llm(ROOT, args.calls_log)
    embedder = default_embedder(ROOT)
    results = run_pilot(
        args.works,
        theme=args.theme,
        llm=llm,
        embedder=embedder,
        limit=args.limit,
    )
    write_report(results, args.out, source_path=args.works, theme=args.theme)
    print(f"wrote report for {len(results)} works to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
