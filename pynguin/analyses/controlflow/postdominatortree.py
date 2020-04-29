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
"""Provides an implementation of a post-dominator tree."""
from __future__ import annotations

import queue
from typing import List, Dict, Set, Optional, Any, KeysView

import pynguin.analyses.controlflow.cfg as cfg
import pynguin.analyses.controlflow.programgraph as pg


class PostDominatorTreeNode(pg.ProgramGraphNode):
    """A node in the post-dominator tree."""

    def __init__(
        self,
        index: int,
        cfg_node: cfg.CFGNode,
        incoming_edges: Optional[List[PostDominatorTreeEdge]] = None,
        outgoing_edges: Optional[List[PostDominatorTreeEdge]] = None,
    ) -> None:
        super().__init__(index, incoming_edges, outgoing_edges)
        self._cfg_node = cfg_node

    @property
    def cfg_node(self) -> cfg.CFGNode:
        """Provides wrapped the CFG node."""
        return self._cfg_node

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PostDominatorTreeNode):
            return False
        if self is other:
            return True
        return self._index == other.index

    def __hash__(self) -> int:
        return 31 + 17 * self._index

    def __str__(self) -> str:
        return f"PostDominatorTreeNode({self._index}, {self._cfg_node})"

    def __repr__(self) -> str:
        return (
            f"PostDominatorTreeNode(index={self._index}, cfg_node="
            f"{self._cfg_node}, incoming_edges={self._incoming_edges}, "
            f"outgoing_edges={self._outgoing_edges})"
        )


class PostDominatorTreeEdge(pg.ProgramGraphEdge):
    """An edge in the post-dominator tree.

    This class exists just to have the type available, it does not add any
    functionality to the `ProgramGraphEdge`.
    """


