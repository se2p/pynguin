#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import threading
from decimal import Decimal
from math import inf
from typing import Any
from unittest.mock import MagicMock

import pytest

import pynguin.utils.typetracing as tt
from pynguin.instrumentation import PynguinCompare
from pynguin.instrumentation.tracer import (
    CodeObjectMetaData,
    ExecutionTracer,
    InstrumentationExecutionTracer,
    LineMetaData,
    SubjectProperties,
    _le,  # noqa: PLC2701
    _lt,  # noqa: PLC2701
)
from pynguin.slicer.executedinstruction import ExecutedSubscriptInstruction
from pynguin.utils.exceptions import TracingAbortedException
from pynguin.utils.orderedset import OrderedSet


def test_register_function(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock(CodeObjectMetaData))
    assert 0 in subject_properties.existing_code_objects


def test_function_already_registered(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock(CodeObjectMetaData))
    with pytest.raises(AssertionError):
        subject_properties.register_code_object(0, MagicMock(CodeObjectMetaData))


def test_entered_function(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock(CodeObjectMetaData))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_code_object(0)

    assert 0 in subject_properties.instrumentation_tracer.get_trace().executed_code_objects


def test_predicate_exists(subject_properties: SubjectProperties):
    assert subject_properties.register_predicate(MagicMock(code_object_id=0)) == 0
    assert subject_properties.register_predicate(MagicMock(code_object_id=0)) == 1
    assert 0 in subject_properties.existing_predicates


def test_line_registration(subject_properties: SubjectProperties):
    assert subject_properties.register_line(LineMetaData(0, "foo", 42)) == 0
    assert subject_properties.register_line(LineMetaData(0, "foo", 43)) == 1
    assert subject_properties.register_line(LineMetaData(0, "bar", 42)) == 2
    assert subject_properties.register_line(LineMetaData(1, "foo", 42)) == 0
    assert {0, 1, 2} == subject_properties.existing_lines.keys()


def test_line_visit(subject_properties: SubjectProperties):
    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.track_line_visit(42)
        subject_properties.instrumentation_tracer.track_line_visit(43)
        subject_properties.instrumentation_tracer.track_line_visit(42)

    assert subject_properties.instrumentation_tracer.get_trace().covered_line_ids == OrderedSet([
        42,
        43,
    ])


def test_update_metrics_covered(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            1, 0, 0, PynguinCompare.EQ
        )
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            1, 0, 0, PynguinCompare.EQ
        )

    assert (
        0,
        2,
    ) in subject_properties.instrumentation_tracer.get_trace().executed_predicates.items()


@pytest.mark.parametrize("true_dist,false_dist", [(-1, 0), (0, -1), (0, 0), (1, 1)])
def test_update_metrics_assertions(true_dist, false_dist, subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))
    with pytest.raises(AssertionError):
        subject_properties.instrumentation_tracer.tracer._update_metrics(false_dist, true_dist, 0)


def test_update_metrics_true_dist_min(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            5, 0, 0, PynguinCompare.EQ
        )
    assert (0, 5) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            4, 0, 0, PynguinCompare.EQ
        )

    assert (0, 4) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()


def test_update_metrics_false_dist_min(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            3, 1, 0, PynguinCompare.NE
        )

    assert (0, 2) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            2, 1, 0, PynguinCompare.NE
        )

    assert (0, 1) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


def test_passed_cmp_predicate(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            1, 0, 0, PynguinCompare.EQ
        )

    assert (
        0,
        1,
    ) in subject_properties.instrumentation_tracer.get_trace().executed_predicates.items()


