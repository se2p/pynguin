#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Some integration tests for the testcase/statements."""

import math

import pytest

import pynguin.assertion.assertion as ass
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as st

from pynguin.utils.exceptions import ConstructionFailedException


def test_method_statement_clone(default_test_case, method_mock):
    int_prim = st.IntPrimitiveStatement(default_test_case, 5)
    str_prim = st.StringPrimitiveStatement(default_test_case, "TestThis")
    method_stmt = st.MethodStatement(
        default_test_case,
        method_mock,
        str_prim.ret_val,
        {"x": int_prim.ret_val},
    )
    default_test_case.add_statement(int_prim)
    default_test_case.add_statement(str_prim)
    default_test_case.add_statement(method_stmt)

    cloned = default_test_case.clone()
    assert isinstance(cloned.statements[2], st.MethodStatement)
    assert cloned.statements[2] is not method_stmt


def test_constructor_statement_clone(default_test_case, constructor_mock):
    int_prim = st.IntPrimitiveStatement(default_test_case, 5)
    method_stmt = st.ConstructorStatement(
        default_test_case,
        constructor_mock,
        {"y": int_prim.ret_val},
    )
    default_test_case.add_statement(int_prim)
    default_test_case.add_statement(method_stmt)

    cloned = default_test_case.clone()
    assert isinstance(cloned.statements[1], st.ConstructorStatement)
    assert cloned.statements[1] is not method_stmt
    assert cloned.statements[0].ret_val is not default_test_case.statements[0].ret_val


def test_assignment_statement_clone(default_test_case):
    int_prim = st.IntPrimitiveStatement(default_test_case, 5)
    int_prim2 = st.IntPrimitiveStatement(default_test_case, 10)
    # TODO(fk) the assignment statement from EvoSuite might not be fitting for our case?
    # Because currently we can only overwrite existing values?
    assignment_stmt = st.AssignmentStatement(default_test_case, int_prim.ret_val, int_prim2.ret_val)
    default_test_case.add_statement(int_prim)
    default_test_case.add_statement(int_prim2)
    default_test_case.add_statement(assignment_stmt)

    cloned = default_test_case.clone()
    assert isinstance(cloned.statements[2], st.AssignmentStatement)
    assert cloned.statements[2] is not assignment_stmt


@pytest.fixture
def simple_test_case(function_mock, default_test_case) -> dtc.DefaultTestCase:
    int_prim = st.IntPrimitiveStatement(default_test_case, 5)
    int_prim2 = st.IntPrimitiveStatement(default_test_case, 5)
    float_prim = st.FloatPrimitiveStatement(default_test_case, 5.5)
    func = st.FunctionStatement(default_test_case, function_mock, {"z": float_prim.ret_val})
    func.add_assertion(ass.ObjectAssertion(func.ret_val, math.pi))
    string_prim = st.StringPrimitiveStatement(default_test_case, "Test")
    string_prim.ret_val._type = default_test_case.test_cluster.type_system.convert_type_hint(
        type(None)
    )
    default_test_case.add_statement(int_prim)
    default_test_case.add_statement(int_prim2)
    default_test_case.add_statement(float_prim)
    default_test_case.add_statement(func)
    default_test_case.add_statement(string_prim)
    return default_test_case


def test_clone_with_assertion(simple_test_case):
    cloned = simple_test_case.clone()
    assert len(cloned.get_statement(3).assertions) == 1


def test_test_case_equals_on_different_prim(
    simple_test_case: dtc.DefaultTestCase, constructor_mock
):
    cloned = simple_test_case.clone()

    # Original points to int at 0
    simple_test_case.add_statement(
        st.ConstructorStatement(
            simple_test_case,
            constructor_mock,
            {"y": simple_test_case.statements[0].ret_val},
        )
    )
    # Clone points to int at 1
    cloned.add_statement(
        st.ConstructorStatement(cloned, constructor_mock, {"y": cloned.statements[1].ret_val})
    )

    # Even though they both point to an int, they are not equal
    assert simple_test_case != cloned


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
        simple_test_case.get_random_object(
            simple_test_case.test_cluster.type_system.convert_type_hint(int), 1
        )
        == simple_test_case.statements[0].ret_val
    )


def test_get_random_object_all(simple_test_case):
    assert simple_test_case.get_random_object(
        simple_test_case.test_cluster.type_system.convert_type_hint(int),
        simple_test_case.size(),
    ) in {
        simple_test_case.statements[0].ret_val,
        simple_test_case.statements[1].ret_val,
    }
