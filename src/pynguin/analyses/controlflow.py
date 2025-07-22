#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides analyses regarding the control-flow of the program."""

from __future__ import annotations

import queue

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeAlias
from typing import TypeVar

import networkx as nx

from bytecode import Bytecode
from bytecode import Compare
from bytecode import ControlFlowGraph
from bytecode import Instr
from bytecode.cfg import BasicBlock
from bytecode.instr import UNSET

import pynguin.utils.opcodes as op

from pynguin.utils.orderedset import OrderedSet


if TYPE_CHECKING:
    from collections.abc import Collection

# Key for storing branch value in networkx edge.
EDGE_DATA_BRANCH_VALUE = "branch_value"


class ArtificialNode(Enum):
    """Types of artificial nodes in the program graph."""

    START = "START"
    """An artificial start node."""
    ENTRY = "ENTRY"
    """An artificial entry node."""
    EXIT = "EXIT"
    """An artificial exit node."""

    def __str__(self) -> str:
        return f"ArtificialNode({self.value})"


class BasicBlockNode:
    """A node in the program graph that is associated with a basic block.

    This node is used to represent a basic block in the program graph.
    """

    def __init__(
        self,
        index: int,
        basic_block: BasicBlock,
        offset: int = 0,
    ) -> None:
        """Instantiates a node for a program graph.

        Args:
            index: The index of the node
            basic_block: The basic block in the code
            offset: The offset of the first instruction of the node
        """
        self._index = index
        self._basic_block = basic_block
        self._offset = offset

    @property
    def index(self) -> int:
        """Provides the index of the node.

        Returns:
            The index of the node
        """
        return self._index

    @property
    def offset(self) -> int:
        """Provides the offset of the node the first instruction of the node.

        Returns:
            The offset of the node
        """
        return self._offset

    @offset.setter
    def offset(self, offset: int) -> None:
        """Set a new offset.

        Args:
            offset: The offset
        """
        self._offset = offset

    @property
    def basic_block(self) -> BasicBlock:
        """Provides the basic block attached to this node.

        Returns:
            The basic block attached to this node
        """
        assert len(self._basic_block) > 0, "Basic block must not be empty."
        return self._basic_block

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BasicBlockNode):
            return False
        if self is other:
            return True
        return self._index == other.index

    def __hash__(self) -> int:
        return hash(self._index)

    def __getstate__(self) -> dict:
        return {
            "index": self._index,
            "basic_block": self._basic_block,
            "offset": self._offset,
        }

    def __setstate__(self, state: dict) -> None:
        self._index = state["index"]
        self._basic_block = state["basic_block"]
        self._offset = state["offset"]

    def __str__(self) -> str:
        instructions = []
        for instr in self._basic_block:
            arg = instr.arg  # type: ignore[union-attr]
            if isinstance(arg, BasicBlock):
                # We cannot determine which BasicBlockNode this is.
                arg = "BasicBlockNode"
            elif isinstance(arg, Compare):
                arg = arg.name
            elif arg is UNSET:
                arg = ""
            else:
                arg = repr(arg)
            formatted = instr.name  # type: ignore[union-attr]
            if arg:
                formatted += f" {arg}"
            instructions.append(formatted)

        return f"BasicBlockNode({self._index})\n" + "\n".join(instructions)

    def __repr__(self) -> str:
        return f"BasicBlockNode(index={self._index}, basic_block={self._basic_block}), offset={self._offset})"  # noqa: E501


ProgramNode: TypeAlias = ArtificialNode | BasicBlockNode


