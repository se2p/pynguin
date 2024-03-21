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


class ParentNodeTransformer(ast.NodeTransformer):
    @classmethod
    def create_ast(cls, code: str) -> ast.AST:
        return cls().visit(ast.parse(code))

    def __init__(self) -> None:
        super().__init__()
        self.parent: ast.AST | None = None

    def visit(self, node: ast.AST) -> ast.AST:
        # Copy the node because an optimisation of the AST makes it
        # reuse the same node at multiple places in the tree to
        # improve memory usage. It would break our goal to create a
        # tree with a single parent for each node if we don't copy.
        if hasattr(node, "parent"):
            node = copy.copy(node)
            if hasattr(node, "lineno"):
                delattr(node, "lineno")

        setattr(node, "parent", self.parent)
        setattr(node, "children", set())

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
            parent_children: set[ast.AST] = getattr(self.parent, "children")

            parent_children.add(node)

            node_children: set[ast.AST] = getattr(node, "children")
            parent_children.update(node_children)

        return node
