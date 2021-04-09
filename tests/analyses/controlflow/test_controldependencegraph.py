#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pynguin.analyses.controlflow.controldependencegraph as cdt


def test_integration(small_control_flow_graph):
    control_dependence_graph = cdt.ControlDependenceGraph.compute(
        small_control_flow_graph
    )
    dot_representation = control_dependence_graph.dot
    graph = """strict digraph  {
"ProgramGraphNode(2)";
"ProgramGraphNode(4)";
"ProgramGraphNode(6)";
"ProgramGraphNode(-9223372036854775807)";
"ProgramGraphNode(3)";
"ProgramGraphNode(5)";
"ProgramGraphNode(0)";
"ProgramGraphNode(-9223372036854775807)" -> "ProgramGraphNode(0)";
"ProgramGraphNode(-9223372036854775807)" -> "ProgramGraphNode(6)";
"ProgramGraphNode(-9223372036854775807)" -> "ProgramGraphNode(5)";
"ProgramGraphNode(-9223372036854775807)" -> "ProgramGraphNode(2)";
"ProgramGraphNode(5)" -> "ProgramGraphNode(3)";
"ProgramGraphNode(5)" -> "ProgramGraphNode(4)";
}
"""
    assert dot_representation == graph
    assert control_dependence_graph.entry_node.is_artificial
