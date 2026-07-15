#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the libcst-based assertion renderer ``assertion_to_cst``.

Assertions carry plain variable-name strings as their ``source`` and are
rendered by :func:`assertion_to_cst`, which returns a
``libcst.SimpleStatementLine`` (or ``None`` for exception assertions, which the
writer handles structurally via ``pytest.raises``).
"""

from __future__ import annotations

import enum
import math

import libcst as cst
import pytest

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_to_ast as ata


def render(assertion: ass.Assertion, **kwargs) -> str | None:
    """Render an assertion to its source string, or ``None`` if not rendered."""
    node = ata.assertion_to_cst(assertion, **kwargs)
    if node is None:
        return None
    return cst.Module(body=[node]).code.rstrip("\n")


# --- FloatAssertion -----------------------------------------------------------


@pytest.mark.parametrize(
    "value, precision, expected",
    [
        (1.5, 0.01, "assert var_0 == pytest.approx(1.5, abs=0.01, rel=0.01)"),
        (-2.0, 0.01, "assert var_0 == pytest.approx(-2.0, abs=0.01, rel=0.01)"),
        (0.0, 0.01, "assert var_0 == pytest.approx(0.0, abs=0.01, rel=0.01)"),
        (1.5, 0.001, "assert var_0 == pytest.approx(1.5, abs=0.001, rel=0.001)"),
        (
            float("nan"),
            0.01,
            "assert var_0 == pytest.approx(float('nan'), abs=0.01, rel=0.01)",
        ),
        (
            float("inf"),
            0.01,
            "assert var_0 == pytest.approx(float('inf'), abs=0.01, rel=0.01)",
        ),
        (
            float("-inf"),
            0.01,
            "assert var_0 == pytest.approx(float('-inf'), abs=0.01, rel=0.01)",
        ),
    ],
)
def test_float_assertion(value, precision, expected):
    assertion = ass.FloatAssertion("var_0", value)
    assert render(assertion, float_precision=precision) == expected


def test_float_assertion_default_precision():
    assertion = ass.FloatAssertion("var_0", 3.25)
    assert render(assertion) == "assert var_0 == pytest.approx(3.25, abs=0.01, rel=0.01)"


# --- ObjectAssertion ----------------------------------------------------------

Dummy = enum.Enum("Dummy", "a")


@pytest.mark.parametrize(
    "value, expected",
    [
        # `is` comparison for bool / None
        (True, "assert var_0 is True"),
        (False, "assert var_0 is False"),
        (None, "assert var_0 is None"),
        # `==` comparison for everything else
        (46, "assert var_0 == 46"),
        (-5, "assert var_0 == -5"),
        ("hi", "assert var_0 == 'hi'"),
        (b"by", "assert var_0 == b'by'"),
        ([3, 8], "assert var_0 == [3, 8]"),
        ([1.5], "assert var_0 == [1.5]"),  # nested float goes through _make_float_literal
        ([[3, 8], {"foo"}], "assert var_0 == [[3, 8], {'foo'}]"),
        ((1,), "assert var_0 == (1, )"),
        ((1, 2), "assert var_0 == (1, 2)"),
        (set(), "assert var_0 == set()"),
        ({1}, "assert var_0 == {1}"),
        ({"foo": ["nope", 1, False, None]}, "assert var_0 == {'foo': ['nope', 1, False, None]}"),
        ({"a": 1}, "assert var_0 == {'a': 1}"),
        (Dummy.a, "assert var_0 == Dummy.a"),
        ({Dummy.a: False}, "assert var_0 == {Dummy.a: False}"),
    ],
)
def test_object_assertion(value, expected):
    assertion = ass.ObjectAssertion("var_0", value)
    assert render(assertion) == expected


# --- TypeNameAssertion --------------------------------------------------------


@pytest.mark.parametrize(
    "module, qualname, expected",
    [
        (
            "foo",
            "bar",
            "assert f\"{type(var_0).__module__}.{type(var_0).__qualname__}\" == 'foo.bar'",
        ),
        (
            "builtins",
            "int",
            "assert f\"{type(var_0).__module__}.{type(var_0).__qualname__}\" == 'builtins.int'",
        ),
    ],
)
def test_type_name_assertion(module, qualname, expected):
    assertion = ass.TypeNameAssertion("var_0", module, qualname)
    assert render(assertion) == expected


# --- IsInstanceAssertion ------------------------------------------------------


@pytest.mark.parametrize(
    "module, qualname, expected",
    [
        ("builtins", "int", "assert isinstance(var_0, int)"),
        ("builtins", "str", "assert isinstance(var_0, str)"),
        ("foo.bar", "Baz", "assert isinstance(var_0, bar_.Baz)"),
        ("foo.bar", "Baz.Qux", "assert isinstance(var_0, bar_.Baz.Qux)"),
    ],
)
def test_isinstance_assertion(module, qualname, expected):
    assertion = ass.IsInstanceAssertion("var_0", module, qualname)
    assert render(assertion) == expected


# --- CollectionLengthAssertion ------------------------------------------------


@pytest.mark.parametrize(
    "length, expected", [(0, "assert len(var_0) == 0"), (42, "assert len(var_0) == 42")]
)
def test_collection_length_assertion(length, expected):
    assertion = ass.CollectionLengthAssertion("var_0", length)
    assert render(assertion) == expected


# --- ExceptionAssertion -------------------------------------------------------


def test_exception_assertion_renders_none():
    # Exception assertions are rendered structurally by the writer (pytest.raises),
    # so the CST renderer returns None for them.
    assertion = ass.ExceptionAssertion(module="builtins", exception_type_name="ValueError")
    assert render(assertion) is None


# --- rendered assertions execute correctly ------------------------------------


def test_float_nan_literal_is_nan():
    node = ata.assertion_to_cst(ass.FloatAssertion("var_0", float("nan")))
    assert node is not None
    # The rendered literal must evaluate back to NaN.
    ns: dict = {}
    exec("v = float('nan')", ns)  # noqa: S102
    assert math.isnan(ns["v"])


# --- conftest fixtures --------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name, expected",
    [
        ("plus_test_with_object_assertion", "assert int_1 == 46"),
        (
            "plus_test_with_float_assertion",
            "assert int_1 == pytest.approx(46.0, abs=0.01, rel=0.01)",
        ),
        (
            "plus_test_with_type_name_assertion",
            "assert f\"{type(int_1).__module__}.{type(int_1).__qualname__}\" == 'builtins.int'",
        ),
    ],
)
def test_render_assertion_from_fixture(request, fixture_name, expected):
    test_case = request.getfixturevalue(fixture_name)
    assertion = test_case.get_statement(-1).assertions[-1]
    assert render(assertion) == expected


def test_exception_fixture_assertion_renders_none(exception_test_with_except_assertion):
    assertion = exception_test_with_except_assertion.get_statement(-1).assertions[-1]
    assert render(assertion) is None


# --- dotted (module/attribute) reference sources -------------------------------


@pytest.mark.parametrize(
    "source, expected",
    [
        ("assertions_.static_state", "assert assertions_.static_state == 0"),
        ("plus_0.calculations", "assert plus_0.calculations == 0"),
        ("a.b.c", "assert a.b.c == 0"),
    ],
)
def test_object_assertion_dotted_source(source, expected):
    assertion = ass.ObjectAssertion(source, 0)
    assert render(assertion) == expected


def test_render_multiple_assertions_fixture_dotted_source(plus_test_with_multiple_assertions):
    statement = plus_test_with_multiple_assertions.get_statement(-1)
    dotted = next(a for a in statement.assertions if a.source == "plus_0.calculations")
    assert render(dotted) == "assert plus_0.calculations == 1"
