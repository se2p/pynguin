#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a control-flow graph implementation."""
from __future__ import annotations

import sys

from bytecode import Bytecode, ControlFlowGraph, Instr
from networkx import NetworkXError, diameter

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
        self._diameter: int | None = None

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
        edges, nodes = CFG._create_nodes_and_edges(blocks)

        # Insert all edges between the previously generated nodes
        CFG._create_graph(cfg, edges, nodes)

        # Filter all dead-code nodes
        cfg = pg.filter_dead_code_nodes(cfg)

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
    def _create_nodes_and_edges(
        blocks: ControlFlowGraph,
    ) -> tuple[dict[int, list[tuple[int, dict]]], dict[int, pg.ProgramGraphNode]]:
        nodes: dict[int, pg.ProgramGraphNode] = {}
        edges: dict[int, list[tuple[int, dict]]] = {}
        for node_index, block in enumerate(blocks):
            node = pg.ProgramGraphNode(index=node_index, basic_block=block)
            nodes[node_index] = node
            if node_index not in edges:
                edges[node_index] = []

            next_block = block.next_block
            target_block = block.get_jump()

            last_instr = block[-1]
            if isinstance(last_instr, Instr) and (
                last_instr.is_cond_jump() or last_instr.name == "FOR_ITER"
            ):
                if last_instr.name in ("POP_JUMP_IF_TRUE", "JUMP_IF_TRUE_OR_POP"):
                    # These jump to arg if ToS is True
                    true_branch = target_block
                    false_branch = next_block
                elif last_instr.name in (
                    "POP_JUMP_IF_FALSE",
                    "JUMP_IF_FALSE_OR_POP",
                    "JUMP_IF_NOT_EXC_MATCH",
                    "FOR_ITER",
                ):
                    # These jump to arg if ToS is False, is Empty or if Exc does
                    # not match.
                    true_branch = next_block
                    false_branch = target_block
                else:
                    raise RuntimeError(
                        "Unknown conditional Jump instruction in bytecode "
                        + last_instr.name
                    )
                for next_branch, value in [(true_branch, True), (false_branch, False)]:
                    next_index = blocks.get_block_index(next_branch)
                    # 'label' is also set to value, to get a nicer DOT representation,
                    # because 'label' is a keyword for labelling edges.
                    edges[node_index].append(
                        (next_index, {pg.EDGE_DATA_BRANCH_VALUE: value, "label": value})
                    )
            else:
                if next_block:
                    next_index = blocks.get_block_index(next_block)
                    edges[node_index].append((next_index, {}))
                if target_block := block.get_jump():
                    next_index = blocks.get_block_index(target_block)
                    edges[node_index].append((next_index, {}))
        return edges, nodes

    @staticmethod
    def _create_graph(
        cfg: CFG,
        edges: dict[int, list[tuple[int, dict]]],
        nodes: dict[int, pg.ProgramGraphNode],
    ):
        # add nodes to graph
        for node in nodes.values():
            cfg.add_node(node)

        # add edges to graph
        for predecessor, successors in edges.items():
            for successor, attrs in successors:
                predecessor_node = nodes.get(predecessor)
                successor_node = nodes.get(successor)
                assert predecessor_node
                assert successor_node
                cfg.add_edge(predecessor_node, successor_node, **attrs)

    @staticmethod
    def _insert_dummy_entry_node(cfg: CFG) -> CFG:
        dummy_entry_node = pg.ProgramGraphNode(index=-1, is_artificial=True)
        # Search node with index 0. This block contains the instruction where
        # the execution of a code object begins.
        node_zero = [n for n in cfg.nodes if n.index == 0]
        assert (
            len(node_zero) == 1
        ), "Execution has to start at exactly one node that has index 0."
        entry_node = node_zero[0]
        cfg.add_node(dummy_entry_node)
        cfg.add_edge(dummy_entry_node, entry_node)
        return cfg

    @staticmethod
    def _insert_dummy_exit_node(cfg: CFG) -> CFG:
        dummy_exit_node = pg.ProgramGraphNode(index=sys.maxsize, is_artificial=True)
        exit_nodes = cfg.exit_nodes
        assert exit_nodes, (
            "Control flow must have at least one exit node. Offending CFG: " + cfg.dot
        )
        cfg.add_node(dummy_exit_node)
        for exit_node in exit_nodes:
            cfg.add_edge(exit_node, dummy_exit_node)
        return cfg

    @property
    def cyclomatic_complexity(self) -> int:
        """Calculates McCabe's cyclomatic complexity for this control-flow graph

        Returns:
            McCabe's cyclocmatic complexity number
        """
        return len(self._graph.edges) - len(self._graph.nodes) + 2

    @property
    def diameter(self) -> int:
        """Computes the diameter of the graph

        Returns:
            The diameter of the graph
        """
        if self._diameter is None:
            # Do this computation lazily
            try:
                self._diameter = diameter(self._graph, usebounds=True)
            except NetworkXError:
                # It seems like NetworkX makes some assumptions on the graph which
                # are not documented (or which I could not find at least) that caused
                # these errors.
                # If the diameter computation fails for some reason, use an upper bound
                self._diameter = len(self._graph.edges)
        return self._diameter
