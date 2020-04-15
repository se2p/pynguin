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
"""A fitness function for branch coverage."""
import pynguin.ga.fitnessfunctions.abstractsuitefitnessfunction as asff
import pynguin.ga.fitnessfunction as ff
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.testcase.execution.executionresult import ExecutionResult


class CoveragePySuiteFitness(asff.AbstractSuiteFitnessFunction):
    """A fitness function for the coverage values measured by Coverage.py.
    This can be line or branch coverage, depending on the configuration."""

    def compute_fitness_values(
        self, individual: tsc.TestSuiteChromosome
    ) -> ff.FitnessValues:
        result = self._run_test_suite_with_coverage_py(individual)
        assert result.coverage
        return ff.FitnessValues(100.0 - result.coverage, result.coverage / 100.0)

    def is_maximisation_function(self) -> bool:
        return False

    def _run_test_suite_with_coverage_py(
        self, individual: tsc.TestSuiteChromosome
    ) -> ExecutionResult:
        """Unfortunately the CoveragePy API does not allow us to cache executions.
        Therefore we have to execute every test case..."""
        # TODO(fk) enable caching of coverage py results.
        return self._executor.execute(
            individual.test_chromosomes, measure_coverage=True
        )
