"""Repository-wide current state built exclusively from :mod:`work_snapshot`."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from aleph.core.config import ConfigError, load_config
from aleph.core.work_snapshot import WorkReader, WorkSnapshot


@dataclass(frozen=True)
class RepositorySnapshot:
    works: tuple[WorkSnapshot, ...]
    budget: dict[str, Any]
    experiments: tuple[dict[str, str], ...]
    active_jobs: tuple[dict[str, Any], ...]
    formal_audits: tuple[dict[str, Any], ...]
    deadlines: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    provenance: dict[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "works": [work.to_dict() for work in self.works],
            "budget": self.budget,
            "experiments": [dict(item) for item in self.experiments],
            "active_jobs": [dict(item) for item in self.active_jobs],
            "formal_audits": [dict(item) for item in self.formal_audits],
            "deadlines": [dict(item) for item in self.deadlines],
            "warnings": list(self.warnings),
            "provenance": {key: list(value) for key, value in self.provenance.items()},
        }

    def readme_status_markdown(self, *, language: str = "ja") -> str:
        """Render the small current-state section; narrative history stays hand-written."""
        published = [work for work in self.works if work.is_published]
        terminal = [work for work in self.works if work.lifecycle and work.lifecycle.value in {"PUBLISH", "SHELVE", "DISCARD"}]
        latest = self.works[-1].work_id if self.works else "—"
        if language == "en":
            return "\n".join(
                [
                    "<!-- repository-snapshot:start -->",
                    f"- Works recorded: {len(self.works)} (through {latest}); terminal: {len(terminal)}.",
                    f"- Published works: {len(published)} — "
                    + (", ".join(f"{work.work_id} {work.title}" for work in published) or "none"),
                    f"- Formal audit artifacts: {len(self.formal_audits)}; tests and formal audit verdicts are reported separately.",
                    "<!-- repository-snapshot:end -->",
                ]
            )
        if language != "ja":
            raise ValueError("language must be 'ja' or 'en'")
        return "\n".join(
            [
                "<!-- repository-snapshot:start -->",
                f"- 作品記録: {len(self.works)}作（{latest}まで）、終端到達: {len(terminal)}作。",
                f"- 公開作品: {len(published)}作 — "
                + ("、".join(f"{work.work_id}「{work.title}」" for work in published) or "なし"),
                f"- formal audit artifact: {len(self.formal_audits)}件。tests greenとformal audit判定は分離して表示する。",
                "<!-- repository-snapshot:end -->",
            ]
        )


class RepositoryReader:
    """Aggregate work, budget, experiment, job, audit, and deadline meanings."""

    def __init__(
        self,
        root: Path,
        *,
        today: date | None = None,
        budget_config: dict[str, Any] | None = None,
    ) -> None:
        self.root = Path(root)
        self.today = today or date.today()
        self.budget_config = budget_config

    def snapshot(self) -> RepositorySnapshot:
        warnings: list[str] = []
        works = self._works(warnings)
        epochs = sorted({work.author_epoch for work in works if work.author_epoch})
        if len(epochs) > 1:
            warnings.append(
                "cross-author-epoch aggregation is non-comparable: " + ", ".join(epochs)
            )
        budget, publish_cap = self._budget(works, warnings)
        deadlines = self._deadlines(publish_cap)
        for deadline in deadlines:
            if deadline["expired"]:
                warnings.append(
                    f"deadline expired: {deadline['decision']} required review by {deadline['due']}"
                )
        return RepositorySnapshot(
            works=works,
            budget=budget,
            experiments=self._experiments(works, warnings),
            active_jobs=self._active_jobs(),
            formal_audits=self._formal_audits(),
            deadlines=deadlines,
            warnings=tuple(dict.fromkeys(warnings)),
            provenance={
                "works": ("works/*",),
                "budget": ("config/budgets.yaml", "state/budget.json"),
                "experiments": ("works/*/seed.json#experiment.id",),
                "active_jobs": ("state/run_<work_id>.pid",),
                "formal_audits": ("audits/", "reports/*AUDIT*.md"),
                "deadlines": ("PLAN_CHANGELOG.md", "config/budgets.yaml"),
            },
        )

    def _works(self, warnings: list[str]) -> tuple[WorkSnapshot, ...]:
        works_root = self.root / "works"
        if not works_root.is_dir():
            return ()
        snapshots: list[WorkSnapshot] = []
        for path in sorted(works_root.iterdir()):
            if not path.is_dir() or not path.name.startswith("w"):
                continue
            snapshot = WorkReader(path).snapshot()
            snapshots.append(snapshot)
            warnings.extend(f"{snapshot.work_id}: {warning}" for warning in snapshot.warnings)
        return tuple(snapshots)

    def _budget(
        self, works: tuple[WorkSnapshot, ...], warnings: list[str]
    ) -> tuple[dict[str, Any], int | None]:
        if self.budget_config is None:
            try:
                config = load_config(self.root)
                budgets = config.budgets
            except (ConfigError, FileNotFoundError, OSError, KeyError, ValueError):
                warnings.append("repository config is unavailable; budget snapshot is empty")
                return {}, None
        else:
            budgets = self.budget_config
        ledger_path = self.root / "state" / "budget.json"
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            ledger = {}
        except (OSError, json.JSONDecodeError):
            warnings.append("state/budget.json is unreadable")
            ledger = {}
        api_ledger = ledger.get("ledgers", {}).get("api", {}) if isinstance(ledger, dict) else {}
        publish = budgets.get("publish", {})
        api = budgets.get("api", {})
        period = api_ledger.get("period_key")
        publish_count = 0
        if isinstance(period, str):
            for work in works:
                if work.is_published and str(work.published_at or "").startswith(period):
                    publish_count += 1
        cap = publish.get("max_per_month")
        ledger_limits = {
            "api": (api.get("usd_per_month", 0.0), "month"),
            "harness": (budgets.get("harness", {}).get("calls_per_day", 0.0), "day"),
            "local": (budgets.get("local", {}).get("gpu_hours_per_day", 0.0), "day"),
        }
        ledger_status = {
            name: {
                "spent": ledger.get("ledgers", {}).get(name, {}).get("spent", 0.0),
                "limit": limit,
                "period": period_name,
            }
            for name, (limit, period_name) in ledger_limits.items()
        }
        return {
            "period_key": period,
            "api_spent": api_ledger.get("spent", 0.0),
            "api_cap": api.get("usd_per_month", 0.0),
            "usd_per_work": api.get("usd_per_work", 0.0),
            "work_spent": ledger.get("work_spent", {}) if isinstance(ledger, dict) else {},
            "publish_count": publish_count,
            "publish_cap": cap,
            "ledgers": ledger.get("ledgers", {}) if isinstance(ledger, dict) else {},
            "ledger_status": ledger_status,
        }, cap if type(cap) is int else None

    def _experiments(
        self, works: tuple[WorkSnapshot, ...], warnings: list[str]
    ) -> tuple[dict[str, str], ...]:
        out: list[dict[str, str]] = []
        for work in works:
            path = self.root / "works" / work.work_id / "seed.json"
            try:
                seed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            experiment = seed.get("experiment") if isinstance(seed, dict) else None
            experiment_id = experiment.get("id") if isinstance(experiment, dict) else None
            if isinstance(experiment_id, str) and experiment_id:
                out.append({"experiment_id": experiment_id, "work_id": work.work_id})
        return tuple(out)

    def _active_jobs(self) -> tuple[dict[str, Any], ...]:
        state = self.root / "state"
        if not state.is_dir():
            return ()
        jobs: list[dict[str, Any]] = []
        for path in sorted(state.glob("run_*.pid")):
            work_id = path.stem.removeprefix("run_")
            try:
                pid = int(path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                jobs.append({"work_id": work_id, "pid": None, "alive": None})
                continue
            try:
                os.kill(pid, 0)
            except OSError:
                alive = False
            else:
                alive = True
            jobs.append({"work_id": work_id, "pid": pid, "alive": alive})
        return tuple(jobs)

    def _formal_audits(self) -> tuple[dict[str, Any], ...]:
        paths = sorted((self.root / "audits").glob("*.md"))
        paths += sorted((self.root / "reports").glob("*AUDIT*.md"))
        audits: list[dict[str, Any]] = []
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            verdict = "UNKNOWN"
            explicit = re.findall(r"(?:判定|verdict)\s*[:：]\s*\*{0,2}(PASS|FAIL)", text, re.I)
            if explicit:
                verdict = explicit[-1].upper()
            audits.append({"path": str(path.relative_to(self.root)), "verdict": verdict})
        return tuple(audits)

    def _deadlines(self, publish_cap: int | None) -> tuple[dict[str, Any], ...]:
        if publish_cap != 999:
            return ()
        due = date(2026, 8, 1)
        return (
            {
                "decision": "publish.max_per_month=999 temporary July exception",
                "due": due.isoformat(),
                "expired": self.today >= due,
                "required_action": "review with 4 as the initial value; do not mutate automatically",
            },
        )
