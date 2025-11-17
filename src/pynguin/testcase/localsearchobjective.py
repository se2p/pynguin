#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the objective for local search."""

from __future__ import annotations

import enum
import logging
import time
from typing import TYPE_CHECKING

import pynguin.utils.statistics.stats as stat
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pynguin.ga.computations import CoverageFunction, FitnessFunction
    from pynguin.ga.testcasechromosome import TestCaseChromosome
    from pynguin.ga.testsuitechromosome import TestSuiteChromosome


class LocalSearchObjective:
    """Monitors the success of the current local search on a chromosome."""

    _logger = logging.getLogger(__name__)

    def __init__(self, test_suite: TestSuiteChromosome, position: int) -> None:
        """Create a new local search objective object.

        Args:
            position: The position of the specific test case which will be modified.
            test_suite: The whole testsuite.
        """
        self._old_fitness: float = 0.0
        self._test_suite = test_suite
        self._position = position
        self._fitness_functions = test_suite.get_fitness_functions()
        self._latest_coverage_map: dict[CoverageFunction, float] = {}
        self._latest_fitness_map: dict[FitnessFunction, float] = {}
        self._update_latest_fitness_map()
        self._update_latest_coverage_map()

        self._is_maximization = (
            self._fitness_functions[0].is_maximisation_function()
            if self._fitness_functions
            else False
        )

    def _update_latest_coverage_map(self) -> None:
        self._oldFitness = 0.0
        for fitness_function in self._test_suite.get_fitness_functions():
            fitness = self._test_suite.get_fitness_for(fitness_function)
            self._oldFitness += fitness
            self._latest_fitness_map[fitness_function] = fitness

    def _update_latest_fitness_map(self) -> None:
        for coverage_function in self._test_suite.get_coverage_functions():
            self._latest_coverage_map[coverage_function] = self._test_suite.get_coverage_for(
                coverage_function
            )

    def has_changed(self, test_case_chromosome: TestCaseChromosome) -> LocalSearchImprovement:
        """Gives back, if the fitness of the testsuite has changed.

        It overrides the specific testcase with the provided chromosome.

        Args:
            test_case_chromosome: The chromosome which will override the original chromosome.

        Returns:
            Gives back 1 if the fitness has increased, -1 if the fitness has decreased and 0 if the
            fitness has not changed at all.
        """
        start_time = int(time.perf_counter()) * 1000
        test_case_chromosome.changed = True
        self._old_fitness = self._test_suite.get_fitness()
        self._test_suite.set_test_case_chromosome(self._position, test_case_chromosome)
        for fitness_function in self._fitness_functions:
            fitness_function.compute_fitness(self._test_suite)
        new_fitness = self._test_suite.get_fitness()
        old_mut = stat.output_variables.get(RuntimeVariable.LocalSearchTotalMutations.name)
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.LocalSearchTotalMutations,
            old_mut.value + 1 if old_mut is not None else 0,
        )

        if (
            new_fitness > self._old_fitness
            if self._is_maximization
            else new_fitness < self._old_fitness
        ):
            self._logger.debug(
                "Local search has improved the fitness of %f to %f",
                self._old_fitness,
                new_fitness,
            )
            self._update_latest_coverage_map()
            self._update_latest_fitness_map()
            return LocalSearchImprovement.IMPROVEMENT
        if (
            new_fitness < self._old_fitness
            if self._is_maximization
            else new_fitness > self._old_fitness
        ):
            self._logger.debug(
                "Local search has worsen the fitness of %f to %f",
                self._old_fitness,
                new_fitness,
            )
            self._test_suite.set_coverage_values(self._latest_coverage_map)
            self._test_suite.set_fitness_values(self._latest_fitness_map)
            return LocalSearchImprovement.DETERIORATION
        self._logger.debug("Local search hasn't changed the fitness of %f", self._old_fitness)
        time_dif = int(time.perf_counter()) * 1000 - start_time
        old_time = stat.output_variables.get(
            RuntimeVariable.TotalLocalSearchFitnessEvaluationTime.name
        )
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.TotalLocalSearchFitnessEvaluationTime,
            old_time.value + time_dif if old_time is not None else time_dif,
        )
        return LocalSearchImprovement.NONE

    def has_improved(self, test_case_chromosome: TestCaseChromosome) -> bool:
        """Gives back if changing the old test case chromosome improves the fitness of the suite.

        Args:
            test_case_chromosome: The chromosome which will override the original chromosome.

        Returns:
            Gives back true, if the test suite has improved.
        """
        return self.has_changed(test_case_chromosome) == LocalSearchImprovement.IMPROVEMENT


class LocalSearchImprovement(enum.Enum):
    """Defines the changes in fitness which were observed."""

    NONE = 0
    IMPROVEMENT = 1
    DETERIORATION = 2
