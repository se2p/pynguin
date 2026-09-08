#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the DynaMOSA-LLM test-generation strategy."""

from __future__ import annotations

import inspect
import logging
import operator
import time
from typing import TYPE_CHECKING, cast

import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm, _GoalsManager
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.ga.operators.ranking import fast_epsilon_dominance_assignment
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.ga.coveragegoals as bg
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc

import pynguin.configuration as config
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageReport, LineAnnotation, get_coverage_report


class LLDynaMOSAAlgorithm(LLMOSAAlgorithm, DynaMOSAAlgorithm):
    """Implements DynaMOSA with LLM-guided stall recovery.

    Extends both LLMOSAAlgorithm and DynaMOSAAlgorithm so the parts of the LLM
    intervention that don't depend on target selection (init, budget guard, callable
    diagnosis, population seeding, breeding) are inherited from LLMOSAAlgorithm; only
    `generate_tests`, `_target_initial_uncovered_goals`, `_eligible_gaos_for_targeting`,
    and `target_uncovered_callables` are overridden here, since those are the ones
    that depend on DynaMOSA's dynamic target set.
    """

    _logger = logging.getLogger(__name__)

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
            # DynaMOSA's UpdateTargets, not archive.update(): also unlocks any goals
            # whose parent these chromosomes just covered.
            self._goals_manager.update(self._population)

            coverage_after = self.create_test_suite(self._archive.solutions).get_coverage()
            self._logger.info("Coverage after LLM call: %5f", coverage_after)
            stat.track_output_variable(RuntimeVariable.CoverageAfterLLMCall, coverage_after)

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self.before_search_start()
        self._goals_manager = _GoalsManager(
            self._test_case_fitness_functions,  # type: ignore[arg-type]
            self._archive,
            self.executor.subject_properties,
        )
        self._number_of_goals = len(self._test_case_fitness_functions)
        stat.set_output_variable_for_runtime_variable(RuntimeVariable.Goals, self._number_of_goals)

        self._population = self._get_random_population()
        self._goals_manager.update(self._population)

        self._target_initial_uncovered_goals()

        # Calculate dominance ranks and crowding distance
        fronts = self._ranking_function.compute_ranking_assignment(
            self._population, self._goals_manager.current_goals
        )
        for i in range(fronts.get_number_of_sub_fronts()):
            fast_epsilon_dominance_assignment(
                fronts.get_sub_front(i), self._goals_manager.current_goals
            )

        self.before_first_search_iteration(self.create_test_suite(self._archive.solutions))

        llm_config = config.configuration.large_language_model
        last_length_of_covered_goals = len(self._archive.covered_goals)
        plateau_counter = 0
        max_plateau_len = llm_config.max_plateau_len
        last_gain_time = time.time()
        while self.resources_left() and len(self._archive.uncovered_goals) > 0:
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
            if config.configuration.local_search.local_search:
                self.local_search()
            self.after_search_iteration(self.create_test_suite(self._archive.solutions))

        self.after_search_finish()
        return self.create_test_suite(
            self._archive.solutions
            if len(self._archive.solutions) > 0
            else self._get_best_individuals()
        )

    def _eligible_gaos_for_targeting(self) -> set[GenericCallableAccessibleObject]:
        """Restricts LLM targeting to callables backing a currently-active goal.

        Unlike MOSA, DynaMOSA only activates a target once its control-dependency
        parent is covered, so this maps each goal in ``current_goals`` back to its
        owning callable (via ``code_object_id`` -> ``co_firstlineno``, matched
        against each callable's source start line) rather than considering every
        callable under test.

        Returns:
            The subset of `self.test_cluster.accessible_objects_under_test` that owns
            at least one currently-active goal.
        """
        subject_properties = self.executor.subject_properties
        active_first_lines: set[int] = set()
        for fitness in self._goals_manager.current_goals:
            # current_goals is typed as OrderedSet[FitnessFunction] by _GoalsManager
            # itself, but is always populated with BranchCoverageTestFitness.
            branch_fitness = cast("bg.BranchCoverageTestFitness", fitness)
            code_object_meta = subject_properties.existing_code_objects.get(
                branch_fitness.goal.code_object_id
            )
            if code_object_meta is not None:
                active_first_lines.add(code_object_meta.code_object.co_firstlineno)

        eligible: set[GenericCallableAccessibleObject] = set()
        for gao in self.test_cluster.accessible_objects_under_test:
            if not isinstance(gao, GenericCallableAccessibleObject):
                continue
            try:
                _, start_line = inspect.getsourcelines(gao.callable)
            except (TypeError, OSError):
                continue
            if start_line in active_first_lines:
                eligible.add(gao)
        return eligible

    def target_uncovered_callables(self) -> list[tcc.TestCaseChromosome]:
        """Identifies the highest-priority uncovered target, queries an LLM.

         and processes the result into a list of test case chromosomes.

        Returns:
            A list of `TestCaseChromosome` objects derived from the LLM query result.
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
            """Calculate the coverage ratio for each eligible callable.

            Returns:
                A dictionary mapping eligible accessible objects to their coverage
                ratios.
            """
            gao_coverage = {}
            for gao in self._eligible_gaos_for_targeting():
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

        def select_highest_priority_target(
            gao_coverage: dict[GenericCallableAccessibleObject, float],
        ) -> dict[GenericCallableAccessibleObject, float]:
            """Narrows the query to a single target, priority = 1 - coverage.

            One target per query, deterministically the least-covered callable into one prompt.

            Args:
                gao_coverage: Coverage-threshold-filtered callables to choose from.

            Returns:
                A single-entry dict with just the highest-priority target, or an
                empty dict if ``gao_coverage`` was empty.
            """
            if not gao_coverage:
                return gao_coverage
            target_gao = min(gao_coverage, key=lambda gao: gao_coverage[gao])
            return {target_gao: gao_coverage[target_gao]}

        # Main logic
        coverage_report: CoverageReport = get_coverage_report(
            solutions_test_suite,
            self.executor.subject_properties,
            set(config.configuration.statistics_output.coverage_metrics),
        )
        line_annotations: list[LineAnnotation] = coverage_report.line_annotations

        gao_coverage_map = calculate_gao_coverage_map()
        filtered_gao_coverage_map = filter_gao_by_coverage(gao_coverage_map)
        targeted_gao_coverage_map = select_highest_priority_target(filtered_gao_coverage_map)

        diagnostics = {
            gao: self._diagnose_callable(gao, line_annotations) for gao in targeted_gao_coverage_map
        }
        diagnostics = {gao: hint for gao, hint in diagnostics.items() if hint}

        llm_query_results = self.model.call_llm_for_uncovered_targets(
            targeted_gao_coverage_map, diagnostics
        )

        return self.model.llm_test_case_handler.get_test_case_chromosomes_from_llm_results(
            llm_query_results=llm_query_results,
            test_cluster=self.test_cluster,
            test_factory=self._test_factory,
            fitness_functions=self._test_case_fitness_functions,
            coverage_functions=self._test_suite_coverage_functions,
        )
