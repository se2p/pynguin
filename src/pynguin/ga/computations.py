#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for computations on chromosomes, e.g., fitness and coverage."""

from __future__ import annotations

import abc
import dataclasses
from abc import abstractmethod
from typing import TYPE_CHECKING

from pynguin.ga.checked_coverage import compute_assertion_checked_coverage
from pynguin.ga.fitness_metrics import (
    analyze_results,
    compute_branch_coverage,
    compute_branch_distance_fitness,
    compute_branch_distance_fitness_is_covered,
    compute_checked_coverage_statement_fitness_is_covered,
    compute_line_coverage,
    compute_line_coverage_fitness_is_covered,
)

if TYPE_CHECKING:
    from pynguin.ga.testcasechromosome import TestCaseChromosome
    from pynguin.ga.testsuitechromosome import TestSuiteChromosome
    from pynguin.testcase.execution import AbstractTestCaseExecutor, ExecutionResult


@dataclasses.dataclass(eq=False)
class ChromosomeComputation(abc.ABC):
    """An abstract computation on chromosomes."""

    _executor: AbstractTestCaseExecutor
    """Executor that will be used by the computation to execute chromosomes."""


class TestCaseChromosomeComputation(ChromosomeComputation, abc.ABC):
    """A function that computes something on a test case chromosome."""

    def _run_test_case_chromosome(self, individual: TestCaseChromosome) -> ExecutionResult:
        """Runs a test suite and updates the execution results.

        Updates all test cases that were changed.

        Args:
            individual: The individual to run

        Returns:
            A list of execution results
        """
        if individual.changed or individual.get_last_execution_result() is None:
            individual.set_last_execution_result(self._executor.execute(individual.test_case))
            individual.changed = False
        result = individual.get_last_execution_result()
        assert result is not None
        return result


class TestSuiteChromosomeComputation(ChromosomeComputation, abc.ABC):
    """A function that computes something on a test suite chromosome."""

    def _run_test_suite_chromosome(self, individual: TestSuiteChromosome) -> list[ExecutionResult]:
        """Runs a test suite and updates the execution results.

        Updates all test cases that were changed.

        Args:
            individual: The individual to run

        Returns:
            A list of execution results
        """
        test_case_chromosomes = tuple(
            (
                test_case_chromosome,
                test_case_chromosome.changed
                or test_case_chromosome.get_last_execution_result() is None,
            )
            for test_case_chromosome in individual.test_case_chromosomes
        )

        changed_results_iterator = iter(
            self._executor.execute_multiple(
                test_case_chromosome.test_case
                for test_case_chromosome, changed in test_case_chromosomes
                if changed
            )
        )

        results: list[ExecutionResult] = []

        for test_case_chromosome, changed in test_case_chromosomes:
            result: ExecutionResult | None
            if changed:
                result = next(changed_results_iterator)
                test_case_chromosome.set_last_execution_result(result)
                test_case_chromosome.changed = False
                # If we execute a suite which in turn executes it's test cases,
                # then we have to invalidate the values of the test cases, because
                # the test case is no longer aware that it was changed.
                test_case_chromosome.invalidate_cache()
            else:
                result = test_case_chromosome.get_last_execution_result()

            assert result is not None

            results.append(result)

        return results


class FitnessFunction:
    """Interface for a fitness function."""

    @abstractmethod
    def compute_fitness(self, individual) -> float:
        """Calculate the fitness value.

        Args:
            individual: the chromosome to compute the fitness for.

        Returns:
            the new fitness  # noqa: DAR202
        """

    @abstractmethod
    def compute_is_covered(self, individual) -> bool:
        """Compute if the goal of this fitness function is covered.

        This computation is usually cheaper than computing the fitness, because
        we are not interested in the distance, but only a boolean result.

        Args:
            individual: the chromosome to check coverage on.

        Returns:
            True, if the goal of this fitness function is covered.
        """

    @abstractmethod
    def is_maximisation_function(self) -> bool:
        """Do we need to maximise or minimise this function?

        Returns:
             Whether or not this is a maximisation function  # noqa: DAR202
        """


class TestCaseFitnessFunction(TestCaseChromosomeComputation, FitnessFunction, abc.ABC):
    """Base class for test case fitness functions."""

    def __init__(self, executor, code_object_id: int):  # noqa: D107
        super().__init__(executor)
        self._code_object_id = code_object_id

    @property
    def code_object_id(self) -> int:
        """The code object id, where the target of the fitness function is located.

        Returns:
            The code object id where the target of the fitness function is located.
        """
        return self._code_object_id


class BranchDistanceTestCaseFitnessFunction(TestCaseFitnessFunction):
    """A fitness function based on branch distances and entered code objects."""

    def compute_fitness(self, individual) -> float:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])

        return compute_branch_distance_fitness(merged_trace, self._executor.subject_properties)

    def compute_is_covered(self, individual) -> bool:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])

        return compute_branch_distance_fitness_is_covered(
            merged_trace, self._executor.subject_properties
        )

    def is_maximisation_function(self) -> bool:  # noqa: D102
        return False


class TestSuiteFitnessFunction(TestSuiteChromosomeComputation, FitnessFunction, abc.ABC):
    """Base class for test suite fitness functions."""


