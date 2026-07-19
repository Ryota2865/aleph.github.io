from __future__ import annotations

import json
from pathlib import Path

from aleph.core.artifacts import Work
from aleph.core.loop import State
from aleph.core.repository_snapshot import RepositoryReader
from aleph.core.transition_commit import initialize
from scripts.build_dashboard import collect_works
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


def test_repository_snapshot_aggregates_work_and_experiment_as_audit_json(tmp_path):
    _published_work(tmp_path)

    snapshot = RepositoryReader(tmp_path).snapshot()
    payload = snapshot.to_dict()

    assert [work.work_id for work in snapshot.works] == ["w9100"]
    assert payload["works"][0]["title"] == "共有題"
    assert payload["works"][0]["best_draft"]["text"] == "採用本文"
    assert payload["experiments"] == [{"experiment_id": "exp-fixture", "work_id": "w9100"}]


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


def test_readme_status_adapter_uses_repository_counts(tmp_path):
    _published_work(tmp_path)

    status = RepositoryReader(tmp_path).snapshot().readme_status_markdown()

    assert "作品記録: 1作（w9100まで）" in status
    assert "公開作品: 1作 — w9100「共有題」" in status


def test_audit_report_keeps_snapshot_warnings_visible(tmp_path):
    _published_work(tmp_path)
    snapshot = RepositoryReader(tmp_path).snapshot()

    report = render_report(snapshot)

    assert f"- warnings: {len(snapshot.warnings)}" in report
    assert all(warning in report for warning in snapshot.warnings)


def test_checked_in_readme_snapshot_sections_match_current_repository():
    snapshot = RepositoryReader(ROOT).snapshot()

    assert snapshot.readme_status_markdown() in (ROOT / "README.md").read_text(encoding="utf-8")
    assert snapshot.readme_status_markdown(language="en") in (ROOT / "README.en.md").read_text(encoding="utf-8")
