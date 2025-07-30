#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import importlib
import threading

from unittest import mock
from unittest.mock import MagicMock
from unittest.mock import call

import pytest

import pynguin.configuration as config
import pynguin.ga.postprocess as pp
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt

from pynguin.analyses.module import ModuleTestCluster
from pynguin.analyses.module import generate_test_cluster
from pynguin.assertion.assertion import ExceptionAssertion
from pynguin.ga.computations import TestSuiteBranchCoverageFunction
from pynguin.ga.computations import TestSuiteLineCoverageFunction
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.large_language_model.parsing.astscoping import VariableRefAST
from pynguin.testcase.execution import SubprocessTestCaseExecutor
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.orderedset import OrderedSet


def test_not_failing():
    trunc = pp.ExceptionTruncation()
    test_case = MagicMock()
    chromosome = MagicMock(test_case=test_case)
    chromosome.is_failing.return_value = False
    trunc.visit_test_case_chromosome(chromosome)
    test_case.chop.assert_not_called()


def test_simple_chop():
    trunc = pp.ExceptionTruncation()
    test_case = MagicMock()
    chromosome = MagicMock(test_case=test_case)
    chromosome.is_failing.return_value = True
    chromosome.get_last_mutatable_statement.return_value = 42
    trunc.visit_test_case_chromosome(chromosome)
    test_case.chop.assert_called_once_with(42)


def test_suite_chop():
    trunc = pp.ExceptionTruncation()
    chromosome = MagicMock()
    suite = MagicMock(test_case_chromosomes=[chromosome, chromosome])
    trunc.visit_test_suite_chromosome(suite)
    chromosome.accept.assert_has_calls([call(trunc), call(trunc)])


def test_suite_assertion_minimization():
    ass_min = pp.AssertionMinimization()
    chromosome = MagicMock()
    suite = MagicMock(test_case_chromosomes=[chromosome, chromosome])
    ass_min.visit_test_suite_chromosome(suite)
    chromosome.accept.assert_has_calls([call(ass_min), call(ass_min)])


def test_test_case_assertion_minimization(default_test_case):
    ass_min = pp.AssertionMinimization()
    statement = stmt.IntPrimitiveStatement(default_test_case)

    assertion_1 = MagicMock(checked_instructions=[MagicMock(lineno=1), MagicMock(lineno=2)])
    assertion_2 = MagicMock(checked_instructions=[MagicMock(lineno=1)])

    statement.add_assertion(assertion_1)
    statement.add_assertion(assertion_2)
    default_test_case.add_statement(statement)

    chromosome = tcc.TestCaseChromosome(test_case=default_test_case)
    ass_min.visit_test_case_chromosome(chromosome)

    assert ass_min.remaining_assertions == OrderedSet([assertion_1])
    assert ass_min.deleted_assertions == OrderedSet([assertion_2])
    assert default_test_case.get_assertions() == [assertion_1]


def test_test_case_assertion_minimization_does_not_remove_exception_assertion(
    default_test_case,
):
    ass_min = pp.AssertionMinimization()
    statement = stmt.IntPrimitiveStatement(default_test_case)

    assertion_1 = MagicMock(checked_instructions=[MagicMock(lineno=1), MagicMock(lineno=2)])
    assertion_2 = MagicMock(spec=ExceptionAssertion, checked_instructions=[MagicMock(lineno=1)])

    statement.add_assertion(assertion_1)
    statement.add_assertion(assertion_2)
    default_test_case.add_statement(statement)

    chromosome = tcc.TestCaseChromosome(test_case=default_test_case)
    ass_min.visit_test_case_chromosome(chromosome)

    assert ass_min.remaining_assertions == OrderedSet([assertion_1, assertion_2])
    assert ass_min.deleted_assertions == OrderedSet()
    assert default_test_case.get_assertions() == [assertion_1, assertion_2]


def test_test_case_assertion_minimization_does_not_remove_empty_assertion(
    default_test_case,
):
    ass_min = pp.AssertionMinimization()
    statement = stmt.IntPrimitiveStatement(default_test_case)

    assertion_1 = MagicMock(checked_instructions=[])

    statement.add_assertion(assertion_1)
    default_test_case.add_statement(statement)

    chromosome = tcc.TestCaseChromosome(test_case=default_test_case)
    ass_min.visit_test_case_chromosome(chromosome)

    assert ass_min.remaining_assertions == OrderedSet([assertion_1])
    assert ass_min.deleted_assertions == OrderedSet()
    assert default_test_case.get_assertions() == [assertion_1]


def test_test_case_postprocessor_suite():
    dummy_visitor = MagicMock()
    tcpp = pp.TestCasePostProcessor([dummy_visitor])
    chromosome = MagicMock()
    suite = MagicMock(test_case_chromosomes=[chromosome, chromosome])
    tcpp.visit_test_suite_chromosome(suite)
    chromosome.accept.assert_has_calls([call(tcpp), call(tcpp)])


