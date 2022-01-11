#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provide some fixtures for the export tests."""
import pytest

import pynguin.assertion.primitiveassertion as pas
import pynguin.testcase.defaulttestcase as dtc
from pynguin.testcase.statement import (
    ConstructorStatement,
    FloatPrimitiveStatement,
    FunctionStatement,
    IntPrimitiveStatement,
)


@pytest.fixture
def exportable_test_case(constructor_mock, function_mock):
    test_case = dtc.DefaultTestCase()
    int_stmt = IntPrimitiveStatement(test_case, 5)
    constructor_stmt = ConstructorStatement(
        test_case, constructor_mock, {"y": int_stmt.ret_val}
    )
    constructor_stmt.add_assertion(pas.PrimitiveAssertion(constructor_stmt.ret_val, 5))
    float_stmt = FloatPrimitiveStatement(test_case, 42.23)
    function_stmt = FunctionStatement(
        test_case, function_mock, {"z": float_stmt.ret_val}
    )
    function_stmt.add_assertion(pas.PrimitiveAssertion(function_stmt.ret_val, 42.23))
    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_stmt)
    test_case.add_statement(float_stmt)
    test_case.add_statement(function_stmt)
    return test_case
