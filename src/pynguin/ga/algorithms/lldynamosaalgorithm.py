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
import time
from typing import TYPE_CHECKING

import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm, _GoalsManager
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.ga.operators.ranking import fast_epsilon_dominance_assignment
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc

import pynguin.configuration as config
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageReport, LineAnnotation, get_coverage_report


class LLDynaMOSAAlgorithm(LLMOSAAlgorithm, DynaMOSAAlgorithm):
    """Implements DynaMOSA with LLM-guided stall recovery.

    Reuses target-independent LLMOSA behavior and overrides target-dependent methods
    to support DynaMOSA's dynamic target set.
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

    def _maybe_intervene_on_stall(self) -> None:
        """Query the LLM on a stall, then unlock any goals the result just covered.

        Unlike MOSA, DynaMOSA gates goals by parent coverage, so newly covered goals
        must be unlocked immediately to avoid losing coverage during truncation.
        """
        super()._maybe_intervene_on_stall()
        self._goals_manager.update(self._population)

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self.before_search_start()
        self._goals_manager = _GoalsManager(
            self._test_case_fitness_functions,
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

    def _eligible_gaos_for_targeting(self) -> OrderedSet[GenericCallableAccessibleObject]:
        """Restricts LLM targeting to callables backing a currently-active goal.

        Maps goals to callables via their code object's source location. An
        ``OrderedSet`` preserves deterministic target selection.

        Returns:
            The subset of `self.test_cluster.accessible_objects_under_test` that owns
            at least one currently-active goal.
        """
        subject_properties = self.executor.subject_properties
        active_first_lines: set[int] = set()
        for fitness in self._goals_manager.current_goals:
            goal = getattr(fitness, "goal", None)
            code_object_id = getattr(goal, "code_object_id", None)
            if code_object_id is not None:
                code_object_meta = subject_properties.existing_code_objects.get(code_object_id)
                if code_object_meta is not None:
                    active_first_lines.add(code_object_meta.code_object.co_firstlineno)

        eligible: OrderedSet[GenericCallableAccessibleObject] = OrderedSet()
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
            set(config.configuration.search_algorithm.coverage_metrics),
        )
        line_annotations: list[LineAnnotation] = coverage_report.line_annotations

        gao_coverage_map = self._calculate_gao_coverage_map(
            self._eligible_gaos_for_targeting(), line_annotations
        )
        filtered_gao_coverage_map = self._filter_gao_by_coverage(gao_coverage_map)
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
