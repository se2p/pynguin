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

from pynguin.configuration import ToCoverConfiguration
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
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=False),
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
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=False),
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
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=False),
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


@pytest.fixture
def covered_branches_module():
    covered_branches_module = importlib.import_module(
        "tests.fixtures.instrumentation.covered_branches"
    )
    return importlib.reload(covered_branches_module)


if sys.version_info >= (3, 14):
    no_cover_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 0),
        (ArtificialNode.AUGMENTED_ENTRY, 3),
    }
    no_cover_while_id = "while initialisation (0) and 'return x' (3) depend on root"
    no_cover_if_in_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 0),
        (ArtificialNode.AUGMENTED_ENTRY, 1),
        (1, 1),
        (1, 4),
        (ArtificialNode.AUGMENTED_ENTRY, 5),
    }
    no_cover_if_in_while_id = (
        "'print(-x)' (4) and 'while (x > 0)' (1) depend on 'while (x > 0)' (1) and"
        "while initialisation (0), 'while (x > 0)' (1) and 'return x' (5) depend on root"
    )
    no_cover_case_only_catchall_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 2),
        (ArtificialNode.AUGMENTED_ENTRY, 3),
    }
    no_cover_case_only_catchall_id = "'a = 0' (2) and 'return str(a)' (3) depend on root"
elif sys.version_info >= (3, 13):
    no_cover_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 3),
    }
    no_cover_while_id = "'return x' (3) depends on root"
    no_cover_if_in_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 0),
        (0, 3),
        (0, 4),
        (4, 3),
        (4, 4),
        (4, 5),
        (ArtificialNode.AUGMENTED_ENTRY, 6),
    }
    no_cover_if_in_while_id = (
        "'print(-x)' (3) and 'while (x > 0)' (4) depend on 'while (x > 0)' (0, 4) and"
        "'while (x > 0)' (0) and 'return x' (6) depend on root"
    )
    no_cover_case_only_catchall_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 2),
        (ArtificialNode.AUGMENTED_ENTRY, 3),
    }
    no_cover_case_only_catchall_id = "'a = 0' (2) and 'return str(a)' (3) depend on root"
elif sys.version_info >= (3, 12):
    no_cover_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 3),
    }
    no_cover_while_id = "'return x' (3) depends on root"
    no_cover_if_in_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 0),
        (0, 3),
        (0, 4),
        (4, 3),
        (4, 4),
        (4, 5),
        (ArtificialNode.AUGMENTED_ENTRY, 6),
    }
    no_cover_if_in_while_id = (
        "'print(-x)' (3) and 'while (x > 0)' (4) depend on 'while (x > 0)' (0, 4) and"
        "'while (x > 0)' (0) and 'return x' (6) depend on root"
    )
    no_cover_case_only_catchall_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 1),
        (ArtificialNode.AUGMENTED_ENTRY, 2),
    }
    no_cover_case_only_catchall_id = "'a = 0' (1) and 'return str(a)' (2) depend on root"
elif sys.version_info >= (3, 11):
    no_cover_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 2),
    }
    no_cover_while_id = "'return x' (2) depends on root"
    no_cover_if_in_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 0),
        (0, 3),
        (0, 4),
        (4, 3),
        (4, 4),
        (ArtificialNode.AUGMENTED_ENTRY, 5),
    }
    no_cover_if_in_while_id = (
        "'print(-x)' (3) and 'while (x > 0)' (4) depend on 'while (x > 0)' (0, 4) and"
        "'while (x > 0)' (0) and 'return x' (5) depend on root"
    )
    no_cover_case_only_catchall_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 2),
        (ArtificialNode.AUGMENTED_ENTRY, 3),
    }
    no_cover_case_only_catchall_id = "'a = 0' (2) and 'return str(a)' (3) depend on root"
else:
    no_cover_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 2),
    }
    no_cover_while_id = "'return x' (2) depends on root"
    no_cover_if_in_while_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 0),
        (0, 3),
        (0, 4),
        (4, 3),
        (4, 4),
        (ArtificialNode.AUGMENTED_ENTRY, 5),
    }
    no_cover_if_in_while_id = (
        "'print(-x)' (3) and 'while (x > 0)' (4) depend on 'while (x > 0)' (0, 4) and"
        "'while (x > 0)' (0) and 'return x' (5) depend on root"
    )
    no_cover_case_only_catchall_values = {
        (ArtificialNode.AUGMENTED_ENTRY, 1),
        (ArtificialNode.AUGMENTED_ENTRY, 2),
    }
    no_cover_case_only_catchall_id = "'a = 0' (1) and 'return str(a)' (2) depend on root"


@pytest.mark.parametrize(
    "function_name, expected_deps",
    [
        pytest.param(
            "no_cover_if",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 2),
            },
            id="'return y' (2) depends on root",
        ),
        pytest.param(
            "no_cover_elif",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 0),
                (0, 1),
                (0, 4),
            },
            id="'return x' (1) and 'return 0' (4) depend on 'if x > 0' (0) and "
            "'if x > 0' (0) depends on root",
        ),
        pytest.param(
            "no_cover_else",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 1),
            },
            id="'return x' (1) depends on root",
        ),
        pytest.param(
            "no_cover_nesting_if",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 4),
            },
            id="'return 0' (4) depends on root",
        ),
        pytest.param(
            "no_cover_nested_if",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 0),
                (0, 3),
                (0, 4),
            },
            id="'return y' (3) depend on 'if x > 0' (0) and "
            "'if x > 0' (0) and 'return 0' (4) depend on root",
        ),
        pytest.param(
            "no_cover_while",
            no_cover_while_values,
            id=no_cover_while_id,
        ),
        pytest.param(
            "no_cover_if_in_while",
            no_cover_if_in_while_values,
            id=no_cover_if_in_while_id,
        ),
        pytest.param(
            "no_cover_for",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 3),
            },
            id="'return x' (3) depends on root",
        ),
        pytest.param(
            "no_cover_for_else",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 2),
                (ArtificialNode.AUGMENTED_ENTRY, 3),
            },
            id="'print(i)' (2), 'return x' (3) depend on root",
        ),
        pytest.param(
            "no_cover_match",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 3),
            },
            id="'return str(a) * 2' (3) depends on root",
        ),
        pytest.param(
            "no_cover_case",
            {
                (ArtificialNode.AUGMENTED_ENTRY, 2),
                (2, 3),
                (2, 4),
            },
            id="'return 2' (3) and 'return 0' (4) depend on 'case 2' (2) and "
            "'case 2' (2) depends on root",
        ),
        pytest.param(
            "no_cover_case_only_catchall",
            no_cover_case_only_catchall_values,
            id=no_cover_case_only_catchall_id,
        ),
    ],
)
def test_no_cover(
    subject_properties: SubjectProperties,
    covered_branches_module,
    function_name,
    expected_deps,
):
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, getattr(covered_branches_module, function_name))
    cdg = next(iter(subject_properties.existing_code_objects.values())).cdg
    actual_deps = {
        (
            node if isinstance(node, ArtificialNode) else node.index,
            succ if isinstance(succ, ArtificialNode) else succ.index,
        )
        for (node, succ) in cdg.graph.edges
    }

    assert actual_deps == expected_deps, cdg.dot
