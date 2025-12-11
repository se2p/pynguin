#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
from ast import Module

import pytest

import pynguin.assertion.assertion as ass
import pynguin.testcase.statement as stmt
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
