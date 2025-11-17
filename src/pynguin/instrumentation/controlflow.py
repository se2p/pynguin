#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides analyses regarding the control-flow of the program."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar

import networkx as nx
from bytecode.cfg import BasicBlock, ControlFlowGraph
from bytecode.instr import UNSET, Compare, Instr, SetLineno, TryBegin, TryEnd

from pynguin.instrumentation import version
from pynguin.utils.orderedset import OrderedSet

if TYPE_CHECKING:
    from collections.abc import Iterable

    from bytecode import Bytecode

# Key for storing branch value in networkx edge.
EDGE_DATA_BRANCH_VALUE = "branch_value"

TRY_BEGIN_POSITION = -1

FIRST_BASIC_BLOCK_NODE_INDEX = 0


class ArtificialInstr(Instr):
    """Marker subclass of an instruction.

    Used to distinguish between original instructions and instructions that were
    inserted by the instrumentation.
    """


class ArtificialNode(Enum):
    """Types of artificial nodes in the program graph."""

    AUGMENTED_ENTRY = "AUGMENTED_ENTRY"
    """An artificial augmented entry node used in the control-dependence graph."""

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
    ) -> None:
        """Instantiates a node for a program graph.

        Args:
            index: The index of the node
            basic_block: The basic block in the code
        """
        self._index = index
        self._basic_block = basic_block

    @property
    def index(self) -> int:
        """Provides the index of the node.

        Returns:
            The index of the node
        """
        return self._index

    @property
    def basic_block(self) -> BasicBlock:
        """Provides the basic block attached to this node.

        Returns:
            The basic block attached to this node
        """
        assert len(self._basic_block) > 0, "Basic block must not be empty."
        return self._basic_block

    @property
    def instructions(self) -> Iterable[Instr]:
        """Provides the instructions of the basic block.

        Returns:
            The instructions of the basic block
        """
        for instr in self._basic_block:
            if isinstance(instr, Instr):
                yield instr

    def _get_instruction(self, index: int) -> Instr:
        """Get the instruction at the given index.

        Args:
            index: The index of the instruction

        Returns:
            The instruction at the given index
        """
        return tuple(instr for instr in self.instructions)[index]

    def try_get_instruction(self, index: int) -> Instr | None:
        """Try to get the instruction at the given index.

        Args:
            index: The index of the instruction

        Returns:
            The instruction at the given index or None if no such instruction exists
        """
        try:
            return self._get_instruction(index)
        except IndexError:
            return None

    @property
    def original_instructions(self) -> Iterable[Instr]:
        """Provides the original instructions of the basic block.

        Returns:
            The original instructions of the basic block
        """
        for instr in self.instructions:
            if not isinstance(instr, ArtificialInstr):
                yield instr

    @property
    def instrumentation_original_instructions(self) -> Iterable[tuple[int, Instr]]:
        """Provides the original instructions in a mode that is suitable for instrumentation.

        This mode means that after each yield, the function will automatically skip all instructions
        added by the instrumentation until the next instruction that was supposed to be yielded.

        Returns:
            An iterable of tuples containing the index of the instructions and the instructions
        """
        instr_index = 0
        while instr_index < len(self._basic_block):
            instr = self.try_get_instruction(instr_index)

            if instr is None:
                break

            if isinstance(instr, ArtificialInstr):
                instr_index += 1
                continue

            yield instr_index, instr

            # Update the instr_index to retarget at the original instruction
            while (
                isinstance(new_instr := self._get_instruction(instr_index), ArtificialInstr)
                or new_instr != instr
            ):
                instr_index += 1

            instr_index += 1

    def find_instruction_by_original_index(self, original_index: int) -> tuple[int, Instr]:
        """Find an index and instruction by its original index.

        Args:
            original_index: The index of the instruction

        Returns:
            The index of the instruction in the basic block and the instruction itself
        """
        return tuple(
            (instr_index, instr)
            for instr_index, instr in enumerate(self.instructions)
            if not isinstance(instr, ArtificialInstr)
        )[original_index]

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
        }

    def __setstate__(self, state: dict) -> None:
        self._index = state["index"]
        self._basic_block = state["basic_block"]

    def __str__(self) -> str:
        instructions = []
        for instr in self._basic_block:
            if isinstance(instr, Instr):
                arg = instr.arg
                if isinstance(arg, BasicBlock):
                    # We cannot determine which BasicBlockNode this is.
                    arg = "BasicBlockNode"
                elif isinstance(arg, Compare):
                    arg = arg.name
                elif arg is UNSET:
                    arg = ""
                else:
                    arg = repr(arg)
                formatted = instr.name
                if arg:
                    formatted += f" {arg}"
            elif isinstance(instr, TryBegin):
                formatted = f"TryBegin {id(instr)}"
            elif isinstance(instr, TryEnd):
                formatted = f"TryEnd {id(instr.entry)}"
            elif isinstance(instr, SetLineno):
                formatted = f"SetLineno({instr.lineno})"
            else:
                raise AssertionError(f"Unknown instruction type {type(instr)}.")

            instructions.append(formatted)

        return f"BasicBlockNode({self._index})\n" + "\n".join(instructions)

    def __repr__(self) -> str:
        return f"BasicBlockNode(index={self._index}, basic_block={self._basic_block})"


