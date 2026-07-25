from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

from aleph.core.artifacts import Work
from aleph.core.loop import State
from aleph.core.repository_snapshot import RepositoryReader
from aleph.core.transition_commit import initialize
from scripts.build_dashboard import collect_pending_gates, collect_works
from scripts.build_public_site import iter_published
from scripts.audit_repository_snapshot import render_report


ROOT = Path(__file__).resolve().parents[1]


def _published_work(root, work_id="w9100"):
    work = Work(root / "works", work_id)
    work.create({"hint": "fixture", "experiment": {"id": "exp-fixture"}})
    work.draft_path(1).write_text("採用本文", encoding="utf-8")
    (work.reviews / "trajectory.jsonl").write_text(
        json.dumps({"version": 1, "mean_score": 8.0}) + "\n", encoding="utf-8"
    )
    initialize(
        work,
        command_id="fixture",
        state=State.PUBLISH,
        reason="fixture",
        decided_by="test",
        payload={"audience": "人間 1.0"},
    )
    work.final.mkdir(exist_ok=True)
    (work.final / "text.md").write_text("採用本文", encoding="utf-8")
    (work.final / "meta.json").write_text('{"title":"共有題"}', encoding="utf-8")
    return work


def _write_audit_ledger(root, entries):
    config = root / "config"
    config.mkdir(exist_ok=True)
    (config / "formal-audits.json").write_text(
        json.dumps({"version": 1, "entries": entries}), encoding="utf-8"
    )


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_git(root):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "snapshot-test@example.invalid")
    _git(root, "config", "user.name", "Repository Snapshot Test")


def test_repository_snapshot_aggregates_work_and_experiment_as_audit_json(tmp_path):
    _published_work(tmp_path)

    snapshot = RepositoryReader(tmp_path).snapshot()
    payload = snapshot.to_dict()

    assert [work.work_id for work in snapshot.works] == ["w9100"]
    assert payload["works"][0]["title"] == "共有題"
    assert payload["works"][0]["best_draft"]["text"] == "採用本文"
    assert payload["experiments"] == [{"experiment_id": "exp-fixture", "work_id": "w9100"}]


def test_repository_snapshot_dict_cannot_mutate_nested_budget_state(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "budget.json").write_text(
        json.dumps(
            {
                "ledgers": {
                    "api": {"spent": 1.25, "period_key": "2026-07"},
                    "harness": {"spent": 2},
                    "local": {"spent": 3},
                },
                "work_spent": {"w9100": 1.25},
            }
        ),
        encoding="utf-8",
    )
    snapshot = RepositoryReader(
        tmp_path,
        budget_config={
            "publish": {"max_per_month": 4},
            "api": {"usd_per_month": 71.0, "usd_per_work": 9.0},
            "harness": {"calls_per_day": 100},
            "local": {"gpu_hours_per_day": 8},
        },
    ).snapshot()

    payload = snapshot.to_dict()
    payload["budget"]["ledgers"]["api"]["spent"] = 99.0
    payload["budget"]["ledger_status"]["api"]["spent"] = 99.0
    payload["budget"]["work_spent"]["w9100"] = 99.0

    assert snapshot.budget["ledgers"]["api"]["spent"] == 1.25
    assert snapshot.budget["ledger_status"]["api"]["spent"] == 1.25
    assert snapshot.budget["work_spent"]["w9100"] == 1.25


def test_formal_audit_provenance_names_the_authoritative_ledger(tmp_path):
    payload = RepositoryReader(tmp_path).snapshot().to_dict()

    assert payload["provenance"]["formal_audits"] == [
        "config/formal-audits.json",
        "audits/",
        "reports/*AUDIT*.md",
    ]


