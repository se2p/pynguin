# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides base classes of a program graph."""
from typing import Any, Generic, Optional, Set, TypeVar

import networkx as nx
from bytecode import BasicBlock
from networkx import lowest_common_ancestor
from networkx.drawing.nx_pydot import to_pydot


class ProgramGraphNode:
    """A base class for a node of the program graph."""

    def __init__(
        self,
        index: int,
        basic_block: Optional[BasicBlock] = None,
        is_artificial: bool = False,
    ) -> None:
        self._index = index
        self._basic_block = basic_block
        self._is_artificial = is_artificial

    @property
    def index(self) -> int:
        """Provides the index of the node.

        Returns:
            The index of the node
        """
        return self._index

    @property
    def basic_block(self) -> Optional[BasicBlock]:
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

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ProgramGraphNode):
            return False
        if self is other:
            return True
        return self._index == other.index

    def __hash__(self) -> int:
        return 31 + 17 * self._index

    def __str__(self) -> str:
        return f"ProgramGraphNode({self._index})"

    def __repr__(self) -> str:
        return f"ProgramGraphNode(index={self._index}, basic_block={self._basic_block})"


N = TypeVar("N", bound=ProgramGraphNode)  # pylint: disable=invalid-name


class ProgramGraph(Generic[N]):
    """Provides a base implementation for a program graph.

    Internally, this program graph uses the `NetworkX` library to hold the graph and
    do all the operations on it.
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()  # TODO(sl) consider a multi graph if necessary?!?

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

    def get_predecessors(self, node: N) -> Set[N]:
        """Provides a set of all direct predecessors of a node.

        Args:
            node: The node to start

        Returns:
            A set of direct predecessors of the node
        """
        predecessors: Set[N] = set()
        for predecessor in self._graph.predecessors(node):
            predecessors.add(predecessor)
        return predecessors

    def get_successors(self, node: N) -> Set[N]:
        """Provides a set of all direct successors of a node.

        Args:
            node: The node to start

        Returns:
            A set of direct successors of the node
        """
        successors: Set[N] = set()
        for successor in self._graph.successors(node):
            successors.add(successor)
        return successors

    @property
    def nodes(self) -> Set[N]:
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
    def entry_node(self) -> Optional[N]:
        """Provides the entry node of the graph.

        Returns:
            The entry node of the graph
        """
        for node in self._graph.nodes:
            if len(self.get_predecessors(node)) == 0:
                return node
        return None

    @property
    def exit_nodes(self) -> Set[N]:
        """Provides the exit nodes of the graph.

        Returns:
            The set of exit nodes of the graph
        """
        exit_nodes: Set[N] = set()
        for node in self._graph.nodes:
            if len(self.get_successors(node)) == 0:
                exit_nodes.add(node)
        return exit_nodes

    def get_transitive_successors(self, node: N) -> Set[N]:
        """Calculates the transitive closure (the transitive successors) of a node.

        Args:
            node: The node to start with

        Returns:
            The transitive closure of the node
        """
        return self._get_transitive_successors(node, set())

    def _get_transitive_successors(self, node: N, done: Set[N]) -> Set[N]:
        successors: Set[N] = set()
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

    def to_dot(self) -> str:
        """Provides the DOT representation of this graph.

        Returns:
            The DOT representation of this graph
        """
        dot = to_pydot(self._graph)
        return dot.to_string()
