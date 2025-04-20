#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a transformer for modules ASTs.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/utils.py
and integrated in Pynguin.
"""

import ast
import copy
import types

from typing import TypeVar


def create_module(ast_node: ast.Module, module_name: str) -> types.ModuleType:
    """Creates a module from an AST node.

    Args:
        ast_node: The AST node.
        module_name: The name of the module.

    Returns:
        The created module.
    """
    code = compile(ast_node, module_name, "exec")
    module = types.ModuleType(module_name)
    exec(code, module.__dict__)  # noqa: S102
    return module


T = TypeVar("T", bound=ast.AST)


class ParentNodeTransformer(ast.NodeTransformer):
    """A transformer that adds a parent attribute to each node of the AST."""

    @classmethod
    def create_ast(cls, code: str) -> ast.Module:
        """Create an AST from a string.

        Args:
            code: The code to parse.

        Returns:
            The module node of the AST with the parent and children attributes set.
        """
        return cls().visit(ast.parse(code))

    def __init__(self) -> None:
        """Initialize the transformer."""
        super().__init__()
        self.parent: ast.AST | None = None

    def visit(self, node: T) -> T:
        """Transform a node of the AST.

        Args:
            node: The node to transform.

        Returns:
            The transformed node.
        """
        # Copy the node because an optimisation of the AST makes it
        # reuse the same node at multiple places in the tree to
        # improve memory usage. It would break our goal to create a
        # tree with a single parent for each node if we don't copy.
        if hasattr(node, "parent"):
            node = copy.copy(node)
            if hasattr(node, "lineno"):
                delattr(node, "lineno")

        node.parent = self.parent  # type: ignore[attr-defined]
        node.children = set()  # type: ignore[attr-defined]

        parent_save = self.parent
        self.parent = node

        # Visit the children of the node and discard the result
        # as it returns the same node with the children modified.
        super().visit(node)

        self.parent = parent_save

        # Add all the ancestors of the node to the children list
        # of the parent if it exists. This is done here so that
        # the tree has been fully traversed before adding the children.
        if self.parent is not None:
            parent_children: set[ast.AST] = self.parent.children  # type: ignore[attr-defined]

            parent_children.add(node)

            node_children: set[ast.AST] = node.children  # type: ignore[attr-defined]
            parent_children.update(node_children)

        return node
