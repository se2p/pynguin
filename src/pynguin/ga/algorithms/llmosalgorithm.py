#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the MOSA-LLM test-generation strategy."""

from __future__ import annotations

import dataclasses
import functools
import inspect
import logging
import math
import time
from typing import TYPE_CHECKING

import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.llmlineage import BLEND_CHANNELS, BlendChannel, LineageTracker
from pynguin.ga.algorithms.mosaalgorithm import MOSAAlgorithm
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    import pynguin.ga.chromosomefactory as cf
    import pynguin.ga.computations as ff
    import pynguin.ga.testsuitechromosome as tsc

import operator

import pynguin.configuration as config
from pynguin.ga.stoppingcondition import MaxSearchTimeStoppingCondition
from pynguin.large_language_model.llmagent import LLMAgent, target_name
from pynguin.large_language_model.llmtestcasehandler import (
    ChromosomeContext,
    LLMGeneration,
    reset_statement_ratio,
)
from pynguin.large_language_model.query_strategy import get_query_strategy
from pynguin.large_language_model.tracing import CallPurpose, count
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.report import CoverageReport, LineAnnotation, get_coverage_report

_MAX_REPORTED_FAILURES = 5


def _timed(step: Callable[[], None]) -> float:
    """Runs a step and measures how long it took.

    Args:
        step: The step to run.

    Returns:
        The wall-clock seconds the step took.
    """
    started = time.perf_counter()
    step()
    return time.perf_counter() - started


def _without(
    chromosomes: list[tcc.TestCaseChromosome], excluded: list[tcc.TestCaseChromosome]
) -> list[tcc.TestCaseChromosome]:
    excluded_ids = {id(chromosome) for chromosome in excluded}
    return [chromosome for chromosome in chromosomes if id(chromosome) not in excluded_ids]