ProgramNode: TypeAlias = ArtificialNode | BasicBlockNode


class ProgramGraph:
    """Provides a base implementation for a program graph.

    Internally, this program graph uses the `NetworkX` library to hold the graph and
    do all the operations on it.
    """

    def __init__(self, graph: nx.DiGraph[ProgramNode] | None = None) -> None:
        """Initializes a new program graph.

        Args:
            graph: The graph to use for this program graph, or None to create a new empty one.
        """
        self._graph: nx.DiGraph[ProgramNode] = graph if graph is not None else nx.DiGraph()

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

    def get_basic_block_node(self, index: int) -> BasicBlockNode:
        """Provides the basic block node with the given index.

        Args:
            index: The index of the basic block node

        Raises:
            ValueError: If no basic block node with the given index exists

        Returns:
            The basic block node with the given index
        """
        for node in self._graph.nodes:
            if isinstance(node, BasicBlockNode) and node.index == index:
                return node

        raise ValueError(f"No BasicBlockNode found with index {index}")

    def get_predecessors(self, node: ProgramNode) -> set[ProgramNode]:
        """Provides a set of all direct predecessors of a node.

        Args:
            node: The node to start

        Returns:
            A set of direct predecessors of the node
        """
        return set(self._graph.predecessors(node))

    def get_ancestors(self, node: ProgramNode) -> set[ProgramNode]:
        """Provides a set of all ancestors of a node.

        An ancestor is a non-direct predecessor of a node, i.e., a node that can be reached
        from the given node by following the edges in the graph in reverse direction.

        Args:
            node: The node to start

        Returns:
            A set of all ancestors of the node
        """
        return nx.ancestors(self._graph, node)

    def get_successors(self, node: ProgramNode) -> set[ProgramNode]:
        """Provides a set of all direct successors of a node.

        Args:
            node: The node to start

        Returns:
            A set of direct successors of the node
        """
        return set(self._graph.successors(node))

    def get_descendants(self, node: ProgramNode) -> set[ProgramNode]:
        """Provides a set of all descendants of a node.

        A descendant is a non-direct successor of a node, i.e., a node that can be reached
        from the given node by following the edges in the graph.

        Args:
            node: The node to start

        Returns:
            A set of all descendants of the node
        """
        return nx.descendants(self._graph, node)

    @property
    def nodes(self) -> set[ProgramNode]:
        """Provides all nodes in the graph.

        Returns:
            The set of all nodes in the graph
        """
        return set(self._graph.nodes)

    @property
    def basic_block_nodes(self) -> set[BasicBlockNode]:
        """Provides all basic block nodes in the graph.

        Returns:
            The set of all basic block nodes in the graph
        """
        return {node for node in self._graph.nodes if isinstance(node, BasicBlockNode)}

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
            if self._graph.in_degree(node) == 0:
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
            if self._graph.out_degree(node) == 0:
                exit_nodes.add(node)
        return exit_nodes

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
                # is the entry node. All other nodes without predecessors are considered
                # dead code and thus removed.
                graph.graph.remove_node(node)
                has_changed = True
    return graph


