#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the MOSA-LLM test-generation strategy."""

from __future__ import annotations

import functools
import inspect
import logging
import time
from typing import TYPE_CHECKING

import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.mosaalgorithm import MOSAAlgorithm
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pynguin.ga.chromosomefactory as cf
    import pynguin.ga.testsuitechromosome as tsc

import operator

import pynguin.configuration as config
from pynguin.ga.stoppingcondition import MaxSearchTimeStoppingCondition
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.query_strategy import get_query_strategy
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageReport, LineAnnotation, get_coverage_report


class _StallTracker:
    """Tracks coverage plateau and stall conditions for LLM interventions."""

    def __init__(self, initial_covered: int) -> None:
        self._llm_config = config.configuration.large_language_model
        self.last_length_of_covered_goals = initial_covered
        self.plateau_counter = 0
        self.max_plateau_len = self._llm_config.max_plateau_len
        self.last_gain_time = time.time()

    def check_stall(self, current_covered: int) -> bool:
        """Updates plateau tracking and returns True if search has stalled.

        Args:
            current_covered: Current number of covered goals in archive.

        Returns:
            True if search has stalled, False otherwise.
        """
        if current_covered != self.last_length_of_covered_goals:
            self.plateau_counter = 0
            self.last_gain_time = time.time()
        else:
            self.plateau_counter += 1
        self.last_length_of_covered_goals = current_covered

        if self._llm_config.stall_detection_window_seconds > 0:
            return (
                time.time() - self.last_gain_time >= self._llm_config.stall_detection_window_seconds
            )
        return self.plateau_counter > self.max_plateau_len

    def reset(self) -> None:
        """Resets tracking state after an intervention."""
        self.plateau_counter = 0
        self.last_gain_time = time.time()
        if self._llm_config.stall_detection_window_seconds <= 0:
            self.max_plateau_len *= 2


