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
import sys

from opcode import opmap
from unittest import mock
from unittest.mock import MagicMock
from unittest.mock import call

import pytest

from pynguin.analyses.constants import ConstantPool
from pynguin.analyses.constants import DynamicConstantProvider
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.instrumentation import PynguinCompare
from pynguin.instrumentation.tracer import InstrumentationExecutionTracer
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import BranchCoverageInstrumentation
from pynguin.instrumentation.version import CheckedCoverageInstrumentation
from pynguin.instrumentation.version import DynamicSeedingInstrumentation
from pynguin.instrumentation.version import LineCoverageInstrumentation
from pynguin.slicer.executedinstruction import ExecutedControlInstruction
from pynguin.slicer.executedinstruction import ExecutedInstruction
from pynguin.slicer.executedinstruction import ExecutedMemoryInstruction
from pynguin.slicer.executedinstruction import ExecutedReturnInstruction
from pynguin.utils.orderedset import OrderedSet
from tests.testutils import instrument_function


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
def subject_properties_mock() -> MagicMock:
    subject_properties = MagicMock()
    subject_properties.create_code_object_id.side_effect = range(100)
    subject_properties.register_predicate.side_effect = range(100)
    subject_properties.instrumentation_tracer = InstrumentationExecutionTracer(MagicMock())
    return subject_properties


def test_entered_function(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.simple_function)
    simple_module.simple_function(1)
    subject_properties_mock.register_code_object.assert_called_once()
    subject_properties_mock.instrumentation_tracer.tracer.executed_code_object.assert_called_once()


def test_entered_for_loop_no_jump(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.for_loop)
    subject_properties_mock.register_predicate.assert_called_once()
    simple_module.for_loop(3)
    subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.assert_called_with(
        True,  # noqa: FBT003
        0,
    )


def test_entered_for_loop_no_jump_not_entered(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.for_loop)
    subject_properties_mock.register_predicate.assert_called_once()
    simple_module.for_loop(0)
    subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.assert_called_with(
        False,  # noqa: FBT003
        0,
    )


def test_entered_for_loop_full_loop(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.full_for_loop)
    subject_properties_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(3)
    subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.assert_has_calls([
        call(True, 0),  # noqa: FBT003
        call(True, 0),  # noqa: FBT003
        call(True, 0),  # noqa: FBT003
        call(False, 0),  # noqa: FBT003
    ])
    assert (
        subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.call_count
        == 4
    )


def test_entered_for_loop_full_loop_not_entered(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.full_for_loop)
    subject_properties_mock.register_predicate.assert_called_once()
    simple_module.full_for_loop(0)
    subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.assert_called_with(
        False,  # noqa: FBT003
        0,
    )


def test_add_bool_predicate(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.bool_predicate)
    simple_module.bool_predicate(True)  # noqa: FBT003
    subject_properties_mock.register_predicate.assert_called_once()
    subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.assert_called_once()


def test_add_cmp_predicate(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.cmp_predicate)
    simple_module.cmp_predicate(1, 2)
    subject_properties_mock.register_predicate.assert_called_once()
    subject_properties_mock.instrumentation_tracer.tracer.executed_compare_predicate.assert_called_once()


def test_transform_for_loop_multi(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.multi_loop)
    assert simple_module.multi_loop(2) == 4
    assert subject_properties_mock.register_predicate.call_count == 3
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
    assert (
        subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.call_count
        == len(calls)
    )
    subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.assert_has_calls(
        calls
    )


def test_add_cmp_predicate_loop_comprehension(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.comprehension)
    call_count = 5
    simple_module.comprehension(call_count, 3)
    assert subject_properties_mock.register_predicate.call_count == 2
    assert (
        subject_properties_mock.instrumentation_tracer.tracer.executed_compare_predicate.call_count
        == call_count
    )
    assert (
        subject_properties_mock.instrumentation_tracer.tracer.executed_bool_predicate.mock_calls
        == [
            call(True, 0),  # noqa: FBT003
            call(True, 0),  # noqa: FBT003
            call(True, 0),  # noqa: FBT003
            call(True, 0),  # noqa: FBT003
            call(True, 0),  # noqa: FBT003
            call(False, 0),  # noqa: FBT003
        ]
    )


