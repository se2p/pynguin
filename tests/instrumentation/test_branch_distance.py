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
import asyncio
from unittest import mock

import pytest
from unittest.mock import Mock, call
from pynguin.instrumentation.branch_distance import BranchDistanceInstrumentation


@pytest.fixture()
def simple_module():
    simple = importlib.import_module("tests.fixtures.instrumentation.simple")
    simple = importlib.reload(simple)
    return simple


def test_entered_function(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.simple_function)
    simple_module.simple_function(1)
    tracer.code_object_exists.assert_called_once()
    tracer.entered_code_object.assert_called_once()


def test_entered_for_loop_no_jump(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.for_loop)
    tracer.predicate_exists.assert_has_calls([call(0)])
    simple_module.for_loop(3)
    tracer.passed_bool_predicate.assert_called_with(True, 0)


def test_entered_for_loop_no_jump_not_entered(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.for_loop)
    tracer.predicate_exists.assert_has_calls([call(0)])
    simple_module.for_loop(0)
    tracer.passed_bool_predicate.assert_called_with(False, 0)


def test_entered_for_loop_full_loop(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.full_for_loop)
    tracer.predicate_exists.assert_has_calls([call(0)])
    simple_module.full_for_loop(3)
    tracer.passed_bool_predicate.assert_called_with(True, 0)


def test_entered_for_loop_full_loop_not_entered(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.full_for_loop)
    tracer.predicate_exists.assert_has_calls([call(0)])
    simple_module.full_for_loop(0)
    tracer.passed_bool_predicate.assert_called_with(False, 0)


def test_add_bool_predicate(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.bool_predicate)
    simple_module.bool_predicate(True)
    tracer.predicate_exists.assert_called_once()
    tracer.passed_bool_predicate.assert_called_once()


def test_add_cmp_predicate(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.cmp_predicate)
    simple_module.cmp_predicate(1, 2)
    tracer.predicate_exists.assert_called_once()
    tracer.passed_cmp_predicate.assert_called_once()


def test_add_cmp_predicate_loop_comprehension(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.comprehension)
    call_count = 5
    simple_module.comprehension(call_count, 3)
    tracer.predicate_exists.assert_has_calls([call(0), call(1)], any_order=True)
    assert tracer.passed_cmp_predicate.call_count == call_count
    tracer.passed_bool_predicate.assert_has_calls([call(True, 0)])


def test_add_cmp_predicate_lambda(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.lambda_func)
    lam = simple_module.lambda_func(10)
    lam(5)
    tracer.predicate_exists.assert_called_once()
    tracer.code_object_exists.assert_has_calls([call(0), call(1)])
    tracer.passed_cmp_predicate.assert_called_once()
    tracer.entered_code_object.assert_has_calls([call(0), call(1)], any_order=True)


def test_conditionally_nested_class(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.conditionally_nested_class)
    tracer.code_object_exists.assert_has_calls(
        [call(0), call(1), call(2)], any_order=True
    )

    simple_module.conditionally_nested_class(6)
    tracer.entered_code_object.assert_has_calls(
        [call(0), call(1), call(2)], any_order=True
    )
    tracer.predicate_exists.assert_has_calls([call(0)])
    tracer.passed_cmp_predicate.assert_called_once()


def test_avoid_duplicate_instrumentation(simple_module):
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument_function(simple_module.cmp_predicate)
    with pytest.raises(AssertionError):
        instr.instrument_function(simple_module.cmp_predicate)


def test_module_instrumentation_integration():
    """Small integration test, which tests the instrumentation for various function types."""
    mixed = importlib.import_module("tests.fixtures.instrumentation.mixed")
    mixed = importlib.reload(mixed)
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    instr.instrument(mixed, "tests.fixtures.instrumentation.mixed")

    inst = mixed.TestClass(5)
    inst.method(5)
    inst.method_with_nested(5)
    mixed.function(5)
    sum(mixed.generator())
    asyncio.run(mixed.coroutine(5))
    asyncio.run(run_async_generator(mixed.async_generator()))

    # The number of functions defined in mixed
    call_count = 8
    calls: list = [call(i) for i in range(call_count)]

    tracer.code_object_exists.assert_has_calls(calls, any_order=True)
    assert tracer.code_object_exists.call_count == call_count
    tracer.entered_code_object.assert_has_calls(calls, any_order=True)
    assert tracer.entered_code_object.call_count == call_count


async def run_async_generator(gen):
    """Small helper to execute async generator"""
    the_sum = 0
    async for i in gen:
        the_sum += i
    return the_sum


def test_instrument_recursion():
    tracer = Mock()
    instr = BranchDistanceInstrumentation(tracer)
    with mock.patch("inspect.getmembers") as member_mock:
        instr.instrument(1, "something", {1})
        member_mock.assert_not_called()