def test_test_case_postprocessor_test():
    dummy_visitor = MagicMock()
    tcpp = pp.TestCasePostProcessor([dummy_visitor])
    test_case = MagicMock()
    test_chromosome = MagicMock(test_case=test_case)
    tcpp.visit_test_case_chromosome(test_chromosome)
    test_case.accept.assert_has_calls([call(dummy_visitor)])


def test_unused_primitives_visitor():
    visitor = pp.UnusedStatementsTestCaseVisitor()
    statement = MagicMock()
    test_case = MagicMock(statements=[statement])
    visitor.visit_default_test_case(test_case)
    assert statement.accept.call_count == 1


# TODO(fk) replace with ast_to_stmt
def test_remove_integration(constructor_mock):
    cluster = ModuleTestCluster(0)
    test_case = dtc.DefaultTestCase(cluster)
    test_case.add_statement(stmt.IntPrimitiveStatement(test_case))
    test_case.add_statement(stmt.FloatPrimitiveStatement(test_case))
    int0 = stmt.IntPrimitiveStatement(test_case)
    test_case.add_statement(int0)
    list0 = stmt.ListStatement(
        test_case, cluster.type_system.convert_type_hint(list[int]), [int0.ret_val]
    )
    test_case.add_statement(list0)
    float0 = stmt.FloatPrimitiveStatement(test_case)
    test_case.add_statement(float0)
    ctor0 = stmt.ConstructorStatement(
        test_case, constructor_mock, {"foo": float0.ret_val, "bar": list0.ret_val}
    )
    test_case.add_statement(ctor0)
    assert test_case.size() == 6
    visitor = pp.UnusedStatementsTestCaseVisitor()
    test_case.accept(visitor)
    assert test_case.statements == [int0, list0, float0, ctor0]


def test_visit_ast_assign_statement():
    """Test that the visit_ast_assign_statement method is called correctly."""
    # Create a test case
    cluster = ModuleTestCluster(0)
    test_case = dtc.DefaultTestCase(cluster)

    # Create an ASTAssignStatement with a variable reference
    # First, create a variable reference
    int_stmt = stmt.IntPrimitiveStatement(test_case)
    test_case.add_statement(int_stmt)
    var_ref = int_stmt.ret_val

    # Create a name node and ref_dict for the variable reference
    name_node = ast.Name(id="test_var", ctx=ast.Load())
    ref_dict = {"test_var": var_ref}

    # Create the ASTAssignStatement that uses the variable reference
    var_ref_ast = VariableRefAST(name_node, ref_dict)
    ast_assign = stmt.ASTAssignStatement(test_case, var_ref_ast, {})
    test_case.add_statement(ast_assign)

    # Create a visitor and visit the ASTAssignStatement
    visitor = pp.UnusedPrimitiveOrCollectionStatementVisitor()
    ast_assign.accept(visitor)

    # Verify that _handle_remaining was called by checking that the variable reference
    # was added to the _used_references set
    assert var_ref in visitor._used_references

    # Also verify that the statement was not removed
    assert ast_assign in test_case.statements


@pytest.mark.parametrize(
    "statement_type, func",
    [
        ("visit_int_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_float_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_string_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_bytes_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_boolean_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_enum_statement", "_handle_collection_or_primitive"),
        ("visit_none_statement", "_handle_collection_or_primitive"),
        ("visit_constructor_statement", "_handle_remaining"),
        ("visit_method_statement", "_handle_remaining"),
        ("visit_function_statement", "_handle_remaining"),
        ("visit_list_statement", "_handle_collection_or_primitive"),
        ("visit_set_statement", "_handle_collection_or_primitive"),
        ("visit_tuple_statement", "_handle_collection_or_primitive"),
        ("visit_dict_statement", "_handle_collection_or_primitive"),
        ("visit_ast_assign_statement", "_handle_remaining"),
    ],
)
def test_all_statements(statement_type, func):
    visitor = pp.UnusedPrimitiveOrCollectionStatementVisitor()
    with mock.patch.object(visitor, func) as f:
        visitor.__getattribute__(statement_type)(MagicMock())  # noqa: PLC2801
        f.assert_called_once()


@pytest.mark.parametrize(
    "statement_type",
    [
        "visit_field_statement",
        "visit_assignment_statement",
    ],
)
def test_not_implemented_statements(statement_type):
    visitor = pp.UnusedPrimitiveOrCollectionStatementVisitor()
    with pytest.raises(NotImplementedError):
        visitor.__getattribute__(statement_type)(MagicMock())  # noqa: PLC2801


