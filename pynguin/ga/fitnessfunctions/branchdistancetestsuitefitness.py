#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provide a fitness function based on branch distances."""
from typing import Set

import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.abstracttestsuitefitnessfunction as atsff
import pynguin.ga.testsuitechromosome as tsc
from pynguin.ga.fitnessfunctions.fitness_utilities import (
    analyze_results,
    compute_branch_coverage,
    compute_branch_distance_fitness,
)
from pynguin.testcase.execution.executiontracer import ExecutionTracer


class BranchDistanceTestSuiteFitnessFunction(atsff.AbstractTestSuiteFitnessFunction):
    """A fitness function based on branch distances and entered code objects."""

    def __init__(self, executor):
        super().__init__(executor)
        self._excluded_code_objects = set()
        self._excluded_true_predicates = set()
        self._excluded_false_predicates = set()

    def restrict(
        self, exclude_code: Set[int], exclude_true: Set[int], exclude_false: Set[int]
    ):
        """Restrict this fitness function, i.e., which branches/code objects it considers"""
        self._excluded_code_objects.update(exclude_code)
        self._excluded_true_predicates.update(exclude_true)
        self._excluded_false_predicates.update(exclude_false)

    def compute_fitness_values(
        self,
        individual: tsc.TestSuiteChromosome,
    ) -> ff.FitnessValues:
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer: ExecutionTracer = self._executor.tracer

        return ff.FitnessValues(
            compute_branch_distance_fitness(
                merged_trace,
                tracer.get_known_data(),
                self._excluded_code_objects,
                self._excluded_true_predicates,
                self._excluded_false_predicates,
            ),
            compute_branch_coverage(merged_trace, tracer.get_known_data()),
        )

    def is_maximisation_function(self) -> bool:
        return False
