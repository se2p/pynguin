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
import pynguin.analyses.controlflow.controldependencegraph as cdt


def test_integration(small_control_flow_graph):
    control_dependence_graph = cdt.ControlDependenceGraph.compute(
        small_control_flow_graph
    )
    dot_representation = control_dependence_graph.to_dot()
    graph = """strict digraph  {
"ProgramGraphNode(2)";
"ProgramGraphNode(4)";
"ProgramGraphNode(6)";
"ProgramGraphNode(3)";
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(5)";
"ProgramGraphNode(0)";
"ProgramGraphNode(5)" -> "ProgramGraphNode(3)";
"ProgramGraphNode(5)" -> "ProgramGraphNode(4)";
}
"""
    assert dot_representation == graph
