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
import pytest
from bytecode import Compare  # type: ignore

from pynguin.instrumentation.tracking import ExecutionTracer


def test_default_fitness():
    tracer = ExecutionTracer()
    assert tracer.get_fitness() == 0.0


def test_fitness_function_diff():
    tracer = ExecutionTracer()
    tracer.function_exists(0)
    tracer.function_exists(1)
    tracer.function_exists(2)
    tracer.entered_function(0)
    assert tracer.get_fitness() == 2.0


def test_fitness_covered():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_bool_predicate(True, 0)
    assert tracer.get_fitness() == 1.0


def test_fitness_neither_covered():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    assert tracer.get_fitness() == 2.0


def test_fitness_covered_twice():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_bool_predicate(True, 0)
    tracer.passed_bool_predicate(True, 0)
    assert tracer.get_fitness() == 0.5


def test_fitness_covered_both():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_bool_predicate(True, 0)
    tracer.passed_bool_predicate(False, 0)
    assert tracer.get_fitness() == 0.0


def test_fitness_normalized():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_cmp_predicate(7, 0, 0, Compare.EQ)
    tracer.passed_cmp_predicate(7, 0, 0, Compare.EQ)
    assert tracer.get_fitness() == 0.875


def test_clear_tracking():
    tracer = ExecutionTracer()
    tracer.function_exists(0)
    tracer.entered_function(0)
    tracer.predicate_exists(0)
    tracer.passed_bool_predicate(True, 0)
    assert tracer.get_fitness() == 1.0
    tracer.clear_tracking()
    assert tracer.get_fitness() == 3.0


def test_functions_exists():
    tracer = ExecutionTracer()
    tracer.function_exists(0)
    assert 0 in tracer.existing_functions


def test_entered_function():
    tracer = ExecutionTracer()
    tracer.function_exists(0)
    tracer.entered_function(0)
    assert 0 in tracer.covered_functions


def test_predicate_exists():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    assert 0 in tracer.existing_predicates


def test_update_metrics_covered():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_cmp_predicate(1, 0, 0, Compare.EQ)
    tracer.passed_cmp_predicate(1, 0, 0, Compare.EQ)
    assert (0, 2) in tracer.covered_predicates.items()


def test_update_metrics_true_dist_min():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_cmp_predicate(5, 0, 0, Compare.EQ)
    assert (0, 5) in tracer.true_distances.items()
    tracer.passed_cmp_predicate(4, 0, 0, Compare.EQ)
    assert (0, 4) in tracer.true_distances.items()


def test_update_metrics_false_dist_min():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_cmp_predicate(3, 1, 0, Compare.NE)
    assert (0, 2) in tracer.false_distances.items()
    tracer.passed_cmp_predicate(2, 1, 0, Compare.NE)
    assert (0, 1) in tracer.false_distances.items()


def test_passed_cmp_predicate():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_cmp_predicate(1, 0, 0, Compare.EQ)
    assert (0, 1) in tracer.covered_predicates.items()


@pytest.mark.parametrize(
    "cmp,val1,val2,true_dist,false_dist",
    [
        pytest.param(Compare.EQ, 5, 0, 5, 0),
        pytest.param(Compare.EQ, 0, 0, 0, 1),
        pytest.param(Compare.EQ, "string", 0, 1, 0),
        pytest.param(Compare.NE, 5, 0, 0, 5),
        pytest.param(Compare.NE, 0, 0, 1, 0),
        pytest.param(Compare.NE, "string", 0, 0, 1),
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
    tracer.predicate_exists(0)
    tracer.passed_cmp_predicate(val1, val2, 0, cmp)
    assert (0, true_dist) in tracer.true_distances.items()
    assert (0, false_dist) in tracer.false_distances.items()


def test_unknown_comp():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    with pytest.raises(Exception):
        tracer.passed_cmp_predicate(1, 1, 0, Compare.EXC_MATCH)


def test_passed_bool_predicate():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_bool_predicate(True, 0)
    assert (0, 1) in tracer.covered_predicates.items()


def test_bool_distance_true():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_bool_predicate(True, 0)
    assert (0, 0.0) in tracer.true_distances.items()
    assert (0, 1.0) in tracer.false_distances.items()


def test_bool_distance_false():
    tracer = ExecutionTracer()
    tracer.predicate_exists(0)
    tracer.passed_bool_predicate(False, 0)
    assert (0, 1.0) in tracer.true_distances.items()
    assert (0, 0.0) in tracer.false_distances.items()
