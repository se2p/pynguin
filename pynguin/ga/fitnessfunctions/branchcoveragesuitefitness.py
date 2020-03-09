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
from typing import Optional

import pynguin.ga.fitnessfunction as ff
from pynguin.testcase.execution.executionresult import ExecutionResult


class BranchCoverageSuiteFitness(ff.FitnessFunction):
    """A fitness function for branch coverage."""

    def get_fitness(
        self, individual, execution_result: Optional[ExecutionResult] = None
    ) -> float:
        if not execution_result:
            individual.set_coverage(self, 0.0)
        else:
            individual.set_coverage(self, execution_result.branch_coverage / 100.0)

        coverage = individual.get_coverage(self)
        assert 0.0 <= coverage <= 1.0, f"Illegal coverage value {coverage}"
        self.update_individual(self, individual, coverage)
        return coverage

    def is_maximisation_function(self) -> bool:
        return False
