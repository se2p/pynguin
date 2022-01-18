#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides base classes of a program graph."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

import networkx as nx
from bytecode import UNSET, BasicBlock, Compare
from networkx import lowest_common_ancestor
from networkx.drawing.nx_pydot import to_pydot

# Key for storing branch value in networkx edge.
EDGE_DATA_BRANCH_VALUE = "branch_value"


class ProgramGraphNode:
    """A base class for a node of the program graph."""

    def __init__(
        self,
        index: int,
        basic_block: BasicBlock | None = None,
        is_artificial: bool = False,
    ) -> None:
        self._index = index
        self._basic_block = basic_block
        self._is_artificial = is_artificial
        self._predicate_id: int | None = None

    @property
    def index(self) -> int:
        """Provides the index of the node.

        Returns:
            The index of the node
        """
        return self._index

    @property
    def basic_block(self) -> BasicBlock | None:
        """Provides the basic block attached to this node.

        Returns:
            The optional basic block attached to this node
        """
        return self._basic_block

    @property
    def is_artificial(self) -> bool:
        """Whether or not a node is artificially inserted into the graph.

        Returns:
            Whether or not a node is artificially inserted into the graph
        """
        return self._is_artificial

    @property
    def predicate_id(self) -> int | None:
        """If this node creates a branch based on a predicate, than this stores the id
        of this predicate.

        Returns:
            The predicate id assigned to this node, if any.
        """
        return self._predicate_id

    @predicate_id.setter
    def predicate_id(self, predicate_id: int) -> None:
        """Set a new predicate id.

        Args:
            predicate_id: The predicate id
        """
        self._predicate_id = predicate_id

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ProgramGraphNode):
            return False
        if self is other:
            return True
        return self._index == other.index

    def __hash__(self) -> int:
        return 31 + 17 * self._index

    def __str__(self) -> str:
        result = f"ProgramGraphNode({self._index})"
        if self._predicate_id is not None:
            result += f"\npredicate_id {self._predicate_id}"
        if self._basic_block is not None:
            instructions = []
            for instr in self._basic_block:
                arg = instr.arg
                if isinstance(arg, BasicBlock):
                    # We cannot determine which ProgramGraphNode this is.
                    arg = "ProgramGraphNode"
                elif isinstance(arg, Compare):
                    arg = arg.name
                elif arg is UNSET:
                    arg = ""
                else:
                    arg = repr(arg)
                formatted = instr.name
                if arg != "":
                    formatted += f" {arg}"
                instructions.append(formatted)
            result += "\n" + "\n".join(instructions)
        return result

    def __repr__(self) -> str:
        return f"ProgramGraphNode(index={self._index}, basic_block={self._basic_block})"


N = TypeVar("N", bound=ProgramGraphNode)  # pylint: disable=invalid-name


class ProgramGraph(Generic[N]):
    """Provides a base implementation for a program graph.

    Internally, this program graph uses the `NetworkX` library to hold the graph and
    do all the operations on it.
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    def add_node(self, node: N, **attr: Any) -> None:
        """Add a node to the graph

        Args:
            node: The node
            attr: A dict of attributes that will be attached to the node
        """
        self._graph.add_node(node, **attr)

    def add_edge(self, start: N, end: N, **attr: Any) -> None:
        """Add an edge between two nodes to the graph

        Args:
            start: The start node of the edge
            end: The end node of the edge
            attr: A dict of attributes that will be attached to the edge.
        """
        self._graph.add_edge(start, end, **attr)

    def get_predecessors(self, node: N) -> set[N]:
        """Provides a set of all direct predecessors of a node.

        Args:
            node: The node to start

        Returns:
            A set of direct predecessors of the node
        """
        predecessors: set[N] = set()
        for predecessor in self._graph.predecessors(node):
            predecessors.add(predecessor)
        return predecessors

    def get_successors(self, node: N) -> set[N]:
        """Provides a set of all direct successors of a node.

        Args:
            node: The node to start

        Returns:
            A set of direct successors of the node
        """
        successors: set[N] = set()
        for successor in self._graph.successors(node):
            successors.add(successor)
        return successors

    @property
    def nodes(self) -> set[N]:
        """Provides all nodes in the graph.

        Returns:
            The set of all nodes in the graph
        """
        return {
            node
            for node in self._graph.nodes  # pylint: disable=unnecessary-comprehension
        }

    @property
    def graph(self) -> nx.DiGraph:
        """The internal graph.

        Returns:
            The internal graph
        """
        return self._graph

    @property
    def entry_node(self) -> N | None:
        """Provides the entry node of the graph.

        Returns:
            The entry node of the graph
        """
        for node in self._graph.nodes:
            if len(self.get_predecessors(node)) == 0:
                return node
        return None

    @property
    def exit_nodes(self) -> set[N]:
        """Provides the exit nodes of the graph.

        Returns:
            The set of exit nodes of the graph
        """
        exit_nodes: set[N] = set()
        for node in self._graph.nodes:
            if len(self.get_successors(node)) == 0:
                exit_nodes.add(node)
        return exit_nodes

    def get_transitive_successors(self, node: N) -> set[N]:
        """Calculates the transitive closure (the transitive successors) of a node.

        Args:
            node: The node to start with

        Returns:
            The transitive closure of the node
        """
        return self._get_transitive_successors(node, set())

    def _get_transitive_successors(self, node: N, done: set[N]) -> set[N]:
        successors: set[N] = set()
        for successor_node in self.get_successors(node):
            if successor_node not in done:
                successors.add(successor_node)
                done.add(successor_node)
                successors.update(self._get_transitive_successors(successor_node, done))
        return successors

    def get_least_common_ancestor(self, first: N, second: N) -> N:
        """Calculates the least or lowest common ancestor node of two nodes of the
        graph.

        Both nodes have to be part of the graph!

        Args:
            first: The first node
            second: The second node

        Returns:
            The least common ancestor node of the two nodes
        """
        return lowest_common_ancestor(self._graph, first, second)

    @property
    def dot(self) -> str:
        """Provides the DOT representation of this graph.

        Returns:
            The DOT representation of this graph
        """
        dot = to_pydot(self._graph)
        return dot.to_string()


G = TypeVar("G", bound=ProgramGraph)  # pylint: disable=invalid-name


def filter_dead_code_nodes(graph: G, entry_node_index: int = 0) -> G:
    """Prunes dead nodes from the given graph.

    A dead node is a node that has no entry node.  To specify a legal entry node,
    one can use the `entry_node_index` parameter.

    Args:
        graph: The graph to prune nodes from
        entry_node_index: The index of the valid entry node

    Returns:
        The graph without the pruned dead nodes
    """
    has_changed = True
    while has_changed:
        # Do this until we have reached a fixed point, i.e., removed all dead
        # nodes from the graph.
        has_changed = False
        for node in graph.nodes:
            if graph.get_predecessors(node) == set() and node.index != entry_node_index:
                # The only node in the graph that is allowed to have no predecessor
                # is the entry node, i.e., the node with index 0.  All other nodes
                # without predecessors are considered dead code and thus removed.
                graph.graph.remove_node(node)
                has_changed = True
    return graph