def test_site_dashboard_and_cli_share_state_title_and_selected_draft(tmp_path, capsys):
    _published_work(tmp_path)

    site = iter_published(tmp_path)
    dashboard = collect_works(tmp_path)
    from aleph.cli import main

    assert main(["status", "--json"], root=tmp_path) == 0
    cli = json.loads(capsys.readouterr().out)

    assert site[0][1]["title"] == dashboard[0]["title"] == cli["works"][0]["title"] == "共有題"
    assert site[0][2] == cli["works"][0]["best_draft"]["text"] == "採用本文"
    assert dashboard[0]["state"] == cli["works"][0]["lifecycle"] == "PUBLISH"


def test_resume_is_a_run_alias_with_the_same_arguments(tmp_path, monkeypatch):
    from aleph import cli

    observed = {}

    def fake_run(root, args):
        observed.update(root=root, work=args.work, index=args.index, audience=args.force_audience)
        return 7

    monkeypatch.setattr(cli, "_cmd_run", fake_run)

    assert cli.main(
        [
            "resume",
            "--work",
            "w9100",
            "--index",
            "state/test-index",
            "--force-audience",
            "LLM 1.0",
        ],
        root=tmp_path,
    ) == 7
    assert observed == {
        "root": tmp_path,
        "work": "w9100",
        "index": "state/test-index",
        "audience": "LLM 1.0",
    }


def test_readme_status_adapter_uses_repository_counts(tmp_path):
    _published_work(tmp_path)

    status = RepositoryReader(tmp_path).snapshot().readme_status_markdown()

    assert "作品記録: 1作（w9100まで）" in status
    assert "公開作品: 1作 — w9100「共有題」" in status
    assert "tests: NOT_RECORDED" in status
    assert "最新記録formal audit: UNKNOWN" in status


def test_repository_snapshot_exposes_latest_conclusive_audit_separately_from_tests(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "PHASE6_THING_AUDIT_20260724_FAIL.md").write_text(
        "# Initial audit\n\nVERDICT: FAIL\n", encoding="utf-8"
    )
    (reports / "PHASE6_THING_REAUDIT_20260724.md").write_text(
        "# Focused re-audit\n\nVERDICT: PASS\n", encoding="utf-8"
    )
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": "reports/PHASE6_THING_AUDIT_20260724_FAIL.md",
                "recorded_on": "2026-07-24",
                "target_changelog": "0.7.20-4",
                "candidate_tree": "a" * 40,
            },
            {
                "sequence": 2,
                "path": "reports/PHASE6_THING_REAUDIT_20260724.md",
                "recorded_on": "2026-07-24",
                "target_changelog": "0.7.20-5",
                "candidate_tree": "b" * 40,
                "supersedes": "reports/PHASE6_THING_AUDIT_20260724_FAIL.md",
            },
        ],
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.assurance["tests"] == {
        "status": "NOT_RECORDED",
        "provenance": [],
    }
    formal = snapshot.assurance["formal_audit"]
    assert formal["status"] == "PASS"
    assert formal["path"] == "reports/PHASE6_THING_REAUDIT_20260724.md"
    assert formal["currency"] == "UNKNOWN"
    assert formal["target_changelog"] == "0.7.20-5"
    assert formal["candidate_tree"] == "b" * 40
    assert formal["tree_binding"]["state"] == "UNAVAILABLE"
    assert [audit["verdict"] for audit in snapshot.formal_audits] == ["FAIL", "PASS"]


def test_audit_ledger_sequence_not_filename_order_selects_latest_and_binds_currency(tmp_path):
    (tmp_path / "PLAN.md").write_text("0.8.0までの改訂\n", encoding="utf-8")
    (tmp_path / "PLAN_CHANGELOG.md").write_text(
        "## 0.8.0 (2026-08-01) — repair pending audit\n", encoding="utf-8"
    )
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "ZZZ_OLD_AUDIT.md").write_text("VERDICT: PASS\n", encoding="utf-8")
    (reports / "AAA_NEW_AUDIT.md").write_text("VERDICT: FAIL\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": "reports/ZZZ_OLD_AUDIT.md",
                "recorded_on": "2026-07-31",
                "target_changelog": "0.7.20-27",
                "candidate_tree": "a" * 40,
            },
            {
                "sequence": 2,
                "path": "reports/AAA_NEW_AUDIT.md",
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "b" * 40,
                "supersedes": "reports/ZZZ_OLD_AUDIT.md",
            },
        ],
    )

    formal = RepositoryReader(tmp_path).snapshot().assurance["formal_audit"]

    assert formal["status"] == "FAIL"
    assert formal["path"] == "reports/AAA_NEW_AUDIT.md"
    assert formal["currency"] == "UNKNOWN"