def test_add_cmp_predicate_lambda(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.lambda_func)
    lam = simple_module.lambda_func(10)
    lam(5)
    subject_properties_mock.register_predicate.assert_called_once()
    assert subject_properties_mock.register_code_object.call_count == 2
    subject_properties_mock.instrumentation_tracer.tracer.executed_compare_predicate.assert_called_once()
    subject_properties_mock.instrumentation_tracer.tracer.executed_code_object.assert_has_calls(
        [call(0), call(1)], any_order=True
    )


def test_conditional_assignment(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.conditional_assignment)
    simple_module.conditional_assignment(10)
    subject_properties_mock.register_predicate.assert_called_once()
    assert subject_properties_mock.register_code_object.call_count == 1
    subject_properties_mock.instrumentation_tracer.tracer.executed_compare_predicate.assert_called_once()
    subject_properties_mock.instrumentation_tracer.tracer.executed_code_object.assert_has_calls([
        call(0)
    ])


def test_conditionally_nested_class(simple_module, subject_properties_mock: MagicMock):
    adapter = BranchCoverageInstrumentation(subject_properties_mock)
    transformer = InstrumentationTransformer(subject_properties_mock, [adapter])
    instrument_function(transformer, simple_module.conditionally_nested_class)
    assert subject_properties_mock.register_code_object.call_count == 3

    simple_module.conditionally_nested_class(6)
    subject_properties_mock.instrumentation_tracer.tracer.executed_code_object.assert_has_calls(
        [call(0), call(1), call(2)], any_order=True
    )
    subject_properties_mock.register_predicate.assert_called_once()
    subject_properties_mock.instrumentation_tracer.tracer.executed_compare_predicate.assert_called_once()


def test_avoid_duplicate_instrumentation(simple_module, subject_properties: SubjectProperties):
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, simple_module.cmp_predicate)
    with pytest.raises(AssertionError):
        instrument_function(transformer, simple_module.cmp_predicate)


# Starting with Python 3.12, the generators are not distinct code objects anymore
if sys.version_info >= (3, 12):
    comprehension_branchless_function_count = 0
else:
    comprehension_branchless_function_count = 1


@pytest.mark.parametrize(
    "function_name, branchless_function_count, branches_count",
    [
        ("simple_function", 1, 0),
        ("cmp_predicate", 0, 1),
        ("bool_predicate", 0, 1),
        ("for_loop", 0, 1),
        ("full_for_loop", 0, 1),
        ("multi_loop", 0, 3),
        ("comprehension", comprehension_branchless_function_count, 2),
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
    subject_properties: SubjectProperties,
):
    function_callable = getattr(simple_module, function_name)
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, function_callable)
    assert sum(1 for _ in subject_properties.branch_less_code_objects) == branchless_function_count
    assert len(list(subject_properties.existing_predicates)) == branches_count


def test_integrate_line_coverage_instrumentation(
    simple_module, subject_properties: SubjectProperties
):
    function_callable = simple_module.multi_loop
    adapter = LineCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, function_callable)

    assert subject_properties.existing_lines
    # the body of the method contains 7 statements on lines 38 to 44
    assert {
        0,
        1,
        2,
        3,
        4,
        5,
        6,
    } == subject_properties.existing_lines.keys()


