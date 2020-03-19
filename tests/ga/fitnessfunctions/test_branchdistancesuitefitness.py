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
from unittest.mock import MagicMock

import pytest

from pynguin.ga.fitnessfunctions.branchdistancesuitefitness import (
    BranchDistanceSuiteFitnessFunction,
)
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace


@pytest.fixture
def execution_result():
    result = ExecutionResult()
    result.execution_trace = ExecutionTrace(set(), set(), set())
    return result


def test_default_fitness(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    assert ff.get_fitness(MagicMock(), execution_result) == 0


def test_fitness_function_diff(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    execution_result.execution_trace.existing_functions.add(0)
    execution_result.execution_trace.existing_functions.add(1)
    execution_result.execution_trace.existing_functions.add(2)
    execution_result.execution_trace.covered_functions.add(0)
    assert ff.get_fitness(MagicMock(), execution_result) == 2.0


def test_fitness_covered(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    execution_result.execution_trace.existing_predicates.add(0)
    execution_result.execution_trace.covered_predicates[0] = 1
    execution_result.execution_trace.false_distances[0] = 1
    execution_result.execution_trace.true_distances[0] = 0
    assert ff.get_fitness(MagicMock(), execution_result) == 1.0


def test_fitness_neither_covered(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    execution_result.execution_trace.existing_predicates.add(0)
    assert ff.get_fitness(MagicMock(), execution_result) == 2.0


def test_fitness_covered_twice(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    execution_result.execution_trace.existing_predicates.add(0)
    execution_result.execution_trace.covered_predicates[0] = 2
    execution_result.execution_trace.false_distances[0] = 1
    execution_result.execution_trace.true_distances[0] = 0
    assert ff.get_fitness(MagicMock(), execution_result) == 0.5


def test_fitness_covered_both(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    execution_result.execution_trace.existing_predicates.add(0)
    execution_result.execution_trace.covered_predicates[0] = 2
    execution_result.execution_trace.false_distances[0] = 0
    execution_result.execution_trace.true_distances[0] = 0
    assert ff.get_fitness(MagicMock(), execution_result) == 0.0


def test_fitness_uncovered_for_loop(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    execution_result.execution_trace.existing_for_loops.add(0)
    assert ff.get_fitness(MagicMock(), execution_result) == 1.0


def test_fitness_covered_for_loop(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    execution_result.execution_trace.existing_for_loops.add(0)
    execution_result.execution_trace.covered_for_loops.add(0)
    assert ff.get_fitness(MagicMock(), execution_result) == 0.0


def test_fitness_normalized(execution_result):
    ff = BranchDistanceSuiteFitnessFunction()
    execution_result.execution_trace.existing_predicates.add(0)
    execution_result.execution_trace.covered_predicates[0] = 2
    execution_result.execution_trace.false_distances[0] = 0
    execution_result.execution_trace.true_distances[0] = 7.0
    assert ff.get_fitness(MagicMock(), execution_result) == 0.875


def test_is_maximisation_function():
    ff = BranchDistanceSuiteFitnessFunction()
    assert not ff.is_maximisation_function()
