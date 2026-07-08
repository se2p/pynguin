#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Thin libcst statement builders shared by the migrated test-case tests.

These wrap :func:`stmt` (a one-line libcst parse) so test bodies can construct
``tc.Statement`` / ``tc.TestCase`` objects without repeating the parse boilerplate.
Keep these tiny and dependency-free; they mirror the ``_make_statement`` helper in
``tests/conftest.py``.
"""

from __future__ import annotations

import libcst as cst

import pynguin.testcase.testcase as tc


def stmt(
    code: str, bound_variable: str | None = None, bound_type: type | None = None
) -> tc.Statement:
    """Build a libcst-backed ``Statement`` from a single source line.

    Args:
        code: A single line of Python source (trailing newline optional).
        bound_variable: The variable name bound by the statement, if any.
        bound_type: The runtime type bound to ``bound_variable``, if known.

    Returns:
        The constructed statement.
    """
    node = cst.parse_module(code if code.endswith("\n") else code + "\n").body[0]
    return tc.Statement(node=node, bound_variable=bound_variable, bound_type=bound_type)


def assign(name: str, rhs: str, bound_type: type | None = None) -> tc.Statement:
    """Build ``name = rhs`` binding *name* (optionally typed).

    Args:
        name: The target variable name.
        rhs: The right-hand-side source expression.
        bound_type: The runtime type bound to *name*, if known.

    Returns:
        The assignment statement.
    """
    return stmt(f"{name} = {rhs}", bound_variable=name, bound_type=bound_type)


def call_stmt(name: str, expr: str, bound_type: type | None = None) -> tc.Statement:
    """Build ``name = expr`` for a call/constructor result.

    Alias of :func:`assign` kept for readability at call sites that build calls.

    Args:
        name: The target variable name.
        expr: The call/constructor source expression.
        bound_type: The runtime type bound to *name*, if known.

    Returns:
        The assignment statement.
    """
    return assign(name, expr, bound_type=bound_type)


def int_stmt(name: str, value: int) -> tc.Statement:
    """Build ``name = <int>`` bound to ``int``."""
    return assign(name, repr(int(value)), bound_type=int)


def float_stmt(name: str, value: float) -> tc.Statement:
    """Build ``name = <float>`` bound to ``float``."""
    return assign(name, repr(float(value)), bound_type=float)


def str_stmt(name: str, value: str) -> tc.Statement:
    """Build ``name = <str>`` bound to ``str``."""
    return assign(name, repr(str(value)), bound_type=str)


def bool_stmt(name: str, value: bool) -> tc.Statement:  # noqa: FBT001
    """Build ``name = <bool>`` bound to ``bool``."""
    return assign(name, repr(bool(value)), bound_type=bool)


def bytes_stmt(name: str, value: bytes) -> tc.Statement:
    """Build ``name = <bytes>`` bound to ``bytes``."""
    return assign(name, repr(bytes(value)), bound_type=bytes)


def make_test_case(*statements: tc.Statement) -> tc.TestCase:
    """Build a ``tc.TestCase`` from an ordered sequence of statements.

    Args:
        *statements: The statements to append, in order.

    Returns:
        The populated test case.
    """
    test_case = tc.TestCase()
    for statement in statements:
        test_case.add_statement(statement)
    return test_case
