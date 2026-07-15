#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Renders assertions to libcst nodes for the generated test source."""

from __future__ import annotations

import math
from typing import Any

import libcst as cst

import pynguin.assertion.assertion as ass
import pynguin.utils.type_utils as tu
from pynguin.utils.naming import get_module_alias

# ---------------------------------------------------------------------------
# libcst-based assertion rendering
# ---------------------------------------------------------------------------

_DEFAULT_FLOAT_PRECISION = 0.01


def assertion_to_cst(
    assertion: ass.Assertion,
    float_precision: float = _DEFAULT_FLOAT_PRECISION,
) -> cst.SimpleStatementLine | None:
    """Convert an Assertion to a libcst SimpleStatementLine.

    Args:
        assertion: The assertion to convert.
        float_precision: The precision used for float comparisons.

    Returns:
        The CST assert statement, or ``None`` for ExceptionAssertion (handled
        structurally by the writer via ``pytest.raises``).
    """
    if isinstance(assertion, ass.FloatAssertion):
        return _float_assertion_to_cst(assertion, float_precision)
    if isinstance(assertion, ass.ObjectAssertion):
        return _object_assertion_to_cst(assertion)
    if isinstance(assertion, ass.TypeNameAssertion):
        return _type_name_assertion_to_cst(assertion)
    if isinstance(assertion, ass.IsInstanceAssertion):
        return _isinstance_assertion_to_cst(assertion)
    if isinstance(assertion, ass.CollectionLengthAssertion):
        return _collection_length_assertion_to_cst(assertion)
    if isinstance(assertion, ass.ExceptionAssertion):
        return None  # Handled structurally by the writer via pytest.raises
    return None  # pragma: no cover


def _make_assert(test: cst.BaseExpression) -> cst.SimpleStatementLine:
    return cst.SimpleStatementLine(body=[cst.Assert(test=test)])


def _name(var: str) -> cst.BaseExpression:
    # ``var`` is usually a bare variable name, but may also be a dotted
    # attribute-access path (e.g. ``plus_0.calculations``) when the assertion
    # source refers to an object's attribute rather than a bound variable
    # itself; parse it as an expression rather than assuming a plain
    # identifier.
    return cst.parse_expression(var)


def _float_assertion_to_cst(
    assertion: ass.FloatAssertion, float_precision: float
) -> cst.SimpleStatementLine:
    approx_call = cst.Call(
        func=cst.Attribute(value=cst.Name("pytest"), attr=cst.Name("approx")),
        args=[
            cst.Arg(value=_make_float_literal(float(assertion.value))),
            cst.Arg(
                keyword=cst.Name("abs"),
                value=_make_float_literal(float_precision),
                equal=cst.AssignEqual(
                    whitespace_before=cst.SimpleWhitespace(""),
                    whitespace_after=cst.SimpleWhitespace(""),
                ),
            ),
            cst.Arg(
                keyword=cst.Name("rel"),
                value=_make_float_literal(float_precision),
                equal=cst.AssignEqual(
                    whitespace_before=cst.SimpleWhitespace(""),
                    whitespace_after=cst.SimpleWhitespace(""),
                ),
            ),
        ],
    )
    return _make_assert(
        cst.Comparison(
            left=_name(assertion.source),
            comparisons=[cst.ComparisonTarget(operator=cst.Equal(), comparator=approx_call)],
        )
    )


def _make_float_literal(value: float) -> cst.BaseExpression:
    if math.isnan(value):
        return cst.Call(func=cst.Name("float"), args=[cst.Arg(value=cst.SimpleString("'nan'"))])
    if math.isinf(value):
        literal = "'inf'" if value > 0 else "'-inf'"
        return cst.Call(func=cst.Name("float"), args=[cst.Arg(value=cst.SimpleString(literal))])
    if value < 0:
        return cst.UnaryOperation(operator=cst.Minus(), expression=cst.Float(str(-value)))
    return cst.Float(str(value))


def _object_assertion_to_cst(assertion: ass.ObjectAssertion) -> cst.SimpleStatementLine:
    value = assertion.object
    if isinstance(value, bool) or value is None:
        # assert var is True/False/None
        return _make_assert(
            cst.Comparison(
                left=_name(assertion.source),
                comparisons=[
                    cst.ComparisonTarget(
                        operator=cst.Is(),
                        comparator=_value_to_cst(value),
                    )
                ],
            )
        )
    # assert var == <value>
    return _make_assert(
        cst.Comparison(
            left=_name(assertion.source),
            comparisons=[
                cst.ComparisonTarget(
                    operator=cst.Equal(),
                    comparator=_value_to_cst(value),
                )
            ],
        )
    )


