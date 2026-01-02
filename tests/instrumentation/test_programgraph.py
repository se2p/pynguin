#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest
from bytecode.cfg import BasicBlock

from pynguin.instrumentation.controlflow import BasicBlockNode, ProgramGraph


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
