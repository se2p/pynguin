#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
import os
import threading
from unittest import mock
from unittest.mock import MagicMock, call

import pytest
from bytecode import Bytecode
from bytecode import Compare
from ordered_set import OrderedSet

import pynguin.utils.opcodes as op
from pynguin.analyses.controlflow import CFG
from pynguin.analyses.seeding import DynamicConstantSeeding
from pynguin.instrumentation.instrumentation import (
    BranchCoverageInstrumentation,
    DynamicSeedingInstrumentation,
    InstrumentationTransformer,
    LineCoverageInstrumentation,
    CheckedCoverageInstrumentation,
    get_nodes_around_node,
    basic_block_is_assertion_error,
)
from pynguin.testcase.execution import (
    ExecutionTracer,
    ExecutedMemoryInstruction,
    ExecutedReturnInstruction
)


@pytest.fixture()
def simple_module():
    simple = importlib.import_module("tests.fixtures.instrumentation.simple")
    simple = importlib.reload(simple)
    return simple


@pytest.fixture()
def artificial_none_module():
    simple = importlib.import_module("tests.fixtures.linecoverage.artificial_none")
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
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.simple_function.__code__ = transformer.instrument_module(
        simple_module.simple_function.__code__
    )
    simple_module.simple_function(1)
    tracer_mock.register_code_object.assert_called_once()
    tracer_mock.executed_code_object.assert_called_once()


