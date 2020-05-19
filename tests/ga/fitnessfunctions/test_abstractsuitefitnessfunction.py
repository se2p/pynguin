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

import pynguin.ga.fitnessfunctions.abstractsuitefitnessfunction as asff
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.ga.fitnessfunction import FitnessValues


class DummySuiteFitnessFunction(asff.AbstractSuiteFitnessFunction):
    def compute_fitness_values(self, individual) -> FitnessValues:
        pass

    def is_maximisation_function(self) -> bool:
        pass


def test_run_test_suite():
    executor = MagicMock()
    result0 = MagicMock()
    result1 = MagicMock()
    result2 = MagicMock()
    executor.execute.side_effect = [result0, result1]
    ff = DummySuiteFitnessFunction(executor)
    indiv = tsc.TestSuiteChromosome()
    test_case0 = dtc.DefaultTestCase()
    test_case0.set_changed(True)
    test_case1 = dtc.DefaultTestCase()
    test_case1.set_changed(False)
    test_case2 = dtc.DefaultTestCase()
    test_case2.set_changed(False)
    test_case2.set_last_execution_result(result2)
    indiv.add_test(test_case0)
    indiv.add_test(test_case1)
    indiv.add_test(test_case2)
    assert ff._run_test_suite(indiv) == [result0, result1, result2]
    assert test_case0.get_last_execution_result() == result0
    assert test_case1.get_last_execution_result() == result1
