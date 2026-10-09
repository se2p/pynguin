#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for aligning original and refined test statements (alignment.py)."""

import ast

from pynguin.refinement.alignment import (
    align_statements,
    find_test_function,
    flatten_unconditional,
    normalise_expression,
)


def _statements(code: str) -> list[ast.stmt]:
    func = find_test_function(ast.parse(code))
    assert func is not None
    return flatten_unconditional(func.body)


def test_align_statements_maps_chained_renames_and_inlined_literals():
    original = _statements(
        "def test_1():\n    int_0 = 5\n    foo_0 = Foo(int_0)\n    var_0 = foo_0.bar()\n"
    )
    refined = _statements("def test_bar():\n    foo = Foo(5)\n    bar = foo.bar()\n")
    alignment = align_statements(original, refined)
    assert alignment.rename_map == {"foo_0": "foo", "var_0": "bar"}
    assert ast.unparse(alignment.literal_map["int_0"]) == "5"


def test_normalise_expression_renames_and_inlines():
    node = ast.parse("var_0 == int_0", mode="eval").body
    literal = ast.parse("5", mode="eval").body
    assert normalise_expression(node, {"var_0": "result"}, {"int_0": literal}) == "result == 5"


def test_flatten_unconditional_skips_conditional_and_raises_blocks():
    stmts = _statements(
        "def test_1():\n"
        "    a = f()\n"
        "    with open(p) as fh:\n"
        "        b = g()\n"
        "    if a:\n"
        "        c = h()\n"
        "    with pytest.raises(E):\n"
        "        d = k()\n"
    )
    assert [ast.unparse(stmt) for stmt in stmts] == ["a = f()", "b = g()"]


def test_find_test_function_skips_helpers():
    tree = ast.parse("def helper():\n    pass\n\ndef test_x():\n    pass\n")
    func = find_test_function(tree)
    assert func is not None
    assert func.name == "test_x"
