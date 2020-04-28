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
"""Provides a control-flow graph implementation consisting of nodes and edges."""
from __future__ import annotations

import sys
from typing import Any, List, Optional, Dict, cast, Tuple

from bytecode import Instr, BasicBlock, Bytecode, ControlFlowGraph


class CFGNode:
    """A node in the control-flow graph."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        index: int,
        incoming_edges: Optional[List[CFGEdge]] = None,
        outgoing_edges: Optional[List[CFGEdge]] = None,
        instructions: Optional[List[Instr]] = None,
        basic_block: Optional[BasicBlock] = None,
    ) -> None:
        self._index = index
        self._incoming_edges = incoming_edges if incoming_edges else []
        self._outgoing_edges = outgoing_edges if outgoing_edges else []
        self._instructions = instructions if instructions else []
        self._basic_block = basic_block

    @property
    def index(self) -> int:
        """Provides the index of the node."""
        return self._index

    @property
    def incoming_edges(self) -> List[CFGEdge]:
        """Return the list of incoming edges."""
        return self._incoming_edges

    @property
    def outgoing_edges(self) -> List[CFGEdge]:
        """Returns the list of outgoing edges."""
        return self._outgoing_edges

    @property
    def instructions(self) -> Optional[List[Instr]]:
        """Returns the list of instructions attached to this block."""
        return self._instructions

    @property
    def basic_block(self) -> Optional[BasicBlock]:
        """Returns the original basic-block object."""
        return self._basic_block

    def add_incoming_edge(self, edge: CFGEdge) -> None:
        """Adds an incoming edge to this node."""
        self._incoming_edges.append(edge)

    def add_outgoing_edge(self, edge: CFGEdge) -> None:
        """Adds an outgoing edge to this node."""
        self._outgoing_edges.append(edge)

    def is_entry_node(self) -> bool:
        """Checks whether or not the node is an entry node."""
        return not self._incoming_edges

    def is_exit_node(self) -> bool:
        """Checks whether or not the node is an exit node."""
        return not self._outgoing_edges

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CFGNode):
            return False
        if other is self:
            return True
        return (
            self._index == other.index
            and self._incoming_edges == other.incoming_edges
            and self._outgoing_edges == other.outgoing_edges
        )

    def __hash__(self) -> int:
        return (
            31
            + 17 * self._index
            + sum(
                [
                    17 * hash(elem)
                    for elem in self._incoming_edges + self._outgoing_edges
                ]
            )
        )

    def __str__(self) -> str:
        return f"CFGNode({self._index})"

    def __repr__(self) -> str:
        return (
            f"CFGNode(index={self._index}, incoming_edges={self._incoming_edges}, "
            f"outgoing_edges={self._outgoing_edges})"
        )


class CFGEdge:
    """An edge in the control-flow graph"""

    def __init__(
        self,
        index: int,
        predecessor: Optional[CFGNode] = None,
        successor: Optional[CFGNode] = None,
    ) -> None:
        self._index = index
        self._predecessor = predecessor
        self._successor = successor

    @property
    def index(self) -> int:
        """Provides the edge's index."""
        return self._index

    @property
    def predecessor(self) -> CFGNode:
        """Provides the optional predecessor node."""
        assert self._predecessor, "Invalid edge without predecessor"
        return self._predecessor

    @property
    def successor(self) -> CFGNode:
        """Provides the optional successor node."""
        assert self._successor, "Invalid edge without successor"
        return self._successor

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CFGEdge):
            return False
        if other is self:
            return True
        return (
            self._index == other.index
            and self._predecessor == other.predecessor
            and self._successor == other.successor
        )

    def __hash__(self) -> int:
        return (
            31
            + 17 * self._index
            + 17 * id(self._predecessor)
            + 17 * id(self._successor)
        )

    def __str__(self) -> str:
        return f"CFGEdge({self._index}; {self._predecessor} -> {self._successor})"

    def __repr__(self) -> str:
        return (
            f"CFGEdge(index={self._index}, predecessor={self._predecessor}, "
            f"successor={self._successor}"
        )


