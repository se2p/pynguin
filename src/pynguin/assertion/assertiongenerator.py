#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an assertion generator."""

from __future__ import annotations

import dataclasses
import logging
import time
from typing import TYPE_CHECKING

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_trace as at
import pynguin.assertion.assertiontraceobserver as ato
import pynguin.assertion.mutation_analysis.controller as ct
import pynguin.configuration as config
import pynguin.ga.chromosomevisitor as cv
import pynguin.testcase.execution as ex
import pynguin.utils.statistics.stats as stat
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.utils import randomness
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import types
    from collections.abc import Generator, Iterable

    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.testcase.testcase as tc


_LOGGER = logging.getLogger(__name__)


def create_filtering_executor(
    plain_executor: ex.TestCaseExecutor,
) -> ex.TestCaseExecutor | None:
    """Build the executor to use for the assertion-filtering pass.

    Returns a fresh-subprocess executor so that filtering catches per-process
    nondeterminism, or ``None`` (meaning: reuse the plain executor and filter
    in-process) when subprocess filtering is disabled or the plain executor already
    runs in a subprocess.

    Args:
        plain_executor: The executor used for the in-process capture pass.

    Returns:
        A subprocess executor for filtering, or ``None`` to filter in-process.
    """
    if not config.configuration.test_case_output.filter_assertions_in_subprocess:
        return None
    if isinstance(plain_executor, ex.SubprocessTestCaseExecutor):
        return None
    return ex.SubprocessTestCaseExecutor(SubjectProperties())


class AssertionGenerator(cv.ChromosomeVisitor):
    """A simple assertion generator.

    Creates all regression assertions.
    """

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        plain_executor: ex.TestCaseExecutor,
        filtering_executions: int = 1,
        *,
        filtering_executor: ex.TestCaseExecutor | None = None,
    ):
        """Create new assertion generator.

        Args:
            plain_executor: The executor that is used to execute on the non mutated
                module.
            filtering_executions: How often should the tests be executed to filter
                out trivially flaky assertions, e.g., str representations based on
                memory locations.
            filtering_executor: The executor used for the filtering executions. When
                a fresh-subprocess executor is supplied, filtering also catches
                per-process nondeterminism (``id()``, identity hashing, ``hash()`` of
                str/bytes, once-computed timestamps) that in-process re-execution
                cannot observe. Defaults to ``plain_executor`` (in-process filtering).
        """
        self._filtering_executions = filtering_executions
        self._plain_executor = plain_executor
        self._filtering_executor = filtering_executor or plain_executor

    def visit_test_suite_chromosome(  # noqa: D102
        self, chromosome: tsc.TestSuiteChromosome
    ) -> None:
        self._add_assertions([chrom.test_case for chrom in chromosome.test_case_chromosomes])

    def visit_test_case_chromosome(  # noqa: D102
        self, chromosome: tcc.TestCaseChromosome
    ) -> None:
        self._add_assertions([chromosome.test_case])

    def _add_assertions(self, test_cases: list[tc.TestCase]):
        # First run of executions to add assertions
        with self._plain_executor.temporarily_add_remote_observer(
            ato.RemoteAssertionTraceObserver()
        ):
            for test, result in zip(
                test_cases,
                self._plain_executor.execute_multiple(test_cases),
                strict=True,
            ):
                self._add_assertions_for(test, result)

        # Perform filtering executions to remove trivially flaky assertions. These run
        # on the (possibly subprocess) filtering executor so that per-process
        # nondeterminism is exercised, not just per-execution nondeterminism.
        with self._filtering_executor.temporarily_add_remote_observer(
            ato.RemoteAssertionVerificationObserver()
        ):
            for _ in range(self._filtering_executions):
                # Create a copy of the list that is shuffled.
                shuffled_copy = list(test_cases)
                randomness.RNG.shuffle(shuffled_copy)
                for test, result in zip(
                    shuffled_copy,
                    self._filtering_executor.execute_multiple(shuffled_copy),
                    strict=True,
                ):
                    self.__remove_non_holding_assertions(test, result)

    @staticmethod
    def __remove_non_holding_assertions(test: tc.TestCase, result: ex.ExecutionResult):
        for idx, statement in enumerate(test.statements):
            pos_to_key = dict(enumerate(statement.assertions))

            to_delete: OrderedSet[int] = OrderedSet()
            if idx in result.assertion_verification_trace.failed:
                to_delete.update(result.assertion_verification_trace.failed[idx])
            if idx in result.assertion_verification_trace.error:
                to_delete.update(result.assertion_verification_trace.error[idx])

            for pos in sorted(to_delete, reverse=True):
                statement.assertions.remove(pos_to_key[pos])

    def _add_assertions_for(self, test_case: tc.TestCase, result: ex.ExecutionResult):
        # In order to avoid repeating the same assertions after each statement,
        # we keep track of the last assertions and only assert things, if they
        # have changed.
        previous_statement_assertions: OrderedSet[ass.Assertion] = OrderedSet()
        for statement in test_case.statements:
            current_statement_assertions = result.assertion_trace.get_assertions(statement)
            for assertion in current_statement_assertions:
                if (
                    not config.configuration.test_case_output.allow_stale_assertions
                    and assertion in previous_statement_assertions
                ):
                    # We already saw the same assertion in the previous statement
                    # So the value did not change.
                    continue
                if (
                    test_case.size_with_assertions()
                    >= config.configuration.test_case_output.max_length_test_case
                ):
                    self._logger.debug(
                        "No more assertions are added, because the maximum length "
                        "of a test case with its assertions was reached"
                    )
                    return
                statement.add_assertion(assertion)

            # Only update the previously seen assertions when we encounter a
            # statement that actually affects assertions.
            if statement.affects_assertions:
                previous_statement_assertions = current_statement_assertions