def _describe_failures(failing: list[tcc.TestCaseChromosome]) -> str:
    """Describes LLM test cases that raised or timed out, for a repair prompt.

    Args:
        failing: The executed chromosomes that did not work.

    Returns:
        A description of the failing tests and their errors.
    """
    parts = [f"{len(failing)} of your tests did not run cleanly:"]
    for index, chromosome in enumerate(failing[:_MAX_REPORTED_FAILURES]):
        result = chromosome.get_last_execution_result()
        if result is not None and result.timeout:
            error = "it timed out"
        elif result is not None and result.exceptions:
            position = min(result.exceptions)
            exception = result.exceptions[position]
            error = f"statement {position + 1} raised {type(exception).__name__}: {exception}"
        else:
            error = "it raised an exception"
        code = chromosome.test_case.to_test_function(index).code
        parts.append(f"```python\n{code.strip()}\n```\nIn this test, {error}.")
    if len(failing) > _MAX_REPORTED_FAILURES:
        parts.append(f"({len(failing) - _MAX_REPORTED_FAILURES} more failing tests omitted.)")
    parts.append(
        "Return only corrected versions of these failing tests; leave out the tests "
        "that already worked."
    )
    return "\n\n".join(parts)


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

    def back_off(self) -> None:
        """Doubles the plateau length after an intervention that did not help.

        CodaMOSA's back-off; it applies to the iteration-count heuristic only.
        """
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
        # The purpose of the query running in the background, if any, so that its
        # result is attributed correctly when a later poll() delivers it.
        self._inflight_purpose: CallPurpose | None = None
        # Whether the current in-flight query already caused a stall to be skipped,
        # so a stall that lasts several iterations is only counted once.
        self._inflight_skip_counted = False
        # The test cases of the last stall query and the number of goals covered
        # before it, until the next generation shows whether the query helped.
        self._back_off_check: tuple[list[tcc.TestCaseChromosome], int] | None = None
        # Lineages of injected LLM test cases, for blending, elitism and statistics.
        self._lineage = LineageTracker()
        self._generation = 0
        # Injected test cases with the blend channels they still have to be bred with.
        self._blend_queue: list[tuple[tcc.TestCaseChromosome, list[BlendChannel]]] = []
        # Offspring of the current generation, which are part of the union in evolve().
        self._last_offspring: list[tcc.TestCaseChromosome] = []

    def _target_initial_uncovered_goals(self) -> None:
        """Performs an LLM intervention to improve coverage before search iteration."""
        coverage_before = self.create_test_suite(self._archive.solutions).get_coverage()

        if (
            config.configuration.large_language_model.call_llm_for_uncovered_targets
            and coverage_before < 1.0
        ):
            self._logger.info("Coverage before LLM call: %5f", coverage_before)
            stat.track_output_variable(RuntimeVariable.CoverageBeforeLLMCall, coverage_before)

            generation = self._query_initial_targets()
            if generation is None:
                self._logger.info(
                    "Initial LLM query runs in the background; its result is integrated "
                    "when it completes."
                )
                return
            working_chromosomes = self._execute_and_repair(generation)
            self._population = (
                self._register_injected_chromosomes(working_chromosomes) + self._population
            )
            self._archive.update(self._population)

            coverage_after = self.create_test_suite(self._archive.solutions).get_coverage()
            self._logger.info("Coverage after LLM call: %5f", coverage_after)
            stat.track_output_variable(RuntimeVariable.CoverageAfterLLMCall, coverage_after)

    def _query_initial_targets(self) -> LLMGeneration | None:
        """Runs the initial LLM query through the configured query strategy.

        Target selection reads the archive and the test cluster, so it runs on the
        search thread. Only the request and the response parsing go through the
        strategy: in SYNC mode the call blocks and counts towards the blocking time,
        in ASYNC mode it returns immediately and a later poll() delivers the result.

        Returns:
            The generation, or None if the query runs in the background.
        """
        targets_map, diagnostics = self._select_uncovered_targets()
        if not targets_map:
            return LLMGeneration(chromosomes=[])
        return self._dispatch_llm_query(
            CallPurpose.UNCOVERED_TARGETS,
            functools.partial(
                self._query_llm_for_targets,
                targets_map,
                diagnostics,
                CallPurpose.UNCOVERED_TARGETS,
            ),
        )

    def _dispatch_llm_query(
        self, purpose: CallPurpose, query_fn: functools.partial[LLMGeneration]
    ) -> LLMGeneration | None:
        """Runs an LLM query through the query strategy and remembers its purpose.

        Args:
            purpose: Why the query is made.
            query_fn: The query.

        Returns:
            The generation, or None if the query runs in the background.
        """
        generation = self._llm_query_strategy.execute(query_fn)
        if generation is None:
            self._inflight_purpose = purpose
            self._inflight_skip_counted = False
        return generation

    def _llm_context(self) -> ChromosomeContext:
        """Bundles what is needed to turn LLM test cases into chromosomes.

        Returns:
            The context.
        """
        return ChromosomeContext(
            test_cluster=self.test_cluster,
            test_factory=self._test_factory,
            fitness_functions=self._test_case_fitness_functions,
            coverage_functions=self._test_suite_coverage_functions,
        )

    def _poll_and_handle_stall(self, stall_tracker: _StallTracker) -> None:
        """Polls for background LLM results and checks stall detection.

        Args:
            stall_tracker: State tracker for stall detection.
        """
        # Checked before poll(): a query that finishes between the two calls must
        # keep its purpose until the next poll() delivers its result.
        was_in_progress = self._llm_query_strategy.is_in_progress()
        pending = self._llm_query_strategy.poll()
        purpose = self._inflight_purpose
        if pending is not None or not was_in_progress:
            # The background query delivered its result, or finished without one
            # (e.g. it raised): nothing is in flight any more.
            self._inflight_purpose = None
            self._inflight_skip_counted = False
        if pending is not None and pending.chromosomes:
            self._integrate_llm_chromosomes(pending.chromosomes)
            if purpose is CallPurpose.STALL:
                count(RuntimeVariable.LLMStallTestsPublished, len(pending.chromosomes))
                self._back_off_check = (
                    pending.chromosomes,
                    stall_tracker.last_length_of_covered_goals,
                )

        if config.configuration.large_language_model.call_llm_on_stall_detection:
            current_covered = len(self._archive.covered_goals)
            self._back_off_if_query_did_not_help(stall_tracker, current_covered)
            if stall_tracker.check_stall(current_covered):
                if self._llm_query_strategy.is_in_progress():
                    if not self._inflight_skip_counted:
                        count(RuntimeVariable.LLMStallSkippedInFlight)
                        self._inflight_skip_counted = True
                else:
                    llm_chromosomes = self._maybe_intervene_on_stall()
                    if llm_chromosomes is not None:
                        self._back_off_check = (llm_chromosomes, current_covered)
                    stall_tracker.reset()

    def _back_off_if_query_did_not_help(
        self, stall_tracker: _StallTracker, current_covered: int
    ) -> None:
        """Backs off if the last stall query's test cases did not help the search.

        Called one generation after the test cases joined the population. As in
        CodaMOSA, the query did not help if none of its test cases stayed in the
        population; a coverage gain since the query also counts as help, since the
        mutants of these test cases cannot be told apart from other offspring.

        Args:
            stall_tracker: State tracker for stall detection.
            current_covered: Current number of covered goals in archive.
        """
        if self._back_off_check is None:
            return
        llm_chromosomes, covered_before = self._back_off_check
        self._back_off_check = None
        kept = {id(chromosome) for chromosome in self._population}
        stayed = any(id(chromosome) in kept for chromosome in llm_chromosomes)
        if not stayed and current_covered <= covered_before:
            stall_tracker.back_off()

    def _seed_archive_from_llm(self) -> None:
        """Seed valid LLM test cases directly into the archive before search iteration 0."""
        generation = self._generate_initial_llm_test_cases()
        if not generation.chromosomes:
            return
        working_chromosomes = self._execute_and_repair(generation)
        if not working_chromosomes:
            self._logger.warning(
                "All %d initial LLM test cases raised exceptions or timed out; "
                "archive will not be seeded with LLM test cases.",
                len(generation.chromosomes),
            )
            self._log_common_failure(generation.chromosomes)
            return
        self._update_archive_with_initial_tests(working_chromosomes)

    def _execute_and_repair(self, generation: LLMGeneration) -> list[tcc.TestCaseChromosome]:
        """Executes LLM chromosomes and asks the LLM to repair the ones that raise.

        Every repaired response is executed again; repairs stop once all chromosomes
        work, ``repair_attempts`` repair calls were made for the original call, or the
        search budget is used up.

        Args:
            generation: The generation to execute.

        Returns:
            The chromosomes that ran without exceptions or timeouts.
        """
        working = self._filter_working_test_cases(generation.chromosomes)
        failing = _without(generation.chromosomes, working)
        while failing:
            repaired = self.model.llm_test_case_handler.repair_chromosomes(
                generation,
                _describe_failures(failing),
                self._llm_context(),
                may_repair=self.resources_left,
            )
            if repaired is None:
                break
            generation = repaired
            # A repaired response may repeat tests that already work; keep one copy.
            known = {chromosome.test_case for chromosome in working}
            candidates = [c for c in generation.chromosomes if c.test_case not in known]
            newly_working = self._filter_working_test_cases(candidates)
            working += newly_working
            failing = _without(candidates, newly_working)
        return working

    def _log_common_failure(self, chromosomes: list[tcc.TestCaseChromosome]) -> None:
        """Log the exception if every candidate chromosome failed with the same one.

        A single systematic problem (e.g. an ``ImportError`` in a shared import)
        otherwise silently discards every LLM test case.

        Args:
            chromosomes: The executed candidate chromosomes.
        """
        failures: set[str] = set()
        for chromosome in chromosomes:
            result = chromosome.get_last_execution_result()
            exceptions = result.exceptions if result is not None else None
            if not isinstance(exceptions, dict) or not exceptions:
                return
            first = exceptions[min(exceptions)]
            failures.add(repr(first))
            if len(failures) > 1:
                return
        if failures:
            self._logger.warning(
                "All initial LLM test cases failed with the same exception: %s",
                failures.pop(),
            )

    def _generate_initial_llm_test_cases(self) -> LLMGeneration:
        """Generate initial test cases using the LLM for the module under test.

        Returns:
            The test case chromosomes generated by the LLM, with their conversation.
        """
        generation = self.model.llm_test_case_handler.generate_chromosomes(
            self.model.build_test_generation_prompt(),
            self._llm_context(),
            purpose=CallPurpose.INITIAL.value,
            may_repair=self.resources_left,
        )
        if generation.response is None:
            self._logger.warning(
                "Initial LLM query for the module under test returned no results "
                "(timeout or error); archive will not be seeded with LLM test cases."
            )
            return generation
        stat.track_output_variable(RuntimeVariable.TotalLTCs, len(generation.chromosomes))
        self._logger.info(
            "Generated %d initial LLM test case chromosomes.", len(generation.chromosomes)
        )
        return generation

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

        self._reset_llm_statistics()
        pre_search_time = 0.0
        if config.configuration.large_language_model.hybrid_initial_population:
            pre_search_time += _timed(self._seed_archive_from_llm)

        self._population = self._get_random_population()
        self._archive.update(self._population)

        pre_search_time += _timed(self._target_initial_uncovered_goals)
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.LLMPreSearchTime, pre_search_time
        )

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
            stat.track_output_variable(
                RuntimeVariable.LLMBlockingTimeSeconds, self._llm_query_strategy.blocked_seconds
            )

        return self._finalize_generation()

    @staticmethod
    def _reset_llm_statistics() -> None:
        """Starts the search-time LLM statistics at zero, so they are always reported."""
        reset_statement_ratio()
        for variable in (
            RuntimeVariable.LLMCallsSucceeded,
            RuntimeVariable.LLMCallsFailed,
            RuntimeVariable.LLMCallsTimedOut,
            RuntimeVariable.LLMRepairCalls,
            RuntimeVariable.LLMStallQueriesSubmitted,
            RuntimeVariable.LLMStallResponsesReceived,
            RuntimeVariable.LLMStallTestsPublished,
            RuntimeVariable.LLMStallSkippedBudget,
            RuntimeVariable.LLMStallSkippedInFlight,
        ):
            count(variable, 0)

    def _integrate_llm_chromosomes(self, llm_chromosomes: list[tcc.TestCaseChromosome]) -> None:
        """Integrates newly generated LLM test case chromosomes into the population.

        Args:
            llm_chromosomes: List of test case chromosomes from the LLM.
        """
        self._population = self._register_injected_chromosomes(llm_chromosomes) + self._population
        self._logger.info(
            "Added %d LLM test case chromosomes to the population.",
            len(llm_chromosomes),
        )

    @staticmethod
    def _blend_counts() -> dict[BlendChannel, int]:
        search_config = config.configuration.search_algorithm
        return {
            BlendChannel.GOAL_CROSSOVER: search_config.llm_blend_goal_crossovers,
            BlendChannel.MUTANT: search_config.llm_blend_mutants,
            BlendChannel.TOURNAMENT_CROSSOVER: search_config.llm_blend_tournament_crossovers,
        }

    def _register_injected_chromosomes(
        self, llm_chromosomes: list[tcc.TestCaseChromosome]
    ) -> list[tcc.TestCaseChromosome]:
        """Starts a lineage for each injected test case and queues it for blending.

        Args:
            llm_chromosomes: The LLM test cases that enter the population.

        Returns:
            The test cases to add to the population: all of them, unless blending is
            enabled and ``llm_blend_keep_raw`` is off. In that case, only the archive
            is updated with them.
        """
        counts = self._blend_counts()
        brood = [channel for channel in BLEND_CHANNELS for _ in range(max(counts[channel], 0))]
        for chromosome in llm_chromosomes:
            self._lineage.inject(chromosome, self._generation)
            if brood:
                self._blend_queue.append((chromosome, list(brood)))
        if brood and not config.configuration.search_algorithm.llm_blend_keep_raw:
            # They do not compete, but the archive keeps the goals they cover.
            self._update_goals_with(llm_chromosomes)
            return []
        return llm_chromosomes

    def _breed_llm_broods(self) -> list[tcc.TestCaseChromosome]:
        """Breeds the queued broods of injected test cases, up to the evaluation cap.

        Returns:
            The blended offspring, each starting a sub-lineage of its injected test.
        """
        cap = config.configuration.search_algorithm.llm_blend_max_evaluations
        limit = cap if cap > 0 else math.inf
        brood: list[tcc.TestCaseChromosome] = []
        while self._blend_queue and len(brood) < limit:
            injected, channels = self._blend_queue[0]
            root = self._lineage.root_of(injected)
            assert root is not None
            while channels and len(brood) < limit:
                channel = channels.pop(0)
                offspring = self._blend(injected, channel)
                if offspring is not None:
                    self._lineage.derive(offspring, root, channel, self._generation)
                    brood.append(offspring)
            if not channels:
                self._blend_queue.pop(0)
        return brood

    def _blend(
        self, injected: tcc.TestCaseChromosome, channel: BlendChannel
    ) -> tcc.TestCaseChromosome | None:
        """Breeds one offspring of an injected test case.

        Args:
            injected: The injected test case.
            channel: The blend channel to use.

        Returns:
            The offspring, or None if it is empty or equal to the injected test case.
        """
        offspring = injected.clone()
        if channel is BlendChannel.MUTANT:
            for _ in range(config.configuration.search_algorithm.number_of_mutations):
                self._mutate(offspring)
        else:
            partner = (
                self._goal_crossover_partner(injected)
                if channel is BlendChannel.GOAL_CROSSOVER
                else None
            )
            if partner is None:
                partner = self._selection_function.select(self._population)[0]
            try:
                self._crossover_function.cross_over(offspring, partner.clone())
            except ConstructionFailedException:
                self._logger.debug("Blending crossover failed.")
                return None
        if offspring.size() == 0 or offspring.test_case == injected.test_case:
            return None
        return offspring

    def _blend_target_goals(self) -> Iterable[ff.FitnessFunction]:
        """Returns the uncovered goals a goal crossover may aim at.

        Returns:
            The uncovered goals of the archive.
        """
        return self._archive.uncovered_goals

    def _goal_crossover_partner(
        self, injected: tcc.TestCaseChromosome
    ) -> tcc.TestCaseChromosome | None:
        """Picks the partner of a goal crossover.

        The target is the uncovered goal the injected test case gets closest to; the
        partner is the population member outside its lineage that gets closest to the
        same goal.

        Args:
            injected: The injected test case.

        Returns:
            The partner, or None if there is no uncovered goal or no candidate.
        """
        goals = list(self._blend_target_goals())
        root = self._lineage.root_of(injected)
        candidates = [
            member
            for member in self._population
            if member is not injected and self._lineage.root_of(member) != root
        ]
        if not goals or not candidates:
            return None
        target = min(goals, key=injected.get_fitness_for)
        return min(candidates, key=lambda member: member.get_fitness_for(target))

    def evolve(self) -> None:
        """Runs one evolution step, then applies lineage bookkeeping and elitism."""
        previous_population = list(self._population)
        self._last_offspring = []
        super().evolve()
        self._lineage.observe(self._population)
        self._apply_lineage_elitism(previous_population + self._last_offspring)
        self._generation += 1

    def _apply_lineage_elitism(self, union: list[tcc.TestCaseChromosome]) -> None:
        """Puts the best member of each young lineage back if selection dropped them all.

        The best member is the one closest to an uncovered goal; rank and crowding
        distance are not used, because the ranking stops after the first fronts that
        fill the population, so dropped members carry stale or unset values. A
        re-inserted member replaces the worst population member that does not belong
        to a young lineage, so the population size stays the same.

        Args:
            union: The parents and offspring that the last selection chose from.
        """
        search_config = config.configuration.search_algorithm
        generations = search_config.llm_lineage_elitism_generations
        if generations <= 0:
            return
        young = self._lineage.young_roots(self._generation, generations)
        if not young:
            return
        cap = math.floor(search_config.llm_lineage_elitism_max_fraction * search_config.population)
        present = self._lineage.roots_in(self._population)
        protected = set(young)
        goals = list(self._blend_target_goals())
        reinserted: list[tcc.TestCaseChromosome] = []
        for root in young:
            if len(reinserted) >= cap:
                break
            if root in present:
                continue
            members = [member for member in union if self._lineage.root_of(member) == root]
            if not members:
                continue
            best = min(
                members,
                key=lambda member: min(
                    (member.get_fitness_for(goal) for goal in goals), default=0.0
                ),
            )
            replace_at = next(
                (
                    index
                    for index in range(len(self._population) - 1, -1, -1)
                    if self._lineage.root_of(self._population[index]) not in protected
                ),
                None,
            )
            if replace_at is None:
                self._population.append(best)
            else:
                self._population[replace_at] = best
            reinserted.append(best)
        if reinserted:
            self._lineage.reinsertions += len(reinserted)
            self._update_goals_with(reinserted)

    def _update_goals_with(self, chromosomes: list[tcc.TestCaseChromosome]) -> None:
        """Updates the archive with chromosomes that joined the population late.

        Args:
            chromosomes: The chromosomes.
        """
        self._archive.update(chromosomes)

    def after_search_finish(self) -> None:
        """Reports the lineage statistics, then notifies the search observers."""
        for variable, value in self._lineage.statistics(self._population).items():
            stat.track_output_variable(variable, value)
        super().after_search_finish()

    def _maybe_intervene_on_stall(self) -> list[tcc.TestCaseChromosome] | None:
        """Query the LLM for uncovered targets on a stall, respecting cap and budget.

        Skips the query when the maximum number of interventions has been reached or
        when too little search budget remains for the query to return and be
        integrated in time (late-budget guard).

        Returns:
            The test case chromosomes the queries produced, possibly none, or None if
            no query was sent or it runs in the background.
        """
        llm_config = config.configuration.large_language_model
        max_llm_int = llm_config.max_llm_interventions
        under_cap = max_llm_int < 0 or self._stall_intervention_count < max_llm_int
        if not under_cap:
            return None
        if not self._enough_budget_for_llm():
            self._logger.info(
                "Skipping stall LLM query: less than %ds of search budget remain.",
                llm_config.min_remaining_budget_for_llm,
            )
            count(RuntimeVariable.LLMStallSkippedBudget)
            return None
        if self._llm_query_strategy.is_in_progress():
            # Counted once per in-flight query by _poll_and_handle_stall.
            return None

        targets_map, diagnostics = self._select_uncovered_targets()
        if not targets_map:
            return None

        self._stall_intervention_count += 1
        generation = self._dispatch_llm_query(
            CallPurpose.STALL,
            functools.partial(
                self._query_llm_repeatedly,
                targets_map,
                diagnostics,
                llm_config.llm_queries_per_stall,
            ),
        )
        if generation is None:
            return None
        if generation.chromosomes:
            self._integrate_llm_chromosomes(generation.chromosomes)
            count(RuntimeVariable.LLMStallTestsPublished, len(generation.chromosomes))
        return generation.chromosomes

    def _query_llm_repeatedly(
        self,
        targets_map: dict[GenericCallableAccessibleObject, float],
        diagnostics: dict[GenericCallableAccessibleObject, str],
        queries: int,
    ) -> LLMGeneration:
        """Sends the same stall query several times, as CodaMOSA's M queries per stall.

        Before each further query it applies the same late-budget guard as before
        the first one: the search must still have resources left and at least
        ``min_remaining_budget_for_llm`` seconds, so that the queries of one stall
        cannot run past the end of the search.

        Args:
            targets_map: Mapping of callables to their coverage ratio.
            diagnostics: Mapping of callables to diagnostic hints.
            queries: How many queries to send, at least one.

        Returns:
            The test case chromosomes of all queries, with the conversation of the
            last one.
        """
        chromosomes: list[tcc.TestCaseChromosome] = []
        generation = LLMGeneration(chromosomes=[])
        for query in range(max(1, queries)):
            if query > 0 and not (self.resources_left() and self._enough_budget_for_llm()):
                break
            count(RuntimeVariable.LLMStallQueriesSubmitted)
            generation = self._query_llm_for_targets(targets_map, diagnostics, CallPurpose.STALL)
            chromosomes += generation.chromosomes
        return dataclasses.replace(generation, chromosomes=chromosomes)

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
        purpose: CallPurpose = CallPurpose.UNCOVERED_TARGETS,
    ) -> LLMGeneration:
        """Queries the LLM for uncovered targets and parses results into chromosomes.

        Safe to run asynchronously on a background thread because it does not access the
        archive.

        Args:
            targets_map: Mapping of callables to their coverage ratio.
            diagnostics: Mapping of callables to diagnostic hints.
            purpose: Why the query is made, for the trace and the stall counters.

        Returns:
            The generated chromosomes, with their conversation.
        """
        if not targets_map:
            return LLMGeneration(chromosomes=[])

        generation = self.model.llm_test_case_handler.generate_chromosomes(
            self.model.build_uncovered_targets_prompt(targets_map, diagnostics),
            self._llm_context(),
            purpose=purpose.value,
            targets=[target_name(gao) for gao in targets_map],
            may_repair=self.resources_left,
        )
        if purpose is CallPurpose.STALL and generation.response is not None:
            count(RuntimeVariable.LLMStallResponsesReceived)
        return generation

    def target_uncovered_callables(self) -> list[tcc.TestCaseChromosome]:
        """Identifies uncovered targets, queries an LLM for test cases.

         and processes the results into a list of test case chromosomes.

        Returns:
            A list of `TestCaseChromosome` objects derived from the LLM query results.
        """
        targets_map, diagnostics = self._select_uncovered_targets()
        return self._query_llm_for_targets(targets_map, diagnostics).chromosomes

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
        offspring = super()._breed_next_generation(actual_factory)
        offspring.extend(self._breed_llm_broods())
        self._last_offspring = offspring
        return offspring