def test_supersedes_resolution_uses_sequence_not_json_array_order(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    old_path = "reports/OLD_AUDIT.md"
    new_path = "reports/NEW_REAUDIT.md"
    (tmp_path / old_path).write_text("VERDICT: FAIL\n", encoding="utf-8")
    (tmp_path / new_path).write_text("VERDICT: PASS\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 2,
                "path": new_path,
                "recorded_on": "2026-08-02",
                "target_changelog": "0.8.0",
                "candidate_tree": "b" * 40,
                "supersedes": old_path,
            },
            {
                "sequence": 1,
                "path": old_path,
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
            },
        ],
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.assurance["formal_audit"]["status"] == "PASS"
    assert snapshot.assurance["formal_audit"]["path"] == new_path
    assert not any("ledger entry is invalid" in warning for warning in snapshot.warnings)


def test_supersedes_cannot_reference_same_or_future_sequence(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    old_path = "reports/OLD_AUDIT.md"
    future_path = "reports/FUTURE_AUDIT.md"
    (tmp_path / old_path).write_text("VERDICT: FAIL\n", encoding="utf-8")
    (tmp_path / future_path).write_text("VERDICT: PASS\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 2,
                "path": future_path,
                "recorded_on": "2026-08-02",
                "target_changelog": "0.8.0",
                "candidate_tree": "b" * 40,
            },
            {
                "sequence": 1,
                "path": old_path,
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
                "supersedes": future_path,
            },
        ],
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.assurance["formal_audit"]["status"] == "UNKNOWN"
    assert any("ledger entry is invalid" in warning for warning in snapshot.warnings)


def test_supersedes_missing_self_and_cycle_are_fail_closed(tmp_path):
    cases = {
        "missing": [
            {
                "sequence": 1,
                "path": "reports/A_AUDIT.md",
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
                "supersedes": "reports/MISSING_AUDIT.md",
            }
        ],
        "self": [
            {
                "sequence": 1,
                "path": "reports/A_AUDIT.md",
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
                "supersedes": "reports/A_AUDIT.md",
            }
        ],
        "cycle": [
            {
                "sequence": 2,
                "path": "reports/B_AUDIT.md",
                "recorded_on": "2026-08-02",
                "target_changelog": "0.8.0",
                "candidate_tree": "b" * 40,
                "supersedes": "reports/A_AUDIT.md",
            },
            {
                "sequence": 1,
                "path": "reports/A_AUDIT.md",
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
                "supersedes": "reports/B_AUDIT.md",
            },
        ],
    }
    for case, entries in cases.items():
        root = tmp_path / case
        reports = root / "reports"
        reports.mkdir(parents=True)
        for entry in entries:
            (root / entry["path"]).write_text("VERDICT: PASS\n", encoding="utf-8")
        _write_audit_ledger(root, entries)

        snapshot = RepositoryReader(root).snapshot()

        assert snapshot.assurance["formal_audit"]["status"] == "UNKNOWN"
        assert any("ledger entry is invalid" in warning for warning in snapshot.warnings)


