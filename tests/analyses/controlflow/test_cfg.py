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

from bytecode import Bytecode

from pynguin.analyses.controlflow.cfg import CFG
from tests.fixtures.programgraph.whileloop import Foo


def test_integration_create_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    dot_representation = cfg.to_dot()
    graph = """strict digraph  {
"ProgramGraphNode(0)";
"ProgramGraphNode(1)";
"ProgramGraphNode(2)";
"ProgramGraphNode(3)";
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)";
"ProgramGraphNode(0)" -> "ProgramGraphNode(1)";
"ProgramGraphNode(0)" -> "ProgramGraphNode(2)";
"ProgramGraphNode(1)" -> "ProgramGraphNode(3)";
"ProgramGraphNode(2)" -> "ProgramGraphNode(3)";
"ProgramGraphNode(3)" -> "ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)" -> "ProgramGraphNode(0)";
}
"""
    assert cfg.cyclomatic_complexity == 2
    assert cfg.entry_node.is_artificial
    assert len(cfg.exit_nodes) == 1
    assert dot_representation == graph


def test_integration_reverse_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    reversed_cfg = cfg.reversed()
    dot_representation = reversed_cfg.to_dot()
    graph = """strict digraph  {
"ProgramGraphNode(0)";
"ProgramGraphNode(1)";
"ProgramGraphNode(2)";
"ProgramGraphNode(3)";
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)";
"ProgramGraphNode(0)" -> "ProgramGraphNode(-1)";
"ProgramGraphNode(1)" -> "ProgramGraphNode(0)";
"ProgramGraphNode(2)" -> "ProgramGraphNode(0)";
"ProgramGraphNode(3)" -> "ProgramGraphNode(1)";
"ProgramGraphNode(3)" -> "ProgramGraphNode(2)";
"ProgramGraphNode(9223372036854775807)" -> "ProgramGraphNode(3)";
}
"""
    assert reversed_cfg.cyclomatic_complexity == 2
    assert cfg.entry_node.is_artificial
    assert len(cfg.exit_nodes) == 1
    assert dot_representation == graph


def test_integration_copy_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    copied_cfg = cfg.copy()
    assert copied_cfg.to_dot() == cfg.to_dot()


def test_integration_while_loop():
    while_loop_cfg = CFG.from_bytecode(Bytecode.from_code(Foo.receive.__code__))
    assert len(while_loop_cfg.nodes) == 3
    assert while_loop_cfg.entry_node.index == -1
    assert while_loop_cfg.exit_nodes.pop().index == sys.maxsize
