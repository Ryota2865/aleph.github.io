"""Repository-wide current state built exclusively from :mod:`work_snapshot`."""
from __future__ import annotations

import json
import os
import re
import subprocess
from copy import deepcopy
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
    assurance: dict[str, Any]
    design_state: dict[str, Any]
    deadlines: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    provenance: dict[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "works": [work.to_dict() for work in self.works],
            "budget": deepcopy(self.budget),
            "experiments": [dict(item) for item in self.experiments],
            "active_jobs": [dict(item) for item in self.active_jobs],
            "formal_audits": [dict(item) for item in self.formal_audits],
            "assurance": deepcopy(self.assurance),
            "design_state": deepcopy(self.design_state),
            "deadlines": [dict(item) for item in self.deadlines],
            "warnings": list(self.warnings),
            "provenance": {key: list(value) for key, value in self.provenance.items()},
        }

    def readme_status_markdown(self, *, language: str = "ja") -> str:
        """Render the small current-state section; narrative history stays hand-written."""
        published = [work for work in self.works if work.is_published]
        terminal = [work for work in self.works if work.lifecycle and work.lifecycle.value in {"PUBLISH", "SHELVE", "DISCARD"}]
        latest = self.works[-1].work_id if self.works else "—"
        audit = self.assurance["formal_audit"]
        tests = self.assurance["tests"]
        deadline = self.deadlines[0] if self.deadlines else None
        deadline_en = (
            f"- Deadline: {deadline['status']} — {deadline['decision']} (due {deadline['due']})."
            if deadline
            else "- Deadline: none recorded."
        )
        deadline_ja = (
            f"- 期限: {deadline['status']} — {deadline['decision']}（{deadline['due']}）。"
            if deadline
            else "- 期限: 記録なし。"
        )
        if language == "en":
            return "\n".join(
                [
                    "<!-- repository-snapshot:start -->",
                    f"- Works recorded: {len(self.works)} (through {latest}); terminal: {len(terminal)}.",
                    f"- Published works: {len(published)} — "
                    + (", ".join(f"{work.work_id} {work.title}" for work in published) or "none"),
                    f"- Assurance: tests: {tests['status']}; latest recorded formal audit: {audit['status']}"
                    + (f" ({audit['path']})" if audit.get("path") else "")
                    + f"; currency: {audit['currency']}; artifacts retained: {len(self.formal_audits)}.",
                    f"- Design state: changelog {self.design_state['changelog_latest'] or 'UNKNOWN'}; "
                    f"poetics "
                    + (
                        f"v{self.design_state['poetics_version']}."
                        if self.design_state["poetics_version"] is not None
                        else "UNKNOWN."
                    ),
                    deadline_en,
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
                f"- assurance: tests: {tests['status']}、最新記録formal audit: {audit['status']}"
                + (f"（{audit['path']}）" if audit.get("path") else "")
                + f"、currency: {audit['currency']}、保存artifact: {len(self.formal_audits)}件。",
                f"- 設計状態: changelog {self.design_state['changelog_latest'] or 'UNKNOWN'}、詩学 "
                + (
                    f"v{self.design_state['poetics_version']}。"
                    if self.design_state["poetics_version"] is not None
                    else "UNKNOWN。"
                ),
                deadline_ja,
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
        design_state = self._design_state(warnings)
        formal_audits, audit_ledger_valid = self._formal_audits(warnings)
        warnings.extend(f"design state stale: {item}" for item in design_state["stale"])
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
            formal_audits=formal_audits,
            assurance=self._assurance(formal_audits, design_state, audit_ledger_valid),
            design_state=design_state,
            deadlines=deadlines,
            warnings=tuple(dict.fromkeys(warnings)),
            provenance={
                "works": ("works/*",),
                "budget": ("config/budgets.yaml", "state/budget.json"),
                "experiments": ("works/*/seed.json#experiment.id",),
                "active_jobs": ("state/run_<work_id>.pid",),
                "formal_audits": (
                    "config/formal-audits.json",
                    "audits/",
                    "reports/*AUDIT*.md",
                ),
                "assurance": (
                    "config/formal-audits.json",
                    "audits/",
                    "reports/*AUDIT*.md",
                    "PLAN_CHANGELOG.md",
                    ".git (read-only HEAD/index/object/ref state)",
                ),
                "design_state": ("PLAN.md", "PLAN_CHANGELOG.md", "poetics/history.jsonl"),
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
        if "max_per_month" not in publish:
            warnings.append("publish.max_per_month is missing; deadline is unavailable")
        elif cap is not None and type(cap) is not int:
            warnings.append("publish.max_per_month is not an integer; deadline is unavailable")
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

    @staticmethod
    def _terminal_verdict(text: str) -> str:
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return "UNKNOWN"
        return {
            "VERDICT: PASS": "PASS",
            "VERDICT: FAIL": "FAIL",
        }.get(lines[-1], "UNKNOWN")

    @staticmethod
    def _valid_closure_paths(report_path: str, value: Any) -> tuple[str, ...] | None:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return None
        if len(value) != len(set(value)):
            return None
        fixed = {
            "PLAN_CHANGELOG.md",
            "PROGRESS.md",
            "README.md",
            "README.en.md",
            "config/formal-audits.json",
            "designs/next-designer-execution-plan.md",
        }
        paths = tuple(value)
        if any(
            Path(item).is_absolute()
            or ".." in Path(item).parts
            or (item not in fixed and item != report_path)
            for item in paths
        ):
            return None
        return paths

    def _formal_audits(
        self, warnings: list[str]
    ) -> tuple[tuple[dict[str, Any], ...], bool]:
        paths = sorted((self.root / "audits").glob("*.md"))
        paths += sorted((self.root / "reports").glob("*AUDIT*.md"))
        by_path: dict[str, dict[str, Any]] = {}
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            relative = str(path.relative_to(self.root))
            by_path[relative] = {
                "path": relative,
                "verdict": self._terminal_verdict(text),
                "ledger": "unregistered",
            }

        ledger_path = self.root / "config" / "formal-audits.json"
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if by_path:
                warnings.append("formal audit ledger is missing")
            return tuple(by_path.values()), not by_path
        except (OSError, json.JSONDecodeError):
            warnings.append("formal audit ledger is unreadable")
            return tuple(by_path.values()), False

        if not isinstance(ledger, dict) or ledger.get("version") != 1:
            warnings.append("formal audit ledger version is invalid")
            return tuple(by_path.values()), False
        ledger_valid = True
        legacy = ledger.get("legacy_unordered", [])
        entries = ledger.get("entries", [])
        if not isinstance(legacy, list) or not all(isinstance(item, str) for item in legacy):
            warnings.append("formal audit ledger legacy_unordered is invalid")
            legacy = []
            ledger_valid = False
        for path in legacy:
            if path in by_path:
                by_path[path]["ledger"] = "legacy"
            else:
                warnings.append(f"formal audit legacy artifact is missing: {path}")
                ledger_valid = False

        if not isinstance(entries, list):
            warnings.append("formal audit ledger entries are invalid")
            entries = []
            ledger_valid = False
        legacy_paths = set(legacy)
        entry_paths = {
            raw["path"]
            for raw in entries
            if isinstance(raw, dict) and isinstance(raw.get("path"), str)
        }
        for path in sorted(legacy_paths & entry_paths):
            warnings.append(f"formal audit path is both legacy and registered: {path}")
            ledger_valid = False
        declared_sequences = {
            raw["path"]: raw["sequence"]
            for raw in entries
            if isinstance(raw, dict)
            and isinstance(raw.get("path"), str)
            and type(raw.get("sequence")) is int
        }
        seen_sequences: set[int] = set()
        registered_paths: set[str] = set()
        for raw in entries:
            if not isinstance(raw, dict):
                warnings.append("formal audit ledger entry is not an object")
                continue
            sequence = raw.get("sequence")
            path = raw.get("path")
            target = raw.get("target_changelog")
            tree = raw.get("candidate_tree")
            commit = raw.get("candidate_commit")
            candidate_ref = raw.get("candidate_ref")
            recorded_on = raw.get("recorded_on")
            closure_paths = self._valid_closure_paths(path, raw.get("closure_paths", []))
            valid = (
                type(sequence) is int
                and sequence > 0
                and sequence not in seen_sequences
                and isinstance(path, str)
                and path in by_path
                and path not in legacy_paths
                and path not in registered_paths
                and isinstance(target, str)
                and bool(re.fullmatch(r"\d+(?:\.\d+)*(?:-\d+)?", target))
                and isinstance(tree, str)
                and bool(re.fullmatch(r"[0-9a-f]{40}", tree))
                and (
                    commit is None
                    or isinstance(commit, str)
                    and bool(re.fullmatch(r"[0-9a-f]{40}", commit))
                )
                and (
                    candidate_ref is None
                    or isinstance(candidate_ref, str)
                    and bool(
                        re.fullmatch(
                            r"refs/tags/audit-candidate/[A-Za-z0-9][A-Za-z0-9._/-]*",
                            candidate_ref,
                        )
                    )
                    and ".." not in candidate_ref
                )
                and isinstance(recorded_on, str)
                and closure_paths is not None
            )
            try:
                parsed_on = date.fromisoformat(recorded_on) if isinstance(recorded_on, str) else None
                valid = valid and parsed_on is not None
            except ValueError:
                valid = False
            supersedes = raw.get("supersedes")
            superseded_sequence = (
                declared_sequences.get(supersedes) if isinstance(supersedes, str) else None
            )
            if supersedes is not None and (
                not isinstance(supersedes, str)
                or type(sequence) is not int
                or superseded_sequence is None
                or superseded_sequence >= sequence
            ):
                valid = False
            if not valid:
                warnings.append(f"formal audit ledger entry is invalid: {path!r}")
                ledger_valid = False
                continue
            seen_sequences.add(sequence)
            registered_paths.add(path)
            by_path[path].update(
                {
                    "ledger": "registered",
                    "sequence": sequence,
                    "recorded_on": recorded_on,
                    "target_changelog": target,
                    "candidate_tree": tree,
                    "candidate_commit": commit,
                    "candidate_ref": candidate_ref,
                    "closure_paths": closure_paths,
                    "supersedes": supersedes,
                }
            )
            if by_path[path]["verdict"] == "UNKNOWN":
                warnings.append(f"formal audit ledger artifact has no terminal verdict: {path}")
                ledger_valid = False

        for audit in by_path.values():
            if audit["ledger"] == "unregistered":
                warnings.append(f"formal audit artifact is unregistered: {audit['path']}")
                ledger_valid = False
        return tuple(by_path.values()), ledger_valid

    def _tree_binding(
        self,
        candidate_tree: str,
        candidate_commit: str | None,
        candidate_ref: str | None,
        closure_paths: tuple[str, ...],
    ) -> dict[str, Any]:
        base = {
            "state": "UNAVAILABLE",
            "candidate_exists": None,
            "candidate_commit_exists": None,
            "candidate_commit_tree": None,
            "candidate_ref_exists": None,
            "candidate_ref_commit": None,
            "head_tree": None,
            "changed_paths": [],
            "unexpected_paths": [],
        }

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

        try:
            head = run("rev-parse", "HEAD^{tree}")
            status = run("status", "--porcelain=v1", "--untracked-files=normal")
            exists = run("cat-file", "-e", f"{candidate_tree}^{{tree}}")
            commit_exists = (
                run("cat-file", "-e", f"{candidate_commit}^{{commit}}")
                if candidate_commit is not None
                else None
            )
            commit_tree = (
                run("rev-parse", f"{candidate_commit}^{{tree}}")
                if candidate_commit is not None
                else None
            )
            ref_commit = (
                run("rev-parse", f"{candidate_ref}^{{commit}}")
                if candidate_ref is not None
                else None
            )
        except (OSError, subprocess.SubprocessError):
            return base
        if head.returncode != 0 or status.returncode != 0:
            return base
        head_tree = head.stdout.strip()
        candidate_exists = exists.returncode == 0
        candidate_commit_exists = commit_exists is not None and commit_exists.returncode == 0
        resolved_commit_tree = (
            commit_tree.stdout.strip()
            if commit_tree is not None and commit_tree.returncode == 0
            else None
        )
        resolved_ref_commit = (
            ref_commit.stdout.strip()
            if ref_commit is not None and ref_commit.returncode == 0
            else None
        )
        base.update(
            head_tree=head_tree,
            candidate_exists=candidate_exists,
            candidate_commit_exists=candidate_commit_exists,
            candidate_commit_tree=resolved_commit_tree,
            candidate_ref_exists=resolved_ref_commit is not None,
            candidate_ref_commit=resolved_ref_commit,
        )
        if (
            not candidate_exists
            or not candidate_commit_exists
            or resolved_commit_tree != candidate_tree
            or resolved_ref_commit != candidate_commit
        ):
            return base

        lines = [line for line in status.stdout.splitlines() if line]
        has_untracked = any(line.startswith("??") for line in lines)
        has_unstaged = any(
            not line.startswith("??") and len(line) >= 2 and line[1] != " "
            for line in lines
        )
        has_staged = any(
            not line.startswith("??") and line[0] != " "
            for line in lines
        )
        if has_untracked or has_unstaged:
            base["state"] = "DIRTY"
            return base

        try:
            if has_staged:
                diff = run("diff", "--cached", "--name-only", candidate_tree, "--")
                state = "INDEX"
            else:
                diff = run("diff", "--name-only", candidate_tree, head_tree, "--")
                state = "HEAD"
        except (OSError, subprocess.SubprocessError):
            return base
        if diff.returncode != 0:
            return base
        changed = sorted(line for line in diff.stdout.splitlines() if line)
        allowed = set(closure_paths)
        unexpected = sorted(set(changed) - allowed)
        base.update(
            state=state,
            changed_paths=changed,
            unexpected_paths=unexpected,
        )
        return base

    def _assurance(
        self,
        formal_audits: tuple[dict[str, Any], ...],
        design_state: dict[str, Any],
        ledger_valid: bool,
    ) -> dict[str, Any]:
        registered = sorted(
            (audit for audit in formal_audits if audit["ledger"] == "registered"),
            key=lambda audit: audit["sequence"],
        )
        latest = registered[-1] if registered else None
        if not ledger_valid or latest is None or latest["verdict"] not in {"PASS", "FAIL"}:
            formal = {
                "status": "UNKNOWN",
                "path": None,
                "currency": "UNKNOWN",
                "target_changelog": None,
                "candidate_tree": None,
                "closure_paths": [],
                "tree_binding": {
                    "state": "UNAVAILABLE",
                    "candidate_exists": None,
                    "candidate_commit_exists": None,
                    "candidate_commit_tree": None,
                    "candidate_ref_exists": None,
                    "candidate_ref_commit": None,
                    "head_tree": None,
                    "changed_paths": [],
                    "unexpected_paths": [],
                },
            }
        else:
            changelog = design_state.get("changelog_latest")
            binding = self._tree_binding(
                latest["candidate_tree"],
                latest["candidate_commit"],
                latest["candidate_ref"],
                latest["closure_paths"],
            )
            if not changelog or binding["candidate_exists"] is False:
                currency = "UNKNOWN"
            elif not binding["candidate_commit_exists"]:
                currency = "UNKNOWN"
            elif binding["candidate_commit_tree"] != latest["candidate_tree"]:
                currency = "UNKNOWN"
            elif not binding["candidate_ref_exists"]:
                currency = "UNKNOWN"
            elif binding["candidate_ref_commit"] != latest["candidate_commit"]:
                currency = "UNKNOWN"
            elif latest["target_changelog"] != changelog:
                currency = "NEEDS_AUDIT"
            elif binding["state"] == "UNAVAILABLE":
                currency = "UNKNOWN"
            elif binding["state"] == "DIRTY" or binding["unexpected_paths"]:
                currency = "NEEDS_AUDIT"
            else:
                currency = "CURRENT"
            formal = {
                "status": latest["verdict"],
                "path": latest["path"],
                "currency": currency,
                "target_changelog": latest["target_changelog"],
                "candidate_tree": latest["candidate_tree"],
                "candidate_commit": latest["candidate_commit"],
                "candidate_ref": latest["candidate_ref"],
                "closure_paths": list(latest["closure_paths"]),
                "tree_binding": binding,
            }
        return {
            "tests": {"status": "NOT_RECORDED", "provenance": []},
            "formal_audit": formal,
        }

    def _design_state(self, warnings: list[str]) -> dict[str, Any]:
        def _read(path: Path) -> str:
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                return ""

        plan = _read(self.root / "PLAN.md")
        changelog = _read(self.root / "PLAN_CHANGELOG.md")
        version_pattern = r"\d+(?:\.\d+)*(?:-\d+)?"
        declared_match = re.search(rf"({version_pattern})までの改訂", plan)
        heading_pattern = re.compile(
            rf"^##\s+({version_pattern})(?:\s+\([^\n]*\))?(?:\s+[—-]\s+(.+))?\s*$"
        )
        heading_matches = []
        fence: str | None = None
        for line in changelog.splitlines():
            marker = line[:3]
            if marker in {"```", "~~~"}:
                fence = None if fence == marker else marker if fence is None else fence
                continue
            if fence is None:
                match = heading_pattern.fullmatch(line)
                if match:
                    heading_matches.append(match)
        latest_match = max(
            heading_matches,
            key=lambda match: tuple(int(part) for part in re.findall(r"\d+", match.group(1))),
            default=None,
        )
        declared = declared_match.group(1) if declared_match else None
        latest = latest_match.group(1) if latest_match else None
        latest_change = (
            latest_match.group(2).strip()
            if latest_match and latest_match.group(2) is not None
            else None
        )
        stale: list[str] = []
        if declared and latest and declared != latest:
            stale.append(f"PLAN.md declares {declared} but PLAN_CHANGELOG latest is {latest}")
        poetics_dir = self.root / "poetics"
        history_path = poetics_dir / "history.jsonl"
        if not poetics_dir.is_dir():
            poetics_version = None
            warnings.append("poetics directory is missing")
        else:
            if not history_path.exists():
                warnings.append("poetics/history.jsonl is missing; poetics defaults to v0")
            history = _read(history_path)
            malformed = False
            for line in history.splitlines():
                if not line.strip():
                    continue
                try:
                    if not isinstance(json.loads(line), dict):
                        malformed = True
                except json.JSONDecodeError:
                    malformed = True
            if malformed:
                poetics_version = None
                warnings.append("poetics/history.jsonl is malformed")
            else:
                from aleph.meta.poetics import current_version

                poetics_version = current_version(poetics_dir)
        return {
            "plan_declared_changelog": declared,
            "changelog_latest": latest,
            "latest_change": latest_change,
            "poetics_version": poetics_version,
            "stale": stale,
        }

    def _deadlines(self, publish_cap: int | None) -> tuple[dict[str, Any], ...]:
        if publish_cap != 999:
            return ()
        due = date(2026, 8, 1)
        return (
            {
                "decision": "publish.max_per_month=999 temporary July exception",
                "due": due.isoformat(),
                "expired": self.today >= due,
                "status": "EXPIRED" if self.today >= due else "UPCOMING",
                "required_action": "review with 4 as the initial value; do not mutate automatically",
            },
        )