class CFG(ProgramGraph):
    """The control-flow graph implementation based on the program graph."""

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
         - an artificial entry node that is guaranteed to fulfill the
           property of an entry node, i.e., there is no incoming edge, and
         - an artificial exit node that is guaranteed to
           fulfill the property of an exit node, i.e., there is no outgoing edge, and
           that is the only such node in the graph, which is important, e.g., for graph
           reversal.

        Args:
            bytecode: The bytecode segment

        Returns:
            The control-flow graph for the segment
        """
        blocks = ControlFlowGraph.from_bytecode(bytecode)
        cfg = CFG(blocks)

        # Split try begin blocks to ensure that all jumps are at the end of each block
        CFG._split_try_begin_blocks(blocks)

        # Create the nodes and a mapping of all edges to generate
        edges, nodes = CFG._create_nodes_and_edges(blocks)

        # Insert all edges between the previously generated nodes
        CFG._create_graph(cfg, edges, nodes)

        # Insert dummy entry and exit nodes
        CFG._insert_dummy_nodes(cfg)

        # Filter all dead-code nodes and return
        return filter_dead_code_nodes(cfg, ArtificialNode.ENTRY)

    @property
    def bytecode_cfg(self) -> ControlFlowGraph:
        """Provide the raw control flow graph from the code object.

        Can be used to instrument the control flow.

        Returns:
            The raw control-flow graph from the code object
        """
        return self._bytecode_cfg

    @property
    def first_basic_block_node(self) -> BasicBlockNode | None:
        """Provides the first basic block node of the graph.

        Returns:
            The first basic block node of the graph or None if no such node exists
        """
        try:
            return self.get_basic_block_node(FIRST_BASIC_BLOCK_NODE_INDEX)
        except ValueError:
            return None

    @staticmethod
    def _split_try_begin_blocks(blocks: ControlFlowGraph) -> None:
        for block in blocks:
            for i, instr in enumerate(block):
                if isinstance(instr, TryBegin):
                    blocks.split_block(block, i + 1)

    @staticmethod
    def _create_nodes_and_edges(
        blocks: ControlFlowGraph,
    ) -> tuple[dict[int, list[tuple[int, dict]]], dict[int, ProgramNode]]:
        nodes: dict[int, ProgramNode] = {}
        edges: dict[int, list[tuple[int, dict]]] = defaultdict(list)
        for node_index, block in enumerate(blocks, start=FIRST_BASIC_BLOCK_NODE_INDEX):
            node = BasicBlockNode(index=node_index, basic_block=block)

            nodes[node_index] = node

            next_block = block.next_block

            last_instr = block.get_last_non_artificial_instruction()

            if last_instr is not None and version.is_conditional_jump(last_instr):
                target_block = block.get_jump()

                assert next_block is not None
                assert target_block is not None

                is_true_branch = version.get_branch_type(last_instr.opcode)

                assert is_true_branch is not None, (
                    f"Unknown conditional Jump instruction in bytecode : {last_instr.name}"
                )

                if is_true_branch:
                    true_branch = target_block
                    false_branch = next_block
                else:
                    true_branch = next_block
                    false_branch = target_block

                for next_branch, value in [(true_branch, True), (false_branch, False)]:
                    next_index = blocks.get_block_index(next_branch)
                    # 'label' is also set to value, to get a nicer DOT representation,
                    # because 'label' is a keyword for labelling edges.
                    edges[node_index].append((
                        next_index,
                        {EDGE_DATA_BRANCH_VALUE: value, "label": value},
                    ))
            else:
                maybe_try_begin = block[TRY_BEGIN_POSITION]

                if isinstance(maybe_try_begin, TryBegin):
                    assert isinstance(maybe_try_begin.target, BasicBlock)
                    target_block = maybe_try_begin.target
                else:
                    target_block = block.get_jump()

                if next_block is not None:
                    next_index = blocks.get_block_index(next_block)
                    edges[node_index].append((next_index, {}))
                if target_block is not None:
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
    def _get_yield_nodes(cfg: CFG) -> Iterable[ProgramNode]:
        """Provides the yield nodes of the graph.

        Iterates over all nodes and checks if any of the instructions in the basic block
        is a yield instruction. If so, the node is added to the set of yield nodes. Then
        we ignore the rest of the instructions in this basic block and continue with the
        next node.

        Returns:
            The iterable of yield nodes of the graph
        """
        for node in cfg.basic_block_nodes:
            for instr in node.instructions:
                if instr.name in version.YIELDING_NAMES:
                    yield node
                    # exist the inner loop (over instructions)
                    # the node is already added thus continue with the next node
                    break

    @staticmethod
    def _insert_dummy_nodes(cfg: CFG) -> None:
        entry_node = cfg.first_basic_block_node

        assert entry_node is not None, (
            f"Control flow must have an entry node. Offending CFG: {cfg.dot}"
        )

        distances_to_entry_point: dict[ProgramNode, int] = nx.single_source_shortest_path_length(
            cfg.graph,
            entry_node,
        )

        # Collect all exit nodes
        exit_nodes = cfg.exit_nodes

        # Add yield nodes
        exit_nodes.update(CFG._get_yield_nodes(cfg))

        # Add infinite loop nodes
        exit_nodes.update(
            loop_entry
            for cycle in nx.simple_cycles(cfg.graph)
            if cfg.get_descendants(
                loop_entry := min(cycle, key=lambda node: distances_to_entry_point[node])
            ).isdisjoint(exit_nodes)
        )

        assert exit_nodes is not None, (
            f"Control flow must have at least one exit or yield node. Offending CFG: {cfg.dot}"
        )

        # Add the dummy nodes
        cfg.add_node(ArtificialNode.ENTRY)
        cfg.add_node(ArtificialNode.EXIT)

        # Connect the dummy nodes
        cfg.add_edge(ArtificialNode.ENTRY, entry_node)
        for exit_node in exit_nodes:
            cfg.add_edge(exit_node, ArtificialNode.EXIT)

    @property
    def cyclomatic_complexity(self) -> int:
        """Calculates McCabe's cyclomatic complexity for this control-flow graph.

        Returns:
            McCabe's cyclocmatic complexity number
        """
        return len(self._graph.edges) - len(self._graph.nodes) + 2

    @cached_property
    def diameter(self) -> int:
        """Computes the diameter of the graph.

        Returns:
            The diameter of the graph
        """
        # Do this computation lazily
        try:
            return nx.diameter(self._graph, usebounds=True)
        except nx.NetworkXError:
            # It seems like NetworkX makes some assumptions on the graph which
            # are not documented (or which I could not find at least) that caused
            # these errors.
            # If the diameter computation fails for some reason, use an upper bound
            return len(self._graph.edges)

    def __getstate__(self):
        return {
            "nodes": tuple(self._graph.nodes(data=True)),
            "edges": tuple(self._graph.edges(data=True)),
            "bytecode_cfg": self._bytecode_cfg,
        }

    def __setstate__(self, state: dict):
        self._graph = nx.DiGraph()
        for node, attr in state["nodes"]:
            self._graph.add_node(node, **attr)
        for source, target, attr in state["edges"]:
            self._graph.add_edge(source, target, **attr)
        self._bytecode_cfg = state["bytecode_cfg"]


class ControlDependenceGraph(ProgramGraph):
    """Implements a control-dependence graph."""

    @staticmethod
    def _create_augmented_graph(cfg: CFG) -> ProgramGraph:
        """Augments a CFG (control flow graph) with an additional entry node.

        When constructing the CDG (control dependence graph) the entry and exit nodes of the CFG are
        removed. If the first node of the resulting CDG graph (1) would be used as root node of the
        CDG, nodes that are only dependent on method entry (7) would not be connected to the graph
        at all. Thus, we instead need to add an artifical root node: the augmented entry node.

        Reference:
        Jeanne Ferrante, Karl J. Ottenstein, and Joe D. Warren. 1987.
        The program dependence graph and its use in optimization. ACM Trans.
        Program. Lang. Syst. 9, 3 (July 1987), 319-349. https://doi.org/10.1145/24039.24041

        See Figure 1 for the referenced example.

        Args:
            cfg: The control flow graph

        Returns:
            A control flow graph with an augmented entry node
        """
        augmented_graph = ProgramGraph(cfg.graph.copy())

        augmented_graph.add_node(ArtificialNode.AUGMENTED_ENTRY)
        augmented_graph.add_edge(ArtificialNode.AUGMENTED_ENTRY, ArtificialNode.ENTRY)
        augmented_graph.add_edge(ArtificialNode.AUGMENTED_ENTRY, ArtificialNode.EXIT)

        return augmented_graph

    @staticmethod
    def _compute_post_dominator_tree(augmented_cfg: ProgramGraph) -> ProgramGraph:
        immediate_dominators: dict[ProgramNode, ProgramNode] = nx.immediate_dominators(
            augmented_cfg.graph.reverse(copy=False),
            ArtificialNode.EXIT,
        )
        return ProgramGraph(
            nx.DiGraph(
                (immediate_dominator, node)
                for node, immediate_dominator in immediate_dominators.items()
                if node != immediate_dominator
            )
        )

    @staticmethod
    def compute(cfg: CFG) -> ControlDependenceGraph:
        """Computes the control-dependence graph for a given control-flow graph.

        Args:
            cfg: The control-flow graph

        Returns:
            The control-dependence graph
        """
        augmented_cfg = ControlDependenceGraph._create_augmented_graph(cfg)
        post_dominator_tree = ControlDependenceGraph._compute_post_dominator_tree(augmented_cfg)
        cdg = ControlDependenceGraph()

        for node in augmented_cfg.nodes:
            cdg.add_node(node)

        # Find matching edges in the CFG.
        edges: tuple[tuple[ProgramNode, ProgramNode, dict], ...] = tuple(
            # Store branching data from edge, i.e., which outcome of the
            # branching node leads to this node.
            (source, target, attr)
            for source, target, attr in augmented_cfg.graph.edges(data=True)
            if target not in post_dominator_tree.get_ancestors(source)
        )

        # Mark nodes in the post-dominator tree and construct edges for them.
        for source, target, attr in edges:
            least_common_ancestor: ProgramNode = nx.lowest_common_ancestor(
                post_dominator_tree.graph,
                source,
                target,
            )

            if least_common_ancestor is source:
                cdg.add_edge(source, least_common_ancestor, **attr)

            current = target
            while current != least_common_ancestor:
                cdg.add_edge(source, current, **attr)
                predecessors = post_dominator_tree.get_predecessors(current)
                assert len(predecessors) == 1, (
                    "Cannot have more than one predecessor in a tree, this violates a "
                    "tree invariant"
                )
                current = predecessors.pop()

        # Remove dummy entry and exit nodes
        cdg.graph.remove_node(ArtificialNode.ENTRY)
        cdg.graph.remove_node(ArtificialNode.EXIT)

        return cdg

    def get_dominator_loops(self, node: BasicBlockNode) -> set[BasicBlockNode]:
        """Provides the set of loops that dominate the given node.

        Args:
            node: The node to check

        Returns:
            The set of loops that dominate the given node
        """
        dominators = self.get_ancestors(node)
        return {
            node
            for node in self.graph.nodes
            if isinstance(node, BasicBlockNode) and self.graph.has_edge(node, node) and dominators
        }

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
                result.add(ControlDependency(pred, branch_value))
            else:
                result.update(self._retrieve_control_dependencies(pred, handled))
        return result

    def is_control_dependent_on_root(
        self,
        node: ProgramNode,
    ) -> bool:
        """Checks if a node is reachable from the entry node without passing through any predicate nodes.

        Args:
            node: The program-graph node for the check

        Returns:
            Whether the given node is directly dependent on the entry of the code object
        """  # noqa: E501
        return self._is_control_dependent_on_root(node, set())

    def _is_control_dependent_on_root(
        self,
        node: ProgramNode,
        visited: set[ProgramNode],
    ) -> bool:
        if (self.entry_node, node) in self.graph.edges:  # type: ignore[operator,unused-ignore]
            return True
        for pred in self.graph.predecessors(node):
            if pred in visited:
                continue
            visited.add(pred)
            if (
                isinstance(pred, BasicBlockNode)
                and self._graph.get_edge_data(pred, node).get(EDGE_DATA_BRANCH_VALUE, None)
                is not None
            ):
                continue
            if pred == node:
                continue
            if self._is_control_dependent_on_root(pred, visited):
                return True
        return False

    def __getstate__(self):
        return {
            "nodes": tuple(self._graph.nodes(data=True)),
            "edges": tuple(self._graph.edges(data=True)),
        }

    def __setstate__(self, state: dict):
        self._graph = nx.DiGraph()
        for node, attr in state["nodes"]:
            self._graph.add_node(node, **attr)
        for source, target, attr in state["edges"]:
            self._graph.add_edge(source, target, **attr)


@dataclass(frozen=True)
class ControlDependency:
    """Models a control dependency."""

    node: BasicBlockNode
    branch_value: bool
