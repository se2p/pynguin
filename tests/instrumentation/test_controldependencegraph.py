#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
import sys

from contextlib import contextmanager

import pytest

from pynguin.instrumentation.controlflow import ArtificialNode
from pynguin.instrumentation.controlflow import ControlDependenceGraph
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import BranchCoverageInstrumentation
from tests.testutils import instrument_function


def test_integration(small_control_flow_graph):
    control_dependence_graph = ControlDependenceGraph.compute(small_control_flow_graph)
    dot_representation = control_dependence_graph.dot
    graph = """strict digraph  {
"BasicBlockNode(0)
";
"BasicBlockNode(1)
";
"BasicBlockNode(2)
";
"BasicBlockNode(3)
";
"BasicBlockNode(4)
";
"BasicBlockNode(5)
";
"ArtificialNode(AUGMENTED_ENTRY)";
"BasicBlockNode(4)
" -> "BasicBlockNode(3)
";
"BasicBlockNode(4)
" -> "BasicBlockNode(2)
";
"ArtificialNode(AUGMENTED_ENTRY)" -> "BasicBlockNode(0)
";
"ArtificialNode(AUGMENTED_ENTRY)" -> "BasicBlockNode(5)
";
"ArtificialNode(AUGMENTED_ENTRY)" -> "BasicBlockNode(4)
";
"ArtificialNode(AUGMENTED_ENTRY)" -> "BasicBlockNode(1)
";
}"""
    assert dot_representation == graph
    assert isinstance(control_dependence_graph.entry_node, ArtificialNode)


@pytest.fixture
def small_fixture():
    def func(x, y):  # pragma: no cover
        if x <= y:  # predicate 0
            if x == y:  # predicate 1
                pass
            if x > 0 and y == 17:  # predicate 2 and 3
                return True
        return False

    return func


@pytest.mark.parametrize(
    "node_index,expected_deps",
    [
        pytest.param(
            0,
            set(),
            id="Node 'if x <= y:' directly depends on no predicate",
        ),
        pytest.param(
            1,
            {
                (0, True),
            },
            id="Node 'if x == y:' directly depends on predicate 'x <= y' being True",
        ),
        pytest.param(
            2,
            {
                (1, True),
            },
            id="Node 'pass' directly depends on predicate 'x == y' being True",
        ),
        pytest.param(
            3,
            {
                (0, True),
            },
            id="Node 'if x > 0' directly depends on predicate 'x <= y' being True",
            # We don't care about predicate x == y here, because we can reach
            # this statement in both cases
        ),
        pytest.param(
            4,
            {
                (2, True),
            },
            id="Node 'and y == 17:' directly depends on predicate 'x > 0' being True",
        ),
        pytest.param(
            5,
            {
                (3, True),
            },
            id="Node 'return True' directly depends on predicate 'y == 17' being True",
        ),
        pytest.param(
            6,
            {
                (0, False),
                (2, False),
                (3, False),
            },
            id="Node 'return False' directly depends on any predicate being False",
        ),
    ],
)
def test_get_control_dependencies(
    node_index, expected_deps, subject_properties: SubjectProperties, small_fixture
):
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(
        subject_properties,
        [adapter],
        enable_inline_pragma_no_cover=False,
    )
    instrument_function(transformer, small_fixture)
    cdg = next(iter(subject_properties.existing_code_objects.values())).cdg
    node = cdg.get_basic_block_node(node_index)

    nodes_predicates = {
        meta_data.node: predicate_id
        for predicate_id, meta_data in subject_properties.existing_predicates.items()
    }
    deps = {
        (nodes_predicates[dep.node], dep.branch_value) for dep in cdg.get_control_dependencies(node)
    }
    assert expected_deps == deps


@pytest.mark.parametrize("node", ["foobar", None])
def test_get_control_dependencies_asserts(
    node, subject_properties: SubjectProperties, small_fixture
):
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(
        subject_properties,
        [adapter],
        enable_inline_pragma_no_cover=False,
    )
    instrument_function(transformer, small_fixture)
    cdg = next(iter(subject_properties.existing_code_objects.values())).cdg
    with pytest.raises(AssertionError):
        cdg.get_control_dependencies(node)


@contextmanager
def dummy_context():  # pragma: no cover
    yield


@pytest.fixture
def long_fixture():
    def func(x, y):  # pragma: no cover
        if x < y:
            z = x + y

        with dummy_context():
            z = x

        if z > 0:
            return 4

        return 9

    return func


if sys.version_info >= (3, 12):
    test_is_control_dependent_on_root_params = [
        pytest.param(0, True),
        pytest.param(1, False),
        pytest.param(2, True),
        pytest.param(3, True),
        pytest.param(4, True),
        pytest.param(5, False),
        pytest.param(6, False),
        pytest.param(7, True),
        pytest.param(8, True),
        pytest.param(9, False),
        pytest.param(10, False),
        pytest.param(11, True),
    ]
elif sys.version_info >= (3, 11):
    test_is_control_dependent_on_root_params = [
        pytest.param(0, True),
        pytest.param(1, False),
        pytest.param(2, True),
        pytest.param(3, True),
        pytest.param(4, True),
        pytest.param(5, True),
        pytest.param(6, False),
        pytest.param(7, True),
        pytest.param(8, False),
        pytest.param(9, False),
        pytest.param(10, True),
        pytest.param(11, False),
        pytest.param(12, False),
    ]
else:
    test_is_control_dependent_on_root_params = [
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
    ]


@pytest.mark.parametrize(
    "node_index,expected_dependant",
    test_is_control_dependent_on_root_params,
)
def test_is_control_dependent_on_root(
    node_index, expected_dependant, subject_properties: SubjectProperties, long_fixture
):
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(
        subject_properties,
        [adapter],
        enable_inline_pragma_no_cover=False,
    )
    instrument_function(transformer, long_fixture)
    cdg = next(iter(subject_properties.existing_code_objects.values())).cdg
    node = cdg.get_basic_block_node(node_index)

    dependant = cdg.is_control_dependent_on_root(node)

    assert expected_dependant == dependant


@pytest.fixture
def yield_fun_module():
    yield_fun_module = importlib.import_module("tests.fixtures.programgraph.yield_fun")
    return importlib.reload(yield_fun_module)


def test_yield_instrumented(subject_properties: SubjectProperties, yield_fun_module):
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, yield_fun_module.yield_fun)
    cdg = next(iter(subject_properties.existing_code_objects.values())).cdg
    assert cdg


def test_yield(yield_control_flow_graph):
    cdg = ControlDependenceGraph.compute(yield_control_flow_graph)
    assert cdg.entry_node is not None
