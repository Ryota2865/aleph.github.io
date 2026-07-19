"""Render the authoritative RepositorySnapshot as audit JSON or a compact report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aleph.core.repository_snapshot import RepositoryReader, RepositorySnapshot


ROOT = Path(__file__).resolve().parents[1]


def render_report(snapshot: RepositorySnapshot) -> str:
    published = [work for work in snapshot.works if work.is_published]
    lines = [
        "# RepositorySnapshot audit",
        "",
        f"- works: {len(snapshot.works)}",
        f"- published: {len(published)}",
        f"- experiments: {len(snapshot.experiments)}",
        f"- active jobs: {sum(job.get('alive') is True for job in snapshot.active_jobs)}",
        f"- warnings: {len(snapshot.warnings)}",
        "",
        "## Warnings",
        "",
    ]
    lines.extend(f"- {warning}" for warning in snapshot.warnings)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    args = parser.parse_args(argv)
    snapshot = RepositoryReader(args.root).snapshot()
    if args.format == "report":
        print(render_report(snapshot), end="")
    else:
        print(json.dumps(snapshot.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
