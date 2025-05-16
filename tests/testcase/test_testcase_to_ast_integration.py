#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast

from ast import Module

import pytest

import pynguin.assertion.assertion as ass
import pynguin.testcase.statement as stmt
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.testcase_to_ast as tc_to_ast
import pynguin.utils.namingscope as ns

from pynguin.testcase.execution import ExecutionResult


@pytest.fixture
def simple_test_case(constructor_mock, default_test_case):
    int_stmt = stmt.IntPrimitiveStatement(default_test_case, 5)
    constructor_stmt = stmt.ConstructorStatement(
        default_test_case, constructor_mock, {"y": int_stmt.ret_val}
    )
    constructor_stmt.add_assertion(ass.ObjectAssertion(constructor_stmt.ret_val, 3))
    default_test_case.add_statement(int_stmt)
    default_test_case.add_statement(constructor_stmt)
    return default_test_case


def test_test_case_to_ast_once(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor(
        ns.NamingScope("module"), set(), store_call_return=True
    )
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        ast.unparse(ast.fix_missing_locations(Module(body=visitor.test_case_ast, type_ignores=[])))
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3"
    )


def test_test_case_to_ast_twice(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor(
        ns.NamingScope("module"), set(), store_call_return=False
    )
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        ast.unparse(ast.fix_missing_locations(Module(body=visitor.test_case_ast, type_ignores=[])))
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3"
    )
    assert (
        ast.unparse(ast.fix_missing_locations(Module(body=visitor.test_case_ast, type_ignores=[])))
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3"
    )


def test_test_case_to_ast_module_aliases(simple_test_case):
    module_aliases = ns.NamingScope("module")
    visitor = tc_to_ast.TestCaseToAstVisitor(module_aliases, set())
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert dict(module_aliases) == {"tests.fixtures.accessibles.accessible": "module_0"}


def test_test_case_to_ast_with_exception_store_call_return_true(simple_test_case):
    # Create an execution result with an exception at position 1
    exec_result = ExecutionResult()
    exec_result.report_new_thrown_exception(1, ValueError("Test exception"))

    # Create visitor with store_call_return=True
    visitor = tc_to_ast.TestCaseToAstVisitor(
        ns.NamingScope("module"), set(), exec_result, store_call_return=True
    )

    # Visit the test case
    simple_test_case.accept(visitor)

    # The test passes if no exception is raised and the AST is generated correctly
    assert visitor.test_case_ast is not None


def test_test_case_to_ast_with_exception_store_call_return_false(simple_test_case):
    # Create an execution result with an exception at position 1
    exec_result = ExecutionResult()
    exec_result.report_new_thrown_exception(1, ValueError("Test exception"))

    # Create visitor with store_call_return=False (default)
    visitor = tc_to_ast.TestCaseToAstVisitor(ns.NamingScope("module"), set(), exec_result)

    # Visit the test case
    simple_test_case.accept(visitor)

    # The test passes if no exception is raised and the AST is generated correctly
    assert visitor.test_case_ast is not None


def test_store_call_return_value_with_exception(simple_test_case, monkeypatch):
    """Test that store_call_return is set to self._store_call_return when an exception is thrown."""
    # Create an execution result with an exception at position 1
    exec_result = ExecutionResult()
    exec_result.report_new_thrown_exception(1, ValueError("Test exception"))

    # Mock the StatementToAstVisitor to capture the store_call_return value
    original_visitor = stmt_to_ast.StatementToAstVisitor
    store_call_return_values = []

    class MockStatementVisitor(original_visitor):
        def __init__(self, module_aliases, variables, store_call_return=None):
            store_call_return = False if store_call_return is None else store_call_return
            super().__init__(module_aliases, variables, store_call_return=store_call_return)
            store_call_return_values.append(store_call_return)

    monkeypatch.setattr(stmt_to_ast, "StatementToAstVisitor", MockStatementVisitor)

    # Test with store_call_return=True
    visitor_true = tc_to_ast.TestCaseToAstVisitor(
        ns.NamingScope("module"), set(), exec_result, store_call_return=True
    )
    simple_test_case.accept(visitor_true)

    # Test with store_call_return=False
    visitor_false = tc_to_ast.TestCaseToAstVisitor(
        ns.NamingScope("module"), set(), exec_result, store_call_return=False
    )
    simple_test_case.accept(visitor_false)

    # The first statement should have store_call_return=True in both cases
    # The second statement (where exception occurs) should have store_call_return=True
    # for the first test
    # and store_call_return=False for the second test
    assert len(store_call_return_values) == 4  # 2 statements × 2 tests
    assert store_call_return_values[0] is True  # First statement, first test
    assert (
        store_call_return_values[1] is True
    )  # Second statement, first test (exception with store_call_return=True)
    assert store_call_return_values[2] is True  # First statement, second test
    assert (
        store_call_return_values[3] is False
    )  # Second statement, second test (exception with store_call_return=False)


def test_unused_return_value_not_stored(constructor_mock, default_test_case, monkeypatch):
    """Test that return values are not stored when they are not used by subsequent statements."""
    # Create a test case with two function calls, where the return value of the first is not used
    int_stmt = stmt.IntPrimitiveStatement(default_test_case, 5)
    constructor_stmt1 = stmt.ConstructorStatement(
        default_test_case, constructor_mock, {"y": int_stmt.ret_val}
    )
    constructor_stmt2 = stmt.ConstructorStatement(
        default_test_case, constructor_mock, {"y": int_stmt.ret_val}
    )
    default_test_case.add_statement(int_stmt)
    default_test_case.add_statement(constructor_stmt1)
    default_test_case.add_statement(constructor_stmt2)

    # Mock the StatementToAstVisitor to capture the store_call_return value
    original_visitor = stmt_to_ast.StatementToAstVisitor
    store_call_return_values = []

    class MockStatementVisitor(original_visitor):
        def __init__(self, module_aliases, variables, store_call_return=None):
            store_call_return = False if store_call_return is None else store_call_return
            super().__init__(module_aliases, variables, store_call_return=store_call_return)
            store_call_return_values.append(store_call_return)

    monkeypatch.setattr(stmt_to_ast, "StatementToAstVisitor", MockStatementVisitor)

    # Visit the test case
    visitor = tc_to_ast.TestCaseToAstVisitor(
        ns.NamingScope("module"), set(), store_call_return=False
    )
    default_test_case.accept(visitor)

    # The first statement (int) should have store_call_return=True because it's used
    # The second statement (constructor) should have store_call_return=False
    # because its return value is not used
    # The third statement (constructor) should have store_call_return=False
    # because the return value of the last statement can also be ignored
    assert len(store_call_return_values) == 3
    assert store_call_return_values[0] is True  # int_stmt
    assert store_call_return_values[1] is False  # constructor_stmt1 (unused return value)
    # constructor_stmt2 (last statement, return value can be ignored)
    assert store_call_return_values[2] is False