def test_formal_audit_currency_is_bound_to_candidate_tree_and_closure_paths(tmp_path):
    (tmp_path / "PLAN.md").write_text("0.8.0までの改訂\n", encoding="utf-8")
    (tmp_path / "PLAN_CHANGELOG.md").write_text(
        "## 0.8.0 (2026-08-01) — implementation\n", encoding="utf-8"
    )
    poetics = tmp_path / "poetics"
    poetics.mkdir()
    (poetics / "history.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "implementation.py").write_text("VALUE = 1\n", encoding="utf-8")
    _init_git(tmp_path)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "candidate")
    candidate_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}")
    candidate_commit = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "tag", "audit-candidate/test", candidate_commit)

    reports = tmp_path / "reports"
    reports.mkdir()
    report_path = "reports/CURRENT_AUDIT.md"
    (tmp_path / report_path).write_text("VERDICT: PASS\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": report_path,
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": candidate_tree,
                "candidate_commit": candidate_commit,
                "candidate_ref": "refs/tags/audit-candidate/test",
                "closure_paths": ["config/formal-audits.json", report_path],
            }
        ],
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "closure")

    formal = RepositoryReader(tmp_path).snapshot().assurance["formal_audit"]

    assert formal["currency"] == "CURRENT"
    assert formal["tree_binding"]["state"] == "HEAD"
    assert formal["tree_binding"]["changed_paths"] == [
        "config/formal-audits.json",
        report_path,
    ]

    (tmp_path / report_path).write_text("VERDICT: PASS\n\n", encoding="utf-8")
    _git(tmp_path, "add", report_path)
    indexed = RepositoryReader(tmp_path).snapshot().assurance["formal_audit"]
    assert indexed["currency"] == "CURRENT"
    assert indexed["tree_binding"]["state"] == "INDEX"

    (tmp_path / "implementation.py").write_text("VALUE = 2\n", encoding="utf-8")
    dirty = RepositoryReader(tmp_path).snapshot().assurance["formal_audit"]
    assert dirty["currency"] == "NEEDS_AUDIT"
    assert dirty["tree_binding"]["state"] == "DIRTY"


def test_unexpected_committed_path_invalidates_tree_currency(tmp_path):
    (tmp_path / "PLAN.md").write_text("0.8.0までの改訂\n", encoding="utf-8")
    (tmp_path / "PLAN_CHANGELOG.md").write_text("## 0.8.0\n", encoding="utf-8")
    poetics = tmp_path / "poetics"
    poetics.mkdir()
    (poetics / "history.jsonl").write_text("", encoding="utf-8")
    _init_git(tmp_path)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "candidate")
    candidate_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}")
    candidate_commit = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "tag", "audit-candidate/test", candidate_commit)
    reports = tmp_path / "reports"
    reports.mkdir()
    report_path = "reports/CURRENT_AUDIT.md"
    (tmp_path / report_path).write_text("VERDICT: PASS\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": report_path,
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": candidate_tree,
                "candidate_commit": candidate_commit,
                "candidate_ref": "refs/tags/audit-candidate/test",
                "closure_paths": ["config/formal-audits.json", report_path],
            }
        ],
    )
    (tmp_path / "unreviewed.py").write_text("UNREVIEWED = True\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "unreviewed")

    formal = RepositoryReader(tmp_path).snapshot().assurance["formal_audit"]

    assert formal["currency"] == "NEEDS_AUDIT"
    assert formal["tree_binding"]["unexpected_paths"] == ["unreviewed.py"]


def test_nonexistent_candidate_tree_cannot_be_current(tmp_path):
    (tmp_path / "PLAN.md").write_text("0.8.0までの改訂\n", encoding="utf-8")
    (tmp_path / "PLAN_CHANGELOG.md").write_text("## 0.8.0\n", encoding="utf-8")
    poetics = tmp_path / "poetics"
    poetics.mkdir()
    (poetics / "history.jsonl").write_text("", encoding="utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    report_path = "reports/CURRENT_AUDIT.md"
    (tmp_path / report_path).write_text("VERDICT: PASS\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": report_path,
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "0" * 40,
                "candidate_commit": "0" * 40,
                "candidate_ref": "refs/tags/audit-candidate/missing",
                "closure_paths": ["config/formal-audits.json", report_path],
            }
        ],
    )
    _init_git(tmp_path)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "closure without candidate")

    formal = RepositoryReader(tmp_path).snapshot().assurance["formal_audit"]

    assert formal["currency"] == "UNKNOWN"
    assert formal["tree_binding"]["candidate_exists"] is False
    assert formal["tree_binding"]["candidate_commit_exists"] is False
    assert formal["tree_binding"]["candidate_ref_exists"] is False


