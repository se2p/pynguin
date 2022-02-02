#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

import pynguin.analyses.controlflow.controldependencegraph as cdt
import pynguin.analyses.controlflow.programgraph as pg
from pynguin.instrumentation.instrumentation import (
    BranchCoverageInstrumentation,
    InstrumentationTransformer,
)
from pynguin.testcase.execution import ExecutionTracer


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


def small_fixture(x, y):  # pragma: no cover
    if x <= y:
        if x == y:
            print("Some output")
        if x > 0:
            if y == 17:
                return True
    return False


@pytest.mark.parametrize(
    "node,deps",
    [
        pytest.param(
            pg.ProgramGraphNode(index=5),
            {cdt.ControlDependency(0, True)},
            id="return True depends on y == 17",
        ),
        pytest.param(pg.ProgramGraphNode(index=0), set(), id="Entry has no dependency"),
        pytest.param(
            pg.ProgramGraphNode(index=6),
            {
                cdt.ControlDependency(predicate_id=0, branch_value=False),
                cdt.ControlDependency(predicate_id=2, branch_value=False),
                cdt.ControlDependency(predicate_id=3, branch_value=False),
            },
            id="return False depends on all False branches",
        ),
    ],
)
def test_get_control_dependencies(node, deps):
    tracer = ExecutionTracer()
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    transformer.instrument_module(small_fixture.__code__)
    cdg = list(tracer.get_known_data().existing_code_objects.values())[0].cdg
    assert set(cdg.get_control_dependencies(node)) == deps


@pytest.mark.parametrize("node", ["foobar", None])
def test_get_control_dependencies_asserts(node):
    tracer = ExecutionTracer()
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    transformer.instrument_module(small_fixture.__code__)
    cdg = list(tracer.get_known_data().existing_code_objects.values())[0].cdg
    with pytest.raises(AssertionError):
        cdg.get_control_dependencies(node)