def test_passed_exception_match(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_exception_match(
            ValueError(), ValueError, 0
        )

    assert (
        0,
        1,
    ) in subject_properties.instrumentation_tracer.get_trace().executed_predicates.items()
    assert (0, 0.0) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()
    assert (0, 1.0) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


def test_passed_exception_match_not(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_exception_match(
            NameError(), ValueError, 0
        )

    assert (
        0,
        1,
    ) in subject_properties.instrumentation_tracer.get_trace().executed_predicates.items()
    assert (0, 1.0) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()
    assert (0, 0.0) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


@pytest.mark.parametrize(
    "cmp,val1,val2,true_dist,false_dist",
    [
        pytest.param(PynguinCompare.EQ, 5, 0, 5, 0),
        pytest.param(PynguinCompare.EQ, 0, 0, 0, 1),
        pytest.param(PynguinCompare.EQ, "string", 0, inf, 0),
        pytest.param(PynguinCompare.EQ, "abc", "cde", 2.0, 0),
        pytest.param(PynguinCompare.EQ, bytes(range(3)), bytes(range(2, 5)), 2.0, 0),
        pytest.param(PynguinCompare.EQ, bytes(range(3)), bytes(range(3)), 0, 1),
        pytest.param(
            PynguinCompare.EQ,
            bytearray(bytes(range(3))),
            bytearray(bytes(range(2, 5))),
            2.0,
            0,
        ),
        pytest.param(
            PynguinCompare.EQ,
            bytearray(bytes(range(3))),
            bytearray(bytes(range(3))),
            0,
            1,
        ),
        pytest.param(PynguinCompare.NE, 5, 0, 0, 5),
        pytest.param(PynguinCompare.NE, 0, 0, 1, 0),
        pytest.param(PynguinCompare.NE, "string", 0, 0, inf),
        pytest.param(PynguinCompare.NE, "abc", "cde", 0, 2.0),
        pytest.param(PynguinCompare.LT, 5, 0, 6, 0),
        pytest.param(PynguinCompare.LT, 0, 5, 0, 5),
        pytest.param(PynguinCompare.LT, Decimal(5), Decimal(0), 6, 0),
        pytest.param(PynguinCompare.LT, Decimal(0), Decimal(5), 0, 5),
        pytest.param(PynguinCompare.LE, 5, 0, 5, 0),
        pytest.param(PynguinCompare.LE, 0, 5, 0, 6),
        pytest.param(PynguinCompare.GT, 5, 0, 0, 5),
        pytest.param(PynguinCompare.GT, 0, 5, 6, 0),
        pytest.param(PynguinCompare.GE, 5, 0, 0, 6),
        pytest.param(PynguinCompare.GE, 0, 5, 5, 0),
        pytest.param(PynguinCompare.IN, 0, [0], 0, 1),
        pytest.param(PynguinCompare.IN, 0, [1], 1, 0),
        pytest.param(PynguinCompare.IN, 0, [], inf, 0),
        pytest.param(PynguinCompare.IN, 0, (5,), 5, 0),
        pytest.param(PynguinCompare.IN, 5, (28, 42, -12), 17, 0),
        pytest.param(PynguinCompare.IN, "a", ("bba", "nope", "aa"), 1, 0),
        pytest.param(PynguinCompare.IN, object(), (object(), object()), inf, 0),
        pytest.param(PynguinCompare.NOT_IN, 0, [0], 1, 0),
        pytest.param(PynguinCompare.NOT_IN, 0, [1], 0, 1),
        pytest.param(PynguinCompare.IS, 0, 0, 0, 1),
        pytest.param(PynguinCompare.IS, 0, 1, 1, 0),
        pytest.param(PynguinCompare.IS_NOT, 0, 0, 1, 0),
        pytest.param(PynguinCompare.IS_NOT, 0, 1, 0, 1),
    ],
)
def test_cmp(  # noqa: PLR0917
    cmp,
    val1,
    val2,
    true_dist,
    false_dist,
    subject_properties: SubjectProperties,
):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(val1, val2, 0, cmp)

    assert (
        0,
        true_dist,
    ) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()
    assert (
        0,
        false_dist,
    ) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


def test_compare_ignores_proxy(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            tt.ObjectProxy(5), tt.ObjectProxy(0), 0, PynguinCompare.EQ
        )

    assert (0, 5) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()
    assert (0, 0) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


@pytest.mark.parametrize(
    "string1,string2,true_distance,false_distance",
    [
        ("a", "b", 0.5, 0),
        ("aa", "bb", 1.0, 0),
        ("aa", "cc", 2 * 2.0 / 3.0, 0),
        ("dd", "aa", 2 * 3.0 / 4.0, 0),
        ("a", "aaa", 2, 0),
        ("aaa", "a", 2, 0),
        ("aaa", "b", 2.5, 0),
        ("foo", "foo", 0, 1),
    ],
)
def test_string_equals_distance(
    string1, string2, true_distance, false_distance, subject_properties: SubjectProperties
):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            string1, string2, 0, PynguinCompare.EQ
        )

    assert (
        0,
        true_distance,
    ) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()
    assert (
        0,
        false_distance,
    ) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


@pytest.mark.parametrize(
    "string1,string2,true_distance,false_distance",
    [
        ("b", "a", 2, 0),
        ("c", "a", 3, 0),
        ("bb", "ba", 2, 0),
        ("bc", "ba", 3, 0),
        ("bc", "b", 1, 0),
        ("b", "b", 1, 0),
        ("a", "b", 0, 1),
        ("a", "bc", 0, 1),
    ],
)
def test_string_lt_distance(
    string1, string2, true_distance, false_distance, subject_properties: SubjectProperties
):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            string1, string2, 0, PynguinCompare.LT
        )

    assert (
        0,
        true_distance,
    ) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()
    assert (
        0,
        false_distance,
    ) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