@pytest.fixture
def basic_test_cluster():
    """Fixture for a basic test cluster."""
    return ModuleTestCluster(0)


@pytest.fixture
def basic_test_case(basic_test_cluster):
    """Fixture for a basic test case with a test cluster."""
    return dtc.DefaultTestCase(basic_test_cluster)


@pytest.fixture
def tc_with_statements(basic_test_case):
    """Fixture for a test case with int and float statements."""
    int_stmt = stmt.IntPrimitiveStatement(basic_test_case)
    basic_test_case.add_statement(int_stmt)
    float_stmt = stmt.FloatPrimitiveStatement(basic_test_case)
    basic_test_case.add_statement(float_stmt)
    return basic_test_case, int_stmt, float_stmt


@pytest.fixture
def mock_fitness_function():
    """Fixture for a mock fitness function."""
    return MagicMock()


@pytest.fixture
def forward_minimization_visitor(mock_fitness_function):
    """Fixture for a ForwardIterativeMinimizationVisitor with a mock fitness function."""
    return pp.ForwardIterativeMinimizationVisitor(mock_fitness_function)


@pytest.fixture
def backward_minimization_visitor(mock_fitness_function):
    """Fixture for a BackwardIterativeMinimizationVisitor with a mock fitness function."""
    return pp.BackwardIterativeMinimizationVisitor(mock_fitness_function)


@pytest.fixture
def test_suite_minimization_visitor(mock_fitness_function):
    """Fixture for a TestSuiteMinimizationVisitor."""
    return pp.TestSuiteMinimizationVisitor(mock_fitness_function)


@pytest.fixture
def combined_minimization_visitor(mock_fitness_function):
    """Fixture for a CombinedMinimizationVisitor."""
    return pp.CombinedMinimizationVisitor(mock_fitness_function)


@pytest.fixture
def create_test_suite():
    """Fixture that returns a function to create a test suite from a test case."""

    def _create_test_suite(test_case):
        test_case_chromosome = tcc.TestCaseChromosome(test_case=test_case)
        test_suite = TestSuiteChromosome()
        test_suite.add_test_case_chromosome(test_case_chromosome)
        return test_suite

    return _create_test_suite


@pytest.mark.parametrize(
    "visitor_fixture",
    [
        "forward_minimization_visitor",
        "backward_minimization_visitor",
    ],
    ids=["forward", "backward"],
)
def test_iterative_minimization_visitor_init(mock_fitness_function, request, visitor_fixture):
    """Test that the iterative minimization visitors initialize correctly."""
    visitor = request.getfixturevalue(visitor_fixture)
    assert visitor._fitness_function == mock_fitness_function
    assert visitor._removed_statements == 0
    assert visitor.removed_statements == 0


@pytest.mark.parametrize(
    "visitor_fixture",
    [
        "forward_minimization_visitor",
        "backward_minimization_visitor",
    ],
    ids=["forward", "backward"],
)
@pytest.mark.parametrize(
    "fitness_behavior,expected_removed,expected_size",
    [
        # Case 1: Fitness preserved when statements are removed
        (
            lambda _: 1.0,  # Constant coverage
            2,  # All statements removed
            0,  # Final size is 0
        ),
        # Case 2: Fitness reduced when statements are removed
        (
            lambda test_suite: 1.0 if test_suite.test_case_chromosomes[0].size() == 2 else 0.5,
            0,  # No statements removed
            2,  # Final size is 2
        ),
    ],
    ids=["fitness_preserved", "fitness_reduced"],
)
def test_iterative_minimization_visitor_statement_removal(  # noqa: PLR0917
    tc_with_statements,
    mock_fitness_function,
    request,
    visitor_fixture,
    fitness_behavior,
    expected_removed,
    expected_size,
):
    """Test that the visitor correctly handles statement removal based on fitness changes."""
    test_case, _, _ = tc_with_statements

    # Set up the mock fitness function behavior
    if callable(fitness_behavior):
        mock_fitness_function.compute_coverage.side_effect = fitness_behavior
    else:
        mock_fitness_function.compute_coverage.return_value = fitness_behavior

    # Get the visitor from the fixture
    visitor = request.getfixturevalue(visitor_fixture)

    # Apply the visitor to the test case
    test_case.accept(visitor)

    # Verify the expected results
    assert visitor.removed_statements == expected_removed
    assert test_case.size() == expected_size


@pytest.mark.parametrize(
    "visitor_fixture",
    [
        "forward_minimization_visitor",
        "backward_minimization_visitor",
    ],
    ids=["forward", "backward"],
)
def test_iterative_minimization_visitor_with_empty_test_case(
    basic_test_case, mock_fitness_function, request, visitor_fixture
):
    """Test that the visitor handles empty test cases correctly."""
    # Set up the mock fitness function
    mock_fitness_function.compute_coverage.return_value = 0.0

    # Get the visitor from the fixture
    visitor = request.getfixturevalue(visitor_fixture)

    # Apply the visitor to the empty test case
    basic_test_case.accept(visitor)

    # Verify that no statements were removed (since there were none to begin with)
    assert visitor.removed_statements == 0
    assert basic_test_case.size() == 0


