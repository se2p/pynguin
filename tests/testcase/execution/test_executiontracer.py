#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import threading

from decimal import Decimal
from math import inf
from unittest.mock import MagicMock

import pytest

import pynguin.utils.typetracing as tt

from pynguin.instrumentation.instrumentation import CodeObjectMetaData
from pynguin.instrumentation.instrumentation import PynguinCompare
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.instrumentation.tracer import _le  # noqa: PLC2701
from pynguin.instrumentation.tracer import _lt  # noqa: PLC2701
from pynguin.utils.orderedset import OrderedSet


def test_functions_exists():
    tracer = ExecutionTracer()
    assert tracer.register_code_object(MagicMock(CodeObjectMetaData)) == 0
    assert tracer.register_code_object(MagicMock(CodeObjectMetaData)) == 1
    assert 0 in tracer.get_subject_properties().existing_code_objects


def test_entered_function():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_code_object(MagicMock(CodeObjectMetaData))
    tracer.executed_code_object(0)
    assert 0 in tracer.get_trace().executed_code_objects


def test_predicate_exists():
    tracer = ExecutionTracer()
    assert tracer.register_predicate(MagicMock(code_object_id=0)) == 0
    assert tracer.register_predicate(MagicMock(code_object_id=0)) == 1
    assert 0 in tracer.get_subject_properties().existing_predicates


def test_line_registration():
    tracer = ExecutionTracer()
    assert tracer.register_line(0, "foo", 42) == 0
    assert tracer.register_line(0, "foo", 43) == 1
    assert tracer.register_line(0, "bar", 42) == 2
    assert tracer.register_line(1, "foo", 42) == 0
    assert {0, 1, 2} == tracer.get_subject_properties().existing_lines.keys()


def test_line_visit():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.track_line_visit(42)
    tracer.track_line_visit(43)
    tracer.track_line_visit(42)
    assert tracer.get_trace().covered_line_ids == OrderedSet([42, 43])


def test_update_metrics_covered():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(1, 0, 0, PynguinCompare.EQ)
    tracer.executed_compare_predicate(1, 0, 0, PynguinCompare.EQ)
    assert (0, 2) in tracer.get_trace().executed_predicates.items()


@pytest.mark.parametrize("true_dist,false_dist", [(-1, 0), (0, -1), (0, 0), (1, 1)])
def test_update_metrics_assertions(true_dist, false_dist):
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(code_object_id=0))
    with pytest.raises(AssertionError):
        tracer._update_metrics(false_dist, true_dist, 0)


def test_update_metrics_true_dist_min():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(5, 0, 0, PynguinCompare.EQ)
    assert (0, 5) in tracer.get_trace().true_distances.items()
    tracer.executed_compare_predicate(4, 0, 0, PynguinCompare.EQ)
    assert (0, 4) in tracer.get_trace().true_distances.items()


def test_update_metrics_false_dist_min():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(3, 1, 0, PynguinCompare.NE)
    assert (0, 2) in tracer.get_trace().false_distances.items()
    tracer.executed_compare_predicate(2, 1, 0, PynguinCompare.NE)
    assert (0, 1) in tracer.get_trace().false_distances.items()


def test_passed_cmp_predicate():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(1, 0, 0, PynguinCompare.EQ)
    assert (0, 1) in tracer.get_trace().executed_predicates.items()


def test_passed_exception_match():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_exception_match(ValueError(), ValueError, 0)
    assert (0, 1) in tracer.get_trace().executed_predicates.items()
    assert (0, 0.0) in tracer.get_trace().true_distances.items()
    assert (0, 1.0) in tracer.get_trace().false_distances.items()


def test_passed_exception_match_not():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_exception_match(NameError(), ValueError, 0)
    assert (0, 1) in tracer.get_trace().executed_predicates.items()
    assert (0, 1.0) in tracer.get_trace().true_distances.items()
    assert (0, 0.0) in tracer.get_trace().false_distances.items()


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
def test_cmp(cmp, val1, val2, true_dist, false_dist):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(val1, val2, 0, cmp)
    assert (0, true_dist) in tracer.get_trace().true_distances.items()
    assert (0, false_dist) in tracer.get_trace().false_distances.items()


def test_compare_ignores_proxy():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(tt.ObjectProxy(5), tt.ObjectProxy(0), 0, PynguinCompare.EQ)
    assert (0, 5) in tracer.get_trace().true_distances.items()
    assert (0, 0) in tracer.get_trace().false_distances.items()


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
def test_string_equals_distance(string1, string2, true_distance, false_distance):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(string1, string2, 0, PynguinCompare.EQ)
    assert (0, true_distance) in tracer.get_trace().true_distances.items()
    assert (0, false_distance) in tracer.get_trace().false_distances.items()


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
def test_string_lt_distance(string1, string2, true_distance, false_distance):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(string1, string2, 0, PynguinCompare.LT)
    assert (0, true_distance) in tracer.get_trace().true_distances.items()
    assert (0, false_distance) in tracer.get_trace().false_distances.items()


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
def test_string_le_distance(string1, string2, true_distance, false_distance):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_compare_predicate(string1, string2, 0, PynguinCompare.LE)
    assert (0, true_distance) in tracer.get_trace().true_distances.items()
    assert (0, false_distance) in tracer.get_trace().false_distances.items()


