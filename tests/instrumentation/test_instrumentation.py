#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import contextlib
import importlib
import os
import string
import threading

from unittest import mock
from unittest.mock import MagicMock
from unittest.mock import call

import pytest

import pynguin.utils.opcodes as op

from pynguin.analyses.constants import ConstantPool
from pynguin.analyses.constants import DynamicConstantProvider
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.instrumentation.instrumentation import ArtificialInstr
from pynguin.instrumentation.instrumentation import BranchCoverageInstrumentation
from pynguin.instrumentation.instrumentation import CheckedCoverageInstrumentation
from pynguin.instrumentation.instrumentation import DynamicSeedingInstrumentation
from pynguin.instrumentation.instrumentation import InstrumentationAdapter
from pynguin.instrumentation.instrumentation import InstrumentationTransformer
from pynguin.instrumentation.instrumentation import LineCoverageInstrumentation
from pynguin.instrumentation.instrumentation import PynguinCompare
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.slicer.executedinstruction import ExecutedControlInstruction
from pynguin.slicer.executedinstruction import ExecutedMemoryInstruction
from pynguin.slicer.executedinstruction import ExecutedReturnInstruction
from pynguin.utils.orderedset import OrderedSet


@pytest.fixture
def simple_module():
    simple = importlib.import_module("tests.fixtures.instrumentation.simple")
    return importlib.reload(simple)


@pytest.fixture
def artificial_none_module():
    simple = importlib.import_module("tests.fixtures.linecoverage.artificial_none")
    return importlib.reload(simple)


@pytest.fixture
def comparison_module():
    comparison = importlib.import_module("tests.fixtures.instrumentation.comparison")
    return importlib.reload(comparison)


@pytest.fixture
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
    simple_module.for_loop.__code__ = transformer.instrument_module(simple_module.for_loop.__code__)
    tracer_mock.register_predicate.assert_called_once()
    simple_module.for_loop(3)
    tracer_mock.executed_bool_predicate.assert_called_with(True, 0)  # noqa: FBT003


