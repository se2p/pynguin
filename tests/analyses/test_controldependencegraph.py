#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from contextlib import contextmanager

import pytest

from pynguin.analyses.controlflow import ControlDependenceGraph
from pynguin.analyses.controlflow import ProgramGraphNode
from pynguin.instrumentation.injection import BranchCoverageInjectionInstrumentation
from pynguin.instrumentation.injection import InjectionInstrumentationTransformer
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.instrumentation.tracer import InstrumentationExecutionTracer
from tests.fixtures.programgraph.yield_fun import yield_fun
from tests.utils.version import only_3_10


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


@only_3_10
@pytest.mark.parametrize(
    "node,expected_deps",
    [
        pytest.param(
            ProgramGraphNode(index=5),
            {(0, True)},
            id="return True depends on y == 17",
        ),
        pytest.param(ProgramGraphNode(index=0), set(), id="Entry has no dependency"),
        pytest.param(
            ProgramGraphNode(index=6),
            {
                (0, False),
                (2, False),
                (3, False),
            },
            id="return False depends on all False branches",
        ),
    ],
)
def test_get_control_dependencies(node, expected_deps):
    tracer = ExecutionTracer()
    instrumentation_tracer = InstrumentationExecutionTracer(tracer)
    adapter = BranchCoverageInjectionInstrumentation(instrumentation_tracer)
    transformer = InjectionInstrumentationTransformer(instrumentation_tracer, [adapter])
    transformer.instrument_module(small_fixture.__code__)
    subject_properties = tracer.get_subject_properties()
    cdg = next(iter(subject_properties.existing_code_objects.values())).cdg
    nodes_predicates = {
        meta_data.node: predicate_id
        for predicate_id, meta_data in subject_properties.existing_predicates.items()
    }
    deps = {
        (nodes_predicates[dep.node], dep.branch_value) for dep in cdg.get_control_dependencies(node)
    }
    assert expected_deps == deps


@only_3_10
@pytest.mark.parametrize("node", ["foobar", None])
def test_get_control_dependencies_asserts(node):
    tracer = ExecutionTracer()
    instrumentation_tracer = InstrumentationExecutionTracer(tracer)
    adapter = BranchCoverageInjectionInstrumentation(instrumentation_tracer)
    transformer = InjectionInstrumentationTransformer(instrumentation_tracer, [adapter])
    transformer.instrument_module(small_fixture.__code__)
    cdg = next(iter(tracer.get_subject_properties().existing_code_objects.values())).cdg
    with pytest.raises(AssertionError):
        cdg.get_control_dependencies(node)


@contextmanager
def dummy_context():  # pragma: no cover
    yield


def long_fixture(x, y):  # pragma: no cover
    if x < y:
        z = x + y

    with dummy_context():
        z = x

    if z > 0:
        return 4

    return 9


@only_3_10
@pytest.mark.parametrize(
    "node_index,expected_dependant",
    [
        pytest.param(0, True),
        pytest.param(1, False),
        pytest.param(2, True),
        pytest.param(3, True),
        pytest.param(4, True),
        pytest.param(5, False),
        pytest.param(6, False),
        pytest.param(7, True),
        pytest.param(8, False),
        pytest.param(9, False),
    ],
)
def test_is_control_dependent_on_root(node_index, expected_dependant):
    tracer = ExecutionTracer()
    instrumentation_tracer = InstrumentationExecutionTracer(tracer)
    adapter = BranchCoverageInjectionInstrumentation(instrumentation_tracer)
    transformer = InjectionInstrumentationTransformer(instrumentation_tracer, [adapter])
    transformer.instrument_module(long_fixture.__code__)
    subject_properties = tracer.get_subject_properties()
    cdg = next(iter(subject_properties.existing_code_objects.values())).cdg

    node = None
    for n in cdg.nodes:
        if n.index == node_index:
            node = n
            break

    assert node is not None

    dependant = cdg.is_control_dependent_on_root(
        node,
        {metadata.node for metadata in subject_properties.existing_predicates.values()},
    )

    assert expected_dependant == dependant


@only_3_10
def test_yield_instrumented():
    tracer = ExecutionTracer()
    instrumentation_tracer = InstrumentationExecutionTracer(tracer)
    adapter = BranchCoverageInjectionInstrumentation(instrumentation_tracer)
    transformer = InjectionInstrumentationTransformer(instrumentation_tracer, [adapter])
    transformer.instrument_module(yield_fun.__code__)
    cdg = next(iter(tracer.get_subject_properties().existing_code_objects.values())).cdg
    assert cdg


def test_yield(yield_control_flow_graph):
    cdg = ControlDependenceGraph.compute(yield_control_flow_graph)
    assert cdg.entry_node is not None
