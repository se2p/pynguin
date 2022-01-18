#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an implementation of a control-dependence graph."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ordered_set import OrderedSet

import pynguin.analyses.controlflow.dominatortree as pdt
import pynguin.analyses.controlflow.programgraph as pg

if TYPE_CHECKING:
    from pynguin.analyses.controlflow import cfg


# pylint:disable=too-few-public-methods.
class ControlDependenceGraph(pg.ProgramGraph[pg.ProgramGraphNode]):
    """Implements a control-dependence graph."""

    @staticmethod
    def compute(graph: cfg.CFG) -> ControlDependenceGraph:
        """Computes the control-dependence graph for a given control-flow graph.

        Args:
            graph: The control-flow graph

        Returns:
            The control-dependence graph
        """
        augmented_cfg = ControlDependenceGraph._create_augmented_graph(graph)
        post_dominator_tree = pdt.DominatorTree.compute_post_dominator_tree(
            augmented_cfg
        )
        cdg = ControlDependenceGraph()
        nodes = augmented_cfg.nodes

        for node in nodes:
            cdg.add_node(node)

        # Find matching edges in the CFG.
        edges: set[ControlDependenceGraph._Edge] = set()
        for source in nodes:
            for target in augmented_cfg.get_successors(source):
                if source not in post_dominator_tree.get_transitive_successors(target):
                    # Store branching data from edge, i.e., which outcome of the
                    # branching node leads to this node.
                    data = frozenset(
                        augmented_cfg.graph.get_edge_data(source, target).items()
                    )
                    edges.add(
                        ControlDependenceGraph._Edge(
                            source=source, target=target, data=data
                        )
                    )

        # Mark nodes in the PDT and construct edges for them.
        for edge in edges:
            least_common_ancestor = post_dominator_tree.get_least_common_ancestor(
                edge.source, edge.target
            )
            current = edge.target
            while current != least_common_ancestor:
                # TODO(fk) can the branching info be actually used here?
                # Seems ok?
                cdg.add_edge(edge.source, current, **dict(edge.data))
                predecessors = post_dominator_tree.get_predecessors(current)
                assert len(predecessors) == 1, (
                    "Cannot have more than one predecessor in a tree, this violates a "
                    + "tree invariant"
                )
                current = predecessors.pop()

            if least_common_ancestor is edge.source:
                cdg.add_edge(edge.source, least_common_ancestor, **dict(edge.data))

        return pg.filter_dead_code_nodes(cdg, entry_node_index=-sys.maxsize)

    def get_control_dependencies(
        self, node: pg.ProgramGraphNode
    ) -> OrderedSet[ControlDependency]:
        """Get the immediate control dependencies of this node.

        Args:
            node: the node whose dependencies should be retrieved.

        Returns:
            The direct control dependencies of the given node, if any.
        """
        assert node is not None
        assert node in self.graph.nodes
        return self._retrieve_control_dependencies(node, OrderedSet())

    def _retrieve_control_dependencies(
        self, node: pg.ProgramGraphNode, handled: OrderedSet
    ) -> OrderedSet[ControlDependency]:
        result = OrderedSet()
        for pred in self._graph.predecessors(node):
            if (pred, node) in handled:
                continue
            handled.add((pred, node))

            if (
                branch_value := self._graph.get_edge_data(pred, node).get(
                    pg.EDGE_DATA_BRANCH_VALUE, None
                )
            ) is not None:
                assert pred.predicate_id is not None
                result.add(ControlDependency(pred.predicate_id, branch_value))
            else:
                result.update(self._retrieve_control_dependencies(pred, handled))
        return result

    def is_control_dependent_on_root(self, node: pg.ProgramGraphNode) -> bool:
        """Does this node directly depend on entering the code object?"""
        return self._is_control_dependent_on_root(node, set())

    def _is_control_dependent_on_root(
        self, node: pg.ProgramGraphNode, visited: set[pg.ProgramGraphNode]
    ) -> bool:
        if (self.entry_node, node) in self.graph.edges:
            return True
        for pred in self.graph.predecessors(node):
            if pred in visited:
                continue
            visited.add(pred)
            if pred.predicate_id is not None:
                continue
            if pred == node:
                continue
            if self._is_control_dependent_on_root(pred, visited):
                return True
        return False

    @staticmethod
    def _create_augmented_graph(graph: cfg.CFG) -> cfg.CFG:
        entry_node = graph.entry_node
        assert entry_node, "Cannot work with CFG without entry node"
        exit_nodes = graph.exit_nodes
        augmented_graph = graph.copy()
        start_node = pg.ProgramGraphNode(index=-sys.maxsize, is_artificial=True)
        augmented_graph.add_node(start_node)
        augmented_graph.add_edge(start_node, entry_node)
        for exit_node in exit_nodes:
            augmented_graph.add_edge(start_node, exit_node)
        return augmented_graph

    @dataclass(frozen=True)
    class _Edge:
        source: pg.ProgramGraphNode
        target: pg.ProgramGraphNode
        data: frozenset


@dataclass(frozen=True)
class ControlDependency:
    """Models a control dependency."""

    predicate_id: int
    branch_value: bool
