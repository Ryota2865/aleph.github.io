"""One authoritative, read-only interpretation of a work directory."""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from aleph.core.artifacts import Work
from aleph.core.loop import Checkpoint, State
from aleph.core.transition_commit import (
    ReplayError,
    SCHEMA_VERSION,
    audit_history,
    has_modern_event_shape,
    strict_replay,
)


class Publication(str, Enum):
    PUBLISH = "PUBLISH"
    SHELVE = "SHELVE"
    DISCARD = "DISCARD"
    UNDECIDED = "UNDECIDED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DraftSnapshot:
    version: int | None
    path: str
    text: str
    selected_by: str


@dataclass(frozen=True)
class WorkSnapshot:
    work_id: str
    title: str
    lifecycle: State | None
    step: int | None
    publication: Publication
    published_at: str | None
    audience: str | None
    best_draft: DraftSnapshot | None
    latest_draft: DraftSnapshot | None
    effective_constraints: tuple[str, ...]
    poetics_version: int | None
    atlas_identity: dict[str, Any] | None
    costs: dict[str, float]
    canonical: bool | None
    canonical_arm: str | None
    last_decision_ts: str | None
    warnings: tuple[str, ...]
    provenance: dict[str, tuple[str, ...]]

    @property
    def is_published(self) -> bool:
        return self.publication == Publication.PUBLISH

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lifecycle"] = self.lifecycle.value if self.lifecycle else None
        payload["publication"] = self.publication.value
        return payload


def _read_json(path: Path, warnings: list[str], label: str) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"{label} is unreadable: {type(exc).__name__}")
        return None


def _read_jsonl(path: Path, warnings: list[str], label: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        warnings.append(f"{label} is missing")
        return []
    except OSError as exc:
        warnings.append(f"{label} is unreadable: {type(exc).__name__}")
        return []
    rows: list[dict[str, Any]] = []
    for position, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"{label} line {position} is invalid JSON")
            continue
        if not isinstance(row, dict):
            warnings.append(f"{label} line {position} is not an object")
            continue
        rows.append(row)
    return rows


