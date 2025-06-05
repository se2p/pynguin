#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertion as ass
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as st
import pynguin.testcase.variablereference as vr

from pynguin.analyses.module import ModuleTestCluster
from pynguin.analyses.typesystem import AnyType
from pynguin.testcase.testcase import TestCase
from pynguin.utils.orderedset import OrderedSet


@pytest.fixture
def default_test_case():
    # TODO what about the logger, should be a mock
    return dtc.DefaultTestCase(ModuleTestCluster(0))


def get_default_test_case():
    return dtc.DefaultTestCase(ModuleTestCluster(0))


def test_add_statement_end(default_test_case):
    stmt_1 = MagicMock(st.Statement, ret_val=MagicMock())
    stmt_2 = MagicMock(st.Statement, ret_val=MagicMock())
    stmt_3 = MagicMock(st.Statement, ret_val=MagicMock())
    stmt_3.return_value = MagicMock(vr.VariableReference)
    default_test_case._statements.extend([stmt_1, stmt_2])

    reference = default_test_case.add_statement(stmt_3)
    assert reference
    assert default_test_case._statements == [stmt_1, stmt_2, stmt_3]


def test_add_statement_middle(default_test_case):
    stmt_1 = MagicMock(st.Statement, ret_val=MagicMock())
    stmt_2 = MagicMock(st.Statement, ret_val=MagicMock())
    stmt_2.return_value = MagicMock(vr.VariableReference)
    stmt_3 = MagicMock(st.Statement, ret_val=MagicMock())
    default_test_case._statements.extend([stmt_1, stmt_3])

    reference = default_test_case.add_statement(stmt_2, position=1)
    assert reference
    assert default_test_case._statements == [stmt_1, stmt_2, stmt_3]


