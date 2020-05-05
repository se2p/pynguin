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
from math import inf
from unittest.mock import MagicMock

import pytest
from bytecode import Compare

from pynguin.testcase.execution.executiontracer import (
    ExecutionTracer,
    _le,
    _lt,
    CodeObjectMetaData,
    PredicateMetaData,
)


def test_functions_exists():
    tracer = ExecutionTracer()
    assert tracer.register_code_object(MagicMock(CodeObjectMetaData)) == 0
    assert tracer.register_code_object(MagicMock(CodeObjectMetaData)) == 1
    assert 0 in tracer.get_known_data().existing_code_objects


def test_entered_function():
    tracer = ExecutionTracer()
    tracer.register_code_object(MagicMock(CodeObjectMetaData))
    tracer.entered_code_object(0)
    assert 0 in tracer.get_trace().covered_code_objects


def test_predicate_exists():
    tracer = ExecutionTracer()
    assert tracer.register_predicate(MagicMock(PredicateMetaData)) == 0
    assert tracer.register_predicate(MagicMock(PredicateMetaData)) == 1
    assert 0 in tracer.get_known_data().existing_predicates


def test_update_metrics_covered():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    tracer.passed_cmp_predicate(1, 0, 0, Compare.EQ)
    tracer.passed_cmp_predicate(1, 0, 0, Compare.EQ)
    assert (0, 2) in tracer.get_trace().covered_predicates.items()


@pytest.mark.parametrize("true_dist,false_dist", [(-1, 0), (0, -1), (0, 0), (1, 1)])
def test_update_metrics_assertions(true_dist, false_dist):
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    with pytest.raises(AssertionError):
        tracer._update_metrics(false_dist, true_dist, 0)


def test_update_metrics_true_dist_min():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    tracer.passed_cmp_predicate(5, 0, 0, Compare.EQ)
    assert (0, 5) in tracer.get_trace().true_distances.items()
    tracer.passed_cmp_predicate(4, 0, 0, Compare.EQ)
    assert (0, 4) in tracer.get_trace().true_distances.items()


def test_update_metrics_false_dist_min():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    tracer.passed_cmp_predicate(3, 1, 0, Compare.NE)
    assert (0, 2) in tracer.get_trace().false_distances.items()
    tracer.passed_cmp_predicate(2, 1, 0, Compare.NE)
    assert (0, 1) in tracer.get_trace().false_distances.items()


def test_passed_cmp_predicate():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    tracer.passed_cmp_predicate(1, 0, 0, Compare.EQ)
    assert (0, 1) in tracer.get_trace().covered_predicates.items()


@pytest.mark.parametrize(
    "cmp,val1,val2,true_dist,false_dist",
    [
        pytest.param(Compare.EQ, 5, 0, 5, 0),
        pytest.param(Compare.EQ, 0, 0, 0, 1),
        pytest.param(Compare.EQ, "string", 0, inf, 0),
        pytest.param(Compare.EQ, "abc", "cde", 3, 0),
        pytest.param(Compare.NE, 5, 0, 0, 5),
        pytest.param(Compare.NE, 0, 0, 1, 0),
        pytest.param(Compare.NE, "string", 0, 0, inf),
        pytest.param(Compare.NE, "abc", "cde", 0, 3),
        pytest.param(Compare.LT, 5, 0, 6, 0),
        pytest.param(Compare.LT, 0, 5, 0, 6),
        pytest.param(Compare.LE, 5, 0, 6, 0),
        pytest.param(Compare.LE, 0, 5, 0, 6),
        pytest.param(Compare.GT, 5, 0, 0, 6),
        pytest.param(Compare.GT, 0, 5, 6, 0),
        pytest.param(Compare.GE, 5, 0, 0, 6),
        pytest.param(Compare.GE, 0, 5, 6, 0),
        pytest.param(Compare.IN, 0, [0], 0, 1),
        pytest.param(Compare.IN, 0, [1], 1, 0),
        pytest.param(Compare.NOT_IN, 0, [0], 1, 0),
        pytest.param(Compare.NOT_IN, 0, [1], 0, 1),
        pytest.param(Compare.IS, 0, 0, 0, 1),
        pytest.param(Compare.IS, 0, 1, 1, 0),
        pytest.param(Compare.IS_NOT, 0, 0, 1, 0),
        pytest.param(Compare.IS_NOT, 0, 1, 0, 1),
    ],
)
def test_cmp(cmp, val1, val2, true_dist, false_dist):
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    tracer.passed_cmp_predicate(val1, val2, 0, cmp)
    assert (0, true_dist) in tracer.get_trace().true_distances.items()
    assert (0, false_dist) in tracer.get_trace().false_distances.items()


def test_unknown_comp():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    with pytest.raises(Exception):
        tracer.passed_cmp_predicate(1, 1, 0, Compare.EXC_MATCH)


def test_passed_bool_predicate():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    tracer.passed_bool_predicate(True, 0)
    assert (0, 1) in tracer.get_trace().covered_predicates.items()


def test_bool_distance_true():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    tracer.passed_bool_predicate(True, 0)
    assert (0, 0.0) in tracer.get_trace().true_distances.items()
    assert (0, 1.0) in tracer.get_trace().false_distances.items()


def test_bool_distance_false():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    tracer.passed_bool_predicate(False, 0)
    assert (0, 1.0) in tracer.get_trace().true_distances.items()
    assert (0, 0.0) in tracer.get_trace().false_distances.items()


def test_clear():
    tracer = ExecutionTracer()
    tracer.register_code_object(MagicMock(CodeObjectMetaData))
    tracer.entered_code_object(0)
    trace = tracer.get_trace()
    tracer.clear_trace()
    assert tracer.get_trace() != trace


def test_enable_disable_cmp():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    assert len(tracer.get_trace().covered_predicates) == 0

    tracer._disable()
    tracer.passed_cmp_predicate(0, 0, 0, Compare.EQ)
    assert len(tracer.get_trace().covered_predicates) == 0

    tracer._enable()
    tracer.passed_cmp_predicate(0, 0, 0, Compare.EQ)
    assert len(tracer.get_trace().covered_predicates) == 1


def test_enable_disable_bool():
    tracer = ExecutionTracer()
    tracer.register_predicate(MagicMock(PredicateMetaData))
    assert len(tracer.get_trace().covered_predicates) == 0

    tracer._disable()
    tracer.passed_bool_predicate(True, 0)
    assert len(tracer.get_trace().covered_predicates) == 0

    tracer._enable()
    tracer.passed_bool_predicate(True, 0)
    assert len(tracer.get_trace().covered_predicates) == 1


@pytest.mark.parametrize("val1,val2,result", [(1, 1, 0), (2, 1, 2), ("c", "b", inf)])
def test_le(val1, val2, result):
    assert _le(val1, val2) == result


@pytest.mark.parametrize("val1,val2,result", [(0, 1, 0), (1, 1, 1), ("b", "b", inf)])
def test_lt(val1, val2, result):
    assert _lt(val1, val2) == result
