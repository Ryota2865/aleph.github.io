"""Build derived, machine-readable colophons for ALEPH works."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
GENERATED_BY = "scripts/build_work_colophon.py"
MODEL_ROLES = {
    "author_models": "author_primary",
    "scout_models": "scout",
    "jury_models": "critic_jury",
    "reader_models": "reader_model",
}
_POETICS_RE = re.compile(r"poetics_version\s*:\s*(-?\d+)")


def _read_json(path: Path) -> dict | list | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _poetics_version(decisions: Iterable[dict]) -> int | None:
    for row in decisions:
        match = _POETICS_RE.search(str(row.get("decision", "")))
        if match:
            return int(match.group(1))
    return None


def _models_for_role(calls: Iterable[dict], role: str) -> list[str]:
    models: list[str] = []
    for row in calls:
        if row.get("role") != role or not row.get("model"):
            continue
        model = str(row["model"])
        if model not in models:
            models.append(model)
    return models


def _canonical(work_dir: Path) -> bool:
    meta = _read_json(work_dir / "meta.json")
    if not isinstance(meta, dict):
        return True
    value = meta.get("canonical", True)
    return value if isinstance(value, bool) else True


def build_colophon(work_dir: Path) -> dict:
    decisions = _read_jsonl(work_dir / "decisions.jsonl")
    calls = _read_jsonl(work_dir / "calls.jsonl")
    payload = {
        "poetics_version": _poetics_version(decisions),
    }
    for field, role in MODEL_ROLES.items():
        payload[field] = _models_for_role(calls, role)
    payload.update(
        {
            "corpus_id": "aozora",
            "atlas_version": None,
            "canonical": _canonical(work_dir),
            "generated_by": GENERATED_BY,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return payload


def _without_generated_at(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    return {key: value for key, value in payload.items() if key != "generated_at"}


def write_colophon(work_dir: Path) -> bool:
    colophon_path = work_dir / "colophon.json"
    next_payload = build_colophon(work_dir)
    current_payload = _read_json(colophon_path)
    if _without_generated_at(current_payload) == _without_generated_at(next_payload):
        return False
    colophon_path.write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def iter_work_dirs(root: Path) -> list[Path]:
    works_root = root / "works"
    if not works_root.is_dir():
        return []
    return [
        path
        for path in sorted(works_root.iterdir())
        if path.is_dir() and (path / "decisions.jsonl").exists()
    ]


def _selected_work_dirs(root: Path, work_ids: list[str]) -> list[Path]:
    if not work_ids or work_ids == ["all"]:
        return iter_work_dirs(root)
    if "all" in work_ids:
        raise ValueError("'all' cannot be combined with explicit work ids")
    return [
        path
        for path in (root / "works" / work_id for work_id in work_ids)
        if "ablation" not in path.parts
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("selection", nargs="*", help="work ids or 'all' (default: all)")
    parser.add_argument("--work", action="append", default=[], help="specific work id")
    args = parser.parse_args(argv)

    work_ids = args.work + args.selection
    changed = 0
    for work_dir in _selected_work_dirs(ROOT, work_ids):
        if not (work_dir / "decisions.jsonl").exists():
            continue
        if write_colophon(work_dir):
            changed += 1
            print(f"{work_dir.name}: wrote colophon.json")
        else:
            print(f"{work_dir.name}: unchanged")
    print(f"changed: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
