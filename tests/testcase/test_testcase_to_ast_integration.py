# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from ast import Module

import astor
import pytest

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.testcase_to_ast as tc_to_ast


@pytest.fixture()
def simple_test_case(constructor_mock):
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, 5)
    constructor_stmt = param_stmt.ConstructorStatement(
        test_case, constructor_mock, [int_stmt.return_value]
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_stmt)
    return test_case


def test_test_case_to_ast_once(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor()
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        astor.to_source(Module(body=visitor.test_case_asts[0]))
        == "var0 = 5\nvar1 = module0.SomeType(var0)\n"
    )


def test_test_case_to_ast_twice(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor()
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        astor.to_source(Module(body=visitor.test_case_asts[0]))
        == "var0 = 5\nvar1 = module0.SomeType(var0)\n"
    )
    assert (
        astor.to_source(Module(body=visitor.test_case_asts[1]))
        == "var0 = 5\nvar1 = module0.SomeType(var0)\n"
    )


def test_test_case_to_ast_module_aliases(simple_test_case):
    visitor = tc_to_ast.TestCaseToAstVisitor()
    simple_test_case.accept(visitor)
    simple_test_case.accept(visitor)
    assert (
        "tests.fixtures.accessibles.accessible"
        in visitor.module_aliases.known_name_indices
    )
    assert (
        visitor.module_aliases.get_name("tests.fixtures.accessibles.accessible")
        == "module0"
    )