def test_git_diff_timeout_preserves_snapshot_and_returns_unknown(tmp_path, monkeypatch):
    (tmp_path / "PLAN.md").write_text("0.8.0までの改訂\n", encoding="utf-8")
    (tmp_path / "PLAN_CHANGELOG.md").write_text("## 0.8.0\n", encoding="utf-8")
    poetics = tmp_path / "poetics"
    poetics.mkdir()
    (poetics / "history.jsonl").write_text("", encoding="utf-8")
    _init_git(tmp_path)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "candidate")
    candidate_tree = _git(tmp_path, "rev-parse", "HEAD^{tree}")
    candidate_commit = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "tag", "audit-candidate/test", candidate_commit)
    reports = tmp_path / "reports"
    reports.mkdir()
    report_path = "reports/CURRENT_AUDIT.md"
    (tmp_path / report_path).write_text("VERDICT: PASS\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": report_path,
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": candidate_tree,
                "candidate_commit": candidate_commit,
                "candidate_ref": "refs/tags/audit-candidate/test",
                "closure_paths": ["config/formal-audits.json", report_path],
            }
        ],
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "closure")

    real_run = subprocess.run

    def timeout_git_diff(args, **kwargs):
        if "diff" in args:
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 5))
        return real_run(args, **kwargs)

    monkeypatch.setattr(
        "aleph.core.repository_snapshot.subprocess.run",
        timeout_git_diff,
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.assurance["formal_audit"]["currency"] == "UNKNOWN"
    assert snapshot.assurance["formal_audit"]["tree_binding"]["state"] == "UNAVAILABLE"


def test_closure_allowlist_cannot_admit_code_paths(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    report_path = "reports/CURRENT_AUDIT.md"
    (tmp_path / report_path).write_text("VERDICT: PASS\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": report_path,
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
                "candidate_commit": "b" * 40,
                "candidate_ref": "refs/tags/audit-candidate/test",
                "closure_paths": ["aleph/core/repository_snapshot.py"],
            }
        ],
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.assurance["formal_audit"]["status"] == "UNKNOWN"
    assert any("ledger entry is invalid" in warning for warning in snapshot.warnings)


def test_non_terminal_or_conflicting_verdict_never_becomes_conclusive(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "BAD_AUDIT.md").write_text(
        "VERDICT: FAIL\n\nAppendix quoting verdict: PASS\n", encoding="utf-8"
    )
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": "reports/BAD_AUDIT.md",
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
            }
        ],
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.formal_audits[0]["verdict"] == "UNKNOWN"
    assert snapshot.assurance["formal_audit"]["status"] == "UNKNOWN"
    assert any("ledger artifact has no terminal verdict" in warning for warning in snapshot.warnings)


def test_terminal_verdict_requires_exact_case_and_spacing():
    assert RepositoryReader._terminal_verdict("VERDICT: PASS\n") == "PASS"
    assert RepositoryReader._terminal_verdict("VERDICT: FAIL\n\n \t\n") == "FAIL"

    for malformed in (
        "verdict: pass",
        "Verdict: PASS",
        "VERDICT: pass",
        "VERDICT:PASS",
        "VERDICT:  PASS",
        "VERDICT:\tPASS",
        " VERDICT: PASS",
        "VERDICT: PASS ",
        "VERDICT: PASS (see appendix)",
    ):
        assert RepositoryReader._terminal_verdict(malformed) == "UNKNOWN"