class LLMOSAAlgorithm(MOSAAlgorithm):
    """Implements the Many-Objective Sorting Algorithm MOSA with LLM."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self.model = LLMAgent()
        self._llm_query_strategy = get_query_strategy()
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
            working_chromosomes = self._filter_working_test_cases(llm_chromosomes)
            self._population = working_chromosomes + self._population
            self._archive.update(self._population)

            coverage_after = self.create_test_suite(self._archive.solutions).get_coverage()
            self._logger.info("Coverage after LLM call: %5f", coverage_after)
            stat.track_output_variable(RuntimeVariable.CoverageAfterLLMCall, coverage_after)

    def _poll_and_handle_stall(self, stall_tracker: _StallTracker) -> None:
        """Polls for background LLM results and checks stall detection.

        Args:
            stall_tracker: State tracker for stall detection.
        """
        pending_chromosomes = self._llm_query_strategy.poll()
        if pending_chromosomes:
            self._integrate_llm_chromosomes(pending_chromosomes)

        if config.configuration.large_language_model.call_llm_on_stall_detection:
            current_covered = len(self._archive.covered_goals)
            if (
                stall_tracker.check_stall(current_covered)
                and not self._llm_query_strategy.is_in_progress()
            ):
                self._maybe_intervene_on_stall()
                stall_tracker.reset()

    def _seed_archive_from_llm(self) -> None:
        """Seed valid LLM test cases directly into the archive before search iteration 0."""
        llm_chromosomes = self._generate_initial_llm_test_cases()
        if not llm_chromosomes:
            return
        working_chromosomes = self._filter_working_test_cases(llm_chromosomes)
        if not working_chromosomes:
            self._logger.warning(
                "All %d initial LLM test cases raised exceptions or timed out; "
                "archive will not be seeded with LLM test cases.",
                len(llm_chromosomes),
            )
            return
        self._update_archive_with_initial_tests(working_chromosomes)

    def _generate_initial_llm_test_cases(self) -> list[tcc.TestCaseChromosome]:
        """Generate initial test cases using the LLM for the module under test.

        Returns:
            A list of test case chromosomes generated by the LLM.
        """
        llm_query_results = self.model.generate_tests_for_module_under_test()
        if llm_query_results is None:
            self._logger.warning(
                "Initial LLM query for the module under test returned no results "
                "(timeout or error); archive will not be seeded with LLM test cases."
            )
            return []
        chromosomes = self.model.llm_test_case_handler.get_test_case_chromosomes_from_llm_results(
            llm_query_results=llm_query_results,
            test_cluster=self.test_cluster,
            test_factory=self._test_factory,
            fitness_functions=self._test_case_fitness_functions,
            coverage_functions=self._test_suite_coverage_functions,
        )
        stat.track_output_variable(RuntimeVariable.TotalLTCs, len(chromosomes))
        self._logger.info("Generated %d initial LLM test case chromosomes.", len(chromosomes))
        return chromosomes

    def _filter_working_test_cases(
        self, chromosomes: list[tcc.TestCaseChromosome]
    ) -> list[tcc.TestCaseChromosome]:
        """Execute candidate chromosomes and filter out crashing tests and timeouts.

        Args:
            chromosomes: Candidate test case chromosomes to execute and filter.

        Returns:
            Working test case chromosomes that ran without exceptions or timeouts.
        """
        results = list(self.executor.execute_multiple(c.test_case for c in chromosomes))
        working_chromosomes: list[tcc.TestCaseChromosome] = []
        for chromosome, result in zip(chromosomes, results, strict=False):
            chromosome.set_last_execution_result(result)
            chromosome.changed = False
            if not (result.has_test_exceptions() or result.timeout):
                working_chromosomes.append(chromosome)
        self._logger.info(
            "Seeding archive with %d working LLM test cases (out of %d generated).",
            len(working_chromosomes),
            len(chromosomes),
        )
        return working_chromosomes

    def _update_archive_with_initial_tests(
        self, working_chromosomes: list[tcc.TestCaseChromosome]
    ) -> None:
        """Updates the archive with initial working LLM test cases.

        Args:
            working_chromosomes: List of working test case chromosomes.
        """
        self._archive.update(working_chromosomes)
        self._logger.info(
            "Archive contains %d solutions covering goals after initial LLM seeding.",
            len(self._archive.solutions),
        )

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self.before_search_start()
        self._number_of_goals = len(self._test_case_fitness_functions)
        stat.set_output_variable_for_runtime_variable(RuntimeVariable.Goals, self._number_of_goals)

        if config.configuration.large_language_model.hybrid_initial_population:
            self._seed_archive_from_llm()

        self._population = self._get_random_population()
        self._archive.update(self._population)

        self._target_initial_uncovered_goals()

        self._compute_dominance()
        self.before_first_search_iteration(self.create_test_suite(self._archive.solutions))

        stall_tracker = _StallTracker(len(self._archive.covered_goals))
        try:
            while (
                self.resources_left()
                and self._number_of_goals - len(self._archive.covered_goals) != 0
            ):
                self._poll_and_handle_stall(stall_tracker)
                self.evolve()
                self.after_search_iteration(self.create_test_suite(self._archive.solutions))
        finally:
            if hasattr(self.model, "cancel_all"):
                self.model.cancel_all()
            self._llm_query_strategy.shutdown()

        return self._finalize_generation()

    def _integrate_llm_chromosomes(self, llm_chromosomes: list[tcc.TestCaseChromosome]) -> None:
        """Integrates newly generated LLM test case chromosomes into the population.

        Args:
            llm_chromosomes: List of test case chromosomes from the LLM.
        """
        self._population = llm_chromosomes + self._population
        self._logger.info(
            "Added %d LLM test case chromosomes to the population.",
            len(llm_chromosomes),
        )

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
        if self._llm_query_strategy.is_in_progress():
            return

        targets_map, diagnostics = self._select_uncovered_targets()
        if not targets_map:
            return

        self._stall_intervention_count += 1
        llm_chromosomes = self._llm_query_strategy.execute(
            functools.partial(self._query_llm_for_targets, targets_map, diagnostics)
        )
        if llm_chromosomes:
            self._integrate_llm_chromosomes(llm_chromosomes)

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

    def _select_uncovered_targets(
        self,
    ) -> tuple[
        dict[GenericCallableAccessibleObject, float],
        dict[GenericCallableAccessibleObject, str],
    ]:
        """Identifies uncovered targets from the current archive solutions and derives diagnostics.

        Runs synchronously on the main thread to safely inspect the archive and test
        cluster before any background LLM queries are dispatched.

        Returns:
            A tuple of (filtered_gao_coverage_map, diagnostics).
        """
        solutions_test_suite = self.create_test_suite(self._archive.solutions)

        coverage_report: CoverageReport = get_coverage_report(
            solutions_test_suite,
            self.executor.subject_properties,
            set(config.configuration.search_algorithm.coverage_metrics),
        )
        line_annotations: list[LineAnnotation] = coverage_report.line_annotations

        candidates = (
            gao
            for gao in self.test_cluster.accessible_objects_under_test
            if isinstance(gao, GenericCallableAccessibleObject)
        )
        gao_coverage_map = self._calculate_gao_coverage_map(candidates, line_annotations)
        filtered_gao_coverage_map = self._filter_gao_by_coverage(gao_coverage_map)

        diagnostics = {
            gao: self._diagnose_callable(gao, line_annotations) for gao in filtered_gao_coverage_map
        }
        diagnostics = {gao: hint for gao, hint in diagnostics.items() if hint}
        return filtered_gao_coverage_map, diagnostics

    def _query_llm_for_targets(
        self,
        targets_map: dict[GenericCallableAccessibleObject, float],
        diagnostics: dict[GenericCallableAccessibleObject, str],
    ) -> list[tcc.TestCaseChromosome]:
        """Queries the LLM for uncovered targets and parses results into chromosomes.

        Safe to run asynchronously on a background thread because it does not access the
        archive.

        Args:
            targets_map: Mapping of callables to their coverage ratio.
            diagnostics: Mapping of callables to diagnostic hints.

        Returns:
            A list of TestCaseChromosome objects.
        """
        if not targets_map:
            return []

        llm_query_results = self.model.call_llm_for_uncovered_targets(targets_map, diagnostics)

        return self.model.llm_test_case_handler.get_test_case_chromosomes_from_llm_results(
            llm_query_results=llm_query_results,
            test_cluster=self.test_cluster,
            test_factory=self._test_factory,
            fitness_functions=self._test_case_fitness_functions,
            coverage_functions=self._test_suite_coverage_functions,
        )

    def target_uncovered_callables(self) -> list[tcc.TestCaseChromosome]:
        """Identifies uncovered targets, queries an LLM for test cases.

         and processes the results into a list of test case chromosomes.

        Returns:
            A list of `TestCaseChromosome` objects derived from the LLM query results.
        """
        targets_map, diagnostics = self._select_uncovered_targets()
        return self._query_llm_for_targets(targets_map, diagnostics)

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

    @staticmethod
    def _coverage_in_range(
        line_annotations: list[LineAnnotation], start_line: int, end_line: int
    ) -> tuple[int, int]:
        """Calculate the total and covered coverage points for a given line range.

        Args:
            line_annotations: Per-line coverage annotations for the module.
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

    def _calculate_gao_coverage_map(
        self,
        candidates: Iterable[GenericCallableAccessibleObject],
        line_annotations: list[LineAnnotation],
    ) -> dict[GenericCallableAccessibleObject, float]:
        """Calculate the coverage ratio for each candidate callable.

        Args:
            candidates: The callables to compute a coverage ratio for.
            line_annotations: Per-line coverage annotations for the module.

        Returns:
            A dictionary mapping candidate accessible objects to their coverage ratios.
        """
        gao_coverage = {}
        for gao in candidates:
            try:
                source_lines, start_line = inspect.getsourcelines(gao.callable)
                end_line = start_line + len(source_lines) - 1
                covered, total = self._coverage_in_range(line_annotations, start_line, end_line)
                coverage_ratio = covered / total if total > 0 else 0
            except (TypeError, OSError):
                coverage_ratio = 0
            gao_coverage[gao] = coverage_ratio
        return gao_coverage

    @staticmethod
    def _filter_gao_by_coverage(
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

    def _get_random_chromosome(self) -> tcc.TestCaseChromosome:
        """Returns a random test case chromosome from the chromosome factory.

        Returns:
            A new random test case chromosome.
        """
        factory = getattr(
            self._chromosome_factory,
            "test_case_chromosome_factory",
            self._chromosome_factory,
        )
        return factory.get_chromosome()

    def _get_random_population(self) -> list[tcc.TestCaseChromosome]:
        pop_size = config.configuration.search_algorithm.population
        population: list[tcc.TestCaseChromosome] = []

        if config.configuration.large_language_model.hybrid_initial_population:
            archive_solutions = list(self._archive.solutions)
            if archive_solutions:
                target_llm_count = int(
                    config.configuration.large_language_model.llm_test_case_percentage * pop_size
                )
                sample_count = min(len(archive_solutions), target_llm_count)
                if sample_count > 0:
                    sampled = (
                        archive_solutions
                        if sample_count == len(archive_solutions)
                        else randomness.sample(archive_solutions, sample_count)
                    )
                    population.extend(sol.clone() for sol in sampled)
                    self._logger.info(
                        "Sampled %d LLM test cases from archive into initial population.",
                        len(population),
                    )

        while len(population) < pop_size:
            population.append(self._get_random_chromosome())

        return population

    def _breed_next_generation(
        self,
        factory: cf.ChromosomeFactory | None = None,
    ) -> list[tcc.TestCaseChromosome]:
        actual_factory = getattr(
            self._chromosome_factory,
            "test_case_chromosome_factory",
            self._chromosome_factory,
        )
        return super()._breed_next_generation(actual_factory)
