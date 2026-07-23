from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from aleph.core.instruments import InstrumentRegistry, MeasurementContext
from scripts.build_phase5_fixation_calibration import build_bundle, write_bundle


ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_DIR = ROOT / "reports" / "calibration" / "phase5"


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_fixation_fixture_is_sealed_to_existing_artifacts_and_label_provenance():
    manifest, _ = build_bundle(ROOT)

    assert manifest["schema_version"] == 1
    assert manifest["sealed"] is True
    assert manifest["purpose"] == "calibration_evaluation_only"
    assert manifest["prohibited_uses"] == [
        "classifier_training",
        "prompt_tuning",
        "label_revision_from_evaluation_results",
    ]
    assert [fixture["fixture_id"] for fixture in manifest["fixtures"]] == [
        "w0004_aphorism_engine",
        "w0005_dialectical_shuttle",
        "w0007_professional_metaphor_network",
        "w0008_quotation_transformation",
        "w0008_w0009_backstage_counterexample",
    ]

    for fixture in manifest["fixtures"]:
        assert set(fixture["labels"]) == {
            "surface_repetition",
            "rhetorical_device",
            "world_type",
            "role_transformation",
        }
        for label in fixture["labels"].values():
            assert label["status"] in {"observed", "unclassified"}
            assert label["epistemic_status"] in {"observation", "interpretation"}
            assert label["provenance_refs"]
        for ref in fixture["target_refs"] + fixture["provenance_refs"]:
            assert ref["sha256"] == _sha256(ROOT / ref["ref"])

    payload = dict(manifest)
    seal = payload.pop("manifest_sha256")
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    assert seal == sha256(encoded).hexdigest()


def test_baseline_records_preserve_narrow_claim_statuses_counterexamples_and_identity():
    manifest, records = build_bundle(ROOT)
    by_subject = {record.subject_ref: record for record in records}

    lexical = by_subject["calibration:fixation:w0004-w0005-w0007"]
    assert lexical.instrument_id == "fixation.poetics_lexical"
    assert lexical.status == "calibrated_limited"
    assert lexical.measurement_status == "observed"
    assert lexical.value["threshold_exceeded"] is False
    assert lexical.value["scope_mismatch"] == "cross_work_rhetoric_outside_claim"

    w0008_missing = by_subject["calibration:fixation:w0008:quotation_transform"]
    assert w0008_missing.instrument_id == "fixation.house_style"
    assert w0008_missing.measurement_status == "missing"
    assert w0008_missing.value is None

    w0009_zero = by_subject["calibration:fixation:w0009:era_pinned:L4:era_taisho_showa"]
    assert w0009_zero.measurement_status == "observed"
    assert w0009_zero.value == 0.0

    assert manifest["baseline_comparisons"][0]["comparable"] is False
    assert "classifier" in manifest["baseline_comparisons"][0]["identity_mismatches"]
    assert "prompt" in manifest["baseline_comparisons"][0]["identity_mismatches"]
    assert "schema" in manifest["baseline_comparisons"][0]["identity_mismatches"]

    registry = InstrumentRegistry.load(ROOT / "config" / "instruments.yaml")
    context = MeasurementContext(
        input_refs=({"ref": "fixture", "hash": "a" * 64},),
        model_ref="deterministic:test",
        prompt_ref="none:deterministic",
        prompt_hash="b" * 64,
        identities={
            "classifier": "test",
            "prompt": "test",
            "schema": "test",
            "segmentation": "test",
            "author_epoch": "test",
            "collection_manifest": "test",
        },
        confidence={"coverage": "none", "calibration": "uncalibrated"},
    )
    for status in ("missing", "invalid", "unclassified"):
        record = registry.record(
            instrument_id="fixation.house_style",
            subject_ref=f"status:{status}",
            value=None,
            context=context,
            evidence_refs=("fixture",),
            measurement_status=status,
            measured_at="2026-07-23T00:00:00+00:00",
        )
        assert record.measurement_status == status and record.value is None


def test_same_inputs_regenerate_byte_identical_bundle(tmp_path):
    first_manifest, first_records = build_bundle(ROOT)
    second_manifest, second_records = build_bundle(ROOT)
    assert first_manifest == second_manifest
    assert [asdict(record) for record in first_records] == [
        asdict(record) for record in second_records
    ]

    first = tmp_path / "first"
    second = tmp_path / "second"
    write_bundle(ROOT, first)
    write_bundle(ROOT, second)
    for name in ("fixation_fixture_manifest.json", "fixation_baseline_records.jsonl"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert (first / name).read_bytes() == (CALIBRATION_DIR / name).read_bytes()