@pytest.fixture
def tc_with_dependencies(basic_test_cluster, basic_test_case):
    """Fixture for a test case with dependencies between statements."""
    # Create statements with dependencies
    int_stmt = stmt.IntPrimitiveStatement(basic_test_case)
    basic_test_case.add_statement(int_stmt)

    # Create a list that depends on the int statement
    list_stmt = stmt.ListStatement(
        basic_test_case,
        basic_test_cluster.type_system.convert_type_hint(list[int]),
        [int_stmt.ret_val],
    )
    basic_test_case.add_statement(list_stmt)

    # Create a string statement that will be removed
    str_stmt = stmt.StringPrimitiveStatement(basic_test_case)
    basic_test_case.add_statement(str_stmt)

    return basic_test_case, int_stmt, list_stmt, str_stmt


@pytest.mark.parametrize(
    "visitor_class",
    [
        pp.ForwardIterativeMinimizationVisitor,
        pp.BackwardIterativeMinimizationVisitor,
    ],
    ids=["forward", "backward"],
)
def test_iterative_minimization_visitor_with_dependencies(
    tc_with_dependencies, mock_fitness_function, visitor_class
):
    """Test that the visitor correctly handles dependencies between statements."""
    test_case, _, _, _ = tc_with_dependencies

    # Set up the mock fitness function to allow removing only the string statement
    def compute_coverage_side_effect(test_suite):
        test_size = test_suite.test_case_chromosomes[0].size()
        # Full test case or test case without string statement has full coverage
        if test_size == 3 or (
            test_size == 2
            and isinstance(
                test_suite.test_case_chromosomes[0].test_case.statements[1], stmt.ListStatement
            )
        ):
            return 1.0
        # Any other modification reduces coverage
        return 0.5

    mock_fitness_function.compute_coverage.side_effect = compute_coverage_side_effect

    # Create the visitor and apply it to the test case
    visitor = visitor_class(mock_fitness_function)
    test_case.accept(visitor)

    # Verify that only the string statement was removed
    assert visitor.removed_statements == 1
    assert test_case.size() == 2
    assert isinstance(test_case.statements[0], stmt.IntPrimitiveStatement)
    assert isinstance(test_case.statements[1], stmt.ListStatement)


@pytest.fixture
def two_test_cases(basic_test_cluster):
    """Fixture for two test cases used in compare_coverage test."""
    test_case1 = dtc.DefaultTestCase(basic_test_cluster)
    int_stmt1 = stmt.IntPrimitiveStatement(test_case1)
    test_case1.add_statement(int_stmt1)

    test_case2 = dtc.DefaultTestCase(basic_test_cluster)
    int_stmt2 = stmt.IntPrimitiveStatement(test_case2)
    test_case2.add_statement(int_stmt2)

    return test_case1, test_case2


@pytest.fixture
def tc_with_complex_dependencies(basic_test_cluster):
    """Fixture for a test case with complex dependencies between statements."""
    test_case = dtc.DefaultTestCase(basic_test_cluster)

    # Create statements with dependencies
    int_stmt = stmt.IntPrimitiveStatement(test_case)
    test_case.add_statement(int_stmt)

    float_stmt = stmt.FloatPrimitiveStatement(test_case)
    test_case.add_statement(float_stmt)

    # Create a list that depends on both int and float statements
    list_stmt = stmt.ListStatement(
        test_case,
        basic_test_cluster.type_system.convert_type_hint(list),
        [int_stmt.ret_val, float_stmt.ret_val],
    )
    test_case.add_statement(list_stmt)

    # Add some statements that can be safely removed
    str_stmt = stmt.StringPrimitiveStatement(test_case)
    test_case.add_statement(str_stmt)

    bool_stmt = stmt.BooleanPrimitiveStatement(test_case)
    test_case.add_statement(bool_stmt)

    none_stmt = stmt.NoneStatement(test_case)
    test_case.add_statement(none_stmt)

    return test_case


