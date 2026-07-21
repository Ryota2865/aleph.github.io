from pathlib import Path

import pytest

from aleph.core.instruments import InstrumentError, InstrumentRegistry, MeasurementContext


ROOT = Path(__file__).resolve().parents[1]


def _context(**identities):
    return MeasurementContext(
        input_refs=({"ref": "works/w0010/drafts/v1.md", "hash": "a" * 64},),
        model_ref="deterministic:test", prompt_ref="none:deterministic", prompt_hash="b" * 64,
        identities=identities, confidence={"coverage": "full", "calibration": "uncalibrated"},
    )


def test_registry_contains_the_nine_ledger_instruments_and_complete_ledger_fields():
    registry = InstrumentRegistry.load(ROOT / "config" / "instruments.yaml")
    assert len(registry.instrument_ids) == 9
    assert registry.definition("novelty.atlas_cosine").status == "provisional"
    assert registry.definition("cost.reconciled_usd").unit == "USD"


def test_record_requires_provenance_identity_evidence_and_distinguishes_missing_from_zero():
    registry = InstrumentRegistry.load(ROOT / "config" / "instruments.yaml")
    context = _context(atlas_identity="atlas-a", embedder="bge-m3@1", segmentation="paragraph-v1")
    zero = registry.record(instrument_id="novelty.atlas_cosine", subject_ref="works/w0010/drafts/v1.md",
                           value=0.0, context=context, evidence_refs=("state/atlas/identity.json",),
                           measured_at="2026-07-21T00:00:00+00:00")
    assert zero.value == 0.0 and zero.measurement_status == "observed"
    missing = registry.record(instrument_id="novelty.atlas_cosine", subject_ref="works/w0010/drafts/v1.md",
                              value=None, context=context, evidence_refs=("calls.jsonl",), measurement_status="missing")
    assert missing.value is None
    with pytest.raises(InstrumentError, match="required identities"):
        registry.record(instrument_id="novelty.atlas_cosine", subject_ref="x", value=1.0,
                        context=_context(atlas_identity="atlas-a"), evidence_refs=("evidence",))


def test_comparison_refuses_identity_mismatch_and_missing_and_returns_only_scalar_delta():
    registry = InstrumentRegistry.load(ROOT / "config" / "instruments.yaml")
    left_context = _context(atlas_identity="atlas-a", embedder="bge-m3@1", segmentation="paragraph-v1")
    right_context = _context(atlas_identity="atlas-b", embedder="bge-m3@1", segmentation="paragraph-v1")
    left = registry.record(instrument_id="novelty.atlas_cosine", subject_ref="left", value=0.2,
                           context=left_context, evidence_refs=("left-evidence",))
    right = registry.record(instrument_id="novelty.atlas_cosine", subject_ref="right", value=0.5,
                            context=right_context, evidence_refs=("right-evidence",))
    assert registry.compare(left, right).comparable is False
    same = registry.record(instrument_id="novelty.atlas_cosine", subject_ref="same", value=0.5,
                           context=left_context, evidence_refs=("same-evidence",))
    assert registry.compare(left, same).delta == pytest.approx(0.3)
    missing = registry.record(instrument_id="novelty.atlas_cosine", subject_ref="missing", value=None,
                              context=left_context, evidence_refs=("missing-evidence",), measurement_status="invalid")
    assert registry.compare(left, missing).delta is None


def test_provisional_measurement_cannot_drive_an_automatic_decision():
    registry = InstrumentRegistry.load(ROOT / "config" / "instruments.yaml")
    context = _context(atlas_identity="atlas-a", embedder="bge-m3@1", segmentation="paragraph-v1")
    record = registry.record(
        instrument_id="novelty.atlas_cosine",
        subject_ref="draft",
        value=0.2,
        context=context,
        evidence_refs=("evidence",),
    )

    with pytest.raises(InstrumentError, match="not decision-eligible"):
        registry.decision_value(record)
