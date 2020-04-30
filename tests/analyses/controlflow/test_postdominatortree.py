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

import pynguin.analyses.controlflow.cfg as cfg
import pynguin.analyses.controlflow.postdominatortree as pdt


def test_integration_post_dominator_tree(conditional_jump_example_bytecode):
    control_flow_graph = cfg.CFG.from_bytecode(conditional_jump_example_bytecode)
    post_dominator_tree = pdt.PostDominatorTree.compute(control_flow_graph)
    dot_representation = post_dominator_tree.to_dot()
    graph = """strict digraph  {
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(3)";
"ProgramGraphNode(2)";
"ProgramGraphNode(1)";
"ProgramGraphNode(0)";
"ProgramGraphNode(9223372036854775807)" -> "ProgramGraphNode(3)";
"ProgramGraphNode(3)" -> "ProgramGraphNode(2)";
"ProgramGraphNode(3)" -> "ProgramGraphNode(1)";
"ProgramGraphNode(3)" -> "ProgramGraphNode(0)";
}
"""
    assert dot_representation == graph
    assert post_dominator_tree.entry_node.index == sys.maxsize


def test_integration(small_control_flow_graph):
    post_dominator_tree = pdt.PostDominatorTree.compute(small_control_flow_graph)
    dot_representation = post_dominator_tree.to_dot()
    graph = """strict digraph  {
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(2)";
"ProgramGraphNode(4)";
"ProgramGraphNode(3)";
"ProgramGraphNode(5)";
"ProgramGraphNode(6)";
"ProgramGraphNode(0)";
"ProgramGraphNode(9223372036854775807)" -> "ProgramGraphNode(2)";
"ProgramGraphNode(2)" -> "ProgramGraphNode(4)";
"ProgramGraphNode(2)" -> "ProgramGraphNode(3)";
"ProgramGraphNode(2)" -> "ProgramGraphNode(5)";
"ProgramGraphNode(5)" -> "ProgramGraphNode(6)";
"ProgramGraphNode(6)" -> "ProgramGraphNode(0)";
}
"""
    assert dot_representation == graph
    assert post_dominator_tree.entry_node.index == sys.maxsize
