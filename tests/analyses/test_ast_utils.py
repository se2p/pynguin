#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the standard-library ``ast`` helper utilities."""

import ast

import pytest

from pynguin.analyses.ast_utils import scope_line_range
from pynguin.analyses.syntaxtree import (
    _nested_statements,  # noqa: PLC2701
    get_class_node_from_ast,
    get_function_node_from_ast,
)


def test_scope_line_range_module_starts_at_zero():
    # A module reports line 0 (matching astroid's ``Module.fromlineno`` and the
    # ``<module>`` code object convention used by the instrumentation transformer).
    module = ast.parse("import os\n\ndef foo():\n    pass\n")
    start, _ = scope_line_range(module)
    assert start == 0


def test_scope_line_range_empty_module():
    assert scope_line_range(ast.parse("")) == (0, 0)


def test_scope_line_range_function():
    module = ast.parse("def foo():\n    pass\n")
    assert scope_line_range(module.body[0]) == (1, 2)


@pytest.mark.parametrize(
    "source",
    [
        "for _ in range(1):\n    def target():\n        pass\n",
        "while True:\n    def target():\n        pass\n",
        "with open('x'):\n    def target():\n        pass\n",
        "match value:\n    case 1:\n        def target():\n            pass\n",
        "if cond:\n    def target():\n        pass\n",
        "try:\n    def target():\n        pass\nexcept Exception:\n    pass\n",
    ],
)
def test_get_function_node_from_ast_descends_into_flow_control(source):
    module = ast.parse(source)
    found = get_function_node_from_ast(module, "target")
    assert found is not None
    assert found.name == "target"


@pytest.mark.parametrize(
    "source",
    [
        "for _ in range(1):\n    class Target:\n        pass\n",
        "while True:\n    class Target:\n        pass\n",
        "match value:\n    case 1:\n        class Target:\n            pass\n",
        "if cond:\n    class Target:\n        pass\n",
    ],
)
def test_get_class_node_from_ast_descends_into_flow_control(source):
    module = ast.parse(source)
    found = get_class_node_from_ast(module, "Target")
    assert found is not None
    assert found.name == "Target"


@pytest.mark.parametrize(
    "source",
    [
        "async def outer():\n    async with ctx():\n        def target():\n            pass\n",
        "async def outer():\n    async for _ in gen():\n        def target():\n            pass\n",
    ],
)
def test_nested_statements_covers_async_flow_control(source):
    # ``async with``/``async for`` are only valid inside an async function, so
    # exercise ``_nested_statements`` on the inner block directly.
    outer = ast.parse(source).body[0]
    inner = outer.body[0]
    nested = _nested_statements(inner)
    assert any(isinstance(stmt, ast.FunctionDef) and stmt.name == "target" for stmt in nested)


def test_get_function_node_from_ast_ignores_nested_scopes():
    # A method defined inside a class must not be found when searching the module.
    module = ast.parse("class C:\n    def method(self):\n        pass\n")
    assert get_function_node_from_ast(module, "method") is None