def test_malformed_latest_verdict_does_not_fall_back_or_become_conclusive(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    old_path = "reports/OLD_AUDIT.md"
    new_path = "reports/NEW_REAUDIT.md"
    (tmp_path / old_path).write_text("VERDICT: PASS\n", encoding="utf-8")
    (tmp_path / new_path).write_text("verdict: pass\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": old_path,
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
            },
            {
                "sequence": 2,
                "path": new_path,
                "recorded_on": "2026-08-02",
                "target_changelog": "0.8.0",
                "candidate_tree": "b" * 40,
                "supersedes": old_path,
            },
        ],
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.assurance["formal_audit"]["status"] == "UNKNOWN"
    assert any("ledger artifact has no terminal verdict" in warning for warning in snapshot.warnings)


def test_unregistered_audit_artifact_invalidates_latest_claim(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "REGISTERED_AUDIT.md").write_text("VERDICT: PASS\n", encoding="utf-8")
    (reports / "NEW_UNREGISTERED_AUDIT.md").write_text("VERDICT: FAIL\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": "reports/REGISTERED_AUDIT.md",
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "a" * 40,
            }
        ],
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.assurance["formal_audit"]["status"] == "UNKNOWN"
    assert snapshot.assurance["formal_audit"]["currency"] == "UNKNOWN"
    assert any("artifact is unregistered" in warning for warning in snapshot.warnings)


def test_missing_newer_ledger_artifact_does_not_fall_back_to_older_pass(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "OLD_AUDIT.md").write_text("VERDICT: PASS\n", encoding="utf-8")
    _write_audit_ledger(
        tmp_path,
        [
            {
                "sequence": 1,
                "path": "reports/OLD_AUDIT.md",
                "recorded_on": "2026-07-31",
                "target_changelog": "0.7.20-27",
                "candidate_tree": "a" * 40,
            },
            {
                "sequence": 2,
                "path": "reports/MISSING_NEW_AUDIT.md",
                "recorded_on": "2026-08-01",
                "target_changelog": "0.8.0",
                "candidate_tree": "b" * 40,
                "supersedes": "reports/OLD_AUDIT.md",
            },
        ],
    )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert snapshot.assurance["formal_audit"]["status"] == "UNKNOWN"
    assert any("ledger entry is invalid" in warning for warning in snapshot.warnings)


def test_repository_snapshot_reports_design_state_and_expired_deadline(tmp_path):
    (tmp_path / "PLAN.md").write_text(
        "**版**: 0.6 + 0.7.20-4までの改訂\n", encoding="utf-8"
    )
    (tmp_path / "PLAN_CHANGELOG.md").write_text(
        "# history\n\n## 0.7.20-5 (2026-07-24) — next\n", encoding="utf-8"
    )
    poetics = tmp_path / "poetics"
    poetics.mkdir()
    (poetics / "history.jsonl").write_text('{"version": 1}\n', encoding="utf-8")

    snapshot = RepositoryReader(
        tmp_path,
        today=date(2026, 8, 1),
        budget_config={
            "api": {},
            "harness": {},
            "local": {},
            "publish": {"max_per_month": 999},
        },
    ).snapshot()

    assert snapshot.design_state == {
        "plan_declared_changelog": "0.7.20-4",
        "changelog_latest": "0.7.20-5",
        "latest_change": "next",
        "poetics_version": 1,
        "stale": ["PLAN.md declares 0.7.20-4 but PLAN_CHANGELOG latest is 0.7.20-5"],
    }
    assert snapshot.deadlines[0]["status"] == "EXPIRED"
    assert "deadline expired:" in "\n".join(snapshot.warnings)
    assert "期限: EXPIRED" in snapshot.readme_status_markdown()


def test_missing_publish_cap_makes_deadline_unavailable_with_warning(tmp_path):
    snapshot = RepositoryReader(
        tmp_path,
        budget_config={"api": {}, "harness": {}, "local": {}, "publish": {}},
    ).snapshot()

    assert snapshot.deadlines == ()
    assert snapshot.budget["publish_cap"] is None
    assert "publish.max_per_month is missing; deadline is unavailable" in snapshot.warnings