@dataclasses.dataclass
class _MutantInfo:
    """Collect data about a single mutant."""

    # Number of the mutant.
    mut_num: int

    # Did the mutant cause a timeout?
    timed_out_by: list[int] = dataclasses.field(default_factory=list)

    # Was the mutant killed by any test?
    killed_by: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class _MutationSummary:
    """Summary about mutation."""

    mutant_information: list[_MutantInfo] = dataclasses.field(default_factory=list)

    def get_survived(self) -> list[_MutantInfo]:
        """Get survived Mutants.

        Returns:
            The survived mutants
        """
        return [
            info for info in self.mutant_information if not info.killed_by and not info.timed_out_by
        ]

    def get_killed(self) -> list[_MutantInfo]:
        """Get killed Mutants.

        Returns:
            The killed mutants
        """
        return [
            info for info in self.mutant_information if info.killed_by and not info.timed_out_by
        ]

    def get_timeout(self) -> list[_MutantInfo]:
        """Get timed out Mutants.

        Returns:
            The timed out mutants
        """
        return [info for info in self.mutant_information if info.timed_out_by]

    def get_metrics(self) -> _MutationMetrics:
        """Provide mutation metrics.

        Returns:
            The mutation metrics.
        """
        return _MutationMetrics(
            num_created_mutants=len(self.mutant_information),
            num_killed_mutants=len(self.get_killed()),
            num_timeout_mutants=len(self.get_timeout()),
        )


@dataclasses.dataclass
class _MutationMetrics:
    num_created_mutants: int
    num_killed_mutants: int
    num_timeout_mutants: int

    def get_score(self) -> float:
        """Computes the mutation score.

        Returns:
            The mutation score
        """
        divisor = self.num_created_mutants - self.num_timeout_mutants
        assert divisor >= 0
        if divisor == 0:
            # No mutants -> all mutants covered.
            return 1.0
        return self.num_killed_mutants / divisor


