"""Authoritative termination-category vocabulary and deterministic mapping."""
from __future__ import annotations

from typing import Final


TERMINATION_CATEGORIES: Final[frozenset[str]] = frozenset(
    {"aesthetic_failure", "resource_stop", "publication_choice", "safety_or_rights"}
)


def classify_termination(stop_path: str | None, reason: str) -> str:
    """Map a stop signal to the four canonical categories.

    The default is aesthetic failure for compatibility with the existing pipeline;
    explicit L7 records are reconciled separately by :class:`WorkReader`.
    """
    normalised_path = stop_path.strip().lower() if isinstance(stop_path, str) else None
    if normalised_path in {"budget", "guard_limit", "resource", "closing_lost"}:
        return "resource_stop"
    if normalised_path in {"safety", "rights", "license"}:
        return "safety_or_rights"
    if normalised_path in {"publication_choice", "author_declined"}:
        return "publication_choice"
    if "上限" in reason or "人間承認待ち" in reason or "予算" in reason:
        return "resource_stop"
    if "著者が非公開を選択した" in reason:
        return "publication_choice"
    if any(token in reason for token in ("安全", "権利", "ライセンス")):
        return "safety_or_rights"
    return "aesthetic_failure"