class PostDominatorTree(pg.ProgramGraph):
    """Implements a post-dominator tree."""

    def __init__(
        self, nodes: List[pg.ProgramGraphNode], edges: List[pg.ProgramGraphEdge],
    ) -> None:
        super().__init__()
        self._nodes = nodes
        self._edges = edges

    @staticmethod
    def compute(graph: cfg.CFG) -> PostDominatorTree:
        """Computes the post-dominator tree for a control-flow graph.

        :param graph: The control-flow graph
        :return: The post-dominator tree for the control-flow graph
        """
        reversed_graph = cfg.CFG.reverse(graph)
        dominance_tree = PostDominatorTree.compute_post_dominance_tree(reversed_graph)
        post_dominator_tree = PostDominatorTree(
            nodes=dominance_tree.nodes, edges=dominance_tree.edges,
        )
        return post_dominator_tree

    @staticmethod
    def compute_post_dominance_tree(graph: pg.ProgramGraph) -> pg.ProgramGraph:
        """Computes the post-dominance tree for a program graph.

        :param graph: The program graph
        :return: The post-dominance tree for the control-flow graph
        """

        def get_entry_node(
            cfg_entry_node: pg.ProgramGraphNode,
            dominance_list: KeysView[pg.ProgramGraphNode],
        ) -> pg.ProgramGraphNode:
            for dominance_node in dominance_list:
                if dominance_node.index == cfg_entry_node.index:
                    return dominance_node
            raise ValueError("Node not found")

        post_dominance: Dict[
            pg.ProgramGraphNode, Set[pg.ProgramGraphNode]
        ] = PostDominatorTree._calculate_post_dominance(graph)
        for post_dominance_node, nodes in post_dominance.items():
            nodes.remove(post_dominance_node)
        dominance_tree: pg.ProgramGraph = pg.ProgramGraph()
        entry_node = get_entry_node(graph.entry_node, post_dominance.keys())
        dominance_tree.add_node(entry_node)

        node_queue: queue.SimpleQueue = queue.SimpleQueue()
        index = 0
        node_queue.put(entry_node)
        while not node_queue.empty():
            node: PostDominatorTreeNode = node_queue.get()
            for current, dominators in post_dominance.items():
                if node in dominators:
                    dominators.remove(node)
                    if len(dominators) == 0:
                        new_edge = PostDominatorTreeEdge(index, node, current)
                        node.add_outgoing_edge(new_edge)
                        current.add_incoming_edge(new_edge)
                        dominance_tree.add_node(current)
                        dominance_tree.add_edge(new_edge)
                        node_queue.put(current)
                        index += 1

        return dominance_tree

    @staticmethod
    def _calculate_post_dominance(
        graph: pg.ProgramGraph,
    ) -> Dict[pg.ProgramGraphNode, Set[pg.ProgramGraphNode]]:
        dominance_map: Dict[pg.ProgramGraphNode, Set[pg.ProgramGraphNode]] = {}
        entry: pg.ProgramGraphNode = graph.entry_node
        entry_dominators: Set[pg.ProgramGraphNode] = {entry}
        dominance_map[entry] = entry_dominators
        for node in graph.nodes:
            if node == entry:
                continue
            all_nodes: Set[pg.ProgramGraphNode] = set(graph.nodes)
            dominance_map[node] = all_nodes

        changed: bool = True
        while changed:
            changed = False
            for node in graph.nodes:
                if node == entry:
                    continue
                current_dominators = dominance_map.get(node)
                new_dominators = PostDominatorTree._calculate_dominators(
                    dominance_map, node
                )

                if current_dominators != new_dominators:
                    changed = True
                    dominance_map[node] = new_dominators
                    break

        return PostDominatorTree._wrap_cfg_nodes(dominance_map)

    @staticmethod
    def _calculate_dominators(
        dominance_map: Dict[pg.ProgramGraphNode, Set[pg.ProgramGraphNode]],
        node: pg.ProgramGraphNode,
    ) -> Set[pg.ProgramGraphNode]:
        dominators: Set[pg.ProgramGraphNode] = {node}
        intersection: Set[pg.ProgramGraphNode] = set()
        predecessors = [edge.predecessor for edge in node.incoming_edges]
        if not predecessors:
            return set()

        first_time: bool = True
        for predecessor in predecessors:
            predecessor_dominators = dominance_map.get(predecessor)
            assert predecessor_dominators, "Cannot be None"
            if first_time:
                intersection = intersection.union(predecessor_dominators)
                first_time = False
            else:
                intersection.intersection_update(predecessor_dominators)
        intersection = intersection.union(dominators)
        return intersection

    @staticmethod
    def _wrap_cfg_nodes(
        dominance_map: Dict[pg.ProgramGraphNode, Set[pg.ProgramGraphNode]]
    ) -> Dict[pg.ProgramGraphNode, Set[pg.ProgramGraphNode]]:
        def get_node_for_cfg_node(
            cfg_node: pg.ProgramGraphNode,
        ) -> PostDominatorTreeNode:
            assert isinstance(cfg_node, cfg.CFGNode), "Only works for CFG nodes"
            return PostDominatorTreeNode(index=cfg_node.index, cfg_node=cfg_node)

        def extract_lookup_table(
            source_map: Dict[pg.ProgramGraphNode, Set[pg.ProgramGraphNode]]
        ) -> Dict[int, pg.ProgramGraphNode]:
            table: Dict[int, pg.ProgramGraphNode] = {}
            for key, values in source_map.items():
                if key.index not in table:
                    table[key.index] = get_node_for_cfg_node(key)
                for value in values:
                    if value.index not in table:
                        table[value.index] = get_node_for_cfg_node(value)
            return table

        lookup_table: Dict[int, pg.ProgramGraphNode] = extract_lookup_table(
            dominance_map
        )

        new_dominance_map: Dict[pg.ProgramGraphNode, Set[pg.ProgramGraphNode]] = {}
        for node, nodes in dominance_map.items():
            new_node = lookup_table[node.index]
            new_dominance_map[new_node] = set()
            for inner_node in nodes:
                new_inner_node = lookup_table[inner_node.index]
                new_dominance_map[new_node].add(new_inner_node)
        return new_dominance_map