def test_changelog_parser_keeps_hyphenated_version_without_title_and_supports_next_series(tmp_path):
    (tmp_path / "PLAN.md").write_text("0.8.0までの改訂\n", encoding="utf-8")
    (tmp_path / "PLAN_CHANGELOG.md").write_text(
        "## 0.8.0 (2026-08-10)\n\n## 0.7.20-27 (2026-07-25) — older\n",
        encoding="utf-8",
    )

    design = RepositoryReader(tmp_path).snapshot().design_state

    assert design["plan_declared_changelog"] == "0.8.0"
    assert design["changelog_latest"] == "0.8.0"
    assert design["latest_change"] is None
    assert design["stale"] == []


def test_changelog_latest_uses_version_order_and_ignores_fenced_headings(tmp_path):
    (tmp_path / "PLAN.md").write_text("0.8.1までの改訂\n", encoding="utf-8")
    (tmp_path / "PLAN_CHANGELOG.md").write_text(
        "\n".join(
            [
                "## 0.7.20-35 (2026-07-25) — physically first",
                "```markdown",
                "## 9.9.9 (2099-01-01) — fenced example",
                "```",
                "> ## 8.8.8 (2098-01-01) — quoted example",
                "## 0.8.1 (2026-08-01) — authoritative latest",
            ]
        ),
        encoding="utf-8",
    )

    design = RepositoryReader(tmp_path).snapshot().design_state

    assert design["changelog_latest"] == "0.8.1"
    assert design["latest_change"] == "authoritative latest"
    assert design["stale"] == []


def test_expired_repository_deadline_is_a_dashboard_gate():
    gates = collect_pending_gates(
        {"publication": {"first_publish_ack": True}, "poetics": {"first_revision_requires_human_ack": True}},
        {"api_cap": 71.0, "api_spent": 0.0},
        deadlines=(
            {
                "decision": "temporary cap",
                "due": "2026-08-01",
                "expired": True,
                "status": "EXPIRED",
                "required_action": "review; do not mutate automatically",
            },
        ),
    )

    assert gates == [
        "期限切れ: temporary cap（期限 2026-08-01）。review; do not mutate automatically"
    ]


def test_malformed_publish_cap_does_not_silently_drop_deadline(tmp_path):
    snapshot = RepositoryReader(
        tmp_path,
        budget_config={
            "api": {},
            "harness": {},
            "local": {},
            "publish": {"max_per_month": "999"},
        },
    ).snapshot()

    assert snapshot.deadlines == ()
    assert any("publish.max_per_month is not an integer" in warning for warning in snapshot.warnings)


def test_audit_report_keeps_snapshot_warnings_visible(tmp_path):
    _published_work(tmp_path)
    snapshot = RepositoryReader(tmp_path).snapshot()

    report = render_report(snapshot)

    assert f"- warnings: {len(snapshot.warnings)}" in report
    assert "- tests: NOT_RECORDED" in report
    assert "- latest recorded formal audit: UNKNOWN" in report
    assert "- formal audit tree state: UNAVAILABLE" in report
    assert all(warning in report for warning in snapshot.warnings)


def test_to_dict_does_not_expose_nested_snapshot_state(tmp_path):
    snapshot = RepositoryReader(tmp_path).snapshot()
    payload = snapshot.to_dict()

    payload["assurance"]["tests"]["status"] = "PASS"
    payload["design_state"]["stale"].append("mutated")

    assert snapshot.assurance["tests"]["status"] == "NOT_RECORDED"
    assert "mutated" not in snapshot.design_state["stale"]


def test_checked_in_readme_snapshot_sections_match_current_repository():
    snapshot = RepositoryReader(ROOT).snapshot()

    assert snapshot.readme_status_markdown() in (ROOT / "README.md").read_text(encoding="utf-8")
    assert snapshot.readme_status_markdown(language="en") in (ROOT / "README.en.md").read_text(encoding="utf-8")
