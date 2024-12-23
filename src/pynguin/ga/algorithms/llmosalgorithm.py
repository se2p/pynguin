#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the MOSA-LLM test-generation strategy."""
from __future__ import annotations

import inspect
import logging

from typing import TYPE_CHECKING
from typing import cast

import pynguin.ga.computations as ff
import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.statistics as stat

from pynguin.ga.algorithms.abstractmosaalgorithm import AbstractMOSAAlgorithm
from pynguin.ga.operators.ranking import fast_epsilon_dominance_assignment
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


if TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc

    from pynguin.utils.orderedset import OrderedSet

import operator

import pynguin.configuration as config

from pynguin.large_language_model.llmagent import OpenAIModel
from pynguin.large_language_model.llmagent import (
    get_test_case_chromosomes_from_llm_results,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageReport
from pynguin.utils.report import LineAnnotation
from pynguin.utils.report import get_coverage_report


class LLMOSAAlgorithm(AbstractMOSAAlgorithm):
    """Implements the Many-Objective Sorting Algorithm MOSA with LLM."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self.model = OpenAIModel()

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self.before_search_start()
        self._number_of_goals = len(self._test_case_fitness_functions)
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.Goals, self._number_of_goals
        )

        self._population = self._get_random_population()
        self._archive.update(self._population)

        # Use LLM to target uncovered functions
        coverage_before_llm_call = self.create_test_suite(
            self._archive.solutions
        ).get_coverage()
        if (
            config.configuration.large_language_model.call_llm_for_uncovered_targets
            and coverage_before_llm_call < 1.0
        ):
            self._logger.info(
                "Coverage before LLM call for uncovered targets: %5f",
                coverage_before_llm_call,
            )
            stat.track_output_variable(
                RuntimeVariable.CoverageBeforeLLMCall, coverage_before_llm_call
            )

            llm_chromosomes = self.target_uncovered_callables()

            self._population = llm_chromosomes + self._population

            self._logger.info(
                "Added %d LLM test case chromosomes to the population.",
                len(llm_chromosomes),
            )

            self._archive.update(self._population)

            coverage_after_llm_call = self.create_test_suite(
                self._archive.solutions
            ).get_coverage()
            self._logger.info(
                "Coverage after LLM call for uncovered targets: %5f",
                coverage_after_llm_call,
            )
            stat.track_output_variable(
                RuntimeVariable.CoverageAfterLLMCall, coverage_after_llm_call
            )

        # Calculate dominance ranks and crowding distance
        fronts = self._ranking_function.compute_ranking_assignment(
            self._population, self._archive.uncovered_goals  # type: ignore[arg-type]
        )
        for i in range(fronts.get_number_of_sub_fronts()):
            fast_epsilon_dominance_assignment(
                fronts.get_sub_front(i),
                self._archive.uncovered_goals,  # type: ignore[arg-type]
            )

        self.before_first_search_iteration(
            self.create_test_suite(self._archive.solutions)
        )

        last_length_of_covered_goals = len(self._archive.covered_goals)
        plateau_counter = 0
        max_plateau_len = config.configuration.large_language_model.max_plateau_len
        while (
            self.resources_left()
            and self._number_of_goals - len(self._archive.covered_goals) != 0
        ):
            if config.configuration.large_language_model.call_llm_on_stall_detection:
                if plateau_counter > max_plateau_len:
                    plateau_counter = 0
                    max_plateau_len *= 2
                    if self.model.llm_calls_counter < config.configuration.large_language_model.max_llm_interventions:
                        llm_chromosomes = self.target_uncovered_callables()
                        self._population = llm_chromosomes + self._population
                        self._logger.info(
                            "Added %d LLM test case chromosomes to the population.",
                            len(llm_chromosomes),
                        )
                length_of_covered_goals = len(self._archive.covered_goals)
                if length_of_covered_goals == last_length_of_covered_goals:
                    plateau_counter += 1
                else:
                    plateau_counter = 0
                last_length_of_covered_goals = length_of_covered_goals
            self.evolve()
            self.after_search_iteration(self.create_test_suite(self._archive.solutions))

        self.after_search_finish()
        return self.create_test_suite(
            self._archive.solutions
            if len(self._archive.solutions) > 0
            else self._get_best_individuals()
        )

    def evolve(self) -> None:
        """Runs one evolution step."""
        offspring_population: list[tcc.TestCaseChromosome] = (
            self._breed_next_generation()
        )

        # Create union of parents and offspring
        union: list[tcc.TestCaseChromosome] = []
        union.extend(self._population)
        union.extend(offspring_population)

        uncovered_goals: OrderedSet[
            ff.FitnessFunction
        ] = self._archive.uncovered_goals  # type: ignore[assignment]

        # Ranking the union
        self._logger.debug("Union Size = %d", len(union))
        # Ranking the union using the best rank algorithm
        fronts = self._ranking_function.compute_ranking_assignment(
            union, uncovered_goals
        )

        remain = len(self._population)
        index = 0
        self._population.clear()

        # Obtain the next front
        front = fronts.get_sub_front(index)

        while remain > 0 and remain >= len(front) != 0:
            # Assign crowding distance to individuals
            fast_epsilon_dominance_assignment(front, uncovered_goals)
            # Add the individuals of this front
            self._population.extend(front)
            # Decrement remain
            remain -= len(front)
            # Obtain the next front
            index += 1
            if remain > 0:
                front = fronts.get_sub_front(index)

        # Remain is less than len(front[index]), insert only the best one
        if remain > 0 and len(front) != 0:
            fast_epsilon_dominance_assignment(front, uncovered_goals)
            front.sort(key=lambda t: t.distance, reverse=True)
            self._population.extend(front[k] for k in range(remain))

        self._archive.update(self._population)

    def target_uncovered_callables(self) -> list[tcc.TestCaseChromosome]:
        """Identifies uncovered targets, queries an LLM for test cases.

         and processes the results into a list of test case chromosomes.

        Returns:
            A list of `TestCaseChromosome` objects derived from the LLM query results.
        """
        solutions_test_suite = self.create_test_suite(self._archive.solutions)

        def coverage_in_range(start_line: int, end_line: int) -> tuple[int, int]:
            """Calculate the total and covered coverage points for a given line range.

            Args:
                start_line: The first line in the range, inclusive.
                end_line: The last line in the range, inclusive.

            Returns:
                A tuple of (covered points, total points).
            """
            total_coverage_points = 0
            covered_coverage_points = 0
            for line_annot in line_annotations:
                if start_line <= line_annot.line_no <= end_line:
                    total_coverage_points += line_annot.total.existing
                    covered_coverage_points += line_annot.total.covered
            return covered_coverage_points, total_coverage_points

        def calculate_gao_coverage_map() -> (
            dict[GenericCallableAccessibleObject, float]
        ):
            """Calculate the coverage ratio for each GenericCallableAccessibleObject.

            Returns:
                A dictionary mapping accessible objects to their coverage ratios.
            """
            gao_coverage = {}
            for gao in self.test_cluster.accessible_objects_under_test:
                if isinstance(gao, GenericCallableAccessibleObject):
                    try:
                        source_lines, start_line = inspect.getsourcelines(gao.callable)
                        end_line = start_line + len(source_lines) - 1
                        covered, total = coverage_in_range(start_line, end_line)
                        coverage_ratio = covered / total if total > 0 else 0
                    except (TypeError, OSError):
                        coverage_ratio = 0
                    gao_coverage[gao] = coverage_ratio
            return gao_coverage

        def filter_gao_by_coverage(
            gao_coverage: dict[GenericCallableAccessibleObject, float]
        ) -> dict[GenericCallableAccessibleObject, float]:
            """Filter GenericCallableAccessibleObjects by their coverage ratio.

            Args:
                gao_coverage: A dictionary of objects and their coverage ratios.

            Returns:
                A filtered dictionary of objects with coverage below the threshold.
            """
            return {
                gao: coverage
                for gao, coverage in sorted(
                    gao_coverage.items(), key=operator.itemgetter(1)
                )
                if coverage
                < config.configuration.large_language_model.coverage_threshold
            }

        # Main logic
        coverage_report: CoverageReport = get_coverage_report(
            solutions_test_suite,
            self.executor,  # type:ignore[arg-type]
            set(config.configuration.statistics_output.coverage_metrics),
        )
        line_annotations: list[LineAnnotation] = coverage_report.line_annotations

        gao_coverage_map = calculate_gao_coverage_map()
        filtered_gao_coverage_map = filter_gao_by_coverage(gao_coverage_map)

        llm_query_results = self.model.call_llm_for_uncovered_targets(
            filtered_gao_coverage_map
        )

        return get_test_case_chromosomes_from_llm_results(
            llm_query_results=llm_query_results,
            test_cluster=self.test_cluster,
            test_factory=self._test_factory,
            fitness_functions=self._test_case_fitness_functions,
            coverage_functions=self._test_suite_coverage_functions,
            model=self.model,
        )

    def _get_random_population(self) -> list[tcc.TestCaseChromosome]:
        if config.configuration.large_language_model.hybrid_initial_population:
            test_suite_chromosome: tsc.TestSuiteChromosome = (
                self._chromosome_factory.get_chromosome()
            )
            return test_suite_chromosome.test_case_chromosomes
        population: list[tcc.TestCaseChromosome] = []
        for _ in range(config.configuration.search_algorithm.population):
            chromosome = (
                self._chromosome_factory.test_case_chromosome_factory.get_chromosome()  # type:ignore[attr-defined]
            )
            population.append(chromosome)
        return population

    def _breed_next_generation(self) -> list[tcc.TestCaseChromosome]:  # noqa: C901
        offspring_population: list[tcc.TestCaseChromosome] = []
        for _ in range(int(config.configuration.search_algorithm.population / 2)):
            parent_1 = self._selection_function.select(self._population)[0]
            parent_2 = self._selection_function.select(self._population)[0]
            offspring_1 = cast(tcc.TestCaseChromosome, parent_1.clone())
            offspring_2 = cast(tcc.TestCaseChromosome, parent_2.clone())

            # Apply crossover
            if (
                randomness.next_float()
                <= config.configuration.search_algorithm.crossover_rate
            ):
                try:
                    self._crossover_function.cross_over(offspring_1, offspring_2)
                except ConstructionFailedException:
                    self._logger.debug("CrossOver failed.")
                    continue

            # Apply mutation on offspring_1
            for _ in range(config.configuration.search_algorithm.number_of_mutations):
                self._mutate(offspring_1)
            if offspring_1.changed and offspring_1.size() > 0:
                offspring_population.append(offspring_1)

            # Apply mutation on offspring_2
            for _ in range(config.configuration.search_algorithm.number_of_mutations):
                self._mutate(offspring_2)
            if offspring_2.changed and offspring_2.size() > 0:
                offspring_population.append(offspring_2)

        # Add new randomly generated tests
        for _ in range(
            int(
                config.configuration.search_algorithm.population
                * config.configuration.search_algorithm.test_insertion_probability
            )
        ):
            if len(self._archive.covered_goals) == 0 or randomness.next_bool():
                tch: tcc.TestCaseChromosome = (
                    self._chromosome_factory.test_case_chromosome_factory.get_chromosome()  # type:ignore[attr-defined]
                )
            else:
                tch = randomness.choice(self._archive.solutions).clone()
                tch.mutate()

            if tch.changed and tch.size() > 0:
                offspring_population.append(tch)

        self._logger.debug("Number of offsprings = %d", len(offspring_population))
        return offspring_population
