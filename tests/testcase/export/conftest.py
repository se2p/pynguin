#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provide some fixtures for the export tests."""

import pytest

import pynguin.assertion.assertion as ass
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc

from pynguin.analyses.module import ModuleTestCluster
from pynguin.testcase.statement import ComplexPrimitiveStatement
from pynguin.testcase.statement import ConstructorStatement
from pynguin.testcase.statement import FloatPrimitiveStatement
from pynguin.testcase.statement import FunctionStatement
from pynguin.testcase.statement import IntPrimitiveStatement


@pytest.fixture
def exportable_test_case(constructor_mock, function_mock):
    test_case = dtc.DefaultTestCase(ModuleTestCluster(0))
    int_stmt = IntPrimitiveStatement(test_case, 5)
    constructor_stmt = ConstructorStatement(test_case, constructor_mock, {"y": int_stmt.ret_val})
    constructor_stmt.add_assertion(ass.ObjectAssertion(constructor_stmt.ret_val, 5))
    float_stmt = FloatPrimitiveStatement(test_case, 42.23)
    function_stmt = FunctionStatement(test_case, function_mock, {"z": float_stmt.ret_val})
    function_stmt.add_assertion(ass.FloatAssertion(function_stmt.ret_val, 42.23))
    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_stmt)
    test_case.add_statement(float_stmt)
    test_case.add_statement(function_stmt)
    return tcc.TestCaseChromosome(test_case)


@pytest.fixture
def exportable_test_case_with_expected_exception(function_mock):
    test_case = dtc.DefaultTestCase(ModuleTestCluster(0))
    float_stmt = FloatPrimitiveStatement(test_case, 42.23)
    function_mock._raised_exceptions = {"ValueError"}
    function_stmt = FunctionStatement(test_case, function_mock, {"z": float_stmt.ret_val})
    function_stmt.add_assertion(ass.ExceptionAssertion("builtins", "ValueError"))
    test_case.add_statement(float_stmt)
    test_case.add_statement(function_stmt)
    return tcc.TestCaseChromosome(test_case)


@pytest.fixture
def exportable_test_case_with_unexpected_exception(function_mock):
    test_case = dtc.DefaultTestCase(ModuleTestCluster(0))
    float_stmt = FloatPrimitiveStatement(test_case, 42.23)
    function_stmt = FunctionStatement(test_case, function_mock, {"z": float_stmt.ret_val})
    function_stmt.add_assertion(ass.ExceptionAssertion("builtins", "ValueError"))
    test_case.add_statement(float_stmt)
    test_case.add_statement(function_stmt)
    return tcc.TestCaseChromosome(test_case)


@pytest.fixture
def exportable_test_case_with_lambda(lambda_mock):
    test_case = dtc.DefaultTestCase(ModuleTestCluster(0))
    int_stmt = IntPrimitiveStatement(test_case, 1)
    lambda_stmt = FunctionStatement(test_case, lambda_mock, {"z": int_stmt.ret_val})
    test_case.add_statement(int_stmt)
    test_case.add_statement(lambda_stmt)
    return tcc.TestCaseChromosome(test_case)


@pytest.fixture
def exportable_test_case_with_lambda_complex(lambda_mock_complex):
    test_case = dtc.DefaultTestCase(ModuleTestCluster(0))
    complex_stmt_1 = ComplexPrimitiveStatement(test_case, 3 + 4j)
    complex_stmt_2 = ComplexPrimitiveStatement(test_case, 1 + 0j)
    float_stmt_1 = FloatPrimitiveStatement(test_case, 0.1)
    float_stmt_2 = FloatPrimitiveStatement(test_case, 0.3)
    lambda_stmt = FunctionStatement(
        test_case,
        lambda_mock_complex,
        {
            "x": complex_stmt_1.ret_val,
            "y": complex_stmt_2.ret_val,
            "w1": float_stmt_1.ret_val,
            "w2": float_stmt_2.ret_val,
        },
    )
    test_case.add_statement(complex_stmt_1)
    test_case.add_statement(complex_stmt_2)
    test_case.add_statement(float_stmt_1)
    test_case.add_statement(float_stmt_2)
    test_case.add_statement(lambda_stmt)
    return tcc.TestCaseChromosome(test_case)
