"""Compatibility adapter for authoritative publication status."""
from __future__ import annotations

from pathlib import Path

from aleph.core.work_snapshot import WorkReader


def is_published(work_dir: Path) -> bool:
    """Return whether a work is publishable according to its L0 history.

    Modern streams are replayed strictly. Historical streams without schema metadata
    retain compatibility through their last lifecycle publication decision. Invalid or
    ambiguous history fails closed.
    """
    try:
        return WorkReader(Path(work_dir)).snapshot().is_published
    except (OSError, ValueError):
        return False