@pytest.mark.parametrize(
    "string1,string2,true_distance,false_distance",
    [
        ("b", "a", 1, 0),
        ("c", "a", 2, 0),
        ("bb", "ba", 1, 0),
        ("bc", "ba", 2, 0),
        ("bc", "b", 1, 0),
        ("b", "b", 0, 1),
        ("a", "bb", 0, 2),
        ("a", "b", 0, 2),
    ],
)
def test_string_le_distance(
    string1, string2, true_distance, false_distance, subject_properties: SubjectProperties
):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            string1, string2, 0, PynguinCompare.LE
        )
    assert (
        0,
        true_distance,
    ) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()
    assert (
        0,
        false_distance,
    ) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


def test_bool_ignores_proxy(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_bool_predicate(
            tt.ObjectProxy([1, 2, 3]), 0
        )

    assert (0, 0.0) in subject_properties.instrumentation_tracer.get_trace().true_distances.items()
    assert (0, 3.0) in subject_properties.instrumentation_tracer.get_trace().false_distances.items()


def test_unknown_comp(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with pytest.raises(Exception), subject_properties.instrumentation_tracer:  # noqa: B017, PT011
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            1, 1, 0, PynguinCompare.EXC_MATCH
        )


def test_passed_bool_predicate(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_bool_predicate(True, 0)  # noqa: FBT003

    assert (
        0,
        1,
    ) in subject_properties.instrumentation_tracer.get_trace().executed_predicates.items()


@pytest.mark.parametrize(
    "val,true_dist,false_dist",
    [
        (True, 0.0, 1.0),
        (object(), 0.0, inf),
        (ExecutionTracer(), 0.0, inf),
        (False, 1.0, 0),
        ([], 1.0, 0),
        (set(), 1.0, 0),
        ({}, 1.0, 0),
        ((), 1.0, 0),
        ("", 1.0, 0),
        (b"", 1.0, 0),
        (0, 1.0, 0),
        (["something"], 0.0, 1.0),
        ({"something"}, 0.0, 1.0),
        ({"a": "something"}, 0.0, 1.0),
        (("something",), 0.0, 1.0),
        ("a", 0.0, 1.0),
        (["something", "another", "bla"], 0.0, 3.0),
        ({"something", "another", "bla"}, 0.0, 3.0),
        ({"a": "something", "b": "another", "c": "bla"}, 0.0, 3.0),
        (("something", "another", "bla"), 0.0, 3.0),
        ("abcdef", 0.0, 6.0),
        (b"abcdef", 0.0, 6.0),
        (42, 0.0, 42.0),
        (3 + 4j, 0.0, 5.0),
        (7.5, 0.0, 7.5),
    ],
)
def test_bool_distances(val, true_dist, false_dist, subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_bool_predicate(val, 0)

    assert subject_properties.instrumentation_tracer.get_trace().true_distances.get(0) == true_dist
    assert (
        subject_properties.instrumentation_tracer.get_trace().false_distances.get(0) == false_dist
    )


def test_init(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock(CodeObjectMetaData))

    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_code_object(0)

    trace = subject_properties.instrumentation_tracer.get_trace()
    subject_properties.instrumentation_tracer.init_trace()
    assert subject_properties.instrumentation_tracer.get_trace() != trace


def test_enable_disable_cmp(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))
    assert len(subject_properties.instrumentation_tracer.get_trace().executed_predicates) == 0

    subject_properties.instrumentation_tracer.disable()
    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            0, 0, 0, PynguinCompare.EQ
        )
    assert len(subject_properties.instrumentation_tracer.get_trace().executed_predicates) == 0

    subject_properties.instrumentation_tracer.enable()
    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            0, 0, 0, PynguinCompare.EQ
        )
    assert len(subject_properties.instrumentation_tracer.get_trace().executed_predicates) == 1