class WorkReader:
    """Interpret all repeated work semantics behind one small interface."""

    def __init__(self, work_dir: Path) -> None:
        self.work_dir = Path(work_dir)
        self.work_id = self.work_dir.name
        self.work = Work(self.work_dir.parent, self.work_id)

    def snapshot(self) -> WorkSnapshot:
        warnings: list[str] = []
        provenance: dict[str, tuple[str, ...]] = {}
        rows = _read_jsonl(self.work_dir / "decisions.jsonl", warnings, "decisions.jsonl")
        l0 = [row for row in rows if row.get("layer") == "L0"]
        modern = any(
            (type(row.get("schema_version")) is int and row.get("schema_version") == SCHEMA_VERSION)
            or has_modern_event_shape(row)
            for row in l0
        )

        replayed: Checkpoint | None = None
        if modern:
            try:
                replayed = strict_replay(self.work_id, self.work_dir / "decisions.jsonl")
                provenance["lifecycle"] = ("decisions.jsonl#strict-replay",)
            except (ReplayError, OSError, ValueError) as exc:
                warnings.append(f"modern L0 replay failed closed: {exc}")
        else:
            checkpoint = self._checkpoint(warnings)
            replayed = checkpoint
            if checkpoint is not None:
                provenance["lifecycle"] = ("checkpoint.json#legacy",)
            if l0:
                try:
                    warnings.extend(audit_history(self.work))
                except (KeyError, ReplayError, OSError, TypeError, ValueError) as exc:
                    warnings.append(f"legacy L0 audit failed: {exc}")

        checkpoint = self._checkpoint(warnings)
        if modern and replayed is not None:
            if checkpoint is None:
                warnings.append("checkpoint is missing while modern replay is available")
            elif checkpoint != replayed:
                warnings.append("checkpoint differs from authoritative strict replay")

        lifecycle = replayed.state if replayed else None
        payload = replayed.payload if replayed else self._legacy_payload(warnings)
        publication = self._publication(lifecycle, payload, l0, modern)
        published_at = self._published_at(rows)
        audience = str(payload["audience"]) if payload.get("audience") else self._legacy_audience(rows)
        title = self._title(warnings)
        best, latest = self._drafts(rows, publication, warnings)
        constraints = self._constraints(warnings)
        poetics_version, atlas_identity = self._colophon(rows, warnings)
        costs = self._costs(warnings)
        canonical, canonical_arm = self._canonical(payload, warnings)

        provenance.update(
            {
                "publication": ("decisions.jsonl",),
                "title": ("final/meta.json", "title.txt", "seed.json"),
                "drafts": ("decisions.jsonl", "reviews/trajectory.jsonl", "drafts/", "final/text.md"),
                "constraints": ("seed.json#experiment.criteria_constraints",),
                "poetics_atlas": ("colophon.json", "decisions.jsonl"),
                "costs": ("calls.jsonl",),
            }
        )
        return WorkSnapshot(
            work_id=self.work_id,
            title=title,
            lifecycle=lifecycle,
            step=replayed.step if replayed else None,
            publication=publication,
            published_at=published_at,
            audience=audience,
            best_draft=best,
            latest_draft=latest,
            effective_constraints=constraints,
            poetics_version=poetics_version,
            atlas_identity=atlas_identity,
            costs=costs,
            canonical=canonical,
            canonical_arm=canonical_arm,
            last_decision_ts=(str(rows[-1].get("ts")) if rows and rows[-1].get("ts") else None),
            warnings=tuple(dict.fromkeys(warnings)),
            provenance=provenance,
        )

    def _checkpoint(self, warnings: list[str]) -> Checkpoint | None:
        try:
            return Checkpoint.load(self.work_dir)
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            warnings.append(f"checkpoint is invalid: {type(exc).__name__}")
            return None

    def _legacy_payload(self, warnings: list[str]) -> dict[str, Any]:
        """Salvage non-state display context without trusting an invalid checkpoint state."""
        raw = _read_json(self.work_dir / "checkpoint.json", warnings, "checkpoint.json")
        if not isinstance(raw, dict):
            return {}
        payload = raw.get("payload")
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _publication(
        lifecycle: State | None,
        payload: dict[str, Any],
        l0: list[dict[str, Any]],
        modern: bool,
    ) -> Publication:
        if not modern:
            for row in reversed(l0):
                decision = row.get("decision")
                if decision in {"FINISH->PUBLISH", "FINISH->SHELVE", "FINISH->DISCARD"}:
                    return Publication(decision.removeprefix("FINISH->"))
        if lifecycle is None:
            return Publication.UNKNOWN
        if lifecycle == State.PUBLISH:
            return Publication.PUBLISH
        if lifecycle == State.SHELVE:
            if modern and payload.get("publication_disposition") == State.PUBLISH.value:
                return Publication.PUBLISH
            return Publication.SHELVE
        if lifecycle == State.DISCARD:
            return Publication.DISCARD
        return Publication.UNDECIDED

    def _published_at(self, rows: list[dict[str, Any]]) -> str | None:
        try:
            meta = json.loads((self.work_dir / "final" / "meta.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = None
        if isinstance(meta, dict) and isinstance(meta.get("published_at"), str):
            return meta["published_at"]
        event_times: list[str] = []
        for row in rows:
            decision = str(row.get("decision", ""))
            payload = row.get("payload")
            disposition = payload.get("publication_disposition") if isinstance(payload, dict) else None
            if (decision == "FINISH->PUBLISH" or disposition == "PUBLISH") and row.get("ts"):
                event_times.append(str(row["ts"]))
        return max(event_times, default=None)

    @staticmethod
    def _legacy_audience(rows: list[dict[str, Any]]) -> str | None:
        for row in rows:
            decision = str(row.get("decision", ""))
            if row.get("layer") == "L1" and "配合比" in decision:
                return decision.split(":", 1)[-1].strip()
        return None

    def _title(self, warnings: list[str]) -> str:
        meta = _read_json(self.work_dir / "final" / "meta.json", warnings, "final/meta.json")
        if isinstance(meta, dict) and isinstance(meta.get("title"), str) and meta["title"].strip():
            return meta["title"].strip()
        title_path = self.work_dir / "title.txt"
        try:
            title = title_path.read_text(encoding="utf-8").strip()
            if title:
                return title
        except OSError:
            pass
        seed = _read_json(self.work_dir / "seed.json", warnings, "seed.json")
        if isinstance(seed, dict):
            for key in ("title", "hint", "seed"):
                if seed.get(key):
                    return str(seed[key])
        return self.work_id

    def _drafts(
        self,
        rows: list[dict[str, Any]],
        publication: Publication,
        warnings: list[str],
    ) -> tuple[DraftSnapshot | None, DraftSnapshot | None]:
        versions = sorted(
            int(path.stem[1:])
            for path in self.work_dir.joinpath("drafts").glob("v*.md")
            if path.stem[1:].isdigit()
        )
        latest = self._draft(versions[-1], "latest") if versions else None
        explicit = next(
            (row["best_version"] for row in reversed(rows) if type(row.get("best_version")) is int),
            None,
        )
        trajectory = _read_jsonl(
            self.work_dir / "reviews" / "trajectory.jsonl", warnings, "reviews/trajectory.jsonl"
        )
        scored: list[tuple[float, int]] = []
        for position, row in enumerate(trajectory, start=1):
            version, score = row.get("version"), row.get("mean_score")
            if type(version) is not int or type(score) not in (int, float) or not math.isfinite(float(score)):
                warnings.append(f"trajectory row {position} has invalid version or mean_score")
                continue
            scored.append((float(score), version))
        selected = explicit
        selected_by = "decision:best_version"
        if selected is None and scored:
            selected = max(scored)[1]
            selected_by = "trajectory:max_mean_score"
        if selected is None and versions:
            selected = versions[-1]
            selected_by = "drafts:latest_fallback"
        best = self._draft(selected, selected_by) if selected is not None else None
        if selected is not None and best is None:
            warnings.append(f"selected draft v{selected} is missing")
            best = latest
        final_path = self.work_dir / "final" / "text.md"
        if publication == Publication.PUBLISH:
            try:
                final_text = final_path.read_text(encoding="utf-8")
            except OSError:
                warnings.append("published work is missing final/text.md")
            else:
                if best is not None and final_text != best.text:
                    warnings.append("final/text.md differs from the selected best draft")
                best = DraftSnapshot(
                    version=best.version if best else None,
                    path=str(final_path),
                    text=final_text,
                    selected_by="published:final/text.md",
                )
        return best, latest

    def _draft(self, version: int, selected_by: str) -> DraftSnapshot | None:
        path = self.work_dir / "drafts" / f"v{version}.md"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return DraftSnapshot(version, str(path), text, selected_by)

    def _constraints(self, warnings: list[str]) -> tuple[str, ...]:
        seed = _read_json(self.work_dir / "seed.json", warnings, "seed.json")
        if not isinstance(seed, dict):
            return ()
        experiment = seed.get("experiment")
        if not isinstance(experiment, dict):
            return ()
        value = experiment.get("criteria_constraints")
        return (value,) if isinstance(value, str) and value.strip() else ()

    def _colophon(
        self, rows: list[dict[str, Any]], warnings: list[str]
    ) -> tuple[int | None, dict[str, Any] | None]:
        colophon_path = self.work_dir / "colophon.json"
        colophon = _read_json(colophon_path, warnings, "colophon.json")
        if not isinstance(colophon, dict):
            warnings.append("colophon is missing")
            return self._poetics_from_decisions(rows), None
        poetics = colophon.get("poetics_version")
        if type(poetics) is not int:
            poetics = self._poetics_from_decisions(rows)
            warnings.append("colophon has no valid poetics_version")
        atlas = {
            "corpus_id": colophon.get("corpus_id"),
            "atlas_version": colophon.get("atlas_version"),
        }
        decisions_path = self.work_dir / "decisions.jsonl"
        try:
            if colophon_path.stat().st_mtime < decisions_path.stat().st_mtime:
                warnings.append("colophon is older than decisions.jsonl")
        except OSError:
            pass
        return poetics, atlas

    @staticmethod
    def _poetics_from_decisions(rows: list[dict[str, Any]]) -> int | None:
        pattern = re.compile(r"poetics_version\s*:\s*(-?\d+)")
        for row in reversed(rows):
            match = pattern.search(str(row.get("decision", "")))
            if match:
                return int(match.group(1))
        return None

    def _costs(self, warnings: list[str]) -> dict[str, float]:
        rows = _read_jsonl(self.work_dir / "calls.jsonl", warnings, "calls.jsonl")
        total = 0.0
        for position, row in enumerate(rows, start=1):
            cost = row.get("cost_usd", 0.0)
            if type(cost) not in (int, float) or not math.isfinite(float(cost)):
                warnings.append(f"calls row {position} has invalid cost_usd")
                continue
            total += float(cost)
        return {"calls_usd": total}

    def _canonical(
        self, payload: dict[str, Any], warnings: list[str]
    ) -> tuple[bool | None, str | None]:
        meta = _read_json(self.work_dir / "meta.json", warnings, "meta.json")
        canonical: bool | None = True
        if isinstance(meta, dict) and "canonical" in meta:
            value = meta["canonical"]
            if type(value) is bool:
                canonical = value
            else:
                canonical = None
                warnings.append("meta.json canonical must be bool")
        arm = payload.get("canonical_arm")
        return canonical, str(arm) if arm is not None else None
