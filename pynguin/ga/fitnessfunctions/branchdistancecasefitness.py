#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides branch distance for test case chromosomes"""
import pynguin.ga.fitnessfunction as fitfun
import pynguin.ga.fitnessfunctions.branchdistancesuitefitness as bdsf
import pynguin.ga.testcasechromosome as tcc
from pynguin.ga.fitnessfunction import FitnessValues
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontracer import ExecutionTracer


class BranchDistanceCaseFitnessFunction(fitfun.FitnessFunction):
    """A fitness function based on branch distances and entered code objects."""

    def compute_fitness_values(
        self, individual: tcc.TestCaseChromosome
    ) -> FitnessValues:
        result = self._run_test(individual)
        _, merged_trace = bdsf.BranchDistanceSuiteFitnessFunction.analyze_traces(
            [result]
        )
        tracer: ExecutionTracer = self._executor.tracer

        return fitfun.FitnessValues(
            bdsf.BranchDistanceSuiteFitnessFunction._compute_fitness(
                merged_trace, tracer.get_known_data()
            ),
            bdsf.BranchDistanceSuiteFitnessFunction._compute_coverage(
                merged_trace, tracer.get_known_data()
            ),
        )

    def is_maximisation_function(self) -> bool:
        return False

    def _run_test(self, individual: tcc.TestCaseChromosome) -> ExecutionResult:
        if individual.has_changed() or individual.get_last_execution_result() is None:
            individual.set_last_execution_result(
                self._executor.execute(individual.test_case)
            )
            individual.set_changed(False)
        result = individual.get_last_execution_result()
        assert result is not None
        return result
