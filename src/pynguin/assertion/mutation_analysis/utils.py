#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/utils.py.
"""

import ast
import copy
import random
import types

from typing import Any

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator


def create_module(ast_node: ast.Module, module_name: str = "mutant", module_dict: dict[str, Any] | None = None):
    code = compile(ast_node, module_name, "exec")
    module = types.ModuleType(module_name)
    module.__dict__.update(module_dict or {})
    exec(code, module.__dict__)
    return module


class RandomSampler:
    def __init__(self, percentage: int) -> None:
        self.percentage = percentage if 0 < percentage < 100 else 100

    def is_mutation_time(self) -> bool:
        return random.randrange(100) < self.percentage


class ParentNodeTransformer(ast.NodeTransformer):
    def __init__(self) -> None:
        super().__init__()
        self.parent = None

    def visit(self, node: ast.AST) -> ast.AST:
        if getattr(node, 'parent', None):
            node = copy.copy(node)
            if hasattr(node, 'lineno'):
                del node.lineno
        node.parent = getattr(self, 'parent', None)
        node.children = []
        self.parent = node
        result_node = super().visit(node)
        self.parent = node.parent
        if self.parent:
            self.parent.children += [node] + node.children
        return result_node


def create_ast(code: str) -> ast.AST:
    return ParentNodeTransformer().visit(ast.parse(code))


def is_docstring(node: ast.AST) -> bool:
    def_node = node.parent.parent
    return (
        isinstance(def_node, (ast.FunctionDef, ast.ClassDef, ast.Module))
        and def_node.body
        and isinstance(def_node.body[0], ast.Expr)
        and isinstance(def_node.body[0].value, ast.Str)
        and def_node.body[0].value == node
    )


def sort_operators(operators: list[type[MutationOperator]]) -> list[type[MutationOperator]]:
    return sorted(operators, key=lambda cls: cls.name())