def test_entered_for_loop_no_jump(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.for_loop.__code__ = transformer.instrument_module(
        simple_module.for_loop.__code__
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.for_loop(3)
    tracer_mock.executed_bool_predicate.assert_called_with(True, 0)


def test_entered_for_loop_no_jump_not_entered(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.for_loop.__code__ = transformer.instrument_module(
        simple_module.for_loop.__code__
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.for_loop(0)
    tracer_mock.executed_bool_predicate.assert_called_with(False, 0)


def test_entered_for_loop_full_loop(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.full_for_loop.__code__ = transformer.instrument_module(
        simple_module.full_for_loop.__code__
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(3)
    tracer_mock.executed_bool_predicate.assert_has_calls(
        [call(True, 0), call(True, 0), call(True, 0), call(False, 0)]
    )
    assert tracer_mock.executed_bool_predicate.call_count == 4


def test_entered_for_loop_full_loop_not_entered(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.full_for_loop.__code__ = transformer.instrument_module(
        simple_module.full_for_loop.__code__
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(0)
    tracer_mock.executed_bool_predicate.assert_called_with(False, 0)


def test_add_bool_predicate(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.bool_predicate.__code__ = transformer.instrument_module(
        simple_module.bool_predicate.__code__
    )
    simple_module.bool_predicate(True)
    tracer_mock.register_predicate.assert_called_once()
    tracer_mock.executed_bool_predicate.assert_called_once()


def test_add_cmp_predicate(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.cmp_predicate.__code__ = transformer.instrument_module(
        simple_module.cmp_predicate.__code__
    )
    simple_module.cmp_predicate(1, 2)
    tracer_mock.register_predicate.assert_called_once()
    tracer_mock.executed_compare_predicate.assert_called_once()


def test_transform_for_loop_multi(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.multi_loop.__code__ = transformer.instrument_module(
        simple_module.multi_loop.__code__
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
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.comprehension.__code__ = transformer.instrument_module(
        simple_module.comprehension.__code__
    )
    call_count = 5
    simple_module.comprehension(call_count, 3)
    assert tracer_mock.register_predicate.call_count == 2
    assert tracer_mock.executed_compare_predicate.call_count == call_count
    # TODO(SiL) does this still test the same as before?
    tracer_mock.executed_bool_predicate.assert_has_calls([call(False, 0)])


def test_add_cmp_predicate_lambda(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.lambda_func.__code__ = transformer.instrument_module(
        simple_module.lambda_func.__code__
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
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.conditional_assignment.__code__ = transformer.instrument_module(
        simple_module.conditional_assignment.__code__
    )
    simple_module.conditional_assignment(10)
    tracer_mock.register_predicate.assert_called_once()
    assert tracer_mock.register_code_object.call_count == 1
    tracer_mock.executed_compare_predicate.assert_called_once()
    tracer_mock.executed_code_object.assert_has_calls([call(0)])


def test_conditionally_nested_class(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.conditionally_nested_class.__code__ = transformer.instrument_module(
        simple_module.conditionally_nested_class.__code__
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
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    already_instrumented = transformer.instrument_module(
        simple_module.cmp_predicate.__code__
    )
    with pytest.raises(AssertionError):
        transformer.instrument_module(already_instrumented)


@pytest.mark.parametrize(
    "function_name, branchless_function_count, branches_count",
    [
        ("simple_function", 1, 0),
        ("cmp_predicate", 0, 1),
        ("bool_predicate", 0, 1),
        ("for_loop", 0, 1),
        ("full_for_loop", 0, 1),
        ("multi_loop", 0, 3),
        ("comprehension", 1, 2),
        ("lambda_func", 1, 1),
        ("conditional_assignment", 0, 1),
        ("conditionally_nested_class", 2, 1),
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
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    function_callable.__code__ = transformer.instrument_module(
        function_callable.__code__
    )
    assert (
        len(tracer.get_known_data().branch_less_code_objects)
        == branchless_function_count
    )
    assert len(list(tracer.get_known_data().existing_predicates)) == branches_count


def test_integrate_line_coverage_instrumentation(simple_module):
    tracer = ExecutionTracer()
    function_callable = getattr(simple_module, "multi_loop")
    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    function_callable.__code__ = transformer.instrument_module(
        function_callable.__code__
    )

    assert tracer.get_known_data().existing_lines
    # the body of the method contains 7 statements on lines 38 to 44
    assert {0, 1, 2, 3, 4, 5, 6} == tracer.get_known_data().existing_lines.keys()


def test_offset_calculation_checked_coverage_instrumentation(simple_module):
    """Checks if the instructions in the checked coverage are traced correctly.
    The disassembled method 'bool_predicate' looks as such:
    21          0 LOAD_FAST                0 (a)
                2 POP_JUMP_IF_FALSE        4 (to 8)

    22          4 LOAD_CONST               1 (1)
                6 RETURN_VALUE

    24     >>    8 LOAD_CONST               2 (0)
                10 RETURN_VALUE
    """
    expected_executed_instructions = OrderedSet([
        ExecutedMemoryInstruction(
            file=simple_module.__file__,
            code_object_id=0,
            node_id=0,
            opcode=op.LOAD_FAST,
            argument='a',
            lineno=21,
            offset=0,
            arg_address=0,
            is_mutable_type=True,
            object_creation=True
        ),
        ExecutedReturnInstruction(
            file=simple_module.__file__,
            code_object_id=0,
            node_id=2,
            opcode=op.RETURN_VALUE,
            argument=None,
            lineno=24,
            offset=10
        ),
    ])

    tracer = ExecutionTracer()
    function_callable = getattr(simple_module, "bool_predicate")
    adapter = CheckedCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])

    function_callable.__code__ = transformer.instrument_module(
        function_callable.__code__
    )
    function_callable(False)

    trace = tracer.get_trace()
    assert trace.executed_instructions
    assert len(trace.executed_instructions) == 2
    for i in range(2):
        expected_instr = expected_executed_instructions[i]
        actual_instr = trace.executed_instructions[i]

        # can not compare expected and actual with equals, since the attribute
        # access instruction holds an argument address that changes with each
        # execution and can not be set in the expected element
        assert type(expected_instr) == type(actual_instr)
        assert expected_instr.file == actual_instr.file
        assert expected_instr.code_object_id == actual_instr.code_object_id
        assert expected_instr.opcode == actual_instr.opcode
        assert expected_instr.lineno == actual_instr.lineno
        assert expected_instr.offset == actual_instr.offset


@pytest.mark.parametrize(
    "op",
    [op for op in Compare if op != Compare.EXC_MATCH],
)
def test_comparison(comparison_module, op):
    tracer = ExecutionTracer()
    function_callable = getattr(comparison_module, "_" + op.name.lower())
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    function_callable.__code__ = transformer.instrument_module(
        function_callable.__code__
    )
    with mock.patch.object(tracer, "executed_compare_predicate") as trace_mock:
        function_callable("a", "a")
        trace_mock.assert_called_with("a", "a", 0, op)


def test_exception():
    tracer = ExecutionTracer()

    def func():
        try:
            raise ValueError()
        except ValueError:
            pass

    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    func.__code__ = transformer.instrument_module(func.__code__)
    with mock.patch.object(tracer, "executed_exception_match") as trace_mock:
        func()
        trace_mock.assert_called_with(ValueError, ValueError, 0)


def test_exception_no_match():
    tracer = ExecutionTracer()

    def func():
        try:
            raise RuntimeError()
        except ValueError:
            pass  # pragma: no cover

    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    func.__code__ = transformer.instrument_module(func.__code__)
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

    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    func.__code__ = transformer.instrument_module(func.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    func()
    assert {0} == tracer.get_trace().executed_code_objects
    assert {0: 1} == tracer.get_trace().executed_predicates
    assert {0: 0.0} == tracer.get_trace().true_distances
    assert {0: 1.0} == tracer.get_trace().false_distances


def test_multiple_instrumentations_share_code_object_ids(simple_module):
    tracer = ExecutionTracer()

    line_instr = LineCoverageInstrumentation(tracer)
    branch_instr = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [line_instr, branch_instr])
    simple_module.simple_function.__code__ = transformer.instrument_module(
        simple_module.simple_function.__code__
    )

    tracer.current_thread_identifier = threading.current_thread().ident
    simple_module.simple_function(42)
    assert {0} == tracer.get_known_data().existing_code_objects.keys()
    assert {0} == tracer.get_known_data().branch_less_code_objects
    assert {0} == tracer.get_trace().executed_code_objects


def test_exception_no_match_integrate():
    tracer = ExecutionTracer()

    def func():
        try:
            raise RuntimeError()
        except ValueError:
            pass  # pragma: no cover

    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    func.__code__ = transformer.instrument_module(func.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    with pytest.raises(RuntimeError):
        func()
    assert {0} == tracer.get_trace().executed_code_objects
    assert {0: 1} == tracer.get_trace().executed_predicates
    assert {0: 1.0} == tracer.get_trace().true_distances
    assert {0: 0.0} == tracer.get_trace().false_distances


def test_tracking_covered_statements_explicit_return(simple_module):
    tracer = ExecutionTracer()

    instr = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [instr])
    simple_module.explicit_none_return.__code__ = transformer.instrument_module(
        simple_module.explicit_none_return.__code__
    )
    tracer.current_thread_identifier = threading.current_thread().ident
    simple_module.explicit_none_return()
    assert tracer.get_trace().covered_line_ids
    assert tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == {77, 78}


@pytest.mark.parametrize(
    "value1, value2, expected_lines",
    [
        pytest.param(0, 1, {14, 17}),
        pytest.param(1, 0, {14, 15}),
    ],
)
def test_tracking_covered_statements_cmp_predicate(
    simple_module, value1, value2, expected_lines
):
    tracer = ExecutionTracer()

    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    simple_module.cmp_predicate.__code__ = transformer.instrument_module(
        simple_module.cmp_predicate.__code__
    )
    tracer.current_thread_identifier = threading.current_thread().ident
    simple_module.cmp_predicate(value1, value2)
    assert tracer.get_trace().covered_line_ids
    assert (
        tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines
    )


@pytest.mark.parametrize(
    "value, expected_lines",
    [
        pytest.param(False, {21, 24}),
        pytest.param(True, {21, 22}),
    ],
)
def test_tracking_covered_statements_bool_predicate(
    simple_module, value, expected_lines
):
    tracer = ExecutionTracer()

    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    simple_module.bool_predicate.__code__ = transformer.instrument_module(
        simple_module.bool_predicate.__code__
    )
    tracer.current_thread_identifier = threading.current_thread().ident
    simple_module.bool_predicate(value)
    assert tracer.get_trace().covered_line_ids
    assert (
        tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines
    )


@pytest.mark.parametrize(
    "number, expected_lines",
    [
        pytest.param(0, {33}),
        pytest.param(1, {33, 34}),
    ],
)
def test_tracking_covered_statements_for_loop(simple_module, number, expected_lines):
    tracer = ExecutionTracer()

    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    simple_module.full_for_loop.__code__ = transformer.instrument_module(
        simple_module.full_for_loop.__code__
    )
    tracer.current_thread_identifier = threading.current_thread().ident
    simple_module.full_for_loop(number)
    assert tracer.get_trace().covered_line_ids
    assert (
        tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines
    )


@pytest.mark.parametrize(
    "number, expected_lines",
    [
        pytest.param(0, {48}),
        pytest.param(1, {48, 49, 50}),
    ],
)
def test_tracking_covered_statements_while_loop(simple_module, number, expected_lines):
    tracer = ExecutionTracer()

    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    simple_module.while_loop.__code__ = transformer.instrument_module(
        simple_module.while_loop.__code__
    )
    tracer.current_thread_identifier = threading.current_thread().ident
    simple_module.while_loop(number)
    assert tracer.get_trace().covered_line_ids
    assert (
        tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines
    )


@pytest.mark.parametrize(
    "func,arg,expected_lines",
    [
        ("explicit_return_none", None, {8}),
        ("empty_function", None, {11}),
        ("pass_function", None, {16}),
        ("only_return_on_branch", True, {20, 21}),
        ("only_return_on_branch", False, {20}),
        ("return_on_both_branches", True, {25, 26}),
        ("return_on_both_branches", False, {25, 27}),
        ("pass_on_both", True, {31, 32}),
        ("pass_on_both", False, {31, 34}),
        ("for_return", [], {38}),
        ("for_return", [1], {38, 39}),
    ],
)
def test_expected_covered_lines(func, arg, expected_lines, artificial_none_module):
    tracer = ExecutionTracer()

    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    func_object = getattr(artificial_none_module, func)
    func_object.__code__ = transformer.instrument_module(func_object.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    func_object(arg)
    assert (
        tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines
    )


@pytest.fixture()
def dynamic_instr():
    dynamic_constants = DynamicConstantSeeding()
    adapter = DynamicSeedingInstrumentation(dynamic_constants)
    transformer = InstrumentationTransformer(ExecutionTracer(), [adapter])
    return dynamic_constants, transformer


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


@pytest.mark.parametrize(
    "assertion_index, expected_before_index, expected_after_index",
    [
        pytest.param(4, 8, 0),  # assertion on line 16
        pytest.param(5, 0, 1),  # assertion on line 17
        pytest.param(7, 1, 2),  # assertion on line 18
    ],
)
def test_get_nodes_around_assertion(assertion_index, expected_before_index, expected_after_index):
    module_name = "tests.fixtures.assertion.multiple"
    module = importlib.import_module(module_name)
    module = importlib.reload(module)
    cfg = CFG.from_bytecode(Bytecode.from_code(module.test_foo.__code__))
    nodes = list(cfg.nodes)

    assertion_node = nodes[assertion_index]
    assert basic_block_is_assertion_error(assertion_node.basic_block)

    before, after = get_nodes_around_node(cfg, assertion_node)

    assert nodes[expected_before_index] == before
    assert nodes[expected_after_index] == after

