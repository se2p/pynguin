#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Pure value<->CST rendering helpers for ML-generated (nested) literals.

These helpers render plain Python values (possibly nested lists/tuples of
int/float/bool/complex/str/None) as libcst expression nodes and parse such
nodes back into values.  They deliberately avoid any numpy dependency so
they can be imported without the optional numpy extra.
"""

from __future__ import annotations

import ast
import math

import libcst as cst


def _int_to_cst(value: int) -> cst.BaseExpression:
    if value < 0:
        return cst.UnaryOperation(
            operator=cst.Minus(),
            expression=cst.Integer(str(abs(value))),
        )
    return cst.Integer(str(value))


def _float_to_cst(value: float) -> cst.BaseExpression:
    abs_val = abs(value)
    if not math.isfinite(abs_val):
        # inf/nan are not valid float literal tokens; render as float("inf")/float("nan").
        inner: cst.BaseExpression = cst.Call(
            func=cst.Name("float"),
            args=[cst.Arg(value=cst.SimpleString(repr(repr(abs_val))))],
        )
    else:
        float_str = repr(abs_val)
        if "." not in float_str and "e" not in float_str:
            float_str += ".0"
        inner = cst.Float(float_str)
    if value < 0:
        return cst.UnaryOperation(
            operator=cst.Minus(),
            expression=inner,
        )
    return inner


def ml_value_to_cst(value: object) -> cst.BaseExpression:  # noqa: C901
    """Render a (possibly nested) value as a CST literal expression.

    Supports lists, tuples, ints, floats, bools, complex numbers, strings,
    and ``None``; containers are rendered recursively.

    Args:
        value: The value to render.

    Returns:
        A ``cst.BaseExpression`` representing the value.

    Raises:
        ValueError: If the value (or a nested element) has an unsupported type.
    """
    if isinstance(value, list):
        return cst.List(elements=[cst.Element(value=ml_value_to_cst(item)) for item in value])
    if isinstance(value, tuple):
        elements = [cst.Element(value=ml_value_to_cst(item)) for item in value]
        if len(elements) == 1:
            # A single-element tuple needs a trailing comma.
            elements[0] = cst.Element(
                value=elements[0].value,
                comma=cst.Comma(whitespace_after=cst.SimpleWhitespace("")),
            )
        return cst.Tuple(elements=elements)
    if value is None:
        return cst.Name("None")
    if isinstance(value, bool):  # must come before int: bool is a subclass of int
        return cst.Name("True" if value else "False")
    if isinstance(value, int):
        return _int_to_cst(value)
    if isinstance(value, float):
        return _float_to_cst(value)
    if isinstance(value, complex):
        if not (math.isfinite(value.real) and math.isfinite(value.imag)):
            raise ValueError(f"Cannot render non-finite complex value {value!r} as CST.")
        # repr of a complex, e.g. "(1.5+2j)" or "2j", parses cleanly.
        return cst.parse_expression(repr(value))
    if isinstance(value, str):
        return cst.SimpleString(repr(value))
    raise ValueError(f"Unsupported value type for CST rendering: {type(value)!r}")


def _name_to_value(expr: cst.Name) -> object:
    mapping: dict[str, object] = {"True": True, "False": False, "None": None}
    if expr.value in mapping:
        return mapping[expr.value]
    raise ValueError(f"Unsupported name in ML literal: {expr.value!r}")


def _call_to_value(expr: cst.Call) -> float:
    # Only float("inf")/float("nan")-style calls are supported.
    if (
        isinstance(expr.func, cst.Name)
        and expr.func.value == "float"
        and len(expr.args) == 1
        and isinstance(expr.args[0].value, cst.SimpleString)
    ):
        return float(ast.literal_eval(expr.args[0].value.value))
    raise ValueError("Unsupported call expression in ML literal.")


def _binary_to_value(expr: cst.BinaryOperation) -> object:
    left = ml_cst_to_value(expr.left)
    right = ml_cst_to_value(expr.right)
    if not isinstance(left, int | float | complex) or not isinstance(right, int | float | complex):
        raise ValueError("Unsupported operand types in ML literal binary operation.")
    if isinstance(expr.operator, cst.Add):
        return left + right
    if isinstance(expr.operator, cst.Subtract):
        return left - right
    raise ValueError(f"Unsupported binary operator in ML literal: {type(expr.operator)!r}")


def ml_cst_to_value(expr: cst.BaseExpression) -> object:  # noqa: C901
    """Parse a CST literal expression back into a plain Python value.

    This is the inverse of :func:`ml_value_to_cst`.

    Args:
        expr: The CST expression to parse.

    Returns:
        The parsed Python value.

    Raises:
        ValueError: If the expression contains unsupported nodes.
    """
    if isinstance(expr, cst.List):
        return [ml_cst_to_value(element.value) for element in expr.elements]
    if isinstance(expr, cst.Tuple):
        return tuple(ml_cst_to_value(element.value) for element in expr.elements)
    if isinstance(expr, cst.Integer):
        return int(expr.value)
    if isinstance(expr, cst.Float):
        return float(expr.value)
    if isinstance(expr, cst.Imaginary):
        return complex(expr.value)
    if isinstance(expr, cst.UnaryOperation) and isinstance(expr.operator, cst.Minus):
        inner = ml_cst_to_value(expr.expression)
        if isinstance(inner, int | float | complex) and not isinstance(inner, bool):
            return -inner
        raise ValueError("Unsupported operand in unary minus of ML literal.")
    if isinstance(expr, cst.Name):
        return _name_to_value(expr)
    if isinstance(expr, cst.SimpleString):
        return ast.literal_eval(expr.value)
    if isinstance(expr, cst.Call):
        return _call_to_value(expr)
    if isinstance(expr, cst.BinaryOperation):
        return _binary_to_value(expr)
    raise ValueError(f"Unsupported CST node in ML literal: {type(expr)!r}")