class ProgramGraph:
    """Provides a base implementation for a program graph.

    Internally, this program graph uses the `NetworkX` library to hold the graph and
    do all the operations on it.
    """

    def __init__(self) -> None:  # noqa: D107
        self._graph: nx.DiGraph[ProgramNode] = nx.DiGraph()

    def add_node(self, node: ProgramNode, **attr: Any) -> None:
        """Add a node to the graph.

        Args:
            node: The node
            attr: A dict of attributes that will be attached to the node
        """
        self._graph.add_node(node, **attr)

    def add_edge(self, start: ProgramNode, end: ProgramNode, **attr: Any) -> None:
        """Add an edge between two nodes to the graph.

        Args:
            start: The start node of the edge
            end: The end node of the edge
            attr: A dict of attributes that will be attached to the edge.
        """
        self._graph.add_edge(start, end, **attr)

    def get_basic_block_node(self, index: int) -> BasicBlockNode | None:
        """Provides the basic block node with the given index.

        Args:
            index: The index of the basic block node

        Returns:
            The basic block node with the given index or None if no such node exists
        """
        for node in self._graph.nodes:
            if isinstance(node, BasicBlockNode) and node.index == index:
                return node
        return None

    def get_predecessors(self, node: ProgramNode) -> set[ProgramNode]:
        """Provides a set of all direct predecessors of a node.

        Args:
            node: The node to start

        Returns:
            A set of direct predecessors of the node
        """
        return set(self._graph.predecessors(node))

    def get_successors(self, node: ProgramNode) -> set[ProgramNode]:
        """Provides a set of all direct successors of a node.

        Args:
            node: The node to start

        Returns:
            A set of direct successors of the node
        """
        return set(self._graph.successors(node))

    @property
    def nodes(self) -> set[ProgramNode]:
        """Provides all nodes in the graph.

        Returns:
            The set of all nodes in the graph
        """
        return set(self._graph.nodes)

    @property
    def graph(self) -> nx.DiGraph[ProgramNode]:
        """The internal graph.

        Returns:
            The internal graph
        """
        return self._graph

    @property
    def entry_node(self) -> ProgramNode | None:
        """Provides the entry node of the graph.

        Returns:
            The entry node of the graph
        """
        for node in self._graph.nodes:
            if len(self.get_predecessors(node)) == 0:
                return node
        return None

    @property
    def exit_nodes(self) -> set[ProgramNode]:
        """Provides the exit nodes of the graph.

        Returns:
            The set of exit nodes of the graph
        """
        exit_nodes: set[ProgramNode] = set()
        for node in self._graph.nodes:
            if len(self.get_successors(node)) == 0:
                exit_nodes.add(node)
        return exit_nodes

    @property
    def yield_nodes(self) -> set[ProgramNode]:
        """Provides the yield nodes of the graph.

        Iterates over all nodes and checks if any of the instructions in the basic block
        is a yield instruction. If so, the node is added to the set of yield nodes. Then
        we ignore the rest of the instructions in this basic block and continue with the
        next node.

        Returns:
            The set of yield nodes of the graph
        """
        yield_nodes: set[ProgramNode] = set()
        for node in self._graph.nodes:
            if isinstance(node, BasicBlockNode):
                for instr in node.basic_block:
                    if instr.opcode == op.YIELD_VALUE:  # type: ignore[union-attr]
                        yield_nodes.add(node)
                        # exist the inner loop (over instructions)
                        # the node is already added thus continue with the next node
                        break
        return yield_nodes

    def get_transitive_successors(self, node: ProgramNode) -> set[ProgramNode]:
        """Calculates the transitive closure (the transitive successors) of a node.

        Args:
            node: The node to start with

        Returns:
            The transitive closure of the node
        """
        return self._get_transitive_successors(node, set())

    def _get_transitive_successors(
        self,
        node: ProgramNode,
        done: set[ProgramNode],
    ) -> set[ProgramNode]:
        successors: set[ProgramNode] = set()
        for successor_node in self.get_successors(node):
            if successor_node not in done:
                successors.add(successor_node)
                done.add(successor_node)
                successors.update(self._get_transitive_successors(successor_node, done))
        return successors

    def get_least_common_ancestor(
        self,
        first: ProgramNode,
        second: ProgramNode,
    ) -> ProgramNode:
        """Calculates the least or lowest common ancestor node of two nodes.

        Both nodes have to be part of the graph!

        Args:
            first: The first node
            second: The second node

        Returns:
            The least common ancestor node of the two nodes
        """
        return nx.lowest_common_ancestor(self._graph, first, second)

    @property
    def dot(self) -> str:
        """Provides the DOT representation of this graph.

        Returns:
            The DOT representation of this graph
        """
        graph = ["strict digraph  {"]
        graph.extend(f'"{node}";' for node in self._graph.nodes)
        for source, target, edge_data in self._graph.edges(data=True):
            if edge_data == {}:
                graph.append(f'"{source}" -> "{target}";')
            else:
                str_edge_data = ", ".join([f"{k}={v}" for k, v in edge_data.items()])
                graph.append(f'"{source}" -> "{target}"  [{str_edge_data}];')
        graph.append("}")
        return "\n".join(graph)