def test_entered_for_loop_no_jump_not_entered(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.for_loop.__code__ = transformer.instrument_module(simple_module.for_loop.__code__)
    tracer_mock.register_predicate.assert_called_once()
    simple_module.for_loop(0)
    tracer_mock.executed_bool_predicate.assert_called_with(False, 0)  # noqa: FBT003


def test_entered_for_loop_full_loop(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.full_for_loop.__code__ = transformer.instrument_module(
        simple_module.full_for_loop.__code__
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(3)
    tracer_mock.executed_bool_predicate.assert_has_calls([
        call(True, 0),  # noqa: FBT003
        call(True, 0),  # noqa: FBT003
        call(True, 0),  # noqa: FBT003
        call(False, 0),  # noqa: FBT003
    ])
    assert tracer_mock.executed_bool_predicate.call_count == 4


def test_entered_for_loop_full_loop_not_entered(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.full_for_loop.__code__ = transformer.instrument_module(
        simple_module.full_for_loop.__code__
    )
    tracer_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(0)
    tracer_mock.executed_bool_predicate.assert_called_with(False, 0)  # noqa: FBT003


def test_add_bool_predicate(simple_module, tracer_mock):
    adapter = BranchCoverageInstrumentation(tracer_mock)
    transformer = InstrumentationTransformer(tracer_mock, [adapter])
    simple_module.bool_predicate.__code__ = transformer.instrument_module(
        simple_module.bool_predicate.__code__
    )
    simple_module.bool_predicate(True)  # noqa: FBT003
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
    # fmt: off
    calls = [
        call(True, 0),  # noqa: FBT003
        call(True, 1),  # noqa: FBT003
        call(True, 1),   # noqa: FBT003
        call(False, 1),  # noqa: FBT003
    ] * 2 + [
        call(False, 0),  # noqa: FBT003
        call(False, 2),  # noqa: FBT003
    ]
    # fmt: on
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
    tracer_mock.executed_bool_predicate.assert_has_calls(
        [call(True, 1)]  # noqa: FBT003
    )


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
    tracer_mock.executed_code_object.assert_has_calls([call(0), call(1)], any_order=True)


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
    tracer_mock.executed_code_object.assert_has_calls([call(0), call(1), call(2)], any_order=True)
    tracer_mock.register_predicate.assert_called_once()
    tracer_mock.executed_compare_predicate.assert_called_once()


def test_avoid_duplicate_instrumentation(simple_module):
    tracer = MagicMock(ExecutionTracer)
    tracer.register_code_object.return_value = 0
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    already_instrumented = transformer.instrument_module(simple_module.cmp_predicate.__code__)
    with pytest.raises(AssertionError):
        transformer.instrument_module(already_instrumented)


@pytest.mark.parametrize(
    "block,expected",
    [
        ([], {}),
        ([MagicMock()], {0: 0}),
        ([MagicMock(), MagicMock()], {0: 0, 1: 1}),
        ([MagicMock(), ArtificialInstr("POP_TOP"), MagicMock()], {0: 0, 1: 2}),
        ([ArtificialInstr("POP_TOP"), ArtificialInstr("POP_TOP"), MagicMock()], {0: 2}),
    ],
)
def test__map_instr_positions(block, expected):
    assert InstrumentationAdapter.map_instr_positions(block) == expected


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
    function_callable.__code__ = transformer.instrument_module(function_callable.__code__)
    assert (
        len(tracer.get_subject_properties().branch_less_code_objects) == branchless_function_count
    )
    assert len(list(tracer.get_subject_properties().existing_predicates)) == branches_count


def test_integrate_line_coverage_instrumentation(simple_module):
    tracer = ExecutionTracer()
    function_callable = simple_module.multi_loop
    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    function_callable.__code__ = transformer.instrument_module(function_callable.__code__)

    assert tracer.get_subject_properties().existing_lines
    # the body of the method contains 7 statements on lines 38 to 44
    assert {
        0,
        1,
        2,
        3,
        4,
        5,
        6,
    } == tracer.get_subject_properties().existing_lines.keys()


def test_offset_calculation_checked_coverage_instrumentation(simple_module):
    """Checks if the instructions in the checked coverage are traced correctly.

    The disassembled method 'bool_predicate' looks as such:
    21          0 LOAD_FAST                0 (a)
                2 POP_JUMP_IF_FALSE        4 (to 8).

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
            argument="a",
            lineno=21,
            offset=0,
            arg_address=0,
            is_mutable_type=True,
            object_creation=True,
        ),
        ExecutedControlInstruction(
            file=simple_module.__file__,
            code_object_id=0,
            node_id=0,
            opcode=op.POP_JUMP_IF_FALSE,
            argument="a",
            lineno=21,
            offset=2,
        ),
        # the LOAD_CONST instruction is not traced by the slicer
        ExecutedReturnInstruction(
            file=simple_module.__file__,
            code_object_id=0,
            node_id=2,
            opcode=op.RETURN_VALUE,
            argument=None,
            lineno=24,
            offset=10,
        ),
    ])

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    function_callable = simple_module.bool_predicate
    adapter = CheckedCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])

    function_callable.__code__ = transformer.instrument_module(function_callable.__code__)
    function_callable(False)  # noqa: FBT003

    trace = tracer.get_trace()
    assert trace.executed_instructions
    assert len(trace.executed_instructions) == len(expected_executed_instructions)
    for expected_instr, actual_instr in zip(
        expected_executed_instructions, trace.executed_instructions, strict=False
    ):
        # can not compare expected and actual with equals, since the attribute
        # access instruction holds an argument address that changes with each
        # execution and can not be set in the expected element
        assert type(expected_instr) is type(actual_instr)
        assert expected_instr.file == actual_instr.file
        assert expected_instr.code_object_id == actual_instr.code_object_id
        assert expected_instr.opcode == actual_instr.opcode
        assert expected_instr.lineno == actual_instr.lineno
        assert expected_instr.offset == actual_instr.offset


@pytest.mark.parametrize(
    "op",
    [op for op in PynguinCompare if op != PynguinCompare.EXC_MATCH],
)
def test_comparison(comparison_module, op):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    function_callable = getattr(comparison_module, "_" + op.name.lower())
    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    function_callable.__code__ = transformer.instrument_module(function_callable.__code__)
    with mock.patch.object(tracer, "executed_compare_predicate") as trace_mock:
        function_callable("a", "a")
        trace_mock.assert_called_with("a", "a", 0, op)


def test_exception():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    def func():
        try:
            raise ValueError
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
    tracer.current_thread_identifier = threading.current_thread().ident

    def func():
        try:
            raise RuntimeError
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
            raise ValueError
        except ValueError:
            pass

    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    func.__code__ = transformer.instrument_module(func.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    func()
    assert OrderedSet([0]) == tracer.get_trace().executed_code_objects
    assert tracer.get_trace().executed_predicates == {0: 1}
    assert tracer.get_trace().true_distances == {0: 0.0}
    assert tracer.get_trace().false_distances == {0: 1.0}


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
    assert {0} == tracer.get_subject_properties().existing_code_objects.keys()
    assert OrderedSet([0]) == tracer.get_subject_properties().branch_less_code_objects
    assert OrderedSet([0]) == tracer.get_trace().executed_code_objects


def test_exception_no_match_integrate():
    tracer = ExecutionTracer()

    def func():
        try:
            raise RuntimeError
        except ValueError:
            pass  # pragma: no cover

    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    func.__code__ = transformer.instrument_module(func.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    with pytest.raises(RuntimeError):
        func()
    assert OrderedSet([0]) == tracer.get_trace().executed_code_objects
    assert tracer.get_trace().executed_predicates == {0: 1}
    assert tracer.get_trace().true_distances == {0: 1.0}
    assert tracer.get_trace().false_distances == {0: 0.0}


def test_jump_if_true_or_pop():
    tracer = ExecutionTracer()

    def func(string, _int_type=int):
        return (hasattr(string, "is_integer") or hasattr(string, "__array__")) or (
            isinstance(string, bytes | str)
        )

    adapter = BranchCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    func.__code__ = transformer.instrument_module(func.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    with contextlib.nullcontext():
        func("123")
    assert OrderedSet([0]) == tracer.get_trace().executed_code_objects
    assert tracer.get_trace().executed_predicates == {0: 1, 1: 1}
    assert tracer.get_trace().true_distances == {0: 1.0, 1: 1.0}
    assert tracer.get_trace().false_distances == {0: 0.0, 1: 0.0}


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
    assert tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == OrderedSet([
        77,
        78,
    ])


@pytest.mark.parametrize(
    "value1, value2, expected_lines",
    [
        pytest.param(0, 1, OrderedSet([14, 17])),
        pytest.param(1, 0, OrderedSet([14, 15])),
    ],
)
def test_tracking_covered_statements_cmp_predicate(simple_module, value1, value2, expected_lines):
    tracer = ExecutionTracer()

    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    simple_module.cmp_predicate.__code__ = transformer.instrument_module(
        simple_module.cmp_predicate.__code__
    )
    tracer.current_thread_identifier = threading.current_thread().ident
    simple_module.cmp_predicate(value1, value2)
    assert tracer.get_trace().covered_line_ids
    assert tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines


@pytest.mark.parametrize(
    "value, expected_lines",
    [
        pytest.param(False, OrderedSet([21, 24])),
        pytest.param(True, OrderedSet([21, 22])),
    ],
)
def test_tracking_covered_statements_bool_predicate(simple_module, value, expected_lines):
    tracer = ExecutionTracer()

    adapter = LineCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])
    simple_module.bool_predicate.__code__ = transformer.instrument_module(
        simple_module.bool_predicate.__code__
    )
    tracer.current_thread_identifier = threading.current_thread().ident
    simple_module.bool_predicate(value)
    assert tracer.get_trace().covered_line_ids
    assert tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines


@pytest.mark.parametrize(
    "number, expected_lines",
    [
        pytest.param(0, OrderedSet([33])),
        pytest.param(1, OrderedSet([33, 34])),
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
    assert tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines


@pytest.mark.parametrize(
    "number, expected_lines",
    [
        pytest.param(0, OrderedSet([48])),
        pytest.param(1, OrderedSet([48, 49, 50])),
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
    assert tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines


@pytest.mark.parametrize(
    "func,arg,expected_lines",
    [
        ("explicit_return_none", None, OrderedSet([8])),
        ("empty_function", None, OrderedSet([11])),
        ("pass_function", None, OrderedSet([16])),
        ("only_return_on_branch", True, OrderedSet([20, 21])),
        ("only_return_on_branch", False, OrderedSet([20])),
        ("return_on_both_branches", True, OrderedSet([25, 26])),
        ("return_on_both_branches", False, OrderedSet([25, 27])),
        ("pass_on_both", True, OrderedSet([31, 32])),
        ("pass_on_both", False, OrderedSet([31, 34])),
        ("for_return", [], OrderedSet([38])),
        ("for_return", [1], OrderedSet([38, 39])),
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
    assert tracer.lineids_to_linenos(tracer.get_trace().covered_line_ids) == expected_lines


@pytest.fixture
def dynamic_instr():
    constant_pool = ConstantPool()
    constant_provider = DynamicConstantProvider(
        pool=constant_pool,
        delegate=EmptyConstantProvider(),
        probability=1.0,
        max_constant_length=50,
    )
    adapter = DynamicSeedingInstrumentation(constant_provider)
    transformer = InstrumentationTransformer(ExecutionTracer(), [adapter])
    return constant_pool, transformer


@pytest.fixture
def dummy_module():
    dummy_module = importlib.import_module(
        "tests.fixtures.seeding.dynamicseeding.dynamicseedingdummies"
    )
    return importlib.reload(dummy_module)


def test_compare_op_int(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(
        dummy_module.compare_op_dummy.__code__
    )
    res = dummy_module.compare_op_dummy(10, 11)

    assert res == 1
    assert dynamic.get_all_constants_for(int) == OrderedSet([11, 10])


def test_compare_op_float(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(
        dummy_module.compare_op_dummy.__code__
    )
    res = dummy_module.compare_op_dummy(1.0, 2.5)

    assert res == 1
    assert dynamic.get_all_constants_for(float) == OrderedSet([2.5, 1.0])


def test_compare_op_string(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(
        dummy_module.compare_op_dummy.__code__
    )
    res = dummy_module.compare_op_dummy("abc", "def")

    assert res == 1
    assert dynamic.get_all_constants_for(str) == OrderedSet(["def", "abc"])


def test_compare_op_other_type(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(
        dummy_module.compare_op_dummy.__code__
    )
    res = dummy_module.compare_op_dummy(True, "def")  # noqa: FBT003

    assert res == 1
    assert not dynamic.has_constant_for(int)
    assert not dynamic.has_constant_for(float)
    assert dynamic.has_constant_for(str)
    assert dynamic.get_all_constants_for(str) == OrderedSet(["def"])


@pytest.mark.parametrize(
    "func_name,inp,tracked,result",
    [
        ("isalnum", "alnumtest", "alnumtest!", 0),
        ("isalnum", "alnum_test", "isalnum", 1),
        ("islower", "lower", "LOWER", 0),
        ("islower", "NotLower", "notlower", 1),
        ("isupper", "UPPER", "upper", 0),
        ("isupper", "NotUpper", "NOTUPPER", 1),
        ("isdecimal", "012345", "non_decimal", 0),
        ("isdecimal", "not_decimal", string.digits, 1),
        ("isalpha", "alpha", "alpha1", 0),
        ("isalpha", "not_alpha", "isalpha", 1),
        ("isdigit", "012345", "012345_", 0),
        ("isdigit", "not_digit", "0", 1),
        ("isidentifier", "is_identifier", "is_identifier!", 0),
        ("isidentifier", "not_identifier!", "is_Identifier", 1),
        ("isnumeric", "44444", "44444A", 0),
        ("isnumeric", "not_numeric", "012345", 1),
        ("isprintable", "printable", f"printable{os.linesep}", 0),
        ("isprintable", f"not_printable{os.linesep}", "is_printable", 1),
        ("isspace", " ", " a", 0),
        ("isspace", "no_space", "   ", 1),
        ("istitle", "Title", "Title AAA", 0),
        ("istitle", "no Title", "Is Title", 1),
    ],
)
def test_string_functions(dynamic_instr, func_name, inp, tracked, result):
    # Some evil trickery
    glob = {}
    loc = {}
    exec(  # noqa: S102
        f"""def dummy(s):
    if s.{func_name}():
        return 0
    else:
        return 1""",
        glob,
        loc,
    )
    func = loc["dummy"]

    dynamic, instr = dynamic_instr
    func.__code__ = instr.instrument_module(func.__code__)
    assert func(inp) == result
    assert dynamic.has_constant_for(str)
    assert dynamic.get_all_constants_for(str) == OrderedSet([inp, tracked])


@pytest.mark.parametrize(
    "func_name,inp1,inp2,tracked,result",
    [
        ("startswith", "abc", "ab", "ababc", 0),
        ("endswith", "abc", "bc", "abcbc", 0),
    ],
)
def test_binary_string_functions(  # noqa: PLR0917
    dynamic_instr, func_name, inp1, inp2, tracked, result
):
    # Some evil trickery
    glob = {}
    loc = {}
    exec(  # noqa: S102
        f"""def dummy(s1,s2):
    if s1.{func_name}(s2):
        return 0
    else:
        return 1""",
        glob,
        loc,
    )
    func = loc["dummy"]

    dynamic, instr = dynamic_instr
    func.__code__ = instr.instrument_module(func.__code__)
    assert func(inp1, inp2) == result
    assert dynamic.has_constant_for(str)
    assert dynamic.get_all_constants_for(str) == OrderedSet([tracked])