def test_calculation_checked_coverage_instrumentation(
    simple_module, subject_properties: SubjectProperties
):
    """Checks if the instructions in the checked coverage are traced correctly.

    The disassembled method 'bool_predicate' looks as such:
    21          0 LOAD_FAST                0 (a)
                2 POP_JUMP_IF_FALSE        4 (to 8).

    22          4 LOAD_CONST               1 (1)
                6 RETURN_VALUE

    24     >>    8 LOAD_CONST               2 (0)
                10 RETURN_VALUE
    """
    if sys.version_info >= (3, 13):
        expected_executed_instructions = OrderedSet([
            ExecutedMemoryInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["LOAD_FAST"],
                argument="a",
                lineno=21,
                instr_original_index=1,
                arg_address=94271749559808,
                is_mutable_type=True,
                object_creation=True,
            ),
            ExecutedInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["TO_BOOL"],
                argument=None,
                lineno=21,
                instr_original_index=2,
            ),
            ExecutedControlInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["POP_JUMP_IF_FALSE"],
                argument="a",
                lineno=21,
                instr_original_index=3,
            ),
            ExecutedReturnInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=2,
                opcode=opmap["RETURN_CONST"],
                argument=None,
                lineno=24,
                instr_original_index=0,
            ),
        ])
    elif sys.version_info >= (3, 12):
        expected_executed_instructions = OrderedSet([
            ExecutedMemoryInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["LOAD_FAST"],
                argument="a",
                lineno=21,
                instr_original_index=1,
                arg_address=94271749559808,
                is_mutable_type=True,
                object_creation=True,
            ),
            ExecutedControlInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["POP_JUMP_IF_FALSE"],
                argument="a",
                lineno=21,
                instr_original_index=2,
            ),
            ExecutedReturnInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=2,
                opcode=opmap["RETURN_CONST"],
                argument=None,
                lineno=24,
                instr_original_index=0,
            ),
        ])
    elif sys.version_info >= (3, 11):
        expected_executed_instructions = OrderedSet([
            ExecutedMemoryInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["LOAD_FAST"],
                argument="a",
                lineno=21,
                instr_original_index=1,
                arg_address=94271749559808,
                is_mutable_type=True,
                object_creation=True,
            ),
            ExecutedControlInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["POP_JUMP_FORWARD_IF_FALSE"],
                argument="a",
                lineno=21,
                instr_original_index=2,
            ),
            # the LOAD_CONST instruction is not traced by the slicer
            ExecutedReturnInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=2,
                opcode=opmap["RETURN_VALUE"],
                argument=None,
                lineno=24,
                instr_original_index=1,
            ),
        ])
    else:
        expected_executed_instructions = OrderedSet([
            ExecutedMemoryInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["LOAD_FAST"],
                argument="a",
                lineno=21,
                instr_original_index=0,
                arg_address=0,
                is_mutable_type=True,
                object_creation=True,
            ),
            ExecutedControlInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=0,
                opcode=opmap["POP_JUMP_IF_FALSE"],
                argument="a",
                lineno=21,
                instr_original_index=1,
            ),
            # the LOAD_CONST instruction is not traced by the slicer
            ExecutedReturnInstruction(
                file=simple_module.__file__,
                code_object_id=0,
                node_id=2,
                opcode=opmap["RETURN_VALUE"],
                argument=None,
                lineno=24,
                instr_original_index=1,
            ),
        ])

    function_callable = simple_module.bool_predicate
    adapter = CheckedCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])

    instrument_function(transformer, function_callable)

    with subject_properties.instrumentation_tracer:
        function_callable(False)  # noqa: FBT003

    trace = subject_properties.instrumentation_tracer.get_trace()
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
        assert expected_instr.instr_original_index == actual_instr.instr_original_index


@pytest.mark.parametrize(
    "op",
    [op for op in PynguinCompare if op != PynguinCompare.EXC_MATCH],
)
def test_comparison(comparison_module, op, subject_properties: SubjectProperties):
    function_callable = getattr(comparison_module, "_" + op.name.lower())
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, function_callable)
    with (
        mock.patch.object(
            subject_properties.instrumentation_tracer, "executed_compare_predicate"
        ) as trace_mock,
        subject_properties.instrumentation_tracer,
    ):
        function_callable("a", "a")
        trace_mock.assert_called_with("a", "a", 0, op)


def test_is_none_comparison(comparison_module, subject_properties: SubjectProperties):
    if sys.version_info >= (3, 11):
        # Python 3.11 inverts the condition in its JUMP instruction
        expected_compare = PynguinCompare.IS_NOT
    else:
        expected_compare = PynguinCompare.IS

    function_callable = comparison_module._is_none
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, function_callable)
    with (
        mock.patch.object(
            subject_properties.instrumentation_tracer, "executed_compare_predicate"
        ) as trace_mock,
        subject_properties.instrumentation_tracer,
    ):
        function_callable("a")
        trace_mock.assert_called_with("a", None, 0, expected_compare)


def test_is_not_none_comparison(comparison_module, subject_properties: SubjectProperties):
    if sys.version_info >= (3, 11):
        # Python 3.11 inverts the condition in its JUMP instruction
        expected_compare = PynguinCompare.IS
    else:
        expected_compare = PynguinCompare.IS_NOT

    function_callable = comparison_module._is_not_none
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, function_callable)
    with (
        mock.patch.object(
            subject_properties.instrumentation_tracer, "executed_compare_predicate"
        ) as trace_mock,
        subject_properties.instrumentation_tracer,
    ):
        function_callable("a")
        trace_mock.assert_called_with("a", None, 0, expected_compare)


