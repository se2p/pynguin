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
from typing import List, TypeVar, Generic, Optional

N = TypeVar("N")  # pylint: disable=invalid-name
E = TypeVar("E")  # pylint: disable=invalid-name


class ProgramGraphNode(Generic[E]):
    """A base class for a node of the program graph."""

    def __init__(
        self,
        index: int,
        incoming_edges: Optional[List[E]] = None,
        outgoing_edges: Optional[List[E]] = None,
    ) -> None:
        self._index = index
        self._incoming_edges = incoming_edges if incoming_edges else []
        self._outgoing_edges = outgoing_edges if outgoing_edges else []

    @property
    def index(self) -> int:
        """Provides the index of the node."""
        return self._index

    @property
    def incoming_edges(self) -> List[E]:
        """Return the list of incoming edges."""
        return self._incoming_edges

    @property
    def outgoing_edges(self) -> List[E]:
        """Returns the list of outgoing edges."""
        return self._outgoing_edges

    def add_incoming_edge(self, edge: E) -> None:
        """Adds an incoming edge to this node."""
        self._incoming_edges.append(edge)

    def add_outgoing_edge(self, edge: E) -> None:
        """Adds an outgoing edge to this node."""
        self._outgoing_edges.append(edge)

    def is_entry_node(self) -> bool:
        """Checks whether or not the node is an entry node."""
        return not self._incoming_edges

    def is_exit_node(self) -> bool:
        """Checks whether or not the node is an exit node."""
        return not self._outgoing_edges


class ProgramGraphEdge(Generic[N]):
    """A base class for an edge of the program graph."""

    def __init__(
        self,
        index: int,
        predecessor: Optional[N] = None,
        successor: Optional[N] = None,
    ) -> None:
        self._index = index
        self._predecessor = predecessor
        self._successor = successor

    @property
    def index(self) -> int:
        """Provides the edge's index."""
        return self._index

    @property
    def predecessor(self) -> N:
        """Provides the optional predecessor node."""
        assert self._predecessor, "Invalid edge without predecessor"
        return self._predecessor

    @property
    def successor(self) -> N:
        """Provides the optional successor node."""
        assert self._successor, "Invalid edge without successor"
        return self._successor


class ProgramGraph(Generic[E, N]):
    """A base class of a program graph, e.g., a CFG or CDG."""

    def __init__(self) -> None:
        self._nodes: List[N] = []
        self._edges: List[E] = []

    @property
    def edges(self) -> List[E]:
        """Provides a list of all edges of this program graph."""
        return self._edges

    @property
    def nodes(self) -> List[N]:
        """Provides a list of all nodes of this program graph."""
        return self._nodes