@pytest.mark.parametrize(
    "executed_predicates_before,executed_predicates_after,is_disabled_before,is_disabled_during,is_disabled_after,function",
    [
        # Temporarily disable when enabled
        (0, 0, False, True, False, InstrumentationExecutionTracer.temporarily_disable),
        # Temporarily disable when already disabled
        (0, 0, True, True, True, InstrumentationExecutionTracer.temporarily_disable),
        # Temporarily enable when disabled
        (0, 1, True, False, True, InstrumentationExecutionTracer.temporarily_enable),
        # Temporarily enable when already enabled
        (0, 1, False, False, False, InstrumentationExecutionTracer.temporarily_enable),
    ],
)
def test_temporarily_enable_disable_cmp(  # noqa: PLR0917
    subject_properties: SubjectProperties,
    executed_predicates_before: int,
    executed_predicates_after: int,
    is_disabled_before: bool,  # noqa: FBT001
    is_disabled_during: bool,  # noqa: FBT001
    is_disabled_after: bool,  # noqa: FBT001
    function,
):
    subject_properties.register_predicate(MagicMock(code_object_id=0))

    if is_disabled_before:
        subject_properties.instrumentation_tracer.disable()
    else:
        subject_properties.instrumentation_tracer.enable()

    assert subject_properties.instrumentation_tracer.is_disabled() is is_disabled_before
    assert (
        len(subject_properties.instrumentation_tracer.get_trace().executed_predicates)
        == executed_predicates_before
    )

    with (
        subject_properties.instrumentation_tracer,
        function(subject_properties.instrumentation_tracer),
    ):
        assert subject_properties.instrumentation_tracer.is_disabled() is is_disabled_during
        subject_properties.instrumentation_tracer.executed_compare_predicate(
            0, 0, 0, PynguinCompare.EQ
        )

    assert subject_properties.instrumentation_tracer.is_disabled() is is_disabled_after
    assert (
        len(subject_properties.instrumentation_tracer.get_trace().executed_predicates)
        == executed_predicates_after
    )


def test_enable_disable_bool(subject_properties: SubjectProperties):
    subject_properties.register_predicate(MagicMock(code_object_id=0))
    assert len(subject_properties.instrumentation_tracer.get_trace().executed_predicates) == 0

    subject_properties.instrumentation_tracer.disable()
    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_bool_predicate(True, 0)  # noqa: FBT003
    assert len(subject_properties.instrumentation_tracer.get_trace().executed_predicates) == 0

    subject_properties.instrumentation_tracer.enable()
    with subject_properties.instrumentation_tracer:
        subject_properties.instrumentation_tracer.executed_bool_predicate(True, 0)  # noqa: FBT003
    assert len(subject_properties.instrumentation_tracer.get_trace().executed_predicates) == 1


@pytest.mark.parametrize(
    "val1,val2,result",
    [
        (1, 1, 0),
        (2, 1, 1),
        ("c", "b", 1),
        (Decimal(0.5), Decimal(0.3), 0.2),  # noqa: RUF032
    ],
)
def test_le(val1, val2, result):
    assert _le(val1, val2) == result


@pytest.mark.parametrize(
    "val1,val2,result",
    [
        (0, 1, 0),
        (1, 1, 1),
        ("b", "b", 1),
        (Decimal(0.5), Decimal(0.3), 1.2),  # noqa: RUF032
    ],
)
def test_lt(val1, val2, result):
    assert _lt(val1, val2) == result


def test_default_branchless_code_object(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock())
    assert set(subject_properties.branch_less_code_objects) == {0}


def test_no_branchless_code_object(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock())
    subject_properties.register_predicate(MagicMock(code_object_id=0))
    assert sum(1 for _ in subject_properties.branch_less_code_objects) == 0