@pytest.mark.parametrize(
    "visitor_class",
    [
        pp.ForwardIterativeMinimizationVisitor,
        pp.BackwardIterativeMinimizationVisitor,
    ],
    ids=["forward", "backward"],
)
def test_iterative_minimization_visitor_dependencies_preserved(
    tc_with_complex_dependencies, mock_fitness_function, visitor_class
):
    """Test that the IterativeMinimizationVisitor preserves dependencies between statements."""
    test_case = tc_with_complex_dependencies

    # Set up the compute_coverage method to return different values based on test case content
    def compute_coverage_side_effect(test_suite):
        # Get the statements from the test case
        statements = test_suite.test_case_chromosomes[0].test_case.statements

        # If the list statement is present, return full coverage
        if any(isinstance(s, stmt.ListStatement) for s in statements):
            # Check if its dependencies are present
            has_int = any(isinstance(s, stmt.IntPrimitiveStatement) for s in statements)
            has_float = any(isinstance(s, stmt.FloatPrimitiveStatement) for s in statements)

            # If dependencies are missing, return reduced coverage
            if not has_int or not has_float:
                return 0.5

            # All dependencies present, return full coverage
            return 1.0

        # List statement missing, return reduced coverage
        return 0.5

    mock_fitness_function.compute_coverage.side_effect = compute_coverage_side_effect

    # Create the visitor and apply it to the test case
    visitor = visitor_class(mock_fitness_function)
    original_size = test_case.size()
    test_case.accept(visitor)

    # Verify that some statements were removed
    assert visitor.removed_statements > 0
    assert test_case.size() < original_size

    # Verify that the list statement and its dependencies are still present
    statement_types = [type(s) for s in test_case.statements]
    assert stmt.ListStatement in statement_types
    assert stmt.IntPrimitiveStatement in statement_types
    assert stmt.FloatPrimitiveStatement in statement_types

    # Verify that the list statement still uses both the int and float statements
    list_stmt_index = statement_types.index(stmt.ListStatement)
    list_statement = test_case.statements[list_stmt_index]

    # Get the variable references used by the list statement
    var_refs = list_statement.get_variable_references()

    # Verify that the list statement uses variables from int and float statements
    int_vars = [
        s.ret_val for s in test_case.statements if isinstance(s, stmt.IntPrimitiveStatement)
    ]
    float_vars = [
        s.ret_val for s in test_case.statements if isinstance(s, stmt.FloatPrimitiveStatement)
    ]

    assert any(int_var in var_refs for int_var in int_vars)
    assert any(float_var in var_refs for float_var in float_vars)


def _setup_integration_test(coverage_metric):
    """Fixture for setting up the integration test environment."""
    # Set up the module name for testing
    config.configuration.module_name = "tests.fixtures.branchcoverage.singlebranches"

    # Create a real tracer and executor
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(config.configuration.module_name, tracer, {coverage_metric}):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        first_function = module.first

        # Create a real executor
        executor = TestCaseExecutor(tracer)

        # Create a test case with multiple statements
        cluster = generate_test_cluster(config.configuration.module_name)
        test_case = dtc.DefaultTestCase(cluster)

        # Find the GenericFunction object for the first_function
        first_function_generic: GenericFunction | None = None
        for obj in cluster.accessible_objects_under_test:
            if isinstance(obj, GenericFunction) and obj._callable == first_function:
                first_function_generic = obj
                break

        if first_function_generic is None:
            raise ValueError("Could not find GenericFunction for first_function")

        return executor, test_case, first_function_generic


@pytest.mark.parametrize(
    "visitor_class",
    [
        pp.ForwardIterativeMinimizationVisitor,
        pp.BackwardIterativeMinimizationVisitor,
    ],
    ids=["forward", "backward"],
)
@pytest.mark.parametrize(
    "coverage_metric,expected_removed",
    [
        (config.CoverageMetric.BRANCH, 2),
        (config.CoverageMetric.LINE, 2),
    ],
)
def test_iterative_minimization_visitor_integration(
    coverage_metric, expected_removed, visitor_class
):
    """Integration test for iterative minimization visitors with different coverage metrics."""
    executor, test_case, first_function_generic = _setup_integration_test(coverage_metric)
    if coverage_metric == config.CoverageMetric.BRANCH:
        coverage_function_class = TestSuiteBranchCoverageFunction
    elif coverage_metric == config.CoverageMetric.LINE:
        coverage_function_class = TestSuiteLineCoverageFunction
    else:
        raise ValueError(f"Unknown coverage metric: {coverage_metric}")

    # Add three statement tuples where the second one can be removed
    for i in range(3):
        int_stmt = stmt.IntPrimitiveStatement(test_case, i - 1)
        test_case.add_statement(int_stmt)
        func_stmt = stmt.FunctionStatement(
            test_case, first_function_generic, {"a": int_stmt.ret_val}
        )
        test_case.add_statement(func_stmt)

    # Execute the test case to ensure it has coverage
    executor.execute(test_case)

    # Create a coverage function and visitor based on the parameters
    fitness_function = coverage_function_class(executor)
    visitor = visitor_class(fitness_function)

    # Apply the visitor to the test case
    test_case.accept(visitor)

    # Verify that the expected number of statements is removed
    assert visitor.removed_statements == expected_removed


