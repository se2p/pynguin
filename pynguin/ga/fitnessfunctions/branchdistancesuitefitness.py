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
from typing import Dict, Tuple, List

import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.abstractsuitefitnessfunction as asff
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace
from pynguin.testcase.execution.executiontracer import KnownData


class BranchDistanceSuiteFitnessFunction(asff.AbstractSuiteFitnessFunction):
    """A fitness function based on branch distances and entered code objects/loops."""

    def compute_fitness_values(
        self, individual: tsc.TestSuiteChromosome,
    ) -> ff.FitnessValues:
        results = self._run_test_suite(individual)
        has_exception, merged_trace = self.analyze_traces(results)
        tracer = self._executor.get_tracer()

        return self._compute(has_exception, merged_trace, tracer.get_known_data())

    def _compute(
        self, has_exception, merged_trace, known_data: KnownData
    ) -> ff.FitnessValues:
        # Check if all code objects were entered.
        code_objects_missing: float = len(known_data.existing_code_objects) - len(
            merged_trace.covered_code_objects
        )
        assert (
            code_objects_missing >= 0.0
        ), "Amount of non covered code objects cannot be negative"
        # Check if all for loops were entered.
        for_loops_missing = len(known_data.existing_for_loops) - len(
            merged_trace.covered_for_loops
        )
        assert (
            for_loops_missing >= 0.0
        ), "Amount of non covered for loops cannot be negative"
        # Check if all predicates are covered
        predicate_fitness: float = 0.0
        for predicate in known_data.existing_predicates:
            predicate_fitness += self._predicate_fitness(
                predicate, merged_trace.true_distances, merged_trace
            )
            predicate_fitness += self._predicate_fitness(
                predicate, merged_trace.false_distances, merged_trace
            )
        assert predicate_fitness >= 0.0, "Predicate fitness cannot be negative."
        total_fitness = code_objects_missing + for_loops_missing + predicate_fitness
        # TODO(fk) compute coverage.
        if has_exception:
            return ff.FitnessValues(self.get_worst_fitness(known_data), 0)
        return ff.FitnessValues(total_fitness, 0)

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

    @staticmethod
    def analyze_traces(results: List[ExecutionResult]) -> Tuple[bool, ExecutionTrace]:
        """Analyze the given traces."""
        has_exception = False
        merged = ExecutionTrace()
        for result in results:
            trace = result.execution_trace
            assert trace
            merged.merge(trace)
            if result.has_test_exceptions():
                has_exception = True
        return has_exception, merged

    @staticmethod
    def get_worst_fitness(known_data: KnownData) -> float:
        """Compute the worst possible fitness value."""
        return (
            len(known_data.existing_code_objects)
            + len(known_data.existing_predicates) * 2
            + len(known_data.existing_for_loops)
        )