def test_no_branchless_code_object_register_multiple(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock())
    subject_properties.register_code_object(1, MagicMock())
    subject_properties.register_predicate(MagicMock(code_object_id=0))
    subject_properties.register_predicate(MagicMock(code_object_id=0))
    assert set(subject_properties.branch_less_code_objects) == {1}


def test_code_object_executed_other_thread(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock())

    def wrapper(*args):
        with pytest.raises(TracingAbortedException):
            subject_properties.instrumentation_tracer.executed_code_object(*args)

    thread = threading.Thread(target=wrapper, args=(0,))

    with subject_properties.instrumentation_tracer:
        thread.start()
        thread.join()

    assert (
        subject_properties.instrumentation_tracer.get_trace().executed_code_objects == OrderedSet()
    )


def test_bool_predicate_executed_other_thread(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock())
    subject_properties.register_code_object(1, MagicMock(code_object_id=0))

    def wrapper(*args):
        with pytest.raises(TracingAbortedException):
            subject_properties.instrumentation_tracer.executed_bool_predicate(*args)

    thread = threading.Thread(target=wrapper, args=(True, 0))

    with subject_properties.instrumentation_tracer:
        thread.start()
        thread.join()

    assert subject_properties.instrumentation_tracer.get_trace().executed_predicates == {}


def test_compare_predicate_executed_other_thread(subject_properties: SubjectProperties):
    subject_properties.register_code_object(0, MagicMock())
    subject_properties.register_code_object(1, MagicMock(code_object_id=0))

    def wrapper(*args):
        with pytest.raises(TracingAbortedException):
            subject_properties.instrumentation_tracer.executed_compare_predicate(*args)

    thread = threading.Thread(target=wrapper, args=(True, False, PynguinCompare.EQ, 0))

    with subject_properties.instrumentation_tracer:
        thread.start()
        thread.join()

    assert subject_properties.instrumentation_tracer.get_trace().executed_predicates == {}


@pytest.mark.parametrize(
    "method,inputs",
    [
        (ExecutionTracer.executed_code_object.__name__, (None,)),
        (ExecutionTracer.executed_compare_predicate.__name__, (None, None, None, None)),
        (ExecutionTracer.executed_bool_predicate.__name__, (None, None)),
        (ExecutionTracer.executed_exception_match.__name__, (None, None, None)),
        (ExecutionTracer.track_line_visit.__name__, (None,)),
    ],
)
def test_killed_by_thread_guard(method, inputs, subject_properties: SubjectProperties):
    with pytest.raises(TracingAbortedException):
        getattr(subject_properties.instrumentation_tracer, method)(*inputs)


def _mk_tracer() -> ExecutionTracer:
    tracer = ExecutionTracer()
    tracer.__enter__()  # noqa: PLC2801
    try:
        # Ensure a fresh trace
        tracer.init_trace()
    finally:
        tracer.__exit__(None, None, None)
    # Re-enter for usage in tests
    tracer.__enter__()  # noqa: PLC2801
    return tracer


def _cleanup_tracer(tracer: ExecutionTracer) -> None:
    tracer.__exit__(None, None, None)


def test_aux_in_predicate_present_key_updates_distances() -> None:
    tracer = _mk_tracer()
    try:
        d = {"k": 1}
        predicate_id = 101
        tracer.executed_in_presence_predicate("k", d, predicate_id, max_container_size=10)

        trace = tracer.get_trace()
        # Predicate should be updated
        assert predicate_id in trace.executed_predicates
        # For present key: true distance 0.0, false distance 1.0
        assert trace.true_distances[predicate_id] == 0.0
        assert trace.false_distances[predicate_id] == 1.0
    finally:
        _cleanup_tracer(tracer)


def test_aux_in_predicate_missing_key_updates_distances() -> None:
    tracer = _mk_tracer()
    try:
        d = {"k": 1}
        predicate_id = 102
        tracer.executed_in_presence_predicate("x", d, predicate_id, max_container_size=10)

        trace = tracer.get_trace()
        assert predicate_id in trace.executed_predicates
        # For missing key: false distance 0.0, true distance > 0.0
        assert trace.false_distances[predicate_id] == 0.0
        assert trace.true_distances[predicate_id] > 0.0
    finally:
        _cleanup_tracer(tracer)


