from __future__ import annotations

import pytest

from scripts.exp_transmute_pilot import (
    extract_structure_features,
    form_fidelity,
    retained_feature_ratio,
)

pytestmark = pytest.mark.m6


def test_law_detector_extracts_structural_features() -> None:
    source = """第一条　この規程において「利用者」とは、庭園を利用する者をいう。
２　管理者は、次の各号に掲げる行為を制限できる。ただし、緊急の場合はこの限りでない。
一　植栽を損傷すること。
二　火気を使用すること。
"""
    features = extract_structure_features("law", source)

    assert features == {
        "law.article",
        "law.paragraph",
        "law.item",
        "law.definition",
        "law.proviso",
    }


def test_law_form_fidelity_counts_retained_source_features() -> None:
    source = """第一条　この規程において「利用者」とは、庭園を利用する者をいう。
２　管理者は、次の各号に掲げる行為を制限できる。ただし、緊急の場合はこの限りでない。
一　植栽を損傷すること。
"""
    generated = """第一条　この作品において「記憶」とは、薄明に残る像をいう。
２　観測者は、記録を静かに読み替えなければならない。
"""

    assert form_fidelity("law", source, generated) == pytest.approx(3 / 5)


def test_rfc_detector_extracts_structural_features() -> None:
    source = """Abstract

This document defines a small protocol.

1. Introduction

Endpoints MUST send a greeting. Receivers SHOULD reply within one second.
Senders MAY retry once.
"""
    features = extract_structure_features("rfc", source)

    assert features == {
        "rfc.abstract",
        "rfc.section",
        "rfc.must",
        "rfc.should",
        "rfc.may",
    }


def test_rfc_form_fidelity_counts_retained_source_features() -> None:
    source = """Abstract

This document defines a small protocol.

1. Introduction

Endpoints MUST send a greeting. Receivers SHOULD reply within one second.
Senders MAY retry once.
"""
    generated = """Abstract

This text keeps a procedural shell.

1. Opening

The speaker MUST name the room. The listener MAY answer with silence.
"""

    assert form_fidelity("rfc", source, generated) == pytest.approx(4 / 5)


def test_retained_feature_ratio_returns_zero_for_unmeasurable_source() -> None:
    assert retained_feature_ratio(set(), {"rfc.must"}) == 0.0
    assert extract_structure_features("unknown", "MUST") == set()
