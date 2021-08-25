#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

import pynguin.assertion.primitiveassertion as pas
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt


@pytest.fixture
def benchmark_test_case(constructor_mock, function_mock):
    """Create a test case with a moderately large structure."""
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, 5)
    constructor_stmt = param_stmt.ConstructorStatement(
        test_case,
        constructor_mock,
        {"y": int_stmt.ret_val, "z": int_stmt.ret_val, "zz": int_stmt.ret_val},
    )
    constructor_stmt.add_assertion(pas.PrimitiveAssertion(constructor_stmt.ret_val, 5))
    float_stmt = prim_stmt.FloatPrimitiveStatement(test_case, 42.23)
    function_stmt = param_stmt.FunctionStatement(
        test_case,
        function_mock,
        {"z": float_stmt.ret_val, "y": int_stmt.ret_val, "zz": int_stmt.ret_val},
    )
    function_stmt.add_assertion(pas.PrimitiveAssertion(function_stmt.ret_val, 42.23))
    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_stmt)
    test_case.add_statement(float_stmt)
    test_case.add_statement(function_stmt)
    # Duplicate size four times.
    test_case.append_test_case(test_case.clone())
    test_case.append_test_case(test_case.clone())
    test_case.append_test_case(test_case.clone())
    test_case.append_test_case(test_case.clone())
    return test_case


# Turn this up for more precise measurements.
BENCHMARK_REPETITIONS = 2


def test_benchmark_eq(benchmark_test_case):
    cloned = benchmark_test_case.clone()
    res = all([benchmark_test_case == cloned for _ in range(BENCHMARK_REPETITIONS)])
    assert res


def test_benchmark_hash(benchmark_test_case):
    assert len({benchmark_test_case.clone() for _ in range(BENCHMARK_REPETITIONS)}) == 1


def test_benchmark_clone(benchmark_test_case):
    cloned = benchmark_test_case.clone()
    for i in range(BENCHMARK_REPETITIONS):
        cloned = cloned.clone()
    assert cloned == benchmark_test_case