def test_exception(subject_properties: SubjectProperties):
    value_error = ValueError("Test exception")

    def func():
        try:
            raise value_error
        except ValueError:
            pass

    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, func)
    with (
        mock.patch.object(
            subject_properties.instrumentation_tracer, "executed_exception_match"
        ) as trace_mock,
        subject_properties.instrumentation_tracer,
    ):
        func()
        if sys.version_info >= (3, 11):
            trace_mock.assert_called_with(value_error, ValueError, 0)
        else:
            trace_mock.assert_called_with(type(value_error), ValueError, 0)


def test_exception_no_match():
    subject_properties = SubjectProperties()

    runtime_error = RuntimeError("Test exception")

    def func():
        try:
            raise runtime_error
        except ValueError:
            pass  # pragma: no cover

    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, func)
    with (
        mock.patch.object(
            subject_properties.instrumentation_tracer, "executed_exception_match"
        ) as trace_mock,
        subject_properties.instrumentation_tracer,
    ):
        with pytest.raises(RuntimeError):
            func()

        if sys.version_info >= (3, 11):
            trace_mock.assert_called_with(runtime_error, ValueError, 0)
        else:
            trace_mock.assert_called_with(type(runtime_error), ValueError, 0)


def test_exception_integrate(subject_properties: SubjectProperties):
    def func():
        try:
            raise ValueError
        except ValueError:
            pass

    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, func)

    with subject_properties.instrumentation_tracer:
        func()

    trace = subject_properties.instrumentation_tracer.get_trace()
    assert OrderedSet([0]) == trace.executed_code_objects
    assert trace.executed_predicates == {0: 1}
    assert trace.true_distances == {0: 0.0}
    assert trace.false_distances == {0: 1.0}


def test_multiple_instrumentations_share_code_object_ids(
    simple_module, subject_properties: SubjectProperties
):
    line_instr = LineCoverageInstrumentation(subject_properties)
    branch_instr = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [line_instr, branch_instr])
    instrument_function(transformer, simple_module.simple_function)

    with subject_properties.instrumentation_tracer:
        simple_module.simple_function(42)

    assert {0} == subject_properties.existing_code_objects.keys()
    assert {0} == set(subject_properties.branch_less_code_objects)
    assert (
        OrderedSet([0])
        == subject_properties.instrumentation_tracer.get_trace().executed_code_objects
    )


def test_exception_no_match_integrate(subject_properties: SubjectProperties):
    def func():
        try:
            raise RuntimeError
        except ValueError:
            pass  # pragma: no cover

    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, func)

    with pytest.raises(RuntimeError), subject_properties.instrumentation_tracer:
        func()

    trace = subject_properties.instrumentation_tracer.get_trace()
    assert OrderedSet([0]) == trace.executed_code_objects
    assert trace.executed_predicates == {0: 1}
    assert trace.true_distances == {0: 1.0}
    assert trace.false_distances == {0: 0.0}


def test_jump_if_true_or_pop(subject_properties: SubjectProperties):
    def func(string, _int_type=int):
        return (hasattr(string, "is_integer") or hasattr(string, "__array__")) or (
            isinstance(string, bytes | str)
        )

    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, func)

    with contextlib.nullcontext(), subject_properties.instrumentation_tracer:
        func("123")

    trace = subject_properties.instrumentation_tracer.get_trace()
    assert OrderedSet([0]) == trace.executed_code_objects
    assert trace.executed_predicates == {0: 1, 1: 1}
    assert trace.true_distances == {0: 1.0, 1: 1.0}
    assert trace.false_distances == {0: 0.0, 1: 0.0}


def test_tracking_covered_statements_explicit_return(
    simple_module, subject_properties: SubjectProperties
):
    instr = LineCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [instr])
    instrument_function(transformer, simple_module.explicit_none_return)

    with subject_properties.instrumentation_tracer:
        simple_module.explicit_none_return()

    assert subject_properties.instrumentation_tracer.get_trace().covered_line_ids
    assert subject_properties.lineids_to_linenos(
        subject_properties.instrumentation_tracer.get_trace().covered_line_ids
    ) == OrderedSet([
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
def test_tracking_covered_statements_cmp_predicate(
    simple_module, value1, value2, expected_lines, subject_properties: SubjectProperties
):
    adapter = LineCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, simple_module.cmp_predicate)

    with subject_properties.instrumentation_tracer:
        simple_module.cmp_predicate(value1, value2)

    trace = subject_properties.instrumentation_tracer.get_trace()
    assert trace.covered_line_ids
    assert subject_properties.lineids_to_linenos(trace.covered_line_ids) == expected_lines


@pytest.mark.parametrize(
    "value, expected_lines",
    [
        pytest.param(False, OrderedSet([21, 24])),
        pytest.param(True, OrderedSet([21, 22])),
    ],
)
def test_tracking_covered_statements_bool_predicate(
    simple_module, value, expected_lines, subject_properties: SubjectProperties
):
    adapter = LineCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, simple_module.bool_predicate)

    with subject_properties.instrumentation_tracer:
        simple_module.bool_predicate(value)

    trace = subject_properties.instrumentation_tracer.get_trace()
    assert trace.covered_line_ids
    assert subject_properties.lineids_to_linenos(trace.covered_line_ids) == expected_lines


