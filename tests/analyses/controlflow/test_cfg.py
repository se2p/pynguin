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
import pytest
from bytecode import Bytecode, Label, Instr, ControlFlowGraph

from pynguin.analyses.controlflow.cfg import CFG, CFGNode, CFGEdge


@pytest.fixture(scope="module")
def conditional_jump_example() -> Bytecode:
    label_else = Label()
    label_print = Label()
    byte_code = Bytecode(
        [
            Instr("LOAD_NAME", "print"),
            Instr("LOAD_NAME", "test"),
            Instr("POP_JUMP_IF_FALSE", label_else),
            Instr("LOAD_CONST", "yes"),
            Instr("JUMP_FORWARD", label_print),
            label_else,
            Instr("LOAD_CONST", "no"),
            label_print,
            Instr("CALL_FUNCTION", 1),
            Instr("LOAD_CONST", None),
            Instr("RETURN_VALUE"),
        ]
    )
    return byte_code


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
    assert edge.predecessor is None


def test_edge_successor(edge):
    assert edge.successor is None


def test_edge_hash(edge):
    assert edge.__hash__() != 0


def test_edge_equals_other(edge):
    assert not edge.__eq__("foo")


def test_edge_equals_self(edge):
    assert edge.__eq__(edge)


def test_edge_equals_other_edge(edge):
    other = CFGEdge(index=42)
    assert edge.__eq__(other)


def test_integration_create_cfg(conditional_jump_example):
    cfg = CFG.from_bytecode(conditional_jump_example)
    assert cfg.cyclomatic_complexity == 2
    assert cfg.entry_node
    assert cfg.exit_node
    assert len(cfg.edges) == 4
    assert len(cfg.nodes) == 4
