#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an assertion generator."""

from __future__ import annotations

import ast
import dataclasses
import logging
import threading
import types

from typing import TYPE_CHECKING

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_trace as at
import pynguin.assertion.assertiontraceobserver as ato
import pynguin.assertion.mutation_analysis.controller as ct
import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.configuration as config
import pynguin.ga.chromosomevisitor as cv
import pynguin.testcase.execution as ex
import pynguin.utils.statistics.stats as stat

from pynguin.analyses.constants import ConstantPool
from pynguin.analyses.constants import DynamicConstantProvider
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.instrumentation.machinery import ExecutionTracer
from pynguin.instrumentation.machinery import InstrumentationExecutionTracer
from pynguin.instrumentation.machinery import build_transformer
from pynguin.utils import randomness
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


if TYPE_CHECKING:
    from collections.abc import Generator
    from collections.abc import Iterable

    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.testcase.testcase as tc

    from pynguin.instrumentation.instrumentation import InstrumentationTransformer

_LOGGER = logging.getLogger(__name__)


class AssertionGenerator(cv.ChromosomeVisitor):
    """A simple assertion generator.

    Creates all regression assertions.
    """

    _logger = logging.getLogger(__name__)

    def __init__(self, plain_executor: ex.TestCaseExecutor, filtering_executions: int = 1):
        """Create new assertion generator.

        Args:
            plain_executor: The executor that is used to execute on the non mutated
                module.
            filtering_executions: How often should the tests be executed to filter
                out trivially flaky assertions, e.g., str representations based on
                memory locations.
        """
        self._filtering_executions = filtering_executions
        self._plain_executor = plain_executor

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

        # Perform filtering executions to remove trivially flaky assertions.
        with self._plain_executor.temporarily_add_remote_observer(
            ato.RemoteAssertionVerificationObserver()
        ):
            for _ in range(self._filtering_executions):
                # Create a copy of the list that is shuffled.
                shuffled_copy = list(test_cases)
                randomness.RNG.shuffle(shuffled_copy)
                for test, result in zip(
                    shuffled_copy,
                    self._plain_executor.execute_multiple(shuffled_copy),
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


class InstrumentedMutationController(ct.MutationController):
    """A controller that creates instrumented mutants."""

    def __init__(
        self,
        mutant_generator: mu.Mutator,
        module_ast: ast.Module,
        module: types.ModuleType,
        tracer: ExecutionTracer,
        *,
        testing: bool = False,
    ) -> None:
        """Create new controller.

        Args:
            mutant_generator: The mutant generator.
            module_ast: The module AST.
            module: The module.
            tracer: The execution tracer.
            testing: Enable test mode, currently required for integration testing.
        """
        super().__init__(mutant_generator, module_ast, module)

        self._transformer = build_transformer(
            InstrumentationExecutionTracer(tracer),
            {config.CoverageMetric.BRANCH},
            DynamicConstantProvider(ConstantPool(), EmptyConstantProvider(), 0, 1),
        )

        # Some debug information
        self._testing = testing
        self._testing_created_mutants: list[str] = []

    @property
    def tracer(self) -> ExecutionTracer:
        """Provides the execution tracer.

        Returns:
            The execution tracer.
        """
        return self._transformer.instrumentation_tracer.tracer

    @property
    def transformer(self) -> InstrumentationTransformer:
        """Provides the instrumentation transformer.

        Returns:
            The instrumentation transformer.
        """
        return self._transformer

    def create_mutant(self, ast_node: ast.Module) -> types.ModuleType:  # noqa: D102
        self.tracer.current_thread_identifier = threading.current_thread().ident
        self.tracer.reset()
        module_name = self._module.__name__
        code = compile(ast_node, module_name, "exec")
        if self._testing:
            self._testing_created_mutants.append(ast.unparse(ast_node))
        code = self._transformer.instrument_module(code)
        module = types.ModuleType(module_name)
        try:
            exec(code, module.__dict__)  # noqa: S102
        except Exception as exception:  # noqa: BLE001
            _LOGGER.debug("Error creating mutant: %s", exception)
        except SystemExit as exception:
            _LOGGER.debug("Caught SystemExit during mutant creation/execution: %s", exception)
        self.tracer.store_import_trace()
        return module


class MutationAnalysisAssertionGenerator(AssertionGenerator):
    """Uses mutation analysis to filter out less relevant assertions."""

    def __init__(
        self,
        plain_executor: ex.TestCaseExecutor,
        mutation_controller: InstrumentedMutationController,
        *,
        testing: bool = False,
    ):
        """Initializes the generator.

        Args:
            plain_executor: Executor used for plain execution
            mutation_controller: Controller for mutation analysis
            testing: Enable test mode, currently required for integration testing.
        """
        super().__init__(plain_executor)

        # We use a separate tracer and executor to execute tests on the mutants.
        if config.configuration.subprocess:
            self._mutation_executor: ex.TestCaseExecutor = ex.SubprocessTestCaseExecutor(
                mutation_controller.tracer
            )
        else:
            self._mutation_executor = ex.TestCaseExecutor(mutation_controller.tracer)

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
    ) -> Iterable[ex.ExecutionResult | None]:
        if mutated_module is None:
            self._logger.info(
                "Skipping mutant %3i/%i because it created an invalid module",
                idx,
                mutant_count,
            )
            return (None for _ in range(len(test_cases)))

        self._logger.info(
            "Running tests on mutant %3i/%i",
            idx,
            mutant_count,
        )
        self._mutation_executor.module_provider.add_mutated_version(
            module_name=config.configuration.module_name,
            mutated_module=mutated_module,
        )

        return self._mutation_executor.execute_multiple(test_cases)

    def _execute_test_case_on_mutants(
        self,
        test_cases: list[tc.TestCase],
        mutant_count: int,
    ) -> Generator[Iterable[ex.ExecutionResult | None], None, None]:
        for idx, (mutated_module, _) in enumerate(
            self._mutation_controller.create_mutants(), start=1
        ):
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

        mutant_count = self._mutation_controller.mutant_count()

        with self._mutation_executor.temporarily_add_remote_observer(
            ato.RemoteAssertionVerificationObserver()
        ):
            for tests_mutant_results in self._execute_test_case_on_mutants(
                test_cases, mutant_count
            ):
                for i, test_mutant_results in enumerate(tests_mutant_results):
                    tests_mutants_results[i].append(test_mutant_results)

        summary = self.__compute_mutation_summary(mutant_count, tests_mutants_results)
        self.__report_mutation_summary(summary)
        self.__remove_non_relevant_assertions(test_cases, tests_mutants_results, summary)

    @staticmethod
    def __remove_non_relevant_assertions(
        test_cases: list[tc.TestCase],
        tests_mutants_results: list[list[ex.ExecutionResult | None]],
        mutation_summary: _MutationSummary,
    ) -> None:
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

    def __report_mutation_summary(self, mutation_summary: _MutationSummary):
        if self._testing:
            self._testing_mutation_summary = mutation_summary
        metrics = mutation_summary.get_metrics()
        stat.track_output_variable(
            RuntimeVariable.NumberOfKilledMutants, metrics.num_killed_mutants
        )
        stat.track_output_variable(
            RuntimeVariable.NumberOfTimedOutMutants, metrics.num_timeout_mutants
        )
        stat.track_output_variable(
            RuntimeVariable.NumberOfCreatedMutants, metrics.num_created_mutants
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
