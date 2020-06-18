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
"""Provides an implementation of a control-dependence graph."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Set

import pynguin.analyses.controlflow.cfg as cfg
import pynguin.analyses.controlflow.dominatortree as pdt
import pynguin.analyses.controlflow.programgraph as pg


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
        edges: Set[ControlDependenceGraph._Edge] = set()
        for source in nodes:
            for target in augmented_cfg.get_successors(source):
                if source not in post_dominator_tree.get_transitive_successors(target):
                    edges.add(
                        ControlDependenceGraph._Edge(source=source, target=target)
                    )

        # Mark nodes in the PDT and construct edges for them.
        for edge in edges:
            least_common_ancestor = post_dominator_tree.get_least_common_ancestor(
                edge.source, edge.target
            )
            current = edge.target
            while current != least_common_ancestor:
                cdg.add_edge(edge.source, current)
                predecessors = post_dominator_tree.get_predecessors(current)
                assert len(predecessors) == 1, (
                    "Cannot have more than one predecessor in a tree, this violates a "
                    "tree invariant"
                )
                current = predecessors.pop()

            if least_common_ancestor is edge.source:
                cdg.add_edge(edge.source, least_common_ancestor)

        return cdg

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

    @dataclass(eq=True, frozen=True)
    class _Edge:
        source: pg.ProgramGraphNode
        target: pg.ProgramGraphNode
