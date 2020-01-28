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
"""Some integration tests for the testcase/statements"""
import pytest

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.assignmentstatement as assign


def test_method_statement_clone():
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    str_prim = prim.StringPrimitiveStatement(test_case, "TestThis")
    method_stmt = ps.MethodStatement(
        test_case, "", str_prim.return_value, str, [int_prim.return_value],
    )
    test_case.add_statement(int_prim)
    test_case.add_statement(str_prim)
    test_case.add_statement(method_stmt)

    cloned = test_case.clone()
    assert isinstance(cloned.statements[2], ps.MethodStatement)
    assert cloned.statements[2] is not method_stmt


def test_constructor_statement_clone():
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    method_stmt = ps.ConstructorStatement(test_case, int, [int_prim.return_value],)
    test_case.add_statement(int_prim)
    test_case.add_statement(method_stmt)

    cloned = test_case.clone()
    assert isinstance(cloned.statements[1], ps.ConstructorStatement)
    assert cloned.statements[1] is not method_stmt
    assert cloned.statements[0].return_value is not test_case.statements[0].return_value


def test_assignment_statement_clone():
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    int_prim2 = prim.IntPrimitiveStatement(test_case, 10)
    # TODO(fk) the assignment statement from EvoSuite might not be fitting for our case?
    # Because currently we can only overwrite existing values?
    assignment_stmt = assign.AssignmentStatement(
        test_case, int_prim.return_value, int_prim2.return_value
    )
    test_case.add_statement(int_prim)
    test_case.add_statement(int_prim2)
    test_case.add_statement(assignment_stmt)

    cloned = test_case.clone()
    assert isinstance(cloned.statements[2], assign.AssignmentStatement)
    assert cloned.statements[2] is not assignment_stmt


@pytest.fixture(scope="function")
def simple_test_case() -> dtc.DefaultTestCase:
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    int_prim2 = prim.IntPrimitiveStatement(test_case, 5)
    test_case.add_statement(int_prim)
    test_case.add_statement(int_prim2)
    return test_case


def test_test_case_equals_on_different_prim(simple_test_case: dtc.DefaultTestCase):
    cloned = simple_test_case.clone()

    # Original points to int at 0
    simple_test_case.add_statement(
        ps.ConstructorStatement(
            simple_test_case, int, [simple_test_case.statements[0].return_value]
        )
    )
    # Clone points to int at 1
    cloned.add_statement(
        ps.ConstructorStatement(cloned, int, [cloned.statements[1].return_value])
    )

    # Even thought they both point to an int, they are not equal
    assert not simple_test_case == cloned
