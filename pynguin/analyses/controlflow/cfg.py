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
from typing import Tuple, Dict, List, cast

from bytecode import Bytecode, ControlFlowGraph

import pynguin.analyses.controlflow.programgraph as pg


class CFG(pg.ProgramGraph[pg.ProgramGraphNode]):
    """The control-flow graph implementation based on the program graph."""

    # Attribute where the predicate id of the instrumentation is stored
    PREDICATE_ID: str = "predicate_id"

    def __init__(self, bytecode_cfg: ControlFlowGraph):
        """Create new CFG. Do not call directly, use static factory methods.
        :param bytecode_cfg the control flow graph of the underlying bytecode."""
        super().__init__()
        self._bytecode_cfg = bytecode_cfg

    @staticmethod
    def from_bytecode(bytecode: Bytecode) -> CFG:
        """Generates a new control-flow graph from a bytecode segment.

        :param bytecode: The bytecode segment
        :return: The control-flow graph for the segment
        """
        blocks = ControlFlowGraph.from_bytecode(bytecode)
        cfg = CFG(blocks)

        # Create the nodes and a mapping of all edges to generate
        edges, nodes = CFG._create_nodes(blocks)

        # Insert all edges between the previously generated nodes
        CFG._create_graph(cfg, edges, nodes)

        # Insert dummy exit node
        cfg = CFG._insert_dummy_exit_node(cfg)
        return cfg

    def bytecode_cfg(self) -> ControlFlowGraph:
        """Provide the raw control flow graph from the code object.
        Can be used to instrument the control flow."""
        return self._bytecode_cfg

    @staticmethod
    def reverse(cfg: CFG) -> CFG:
        """Reverses a control-flow graph, i.e., entry nodes become exit nodes and
        vice versa.

        :param cfg: The control-flow graph to reverse
        :return: The reversed control-flow graph
        """
        reversed_cfg = CFG(cfg.bytecode_cfg())
        # pylint: disable=attribute-defined-outside-init
        reversed_cfg._graph = cfg._graph.reverse(copy=True)
        return reversed_cfg

    def reversed(self) -> CFG:
        """Provides the reversed graph of this graph.

        :return: The reversed graph
        """
        return CFG.reverse(self)

    @staticmethod
    def copy_graph(cfg: CFG) -> CFG:
        """Provides a copy of the control-flow graph.

        :param cfg: The original graph
        :return: The copied graph
        """
        copy = CFG(
            ControlFlowGraph()
        )  # TODO(fk) Cloning the bytecode cfg is complicated.
        # pylint: disable=attribute-defined-outside-init
        copy._graph = cfg._graph.copy()
        return copy

    def copy(self) -> CFG:
        """Provides a copy of the control-flow graph.

        :return: The copied graph
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
    def _insert_dummy_exit_node(cfg: CFG) -> CFG:
        dummy_exit_node = pg.ProgramGraphNode(index=sys.maxsize)
        exit_nodes = cfg.exit_nodes
        cfg.add_node(dummy_exit_node)
        for exit_node in exit_nodes:
            cfg.add_edge(exit_node, dummy_exit_node)
        return cfg

    @property
    def cyclomatic_complexity(self) -> int:
        """Calculates McCabe's cyclomatic complexity for this control-flow graph

        :return: McCabe's cyclocmatic complexity number
        """
        return len(self._graph.edges) - len(self._graph.nodes) + 2
