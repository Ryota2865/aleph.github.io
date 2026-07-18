from __future__ import annotations

import json
from types import SimpleNamespace

from aleph import cli
from aleph.core.artifacts import Work
from aleph.core.loop import Checkpoint, State
from aleph.core.transition_commit import initialize, strict_replay


class _Config:
    policies = {"publication": {"first_publish_ack": True}}
    secrets = {}
    models = {}
    budgets = {"publish": {"max_per_month": 4}}


class _Deps:
    def __init__(self, *args, **kwargs):
        pass

    def decide_publication(self, work, audience):
        return {"decision": "PUBLISH", "reason": "manual reassessment passed"}


def _wire_cli(monkeypatch, root):
    import aleph.pipeline

    monkeypatch.setattr(cli, "load_config", lambda _: _Config())
    monkeypatch.setattr(cli, "CallLogger", lambda *a, **k: object())
    monkeypatch.setattr(cli, "Budget", lambda *a, **k: object())
    monkeypatch.setattr(cli, "Router", lambda *a, **k: object())
    monkeypatch.setattr(aleph.pipeline, "RealDeps", _Deps)
    monkeypatch.setattr(
        aleph.pipeline,
        "_finalize_publish",
        lambda work, deps: (work.final / "published.marker").write_text("ok", encoding="utf-8"),
    )
    return SimpleNamespace(work="w9902", index="state/atlas")


def test_publish_reassessment_keeps_shelve_lifecycle(tmp_path, monkeypatch):
    work = Work(tmp_path / "works", "w9902")
    work.create({})
    initialize(
        work,
        command_id="fixture",
        state=State.SHELVE,
        reason="fixture",
        decided_by="test",
        payload={"audience": "human", "publication_disposition": "SHELVE"},
    )

    rc = cli._cmd_publish(tmp_path, _wire_cli(monkeypatch, tmp_path))

    assert rc == 0
    checkpoint = Checkpoint.load(work.dir)
    assert checkpoint.state == State.SHELVE
    assert checkpoint.payload["publication_disposition"] == "PUBLISH"
    assert checkpoint == strict_replay(work.work_id, work.decisions)
    assert (work.final / "published.marker").read_text(encoding="utf-8") == "ok"


def test_publish_reassessment_reconciles_legacy_prefix_without_rewrite(tmp_path, monkeypatch):
    work = Work(tmp_path / "works", "w9902")
    work.create({})
    legacy = {
        "ts": "2026-07-01T00:00:00+00:00",
        "layer": "L0",
        "decision": "FINISH->SHELVE",
        "reason": "legacy",
        "decided_by": "legacy",
        "refs": [],
    }
    work.append_decision(legacy)
    Checkpoint(
        work_id=work.work_id,
        state=State.SHELVE,
        step=8,
        payload={"audience": "human"},
    ).save(work.dir)

    rc = cli._cmd_publish(tmp_path, _wire_cli(monkeypatch, tmp_path))

    assert rc == 0
    rows = [json.loads(line) for line in work.decisions.read_text(encoding="utf-8").splitlines()]
    l0 = [row for row in rows if row.get("layer") == "L0"]
    assert l0[0] == legacy
    assert l0[1]["event_type"] == "reconciliation"
    assert l0[1]["legacy_warnings"]
    assert l0[2]["event_type"] == "projection"
