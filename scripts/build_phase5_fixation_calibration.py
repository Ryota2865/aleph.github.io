#!/usr/bin/env python3
"""Build the Phase 5C step-9 fixation fixture from immutable local artifacts.

This builder performs no provider calls and does not calculate a new house-style
classification.  It seals owner-mediated Fable labels and projects already
recorded lexical/classifier outputs through the Phase 5 InstrumentRegistry.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from aleph.core.instruments import InstrumentRecord, InstrumentRegistry, MeasurementContext
from aleph.meta.poetics import _jaccard


_MEASURED_AT = "2026-07-23T00:00:00+00:00"
_W0004_EXCERPT = (
    "逃げると言われる役者ほど、逃げ道の位置をよく見る。"
    "乾いた赤ほど、よく残るものはない。"
    "段取りほど、よく隠れるものはない。"
    "半分残った名ほど呼びにくいものはない。"
    "大きな言葉ほど、仮小屋の梁へ当たる音は軽い。"
)
_W0005_EXCERPT = (
    "だが、問題はそこで終わらない。いかなる「問題」が問題として提出されうるのか。"
    "しかし、問題はそこで止まらない。行為の成功は、誰にとっての成功か。"
)
_W0007_EXCERPT = (
    "折り目は、進物の掛け紙と同じ向きにした。折り目は家を語る。"
    "畳み方の正しい品は仕舞い方の正しい家から来て、"
    "折り目は掛け紙の向きに揃い、折り目のところで止まった。"
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _ref(root: Path, relative: str) -> dict[str, str]:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"sealed fixation source is missing: {relative}")
    return {"ref": relative, "sha256": _sha256(path)}


def _label(
    *,
    status: str,
    value: str | None,
    epistemic_status: str,
    claim: str,
    provenance_refs: list[str],
) -> dict[str, Any]:
    return {
        "status": status,
        "value": value,
        "epistemic_status": epistemic_status,
        "claim": claim,
        "provenance_refs": provenance_refs,
    }


def _fixture_definitions() -> list[dict[str, Any]]:
    unclassified = lambda claim, refs: _label(  # noqa: E731 - compact sealed schema declaration
        status="unclassified",
        value=None,
        epistemic_status="observation",
        claim=claim,
        provenance_refs=refs,
    )
    return [
        {
            "fixture_id": "w0004_aphorism_engine",
            "targets": ["works/w0004/final/text.md"],
            "provenance": ["reports/CRITIQUE_FABLE5_CHAT_w0004_20260712.md"],
            "labels": {
                "surface_repetition": _label(
                    status="observed", value="repeated_hodo_construction",
                    epistemic_status="interpretation",
                    claim="Fable identifies high-frequency ～ほど aphoristic sentences.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0004_20260712.md"],
                ),
                "rhetorical_device": _label(
                    status="observed", value="aphorism_engine",
                    epistemic_status="interpretation",
                    claim="The repetition is labeled an aphoristic engine approaching a tic.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0004_20260712.md"],
                ),
                "world_type": unclassified(
                    "The critique does not label world type as the fixation carrier.",
                    ["reports/CRITIQUE_FABLE5_CHAT_w0004_20260712.md"],
                ),
                "role_transformation": unclassified(
                    "No role transformation is claimed for this fixture.",
                    ["reports/CRITIQUE_FABLE5_CHAT_w0004_20260712.md"],
                ),
            },
        },
        {
            "fixture_id": "w0005_dialectical_shuttle",
            "targets": ["works/w0005/final/text.md"],
            "provenance": ["reports/CRITIQUE_FABLE5_CHAT_w0005_20260713.md"],
            "labels": {
                "surface_repetition": _label(
                    status="observed", value="constrained_but_not_reduced_pattern",
                    epistemic_status="interpretation",
                    claim="Fable identifies repeated dialectical sentence turns.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0005_20260713.md"],
                ),
                "rhetorical_device": _label(
                    status="observed", value="dialectical_shuttle",
                    epistemic_status="interpretation",
                    claim="The device is labeled the philosophical form of w0004's engine.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0005_20260713.md"],
                ),
                "world_type": unclassified(
                    "The critique does not label world type as the fixation carrier.",
                    ["reports/CRITIQUE_FABLE5_CHAT_w0005_20260713.md"],
                ),
                "role_transformation": unclassified(
                    "No role transformation is claimed for this fixture.",
                    ["reports/CRITIQUE_FABLE5_CHAT_w0005_20260713.md"],
                ),
            },
        },
        {
            "fixture_id": "w0007_professional_metaphor_network",
            "targets": ["works/w0007/final/text.md"],
            "provenance": ["reports/CRITIQUE_FABLE5_CHAT_w0007review_20260717.md"],
            "labels": {
                "surface_repetition": _label(
                    status="observed", value="folding_and_trade_vocabulary",
                    epistemic_status="interpretation",
                    claim="Fable identifies recurring fold, wrapping, cutting, and trade vocabulary.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0007review_20260717.md"],
                ),
                "rhetorical_device": _label(
                    status="observed", value="aphorism_engine_in_craft_clothing",
                    epistemic_status="interpretation",
                    claim="The aphorism engine is identified as returning in craft clothing.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0007review_20260717.md"],
                ),
                "world_type": _label(
                    status="observed", value="professional_interior_metaphor_network",
                    epistemic_status="interpretation",
                    claim="Professional vocabularies organize a unified metaphorical world.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0007review_20260717.md"],
                ),
                "role_transformation": unclassified(
                    "No narrator-to-character role transformation is claimed here.",
                    ["reports/CRITIQUE_FABLE5_CHAT_w0007review_20260717.md"],
                ),
            },
        },
        {
            "fixture_id": "w0008_quotation_transformation",
            "targets": ["works/w0008/final/text.md"],
            "provenance": ["reports/CRITIQUE_FABLE5_CHAT_w0008review_20260718.md"],
            "labels": {
                "surface_repetition": unclassified(
                    "The critique does not claim lexical disappearance or a surface rate.",
                    ["reports/CRITIQUE_FABLE5_CHAT_w0008review_20260718.md"],
                ),
                "rhetorical_device": _label(
                    status="observed", value="aphoristic_voice_persists_as_object",
                    epistemic_status="interpretation",
                    claim="Fable says the house style is staged as an object rather than escaped.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0008review_20260718.md"],
                ),
                "world_type": _label(
                    status="observed", value="backstage_world",
                    epistemic_status="interpretation",
                    claim="The critique preserves backstage staging as a distinct house-style path.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0008review_20260718.md"],
                ),
                "role_transformation": _label(
                    status="observed", value="narration_to_character_quotation",
                    epistemic_status="interpretation",
                    claim="Aphoristic assertions are reassigned to the teacher's quoted speech.",
                    provenance_refs=["reports/CRITIQUE_FABLE5_CHAT_w0008review_20260718.md"],
                ),
            },
        },
        {
            "fixture_id": "w0008_w0009_backstage_counterexample",
            "targets": [
                "works/w0008/ablation/classification.json",
                "works/w0008/niche/covariate_markers.json",
                "works/w0009/experiment/classification.json",
                "works/w0009/experiment/manifest.json",
            ],
            "provenance": [
                "reports/EXP_w0008_ablation_20260718.md",
                "reports/EXP_w0009_l2_era_20260719.md",
            ],
            "labels": {
                "surface_repetition": _label(
                    status="observed", value="aphoristic_marker_rates_recorded",
                    epistemic_status="observation",
                    claim="Existing classifications contain observed aphoristic marker rates, including 0.0.",
                    provenance_refs=["reports/EXP_w0009_l2_era_20260719.md"],
                ),
                "rhetorical_device": _label(
                    status="observed", value="house_style_markers_do_not_move_together",
                    epistemic_status="interpretation",
                    claim="The reports separate aphoristic voice from era and backstage markers.",
                    provenance_refs=[
                        "reports/EXP_w0008_ablation_20260718.md",
                        "reports/EXP_w0009_l2_era_20260719.md",
                    ],
                ),
                "world_type": _label(
                    status="observed", value="backstage_world_rate_1_0_despite_exclusion",
                    epistemic_status="observation",
                    claim="w0009 records backstage_world=1.0 after backstage terms were excluded from the meaning core.",
                    provenance_refs=["reports/EXP_w0009_l2_era_20260719.md"],
                ),
                "role_transformation": _label(
                    status="observed", value="quotation_transform_rate_recorded",
                    epistemic_status="observation",
                    claim="w0009 records quotation_transform separately from aphoristic_voice.",
                    provenance_refs=["reports/EXP_w0009_l2_era_20260719.md"],
                ),
            },
        },
    ]


def _context(
    root: Path,
    *,
    refs: list[str],
    model_ref: str,
    prompt_ref: str,
    prompt_hash: str,
    identities: dict[str, str],
    confidence: dict[str, Any],
    warnings: tuple[str, ...] = (),
) -> MeasurementContext:
    return MeasurementContext(
        input_refs=tuple({"ref": ref, "hash": _sha256(root / ref)} for ref in refs),
        model_ref=model_ref,
        prompt_ref=prompt_ref,
        prompt_hash=prompt_hash,
        identities=identities,
        confidence=confidence,
        warnings=warnings,
    )


def _baseline_records(root: Path, registry: InstrumentRegistry) -> list[InstrumentRecord]:
    lexical_refs = [
        "works/w0004/final/text.md",
        "works/w0005/final/text.md",
        "works/w0007/final/text.md",
        "tests/test_fixation_check_first_case.py",
    ]
    lexical_series = [
        _jaccard(_W0004_EXCERPT, _W0005_EXCERPT),
        _jaccard(_W0005_EXCERPT, _W0007_EXCERPT),
    ]
    records = [
        registry.record(
            instrument_id="fixation.poetics_lexical",
            subject_ref="calibration:fixation:w0004-w0005-w0007",
            value={
                "jaccard_series": lexical_series,
                "mean": sum(lexical_series) / len(lexical_series),
                "threshold": 0.8,
                "threshold_exceeded": False,
                "scope_mismatch": "cross_work_rhetoric_outside_claim",
            },
            context=_context(
                root,
                refs=lexical_refs,
                model_ref="deterministic:aleph.meta.poetics._jaccard",
                prompt_ref="none:deterministic",
                prompt_hash=sha256(b"none:deterministic").hexdigest(),
                identities={
                    "detector": "aleph.meta.poetics.character-bigram-jaccard@v1",
                    "threshold": "0.8",
                    "tokenization": "unicode-character-2gram",
                },
                confidence={
                    "coverage": "three sealed cross-work excerpts",
                    "calibration": "scope-counterexample, not poetics-version calibration",
                    "validity": "deterministic calculation does not validate house-style detection",
                },
                warnings=("Input is intentionally outside the instrument's narrow poetics-version claim.",),
            ),
            evidence_refs=tuple(lexical_refs),
            measured_at=_MEASURED_AT,
        )
    ]

    w8_ref = "works/w0008/ablation/classification.json"
    w8 = json.loads((root / w8_ref).read_text(encoding="utf-8"))
    w8_prompt_ref = "scripts/run_w0008.py"
    w8_context = _context(
        root,
        refs=[w8_ref],
        model_ref="gemma-4-26B-A4B-it-qat-UD-Q4_K_XL:recorded-scout-output",
        prompt_ref=f"{w8_prompt_ref}#_classify_prompt",
        prompt_hash=_sha256(root / w8_prompt_ref),
        identities={
            "classifier": "w0008-recorded-scout-classification",
            "prompt": "w0008-house-style-legacy-four-marker",
            "schema": "era_backstage_aphoristic_prior-attractor",
            "segmentation": "L4-proposal_and_L5-greedy-600-char",
            "author_epoch": "legacy:missing-author-epoch",
            "collection_manifest": _sha256(root / w8_ref),
        },
        confidence={
            "coverage": "all recorded w0008 classification units",
            "calibration": "uncalibrated legacy classifier output",
            "validity": "existing output only; no relabeling",
        },
        warnings=("Legacy author_epoch is missing; do not compare across epochs.",),
    )
    records.extend(
        [
            registry.record(
                instrument_id="fixation.house_style",
                subject_ref="calibration:fixation:w0008:aozora:L4:aphoristic_voice",
                value=w8["aggregates"]["aozora"]["L4"]["marker_rates"]["aphoristic_voice"],
                context=w8_context,
                evidence_refs=(w8_ref, "reports/EXP_w0008_ablation_20260718.md"),
                measured_at=_MEASURED_AT,
            ),
            registry.record(
                instrument_id="fixation.house_style",
                subject_ref="calibration:fixation:w0008:none:L5:backstage_world",
                value=w8["aggregates"]["none"]["L5"]["marker_rates"]["backstage_world"],
                context=w8_context,
                evidence_refs=(w8_ref, "reports/EXP_w0008_ablation_20260718.md"),
                measured_at=_MEASURED_AT,
            ),
            registry.record(
                instrument_id="fixation.house_style",
                subject_ref="calibration:fixation:w0008:quotation_transform",
                value=None,
                context=w8_context,
                evidence_refs=(w8_ref, "reports/CRITIQUE_FABLE5_CHAT_w0008review_20260718.md"),
                measurement_status="missing",
                measured_at=_MEASURED_AT,
            ),
        ]
    )

    w9_ref = "works/w0009/experiment/classification.json"
    w9 = json.loads((root / w9_ref).read_text(encoding="utf-8"))
    w9_prompt_ref = "scripts/run_w0009.py"
    w9_context = _context(
        root,
        refs=[w9_ref, "works/w0009/experiment/manifest.json"],
        model_ref="gemma-4-26B-A4B-it-qat-UD-Q4_K_XL:recorded-scout-output",
        prompt_ref=f"{w9_prompt_ref}#_classify_prompt",
        prompt_hash=_sha256(root / w9_prompt_ref),
        identities={
            "classifier": "w0009-recorded-scout-classification",
            "prompt": "w0009-house-style-v1",
            "schema": "era_backstage_aphoristic_quotation_perspective",
            "segmentation": "L4-proposal_and_L5-greedy-600-char",
            "author_epoch": "legacy:missing-author-epoch",
            "collection_manifest": _sha256(root / "works/w0009/experiment/manifest.json"),
        },
        confidence={
            "coverage": "40/40 recorded units; unclassified=0",
            "calibration": "uncalibrated preregistered classifier output",
            "validity": "single generation with dependent pseudo-sections",
        },
        warnings=(
            "Do not interpret pseudo-sections as independent samples.",
            "Legacy author_epoch is missing; do not compare across epochs.",
        ),
    )
    for arm, level, marker in (
        ("era_pinned", "L4", "era_taisho_showa"),
        ("era_pinned", "L4", "backstage_world"),
        ("era_unpinned", "L4", "quotation_transform"),
        ("era_unpinned", "L5", "aphoristic_voice"),
    ):
        records.append(
            registry.record(
                instrument_id="fixation.house_style",
                subject_ref=f"calibration:fixation:w0009:{arm}:{level}:{marker}",
                value=w9["aggregates"][arm][level]["marker_rates"][marker],
                context=w9_context,
                evidence_refs=(w9_ref, "reports/EXP_w0009_l2_era_20260719.md"),
                measured_at=_MEASURED_AT,
            )
        )
    return records


def build_bundle(root: Path) -> tuple[dict[str, Any], list[InstrumentRecord]]:
    root = Path(root)
    registry = InstrumentRegistry.load(root / "config" / "instruments.yaml")
    fixtures = []
    for source in _fixture_definitions():
        fixture = {
            "fixture_id": source["fixture_id"],
            "target_refs": [_ref(root, ref) for ref in source["targets"]],
            "provenance_refs": [_ref(root, ref) for ref in source["provenance"]],
            "labels": source["labels"],
        }
        fixtures.append(fixture)

    comparison = {
        "left": "w0008-recorded-house-style-baseline",
        "right": "w0009-recorded-house-style-baseline",
        "comparable": False,
        "identity_mismatches": ["classifier", "prompt", "schema", "collection_manifest"],
        "interpretation": "Keep both baselines; do not calculate a delta or winner.",
    }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "fixture_version": "phase5c-step9-v1",
        "sealed": True,
        "sealed_at": _MEASURED_AT,
        "purpose": "calibration_evaluation_only",
        "prohibited_uses": [
            "classifier_training",
            "prompt_tuning",
            "label_revision_from_evaluation_results",
        ],
        "status_semantics": {
            "observed": "A value, including numeric 0.0, is present in existing evidence.",
            "missing": "The expected field was not part of the source schema or artifact.",
            "invalid": "A source output exists but failed its registered validity rule.",
            "unclassified": "The source did not assign a class; do not coerce to false or 0.0.",
        },
        "instrument_claims": {
            "fixation.poetics_lexical": "Only adjacent poetics-version character 2-gram similarity.",
            "fixation.house_style": "Provisional cross-work rhetoric/world/role observation; no automatic decision.",
        },
        "fixtures": fixtures,
        "baseline_comparisons": [comparison],
    }
    manifest["manifest_sha256"] = sha256(_canonical_bytes(manifest)).hexdigest()
    return manifest, _baseline_records(root, registry)


def write_bundle(root: Path, output_dir: Path) -> None:
    manifest, records = build_bundle(root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_bytes = _canonical_bytes(manifest) + b"\n"
    records_bytes = b"".join(_canonical_bytes(asdict(record)) + b"\n" for record in records)
    (output_dir / "fixation_fixture_manifest.json").write_bytes(manifest_bytes)
    (output_dir / "fixation_baseline_records.jsonl").write_bytes(records_bytes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/calibration/phase5"),
    )
    args = parser.parse_args()
    output = args.output_dir if args.output_dir.is_absolute() else args.root / args.output_dir
    write_bundle(args.root, output)


if __name__ == "__main__":
    main()
