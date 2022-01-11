#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
import os
import threading
from unittest import mock
from unittest.mock import MagicMock, call

import pytest
from bytecode import Compare

from pynguin.analyses.seeding.constantseeding import DynamicConstantSeeding
from pynguin.instrumentation.instrumentation import (
    BranchCoverageInstrumentation,
    DynamicSeedingInstrumentation, StatementCoverageInstrumentation,
)
from pynguin.testcase.execution import ExecutionTracer
from tests.conftest import python38, python39plus


@pytest.fixture()
def simple_module():
    simple = importlib.import_module("tests.fixtures.instrumentation.simple")
    simple = importlib.reload(simple)
    return simple


@pytest.fixture()
def comparison_module():
    comparison = importlib.import_module("tests.fixtures.instrumentation.comparison")
    comparison = importlib.reload(comparison)
    return comparison


@pytest.fixture()
def tracer_mock():
    tracer = MagicMock()
    tracer.register_code_object.side_effect = range(100)
    tracer.register_predicate.side_effect = range(100)
    return tracer


def test_entered_function(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.simple_function.__code__ = instr._instrument_code_recursive(
        simple_module.simple_function.__code__, True
    )
    simple_module.simple_function(1)
    tracer_mock.register_code_object.assert_called_once()
    tracer_mock.executed_code_object.assert_called_once()


def test_entered_for_loop_no_jump(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.for_loop.__code__, True
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.for_loop(3)
    tracer_mock.executed_bool_predicate.assert_called_with(True, 0)


def test_entered_for_loop_no_jump_not_entered(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.for_loop.__code__, True
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.for_loop(0)
    tracer_mock.executed_bool_predicate.assert_called_with(False, 0)


def test_entered_for_loop_full_loop(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.full_for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.full_for_loop.__code__, True
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(3)
    tracer_mock.executed_bool_predicate.assert_has_calls(
        [call(True, 0), call(True, 0), call(True, 0), call(False, 0)]
    )
    assert tracer_mock.executed_bool_predicate.call_count == 4


def test_entered_for_loop_full_loop_not_entered(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.full_for_loop.__code__ = instr._instrument_code_recursive(
        simple_module.full_for_loop.__code__, True
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(0)
    tracer_mock.executed_bool_predicate.assert_called_with(False, 0)


def test_add_bool_predicate(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.bool_predicate.__code__ = instr._instrument_code_recursive(
        simple_module.bool_predicate.__code__, True
    )
    simple_module.bool_predicate(True)
    tracer_mock.register_predicate.assert_called_once()
    tracer_mock.executed_bool_predicate.assert_called_once()


def test_add_cmp_predicate(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.cmp_predicate.__code__ = instr._instrument_code_recursive(
        simple_module.cmp_predicate.__code__, True
    )
    simple_module.cmp_predicate(1, 2)
    tracer_mock.register_predicate.assert_called_once()
    tracer_mock.executed_compare_predicate.assert_called_once()


def test_transform_for_loop_multi(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.multi_loop.__code__ = instr._instrument_code_recursive(
        simple_module.multi_loop.__code__, True
    )
    assert simple_module.multi_loop(2) == 4
    assert tracer_mock.register_predicate.call_count == 3
    calls = [call(True, 0), call(True, 1), call(True, 1), call(False, 1)] * 2 + [
        call(False, 0),
        call(False, 2),
    ]
    assert tracer_mock.executed_bool_predicate.call_count == len(calls)
    tracer_mock.executed_bool_predicate.assert_has_calls(calls)


def test_add_cmp_predicate_loop_comprehension(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.comprehension.__code__ = instr._instrument_code_recursive(
        simple_module.comprehension.__code__, True
    )
    call_count = 5
    simple_module.comprehension(call_count, 3)
    assert tracer_mock.register_predicate.call_count == 2
    assert tracer_mock.executed_compare_predicate.call_count == call_count
    tracer_mock.executed_bool_predicate.assert_has_calls([call(True, 1)])


def test_add_cmp_predicate_lambda(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
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
    instr = BranchCoverageInstrumentation(tracer_mock)
    simple_module.conditional_assignment.__code__ = instr._instrument_code_recursive(
        simple_module.conditional_assignment.__code__, True
    )
    simple_module.conditional_assignment(10)
    tracer_mock.register_predicate.assert_called_once()
    assert tracer_mock.register_code_object.call_count == 1
    tracer_mock.executed_compare_predicate.assert_called_once()
    tracer_mock.executed_code_object.assert_has_calls([call(0)])


def test_conditionally_nested_class(simple_module, tracer_mock):
    instr = BranchCoverageInstrumentation(tracer_mock)
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
    tracer.register_code_object.return_value = 0
    instr = BranchCoverageInstrumentation(tracer)
    already_instrumented = instr.instrument_module(simple_module.cmp_predicate.__code__)
    with pytest.raises(AssertionError):
        instr.instrument_module(already_instrumented)


@pytest.mark.parametrize(
    "function_name, branchless_function_count, branches_count",
    [
        pytest.param("simple_function", 1, 0),
        pytest.param("cmp_predicate", 0, 1),
        pytest.param("bool_predicate", 0, 1),
        pytest.param("for_loop", 0, 1),
        pytest.param("full_for_loop", 0, 1),
        pytest.param("multi_loop", 0, 3),
        pytest.param("comprehension", 1, 2),
        pytest.param("lambda_func", 1, 1),
        pytest.param("conditional_assignment", 0, 1),
        pytest.param("conditionally_nested_class", 2, 1),
    ],
)
def test_integrate_branch_distance_instrumentation(
    simple_module,
    function_name,
    branchless_function_count,
    branches_count,
):
    tracer = ExecutionTracer()
    function_callable = getattr(simple_module, function_name)
    instr = BranchCoverageInstrumentation(tracer)
    function_callable.__code__ = instr._instrument_code_recursive(
        function_callable.__code__, 0
    )
    assert (
        len(tracer.get_known_data().branch_less_code_objects)
        == branchless_function_count
    )
    assert len(list(tracer.get_known_data().existing_predicates)) == branches_count


def test_integrate_statement_coverage_instrumentation(
    simple_module
):
    tracer = ExecutionTracer()
    function_callable = getattr(simple_module, "multi_loop")
    instr = StatementCoverageInstrumentation(tracer)
    function_callable.__code__ = instr._instrument_code_recursive(
        function_callable.__code__, 0
    )

    # only one file was instrumented
    assert (
        len(tracer.get_known_data().existing_statements)
        == 1
    )
    # the body of the method contains 7 statements on lines 38 to 44
    assert (
        list(tracer.get_known_data().existing_statements.values())[0]
        == {38, 39, 40, 41, 42, 43, 44}
    )


@pytest.mark.parametrize(
    "op",
    [pytest.param(op) for op in Compare if op != Compare.EXC_MATCH],
)
def test_comparison(comparison_module, op):
    tracer = ExecutionTracer()
    function_callable = getattr(comparison_module, "_" + op.name.lower())
    instr = BranchCoverageInstrumentation(tracer)
    function_callable.__code__ = instr._instrument_code_recursive(
        function_callable.__code__, 0
    )
    with mock.patch.object(tracer, "executed_compare_predicate") as trace_mock:
        function_callable("a", "a")
        trace_mock.assert_called_with("a", "a", 0, op)


@python38
def test_exception():
    tracer = ExecutionTracer()

    def func():
        try:
            raise ValueError()
        except ValueError:
            pass

    instr = BranchCoverageInstrumentation(tracer)
    func.__code__ = instr._instrument_code_recursive(func.__code__, 0)
    with mock.patch.object(tracer, "executed_bool_predicate") as trace_mock:
        func()
        trace_mock.assert_called_with(True, 0)


@python38
def test_exception_no_match():
    tracer = ExecutionTracer()

    def func():
        try:
            raise RuntimeError()
        except ValueError:
            pass  # pragma: no cover

    instr = BranchCoverageInstrumentation(tracer)
    func.__code__ = instr._instrument_code_recursive(func.__code__, 0)
    with mock.patch.object(tracer, "executed_bool_predicate") as trace_mock:
        with pytest.raises(RuntimeError):
            func()
        trace_mock.assert_called_with(False, 0)


@python39plus
def test_exception_39plus():
    tracer = ExecutionTracer()

    def func():
        try:
            raise ValueError()
        except ValueError:
            pass

    instr = BranchCoverageInstrumentation(tracer)
    func.__code__ = instr._instrument_code_recursive(func.__code__, 0)
    with mock.patch.object(tracer, "executed_exception_match") as trace_mock:
        func()
        trace_mock.assert_called_with(ValueError, ValueError, 0)


@python39plus
def test_exception_no_match_39plus():
    tracer = ExecutionTracer()

    def func():
        try:
            raise RuntimeError()
        except ValueError:
            pass

    instr = BranchCoverageInstrumentation(tracer)
    func.__code__ = instr._instrument_code_recursive(func.__code__, 0)
    with mock.patch.object(tracer, "executed_exception_match") as trace_mock:
        with pytest.raises(RuntimeError):
            func()
        trace_mock.assert_called_with(RuntimeError, ValueError, 0)


def test_exception_integrate():
    tracer = ExecutionTracer()

    def func():
        try:
            raise ValueError()
        except ValueError:
            pass

    instr = BranchCoverageInstrumentation(tracer)
    func.__code__ = instr._instrument_code_recursive(func.__code__, 0)
    tracer.current_thread_identifier = threading.current_thread().ident
    func()
    assert {0} == tracer.get_trace().executed_code_objects
    assert {0: 1} == tracer.get_trace().executed_predicates
    assert {0: 0.0} == tracer.get_trace().true_distances
    assert {0: 1.0} == tracer.get_trace().false_distances


def test_exception_no_match_integrate():
    tracer = ExecutionTracer()

    def func():
        try:
            raise RuntimeError()
        except ValueError:
            pass  # pragma: no cover

    instr = BranchCoverageInstrumentation(tracer)
    func.__code__ = instr._instrument_code_recursive(func.__code__, 0)
    tracer.current_thread_identifier = threading.current_thread().ident
    with pytest.raises(RuntimeError):
        func()
    assert {0} == tracer.get_trace().executed_code_objects
    assert {0: 1} == tracer.get_trace().executed_predicates
    assert {0: 1.0} == tracer.get_trace().true_distances
    assert {0: 0.0} == tracer.get_trace().false_distances


def test_tracking_covered_statements_explicit_return():
    tracer = ExecutionTracer()

    def func():
        a = 42
        if a:
            a = "foo"
        else:
            a = "bar"
        return None

    instr = StatementCoverageInstrumentation(tracer)
    func.__code__ = instr._instrument_code_recursive(func.__code__, 0)
    tracer.current_thread_identifier = threading.current_thread().ident
    func()
    covered_lines = list(tracer.get_trace().covered_statements.values())[0]
    assert {385, 386, 387, 390} == covered_lines


def test_tracking_covered_statements_implicit_return():
    tracer = ExecutionTracer()

    def func():
        a = 42
        if a:
            a = "foo"
        else:
            a = "bar"

    instr = StatementCoverageInstrumentation(tracer)
    func.__code__ = instr._instrument_code_recursive(func.__code__, 0)
    tracer.current_thread_identifier = threading.current_thread().ident
    func()
    covered_lines = list(tracer.get_trace().covered_statements.values())[0]
    assert {404, 405, 406} == covered_lines


@pytest.fixture()
def dynamic_instr():
    dynamic_constants = DynamicConstantSeeding()
    instr = DynamicSeedingInstrumentation(dynamic_constants)
    return dynamic_constants, instr


@pytest.fixture()
def dummy_module():
    dummy_module = importlib.import_module(
        "tests.fixtures.seeding.dynamicseeding.dynamicseedingdummies"
    )
    dummy_module = importlib.reload(dummy_module)
    return dummy_module


def test_compare_op_int(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(
        dummy_module.compare_op_dummy.__code__
    )
    res = dummy_module.compare_op_dummy(10, 11)

    assert res == 1
    assert 10 in dynamic._dynamic_pool[int]
    assert 11 in dynamic._dynamic_pool[int]


def test_compare_op_float(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(
        dummy_module.compare_op_dummy.__code__
    )
    res = dummy_module.compare_op_dummy(1.0, 2.5)

    assert res == 1
    assert 1.0 in dynamic._dynamic_pool[float]
    assert 2.5 in dynamic._dynamic_pool[float]


def test_compare_op_string(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(
        dummy_module.compare_op_dummy.__code__
    )
    res = dummy_module.compare_op_dummy("abc", "def")

    assert res == 1
    assert "abc" in dynamic._dynamic_pool[str]
    assert "def" in dynamic._dynamic_pool[str]


def test_compare_op_other_type(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(
        dummy_module.compare_op_dummy.__code__
    )
    res = dummy_module.compare_op_dummy(True, "def")

    assert res == 1
    assert not dynamic.has_ints
    assert not dynamic.has_floats
    assert dynamic.has_strings
    assert "def" in dynamic._dynamic_pool[str]


def test_startswith_function(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.startswith_dummy.__code__ = instr.instrument_module(
        dummy_module.startswith_dummy.__code__
    )
    res = dummy_module.startswith_dummy("abc", "ab")

    assert res == 0
    assert dynamic.has_strings
    assert "ababc" in dynamic._dynamic_pool[str]


def test_endswith_function(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.endswith_dummy.__code__ = instr.instrument_module(
        dummy_module.endswith_dummy.__code__
    )
    res = dummy_module.endswith_dummy("abc", "bc")

    assert res == 0
    assert dynamic.has_strings
    assert "abcbc" in dynamic._dynamic_pool[str]


def test_isalnum_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isalnum_dummy.__code__ = instr.instrument_module(
        dummy_module.isalnum_dummy.__code__
    )
    res = dummy_module.isalnum_dummy("alnumtest")

    assert res == 0
    assert dynamic.has_strings
    assert "alnumtest" in dynamic._dynamic_pool[str]
    assert "alnumtest!" in dynamic._dynamic_pool[str]


def test_isalnum_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isalnum_dummy.__code__ = instr.instrument_module(
        dummy_module.isalnum_dummy.__code__
    )
    res = dummy_module.isalnum_dummy("alnum_test")

    assert res == 1
    assert dynamic.has_strings
    assert "alnum_test" in dynamic._dynamic_pool[str]
    assert "isalnum" in dynamic._dynamic_pool[str]


def test_islower_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.islower_dummy.__code__ = instr.instrument_module(
        dummy_module.islower_dummy.__code__
    )
    res = dummy_module.islower_dummy("lower")

    assert res == 0
    assert dynamic.has_strings
    assert "lower" in dynamic._dynamic_pool[str]
    assert "LOWER" in dynamic._dynamic_pool[str]


def test_islower_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.islower_dummy.__code__ = instr.instrument_module(
        dummy_module.islower_dummy.__code__
    )
    res = dummy_module.islower_dummy("NotLower")

    assert res == 1
    assert dynamic.has_strings
    assert "NotLower" in dynamic._dynamic_pool[str]
    assert "notlower" in dynamic._dynamic_pool[str]


def test_isupper_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isupper_dummy.__code__ = instr.instrument_module(
        dummy_module.isupper_dummy.__code__
    )
    res = dummy_module.isupper_dummy("UPPER")

    assert res == 0
    assert dynamic.has_strings
    assert "UPPER" in dynamic._dynamic_pool[str]
    assert "upper" in dynamic._dynamic_pool[str]


def test_isupper_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isupper_dummy.__code__ = instr.instrument_module(
        dummy_module.isupper_dummy.__code__
    )
    res = dummy_module.isupper_dummy("NotUpper")

    assert res == 1
    assert dynamic.has_strings
    assert "NotUpper" in dynamic._dynamic_pool[str]
    assert "NOTUPPER" in dynamic._dynamic_pool[str]


def test_isdecimal_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isdecimal_dummy.__code__ = instr.instrument_module(
        dummy_module.isdecimal_dummy.__code__
    )
    res = dummy_module.isdecimal_dummy("012345")

    assert res == 0
    assert dynamic.has_strings
    assert "012345" in dynamic._dynamic_pool[str]
    assert "non_decimal" in dynamic._dynamic_pool[str]


def test_isdecimal_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isdecimal_dummy.__code__ = instr.instrument_module(
        dummy_module.isdecimal_dummy.__code__
    )
    res = dummy_module.isdecimal_dummy("not_decimal")

    assert res == 1
    assert dynamic.has_strings
    assert "not_decimal" in dynamic._dynamic_pool[str]
    assert "0123456789" in dynamic._dynamic_pool[str]


def test_isalpha_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isalpha_dummy.__code__ = instr.instrument_module(
        dummy_module.isalpha_dummy.__code__
    )
    res = dummy_module.isalpha_dummy("alpha")

    assert res == 0
    assert dynamic.has_strings
    assert "alpha" in dynamic._dynamic_pool[str]
    assert "alpha1" in dynamic._dynamic_pool[str]


def test_isalpha_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isalpha_dummy.__code__ = instr.instrument_module(
        dummy_module.isalpha_dummy.__code__
    )
    res = dummy_module.isalpha_dummy("not_alpha")

    assert res == 1
    assert dynamic.has_strings
    assert "not_alpha" in dynamic._dynamic_pool[str]
    assert "isalpha" in dynamic._dynamic_pool[str]


def test_isdigit_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isdigit_dummy.__code__ = instr.instrument_module(
        dummy_module.isdigit_dummy.__code__
    )
    res = dummy_module.isdigit_dummy("012345")

    assert res == 0
    assert dynamic.has_strings
    assert "012345" in dynamic._dynamic_pool[str]
    assert "012345_" in dynamic._dynamic_pool[str]


def test_isdigit_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isdigit_dummy.__code__ = instr.instrument_module(
        dummy_module.isdigit_dummy.__code__
    )
    res = dummy_module.isdigit_dummy("not_digit")

    assert res == 1
    assert dynamic.has_strings
    assert "not_digit" in dynamic._dynamic_pool[str]
    assert "0" in dynamic._dynamic_pool[str]


def test_isidentifier_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isidentifier_dummy.__code__ = instr.instrument_module(
        dummy_module.isidentifier_dummy.__code__
    )
    res = dummy_module.isidentifier_dummy("is_identifier")

    assert res == 0
    assert dynamic.has_strings
    assert "is_identifier" in dynamic._dynamic_pool[str]
    assert "is_identifier!" in dynamic._dynamic_pool[str]


def test_isidentifier_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isidentifier_dummy.__code__ = instr.instrument_module(
        dummy_module.isidentifier_dummy.__code__
    )
    res = dummy_module.isidentifier_dummy("not_identifier!")

    assert res == 1
    assert dynamic.has_strings
    assert "not_identifier!" in dynamic._dynamic_pool[str]
    assert "is_Identifier" in dynamic._dynamic_pool[str]


def test_isnumeric_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isnumeric_dummy.__code__ = instr.instrument_module(
        dummy_module.isnumeric_dummy.__code__
    )
    res = dummy_module.isnumeric_dummy("44444")

    assert res == 0
    assert dynamic.has_strings
    assert "44444" in dynamic._dynamic_pool[str]
    assert "44444A" in dynamic._dynamic_pool[str]


def test_isnumeric_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isnumeric_dummy.__code__ = instr.instrument_module(
        dummy_module.isnumeric_dummy.__code__
    )
    res = dummy_module.isnumeric_dummy("not_numeric")

    assert res == 1
    assert dynamic.has_strings
    assert "not_numeric" in dynamic._dynamic_pool[str]
    assert "012345" in dynamic._dynamic_pool[str]


def test_isprintable_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isprintable_dummy.__code__ = instr.instrument_module(
        dummy_module.isprintable_dummy.__code__
    )
    res = dummy_module.isprintable_dummy("printable")

    assert res == 0
    assert dynamic.has_strings
    assert "printable" in dynamic._dynamic_pool[str]
    assert f"printable{os.linesep}" in dynamic._dynamic_pool[str]


def test_isprintable_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isprintable_dummy.__code__ = instr.instrument_module(
        dummy_module.isprintable_dummy.__code__
    )
    res = dummy_module.isprintable_dummy(f"not_printable{os.linesep}")

    assert res == 1
    assert dynamic.has_strings
    assert f"not_printable{os.linesep}" in dynamic._dynamic_pool[str]
    assert "is_printable" in dynamic._dynamic_pool[str]


def test_isspace_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isspace_dummy.__code__ = instr.instrument_module(
        dummy_module.isspace_dummy.__code__
    )
    res = dummy_module.isspace_dummy(" ")

    assert res == 0
    assert dynamic.has_strings
    assert " " in dynamic._dynamic_pool[str]
    assert " a" in dynamic._dynamic_pool[str]


def test_isspace_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.isspace_dummy.__code__ = instr.instrument_module(
        dummy_module.isspace_dummy.__code__
    )
    res = dummy_module.isspace_dummy("no_space")

    assert res == 1
    assert dynamic.has_strings
    assert "no_space" in dynamic._dynamic_pool[str]
    assert "   " in dynamic._dynamic_pool[str]


def test_istitle_function_true(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.istitle_dummy.__code__ = instr.instrument_module(
        dummy_module.istitle_dummy.__code__
    )
    res = dummy_module.istitle_dummy("Title")

    assert res == 0
    assert dynamic.has_strings
    assert "Title" in dynamic._dynamic_pool[str]
    assert "Title AAA" in dynamic._dynamic_pool[str]


def test_istitle_function_false(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.istitle_dummy.__code__ = instr.instrument_module(
        dummy_module.istitle_dummy.__code__
    )
    res = dummy_module.istitle_dummy("no Title")

    assert res == 1
    assert dynamic.has_strings
    assert "no Title" in dynamic._dynamic_pool[str]
    assert "Is Title" in dynamic._dynamic_pool[str]
