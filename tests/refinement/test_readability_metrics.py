#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the readability scoring metrics (readability_metrics.py)."""

from __future__ import annotations

import pytest

from pynguin.refinement import readability_metrics as rm


def test_score_aaa_returns_zero_without_markers():
    assert rm.score_aaa("def test_x():\n    assert True\n") == 0.0


def test_score_aaa_full_markers_in_order_is_max():
    code = """\
def test_x():
    # Arrange
    x = 1
    # Act
    y = x + 1
    # Assert
    assert y == 2
"""
    assert rm.score_aaa(code) == 1.0


def test_score_aaa_partial_markers_below_one():
    code = "def test_x():\n    # Arrange\n    assert True\n"
    score = rm.score_aaa(code)
    assert 0.0 < score < 1.0


def test_score_semantic_names_all_generic_is_zero():
    code = "def test_x():\n    var_0 = 5\n    var_1 = 3\n    assert var_0 != var_1\n"
    assert rm.score_semantic_names(code) == 0.0


def test_score_semantic_names_all_semantic_is_one():
    code = (
        "def test_addition():\n    operand = 5\n    result = operand + 1\n    assert result == 6\n"
    )
    assert rm.score_semantic_names(code) == 1.0


def test_score_semantic_names_syntax_error_is_zero():
    assert rm.score_semantic_names("def test_x(:\n    assert") == 0.0


def test_score_semantic_names_no_identifiers_is_zero():
    assert rm.score_semantic_names("assert True\n") == 0.0


def test_score_assertion_clarity_specific_assertion():
    assert rm.score_assertion_clarity("def test_x():\n    assert foo == 1\n") == 1.0


def test_score_assertion_clarity_trivial_assertion():
    # ``assert flag`` is a bare Name -> not considered specific.
    assert rm.score_assertion_clarity("def test_x():\n    flag = True\n    assert flag\n") == 0.0


def test_score_assertion_clarity_no_assertions_is_zero():
    assert rm.score_assertion_clarity("def test_x():\n    x = 1\n") == 0.0


@pytest.mark.parametrize(
    ("line_count", "expected"),
    [
        (0, 0.0),
        (5, 0.5),
        (10, 1.0),
    ],
)
def test_score_conciseness_short_tests(line_count, expected):
    code = "\n".join(f"x{i} = {i}" for i in range(line_count))
    assert rm.score_conciseness(code) == pytest.approx(expected)


def test_score_conciseness_long_test_decays():
    code = "\n".join(f"x{i} = {i}" for i in range(80))
    assert rm.score_conciseness(code) == 0.0


def test_compute_all_has_aggregate_mean():
    code = """\
def test_addition():
    # Arrange
    operand = 5
    # Act
    result = operand + 1
    # Assert
    assert result == 6
"""
    scores = rm.compute_all(code)
    assert set(scores) == {
        "aaa",
        "semantic_names",
        "assertion_clarity",
        "conciseness",
        "aggregate",
    }
    component_mean = (
        sum(scores[k] for k in ("aaa", "semantic_names", "assertion_clarity", "conciseness")) / 4
    )
    assert scores["aggregate"] == pytest.approx(component_mean)
