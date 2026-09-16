#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import ast

import pytest

import pynguin.configuration as config
from pynguin.assertion.mutation_analysis.transformer import (
    ParentNodeTransformer,
    create_module,
)
from pynguin.utils.timeout import TestExecutionTimeoutError


def test_create_module_normal():
    code = """def foo():
    return 42
"""
    tree = ast.parse(code)
    mod = create_module(tree, "temp_mod")
    assert mod.foo() == 42


def test_create_module_timeout():
    code = """import time
time.sleep(2)
"""
    tree = ast.parse(code)
    config.configuration.stopping.maximum_module_execution_timeout = 0.1
    with pytest.raises(TestExecutionTimeoutError):
        create_module(tree, "sleep_mod")


def test_parent_node_transformer():
    code = "a = 1 + 2"
    tree = ParentNodeTransformer.create_ast(code)
    assign_node = tree.body[0]
    assert isinstance(assign_node, ast.Assign)
    assert hasattr(assign_node, "parent")
    assert assign_node.parent == tree


def test_parent_node_transformer_node_with_parent():
    code = "a = 1 + 2"
    tree = ParentNodeTransformer.create_ast(code)
    transformer = ParentNodeTransformer()
    tree2 = transformer.visit(tree)
    assign_node = tree2.body[0]
    assert assign_node.parent == tree2