def test_add_statements(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.append(stmt_1)
    default_test_case.add_statements([stmt_2, stmt_3])
    assert default_test_case._statements == [stmt_1, stmt_2, stmt_3]


def test_chop(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    default_test_case.chop(1)
    assert default_test_case._statements == [stmt_1, stmt_2]


def test_contains_true(default_test_case):
    stmt = MagicMock(st.Statement)
    default_test_case._statements.append(stmt)
    assert default_test_case.contains(stmt)


def test_contains_false(default_test_case):
    assert not default_test_case.contains(MagicMock(st.Statement))


def test_size(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    assert default_test_case.size() == 3


def test_remove_nothing(default_test_case):
    default_test_case.remove(1)


def test_remove(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    default_test_case.remove(1)
    assert default_test_case._statements == [stmt_1, stmt_3]


def test_remove_statement(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case.add_statements([stmt_1, stmt_2, stmt_3])
    assert default_test_case.size() == 3
    default_test_case.remove_statement(stmt_2)
    assert default_test_case.statements == [stmt_1, stmt_3]


def test_get_statement(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    assert default_test_case.get_statement(1) == stmt_2


def test_get_statement_negative_position(default_test_case):
    with pytest.raises(AssertionError):
        default_test_case.get_statement(-1)


def test_get_statement_positive_position(default_test_case):
    with pytest.raises(AssertionError):
        default_test_case.get_statement(42)


def test_has_statement(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    assert not default_test_case.has_statement(-1)
    assert default_test_case.has_statement(1)
    assert not default_test_case.has_statement(3)


def test_hash(default_test_case):
    assert hash(default_test_case)


@pytest.mark.parametrize(
    "test_case,other,result",
    [
        pytest.param(get_default_test_case(), None, False),
        pytest.param(get_default_test_case(), "Foo", False),
    ],
)
def test_eq_parameterized(test_case, other, result):
    assert (test_case == other) == result


def test_eq_same(default_test_case):
    assert default_test_case == default_test_case  # noqa: PLR0124


def test_eq_statements_1(default_test_case):
    other = dtc.DefaultTestCase(ModuleTestCluster(0))
    other._statements = [MagicMock(st.Statement)]
    assert default_test_case != other


def test_eq_statements_2(default_test_case):
    default_test_case._statements = [MagicMock(st.Statement)]
    other = dtc.DefaultTestCase(ModuleTestCluster(0))
    other._statements = [MagicMock(st.Statement), MagicMock(st.Statement)]
    assert default_test_case != other


def test_eq_statements_3(default_test_case):
    stmt1 = MagicMock(ret_val=MagicMock())
    stmt1.structural_eq.return_value = False
    default_test_case._statements = [stmt1]
    other = dtc.DefaultTestCase(ModuleTestCluster(0))
    other._statements = [MagicMock(st.Statement, ret_val=MagicMock())]
    assert default_test_case != other


def test_eq_statements_4(default_test_case):
    statements = [
        MagicMock(st.Statement, ret_val=MagicMock()),
        MagicMock(st.Statement, ret_val=MagicMock()),
    ]
    default_test_case._statements = statements
    other = dtc.DefaultTestCase(ModuleTestCluster(0))
    other._statements = statements
    assert default_test_case == other


def test_eq_statements_5(default_test_case):
    default_test_case._statements = []
    other = dtc.DefaultTestCase(ModuleTestCluster(0))
    other._statements = []
    assert default_test_case == other


def test_clone(default_test_case):
    stmt = MagicMock(st.Statement, ret_val=MagicMock())
    ref = MagicMock(vr.VariableReference)
    stmt.clone.return_value = stmt
    stmt.return_value.clone.return_value = ref
    default_test_case._statements = [stmt]
    result = default_test_case.clone()
    assert isinstance(result, dtc.DefaultTestCase)
    assert result.size() == 1
    assert result.get_statement(0) == stmt


def test_statements(default_test_case):
    assert default_test_case.statements == []


def test_append_test_case(default_test_case):
    stmt = MagicMock(st.Statement, ret_val=MagicMock())
    stmt.clone.return_value = stmt
    other = dtc.DefaultTestCase(ModuleTestCluster(0))
    other._statements = [stmt]
    assert len(default_test_case.statements) == 0
    default_test_case.append_test_case(other)
    assert len(default_test_case.statements) == 1


def test_get_objects(default_test_case, type_system):
    stmt_1 = MagicMock(st.Statement)
    vri_1 = vr.VariableReference(default_test_case, type_system.convert_type_hint(int))
    stmt_1.ret_val = vri_1
    stmt_2 = MagicMock(st.Statement)
    vri_2 = vr.VariableReference(default_test_case, type_system.convert_type_hint(float))
    stmt_2.ret_val = vri_2
    stmt_3 = MagicMock(st.Statement)
    vri_3 = vr.VariableReference(default_test_case, type_system.convert_type_hint(int))
    stmt_3.ret_val = vri_3
    default_test_case._statements = [stmt_1, stmt_2, stmt_3]
    result = default_test_case.get_objects(type_system.convert_type_hint(int), 2)
    assert result == [vri_1]


def test_get_objects_without_type(default_test_case):
    result = default_test_case.get_objects(AnyType(), 42)
    assert result == []


def test_set_statement_empty(default_test_case):
    with pytest.raises(AssertionError):
        default_test_case.set_statement(MagicMock(st.Statement), 0)


def test_set_statement_valid(default_test_case):
    int0 = st.IntPrimitiveStatement(default_test_case, 5)
    int1 = st.IntPrimitiveStatement(default_test_case, 5)
    default_test_case.add_statement(int0)
    default_test_case.add_statement(int1)
    assert default_test_case.set_statement(int1, 0) == int1.ret_val
    assert default_test_case.get_statement(0) == int1


def test_get_dependencies_self_empty(default_test_case, constructor_mock):
    const0 = st.ConstructorStatement(default_test_case, constructor_mock)
    default_test_case.add_statement(const0)
    dependencies = default_test_case.get_dependencies(const0.ret_val)
    assert dependencies == OrderedSet([const0.ret_val])


def test_get_dependencies_chained(default_test_case, function_mock):
    unused_float = st.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(unused_float)

    float0 = st.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(float0)

    func0 = st.FunctionStatement(default_test_case, function_mock, {"a": float0.ret_val})
    default_test_case.add_statement(func0)

    func1 = st.FunctionStatement(default_test_case, function_mock, {"a": func0.ret_val})
    default_test_case.add_statement(func1)
    dependencies = default_test_case.get_dependencies(func1.ret_val)
    assert dependencies == OrderedSet([func1.ret_val, func0.ret_val, float0.ret_val])


def test_get_assertions_empty(default_test_case):
    assert default_test_case.get_assertions() == []


@pytest.fixture
def default_test_case_with_assertions(default_test_case):
    float0 = st.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(float0)
    float0ass0 = ass.ObjectAssertion(float0.ret_val, 5.5)
    float0ass1 = ass.ObjectAssertion(float0.ret_val, 6)
    float0.add_assertion(float0ass0)
    float0.add_assertion(float0ass1)

    float1 = st.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(float1)

    float2 = st.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(float2)
    float2ass0 = ass.ObjectAssertion(float2.ret_val, 5.5)
    float2.add_assertion(float2ass0)
    return default_test_case, {float0ass0, float0ass1, float2ass0}


def test_get_assertions_multiple_statements(default_test_case_with_assertions):
    test_case, assertions = default_test_case_with_assertions
    assert set(test_case.get_assertions()) == assertions


def test_get_size_with_assertions(default_test_case_with_assertions):
    test_case, _assertions = default_test_case_with_assertions
    assert test_case.size_with_assertions() == 6  # 3 stmts + 3 assertions


def setup_dependency_testcase(default_test_case, function_mock=None, scenario="empty"):
    """Helper function to set up test cases for forward dependency tests.

    Args:
        default_test_case: The test case to set up
        function_mock: Mock function to use in statements
        scenario: The dependency scenario to set up:
            - "empty": No forward dependencies
            - "direct": Direct forward dependencies
            - "indirect": Indirect forward dependencies
            - "mixed": Mix of dependent and independent statements

    Returns:
        A tuple containing the variable references and expected dependencies
    """
    # Create the first variable (used in all scenarios)
    int0 = st.IntPrimitiveStatement(default_test_case, 5)
    default_test_case.add_statement(int0)

    if scenario == "empty":
        return {"int0": int0.ret_val}, {}

    if scenario == "direct":
        # Create a statement that uses the variable
        func0 = st.FunctionStatement(default_test_case, function_mock, {"a": int0.ret_val})
        default_test_case.add_statement(func0)

        return {"int0": int0.ret_val}, {"int0": OrderedSet([func0.ret_val])}

    if scenario == "indirect":
        # Create a statement that uses the variable
        func0 = st.FunctionStatement(default_test_case, function_mock, {"a": int0.ret_val})
        default_test_case.add_statement(func0)

        # Create another statement that uses the result of the first function
        func1 = st.FunctionStatement(default_test_case, function_mock, {"a": func0.ret_val})
        default_test_case.add_statement(func1)

        return {"int0": int0.ret_val}, {"int0": OrderedSet([func0.ret_val, func1.ret_val])}

    if scenario == "mixed":
        # Create a second independent variable
        float0 = st.FloatPrimitiveStatement(default_test_case, 5.5)
        default_test_case.add_statement(float0)

        # Create a statement that uses only int0
        func0 = st.FunctionStatement(default_test_case, function_mock, {"a": int0.ret_val})
        default_test_case.add_statement(func0)

        # Create a statement that uses only float0
        func1 = st.FunctionStatement(default_test_case, function_mock, {"a": float0.ret_val})
        default_test_case.add_statement(func1)

        return {"int0": int0.ret_val, "float0": float0.ret_val}, {
            "int0": OrderedSet([func0.ret_val]),
            "float0": OrderedSet([func1.ret_val]),
        }

    raise ValueError(f"{scenario}: Value not supported.")


@pytest.mark.parametrize(
    "scenario, var_key, expected_dependencies",
    [
        ("empty", "int0", OrderedSet()),
        ("direct", "int0", None),  # Will be filled from the setup function
        ("indirect", "int0", None),  # Will be filled from the setup function
        ("mixed", "int0", None),  # Will be filled from the setup function
        ("mixed", "float0", None),  # Will be filled from the setup function
    ],
)
def test_get_forward_dependencies(
    default_test_case, function_mock, scenario, var_key, expected_dependencies
):
    """Test get_forward_dependencies with various dependency scenarios."""
    # Set up the test case according to the scenario
    variables, expected_deps_dict = setup_dependency_testcase(
        default_test_case, function_mock, scenario
    )

    # If expected_dependencies is None, get it from the expected_deps_dict
    if expected_dependencies is None:
        expected_dependencies = expected_deps_dict[var_key]

    # Get the variable to check dependencies for
    var = variables[var_key]

    # Check the dependencies
    dependencies = default_test_case.get_forward_dependencies(var)
    assert dependencies == expected_dependencies


def test_positions_to_remove():
    """Test the positions_to_remove static method."""
    # Create a statement and some mock forward dependencies
    statement = MagicMock()
    statement.get_position.return_value = 2

    dep1 = MagicMock()
    dep1.get_statement_position.return_value = 3

    dep2 = MagicMock()
    dep2.get_statement_position.return_value = 5

    # Call the method directly
    positions = TestCase.positions_to_remove(statement, [dep1, dep2])

    # Verify the positions are correct and in reverse order
    assert positions == [5, 3, 2]


@pytest.fixture
def tc_with_three_statements(default_test_case):
    """Fixture for a test case with three statements."""
    int_stmt = st.IntPrimitiveStatement(default_test_case)
    default_test_case.add_statement(int_stmt)

    float_stmt = st.FloatPrimitiveStatement(default_test_case)
    default_test_case.add_statement(float_stmt)

    str_stmt = st.StringPrimitiveStatement(default_test_case)
    default_test_case.add_statement(str_stmt)

    return default_test_case, int_stmt, float_stmt, str_stmt


def test_remove_with_dependencies(tc_with_three_statements):
    """Test the remove_with_forward_dependencies method."""
    test_case, int_stmt, _, str_stmt = tc_with_three_statements

    # Get the actual method from the test_case instance
    positions_removed = test_case.remove_with_forward_dependencies(1)

    # Verify the positions removed
    assert positions_removed == [1]

    # Verify the test case has the correct statements
    assert test_case.size() == 2
    assert test_case.statements[0] == int_stmt
    assert test_case.statements[1] == str_stmt


def test_remove_with_dependencies_empty(default_test_case):
    """Test the remove_with_forward_dependencies method on an empty test case."""
    # Attempt to remove a statement from an empty test case
    with pytest.raises(ValueError, match="Position 0 is out of bounds"):
        default_test_case.remove_with_forward_dependencies(0)


def test_remove_statement_with_dependencies(tc_with_three_statements):
    """Test the remove_statement_with_forward_dependencies method."""
    test_case, int_stmt, float_stmt, str_stmt = tc_with_three_statements

    # Call the method
    positions_removed = test_case.remove_statement_with_forward_dependencies(float_stmt)

    # Verify the positions removed
    assert positions_removed == [1]

    # Verify the test case has the correct statements
    assert test_case.size() == 2
    assert test_case.statements[0] == int_stmt
    assert test_case.statements[1] == str_stmt


def test_remove_statement_with_dependencies_empty(default_test_case):
    """Test the remove_statement_with_forward_dependencies method on an empty test case."""
    # Attempt to remove a statement from an empty test case
    with pytest.raises(ValueError, match="not found in test case"):
        default_test_case.remove_statement_with_forward_dependencies(MagicMock(st.Statement))


def test_remove_statement_with_dependencies_with_dependencies(default_test_case, function_mock):
    """Test the remove_statement_with_forward_dependencies method with dependencies."""
    setup_dependency_testcase(default_test_case, function_mock, "indirect")

    # Initial size check
    assert default_test_case.size() == 3

    # Select statement to remove - use the first statement (int0)
    stmt = default_test_case.get_statement(0)

    # Call the method
    positions_removed = default_test_case.remove_statement_with_forward_dependencies(stmt)

    # Assert positions removed
    assert sorted(positions_removed, reverse=True) == [2, 1, 0]
    assert default_test_case.size() == 0
