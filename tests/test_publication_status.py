from __future__ import annotations

import json

import pytest

from aleph.core.artifacts import Work
from aleph.core.loop import State
from aleph.core.transition_commit import initialize, project
from aleph.publish.status import is_published


def _work(tmp_path, work_id="w9950"):
    work = Work(tmp_path / "works", work_id)
    work.create({})
    return work


def test_shelved_work_is_published_after_committed_reassessment(tmp_path):
    work = _work(tmp_path)
    initialize(
        work,
        command_id="fixture",
        state=State.SHELVE,
        reason="fixture",
        decided_by="test",
        payload={"publication_disposition": "SHELVE"},
    )
    project(
        work,
        command_id="publish-reassessment",
        expected_state=State.SHELVE,
        name="publication_reassessment",
        reason="approved",
        decided_by="test",
        payload_delta={"publication_disposition": "PUBLISH"},
    )

    assert is_published(work.dir) is True


def test_finish_projection_does_not_replace_initial_publish_transition(tmp_path):
    work = _work(tmp_path)
    initialize(
        work,
        command_id="fixture",
        state=State.FINISH,
        reason="fixture",
        decided_by="test",
    )
    with pytest.raises(ValueError, match="SHELVE"):
        project(
            work,
            command_id="invalid-shortcut",
            expected_state=State.FINISH,
            name="publication_reassessment",
            reason="not a valid initial transition",
            decided_by="test",
            payload_delta={"publication_disposition": "PUBLISH"},
        )

    assert is_published(work.dir) is False


def test_invalid_modern_history_fails_closed(tmp_path):
    work = _work(tmp_path)
    initialize(
        work,
        command_id="fixture",
        state=State.PUBLISH,
        reason="fixture",
        decided_by="test",
    )
    row = json.loads(work.decisions.read_text(encoding="utf-8"))
    row["decision"] = "initialize:FINISH"
    work.decisions.write_text(json.dumps(row) + "\n", encoding="utf-8")

    assert is_published(work.dir) is False


def test_unrelated_projection_cannot_grant_publication(tmp_path):
    """再監査 finding 3: dispositionを書けるprojection名を公開再評価に限定する。"""
    work = _work(tmp_path)
    initialize(
        work,
        command_id="fixture",
        state=State.SHELVE,
        reason="fixture",
        decided_by="test",
    )
    with pytest.raises(ValueError, match="publication_reassessment"):
        project(
            work,
            command_id="unrelated",
            expected_state=State.SHELVE,
            name="unrelated_projection",
            reason="must not publish",
            decided_by="test",
            payload_delta={"publication_disposition": "PUBLISH"},
        )

    assert is_published(work.dir) is False


def test_tampered_unrelated_projection_fails_closed(tmp_path):
    """interfaceを迂回して公開payloadを注入されてもstrict replayで拒否する。"""
    work = _work(tmp_path)
    initialize(
        work,
        command_id="fixture",
        state=State.SHELVE,
        reason="fixture",
        decided_by="test",
    )
    project(
        work,
        command_id="unrelated",
        expected_state=State.SHELVE,
        name="unrelated_projection",
        reason="orthogonal metadata",
        decided_by="test",
        payload_delta={"unrelated": True},
    )
    rows = [json.loads(line) for line in work.decisions.read_text(encoding="utf-8").splitlines()]
    rows[-1]["payload"] = {"publication_disposition": "PUBLISH"}
    work.decisions.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    assert is_published(work.dir) is False


def test_later_unrelated_projection_does_not_erase_valid_publication(tmp_path):
    """公開権限は最後の全eventでなく、最後のdisposition更新eventの由来で判定する。"""
    work = _work(tmp_path)
    initialize(
        work,
        command_id="fixture",
        state=State.SHELVE,
        reason="fixture",
        decided_by="test",
    )
    project(
        work,
        command_id="publish",
        expected_state=State.SHELVE,
        name="publication_reassessment",
        reason="approved",
        decided_by="test",
        payload_delta={"publication_disposition": "PUBLISH"},
    )
    project(
        work,
        command_id="later-unrelated",
        expected_state=State.SHELVE,
        name="unrelated_projection",
        reason="orthogonal metadata",
        decided_by="test",
        payload_delta={"unrelated": True},
    )

    assert is_published(work.dir) is True


def test_modern_history_missing_schema_does_not_fall_back_to_legacy_publish(tmp_path):
    """再監査 finding 4: modern専用fieldが残るschema欠落履歴は公開拒否する。"""
    work = _work(tmp_path)
    initialize(
        work,
        command_id="fixture",
        state=State.PUBLISH,
        reason="fixture",
        decided_by="test",
    )
    row = json.loads(work.decisions.read_text(encoding="utf-8"))
    del row["schema_version"]
    row["decision"] = "FINISH->PUBLISH"
    work.decisions.write_text(json.dumps(row) + "\n", encoding="utf-8")

    assert is_published(work.dir) is False