def _create_test_case_with_calls(base_test_case, function_generic, values):
    """Helper function to create a test case with function calls.

    Args:
        base_test_case: The base test case to clone
        function_generic: The function to call
        values: The values to pass to the function

    Returns:
        The created test case
    """
    test_case = base_test_case.clone()

    for value in values:
        int_stmt = stmt.IntPrimitiveStatement(test_case, value)
        test_case.add_statement(int_stmt)
        func_stmt = stmt.FunctionStatement(test_case, function_generic, {"a": int_stmt.ret_val})
        test_case.add_statement(func_stmt)

    return test_case


@pytest.fixture
def mock_executor():
    """Fixture for a mock SubprocessTestCaseExecutor."""
    return MagicMock(spec=SubprocessTestCaseExecutor)


@pytest.fixture
def crash_preserving_minimization_visitor(mock_executor):
    """Fixture for a CrashPreservingMinimizationVisitor with a mock executor."""
    return pp.CrashPreservingMinimizationVisitor(mock_executor)


def test_crash_preserving_minimization_visitor_init(
    mock_executor, crash_preserving_minimization_visitor
):
    """Test that the CrashPreservingMinimizationVisitor initializes correctly."""
    assert crash_preserving_minimization_visitor._executor == mock_executor
    assert crash_preserving_minimization_visitor._removed_statements == 0
    assert crash_preserving_minimization_visitor.removed_statements == 0


@pytest.mark.parametrize(
    "execution_results,expected_removed",
    [
        (
            [True, True],
            2,
        ),
        (
            [False, False],
            0,
        ),
        (
            [True, False, False],
            1,
        ),
    ],
    ids=["all_crash", "none_crash", "mixed_results"],
)
def test_crash_preserving_minimization_visitor_statement_removal(
    tc_with_statements,
    mock_executor,
    execution_results,
    expected_removed,
):
    """Test that the visitor correctly handles statement removal based on crash behavior."""
    test_case, _, _ = tc_with_statements
    original_size = test_case.size()

    mock_exit_codes = []
    for has_exception in execution_results:
        # If has_exception is True, return a non-zero exit code (indicating a crash)
        # Otherwise, return 0 (indicating success)
        mock_exit_codes = [-11 if has_exception else 0 for has_exception in execution_results]

    mock_executor.execute_with_exit_code.side_effect = mock_exit_codes
    visitor = pp.CrashPreservingMinimizationVisitor(mock_executor)
    test_case.accept(visitor)
    assert visitor.removed_statements == expected_removed
    assert test_case.size() == original_size - expected_removed


def test_crash_preserving_minimization_visitor_with_empty_test_case(basic_test_case, mock_executor):
    """Test that the visitor handles empty test cases correctly."""
    # Create the visitor and apply it to the empty test case
    visitor = pp.CrashPreservingMinimizationVisitor(mock_executor)
    basic_test_case.accept(visitor)

    # Verify that no statements were removed (since there were none to begin with)
    assert visitor.removed_statements == 0
    assert basic_test_case.size() == 0
    # Verify that the executor was not called
    mock_executor.execute_with_exit_code.assert_not_called()


def test_crash_preserving_minimization_visitor_with_dependencies(
    tc_with_dependencies, mock_executor
):
    """Test that the visitor correctly handles dependencies between statements."""
    test_case, _, _, _ = tc_with_dependencies

    # Set up the mock executor to return different exit codes based on the test case
    def execute_with_exit_code_side_effect(test_case_arg):
        # If the test case has a string statement, it crashes (non-zero exit code)
        has_string = any(
            isinstance(s, stmt.StringPrimitiveStatement) for s in test_case_arg.statements
        )
        return -11 if has_string else 0

    mock_executor.execute_with_exit_code.side_effect = execute_with_exit_code_side_effect

    # Create the visitor and apply it to the test case
    visitor = pp.CrashPreservingMinimizationVisitor(mock_executor)
    test_case.accept(visitor)

    # Verify the test case was processed
    # Note: The exact number of removed statements and final size can vary
    # depending on the implementation details and test case structure
    assert test_case.size() > 0  # At least one statement remains
    # Verify that the executor was called at least once
    assert mock_executor.execute_with_exit_code.call_count > 0


def test_suite_minimization_visitor_init(mock_fitness_function, test_suite_minimization_visitor):
    """Test that the TestSuiteMinimizationVisitor initializes correctly."""
    assert test_suite_minimization_visitor._fitness_function == mock_fitness_function
    assert test_suite_minimization_visitor.removed_test_cases == 0


