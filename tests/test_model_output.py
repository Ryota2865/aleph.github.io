from __future__ import annotations

from aleph.core.model_output import parse_model_output


def test_single_fenced_json_keeps_raw_fragment_and_strict_types():
    raw = '前置き\n```json\n{"publish": false, "reason": "保留"}\n```\n後置き'

    result = parse_model_output(raw, schema={"publish": bool, "reason": str})

    assert result.value == {"publish": False, "reason": "保留"}
    assert result.raw == raw
    assert result.fragment == '{"publish": false, "reason": "保留"}'
    assert result.source_span is not None
    assert result.warnings == ()


def test_multiple_json_values_are_ambiguous_and_fail_closed():
    result = parse_model_output(
        '{"publish": true, "reason": "A"}\n{"publish": false, "reason": "B"}',
        schema={"publish": bool, "reason": str},
    )

    assert result.value is None
    assert any("multiple JSON values" in warning for warning in result.warnings)


def test_duplicate_keys_are_rejected_as_contradictory():
    result = parse_model_output(
        '{"publish": true, "publish": false, "reason": "矛盾"}',
        schema={"publish": bool, "reason": str},
    )

    assert result.value is None
    assert any("duplicate JSON key: publish" in warning for warning in result.warnings)


def test_duplicate_key_in_outer_object_fails_closed_even_with_later_valid_object():
    raw = '{"publish": true, "publish": false, "reason": {"publish": true, "reason": "valid"}}'
    schema = {"publish": bool, "reason": str}

    result = parse_model_output(raw, schema=schema, fail_closed=True)

    assert result.value is None
    assert any("duplicate JSON key: publish" in warning for warning in result.warnings)