@pytest.mark.parametrize(
    "number, expected_lines",
    [
        pytest.param(0, OrderedSet([33])),
        pytest.param(1, OrderedSet([33, 34])),
    ],
)
def test_tracking_covered_statements_for_loop(
    simple_module, number, expected_lines, subject_properties: SubjectProperties
):
    adapter = LineCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, simple_module.full_for_loop)

    with subject_properties.instrumentation_tracer:
        simple_module.full_for_loop(number)

    trace = subject_properties.instrumentation_tracer.get_trace()
    assert trace.covered_line_ids
    assert subject_properties.lineids_to_linenos(trace.covered_line_ids) == expected_lines


@pytest.mark.parametrize(
    "number, expected_lines",
    [
        pytest.param(0, OrderedSet([48])),
        pytest.param(1, OrderedSet([48, 49, 50])),
    ],
)
def test_tracking_covered_statements_while_loop(
    simple_module, number, expected_lines, subject_properties: SubjectProperties
):
    adapter = LineCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    instrument_function(transformer, simple_module.while_loop)

    with subject_properties.instrumentation_tracer:
        simple_module.while_loop(number)

    trace = subject_properties.instrumentation_tracer.get_trace()
    assert trace.covered_line_ids
    assert subject_properties.lineids_to_linenos(trace.covered_line_ids) == expected_lines


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
def test_expected_covered_lines(
    func, arg, expected_lines, artificial_none_module, subject_properties: SubjectProperties
):
    adapter = LineCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    func_object = getattr(artificial_none_module, func)
    instrument_function(transformer, func_object)

    with subject_properties.instrumentation_tracer:
        func_object(arg)

    assert (
        subject_properties.lineids_to_linenos(
            subject_properties.instrumentation_tracer.get_trace().covered_line_ids
        )
        == expected_lines
    )


@pytest.fixture
def dynamic_instr(subject_properties: SubjectProperties):
    constant_pool = ConstantPool()
    constant_provider = DynamicConstantProvider(
        pool=constant_pool,
        delegate=EmptyConstantProvider(),
        probability=1.0,
        max_constant_length=50,
    )
    adapter = DynamicSeedingInstrumentation(constant_provider)
    transformer = InstrumentationTransformer(subject_properties, [adapter])
    return constant_pool, transformer


@pytest.fixture
def dummy_module():
    dummy_module = importlib.import_module(
        "tests.fixtures.seeding.dynamicseeding.dynamicseedingdummies"
    )
    return importlib.reload(dummy_module)


def test_compare_op_int(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    instrument_function(instr, dummy_module.compare_op_dummy)
    res = dummy_module.compare_op_dummy(10, 11)

    assert res == 1
    assert dynamic.get_all_constants_for(int) == OrderedSet([11, 10])


def test_compare_op_float(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    instrument_function(instr, dummy_module.compare_op_dummy)
    res = dummy_module.compare_op_dummy(1.0, 2.5)

    assert res == 1
    assert dynamic.get_all_constants_for(float) == OrderedSet([2.5, 1.0])


def test_compare_op_string(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    instrument_function(instr, dummy_module.compare_op_dummy)
    res = dummy_module.compare_op_dummy("abc", "def")

    assert res == 1
    assert dynamic.get_all_constants_for(str) == OrderedSet(["def", "abc"])


def test_compare_op_other_type(dynamic_instr, dummy_module):
    dynamic, instr = dynamic_instr
    instrument_function(instr, dummy_module.compare_op_dummy)
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
    instrument_function(instr, func)
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
    instrument_function(instr, func)
    assert func(inp1, inp2) == result
    assert dynamic.has_constant_for(str)
    assert dynamic.get_all_constants_for(str) == OrderedSet([tracked])
