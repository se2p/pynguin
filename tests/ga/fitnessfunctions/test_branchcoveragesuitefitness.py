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

import pynguin.ga.fitnessfunctions.branchcoveragesuitefitness as bcsf
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.testcase.execution.executionresult import ExecutionResult


@pytest.fixture
def individual():
    return tsc.TestSuiteChromosome()


@pytest.fixture
def fitness_function():
    return bcsf.BranchCoverageSuiteFitness()


@pytest.fixture
def execution_result():
    result = ExecutionResult()
    result.branch_coverage = 75
    return result


def test_is_maximisation_function(fitness_function):
    assert not fitness_function.is_maximisation_function()


def test_get_fitness_no_result(fitness_function, individual):
    assert fitness_function.get_fitness(individual) == 0.0


def test_get_fitness(fitness_function, individual, execution_result):
    assert fitness_function.get_fitness(individual, execution_result) == 0.75
