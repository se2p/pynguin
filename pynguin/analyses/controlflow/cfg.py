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
"""Provides a control-flow graph implementation."""
from __future__ import annotations

import sys
from typing import Dict, List, Tuple, cast

from bytecode import Bytecode, ControlFlowGraph

import pynguin.analyses.controlflow.programgraph as pg


class CFG(pg.ProgramGraph[pg.ProgramGraphNode]):
    """The control-flow graph implementation based on the program graph."""

    # Attribute where the predicate id of the instrumentation is stored
    PREDICATE_ID: str = "predicate_id"

    def __init__(self, bytecode_cfg: ControlFlowGraph):
        """Create new CFG. Do not call directly, use static factory methods.

        Args:
            bytecode_cfg: the control flow graph of the underlying bytecode.
        """
        super().__init__()
        self._bytecode_cfg = bytecode_cfg

    @staticmethod
    def from_bytecode(bytecode: Bytecode) -> CFG:
        """Generates a new control-flow graph from a bytecode segment.

        Besides generating a node for each block in the bytecode segment, as returned by
        `bytecode`'s `ControlFlowGraph` implementation, we add two artificial nodes to
        the generated CFG:
         - an artificial entry node, having index -1, that is guaranteed to fulfill the
           property of an entry node, i.e., there is no incoming edge, and
         - an artificial exit node, having index `sys.maxsize`, that is guaranteed to
           fulfill the property of an exit node, i.e., there is no outgoing edge, and
           that is the only such node in the graph, which is important, e.g., for graph
           reversal.
        The index values are chosen that they do not appear in regular graphs, thus one
        can easily distinguish them from the normal nodes in the graph by checking for
        their index-property's value.

        Args:
            bytecode: The bytecode segment

        Returns:
            The control-flow graph for the segment
        """
        blocks = ControlFlowGraph.from_bytecode(bytecode)
        cfg = CFG(blocks)

        # Create the nodes and a mapping of all edges to generate
        edges, nodes = CFG._create_nodes(blocks)

        # Insert all edges between the previously generated nodes
        CFG._create_graph(cfg, edges, nodes)

        # Filter all dead-code nodes
        cfg = CFG._filter_dead_code_nodes(cfg)

        # Insert dummy exit and entry nodes
        cfg = CFG._insert_dummy_exit_node(cfg)
        cfg = CFG._insert_dummy_entry_node(cfg)
        return cfg

    def bytecode_cfg(self) -> ControlFlowGraph:
        """Provide the raw control flow graph from the code object.
        Can be used to instrument the control flow.

        Returns:
            The raw control-flow graph from the code object
        """
        return self._bytecode_cfg

    @staticmethod
    def reverse(cfg: CFG) -> CFG:
        """Reverses a control-flow graph, i.e., entry nodes become exit nodes and
        vice versa.

        Args:
            cfg: The control-flow graph to reverse

        Returns:
            The reversed control-flow graph
        """
        reversed_cfg = CFG(cfg.bytecode_cfg())
        # pylint: disable=attribute-defined-outside-init
        reversed_cfg._graph = cfg._graph.reverse(copy=True)
        return reversed_cfg

    def reversed(self) -> CFG:
        """Provides the reversed graph of this graph.

        Returns:
            The reversed graph
        """
        return CFG.reverse(self)

    @staticmethod
    def copy_graph(cfg: CFG) -> CFG:
        """Provides a copy of the control-flow graph.

        Args:
            cfg: The original graph

        Returns:
            The copied graph
        """
        copy = CFG(
            ControlFlowGraph()
        )  # TODO(fk) Cloning the bytecode cfg is complicated.
        # pylint: disable=attribute-defined-outside-init
        copy._graph = cfg._graph.copy()
        return copy

    def copy(self) -> CFG:
        """Provides a copy of the control-flow graph.

        Returns:
            The copied graph
        """
        return CFG.copy_graph(self)

    @staticmethod
    def _create_nodes(
        blocks: ControlFlowGraph,
    ) -> Tuple[Dict[int, List[int]], Dict[int, pg.ProgramGraphNode]]:
        nodes: Dict[int, pg.ProgramGraphNode] = {}
        edges: Dict[int, List[int]] = {}
        for node_index, block in enumerate(blocks):
            node = pg.ProgramGraphNode(index=node_index, basic_block=block)
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
    def _create_graph(
        cfg: CFG, edges: Dict[int, List[int]], nodes: Dict[int, pg.ProgramGraphNode]
    ):
        # add nodes to graph
        for node in nodes.values():
            cfg.add_node(node)

        # add edges to graph
        for predecessor in edges.keys():
            successors = edges.get(predecessor)
            for successor in cast(List[int], successors):
                predecessor_node = nodes.get(predecessor)
                successor_node = nodes.get(successor)
                assert predecessor_node
                assert successor_node
                cfg.add_edge(predecessor_node, successor_node)

    @staticmethod
    def _insert_dummy_entry_node(cfg: CFG) -> CFG:
        dummy_entry_node = pg.ProgramGraphNode(index=-1, is_artificial=True)
        entry_node = cfg.entry_node
        if not entry_node and len(cfg.nodes) == 1:
            entry_node = cfg.nodes.pop()  # There is only one candidate to pop
        elif not entry_node:
            entry_node = [n for n in cfg.nodes if n.index == 0][0]
        cfg.add_node(dummy_entry_node)
        cfg.add_edge(dummy_entry_node, entry_node)
        return cfg

    @staticmethod
    def _insert_dummy_exit_node(cfg: CFG) -> CFG:
        dummy_exit_node = pg.ProgramGraphNode(index=sys.maxsize, is_artificial=True)
        exit_nodes = cfg.exit_nodes
        if not exit_nodes and len(cfg.nodes) == 1:
            exit_nodes = cfg.nodes
        cfg.add_node(dummy_exit_node)
        for exit_node in exit_nodes:
            cfg.add_edge(exit_node, dummy_exit_node)
        return cfg

    @staticmethod
    def _filter_dead_code_nodes(graph: CFG) -> CFG:
        for node in graph.nodes:
            if graph.get_predecessors(node) == set() and node.index != 0:
                # The only node in the graph that is allowed to have no predecessor
                # is the entry node, i.e., the node with index 0.  All other nodes
                # without predecessors are considered dead code and thus removed.
                graph._graph.remove_node(node)
        return graph

    @property
    def cyclomatic_complexity(self) -> int:
        """Calculates McCabe's cyclomatic complexity for this control-flow graph

        Returns:
            McCabe's cyclocmatic complexity number
        """
        return len(self._graph.edges) - len(self._graph.nodes) + 2
