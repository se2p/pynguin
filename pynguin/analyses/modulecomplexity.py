#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses implemented on the abstract syntax tree.

The implementation of this module contains some code adopted from the ``mccabe``
library (https://github.com/PyCQA/mccabe), which was released by Florent Xicluna,
Tarek Ziade, and Ned Batchelder under Expad License.

Original copyright notice:
Copyright © <year> Ned Batchelder
Copyright © 2011-2013 Tarek Ziade <tarek@ziade.org>
Copyright © 2013 Florent Xicluna <florent.xicluna@gmail.com>

Licensed under the terms of the Expat License

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation files
(the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from __future__ import annotations

import ast
from abc import ABCMeta
from ast import iter_child_nodes
from collections import defaultdict
from dataclasses import dataclass


class _ASTVisitor(metaclass=ABCMeta):
    """Performs a depth-first walk of the AST."""

    def __init__(self):
        self.node = None
        self.visitor = None
        self._cache = {}

    def default(self, node: ast.AST) -> None:
        for child in iter_child_nodes(node):
            self.dispatch(child)

    def dispatch(self, node: ast.AST):
        self.node = node
        klass = node.__class__
        meth = self._cache.get(klass)
        if meth is None:
            class_name = klass.__name__
            meth = getattr(self.visitor, "visit" + class_name, self.default)
            self._cache[klass] = meth
        return meth(node)  # type: ignore

    def preorder(self, tree: ast.AST, visitor: _ASTVisitor):
        """Do preorder walk of tree using visitor"""
        self.visitor = visitor
        self.dispatch(tree)

    visit = dispatch


@dataclass(unsafe_hash=True, frozen=True)
class _PathNode:
    name: str


class _PathGraph:
    def __init__(self, name, entity, lineno, column=0):
        self.name = name
        self.entity = entity
        self.lineno = lineno
        self.column = column
        self.nodes = defaultdict(list)

    def connect(self, n1, n2):
        self.nodes[n1].append(n2)
        # Ensure that the destination node is always counted.
        self.nodes[n2] = []

    def complexity(self):
        """Return the McCabe complexity for the graph.
        V-E+2
        """
        num_edges = sum(len(n) for n in self.nodes.values())
        num_nodes = len(self.nodes)
        return num_edges - num_nodes + 2


class _PathGraphingAstVisitor(_ASTVisitor):
    """A visitor for a parsed Abstract Syntax Tree which finds executable
    statements.
    """

    def __init__(self):
        super().__init__()
        self.class_name = ""
        self.graphs = {}
        self.reset()

    def reset(self):
        self.graph = None
        self.tail = None

    def dispatch_list(self, node_list):
        for node in node_list:
            self.dispatch(node)

    def visitFunctionDef(self, node):
        entity = node.name
        name = "%d:%d: %r" % (node.lineno, node.col_offset, entity)

        if self.graph is not None:
            # closure
            path_node = self.__append_path_node(name)
            self.tail = path_node
            self.dispatch_list(node.body)
            bottom = _PathNode("")
            self.graph.connect(self.tail, bottom)
            self.graph.connect(path_node, bottom)
            self.tail = bottom
        else:
            self.graph = _PathGraph(name, entity, node.lineno, node.col_offset)
            path_node = _PathNode(name)
            self.tail = path_node
            self.dispatch_list(node.body)
            self.graphs[f"{self.class_name}{node.name}"] = self.graph
            self.reset()

    visitAsyncFunctionDef = visitFunctionDef

    def __append_path_node(self, name):
        if not self.tail:
            return
        assert self.graph is not None
        path_node = _PathNode(name)
        self.graph.connect(self.tail, path_node)
        self.tail = path_node
        return path_node

    def visitSimpleStatement(self, node):
        name = f"Stmt {node.lineno}"
        self.__append_path_node(name)

    def default(self, node, *args):
        if isinstance(node, ast.stmt):
            self.visitSimpleStatement(node)
        else:
            super().default(node, *args)

    def visitLoop(self, node):
        name = f"Loop {node.lineno}"
        self._subgraph(node, name)

    visitAsyncFor = visitFor = visitWhile = visitLoop

    def visitIf(self, node):
        name = f"If {node.lineno}"
        self._subgraph(node, name)

    def _subgraph(self, node, name, extra_blocks=()):
        """create the subgraphs representing any `if` and `for` statements"""
        if self.graph is None:
            # global loop
            self.graph = _PathGraph(name, name, node.lineno, node.col_offset)
            path_node = _PathNode(name)
            self._subgraph_parse(node, path_node, extra_blocks)
            self.graphs[f"{self.class_name}{name}"] = self.graph
            self.reset()
        else:
            path_node = self.__append_path_node(name)
            self._subgraph_parse(node, path_node, extra_blocks)

    def _subgraph_parse(self, node, path_node, extra_blocks):
        """parse the body and any `else` block of `if` and `for` statements"""
        loose_ends = []
        self.tail = path_node
        self.dispatch_list(node.body)
        loose_ends.append(self.tail)
        for extra in extra_blocks:
            self.tail = path_node
            self.dispatch_list(extra.body)
            loose_ends.append(self.tail)
        if node.orelse:
            self.tail = path_node
            self.dispatch_list(node.orelse)
            loose_ends.append(self.tail)
        else:
            loose_ends.append(path_node)
        if path_node:
            bottom = _PathNode("")
            assert self.graph is not None
            for le in loose_ends:
                self.graph.connect(le, bottom)
            self.tail = bottom

    def visitTryExcept(self, node):
        name = "TryExcept %d" % node.lineno
        self._subgraph(node, name, extra_blocks=node.handlers)

    visitTry = visitTryExcept

    def visitWith(self, node):
        name = "With %d" % node.lineno
        self.__append_path_node(name)
        self.dispatch_list(node.body)

    visitAsyncWith = visitWith


def mccabe_complexity(tree: ast.AST) -> int:
    """Computes McCabe's complexity for an AST.

    Args:
        tree: the AST

    Returns:
        The McCabe complexity of the AST
    """
    visitor = _PathGraphingAstVisitor()
    visitor.preorder(tree, visitor)
    return sum(graph.complexity() for graph in visitor.graphs.values())
