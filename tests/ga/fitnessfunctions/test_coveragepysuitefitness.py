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
from unittest.mock import MagicMock, call

import pynguin.ga.fitnessfunctions.coveragepysuitefitness as cpsf
import pynguin.ga.fitnessfunction as ff
import pynguin.testcase.testcase as tc
from pynguin.testcase.execution.executionresult import ExecutionResult


def test_is_maximisation_function():
    fitness_function = cpsf.CoveragePySuiteFitness(MagicMock())
    assert not fitness_function.is_maximisation_function()


def test_get_fitness_no_result():
    executor = MagicMock()
    result = ExecutionResult()
    result.coverage = 75
    executor.execute.return_value = result
    fitness_function = cpsf.CoveragePySuiteFitness(executor)
    test_case = MagicMock(tc.TestCase)
    indiv = MagicMock()
    indiv.test_chromosomes = [test_case]
    assert fitness_function.compute_fitness_values(indiv) == ff.FitnessValues(25, 0.75)
    executor.execute.assert_has_calls([call([test_case], measure_coverage=True)])
