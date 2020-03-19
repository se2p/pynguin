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
"""Provide a fitness function based on branch distances."""
from typing import Dict, Optional

import pynguin.ga.fitnessfunction as ff
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace


class BranchDistanceSuiteFitnessFunction(ff.FitnessFunction):

    """A fitness function based on the branch distances and entered methods/loops."""

    def get_fitness(
        self,
        individual: tsc.TestSuiteChromosome,
        execution_result: Optional[ExecutionResult] = None,
    ) -> float:
        assert execution_result, "Need execution result."
        trace = execution_result.execution_trace
        assert trace, "Need trace for fitness."

        # Check if all functions were entered.
        functions_missing: float = len(trace.existing_functions) - len(
            trace.covered_functions
        )
        assert (
            functions_missing >= 0.0
        ), "Amount of non covered functions cannot be negative"

        # Check if all for loops were entered.
        for_loops_missing = len(trace.existing_for_loops) - len(trace.covered_for_loops)
        assert (
            for_loops_missing >= 0.0
        ), "Amount of non covered for loops cannot be negative"

        # Check if all predicates are covered
        predicate_fitness: float = 0.0
        for predicate in trace.existing_predicates:
            predicate_fitness += self._predicate_fitness(
                predicate, trace.true_distances, trace
            )
            predicate_fitness += self._predicate_fitness(
                predicate, trace.false_distances, trace
            )
        assert predicate_fitness >= 0.0, "Predicate fitness cannot be negative."

        total_fitness = functions_missing + for_loops_missing + predicate_fitness
        self.update_individual(self, individual, total_fitness)
        return total_fitness

    def _predicate_fitness(
        self, predicate: int, branch_distances: Dict[int, float], trace: ExecutionTrace
    ) -> float:
        if predicate in branch_distances and branch_distances[predicate] == 0.0:
            return 0.0
        if (
            predicate in trace.covered_predicates
            and trace.covered_predicates[predicate] >= 2
        ):
            return self.normalise(branch_distances[predicate])
        return 1.0

    def is_maximisation_function(self) -> bool:
        return False
