#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an abstract base class for MOSA and its derivatives."""
from __future__ import annotations

import inspect
import logging
import pynguin.utils.statistics.statistics as stat

from abc import ABC
from typing import cast, Tuple, List, Dict

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc

from pynguin.ga.algorithms.archive import CoverageArchive
from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
from pynguin.ga.operators.comparator import DominanceComparator
from pynguin.large_language_model.openaimodel import OpenAIModel, save_llm_tests_to_file
from pynguin.large_language_model.parsing import deserializer
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject
from pynguin.utils.report import get_coverage_report, LineAnnotation
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


class AbstractMOSAAlgorithm(GenerationAlgorithm[CoverageArchive], ABC):
    """An abstract base implementation for MOSA and its derivatives."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self._population: list[tcc.TestCaseChromosome] = []
        self._number_of_goals = -1

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
            tch: tcc.TestCaseChromosome
            if len(self._archive.covered_goals) == 0 or randomness.next_bool():
                if config.configuration.large_language_model.hybrid_initial_population:
                    tch = (
                        self._chromosome_factory.test_case_chromosome_factory.get_chromosome()
                    # type: ignore[attr-defined]
                    )
                else:
                    tch = self._chromosome_factory.get_chromosome()
            else:
                tch = randomness.choice(self._archive.solutions).clone()
                tch.mutate()

            if tch.changed and tch.size() > 0:
                offspring_population.append(tch)

        self._logger.debug("Number of offsprings = %d", len(offspring_population))
        return offspring_population

    @staticmethod
    def _mutate(offspring: tcc.TestCaseChromosome) -> None:
        offspring.mutate()
        if not offspring.changed:
            # if offspring is not changed, we try to mutate it once again
            offspring.mutate()

    def _get_non_dominated_solutions(
        self, solutions: list[tcc.TestCaseChromosome]
    ) -> list[tcc.TestCaseChromosome]:
        comparator: DominanceComparator[tcc.TestCaseChromosome] = DominanceComparator(
            goals=self._archive.covered_goals  # type: ignore[arg-type]
        )
        next_front: list[tcc.TestCaseChromosome] = []
        for solution in solutions:
            is_dominated = False
            dominated_solutions: list[tcc.TestCaseChromosome] = []
            for best in next_front:
                flag = comparator.compare(solution, best)
                if flag < 0:
                    dominated_solutions.append(best)
                if flag > 0:
                    is_dominated = True
            if is_dominated:
                continue
            next_front.append(solution)
            for dominated_solution in dominated_solutions:
                if dominated_solution in next_front:
                    next_front.remove(dominated_solution)
        return next_front

    def _get_random_population(self) -> list[tcc.TestCaseChromosome]:
        if config.configuration.large_language_model.hybrid_initial_population:
            test_suite_chromosome: tsc.TestSuiteChromosome = (
                self._chromosome_factory.get_chromosome()
            )
            return test_suite_chromosome.test_case_chromosomes
        population: list[tcc.TestCaseChromosome] = []
        for _ in range(config.configuration.search_algorithm.population):
            chromosome = self._chromosome_factory.get_chromosome()
            population.append(chromosome)
        return population

    def _get_best_individuals(self) -> list[tcc.TestCaseChromosome]:
        return self._get_non_dominated_solutions(self._population)

    def target_uncovered_function(self):

        solutions_test_suite = self.create_test_suite(self._archive.solutions)

        def coverage_in_range(start_line: int, end_line: int) -> Tuple[int, int]:
            """Helper coverage to determine the coverage of consecutive lines.

            Args:
                start_line: first line to consider, inclusive
                end_line: last line to consider, inclusive

            Returns:
                the total number of covered elements (branches, lines) in the line
                range, as well as the total number of coverable elements in that range.
            """
            total_coverage_points = 0
            covered_coverage_points = 0
            for line_annot in line_annotations:
                if start_line <= line_annot.line_no <= end_line:
                    total_coverage_points += line_annot.total.existing
                    covered_coverage_points += line_annot.total.covered
            return covered_coverage_points, total_coverage_points

        coverage_report = get_coverage_report(
            solutions_test_suite,
            self.executor,
            config.configuration.statistics_output.coverage_metrics,
        )
        line_annotations: List[LineAnnotation] = coverage_report.line_annotations
        gao_coverage_map: Dict[GenericCallableAccessibleObject, float] = {}

        for gao in self.test_cluster.accessible_objects_under_test:
            if isinstance(gao, GenericCallableAccessibleObject):
                try:
                    source_lines, start_line = inspect.getsourcelines(gao.callable)
                    end_line = start_line + len(source_lines) - 1
                    covered, total = coverage_in_range(start_line, end_line)
                    coverage_ratio = covered / total if total > 0 else 0
                except (TypeError, OSError):
                    coverage_ratio = 0

                gao_coverage_map[gao] = coverage_ratio

        # target only GenericCallableAccessibleObject that have coverage less than coverage_threshold
        filtered_gao_coverage_map = {
            gao: coverage
            for gao, coverage in sorted(
                gao_coverage_map.items(),
                key=lambda item: item[1]
            )
            if coverage < config.configuration.large_language_model.coverage_threshold
        }

        winning_test_case_source_code = unparse_test_case(solutions_test_suite.test_case_chromosomes[0].test_case)
        model = OpenAIModel()
        llm_test_case_chromosomes: list[tcc.TestCaseChromosome] = []
        llm_query_results = model.call_llm_for_uncovered_targets(filtered_gao_coverage_map,
                                                                 winning_test_case_source_code)
        if llm_query_results is not None:
            llm_test_cases_str = model.extract_test_cases_from_llm_output(
                llm_query_results
            )

            (
                test_cases,
                total_statements,
                parsed_statements,
                uninterpreted_statements,
            ) = deserializer.deserialize_code_to_testcases(
                llm_test_cases_str, test_cluster=self._test_cluster
            )

            tests_source_code = ""
            for test_case in test_cases:
                test_case_source_code = unparse_test_case(test_case) or ""
                tests_source_code += test_case_source_code + "\n\n"
            save_llm_tests_to_file(tests_source_code, "deserializer_llm_test_cases.py")

            stat.track_output_variable(
                RuntimeVariable.LLMTotalParsedStatements, parsed_statements
            )
            stat.track_output_variable(
                RuntimeVariable.LLMTotalStatements, total_statements
            )
            stat.track_output_variable(
                RuntimeVariable.LLMUninterpretedStatements, uninterpreted_statements
            )

            for test_case in test_cases:
                test_case_chromosome = tcc.TestCaseChromosome(
                    test_case=test_case, test_factory=self._test_factory
                )
                for fitness_function in self._test_case_fitness_functions:  # Use _test_case_fitness_functions
                    test_case_chromosome.add_fitness_function(fitness_function)

                for coverage_function in self._test_suite_coverage_functions:
                    test_case_chromosome.add_coverage_function(coverage_function)

                llm_test_case_chromosomes.append(test_case_chromosome)

        return llm_test_case_chromosomes
