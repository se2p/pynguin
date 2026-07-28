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
import time
from typing import TYPE_CHECKING

import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.mosaalgorithm import MOSAAlgorithm
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.ga.chromosomefactory as cf
    import pynguin.ga.testsuitechromosome as tsc

import operator

import pynguin.configuration as config
from pynguin.ga.stoppingcondition import MaxSearchTimeStoppingCondition
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageReport, LineAnnotation, get_coverage_report


class LLMOSAAlgorithm(MOSAAlgorithm):
    """Implements the Many-Objective Sorting Algorithm MOSA with LLM."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self.model = LLMAgent()
        # Counts only stall-triggered interventions, kept separate from the model's
        # global llm_calls_counter (which also counts pre-search/seeding queries) so
        # that ``max_llm_interventions`` caps stall queries independently.
        self._stall_intervention_count = 0

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

        llm_config = config.configuration.large_language_model
        last_length_of_covered_goals = len(self._archive.covered_goals)
        plateau_counter = 0
        max_plateau_len = llm_config.max_plateau_len
        last_gain_time = time.time()
        while (
            self.resources_left() and self._number_of_goals - len(self._archive.covered_goals) != 0
        ):
            if llm_config.call_llm_on_stall_detection:
                current_covered = len(self._archive.covered_goals)
                if current_covered != last_length_of_covered_goals:
                    plateau_counter = 0
                    last_gain_time = time.time()
                else:
                    plateau_counter += 1
                last_length_of_covered_goals = current_covered

                if llm_config.stall_detection_window_seconds > 0:
                    stalled = (
                        time.time() - last_gain_time >= llm_config.stall_detection_window_seconds
                    )
                else:
                    stalled = plateau_counter > max_plateau_len

                if stalled:
                    self._maybe_intervene_on_stall()
                    # Reset stall tracking after a firing (or a suppressed attempt) so
                    # we wait for a fresh plateau before querying again.
                    plateau_counter = 0
                    last_gain_time = time.time()
                    if llm_config.stall_detection_window_seconds <= 0:
                        max_plateau_len *= 2
            self.evolve()
            self.after_search_iteration(self.create_test_suite(self._archive.solutions))

        return self._finalize_generation()

    def _maybe_intervene_on_stall(self) -> None:
        """Query the LLM for uncovered targets on a stall, respecting cap and budget.

        Skips the query when the maximum number of interventions has been reached or
        when too little search budget remains for the query to return and be
        integrated in time (late-budget guard).
        """
        llm_config = config.configuration.large_language_model
        max_llm_int = llm_config.max_llm_interventions
        under_cap = max_llm_int < 0 or self._stall_intervention_count < max_llm_int
        if not under_cap:
            return
        if not self._enough_budget_for_llm():
            self._logger.info(
                "Skipping stall LLM query: less than %ds of search budget remain.",
                llm_config.min_remaining_budget_for_llm,
            )
            return
        self._stall_intervention_count += 1
        llm_chromosomes = self.target_uncovered_callables()
        self._population = llm_chromosomes + self._population
        self._logger.info(
            "Added %d LLM test case chromosomes to the population.",
            len(llm_chromosomes),
        )

    def _enough_budget_for_llm(self) -> bool:
        """Whether enough search time remains to fire a stall-triggered LLM query.

        Returns:
            ``True`` if the late-budget guard is disabled, no maximum search time is
            configured, or the remaining time is at least
            ``min_remaining_budget_for_llm`` seconds; ``False`` otherwise.
        """
        min_budget = config.configuration.large_language_model.min_remaining_budget_for_llm
        if min_budget <= 0:
            return True
        for stopping_condition in getattr(self, "_stopping_conditions", ()):
            if isinstance(stopping_condition, MaxSearchTimeStoppingCondition):
                remaining = stopping_condition.limit() - stopping_condition.current_value()
                return remaining >= min_budget
        return True

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
            self.executor.subject_properties,
            set(config.configuration.statistics_output.coverage_metrics),
        )
        line_annotations: list[LineAnnotation] = coverage_report.line_annotations

        gao_coverage_map = calculate_gao_coverage_map()
        filtered_gao_coverage_map = filter_gao_by_coverage(gao_coverage_map)

        diagnostics = {
            gao: self._diagnose_callable(gao, line_annotations) for gao in filtered_gao_coverage_map
        }
        diagnostics = {gao: hint for gao, hint in diagnostics.items() if hint}

        llm_query_results = self.model.call_llm_for_uncovered_targets(
            filtered_gao_coverage_map, diagnostics
        )

        return self.model.llm_test_case_handler.get_test_case_chromosomes_from_llm_results(
            llm_query_results=llm_query_results,
            test_cluster=self.test_cluster,
            test_factory=self._test_factory,
            fitness_functions=self._test_case_fitness_functions,
            coverage_functions=self._test_suite_coverage_functions,
        )

    @staticmethod
    def _diagnose_callable(
        gao: GenericCallableAccessibleObject,
        line_annotations: list[LineAnnotation],
    ) -> str:
        """Derive a diagnostic "problem card" for an uncovered callable.

        Uses the per-line coverage annotations already computed for the search to
        explain *why* a callable is uncovered, so the LLM can target the gap:

        * **Reachability** -- none of the callable's lines were covered, i.e. it was
          never reached (setup likely fails before the invocation).
        * **Branch polarity** -- a branch inside the callable only ever took one
          outcome, so the opposite outcome needs to be triggered.

        Args:
            gao: The uncovered callable.
            line_annotations: Per-line coverage annotations for the module.

        Returns:
            A short hint string, or ``""`` when nothing informative can be derived.
        """
        try:
            source_lines, start_line = inspect.getsourcelines(gao.callable)
        except (TypeError, OSError):
            return ""
        end_line = start_line + len(source_lines) - 1

        covered = 0
        total = 0
        one_sided_branch_lines: list[int] = []
        for annotation in line_annotations:
            if start_line <= annotation.line_no <= end_line:
                covered += annotation.total.covered
                total += annotation.total.existing
                branches = annotation.branches
                if branches.existing > 0 and 0 < branches.covered < branches.existing:
                    one_sided_branch_lines.append(annotation.line_no)

        if total > 0 and covered == 0:
            return (
                "never reached; the setup likely fails before the call is made -- "
                "construct valid inputs/state and invoke it directly"
            )
        if one_sided_branch_lines:
            lines_str = ", ".join(str(line_no) for line_no in one_sided_branch_lines)
            return (
                f"branch(es) at line(s) {lines_str} only took one outcome -- "
                "vary one input/state axis to trigger the opposite outcome"
            )
        return ""

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
