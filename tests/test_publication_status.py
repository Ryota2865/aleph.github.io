from __future__ import annotations

import json

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
