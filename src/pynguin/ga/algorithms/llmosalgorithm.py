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

import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.stats as stat

from pynguin.ga.algorithms.mosaalgorithm import MOSAAlgorithm
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


if TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.ga.chromosomefactory as cf

import operator

import pynguin.configuration as config

from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageReport
from pynguin.utils.report import LineAnnotation
from pynguin.utils.report import get_coverage_report


class LLMOSAAlgorithm(MOSAAlgorithm):
    """Implements the Many-Objective Sorting Algorithm MOSA with LLM."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self.model = LLMAgent()

    def _target_initial_uncovered_goals(self) -> None:
        """Performs an LLM intervention to improve coverage before search iteration."""
        coverage_before = self.create_test_suite(self._archive.solutions).get_coverage()

        if (
            config.configuration.large_language_model.call_llm_for_uncovered_targets
            and coverage_before < 1.0
        ):
            self._logger.info("Coverage before LLM call: %5f", coverage_before)
            stat.track_output_variable(RuntimeVariable.CoverageBeforeLLMCall, coverage_before)

            llm_chromosomes = self.target_uncovered_callables()
            self._population += llm_chromosomes
            self._archive.update(self._population)

            coverage_after = self.create_test_suite(self._archive.solutions).get_coverage()
            self._logger.info("Coverage after LLM call: %5f", coverage_after)
            stat.track_output_variable(RuntimeVariable.CoverageAfterLLMCall, coverage_after)

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self.before_search_start()
        self._number_of_goals = len(self._test_case_fitness_functions)
        stat.set_output_variable_for_runtime_variable(RuntimeVariable.Goals, self._number_of_goals)

        self._population = self._get_random_population()
        self._archive.update(self._population)

        self._target_initial_uncovered_goals()

        self._compute_dominance()
        self.before_first_search_iteration(self.create_test_suite(self._archive.solutions))

        last_length_of_covered_goals = len(self._archive.covered_goals)
        plateau_counter = 0
        max_llm_int = config.configuration.large_language_model.max_llm_interventions
        max_plateau_len = config.configuration.large_language_model.max_plateau_len
        while (
            self.resources_left() and self._number_of_goals - len(self._archive.covered_goals) != 0
        ):
            if config.configuration.large_language_model.call_llm_on_stall_detection:
                if plateau_counter > max_plateau_len:
                    plateau_counter = 0
                    max_plateau_len *= 2
                    if self.model.llm_calls_counter < max_llm_int:
                        llm_chromosomes = self.target_uncovered_callables()
                        self._population = llm_chromosomes + self._population
                        self._logger.info(
                            "Added %d LLM test case chromosomes to the population.",
                            len(llm_chromosomes),
                        )
                current_covered = len(self._archive.covered_goals)
                if current_covered == last_length_of_covered_goals:
                    plateau_counter += 1
                else:
                    plateau_counter = 0
                last_length_of_covered_goals = current_covered
            self.evolve()
            self.after_search_iteration(self.create_test_suite(self._archive.solutions))

        return self._finalize_generation()

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

        def calculate_gao_coverage_map() -> dict[GenericCallableAccessibleObject, float]:
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
            gao_coverage: dict[GenericCallableAccessibleObject, float],
        ) -> dict[GenericCallableAccessibleObject, float]:
            """Filter GenericCallableAccessibleObjects by their coverage ratio.

            Args:
                gao_coverage: A dictionary of objects and their coverage ratios.

            Returns:
                A filtered dictionary of objects with coverage below the threshold.
            """
            return {
                gao: coverage
                for gao, coverage in sorted(gao_coverage.items(), key=operator.itemgetter(1))
                if coverage < config.configuration.large_language_model.coverage_threshold
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

        llm_query_results = self.model.call_llm_for_uncovered_targets(filtered_gao_coverage_map)

        return self.model.llm_test_case_handler.get_test_case_chromosomes_from_llm_results(
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

    def _breed_next_generation(
        self,
        factory: cf.ChromosomeFactory | None = None,
    ) -> list[tcc.TestCaseChromosome]:
        return super()._breed_next_generation(self._chromosome_factory.test_case_chromosome_factory)  # type:ignore[attr-defined]
