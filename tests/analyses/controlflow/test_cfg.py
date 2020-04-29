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
import sys
from unittest.mock import MagicMock

import pytest

from pynguin.analyses.controlflow.cfg import CFG, CFGNode, CFGEdge


@pytest.fixture
def node() -> CFGNode:
    return CFGNode(index=42, incoming_edges=[], outgoing_edges=[], instructions=[])


@pytest.fixture
def edge() -> CFGEdge:
    return CFGEdge(index=42)


def test_node_index(node):
    assert node.index == 42


def test_node_incoming_edges(node):
    assert node.incoming_edges == []


def test_node_outgoing_edges(node):
    assert node.outgoing_edges == []


def test_node_hash(node):
    assert node.__hash__() != 0


def test_node_equals_other(node):
    assert not node.__eq__("foo")


def test_node_equals_self(node):
    assert node.__eq__(node)


def test_node_equals_other_node(node):
    other = CFGNode(index=42, incoming_edges=[], outgoing_edges=[], instructions=[])
    assert node.__eq__(other)


def test_edge_index(edge):
    assert edge.index == 42


def test_edge_predecessor(edge):
    with pytest.raises(AssertionError):
        edge.predecessor


def test_edge_successor(edge):
    with pytest.raises(AssertionError):
        edge.successor


def test_edge_hash(edge):
    assert edge.__hash__() != 0


def test_edge_equals_other(edge):
    assert not edge.__eq__("foo")


def test_edge_equals_self(edge):
    assert edge.__eq__(edge)


def test_edge_equals_other_edge(edge):
    predecessor = MagicMock(CFGNode)
    successor = MagicMock(CFGNode)
    edge._predecessor = predecessor
    edge._successor = successor
    other = CFGEdge(index=42, predecessor=predecessor, successor=successor)
    assert edge.__eq__(other)


def test_integration_create_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    assert cfg.cyclomatic_complexity == 2
    assert cfg.entry_node
    assert cfg.exit_node
    assert len(cfg.edges) == 5
    assert len(cfg.nodes) == 5


def test_integration_reverse_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    reversed_cfg = CFG.reverse(cfg)
    assert reversed_cfg.entry_node.index == sys.maxsize
    assert reversed_cfg.exit_node.index == 0
    assert len(reversed_cfg.edges) == 5
    assert len(reversed_cfg.nodes) == 5


def test_integration_reverse_small_cfg(small_control_flow_graph):
    cfg = CFG()
    entry = CFGNode(index=0)
    n6 = CFGNode(index=6)
    n5 = CFGNode(index=5)
    n4 = CFGNode(index=4)
    n3 = CFGNode(index=3)
    n2 = CFGNode(index=2)
    exit_node = CFGNode(index=sys.maxsize)
    e0 = CFGEdge(index=0, predecessor=n6, successor=entry)
    e1 = CFGEdge(index=1, predecessor=n5, successor=n6)
    e2 = CFGEdge(index=2, predecessor=n4, successor=n5)
    e3 = CFGEdge(index=3, predecessor=n3, successor=n5)
    e4 = CFGEdge(index=4, predecessor=n2, successor=n4)
    e5 = CFGEdge(index=5, predecessor=n2, successor=n3)
    e6 = CFGEdge(index=6, predecessor=exit_node, successor=n2)
    exit_node.add_outgoing_edge(e6)
    n2.add_incoming_edge(e6)
    n2.add_outgoing_edge(e5)
    n2.add_outgoing_edge(e4)
    n3.add_incoming_edge(e5)
    n3.add_outgoing_edge(e3)
    n4.add_incoming_edge(e4)
    n4.add_outgoing_edge(e2)
    n5.add_incoming_edge(e2)
    n5.add_incoming_edge(e3)
    n5.add_outgoing_edge(e1)
    n6.add_incoming_edge(e1)
    n6.add_outgoing_edge(e0)
    entry.add_incoming_edge(e0)
    cfg._nodes = [entry, n6, n5, n4, n3, n2, exit_node]
    cfg._edges = [e0, e1, e2, e3, e4, e5, e6]
    reversed_cfg = CFG.reverse(small_control_flow_graph)
    assert reversed_cfg.exit_node == cfg.exit_node
    assert reversed_cfg.entry_node == cfg.entry_node
    assert reversed_cfg.nodes == cfg.nodes
    assert reversed_cfg.edges == cfg.edges