def _select_minimal_assertions(
    kill_map: dict[tuple[int, int], set[int]],
) -> set[tuple[int, int]]:
    """Greedy set-cover selection of a minimal assertion subset.

    Given a mapping from assertion key ``(stmt_idx, assertion_idx)`` to the set of
    mutant indices that assertion kills, return the subset of keys that together
    cover every killed mutant (the union of all kill sets). Assertions with an empty
    kill set are never selected. Ties are broken by ascending key (insertion order)
    for deterministic output.

    Args:
        kill_map: Mapping from assertion key to the set of mutants it kills.

    Returns:
        The set of assertion keys to keep.
    """
    universe: set[int] = set()
    for kills in kill_map.values():
        universe |= kills

    # Only assertions that kill at least one mutant can ever be selected.
    candidates = {key: kills for key, kills in kill_map.items() if kills}

    uncovered = set(universe)
    keep: set[tuple[int, int]] = set()
    while uncovered:
        best_key: tuple[int, int] | None = None
        best_cover = 0
        for key in sorted(candidates):
            cover = len(candidates[key] & uncovered)
            if cover > best_cover:
                best_cover = cover
                best_key = key
        if best_key is None:
            break
        keep.add(best_key)
        uncovered -= candidates[best_key]
        del candidates[best_key]

    # Greedy may leave a selection whose kills are fully covered by the others it
    # later picked. Prune such redundant assertions, dropping higher keys first so
    # lower (earlier) assertions are preferred, keeping coverage unchanged.
    for key in sorted(keep, reverse=True):
        others: set[int] = set()
        for other in keep:
            if other != key:
                others |= kill_map[other]
        if kill_map[key] <= others:
            keep.discard(key)
    return keep


