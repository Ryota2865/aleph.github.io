from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from aleph.core.artifacts import Work
from aleph.core.instruments import (
    InstrumentError,
    InstrumentRecorder,
    InstrumentRegistry,
    MeasurementContext,
)
from aleph.core.llm import LLMResponse, TokenLogprob, Usage
from aleph.pipeline import RealDeps


ROOT = Path(__file__).resolve().parents[1]


def _registry() -> InstrumentRegistry:
    return InstrumentRegistry.load(ROOT / "config" / "instruments.yaml")


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _tiny_index(tmp_path: Path) -> Path:
    index = tmp_path / "atlas"
    index.mkdir()
    np.save(index / "embeddings.npy", np.eye(2, 4, dtype=np.float32))
    (index / "chunks.jsonl").write_text(
        "\n".join(
            json.dumps({"chunk_id": f"c{i}", "text": "fixture"})
            for i in range(2)
        )
        + "\n",
        encoding="utf-8",
    )
    return index


def test_review_projects_four_instruments_and_keeps_invalid_parse_out_of_disagreement(
    tmp_path,
):
    from aleph.critique.review import run_review

    work = Work(tmp_path / "works", "w-step11")
    work.create({})
    draft = "fixture draft"
    work.draft_path(1).write_text(draft, encoding="utf-8")
    recorder = InstrumentRecorder(_registry(), work.measurements)
    jury = [
        lambda _prompt: '{"score": 4, "critique": "low"}',
        lambda _prompt: '{"score": 8, "critique": "high"}',
        lambda _prompt: '{"critique": "score missing"}',
    ]

    def reader_llm(_messages, **_kwargs):
        return LLMResponse(
            "ok",
            "reader-fixture",
            "fixture",
            Usage(1, 1),
            0.0,
            logprobs=(TokenLogprob("x", -2.0),),
        )

    report = run_review(
        work,
        draft,
        "criteria",
        "LLM 1.0 / 人間 0.0",
        version=1,
        scout=lambda prompt: (
            '{"issues":[]}' if "破綻" in prompt else '{"exists":false}'
        ),
        jury=jury,
        reader=lambda _prompt: '{"reaction":"ok"}',
        embedder=lambda texts: np.asarray(
            [[0.0, 0.0, 0.0, 1.0] for _ in texts], dtype=np.float32
        ),
        index_dir=_tiny_index(tmp_path),
        search_fn=lambda *_args, **_kwargs: [],
        reader_llm=reader_llm,
        instrument_recorder=recorder,
        instrument_metadata={
            "measured_at": "2026-07-23T00:00:00+00:00",
            "atlas_identity": "atlas-full-a",
            "atlas_identity_ref": "state/atlas/identity.json",
            "embedder": "bge-m3@fixture",
            "novelty_segmentation": "three-segment-v1",
            "jury_roster": "roster-a",
            "jury_model_ref": "jury-fixture",
            "reader_model": "reader-fixture",
            "reader_tokenizer": "tokenizer-fixture",
            "reader_context": "context-fixture",
        },
    )

    assert report["criteria_review"]["valid_jurors"] == 2
    assert report["criteria_review"]["invalid_jurors"] == 1
    assert report["criteria_review"]["disagreement"] == pytest.approx(2.0)
    records = {row["instrument_id"]: row for row in _rows(work.measurements)}
    assert set(records) == {
        "novelty.atlas_cosine",
        "jury.disagreement_stddev",
        "parse.reliability",
        "reader.mean_logprob",
    }
    assert records["parse.reliability"]["value"] == pytest.approx(2 / 3)
    assert records["parse.reliability"]["confidence"]["invalid_slots"] == 1
    assert records["reader.mean_logprob"]["value"] == pytest.approx(-2.0)
    assert records["novelty.atlas_cosine"]["identities"]["atlas_identity"] == "atlas-full-a"


def test_runtime_completion_is_observed_but_cost_without_provider_statement_is_missing(
    tmp_path,
):
    work = Work(tmp_path / "works", "w-step11")
    work.create(
        {
            "run_budget": {
                "version": 1,
                "batches": [
                    {"batch_id": "close", "pool": "closing", "role": "author_primary"}
                ],
            }
        }
    )
    work.append_decision(
        {
            "ts": "2026-07-23T00:00:00+00:00",
            "layer": "L7",
            "decision": "run_completion:complete_short",
            "reason": "fixture",
            "decided_by": "fixture",
        }
    )
    deps = RealDeps.__new__(RealDeps)
    deps._instrument_recorder = InstrumentRecorder(_registry(), work.measurements)

    deps.record_run_instruments(
        work,
        category="complete_short",
        stop_path="budget",
        measured_at="2026-07-23T00:00:00+00:00",
    )
    deps.record_run_instruments(
        work,
        category="complete_short",
        stop_path="budget",
        measured_at="2026-07-23T00:00:00+00:00",
    )

    rows = _rows(work.measurements)
    assert len(rows) == 2
    records = {row["instrument_id"]: row for row in rows}
    assert records["run.completion"]["value"] == "complete_short"
    assert records["run.completion"]["measurement_status"] == "observed"
    assert records["cost.reconciled_usd"]["value"] is None
    assert records["cost.reconciled_usd"]["measurement_status"] == "missing"
    assert records["cost.reconciled_usd"]["confidence"]["reconciliation_status"] == "unreconciled"


def test_measurement_append_is_idempotent_and_rejects_same_id_with_other_content(
    tmp_path,
):
    registry = _registry()
    recorder = InstrumentRecorder(registry, tmp_path / "measurements.jsonl")
    record = registry.record(
        instrument_id="novelty.atlas_cosine",
        subject_ref="works/w/drafts/v1.md",
        value=0.2,
        context=MeasurementContext(
            input_refs=({"ref": "draft", "hash": "a" * 64},),
            model_ref="deterministic:fixture",
            prompt_ref="none:deterministic",
            prompt_hash="b" * 64,
            identities={
                "atlas_identity": "atlas-a",
                "embedder": "embedder-a",
                "segmentation": "segmentation-a",
            },
            confidence={"calibration": "fixture"},
        ),
        evidence_refs=("evidence",),
        measured_at="2026-07-23T00:00:00+00:00",
    )

    recorder.append(record)
    recorder.append(record)
    assert len(_rows(recorder.path)) == 1
    with pytest.raises(InstrumentError, match="collision"):
        recorder.append(replace(record, value=0.3))