def _value_to_cst(value: Any) -> cst.BaseExpression:  # noqa: C901
    """Recursively convert a Python value to a libcst expression.

    Args:
        value: The value to convert.

    Returns:
        The CST expression representing the value.
    """
    if value is None:
        return cst.Name("None")
    if isinstance(value, bool):
        return cst.Name("True" if value else "False")
    if isinstance(value, int):
        if value < 0:
            return cst.UnaryOperation(operator=cst.Minus(), expression=cst.Integer(str(-value)))
        return cst.Integer(str(value))
    if isinstance(value, float):
        return _make_float_literal(value)
    if isinstance(value, str):
        return cst.SimpleString(repr(value))
    if isinstance(value, bytes):
        return cst.SimpleString(repr(value))
    if isinstance(value, complex):
        return cst.SimpleString(repr(value))
    if tu.is_enum(type(value)):
        # EnumClass.MEMBER
        class_name = type(value).__name__
        member_name = value.name
        return cst.Attribute(value=cst.Name(class_name), attr=cst.Name(member_name))
    typ = type(value)
    if tu.is_list(typ):
        return cst.List(elements=[cst.Element(value=_value_to_cst(v)) for v in value])
    if tu.is_tuple(typ):
        if len(value) == 1:
            return cst.Tuple(
                elements=[
                    cst.Element(
                        value=_value_to_cst(value[0]),
                        comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" ")),
                    )
                ]
            )
        return cst.Tuple(elements=[cst.Element(value=_value_to_cst(v)) for v in value])
    if tu.is_set(typ):
        elems = list(value)
        if not elems:
            # empty set: set()
            return cst.Call(func=cst.Name("set"))
        return cst.Set(elements=[cst.Element(value=_value_to_cst(v)) for v in elems])
    if tu.is_dict(typ):
        return cst.Dict(
            elements=[
                cst.DictElement(key=_value_to_cst(k), value=_value_to_cst(v))
                for k, v in value.items()
            ]
        )
    return cst.SimpleString(repr(value))


def _type_name_assertion_to_cst(assertion: ass.TypeNameAssertion) -> cst.SimpleStatementLine:
    var = _name(assertion.source)
    type_call = cst.Call(func=cst.Name("type"), args=[cst.Arg(value=var)])

    fstring = cst.FormattedString(
        parts=[
            cst.FormattedStringExpression(
                expression=cst.Attribute(value=type_call, attr=cst.Name("__module__"))
            ),
            cst.FormattedStringText(value="."),
            cst.FormattedStringExpression(
                expression=cst.Attribute(value=type_call, attr=cst.Name("__qualname__"))
            ),
        ]
    )
    expected = cst.SimpleString(repr(f"{assertion.module}.{assertion.qualname}"))
    return _make_assert(
        cst.Comparison(
            left=fstring,
            comparisons=[cst.ComparisonTarget(operator=cst.Equal(), comparator=expected)],
        )
    )


def _isinstance_assertion_to_cst(assertion: ass.IsInstanceAssertion) -> cst.SimpleStatementLine:
    # assert isinstance(var, Type) or assert isinstance(var, module.Type)
    var = _name(assertion.source)

    if assertion.module == "builtins":
        type_expr: cst.BaseExpression = cst.Name(assertion.qualname)
    else:
        module_alias = get_module_alias(assertion.module)
        type_expr = cst.Name(module_alias)
        for part in assertion.qualname.split("."):
            type_expr = cst.Attribute(value=type_expr, attr=cst.Name(part))

    isinstance_call = cst.Call(
        func=cst.Name("isinstance"),
        args=[cst.Arg(value=var), cst.Arg(value=type_expr)],
    )
    return _make_assert(isinstance_call)


def _collection_length_assertion_to_cst(
    assertion: ass.CollectionLengthAssertion,
) -> cst.SimpleStatementLine:
    # assert len(var) == n  # noqa: ERA001
    len_call = cst.Call(
        func=cst.Name("len"),
        args=[cst.Arg(value=_name(assertion.source))],
    )
    n = cst.Integer(str(assertion.length))
    return _make_assert(
        cst.Comparison(
            left=len_call,
            comparisons=[cst.ComparisonTarget(operator=cst.Equal(), comparator=n)],
        )
    )
