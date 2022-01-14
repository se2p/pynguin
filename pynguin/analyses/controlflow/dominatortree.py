#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an implementation of a dominator tree."""
from __future__ import annotations

import queue
from typing import TYPE_CHECKING

import pynguin.analyses.controlflow.programgraph as pg

if TYPE_CHECKING:
    from pynguin.analyses.controlflow import cfg


class DominatorTree(pg.ProgramGraph[pg.ProgramGraphNode]):
    """Implements a dominator tree."""

    @staticmethod
    def compute(graph: cfg.CFG) -> DominatorTree:
        """Computes the dominator tree for a control-flow graph.

        Args:
            graph: The control-flow graph

        Returns:
            The dominator tree for the control-flow graph
        """
        return DominatorTree.compute_dominance_tree(graph)

    @staticmethod
    def compute_post_dominator_tree(graph: cfg.CFG) -> DominatorTree:
        """Computes the post-dominator tree for a control-flow graph.

        Args:
            graph: The control-flow graph

        Returns:
            The post-dominator tree for the control-flow graph
        """
        reversed_cfg = graph.reversed()
        return DominatorTree.compute(reversed_cfg)

    @staticmethod
    def compute_dominance_tree(graph: cfg.CFG) -> DominatorTree:
        """Computes the dominance tree for a control-flow graph.

        Args:
            graph: The control-flow graph

        Returns:
            The dominance tree for the control-flow graph
        """
        dominance: dict[
            pg.ProgramGraphNode, set[pg.ProgramGraphNode]
        ] = DominatorTree._calculate_dominance(graph)
        for dominance_node, nodes in dominance.items():
            nodes.discard(dominance_node)
        dominance_tree = DominatorTree()
        entry_node = graph.entry_node
        assert entry_node is not None
        dominance_tree.add_node(entry_node)

        node_queue: queue.SimpleQueue = queue.SimpleQueue()
        node_queue.put(entry_node)
        while not node_queue.empty():
            node: pg.ProgramGraphNode = node_queue.get()
            for current, dominators in dominance.items():
                if node in dominators:
                    dominators.remove(node)
                    if len(dominators) == 0:
                        dominance_tree.add_node(current)
                        dominance_tree.add_edge(node, current)
                        node_queue.put(current)
        return dominance_tree

    @staticmethod
    def _calculate_dominance(
        graph: cfg.CFG,
    ) -> dict[pg.ProgramGraphNode, set[pg.ProgramGraphNode]]:
        dominance_map: dict[pg.ProgramGraphNode, set[pg.ProgramGraphNode]] = {}
        entry = graph.entry_node
        assert entry, "Cannot work with a graph without entry nodes"
        entry_dominators: set[pg.ProgramGraphNode] = {entry}
        dominance_map[entry] = entry_dominators

        for node in graph.nodes:
            if node == entry:
                continue
            all_nodes: set[pg.ProgramGraphNode] = set(graph.nodes)
            dominance_map[node] = all_nodes

        changed: bool = True
        while changed:
            changed = False
            for node in graph.nodes:
                if node == entry:
                    continue
                current_dominators = dominance_map.get(node)
                new_dominators = DominatorTree._calculate_dominators(
                    graph, dominance_map, node
                )

                if current_dominators != new_dominators:
                    changed = True
                    dominance_map[node] = new_dominators
                    break

        return dominance_map

    @staticmethod
    def _calculate_dominators(
        graph: cfg.CFG,
        dominance_map: dict[pg.ProgramGraphNode, set[pg.ProgramGraphNode]],
        node: pg.ProgramGraphNode,
    ) -> set[pg.ProgramGraphNode]:
        dominators: set[pg.ProgramGraphNode] = {node}
        intersection: set[pg.ProgramGraphNode] = set()
        predecessors = graph.get_predecessors(node)
        if not predecessors:
            return set()

        first_time: bool = True
        for predecessor in predecessors:
            predecessor_dominators = dominance_map.get(predecessor)
            assert predecessor_dominators is not None, "Cannot be None"
            if first_time:
                intersection = intersection.union(predecessor_dominators)
                first_time = False
            else:
                intersection.intersection_update(predecessor_dominators)
        intersection = intersection.union(dominators)
        return intersection