G = TypeVar("G", bound=ProgramGraph)


def filter_dead_code_nodes(graph: G, entry_node: ProgramNode) -> G:
    """Prunes dead nodes from the given graph.

    A dead node is a node that has no entry node.  To specify a legal entry node,
    one can use the `entry_node` parameter.

    Args:
        graph: The graph to prune nodes from
        entry_node: The entry node of the graph

    Returns:
        The graph without the pruned dead nodes
    """
    has_changed = True
    while has_changed:
        # Do this until we have reached a fixed point, i.e., removed all dead
        # nodes from the graph.
        has_changed = False
        for node in graph.nodes:
            if node != entry_node and not graph.get_predecessors(node):
                # The only node in the graph that is allowed to have no predecessor
                # is the entry node, i.e., the node with index 0.  All other nodes
                # without predecessors are considered dead code and thus removed.
                graph.graph.remove_node(node)
                has_changed = True
    return graph


class CFG(ProgramGraph):
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
        entry_node = cfg.get_basic_block_node(0)
        assert entry_node is not None, "There has to be a node with index 0 in the CFG."
        cfg = filter_dead_code_nodes(cfg, entry_node)

        # Insert dummy exit and entry nodes
        cfg = CFG._insert_dummy_exit_node(cfg)
        cfg = CFG._insert_dummy_entry_node(cfg)
        return cfg  # noqa: RET504

    def bytecode_cfg(self) -> ControlFlowGraph:
        """Provide the raw control flow graph from the code object.

        Can be used to instrument the control flow.

        Returns:
            The raw control-flow graph from the code object
        """
        return self._bytecode_cfg

    @staticmethod
    def reverse(cfg: CFG) -> CFG:
        """Reverses a control-flow graph.

        Generates a copy of the original control-flow graph.

        Args:
            cfg: The control-flow graph to reverse

        Returns:
            The reversed control-flow graph
        """
        reversed_cfg = CFG(cfg.bytecode_cfg())

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
        copy = CFG(ControlFlowGraph())  # TODO(fk) Cloning the bytecode cfg is complicated.

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
    ) -> tuple[dict[int, list[tuple[int, dict]]], dict[int, ProgramNode]]:
        nodes: dict[int, ProgramNode] = {}
        edges: dict[int, list[tuple[int, dict]]] = {}
        offset = 0
        for node_index, block in enumerate(blocks):
            node = BasicBlockNode(index=node_index, basic_block=block, offset=offset)
            # each instruction increases the offset by 2, therefore the offset at the
            # beginning of the next block is the current offset plus twice the length
            # of the current block
            offset += len(block) * 2

            nodes[node_index] = node
            if node_index not in edges:
                edges[node_index] = []

            next_block = block.next_block
            target_block = block.get_jump()

            last_instr = block[-1]
            if isinstance(last_instr, Instr) and (
                last_instr.is_cond_jump() or last_instr.opcode == op.FOR_ITER
            ):
                if last_instr.opcode in {op.POP_JUMP_IF_TRUE, op.JUMP_IF_TRUE_OR_POP}:
                    # These jump to arg if ToS is True
                    true_branch = target_block
                    false_branch = next_block
                elif last_instr.opcode in {
                    op.POP_JUMP_IF_FALSE,
                    op.JUMP_IF_FALSE_OR_POP,
                    op.JUMP_IF_NOT_EXC_MATCH,
                    op.FOR_ITER,
                }:
                    # These jump to arg if ToS is False, is Empty or if Exc does
                    # not match.
                    true_branch = next_block
                    false_branch = target_block
                else:
                    raise RuntimeError(
                        "Unknown conditional Jump instruction in bytecode " + last_instr.name
                    )
                for next_branch, value in [(true_branch, True), (false_branch, False)]:
                    next_index = blocks.get_block_index(
                        next_branch  # type: ignore[arg-type]
                    )
                    # 'label' is also set to value, to get a nicer DOT representation,
                    # because 'label' is a keyword for labelling edges.
                    edges[node_index].append((
                        next_index,
                        {EDGE_DATA_BRANCH_VALUE: value, "label": value},
                    ))
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
        nodes: dict[int, ProgramNode],
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
    def _infinite_loop_nodes(cfg: CFG) -> set[ProgramNode]:
        nodes: set[ProgramNode] = set()
        exit_nodes = cfg.exit_nodes
        for node in cfg.nodes:
            successors = cfg.get_successors(node)
            if node in successors and successors.isdisjoint(exit_nodes):
                nodes.add(node)
        return nodes

    @staticmethod
    def _insert_dummy_entry_node(cfg: CFG) -> CFG:
        dummy_entry_node = ArtificialNode.ENTRY
        # Search node with index 0. This block contains the instruction where
        # the execution of a code object begins.
        entry_node = cfg.get_basic_block_node(0)
        assert entry_node is not None, "There has to be a node with index 0 in the CFG."
        cfg.add_node(dummy_entry_node)
        cfg.add_edge(dummy_entry_node, entry_node)
        return cfg

    @staticmethod
    def _insert_dummy_exit_node(cfg: CFG) -> CFG:
        dummy_exit_node = ArtificialNode.EXIT
        exit_nodes = cfg.exit_nodes
        yield_nodes = cfg.yield_nodes
        assert exit_nodes.union(yield_nodes), (
            "Control flow must have at least one exit or yield node. Offending CFG: " + cfg.dot
        )

        # Add the dummy exit node to the graph
        cfg.add_node(dummy_exit_node)

        # Connect the dummy exit node to all yield nodes
        for yield_node in yield_nodes:
            cfg.add_edge(yield_node, dummy_exit_node)

        # Connect the dummy exit node to all exit nodes
        for exit_node in exit_nodes:
            if exit_node is not dummy_exit_node:
                cfg.add_edge(exit_node, dummy_exit_node)

        for infinite_loop_node in CFG._infinite_loop_nodes(cfg):
            cfg.add_edge(infinite_loop_node, dummy_exit_node)
        return cfg

    @property
    def cyclomatic_complexity(self) -> int:
        """Calculates McCabe's cyclomatic complexity for this control-flow graph.

        Returns:
            McCabe's cyclocmatic complexity number
        """
        return len(self._graph.edges) - len(self._graph.nodes) + 2

    @property
    def diameter(self) -> int:
        """Computes the diameter of the graph.

        Returns:
            The diameter of the graph
        """
        if self._diameter is None:
            # Do this computation lazily
            try:
                self._diameter = nx.diameter(self._graph, usebounds=True)
            except nx.NetworkXError:
                # It seems like NetworkX makes some assumptions on the graph which
                # are not documented (or which I could not find at least) that caused
                # these errors.
                # If the diameter computation fails for some reason, use an upper bound
                self._diameter = len(self._graph.edges)

        assert self._diameter is not None

        return self._diameter

    def __getstate__(self):
        return {
            "nodes": tuple(self._graph.nodes(data=True)),
            "edges": tuple(self._graph.edges(data=True)),
            "bytecode_cfg": self._bytecode_cfg,
            "diameter": self._diameter,
        }

    def __setstate__(self, state: dict):
        self._graph = nx.DiGraph()
        for node, data in state["nodes"]:
            self._graph.add_node(node, **data)
        for source, target, data in state["edges"]:
            self._graph.add_edge(source, target, **data)
        self._bytecode_cfg = state["bytecode_cfg"]
        self._diameter = state["diameter"]


