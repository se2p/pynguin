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
from unittest import mock
from unittest.mock import MagicMock

import pynguin.ga.fitnessfunctions.branchcoveragesuitefitness as bcsf
import pynguin.ga.fitnessfunction as ff
from pynguin.testcase.execution.executionresult import ExecutionResult


def test_is_maximisation_function():
    fitness_function = bcsf.BranchCoverageSuiteFitness(MagicMock())
    assert not fitness_function.is_maximisation_function()


def test_get_fitness_no_result():
    executor = MagicMock()
    result = ExecutionResult()
    result.branch_coverage = 75
    executor.execute_test_suite.return_value = result
    fitness_function = bcsf.BranchCoverageSuiteFitness(executor)
    indiv = MagicMock()
    assert fitness_function.compute_fitness_values(indiv) == ff.FitnessValues(25, 0.75)
    executor.execute_test_suite.assert_called_with(indiv)