class BranchDistanceTestSuiteFitnessFunction(TestSuiteFitnessFunction):
    """A fitness function based on branch distances and entered code objects."""

    def __init__(self, executor):  # noqa: D107
        super().__init__(executor)
        self._excluded_code_objects: set[int] = set()
        self._excluded_true_predicates: set[int] = set()
        self._excluded_false_predicates: set[int] = set()

    def restrict(
        self, exclude_code: set[int], exclude_true: set[int], exclude_false: set[int]
    ) -> None:
        """Restrict this fitness function.

        Restricts the fitness function with respect to the branches/code objects it
        considers.

        Args:
            exclude_code: Ids of the code objects that should not be considered.
            exclude_true: Ids of predicates whose True branch should not be considered.
            exclude_false: Ids of predicates whose False branch should not be
                considered.
        """
        self._excluded_code_objects.update(exclude_code)
        self._excluded_true_predicates.update(exclude_true)
        self._excluded_false_predicates.update(exclude_false)

    def compute_fitness(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        return compute_branch_distance_fitness(
            merged_trace,
            self._executor.subject_properties,
            self._excluded_code_objects,
            self._excluded_true_predicates,
            self._excluded_false_predicates,
        )

    def compute_is_covered(self, individual) -> bool:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        return compute_branch_distance_fitness_is_covered(
            merged_trace,
            self._executor.subject_properties,
            self._excluded_code_objects,
            self._excluded_true_predicates,
            self._excluded_false_predicates,
        )

    def is_maximisation_function(self) -> bool:  # noqa: D102
        return False


class LineTestSuiteFitnessFunction(TestSuiteFitnessFunction):
    """A fitness function based on lines covered and entered code objects."""

    def compute_fitness(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        existing_lines = self._executor.subject_properties.existing_lines
        return len(existing_lines) - len(merged_trace.covered_line_ids)

    def compute_is_covered(self, individual) -> bool:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        return compute_line_coverage_fitness_is_covered(
            merged_trace,
            self._executor.subject_properties,
        )

    def is_maximisation_function(self) -> bool:  # noqa: D102
        return False


class StatementCheckedTestSuiteFitnessFunction(TestSuiteFitnessFunction):
    """A fitness function for the checked statement coverage of test suites.

    A fitness function based on lines included in the backward slice of each statement
    of a test suite.
    """

    def compute_fitness(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        return len(self._executor.subject_properties.existing_lines) - len(
            merged_trace.checked_lines
        )

    def compute_is_covered(self, individual) -> bool:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        return compute_checked_coverage_statement_fitness_is_covered(
            merged_trace,
            self._executor.subject_properties,
        )

    def is_maximisation_function(self) -> bool:  # noqa: D102
        return False


class CoverageFunction:
    """Interface for a coverage function."""

    @abstractmethod
    def compute_coverage(self, individual) -> float:
        """Compute the coverage of the given individual.

        Args:
            individual: the chromosome to compute the coverage for.

        Returns:
            The computed coverage.
        """


class TestSuiteCoverageFunction(TestSuiteChromosomeComputation, CoverageFunction, abc.ABC):
    """Base class for all coverage functions that act on test suite level."""


class TestCaseCoverageFunction(TestCaseChromosomeComputation, CoverageFunction, abc.ABC):
    """Base class for all coverage functions that act on test case level."""


class TestSuiteBranchCoverageFunction(TestSuiteCoverageFunction):
    """Computes branch coverage on test suites."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        return compute_branch_coverage(merged_trace, self._executor.subject_properties)


class TestCaseBranchCoverageFunction(TestCaseCoverageFunction):
    """Computes branch coverage on test cases."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])

        return compute_branch_coverage(merged_trace, self._executor.subject_properties)


class TestSuiteLineCoverageFunction(TestSuiteCoverageFunction):
    """Computes line coverage on test suites."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        return compute_line_coverage(merged_trace, self._executor.subject_properties)


class TestCaseLineCoverageFunction(TestCaseCoverageFunction):
    """Computes line coverage on test cases."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])

        return compute_line_coverage(merged_trace, self._executor.subject_properties)


class TestSuiteStatementCheckedCoverageFunction(TestSuiteCoverageFunction):
    """Computes checked coverage on the statements of test suites."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        existing = len(self._executor.subject_properties.existing_lines)

        if existing == 0:
            # Nothing to cover => everything is covered.
            coverage = 1.0
        else:
            covered = len(merged_trace.checked_lines)
            coverage = covered / existing
        assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
        return coverage


class TestCaseStatementCheckedCoverageFunction(TestCaseCoverageFunction):
    """Computes checked coverage on the statements of test cases."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])

        existing = len(self._executor.subject_properties.existing_lines)

        if existing == 0:
            # Nothing to cover => everything is covered.
            coverage = 1.0
        else:
            covered = len(merged_trace.checked_lines)
            coverage = covered / existing
        assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
        return coverage


class TestSuiteAssertionCheckedCoverageFunction(TestSuiteCoverageFunction):
    """Computes checked coverage on test suites with assertions."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)

        return compute_assertion_checked_coverage(merged_trace, self._executor.subject_properties)


class TestCaseAssertionCheckedCoverageFunction(TestCaseCoverageFunction):
    """Computes checked coverage on test cases with assertions."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])

        return compute_assertion_checked_coverage(merged_trace, self._executor.subject_properties)