def test_bool_ignores_proxy():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_bool_predicate(tt.ObjectProxy([1, 2, 3]), 0)
    assert (0, 0.0) in tracer.get_trace().true_distances.items()
    assert (0, 3.0) in tracer.get_trace().false_distances.items()


def test_unknown_comp():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    with pytest.raises(Exception):  # noqa: B017, PT011
        tracer.executed_compare_predicate(1, 1, 0, PynguinCompare.EXC_MATCH)


def test_passed_bool_predicate():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.executed_bool_predicate(True, 0)  # noqa: FBT003
    assert (0, 1) in tracer.get_trace().executed_predicates.items()


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
def test_bool_distances(val, true_dist, false_dist):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.executed_bool_predicate(val, 0)
    assert tracer.get_trace().true_distances.get(0) == true_dist
    assert tracer.get_trace().false_distances.get(0) == false_dist


def test_init():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_code_object(MagicMock(CodeObjectMetaData))
    tracer.executed_code_object(0)
    trace = tracer.get_trace()
    tracer.init_trace()
    assert tracer.get_trace() != trace


def test_enable_disable_cmp():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    assert len(tracer.get_trace().executed_predicates) == 0

    tracer.disable()
    tracer.executed_compare_predicate(0, 0, 0, PynguinCompare.EQ)
    assert len(tracer.get_trace().executed_predicates) == 0

    tracer.enable()
    tracer.executed_compare_predicate(0, 0, 0, PynguinCompare.EQ)
    assert len(tracer.get_trace().executed_predicates) == 1


def test_enable_disable_bool():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_predicate(MagicMock(code_object_id=0))
    assert len(tracer.get_trace().executed_predicates) == 0

    tracer.disable()
    tracer.executed_bool_predicate(True, 0)  # noqa: FBT003
    assert len(tracer.get_trace().executed_predicates) == 0

    tracer.enable()
    tracer.executed_bool_predicate(True, 0)  # noqa: FBT003
    assert len(tracer.get_trace().executed_predicates) == 1


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


def test_default_branchless_code_object():
    tracer = ExecutionTracer()
    tracer.register_code_object(MagicMock())
    assert tracer.get_subject_properties().branch_less_code_objects == OrderedSet([0])


def test_no_branchless_code_object():
    tracer = ExecutionTracer()
    tracer.register_code_object(MagicMock())
    tracer.register_predicate(MagicMock(code_object_id=0))
    assert len(tracer.get_subject_properties().branch_less_code_objects) == 0


def test_no_branchless_code_object_register_multiple():
    tracer = ExecutionTracer()
    tracer.register_code_object(MagicMock())
    tracer.register_code_object(MagicMock())
    tracer.register_predicate(MagicMock(code_object_id=0))
    tracer.register_predicate(MagicMock(code_object_id=0))
    assert tracer.get_subject_properties().branch_less_code_objects == OrderedSet([1])


def test_code_object_executed_other_thread():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_code_object(MagicMock())

    def wrapper(*args):
        with pytest.raises(RuntimeError):
            tracer.executed_code_object(*args)

    thread = threading.Thread(target=wrapper, args=(0,))
    thread.start()
    thread.join()
    assert tracer.get_trace().executed_code_objects == OrderedSet()


def test_bool_predicate_executed_other_thread():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_code_object(MagicMock())
    tracer.register_code_object(MagicMock(code_object_id=0))

    def wrapper(*args):
        with pytest.raises(RuntimeError):
            tracer.executed_bool_predicate(*args)

    thread = threading.Thread(target=wrapper, args=(True, 0))
    thread.start()
    thread.join()
    assert tracer.get_trace().executed_predicates == {}


def test_compare_predicate_executed_other_thread():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    tracer.register_code_object(MagicMock())
    tracer.register_code_object(MagicMock(code_object_id=0))

    def wrapper(*args):
        with pytest.raises(RuntimeError):
            tracer.executed_compare_predicate(*args)

    thread = threading.Thread(target=wrapper, args=(True, False, PynguinCompare.EQ, 0))
    thread.start()
    thread.join()
    assert tracer.get_trace().executed_predicates == {}


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
def test_killed_by_thread_guard(method, inputs):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident + 1
    with pytest.raises(RuntimeError):
        getattr(tracer, method)(*inputs)