class DominatorTree(ProgramGraph):
    """Implements a dominator tree."""

    @staticmethod
    def compute(graph: CFG) -> DominatorTree:
        """Computes the dominator tree for a control-flow graph.

        Args:
            graph: The control-flow graph

        Returns:
            The dominator tree for the control-flow graph
        """
        return DominatorTree.compute_dominance_tree(graph)

    @staticmethod
    def compute_post_dominator_tree(graph: CFG) -> DominatorTree:
        """Computes the post-dominator tree for a control-flow graph.

        Args:
            graph: The control-flow graph

        Returns:
            The post-dominator tree for the control-flow graph
        """
        reversed_cfg = graph.reversed()
        return DominatorTree.compute(reversed_cfg)

    @staticmethod
    def compute_dominance_tree(graph: CFG) -> DominatorTree:
        """Computes the dominance tree for a control-flow graph.

        Args:
            graph: The control-flow graph

        Returns:
            The dominance tree for the control-flow graph
        """
        dominance: dict[ProgramNode, set[ProgramNode]] = DominatorTree._calculate_dominance(graph)
        for dominance_node, nodes in dominance.items():
            nodes.discard(dominance_node)
        dominance_tree = DominatorTree()
        entry_node = graph.entry_node
        assert entry_node is not None
        dominance_tree.add_node(entry_node)

        node_queue: queue.SimpleQueue[ProgramNode] = queue.SimpleQueue()
        node_queue.put(entry_node)
        while not node_queue.empty():
            node = node_queue.get()
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
        graph: CFG,
    ) -> dict[ProgramNode, set[ProgramNode]]:
        dominance_map: dict[ProgramNode, set[ProgramNode]] = {}
        entry = graph.entry_node
        assert entry, "Cannot work with a graph without entry nodes"
        entry_dominators: set[ProgramNode] = {entry}
        dominance_map[entry] = entry_dominators

        for node in graph.nodes:
            if node == entry:
                continue
            all_nodes: set[ProgramNode] = set(graph.nodes)
            dominance_map[node] = all_nodes

        changed: bool = True
        while changed:
            changed = False
            for node in graph.nodes:
                if node == entry:
                    continue
                current_dominators = dominance_map.get(node)
                new_dominators = DominatorTree._calculate_dominators(graph, dominance_map, node)

                if current_dominators != new_dominators:
                    changed = True
                    dominance_map[node] = new_dominators
                    break

        return dominance_map

    @staticmethod
    def _calculate_dominators(
        graph: CFG,
        dominance_map: dict[ProgramNode, set[ProgramNode]],
        node: ProgramNode,
    ) -> set[ProgramNode]:
        dominators: set[ProgramNode] = {node}
        intersection: set[ProgramNode] = set()
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
        return intersection  # noqa: RET504


