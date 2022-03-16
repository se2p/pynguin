#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest
from bytecode import BasicBlock

from pynguin.analyses.controlflow import ProgramGraph, ProgramGraphNode


@pytest.fixture
def mock_basic_block() -> BasicBlock:
    return MagicMock(BasicBlock)


@pytest.fixture
def node() -> ProgramGraphNode:
    return ProgramGraphNode(index=42)


@pytest.fixture
def second_node() -> ProgramGraphNode:
    return ProgramGraphNode(index=23)


@pytest.fixture
def third_node() -> ProgramGraphNode:
    return ProgramGraphNode(index=21)


@pytest.fixture
def fourth_node() -> ProgramGraphNode:
    return ProgramGraphNode(index=24)


@pytest.fixture
def graph() -> ProgramGraph:
    return ProgramGraph()


def test_node_index(node):
    assert node.index == 42


def test_node_basic_block(mock_basic_block):
    node = ProgramGraphNode(index=42, basic_block=mock_basic_block)
    assert node.basic_block == mock_basic_block


def test_node_hash(node):
    assert node.__hash__() != 0


def test_node_equals_other(node):
    assert not node.__eq__("foo")


def test_node_equals_self(node):
    assert node.__eq__(node)


def test_node_equals_other_node(node):
    other = ProgramGraphNode(index=42)
    assert node.__eq__(other)


def test_add_graph(graph, node):
    graph.add_node(node)
    assert len(graph.nodes) == 1


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
    assert result != ""


def test_get_predecessors(graph, node, second_node):
    graph.add_node(node)
    graph.add_node(second_node)
    graph.add_edge(node, second_node)
    result = graph.get_predecessors(second_node)
    assert result == {node}


def test_is_artificial():
    node = ProgramGraphNode(index=42, is_artificial=True)
    assert node.is_artificial


def test_predicate_id_none():
    node = ProgramGraphNode(index=42)
    assert node.predicate_id is None


def test_predicate_id_set():
    node = ProgramGraphNode(index=42)
    node.predicate_id = 1337
    assert node.predicate_id == 1337
