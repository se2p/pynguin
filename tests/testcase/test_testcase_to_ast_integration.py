#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast
from ast import Module

import pytest

import pynguin.assertion.assertion as ass
import pynguin.testcase.statement as stmt
import pynguin.testcase.testcase_to_ast as tc_to_ast
import pynguin.utils.namingscope as ns


@pytest.fixture()
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
    visitor = tc_to_ast.TestCaseToAstVisitor(ns.NamingScope("module"), set())
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        ast.unparse(
            ast.fix_missing_locations(
                Module(body=visitor.test_case_ast, type_ignores=[])
            )
        )
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3"
    )


def test_test_case_to_ast_twice(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor(ns.NamingScope("module"), set())
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        ast.unparse(
            ast.fix_missing_locations(
                Module(body=visitor.test_case_ast, type_ignores=[])
            )
        )
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3"
    )
    assert (
        ast.unparse(
            ast.fix_missing_locations(
                Module(body=visitor.test_case_ast, type_ignores=[])
            )
        )
        == "int_0 = 5\nsome_type_0 = module_0.SomeType(int_0)\nassert some_type_0 == 3"
    )


def test_test_case_to_ast_module_aliases(simple_test_case):
    module_aliases = ns.NamingScope("module")
    visitor = tc_to_ast.TestCaseToAstVisitor(module_aliases, set())
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert dict(module_aliases) == {"tests.fixtures.accessibles.accessible": "module_0"}