class ControlDependenceGraph(ProgramGraph):
    """Implements a control-dependence graph."""

    @staticmethod
    def compute(graph: CFG) -> ControlDependenceGraph:
        """Computes the control-dependence graph for a given control-flow graph.

        Args:
            graph: The control-flow graph

        Returns:
            The control-dependence graph
        """
        augmented_cfg = ControlDependenceGraph._create_augmented_graph(graph)
        post_dominator_tree = DominatorTree.compute_post_dominator_tree(augmented_cfg)
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
                    data = frozenset(augmented_cfg.graph.get_edge_data(source, target).items())
                    edges.add(ControlDependenceGraph._Edge(source=source, target=target, data=data))

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
                    "tree invariant"
                )
                current = predecessors.pop()

            if least_common_ancestor is edge.source:
                cdg.add_edge(edge.source, least_common_ancestor, **dict(edge.data))

        return filter_dead_code_nodes(cdg, ArtificialNode.START)

    def get_control_dependencies(self, node: ProgramNode) -> OrderedSet[ControlDependency]:
        """Get the immediate control dependencies of this node.

        Args:
            node: the node whose dependencies should be retrieved.

        Returns:
            The direct control dependencies of the given node, if any.
        """
        assert node in self.graph.nodes
        return self._retrieve_control_dependencies(node, OrderedSet())

    def _retrieve_control_dependencies(
        self,
        node: ProgramNode,
        handled: OrderedSet,
    ) -> OrderedSet[ControlDependency]:
        result: OrderedSet[ControlDependency] = OrderedSet()
        for pred in self._graph.predecessors(node):
            if (pred, node) in handled:
                continue
            handled.add((pred, node))

            if (
                isinstance(pred, BasicBlockNode)
                and (
                    branch_value := self._graph.get_edge_data(pred, node).get(
                        EDGE_DATA_BRANCH_VALUE, None
                    )
                )
                is not None
            ):
                # Why is it only based on the CFG whereas it is also based on the
                # concrete predicates in function is_control_dependent_on_root
                result.add(ControlDependency(pred, branch_value))
            else:
                result.update(self._retrieve_control_dependencies(pred, handled))
        return result

    def is_control_dependent_on_root(
        self,
        node: ProgramNode,
        predicate_nodes: Collection[ProgramNode],
    ) -> bool:
        """Does this node directly depend on entering the code object?

        Args:
            node: The program-graph node for the check
            predicate_nodes: The collection of nodes that are predicates in the graph

        Returns:
            Whether the given node is directly dependent on the entry of the code object
        """
        return self._is_control_dependent_on_root(node, predicate_nodes, set())

    def _is_control_dependent_on_root(
        self,
        node: ProgramNode,
        predicate_nodes: Collection[ProgramNode],
        visited: set[ProgramNode],
    ) -> bool:
        if (self.entry_node, node) in self.graph.edges:  # type: ignore[operator]
            return True
        for pred in self.graph.predecessors(node):
            if pred in visited:
                continue
            visited.add(pred)
            if pred in predicate_nodes:
                continue
            if pred == node:
                continue
            if self._is_control_dependent_on_root(pred, predicate_nodes, visited):
                return True
        return False

    def __getstate__(self):
        return {
            "nodes": tuple(self._graph.nodes(data=True)),
            "edges": tuple(self._graph.edges(data=True)),
        }

    def __setstate__(self, state: dict):
        self._graph = nx.DiGraph()
        for node, data in state["nodes"]:
            self._graph.add_node(node, **data)
        for source, target, data in state["edges"]:
            self._graph.add_edge(source, target, **data)

    @staticmethod
    def _create_augmented_graph(graph: CFG) -> CFG:
        entry_node = graph.entry_node
        assert entry_node, "Cannot work with CFG without entry node"
        exit_nodes = graph.exit_nodes
        augmented_graph = graph.copy()
        start_node = ArtificialNode.START
        augmented_graph.add_node(start_node)
        augmented_graph.add_edge(start_node, entry_node)
        for exit_node in exit_nodes:
            augmented_graph.add_edge(start_node, exit_node)
        return augmented_graph

    @dataclass(frozen=True)
    class _Edge:
        source: ProgramNode
        target: ProgramNode
        data: frozenset


@dataclass(frozen=True)
class ControlDependency:
    """Models a control dependency."""

    node: BasicBlockNode
    branch_value: bool
