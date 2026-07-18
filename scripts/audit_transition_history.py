"""Read-only audit of checkpoint/L0 event continuity for every work."""
from __future__ import annotations

import argparse
from pathlib import Path

from aleph.core.artifacts import Work
from aleph.core.transition_commit import audit_history


def render(works_root: Path) -> str:
    lines = ["# Transition history audit", ""]
    for work_dir in sorted(works_root.glob("w[0-9][0-9][0-9][0-9]")):
        warnings = audit_history(Work(works_root, work_dir.name))
        lines.append(f"## {work_dir.name}")
        lines.append("")
        if warnings:
            lines.extend(f"- {warning}" for warning in warnings)
        else:
            lines.append("- strict replay: PASS")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--works", type=Path, default=Path("works"))
    args = parser.parse_args()
    print(render(args.works))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
