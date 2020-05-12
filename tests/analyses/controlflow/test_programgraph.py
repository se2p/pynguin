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
from typing import List
from unittest.mock import MagicMock

import pytest
from bytecode import Instr, BasicBlock

from pynguin.analyses.controlflow.programgraph import ProgramGraphNode, ProgramGraph


@pytest.fixture
def mock_instructions() -> List[Instr]:
    return [MagicMock(Instr)]


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
    result = graph.to_dot()
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
