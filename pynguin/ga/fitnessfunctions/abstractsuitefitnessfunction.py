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
"""Provides an abstract fitness function for test suites."""
from abc import ABCMeta
from typing import List

import pynguin.ga.fitnessfunction as ff
from pynguin.testcase.execution.executionresult import ExecutionResult


# pylint: disable=abstract-method
class AbstractSuiteFitnessFunction(ff.FitnessFunction, metaclass=ABCMeta):
    """Abstract fitness function for test suites.
    """

    def _run_test_suite(self, individual) -> List[ExecutionResult]:
        """Runs a test suite and updates the execution results for
        all test cases that were changed.

        Args:
            individual: The individual to run

        Returns:
            A list of execution results
        """
        results: List[ExecutionResult] = []
        for test_case in individual.test_chromosomes:
            if test_case.has_changed() or test_case.get_last_execution_result() is None:
                test_case.set_last_execution_result(self._executor.execute([test_case]))
                test_case.set_changed(False)
            result = test_case.get_last_execution_result()
            assert result
            results.append(result)
        return results
