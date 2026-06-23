#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the deterministic AAA marker inserter (aaa_inserter.py)."""

from __future__ import annotations

from pynguin.refinement.aaa_inserter import insert_aaa_markers_simple

SIMPLE_TEST = """\
import module_0

def test_case_0():
    var_0 = 5
    var_1 = module_0.add(var_0, var_0)
    assert var_1 == 10
"""


def _positions(code: str) -> tuple[int, int, int]:
    return (code.index("# Arrange"), code.index("# Act"), code.index("# Assert"))


def test_inserts_all_three_markers():
    # focal line (1-based) of the ``module_0.add`` call is line 5
    result = insert_aaa_markers_simple(SIMPLE_TEST, focal_line_number=5)
    assert "# Arrange" in result
    assert "# Act" in result
    assert "# Assert" in result


def test_markers_are_in_correct_order():
    result = insert_aaa_markers_simple(SIMPLE_TEST, focal_line_number=5)
    arrange, act, assert_ = _positions(result)
    assert arrange < act < assert_


def test_act_section_contains_focal_call():
    result = insert_aaa_markers_simple(SIMPLE_TEST, focal_line_number=5)
    lines = result.split("\n")
    act_index = next(i for i, line in enumerate(lines) if line.strip() == "# Act")
    assert "module_0.add" in lines[act_index + 1]


def test_assert_section_contains_assertion():
    result = insert_aaa_markers_simple(SIMPLE_TEST, focal_line_number=5)
    lines = result.split("\n")
    assert_index = next(i for i, line in enumerate(lines) if line.strip() == "# Assert")
    assert lines[assert_index + 1].strip().startswith("assert")


def test_is_idempotent():
    once = insert_aaa_markers_simple(SIMPLE_TEST, focal_line_number=5)
    twice = insert_aaa_markers_simple(once, focal_line_number=5)
    # Running again must not duplicate markers.
    assert once.count("# Arrange") == 1
    assert twice.count("# Arrange") == 1
    assert twice.count("# Act") == 1
    assert twice.count("# Assert") == 1


def test_returns_original_when_no_test_function():
    code = "x = 1\ny = 2\n"
    assert insert_aaa_markers_simple(code, focal_line_number=1) == code


def test_invalid_focal_line_falls_back_to_heuristic():
    # focal_line_number of 0 forces the "last non-blank line before assert" path
    result = insert_aaa_markers_simple(SIMPLE_TEST, focal_line_number=0)
    arrange, act, assert_ = _positions(result)
    assert arrange < act < assert_
    lines = result.split("\n")
    act_index = next(i for i, line in enumerate(lines) if line.strip() == "# Act")
    assert "module_0.add" in lines[act_index + 1]


def test_handles_test_without_assertions():
    code = """\
import module_0

def test_case_0():
    var_0 = 5
    module_0.do_something(var_0)
"""
    result = insert_aaa_markers_simple(code, focal_line_number=5)
    assert "# Arrange" in result
    assert "# Act" in result
    # No assertion present -> no Assert marker is added.
    assert "# Assert" not in result


def test_skips_docstring_when_placing_markers():
    code = '''\
def test_case_0():
    """A docstring that must not be treated as the Arrange section."""
    var_0 = 5
    var_1 = module_0.add(var_0, var_0)
    assert var_1 == 10
'''
    result = insert_aaa_markers_simple(code, focal_line_number=0)
    lines = result.split("\n")
    arrange_index = next(i for i, line in enumerate(lines) if line.strip() == "# Arrange")
    # The docstring stays above the Arrange marker.
    assert any('"""' in line for line in lines[:arrange_index])