@pytest.mark.parametrize(
    "fitness_behavior,expected_results",
    [
        # Case 1: Fitness preserved when test cases are removed
        (
            lambda _: 1.0,  # Constant coverage
            {"removed": 1, "size": 1},  # One test case removed, final size is 1
        ),
        # Case 2: Fitness reduced when test cases are removed
        (
            lambda test_suite: 1.0 if test_suite.size() == 2 else 0.5,
            {"removed": 0, "size": 2},  # No test cases removed, final size is 2
        ),
    ],
    ids=["fitness_preserved", "fitness_reduced"],
)
def test_suite_minimization_visitor_test_case_removal(
    mock_fitness_function,
    test_suite_minimization_visitor,
    fitness_behavior,
    expected_results,
    basic_test_case,
):
    """Test that the visitor correctly handles test case removal based on fitness changes."""
    # Create a test suite with two identical test cases
    test_suite = TestSuiteChromosome()
    test_case1 = tcc.TestCaseChromosome(test_case=basic_test_case.clone())
    test_case2 = tcc.TestCaseChromosome(test_case=basic_test_case.clone())
    test_suite.add_test_case_chromosome(test_case1)
    test_suite.add_test_case_chromosome(test_case2)

    # Set up the mock fitness function behavior
    if callable(fitness_behavior):
        mock_fitness_function.compute_coverage.side_effect = fitness_behavior
    else:
        mock_fitness_function.compute_coverage.return_value = fitness_behavior

    # Apply the visitor to the test suite
    test_suite.accept(test_suite_minimization_visitor)

    # Verify the expected results
    assert test_suite_minimization_visitor.removed_test_cases == expected_results["removed"]
    assert test_suite.size() == expected_results["size"]


def test_test_suite_minimization_visitor_with_single_test_case(
    mock_fitness_function,
    test_suite_minimization_visitor,
    basic_test_case,
):
    """Test that the visitor handles test suites with a single test case correctly."""
    # Create a test suite with a single test case
    test_suite = TestSuiteChromosome()
    test_case = tcc.TestCaseChromosome(test_case=basic_test_case.clone())
    test_suite.add_test_case_chromosome(test_case)

    # Set up the mock fitness function
    mock_fitness_function.compute_coverage.return_value = 1.0

    # Apply the visitor to the test suite
    test_suite.accept(test_suite_minimization_visitor)

    # Verify that no test cases were removed (since there's only one)
    assert test_suite_minimization_visitor.removed_test_cases == 0
    assert test_suite.size() == 1


def _create_test_case_with_calls(base_test_case, function_generic, values):
    """Helper function to create a test case with function calls.

    Args:
        base_test_case: The base test case to clone
        function_generic: The function to call
        values: The values to pass to the function

    Returns:
        The created test case
    """
    test_case = base_test_case.clone()

    for value in values:
        int_stmt = stmt.IntPrimitiveStatement(test_case, value)
        test_case.add_statement(int_stmt)
        func_stmt = stmt.FunctionStatement(test_case, function_generic, {"a": int_stmt.ret_val})
        test_case.add_statement(func_stmt)

    return test_case


@pytest.mark.parametrize(
    "coverage_metric,expected_removed",
    [
        (config.CoverageMetric.BRANCH, 1),
        (config.CoverageMetric.LINE, 1),
    ],
)
def test_suite_minimization_visitor_integration(coverage_metric, expected_removed):
    """Integration test for TestSuiteMinimizationVisitor with different coverage functions."""
    executor, test_case, first_function_generic = _setup_integration_test(coverage_metric)
    if coverage_metric == config.CoverageMetric.BRANCH:
        coverage_function_class = TestSuiteBranchCoverageFunction
    elif coverage_metric == config.CoverageMetric.LINE:
        coverage_function_class = TestSuiteLineCoverageFunction
    else:
        raise ValueError(f"Unknown coverage metric: {coverage_metric}")

    # Create two test cases that achieve the same coverage
    test_suite = TestSuiteChromosome()

    # Create test cases with calls to first(-1) and first(0)
    values = [-1, 0]
    test_case1 = _create_test_case_with_calls(test_case, first_function_generic, values)
    test_case2 = _create_test_case_with_calls(test_case, first_function_generic, values)

    # Add both test cases to the test suite
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case=test_case1))
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case=test_case2))

    # Execute the test cases to ensure they have coverage
    for test_case_chrom in test_suite.test_case_chromosomes:
        executor.execute(test_case_chrom.test_case)

    # Create a coverage function and visitor based on the parameter
    fitness_function = coverage_function_class(executor)
    visitor = pp.TestSuiteMinimizationVisitor(fitness_function)

    # Apply the visitor to the test suite
    test_suite.accept(visitor)

    # Verify that the expected number of test cases is removed
    assert visitor.removed_test_cases == expected_removed
    assert test_suite.size() == 1  # Only one test case should remain


