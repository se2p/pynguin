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

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.assignmentstatement as assign


def test_method_statement_clone(inferred_method_type_mock):
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    str_prim = prim.StringPrimitiveStatement(test_case, "TestThis")
    method_stmt = ps.MethodStatement(
        test_case,
        inferred_method_type_mock,
        str_prim.return_value,
        [int_prim.return_value],
    )
    test_case.add_statement(int_prim)
    test_case.add_statement(str_prim)
    test_case.add_statement(method_stmt)

    cloned = test_case.clone()
    assert isinstance(cloned.statements[2], ps.MethodStatement)
    assert cloned.statements[2] is not method_stmt


def test_constructor_statement_clone(inferred_method_type_mock):
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    method_stmt = ps.ConstructorStatement(
        test_case, inferred_method_type_mock, int, [int_prim.return_value],
    )
    test_case.add_statement(int_prim)
    test_case.add_statement(method_stmt)

    cloned = test_case.clone()
    assert isinstance(cloned.statements[1], ps.ConstructorStatement)
    assert cloned.statements[1] is not method_stmt


def test_assignment_clone():
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
