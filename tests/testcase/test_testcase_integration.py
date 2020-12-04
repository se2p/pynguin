#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Some integration tests for the testcase/statements"""
import pytest

import pynguin.assertion.primitiveassertion as pas
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.assignmentstatement as assign
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.primitivestatements as prim
from pynguin.utils.exceptions import ConstructionFailedException


def test_method_statement_clone(method_mock):
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    str_prim = prim.StringPrimitiveStatement(test_case, "TestThis")
    method_stmt = ps.MethodStatement(
        test_case,
        method_mock,
        str_prim.ret_val,
        [int_prim.ret_val],
    )
    test_case.add_statement(int_prim)
    test_case.add_statement(str_prim)
    test_case.add_statement(method_stmt)

    cloned = test_case.clone()
    assert isinstance(cloned.statements[2], ps.MethodStatement)
    assert cloned.statements[2] is not method_stmt


def test_constructor_statement_clone(constructor_mock):
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    method_stmt = ps.ConstructorStatement(
        test_case,
        constructor_mock,
        [int_prim.ret_val],
    )
    test_case.add_statement(int_prim)
    test_case.add_statement(method_stmt)

    cloned = test_case.clone()
    assert isinstance(cloned.statements[1], ps.ConstructorStatement)
    assert cloned.statements[1] is not method_stmt
    assert cloned.statements[0].ret_val is not test_case.statements[0].ret_val


def test_assignment_statement_clone():
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    int_prim2 = prim.IntPrimitiveStatement(test_case, 10)
    # TODO(fk) the assignment statement from EvoSuite might not be fitting for our case?
    # Because currently we can only overwrite existing values?
    assignment_stmt = assign.AssignmentStatement(
        test_case, int_prim.ret_val, int_prim2.ret_val
    )
    test_case.add_statement(int_prim)
    test_case.add_statement(int_prim2)
    test_case.add_statement(assignment_stmt)

    cloned = test_case.clone()
    assert isinstance(cloned.statements[2], assign.AssignmentStatement)
    assert cloned.statements[2] is not assignment_stmt


@pytest.fixture(scope="function")
def simple_test_case(function_mock) -> dtc.DefaultTestCase:
    test_case = dtc.DefaultTestCase()
    int_prim = prim.IntPrimitiveStatement(test_case, 5)
    int_prim2 = prim.IntPrimitiveStatement(test_case, 5)
    float_prim = prim.FloatPrimitiveStatement(test_case, 5.5)
    func = ps.FunctionStatement(test_case, function_mock, [float_prim.ret_val])
    func.add_assertion(pas.PrimitiveAssertion(func.ret_val, 3.1415))
    string_prim = prim.StringPrimitiveStatement(test_case, "Test")
    string_prim.ret_val.variable_type = type(None)
    test_case.add_statement(int_prim)
    test_case.add_statement(int_prim2)
    test_case.add_statement(float_prim)
    test_case.add_statement(func)
    test_case.add_statement(string_prim)
    return test_case


def test_clone_with_assertion(simple_test_case):
    cloned = simple_test_case.clone()
    assert len(cloned.get_statement(3).assertions) == 1


def test_test_case_equals_on_different_prim(
    simple_test_case: dtc.DefaultTestCase, constructor_mock
):
    cloned = simple_test_case.clone()

    # Original points to int at 0
    simple_test_case.add_statement(
        ps.ConstructorStatement(
            simple_test_case,
            constructor_mock,
            [simple_test_case.statements[0].ret_val],
        )
    )
    # Clone points to int at 1
    cloned.add_statement(
        ps.ConstructorStatement(
            cloned, constructor_mock, [cloned.statements[1].ret_val]
        )
    )

    # Even though they both point to an int, they are not equal
    assert not simple_test_case == cloned


def test_get_all_objects_short(simple_test_case):
    assert simple_test_case.get_all_objects(2) == [
        simple_test_case.statements[0].ret_val,
        simple_test_case.statements[1].ret_val,
    ]


def test_get_all_objects_full_length(simple_test_case):
    assert simple_test_case.get_all_objects(simple_test_case.size()) == [
        simple_test_case.statements[0].ret_val,
        simple_test_case.statements[1].ret_val,
        simple_test_case.statements[2].ret_val,
        simple_test_case.statements[3].ret_val,
    ]


def test_get_all_objects_over_max_size(simple_test_case):
    assert simple_test_case.get_all_objects(2000) == [
        simple_test_case.statements[0].ret_val,
        simple_test_case.statements[1].ret_val,
        simple_test_case.statements[2].ret_val,
        simple_test_case.statements[3].ret_val,
    ]


def test_get_random_object_none_found(simple_test_case):
    with pytest.raises(ConstructionFailedException):
        simple_test_case.get_random_object(bool, simple_test_case.size())


def test_get_random_object_one(simple_test_case):
    assert (
        simple_test_case.get_random_object(int, 1)
        == simple_test_case.statements[0].ret_val
    )


def test_get_random_object_all(simple_test_case):
    assert simple_test_case.get_random_object(int, simple_test_case.size()) in [
        simple_test_case.statements[0].ret_val,
        simple_test_case.statements[1].ret_val,
    ]