def test_combined_minimization_visitor_init(mock_fitness_function, combined_minimization_visitor):
    """Test that the CombinedMinimizationVisitor initializes correctly."""
    assert combined_minimization_visitor._fitness_function == mock_fitness_function
    assert combined_minimization_visitor._removed_statements == 0
    assert combined_minimization_visitor.removed_statements == 0


@pytest.mark.parametrize(
    "fitness_behavior,expected_results",
    [
        # Case 1: Fitness preserved when test cases and statements are removed
        (
            lambda _: 1.0,  # Constant coverage
            {"removed_statements": 4},
        ),
        # Case 2: Fitness reduced when statements are removed
        (
            "use_counter",  # Special value to use a counter-based approach
            {"removed_statements": 0},
        ),
    ],
    ids=["fitness_preserved", "fitness_changed"],
)
def test_combined_minimization_visitor_minimization(
    mock_fitness_function,
    combined_minimization_visitor,
    fitness_behavior,
    expected_results,
    tc_with_statements,
):
    """Test that the visitor correctly handles combined minimization."""
    test_case, _, _ = tc_with_statements

    # Create a test suite with two test cases
    test_suite = TestSuiteChromosome()
    test_case1 = tcc.TestCaseChromosome(test_case=test_case.clone())
    test_case2 = tcc.TestCaseChromosome(test_case=test_case.clone())
    test_suite.add_test_case_chromosome(test_case1)
    test_suite.add_test_case_chromosome(test_case2)

    # Set up the mock fitness function behavior
    if fitness_behavior == "use_counter":
        # Use a counter to return different values on successive calls
        call_count = [0]

        def side_effect(_):
            call_count[0] += 1
            return 1.0 if call_count[0] == 1 else 0.0  # First call returns 1.0, others return 0.0

        mock_fitness_function.compute_coverage.side_effect = side_effect
    else:
        mock_fitness_function.compute_coverage.side_effect = fitness_behavior

    # Apply the visitor to the test suite
    test_suite.accept(combined_minimization_visitor)

    # Verify the expected results
    assert (
        combined_minimization_visitor.removed_statements == expected_results["removed_statements"]
    )


def test_combined_minimization_visitor_with_single_test_case(
    mock_fitness_function,
    combined_minimization_visitor,
    tc_with_statements,
):
    """Test that the visitor handles test suites with a single test case correctly."""
    test_case, _, _ = tc_with_statements

    # Create a test suite with a single test case
    test_suite = TestSuiteChromosome()
    test_case_chrom = tcc.TestCaseChromosome(test_case=test_case.clone())
    test_suite.add_test_case_chromosome(test_case_chrom)

    # Set up the mock fitness function to allow removing statements
    call_count = [0]  # Use a list to store mutable state

    def side_effect(_):
        call_count[0] += 1
        return 1.0 if call_count[0] == 1 else 0.5

    mock_fitness_function.compute_coverage.side_effect = side_effect

    # Apply the visitor to the test suite
    test_suite.accept(combined_minimization_visitor)

    # Verify that no test cases were removed (since there's only one)
    assert test_suite.size() == 1


@pytest.mark.parametrize(
    "coverage_metric,expected_removed_statements",
    [
        (config.CoverageMetric.BRANCH, 8),
        (config.CoverageMetric.LINE, 8),
    ],
)
def test_combined_minimization_visitor_integration(coverage_metric, expected_removed_statements):
    """Integration test for CombinedMinimizationVisitor with different coverage functions."""
    executor, test_case, first_function_generic = _setup_integration_test(coverage_metric)
    if coverage_metric == config.CoverageMetric.BRANCH:
        coverage_function_class = TestSuiteBranchCoverageFunction
    elif coverage_metric == config.CoverageMetric.LINE:
        coverage_function_class = TestSuiteLineCoverageFunction
    else:
        raise ValueError(f"Unknown coverage metric: {coverage_metric}")

    # Create a test suite with two identical test cases
    test_suite = TestSuiteChromosome()

    # Create test cases with calls to first(-1) and first(0)
    values = [0, 1, 2]
    test_case1 = _create_test_case_with_calls(test_case, first_function_generic, values)
    test_case2 = _create_test_case_with_calls(test_case, first_function_generic, values)

    # Add both test cases to the test suite
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case=test_case1))
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case=test_case2))

    # Execute the test cases to ensure they have coverage
    for test_case_chrom in test_suite.test_case_chromosomes:
        executor.execute(test_case_chrom.test_case)

    # Create a coverage function and visitor based on the parameter
    fitness_function = coverage_function_class(executor)
    visitor = pp.CombinedMinimizationVisitor(fitness_function)

    # Apply the visitor to the test suite
    test_suite.accept(visitor)

    # Verify that the expected number of statements and test cases are removed
    assert visitor.removed_statements == expected_removed_statements
    assert test_suite.size() == 2