class CFG:
    """The control-flow graph implementation"""

    def __init__(self) -> None:
        self._nodes: List[CFGNode] = []
        self._edges: List[CFGEdge] = []

    @staticmethod
    def from_bytecode(bytecode: Bytecode) -> CFG:
        """Generates a new control-flow graph from a bytecode segment.

        :param bytecode: The bytecode segment
        :return: The control-flow graph for the segment
        """
        blocks = ControlFlowGraph.from_bytecode(bytecode)
        cfg = CFG()

        # Create the nodes and a mapping of all edges to generate
        edges, nodes = CFG._create_nodes(blocks)

        # Create all edges between the previously generated nodes
        new_edges = CFG._create_and_insert_edges(edges, nodes)

        cfg._nodes = [
            node for node in nodes.values()  # pylint: disable=unnecessary-comprehension
        ]
        cfg._edges = new_edges
        cfg = CFG._insert_dummy_exit_node(cfg)
        return cfg

    @staticmethod
    def reverse(cfg: CFG) -> CFG:
        """Reverses a control-flow graph, i.e., entry nodes be come exit nodes and
        vice versa.

        :param cfg: The control-flow graph to reverse
        :return: The reversed control-flow graph
        """

        def get_node_by_index(nodes: List[CFGNode], index: int) -> CFGNode:
            node = [n for n in nodes if n.index == index]
            assert len(node) == 1
            return node[0]

        reversed_cfg = CFG()
        reversed_cfg._nodes = [
            CFGNode(
                index=node.index,
                instructions=node.instructions,
                basic_block=node.basic_block,
            )
            for node in cfg.nodes
        ]
        edge_index = 0
        edges: List[CFGEdge] = []
        for edge in cfg.edges:
            old_predecessor_index = edge.predecessor.index
            old_successor_index = edge.successor.index
            new_predecessor = get_node_by_index(reversed_cfg.nodes, old_successor_index)
            new_successor = get_node_by_index(reversed_cfg.nodes, old_predecessor_index)
            new_edge = CFGEdge(
                index=edge_index, predecessor=new_predecessor, successor=new_successor
            )
            new_predecessor.add_outgoing_edge(new_edge)
            new_successor.add_incoming_edge(new_edge)
            edges.append(new_edge)
            edge_index += 1
        reversed_cfg._edges = edges
        return reversed_cfg

    @staticmethod
    def _create_nodes(
        blocks: ControlFlowGraph,
    ) -> Tuple[Dict[int, List[int]], Dict[int, CFGNode]]:
        nodes: Dict[int, CFGNode] = {}
        edges: Dict[int, List[int]] = {}
        for node_index, block in enumerate(blocks):
            node = CFGNode(
                node_index,
                instructions=[
                    instruction
                    for instruction in block  # pylint: disable=unnecessary-comprehension
                ],
                basic_block=block,
            )
            nodes[node_index] = node
            if node_index not in edges:
                edges[node_index] = []

            next_block = block.next_block
            if next_block:
                next_index = blocks.get_block_index(next_block)
                edges[node_index].append(next_index)
            if target_block := block.get_jump():
                next_index = blocks.get_block_index(target_block)
                edges[node_index].append(next_index)
        return edges, nodes

    @staticmethod
    def _insert_dummy_exit_node(cfg: CFG) -> CFG:
        dummy_exit_node = CFGNode(index=sys.maxsize)
        exit_nodes = [node for node in cfg.nodes if node.is_exit_node()]
        new_edges: List[CFGEdge] = []
        index = max([edge.index for edge in cfg.edges]) + 1
        for exit_node in exit_nodes:
            new_edge = CFGEdge(index, predecessor=exit_node, successor=dummy_exit_node)
            exit_node.add_outgoing_edge(new_edge)
            dummy_exit_node.add_incoming_edge(new_edge)
            new_edges.append(new_edge)
        cfg._nodes.append(dummy_exit_node)
        cfg._edges.extend(new_edges)
        return cfg

    @staticmethod
    def _create_and_insert_edges(
        edges: Dict[int, List[int]], nodes: Dict[int, CFGNode]
    ) -> List[CFGEdge]:
        index = 0
        new_edges: List[CFGEdge] = []
        for predecessor in edges.keys():
            successors = edges.get(predecessor)
            for successor in cast(List[int], successors):
                predecessor_node = nodes.get(predecessor)
                successor_node = nodes.get(successor)
                assert predecessor_node
                assert successor_node
                edge = CFGEdge(index, predecessor_node, successor_node)
                predecessor_node.add_outgoing_edge(edge)
                successor_node.add_incoming_edge(edge)
                new_edges.append(edge)
                index += 1
        return new_edges

    @property
    def entry_node(self) -> CFGNode:
        """Provides the entry node of the control-flow graph."""
        entry_nodes = [node for node in self._nodes if node.is_entry_node()]
        assert len(entry_nodes) == 1, "Cannot work with more than one entry node!"
        return entry_nodes[0]

    @property
    def exit_node(self) -> CFGNode:
        """Provides a list of all exit nodes of the control-flow graph."""
        exit_nodes = [node for node in self._nodes if node.is_exit_node()]
        assert len(exit_nodes) == 1, "Cannot work with more than one exit node!"
        return exit_nodes[0]

    @property
    def edges(self) -> List[CFGEdge]:
        """Provides a list of all edges of this control-flow graph."""
        return self._edges

    @property
    def nodes(self) -> List[CFGNode]:
        """Provides a list of all nodes of this control-flow graph."""
        return self._nodes

    @property
    def cyclomatic_complexity(self) -> int:
        """Calculates McCabe's cyclomatic complexity for this control-flow graph.

        :return: McCabe's cyclomatic complexity number
        """
        return len(self._edges) - len(self._nodes) + 2
