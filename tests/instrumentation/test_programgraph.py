#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from opcode import opmap
from unittest.mock import MagicMock

import pytest

from bytecode.cfg import BasicBlock
from bytecode.instr import Instr

from pynguin.instrumentation.controlflow import BasicBlockNode
from pynguin.instrumentation.controlflow import ProgramGraph


@pytest.fixture
def mock_basic_block() -> BasicBlock:
    mock = MagicMock(BasicBlock)
    mock.__len__.side_effect = lambda: 1  # To pass an assertion in BasicBlockNode
    return mock


@pytest.fixture
def node(mock_basic_block) -> BasicBlockNode:
    return BasicBlockNode(index=42, basic_block=mock_basic_block)


@pytest.fixture
def second_node(mock_basic_block) -> BasicBlockNode:
    return BasicBlockNode(index=23, basic_block=mock_basic_block)


@pytest.fixture
def third_node(mock_basic_block) -> BasicBlockNode:
    return BasicBlockNode(index=21, basic_block=mock_basic_block)


@pytest.fixture
def fourth_node(mock_basic_block) -> BasicBlockNode:
    return BasicBlockNode(index=24, basic_block=mock_basic_block)


@pytest.fixture
def graph() -> ProgramGraph:
    return ProgramGraph()


def test_node_index(node):
    assert node.index == 42


def test_node_basic_block(mock_basic_block):
    node = BasicBlockNode(index=42, basic_block=mock_basic_block)
    assert node.basic_block == mock_basic_block


def test_node_hash(node):
    assert (hash(node)) != 0


def test_node_equals_other(node):
    assert node != "foo"


def test_node_equals_self(node):
    assert node == node  # noqa: PLR0124


def test_node_equals_other_node(node, mock_basic_block):
    other = BasicBlockNode(index=42, basic_block=mock_basic_block)
    assert node == other


def test_add_graph(graph, node):
    graph.add_node(node)
    assert len(graph.nodes) == 1


def test_graph_nodes_set(graph, node, second_node, third_node, fourth_node):
    graph.add_node(node)
    graph.add_node(second_node)
    graph.add_node(third_node)
    graph.add_node(fourth_node)
    nodes = graph.nodes
    assert nodes == {node, second_node, third_node, fourth_node}


def test_add_edge(graph, node, second_node):
    graph.add_node(node)
    graph.add_node(second_node)
    graph.add_edge(node, second_node)
    assert graph.entry_node == node
    assert graph.exit_nodes == {second_node}


def test_entry_exit_node_without_nodes(graph):
    assert graph.entry_node is None
    assert graph.exit_nodes == set()


def test_get_transitive_successors(graph, node, second_node, third_node, fourth_node):
    graph.add_node(fourth_node)
    graph.add_node(node)
    graph.add_node(second_node)
    graph.add_node(third_node)
    graph.add_edge(node, second_node)
    graph.add_edge(second_node, third_node)
    graph.add_edge(third_node, fourth_node)
    result = graph.get_transitive_successors(second_node)
    assert result == {third_node, fourth_node}


def test_get_least_common_ancestor(graph, node, second_node, third_node):
    graph.add_node(node)
    graph.add_node(second_node)
    graph.add_node(third_node)
    graph.add_edge(node, second_node)
    graph.add_edge(node, third_node)
    result = graph.get_least_common_ancestor(second_node, third_node)
    assert result == node


def test_to_dot(graph, node, second_node):
    graph.add_node(node)
    graph.add_node(second_node)
    graph.add_edge(node, second_node)
    result = graph.dot
    assert result != ""  # noqa: PLC1901


def test_get_predecessors(graph, node, second_node):
    graph.add_node(node)
    graph.add_node(second_node)
    graph.add_edge(node, second_node)
    result = graph.get_predecessors(second_node)
    assert result == {node}


def test_yield_nodes():
    graph = ProgramGraph()
    yield_instr = Instr(name="YIELD_VALUE")
    yield_instr.opcode = opmap["YIELD_VALUE"]
    instructions = [yield_instr]
    basic_block = BasicBlock(instructions=instructions)
    node = BasicBlockNode(index=42, basic_block=basic_block)
    graph.add_node(node)
    yield_nodes = graph.yield_nodes
    assert len(yield_nodes) == 1


def test_yield_nodes_2():
    graph = ProgramGraph()

    yield_instr = Instr(name="YIELD_VALUE")
    yield_instr.opcode = opmap["YIELD_VALUE"]
    instructions = [yield_instr]
    basic_block = BasicBlock(instructions=instructions)
    node = BasicBlockNode(index=42, basic_block=basic_block)
    graph.add_node(node)

    yield_instr_2 = Instr(name="YIELD_VALUE")
    yield_instr_2.opcode = opmap["YIELD_VALUE"]
    instructions_2 = [yield_instr_2]
    basic_block_2 = BasicBlock(instructions=instructions_2)
    node_2 = BasicBlockNode(index=43, basic_block=basic_block_2)
    graph.add_node(node_2)

    yield_nodes = graph.yield_nodes
    assert len(yield_nodes) == 2
