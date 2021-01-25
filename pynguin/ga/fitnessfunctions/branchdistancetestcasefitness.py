#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides branch distance for test case chromosomes"""
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.abstracttestcasefitnessfunction as atcff
import pynguin.ga.testcasechromosome as tcc
from pynguin.ga.fitnessfunctions.fitness_utilities import (
    analyze_results,
    compute_branch_coverage,
    compute_branch_distance_fitness,
)
from pynguin.testcase.execution.executiontracer import ExecutionTracer


class BranchDistanceTestCaseFitnessFunction(atcff.AbstractTestCaseFitnessFunction):
    """A fitness function based on branch distances and entered code objects."""

    def compute_fitness_values(
        self, individual: tcc.TestCaseChromosome
    ) -> ff.FitnessValues:
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer: ExecutionTracer = self._executor.tracer

        return ff.FitnessValues(
            compute_branch_distance_fitness(merged_trace, tracer.get_known_data()),
            compute_branch_coverage(merged_trace, tracer.get_known_data()),
        )

    def is_maximisation_function(self) -> bool:
        return False