class MutationAnalysisAssertionGenerator(AssertionGenerator):
    """Uses mutation analysis to filter out less relevant assertions."""

    def __init__(
        self,
        plain_executor: ex.TestCaseExecutor,
        mutation_controller: ct.MutationController,
        *,
        filtering_executor: ex.TestCaseExecutor | None = None,
        testing: bool = False,
    ):
        """Initializes the generator.

        Args:
            plain_executor: Executor used for plain execution
            mutation_controller: Controller for mutation analysis
            filtering_executor: Executor used for the assertion-filtering pass; see
                :class:`AssertionGenerator`. Defaults to in-process filtering.
            testing: Enable test mode, currently required for integration testing.
        """
        super().__init__(plain_executor, filtering_executor=filtering_executor)

        # We use a separate executor to execute tests on the mutants.
        subject_properties = SubjectProperties()

        self._mutation_executor: ex.TestCaseExecutor
        if config.configuration.subprocess:
            self._mutation_executor = ex.SubprocessTestCaseExecutor(subject_properties)
        else:
            self._mutation_executor = ex.TestCaseExecutor(subject_properties)

        self._mutation_executor.add_remote_observer(ato.RemoteAssertionVerificationObserver())

        self._mutation_controller = mutation_controller

        # Some debug information
        self._testing = testing
        self._testing_mutation_summary: _MutationSummary = _MutationSummary()

    def _execute_test_case_on_mutant(
        self,
        test_cases: list[tc.TestCase],
        mutated_module: types.ModuleType | None,
        idx: int,
        mutant_count: int,
    ) -> Iterable[ex.ExecutionResult | None] | None:
        if mutated_module is None:
            self._logger.info(
                "Skipping mutant %3i/%i because it created an invalid module",
                idx,
                mutant_count,
            )
            return None

        self._logger.info(
            "Running tests on mutant %3i/%i",
            idx,
            mutant_count,
        )
        self._mutation_executor.module_provider.add_mutated_version(
            module_name=config.configuration.module_name,
            mutated_module=mutated_module,
        )

        results = self._mutation_executor.execute_multiple(test_cases)

        # The subprocess executor materializes and runs all tests before returning,
        # so aborting early there saves nothing; only the in-process executor is a
        # lazy generator we can stop consuming.
        if isinstance(self._mutation_executor, ex.SubprocessTestCaseExecutor):
            return results
        return self._abort_after_first_timeout(results, len(test_cases))

    @staticmethod
    def _abort_after_first_timeout(
        results: Iterable[ex.ExecutionResult | None],
        num_tests: int,
    ) -> Generator[ex.ExecutionResult | None, None, None]:
        """Stop executing a mutant once one of its tests times out.

        A mutant that turns a terminating loop into a non-terminating one times
        out on every remaining test, each costing the full execution timeout.
        Since a timed-out mutant is discarded from both the score and the
        assertion filtering, everything after the first timeout is wasted. Pad the
        remaining test slots with ``None`` so the result shape is preserved.

        Args:
            results: The lazily produced per-test execution results.
            num_tests: The total number of tests for this mutant.

        Yields:
            The execution results, padded with ``None`` after the first timeout.
        """
        consumed = 0
        aborted = False
        for result in results:
            consumed += 1
            yield result
            if result is not None and result.timeout:
                aborted = True
                break
        if aborted:
            for _ in range(num_tests - consumed):
                yield None

    def _execute_test_case_on_mutants(
        self,
        test_cases: list[tc.TestCase],
        mutant_count: int,
    ) -> Generator[Iterable[ex.ExecutionResult | None] | None, None, None]:
        maximum_time = config.configuration.test_case_output.maximum_mutation_time
        start_time = time.monotonic()

        for idx, (mutated_module, _) in enumerate(
            self._mutation_controller.create_mutants(), start=1
        ):
            if maximum_time >= 0 and time.monotonic() - start_time >= maximum_time:
                self._logger.info(
                    "Mutation time budget of %ss exceeded; checked %i of %i mutant(s).",
                    maximum_time,
                    idx - 1,
                    mutant_count,
                )
                break
            yield self._execute_test_case_on_mutant(
                test_cases,
                mutated_module,
                idx,
                mutant_count,
            )

    def _add_assertions(self, test_cases: list[tc.TestCase]):
        super()._add_assertions(test_cases)
        self._handle_add_assertions(test_cases)

    def _handle_add_assertions(self, test_cases: list[tc.TestCase]):
        tests_mutants_results: list[list[ex.ExecutionResult | None]] = [[] for _ in test_cases]

        # Pre-truncation total number of mutants the module yields.
        num_created = self._mutation_controller.mutant_count()

        # Only fully-checked mutants (valid module, executed within the budget)
        # get a column; unchecked mutants must not enter the score as survivors.
        num_checked = 0
        for tests_mutant_results in self._execute_test_case_on_mutants(test_cases, num_created):
            if tests_mutant_results is None:
                continue
            num_checked += 1
            for i, test_mutant_results in enumerate(tests_mutant_results):
                tests_mutants_results[i].append(test_mutant_results)

        summary = self.__compute_mutation_summary(num_checked, tests_mutants_results)
        self.__report_mutation_summary(summary, num_created)
        self.__remove_non_relevant_assertions(test_cases, tests_mutants_results, summary)

    @staticmethod
    def __remove_non_relevant_assertions(
        test_cases: list[tc.TestCase],
        tests_mutants_results: list[list[ex.ExecutionResult | None]],
        mutation_summary: _MutationSummary,
    ) -> None:
        if config.configuration.test_case_output.assertion_minimization:
            MutationAnalysisAssertionGenerator.__minimize_assertions(
                test_cases, tests_mutants_results, mutation_summary
            )
            return
        for test, results in zip(test_cases, tests_mutants_results, strict=True):
            merged = at.AssertionVerificationTrace()
            for result, mut in zip(results, mutation_summary.mutant_information, strict=True):
                # Ignore timed out executions
                if result is not None and len(mut.timed_out_by) == 0:
                    merged.merge(result.assertion_verification_trace)
            for stmt_idx, statement in enumerate(test.statements):
                for assertion_idx, assertion in reversed(list(enumerate(statement.assertions))):
                    if not merged.was_violated(stmt_idx, assertion_idx):
                        statement.assertions.remove(assertion)

    @staticmethod
    def __minimize_assertions(
        test_cases: list[tc.TestCase],
        tests_mutants_results: list[list[ex.ExecutionResult | None]],
        mutation_summary: _MutationSummary,
    ) -> None:
        """Keep a minimal subset of assertions preserving the killed mutants.

        For each test case, a greedy set-cover selection keeps only enough
        assertions to preserve the full set of assertion-attributable mutant kills.
        Assertions that kill nothing are dropped (subsuming the plain
        non-relevant-assertion removal); redundant assertions that only re-kill
        mutants already covered by kept assertions are removed as well.

        Statements carrying only an exception assertion are left untouched to
        avoid the fragility of mixing exception and value assertions.

        Args:
            test_cases: The test cases whose assertions are minimized.
            tests_mutants_results: Per-test, per-mutant execution results.
            mutation_summary: Summary with per-mutant timeout information.
        """
        for test, results in zip(test_cases, tests_mutants_results, strict=True):
            kill_map = MutationAnalysisAssertionGenerator.__build_kill_map(
                test, results, mutation_summary
            )
            keep = _select_minimal_assertions(kill_map)

            for stmt_idx, statement in enumerate(test.statements):
                if statement.has_only_exception_assertion():
                    continue
                for assertion_idx, assertion in reversed(list(enumerate(statement.assertions))):
                    if (stmt_idx, assertion_idx) not in keep:
                        statement.assertions.remove(assertion)

    @staticmethod
    def __build_kill_map(
        test: tc.TestCase,
        results: list[ex.ExecutionResult | None],
        mutation_summary: _MutationSummary,
    ) -> dict[tuple[int, int], set[int]]:
        """Map each assertion to the set of mutants it kills via violation.

        Statements carrying only an exception assertion are skipped. Only
        assertion-attributable kills on non-timed-out mutants are counted.

        Args:
            test: The test case whose assertions are inspected.
            results: Per-mutant execution results for this test.
            mutation_summary: Summary with per-mutant timeout information.

        Returns:
            Mapping from ``(stmt_idx, assertion_idx)`` to the killed mutant indices.
        """
        kill_map: dict[tuple[int, int], set[int]] = {}
        for stmt_idx, statement in enumerate(test.statements):
            if statement.has_only_exception_assertion():
                continue
            for assertion_idx in range(len(statement.assertions)):
                kills = {
                    mutant_idx
                    for mutant_idx, (result, mut) in enumerate(
                        zip(results, mutation_summary.mutant_information, strict=True)
                    )
                    if result is not None
                    and len(mut.timed_out_by) == 0
                    and result.assertion_verification_trace.was_violated(stmt_idx, assertion_idx)
                }
                kill_map[stmt_idx, assertion_idx] = kills
        return kill_map

    @staticmethod
    def __compute_mutation_summary(
        number_of_mutants: int,
        tests_mutants_results: list[list[ex.ExecutionResult | None]],
    ) -> _MutationSummary:
        mutation_info = [_MutantInfo(i) for i in range(number_of_mutants)]
        for test_num, test_mutants_results in enumerate(tests_mutants_results):
            # For each mutation, check if we had a violated assertion
            for info, result in zip(mutation_info, test_mutants_results, strict=True):
                if result is None or info.timed_out_by:
                    continue
                if result.timeout:
                    # Mutant caused timeout
                    info.timed_out_by.append(test_num)
                elif (
                    len(result.assertion_verification_trace.error) > 0
                    or len(result.assertion_verification_trace.failed) > 0
                    or result.has_test_exceptions()
                    # Execution with assertions should not raise exceptions.
                    # If it does, it is probably an incompetent mutant
                ):
                    info.killed_by.append(test_num)
        return _MutationSummary(mutation_info)

    def __report_mutation_summary(self, mutation_summary: _MutationSummary, num_created: int):
        if self._testing:
            self._testing_mutation_summary = mutation_summary
        metrics = mutation_summary.get_metrics()
        stat.track_output_variable(
            RuntimeVariable.NumberOfKilledMutants, metrics.num_killed_mutants
        )
        stat.track_output_variable(
            RuntimeVariable.NumberOfTimedOutMutants, metrics.num_timeout_mutants
        )
        # NumberOfCreatedMutants stays the pre-truncation total; NumberOfCheckedMutants
        # is how many were actually executed. The score is computed over the latter.
        stat.track_output_variable(RuntimeVariable.NumberOfCreatedMutants, num_created)
        stat.track_output_variable(
            RuntimeVariable.NumberOfCheckedMutants, metrics.num_created_mutants
        )
        if num_created != metrics.num_created_mutants:
            _LOGGER.info(
                "Mutation analysis truncated: created %i mutant(s), checked %i.",
                num_created,
                metrics.num_created_mutants,
            )
        stat.track_output_variable(RuntimeVariable.MutationScore, metrics.get_score())

        for info in mutation_summary.mutant_information:
            if info.killed_by:
                _LOGGER.info(
                    "Mutant %i killed by Test(s): %s",
                    info.mut_num,
                    ", ".join(map(str, info.killed_by)),
                )
            elif info.timed_out_by:
                _LOGGER.info(
                    "Mutant %i timed out. First time with test %i.",
                    info.mut_num,
                    info.timed_out_by[0],
                )
        survived = mutation_summary.get_survived()
        _LOGGER.info(
            "Number of Surviving Mutant(s): %i (Mutants: %s)",
            len(survived),
            ", ".join(str(x.mut_num) for x in survived),
        )
