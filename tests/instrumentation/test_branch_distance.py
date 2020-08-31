#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
from unittest.mock import MagicMock, call

import pytest

from pynguin.instrumentation.branch_distance import BranchDistanceInstrumentation
from pynguin.testcase.execution.executiontracer import ExecutionTracer


@pytest.fixture()
def simple_module():
    simple = importlib.import_module("tests.fixtures.instrumentation.simple")
    simple = importlib.reload(simple)
    return simple


@pytest.fixture()
def tracer_mock():
    tracer = MagicMock()
    tracer.register_code_object.side_effect = range(100)
    tracer.register_predicate.side_effect = range(100)
    return tracer


def test_entered_function(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.simple_function.__code__ = instr._instrument_code_recursive(
        simple_module.simple_function.__code__, True
    )
    simple_module.simple_function(1)
    tracer_mock.register_code_object.assert_called_once()
    tracer_mock.executed_code_object.assert_called_once()


def test_entered_for_loop_no_jump(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.for_loop.__code__, True
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.for_loop(3)
    tracer_mock.executed_bool_predicate.assert_called_with(True, 0)


def test_entered_for_loop_no_jump_not_entered(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.for_loop.__code__, True
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.for_loop(0)
    tracer_mock.executed_bool_predicate.assert_called_with(False, 0)


def test_entered_for_loop_full_loop(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.full_for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.full_for_loop.__code__, True
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(3)
    tracer_mock.executed_bool_predicate.assert_called_with(True, 0)
    assert tracer_mock.executed_bool_predicate.call_count == 1


def test_entered_for_loop_full_loop_not_entered(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.full_for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.full_for_loop.__code__, True
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(0)
    tracer_mock.executed_bool_predicate.assert_called_with(False, 0)


def test_add_bool_predicate(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.bool_predicate.__code__ = instr._instrument_code_recursive(
        simple_module.bool_predicate.__code__, True
    )
    simple_module.bool_predicate(True)
    tracer_mock.register_predicate.assert_called_once()
    tracer_mock.executed_bool_predicate.assert_called_once()


def test_add_cmp_predicate(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.cmp_predicate.__code__ = instr._instrument_code_recursive(
        simple_module.cmp_predicate.__code__, True
    )
    simple_module.cmp_predicate(1, 2)
    tracer_mock.register_predicate.assert_called_once()
    tracer_mock.executed_compare_predicate.assert_called_once()


def test_transform_for_loop_multi(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.multi_loop.__code__ = instr._instrument_code_recursive(
        simple_module.multi_loop.__code__, True
    )
    assert simple_module.multi_loop(5) == 25
    assert tracer_mock.register_predicate.call_count == 3
    calls = [
        call(True, 0),
        call(True, 1),
        call(True, 1),
        call(True, 1),
        call(True, 1),
        call(True, 1),
        call(False, 2),
    ]
    assert tracer_mock.executed_bool_predicate.call_count == len(calls)
    tracer_mock.executed_bool_predicate.assert_has_calls(calls)


def test_add_cmp_predicate_loop_comprehension(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.comprehension.__code__ = instr._instrument_code_recursive(
        simple_module.comprehension.__code__, True
    )
    call_count = 5
    simple_module.comprehension(call_count, 3)
    assert tracer_mock.register_predicate.call_count == 2
    assert tracer_mock.executed_compare_predicate.call_count == call_count
    tracer_mock.executed_bool_predicate.assert_has_calls([call(True, 1)])


def test_add_cmp_predicate_lambda(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.lambda_func.__code__ = instr._instrument_code_recursive(
        simple_module.lambda_func.__code__, True
    )
    lam = simple_module.lambda_func(10)
    lam(5)
    tracer_mock.register_predicate.assert_called_once()
    assert tracer_mock.register_code_object.call_count == 2
    tracer_mock.executed_compare_predicate.assert_called_once()
    tracer_mock.executed_code_object.assert_has_calls(
        [call(0), call(1)], any_order=True
    )


def test_conditional_assignment(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.conditional_assignment.__code__ = instr._instrument_code_recursive(
        simple_module.conditional_assignment.__code__, True
    )
    simple_module.conditional_assignment(10)
    tracer_mock.register_predicate.assert_called_once()
    assert tracer_mock.register_code_object.call_count == 1
    tracer_mock.executed_compare_predicate.assert_called_once()
    tracer_mock.executed_code_object.assert_has_calls([call(0)])


def test_conditionally_nested_class(simple_module, tracer_mock):
    instr = BranchDistanceInstrumentation(tracer_mock)
    simple_module.conditionally_nested_class.__code__ = (
        instr._instrument_code_recursive(
            simple_module.conditionally_nested_class.__code__, True
        )
    )
    assert tracer_mock.register_code_object.call_count == 3

    simple_module.conditionally_nested_class(6)
    tracer_mock.executed_code_object.assert_has_calls(
        [call(0), call(1), call(2)], any_order=True
    )
    tracer_mock.register_predicate.assert_called_once()
    tracer_mock.executed_compare_predicate.assert_called_once()


def test_avoid_duplicate_instrumentation(simple_module):
    tracer = MagicMock(ExecutionTracer)
    instr = BranchDistanceInstrumentation(tracer)
    already_instrumented = instr.instrument_module(simple_module.cmp_predicate.__code__)
    with pytest.raises(AssertionError):
        instr.instrument_module(already_instrumented)
