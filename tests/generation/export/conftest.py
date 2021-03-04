#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provide some fixtures for the export tests."""
import pytest

import pynguin.assertion.primitiveassertion as pas
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt


@pytest.fixture
def exportable_test_case(constructor_mock, function_mock):
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, 5)
    constructor_stmt = param_stmt.ConstructorStatement(
        test_case, constructor_mock, [int_stmt.ret_val]
    )
    constructor_stmt.add_assertion(pas.PrimitiveAssertion(constructor_stmt.ret_val, 5))
    float_stmt = prim_stmt.FloatPrimitiveStatement(test_case, 42.23)
    function_stmt = param_stmt.FunctionStatement(
        test_case, function_mock, [float_stmt.ret_val]
    )
    function_stmt.add_assertion(pas.PrimitiveAssertion(function_stmt.ret_val, 42.23))
    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_stmt)
    test_case.add_statement(float_stmt)
    test_case.add_statement(function_stmt)
    return test_case
