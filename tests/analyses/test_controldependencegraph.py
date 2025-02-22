#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from pynguin.analyses.controlflow import ControlDependenceGraph
from pynguin.analyses.controlflow import ControlDependency
from pynguin.analyses.controlflow import ProgramGraphNode
from pynguin.instrumentation.instrumentation import BranchCoverageInstrumentation
from pynguin.instrumentation.instrumentation import InstrumentationTransformer
from pynguin.instrumentation.tracer import ExecutionTracer
from tests.fixtures.programgraph.yield_fun import yield_fun


def test_integration(small_control_flow_graph):
    control_dependence_graph = ControlDependenceGraph.compute(small_control_flow_graph)
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
}"""
    assert dot_representation == graph
    assert control_dependence_graph.entry_node.is_artificial


def small_fixture(x, y):  # pragma: no cover
    if x <= y:
        if x == y:
            pass
        if x > 0 and y == 17:
            return True
    return False


@pytest.mark.parametrize(
    "node,deps",
    [
        pytest.param(
            ProgramGraphNode(index=5),
            {ControlDependency(0, True)},  # noqa: FBT003
            id="return True depends on y == 17",
        ),
        pytest.param(ProgramGraphNode(index=0), set(), id="Entry has no dependency"),
        pytest.param(
            ProgramGraphNode(index=6),
            {
                ControlDependency(predicate_id=0, branch_value=False),
                ControlDependency(predicate_id=2, branch_value=False),
                ControlDependency(predicate_id=3, branch_value=False),
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
    cdg = next(iter(tracer.get_subject_properties().existing_code_objects.values())).cdg
    assert set(cdg.get_control_dependencies(node)) == deps


@pytest.mark.parametrize("node", ["foobar", None])
def test_get_control_dependencies_asserts(node):
    tracer = ExecutionTracer()
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    transformer.instrument_module(small_fixture.__code__)
    cdg = next(iter(tracer.get_subject_properties().existing_code_objects.values())).cdg
    with pytest.raises(AssertionError):
        cdg.get_control_dependencies(node)


def test_yield_instrumented():
    tracer = ExecutionTracer()
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    transformer.instrument_module(yield_fun.__code__)
    cdg = next(iter(tracer.get_subject_properties().existing_code_objects.values())).cdg
    assert cdg


def test_yield(yield_control_flow_graph):
    cdg = ControlDependenceGraph.compute(yield_control_flow_graph)
    assert cdg.entry_node is not None
