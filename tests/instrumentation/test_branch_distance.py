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

import importlib

import pytest
from unittest.mock import Mock, call, MagicMock
from pynguin.instrumentation.branch_distance import BranchDistanceInstrumentation
from pynguin.testcase.execution.executiontracer import ExecutionTracer


@pytest.fixture()
def simple_module():
    simple = importlib.import_module("tests.fixtures.instrumentation.simple")
    simple = importlib.reload(simple)
    return simple


def test_entered_function(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.simple_function.__code__ = instr._instrument_code_recursive(
        simple_module.simple_function.__code__, True
    )
    simple_module.simple_function(1)
    tracer.code_object_exists.assert_called_once()
    tracer.entered_code_object.assert_called_once()


def test_entered_for_loop_no_jump(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.for_loop.__code__, True
    )
    tracer.predicate_exists.assert_has_calls([call(0)])
    simple_module.for_loop(3)
    tracer.passed_bool_predicate.assert_called_with(True, 0)


def test_entered_for_loop_no_jump_not_entered(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.for_loop.__code__, True
    )
    tracer.predicate_exists.assert_has_calls([call(0)])
    simple_module.for_loop(0)
    tracer.passed_bool_predicate.assert_called_with(False, 0)


def test_entered_for_loop_full_loop(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.full_for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.full_for_loop.__code__, True
    )
    tracer.predicate_exists.assert_has_calls([call(0)])
    simple_module.full_for_loop(3)
    tracer.passed_bool_predicate.assert_called_with(True, 0)


def test_entered_for_loop_full_loop_not_entered(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.full_for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.full_for_loop.__code__, True
    )
    tracer.predicate_exists.assert_has_calls([call(0)])
    simple_module.full_for_loop(0)
    tracer.passed_bool_predicate.assert_called_with(False, 0)


def test_add_bool_predicate(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.bool_predicate.__code__ = instr._instrument_code_recursive(
        simple_module.bool_predicate.__code__, True
    )
    simple_module.bool_predicate(True)
    tracer.predicate_exists.assert_called_once()
    tracer.passed_bool_predicate.assert_called_once()


def test_add_cmp_predicate(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.cmp_predicate.__code__ = instr._instrument_code_recursive(
        simple_module.cmp_predicate.__code__, True
    )
    simple_module.cmp_predicate(1, 2)
    tracer.predicate_exists.assert_called_once()
    tracer.passed_cmp_predicate.assert_called_once()


def test_add_cmp_predicate_loop_comprehension(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.comprehension.__code__ = instr._instrument_code_recursive(
        simple_module.comprehension.__code__, True
    )
    call_count = 5
    simple_module.comprehension(call_count, 3)
    tracer.predicate_exists.assert_has_calls([call(0), call(1)], any_order=True)
    assert tracer.passed_cmp_predicate.call_count == call_count
    tracer.passed_bool_predicate.assert_has_calls([call(True, 0)])


def test_add_cmp_predicate_lambda(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.lambda_func.__code__ = instr._instrument_code_recursive(
        simple_module.lambda_func.__code__, True
    )
    lam = simple_module.lambda_func(10)
    lam(5)
    tracer.predicate_exists.assert_called_once()
    assert tracer.code_object_exists.call_count == 2
    tracer.passed_cmp_predicate.assert_called_once()
    tracer.entered_code_object.assert_has_calls([call(0), call(1)], any_order=True)


def test_conditional_assignment(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.conditional_assignment.__code__ = instr._instrument_code_recursive(
        simple_module.conditional_assignment.__code__, True
    )
    simple_module.conditional_assignment(10)
    tracer.predicate_exists.assert_called_once()
    assert tracer.code_object_exists.call_count == 1
    tracer.passed_cmp_predicate.assert_called_once()
    tracer.entered_code_object.assert_has_calls([call(0)])


def test_conditionally_nested_class(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    simple_module.conditionally_nested_class.__code__ = instr._instrument_code_recursive(
        simple_module.conditionally_nested_class.__code__, True
    )
    assert tracer.code_object_exists.call_count == 3

    simple_module.conditionally_nested_class(6)
    tracer.entered_code_object.assert_has_calls(
        [call(0), call(1), call(2)], any_order=True
    )
    tracer.predicate_exists.assert_has_calls([call(0)])
    tracer.passed_cmp_predicate.assert_called_once()


def test_avoid_duplicate_instrumentation(simple_module):
    tracer = MagicMock(ExecutionTracer)
    instr = BranchDistanceInstrumentation(tracer)
    already_instrumented = instr.instrument_module(simple_module.cmp_predicate.__code__)
    with pytest.raises(AssertionError):
        instr.instrument_module(already_instrumented)


def test_get_name():
    code = compile("a = 5", "somefile", "exec")
    assert BranchDistanceInstrumentation._get_name(code) == "somefile.<module>:1"
