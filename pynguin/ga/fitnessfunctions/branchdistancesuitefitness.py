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
from typing import Dict, List, Tuple

import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.abstractsuitefitnessfunction as asff
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace
from pynguin.testcase.execution.executiontracer import ExecutionTracer, KnownData


class BranchDistanceSuiteFitnessFunction(asff.AbstractSuiteFitnessFunction):
    """A fitness function based on branch distances and entered code objects."""

    def compute_fitness_values(
        self, individual: tsc.TestSuiteChromosome,
    ) -> ff.FitnessValues:
        results = self._run_test_suite(individual)
        _, merged_trace = self.analyze_traces(results)
        tracer: ExecutionTracer = self._executor.get_tracer()

        return ff.FitnessValues(
            self._compute_fitness(merged_trace, tracer.get_known_data()),
            self._compute_coverage(merged_trace, tracer.get_known_data()),
        )

    @staticmethod
    def _compute_fitness(trace: ExecutionTrace, known_data: KnownData) -> float:
        # Check if all code objects were executed.
        code_objects_missing: float = len(known_data.existing_code_objects) - len(
            trace.executed_code_objects
        )
        assert (
            code_objects_missing >= 0.0
        ), "Amount of non covered code objects cannot be negative"
        # Check if all predicates are covered
        predicate_fitness: float = 0.0
        for predicate in known_data.existing_predicates:
            predicate_fitness += BranchDistanceSuiteFitnessFunction._predicate_fitness(
                predicate, trace.true_distances, trace
            )
            predicate_fitness += BranchDistanceSuiteFitnessFunction._predicate_fitness(
                predicate, trace.false_distances, trace
            )
        assert predicate_fitness >= 0.0, "Predicate fitness cannot be negative."
        total_fitness = code_objects_missing + predicate_fitness
        return total_fitness

    @staticmethod
    def _predicate_fitness(
        predicate: int, branch_distances: Dict[int, float], trace: ExecutionTrace
    ) -> float:
        if predicate in branch_distances and branch_distances[predicate] == 0.0:
            return 0.0
        if (
            predicate in trace.executed_predicates
            and trace.executed_predicates[predicate] >= 2
        ):
            return BranchDistanceSuiteFitnessFunction.normalise(
                branch_distances[predicate]
            )
        return 1.0

    @staticmethod
    def _compute_coverage(trace: ExecutionTrace, known_data: KnownData) -> float:
        """Computes branch coverage on bytecode instructions which should equal
        decision coverage on source.

        Args:
            trace: The execution trace
            known_data: All known data

        Returns:
            The computed coverage value
        """

        covered = len(trace.executed_code_objects)
        existing = len(known_data.existing_code_objects)

        # Every predicate creates two branches
        existing += len(known_data.existing_predicates) * 2

        # A branch is covered if it has a distance of 0.0
        # Must consider both branches created by a predicate, i.e. true and false.
        covered += len([v for v in trace.true_distances.values() if v == 0.0])
        covered += len([v for v in trace.false_distances.values() if v == 0.0])

        if existing == 0:
            # Nothing to cover => everything is covered.
            coverage = 1.0
        else:
            coverage = covered / existing
        assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
        return coverage

    def is_maximisation_function(self) -> bool:
        return False

    @staticmethod
    def analyze_traces(results: List[ExecutionResult]) -> Tuple[bool, ExecutionTrace]:
        """Analyze the given traces.

        Args:
            results: The list of execution results to analyse

        Returns:
            A tuple that tells whether or not a trace contained an exception and the
            merged traces.
        """
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
        """Compute the worst possible fitness value.

        Can be used to penalize time outs.

        Args:
             known_data: The known data about the executions

        Returns:
            The worst fitness value
        """
        return (
            len(known_data.existing_code_objects)
            + len(known_data.existing_predicates) * 2
        )