def test_aux_in_predicate_size_guard_skips_large_container() -> None:
    tracer = _mk_tracer()
    try:
        # Create container larger than threshold
        d = {str(i): i for i in range(300)}
        predicate_id = 103
        tracer.executed_in_presence_predicate("k", d, predicate_id, max_container_size=10)

        trace = tracer.get_trace()
        # Guard should prevent predicate update
        assert predicate_id not in trace.executed_predicates
        assert predicate_id not in trace.true_distances
        assert predicate_id not in trace.false_distances
    finally:
        _cleanup_tracer(tracer)


def test_track_subscript_access_immutable_key_records_snapshot() -> None:
    tracer = _mk_tracer()
    try:
        d: dict[str, int] = {"k": 1}
        key = "k"
        tracer.track_subscript_access(
            module=__file__,
            code_object_id=0,
            node_id=0,
            opcode=0,  # opcode value not relevant for this unit test
            lineno=1,
            offset=0,
            container=d,
            key=key,
        )

        trace = tracer.get_trace()
        assert trace.executed_instructions, "No instructions recorded"
        instr = trace.executed_instructions[-1]
        assert isinstance(instr, ExecutedSubscriptInstruction)
        # Container and key addresses must match
        assert instr.container_address == id(d)
        assert instr.key_address == id(key)
        # Immutable key should have a snapshot repr
        assert instr.key_is_immutable is True
        assert instr.key_repr == repr(key)
    finally:
        _cleanup_tracer(tracer)


def test_track_subscript_access_mutable_key_records_no_snapshot() -> None:
    tracer = _mk_tracer()
    try:
        d: dict[Any, int] = {}
        key = [1, 2]
        tracer.track_subscript_access(
            module=__file__,
            code_object_id=0,
            node_id=0,
            opcode=0,
            lineno=1,
            offset=0,
            container=d,
            key=key,
        )

        trace = tracer.get_trace()
        instr = trace.executed_instructions[-1]
        assert isinstance(instr, ExecutedSubscriptInstruction)
        assert instr.container_address == id(d)
        assert instr.key_address == id(key)
        # Mutable key: no snapshot
        assert instr.key_is_immutable is False
        assert instr.key_repr is None
    finally:
        _cleanup_tracer(tracer)


def test_executed_subscript_result_records_immutable_value_snapshot() -> None:
    tracer = _mk_tracer()
    try:
        d = {"k": 42}
        # Simulate instrumentation: first record access, then record result value
        tracer.track_subscript_access(
            module=__file__,
            code_object_id=1,
            node_id=2,
            opcode=0,  # opcode not relevant for this unit test
            lineno=10,
            offset=0,
            container=d,
            key="k",
        )
        tracer.executed_subscript_result(
            module=__file__,
            code_object_id=1,
            node_id=2,
            opcode=0,
            lineno=10,
            offset=0,
            value=d["k"],
        )

        trace = tracer.get_trace()
        assert len(trace.executed_instructions) >= 2
        last = trace.executed_instructions[-1]
        assert isinstance(last, ExecutedSubscriptInstruction)
        assert last.value_address == id(42)
        assert last.value_is_immutable is True
        assert last.value_repr == repr(42)
    finally:
        _cleanup_tracer(tracer)


def test_executed_subscript_result_records_mutable_value_without_snapshot() -> None:
    tracer = _mk_tracer()
    try:
        v = [1, 2]
        d = {"k": v}
        tracer.track_subscript_access(
            module=__file__,
            code_object_id=3,
            node_id=4,
            opcode=0,
            lineno=20,
            offset=0,
            container=d,
            key="k",
        )
        tracer.executed_subscript_result(
            module=__file__,
            code_object_id=3,
            node_id=4,
            opcode=0,
            lineno=20,
            offset=0,
            value=v,
        )

        trace = tracer.get_trace()
        last = trace.executed_instructions[-1]
        assert isinstance(last, ExecutedSubscriptInstruction)
        assert last.value_address == id(v)
        assert last.value_is_immutable is False
        assert last.value_repr is None
    finally:
        _cleanup_tracer(tracer)
