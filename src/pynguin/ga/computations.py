#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for computations on chromosomes, e.g., fitness and coverage."""

from __future__ import annotations

import abc
import dataclasses
import math
import statistics

from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar

import pynguin.utils.opcodes as op

from pynguin.instrumentation.tracer import ExecutionTrace
from pynguin.slicer.dynamicslicer import AssertionSlicer
from pynguin.slicer.dynamicslicer import DynamicSlicer


if TYPE_CHECKING:
    from collections.abc import Callable

    from pynguin.ga.testcasechromosome import TestCaseChromosome
    from pynguin.ga.testsuitechromosome import TestSuiteChromosome
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.slicer.dynamicslicer import SlicingCriterion
    from pynguin.testcase.execution import AbstractTestCaseExecutor
    from pynguin.testcase.execution import ExecutionResult
    from pynguin.testcase.statement import Statement


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
        tracer = self._executor.tracer

        return compute_branch_distance_fitness(merged_trace, tracer.get_subject_properties())

    def compute_is_covered(self, individual) -> bool:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer = self._executor.tracer

        return compute_branch_distance_fitness_is_covered(
            merged_trace, tracer.get_subject_properties()
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
        tracer = self._executor.tracer

        return compute_branch_distance_fitness(
            merged_trace,
            tracer.get_subject_properties(),
            self._excluded_code_objects,
            self._excluded_true_predicates,
            self._excluded_false_predicates,
        )

    def compute_is_covered(self, individual) -> bool:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer

        return compute_branch_distance_fitness_is_covered(
            merged_trace,
            tracer.get_subject_properties(),
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
        tracer = self._executor.tracer
        existing_lines = tracer.get_subject_properties().existing_lines
        return len(existing_lines) - len(merged_trace.covered_line_ids)

    def compute_is_covered(self, individual) -> bool:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer

        return compute_line_coverage_fitness_is_covered(
            merged_trace,
            tracer.get_subject_properties(),
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
        tracer = self._executor.tracer

        return len(tracer.get_subject_properties().existing_lines) - len(merged_trace.checked_lines)

    def compute_is_covered(self, individual) -> bool:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer

        return compute_checked_coverage_statement_fitness_is_covered(
            merged_trace,
            tracer.get_subject_properties(),
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
        tracer = self._executor.tracer
        return compute_branch_coverage(merged_trace, tracer.get_subject_properties())


class TestCaseBranchCoverageFunction(TestCaseCoverageFunction):
    """Computes branch coverage on test cases."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer = self._executor.tracer
        return compute_branch_coverage(merged_trace, tracer.get_subject_properties())


class TestSuiteLineCoverageFunction(TestSuiteCoverageFunction):
    """Computes line coverage on test suites."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer
        return compute_line_coverage(merged_trace, tracer.get_subject_properties())


class TestCaseLineCoverageFunction(TestCaseCoverageFunction):
    """Computes line coverage on test cases."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer = self._executor.tracer
        return compute_line_coverage(merged_trace, tracer.get_subject_properties())


class TestSuiteStatementCheckedCoverageFunction(TestSuiteCoverageFunction):
    """Computes checked coverage on the statements of test suites."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer

        existing = len(tracer.get_subject_properties().existing_lines)

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
        tracer = self._executor.tracer
        existing = len(tracer.get_subject_properties().existing_lines)

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
        tracer = self._executor.tracer
        return compute_assertion_checked_coverage(merged_trace, tracer.get_subject_properties())


class TestCaseAssertionCheckedCoverageFunction(TestCaseCoverageFunction):
    """Computes checked coverage on test cases with assertions."""

    def compute_coverage(self, individual) -> float:  # noqa: D102
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer = self._executor.tracer
        return compute_assertion_checked_coverage(merged_trace, tracer.get_subject_properties())


class ComputationCache:
    """Caches computation results and computes values on demand."""

    def __init__(  # noqa: D107
        self,
        chromosome,
        *,
        fitness_functions: list[FitnessFunction] | None = None,
        coverage_functions: list[CoverageFunction] | None = None,
        fitness_cache: dict[FitnessFunction, float] | None = None,
        is_covered_cache: dict[FitnessFunction, bool] | None = None,
        coverage_cache: dict[CoverageFunction, float] | None = None,
    ):
        self._chromosome = chromosome
        self._fitness_functions = fitness_functions or []
        self._coverage_functions = coverage_functions or []
        self._fitness_cache: dict[FitnessFunction, float] = fitness_cache or {}
        self._is_covered_cache: dict[FitnessFunction, bool] = is_covered_cache or {}
        self._coverage_cache: dict[CoverageFunction, float] = coverage_cache or {}

    def clone(self, new_chromosome) -> ComputationCache:
        """Create a deep copy of this cache.

        Args:
            new_chromosome: The chromosome with which this cache is associated.

        Returns:
            A deep copy.
        """
        return ComputationCache(
            new_chromosome,
            fitness_functions=list(self._fitness_functions),
            coverage_functions=list(self._coverage_functions),
            fitness_cache=dict(self._fitness_cache),
            is_covered_cache=dict(self._is_covered_cache),
            coverage_cache=dict(self._coverage_cache),
        )

    def get_fitness_functions(self) -> list[FitnessFunction]:
        """Provide the currently configured fitness functions of this chromosome.

        Returns:
            The list of currently configured fitness functions
        """
        return self._fitness_functions

    def add_fitness_function(
        self,
        fitness_function: FitnessFunction,
    ) -> None:
        """Adds the given fitness function.

        Args:
            fitness_function: A fitness function
        """
        assert not fitness_function.is_maximisation_function(), (
            "Currently only minimization is supported"
        )
        self._fitness_functions.append(fitness_function)

    def get_coverage_functions(self) -> list[CoverageFunction]:
        """Provide the currently configured coverage functions of this chromosome.

        Returns:
            The list of currently configured coverage functions.
        """
        return self._coverage_functions

    def add_coverage_function(
        self,
        coverage_function: CoverageFunction,
    ) -> None:
        """Adds a coverage function.

        Args:
            coverage_function: A fitness function
        """
        self._coverage_functions.append(coverage_function)

    T = TypeVar("T", CoverageFunction, FitnessFunction)

    def _check_cache(
        self,
        comp: Callable[[T | None], None],
        cache: dict[T, Any],
        funcs: list[T],
        only: T | None = None,
    ) -> None:
        """Check if values need to be computed.

        Args:
            comp: The function to execute, if values need to be computed.
            cache: The cache that should be checked.
            funcs: The functions that are used to fill the respective cache.
            only: Only compute the values for this function, optional.
        """
        if self._chromosome.changed:
            # If the chromosome has changed, we invalidate all values computed so far
            self.invalidate_cache()
            # Compute those values in which we are interested.
            comp(only)
            # Mark individual as no longer changed.
            self._chromosome.changed = False
        elif len(cache) != len(funcs):
            # The individual has not changed, but not all values are cached.
            # So we might have to compute the missing ones.
            comp(only)

    def _compute_fitness(self, only: FitnessFunction | None = None):
        for fitness_func in self._fitness_functions if only is None else (only,):
            if fitness_func not in self._fitness_cache:
                new_value = fitness_func.compute_fitness(self._chromosome)
                assert (  # noqa: PT018
                    not math.isnan(new_value) and not math.isinf(new_value) and new_value >= 0
                ), f"Invalid fitness value {new_value}"
                self._fitness_cache[fitness_func] = new_value
                # When computing a minimising fitness value, we can also determine
                # if the goal is covered, i.e. if it is zero.
                self._is_covered_cache[fitness_func] = new_value == 0.0

    def _compute_is_covered(self, only: FitnessFunction | None = None):
        for fitness_func in self._fitness_functions if only is None else (only,):
            if fitness_func not in self._is_covered_cache:
                new_value = fitness_func.compute_is_covered(self._chromosome)
                self._is_covered_cache[fitness_func] = new_value

    def _compute_coverage(self, only: CoverageFunction | None = None):
        for coverage_func in self._coverage_functions if only is None else (only,):
            if coverage_func not in self._coverage_cache:
                new_value = coverage_func.compute_coverage(self._chromosome)
                assert (  # noqa: PT018
                    not math.isnan(new_value)
                    and not math.isinf(new_value)
                    and (0 <= new_value <= 1)
                ), f"Invalid coverage value {new_value}"
                self._coverage_cache[coverage_func] = new_value

    def invalidate_cache(self) -> None:
        """Invalidate all cached computation values."""
        self._fitness_cache.clear()
        self._is_covered_cache.clear()
        self._coverage_cache.clear()

    def get_fitness(self) -> float:
        """Provide a sum of the current fitness values.

        Returns:
            The sum of the current fitness values
        """
        self._check_cache(
            self._compute_fitness,
            self._fitness_cache,
            self._fitness_functions,
        )
        return sum(self._fitness_cache.values())

    def get_fitness_for(self, fitness_function: FitnessFunction) -> float:
        """Returns the fitness values of a specific fitness function.

        Args:
            fitness_function: The fitness function

        Returns:
            Its fitness value
        """
        self._check_cache(
            self._compute_fitness,
            self._fitness_cache,
            self._fitness_functions,
            fitness_function,
        )
        return self._fitness_cache[fitness_function]

    def get_is_covered(self, fitness_function: FitnessFunction) -> bool:
        """Check if the individual covers this fitness function.

        Args:
            fitness_function: The fitness function to check

        Returns:
            True, iff the individual covers the fitness function.
        """
        self._check_cache(
            self._compute_is_covered,
            self._is_covered_cache,
            self._fitness_functions,
            fitness_function,
        )
        return self._is_covered_cache[fitness_function]

    def get_coverage(self) -> float:
        """Provides the mean coverage value.

        Returns:
            The mean coverage value
        """
        self._check_cache(
            self._compute_coverage,
            self._coverage_cache,
            self._coverage_functions,
        )
        return statistics.mean(self._coverage_cache.values())

    def get_coverage_for(self, coverage_function: CoverageFunction) -> float:
        """Provides the coverage value for a certain coverage function.

        Args:
            coverage_function: The fitness function whose coverage value shall be
                returned

        Returns:
            The coverage value for the fitness function
        """
        self._check_cache(
            self._compute_coverage,
            self._coverage_cache,
            self._coverage_functions,
            coverage_function,
        )
        return self._coverage_cache[coverage_function]


def normalise(value: float) -> float:
    """Normalise a value.

    Args:
        value: The value to normalise

    Returns:
        The normalised value

    Raises:
        RuntimeError: if the value is negative
    """
    if value < 0:
        raise RuntimeError("Values to normalise cannot be negative")
    if math.isinf(value):
        return 1.0
    return value / (1.0 + value)


def analyze_results(results: list[ExecutionResult]) -> ExecutionTrace:
    """Merge the trace of the given results.

    Args:
        results: The list of execution results to analyze

    Returns:
        the merged traces.
    """
    merged = ExecutionTrace()
    for result in results:
        trace = result.execution_trace
        assert trace is not None
        merged.merge(trace)
    return merged


def compute_branch_distance_fitness(
    trace: ExecutionTrace,
    subject_properties: SubjectProperties,
    exclude_code: set[int] | None = None,
    exclude_true: set[int] | None = None,
    exclude_false: set[int] | None = None,
) -> float:
    """Computes fitness based on covered branches and branch distances.

    Args:
        trace: The execution trace
        subject_properties: All known data
        exclude_code: Ids of the code objects that should not be considered.
        exclude_true: Ids of predicates whose True branch should not be considered.
        exclude_false: Ids of predicates whose False branch should not be considered.

    Returns:
        The computed fitness value
    """
    # Handle None. Cannot use empty set as default, because of mutable default args.
    exclude_code = set() if exclude_code is None else exclude_code

    # Check if all branch-less code objects were executed.
    code_objects_missing: float = len(
        subject_properties.branch_less_code_objects.difference(
            trace.executed_code_objects, exclude_code
        )
    )
    assert code_objects_missing >= 0.0, "Amount of non covered code objects cannot be negative"

    # Handle None for branches.
    exclude_true = set() if exclude_true is None else exclude_true
    exclude_false = set() if exclude_false is None else exclude_false

    # Check if all predicates are covered
    predicate_fitness: float = 0.0
    for predicate in subject_properties.existing_predicates:
        if predicate not in exclude_true:
            predicate_fitness += _predicate_fitness(predicate, trace.true_distances, trace)
        if predicate not in exclude_false:
            predicate_fitness += _predicate_fitness(predicate, trace.false_distances, trace)

    assert predicate_fitness >= 0.0, "Predicate fitness cannot be negative."
    return code_objects_missing + predicate_fitness


def _predicate_fitness(
    predicate: int, branch_distances: dict[int, float], trace: ExecutionTrace
) -> float:
    if predicate in branch_distances and branch_distances[predicate] == 0.0:
        return 0.0
    if predicate in trace.executed_predicates and trace.executed_predicates[predicate] >= 2:
        return normalise(branch_distances[predicate])
    return 1.0


def compute_branch_distance_fitness_is_covered(
    trace: ExecutionTrace,
    subject_properties: SubjectProperties,
    exclude_code: set[int] | None = None,
    exclude_true: set[int] | None = None,
    exclude_false: set[int] | None = None,
) -> bool:
    """Computes if all branches and code objects have been executed.

    Args:
        trace: The execution trace
        subject_properties: All known data
        exclude_code: Ids of the code objects that should not be considered.
        exclude_true: Ids of predicates whose True branch should not be considered.
        exclude_false: Ids of predicates whose False branch should not be considered.

    Returns:
        True, if all branches were covered
    """
    # Handle None. Cannot use empty set as default, because of mutable default args.
    exclude_code = set() if exclude_code is None else exclude_code

    # Check if all branch-less code objects were executed.
    if (
        len(
            subject_properties.branch_less_code_objects.difference(
                trace.executed_code_objects, exclude_code
            )
        )
        > 0
    ):
        return False

    # Handle None for branches.
    exclude_true = set() if exclude_true is None else exclude_true
    exclude_false = set() if exclude_false is None else exclude_false

    # Check if all predicates are covered
    for predicate in subject_properties.existing_predicates:
        if predicate not in exclude_true and (predicate, 0.0) not in trace.true_distances:
            return False
        if predicate not in exclude_false and (predicate, 0.0) not in trace.false_distances:
            return False
    return True


def compute_line_coverage_fitness_is_covered(
    trace: ExecutionTrace, subject_properties: SubjectProperties
) -> bool:
    """Computes if all lines and code objects have been executed.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        True, if all lines were covered, false otherwise
    """
    return len(trace.covered_line_ids) == len(subject_properties.existing_lines)


def compute_checked_coverage_statement_fitness_is_covered(
    trace: ExecutionTrace, subject_properties: SubjectProperties
) -> bool:
    """Computes if all lines and code objects are checked by a return statement.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        True, if all lines were checked by a return, false otherwise
    """
    return len(trace.checked_lines) == len(subject_properties.existing_lines)


def compute_branch_coverage(trace: ExecutionTrace, subject_properties: SubjectProperties) -> float:
    """Computes branch coverage on bytecode instructions.

    The resulting coverage should be equal to decision coverage on source code.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        The computed coverage value
    """
    covered = len(
        trace.executed_code_objects.intersection(subject_properties.branch_less_code_objects)
    )
    existing = len(subject_properties.branch_less_code_objects)

    # Every predicate creates two branches
    existing += len(subject_properties.existing_predicates) * 2

    # A branch is covered if it has a distance of 0.0
    # Must consider both branches created by a predicate, i.e. true and false.
    covered += len([v for v in trace.true_distances.values() if v == 0.0])
    covered += len([v for v in trace.false_distances.values() if v == 0.0])

    coverage = 1.0 if existing == 0 else covered / existing
    assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
    return coverage


def compute_line_coverage(trace: ExecutionTrace, subject_properties: SubjectProperties) -> float:
    """Computes line coverage on bytecode instructions.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        The computed coverage value
    """
    existing = len(subject_properties.existing_lines)

    if existing == 0:
        # Nothing to cover => everything is covered.
        coverage = 1.0
    else:
        covered = len(trace.covered_line_ids)
        coverage = covered / existing
    assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
    return coverage


def _cleanse_included_implicit_return_none(
    subject_properties, statement_checked_lines, statement_slice
):
    if (  # noqa: SIM102
        # check if the last included instructions before the store
        # are a "return None"
        len(statement_slice) >= 3
        and statement_slice[-3].opcode == op.LOAD_CONST
        and statement_slice[-3].arg is None
        and statement_slice[-2].opcode == op.RETURN_VALUE
    ):
        if (
            # check if the "return None" is implicit or explicit
            len(statement_slice) != 3 and statement_slice[-4].lineno != statement_slice[-3].lineno
        ):
            statement_checked_lines.remove(
                DynamicSlicer.get_line_id_by_instruction(statement_slice[-3], subject_properties)
            )


def compute_statement_checked_lines(
    statements: list[Statement],
    trace: ExecutionTrace,
    subject_properties: SubjectProperties,
    statement_slicing_criteria: dict[int, SlicingCriterion],
) -> set[int]:
    """Computes checked coverage on bytecode instructions.

    Each statement can be sliced, returning a list of instructions
    that are checked by the return value of the statement.
    If we combine all lists of instructions returned by slicing all statements,
    we get the combined dynamic slice of the test execution's statements.
    We then can map all instructions inside the slice to lines
    that are checked covered of the module under test.

    Args:
        statements: The sliced instructions
        trace: The execution trace
        subject_properties: All known data
        statement_slicing_criteria: a dictionary of statement positions
            and its slicing criteria

    Returns:
        The checked line ids of lines checked by the statements
    """
    known_code_objects = subject_properties.existing_code_objects
    dynamic_slicer = DynamicSlicer(known_code_objects)
    checked_lines_ids = set()
    for statement in statements:
        if statement.get_position() not in statement_slicing_criteria:
            # if there is no slicing criterion there was an exception during
            # the test case execution and the latter statements after the one
            # with an exception will never be executed,
            # thus having no slicing criterion
            break
        statement_slice = dynamic_slicer.slice(
            trace,
            statement_slicing_criteria[statement.get_position()],
        )
        statement_checked_lines = DynamicSlicer.map_instructions_to_lines(
            statement_slice, subject_properties
        )

        _cleanse_included_implicit_return_none(
            subject_properties, statement_checked_lines, statement_slice
        )

        checked_lines_ids.update(statement_checked_lines)
    return checked_lines_ids


def compute_assertion_checked_coverage(
    trace: ExecutionTrace, subject_properties: SubjectProperties
) -> float:
    """Computes checked coverage on bytecode instructions.

    Each assertion can be sliced, returning a list of instructions
    that are checked by an assertion.
    If we combine all lists of instructions returned by slicing all assertions,
    we get the combined dynamic slice of the test execution's assertions.
    We then can map all instructions inside the slice to lines
    that are checked covered of the module under test.
    To calculate the coverage we can then divide the amount of lines checked
    covered through the test execution by the lines overall available in the
    module under test.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        The computed coverage value
    """
    existing = len(subject_properties.existing_lines)

    if existing == 0:
        # Nothing to cover => everything is covered.
        coverage = 1.0
    else:
        assertion_slicer = AssertionSlicer(subject_properties.existing_code_objects)
        checked_instructions = []
        for executed_assertion in trace.executed_assertions:
            assertion_checked_instructions = assertion_slicer.slice_assertion(
                executed_assertion, trace
            )
            executed_assertion.assertion.checked_instructions.extend(assertion_checked_instructions)
            # checked at any point by the assertion of a statement
            checked_instructions.extend(assertion_checked_instructions)

        # reduce coverage to lines instead of instructions
        checked_lines = DynamicSlicer.map_instructions_to_lines(
            checked_instructions, subject_properties
        )

        covered = len(checked_lines)
        coverage = covered / existing
    assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
    return coverage


def compare(fitness_1: float, fitness_2: float) -> int:
    """Compare the two specified values.

    Args:
        fitness_1: The first value to compare
        fitness_2: The second value to compare

    Returns:
        the value 0 if fitness_1 is equal to fitness_2; a value less than 0 if
        fitness_1 is less than fitness_2; and a value greater than 0 if fitness_1 is
        greater than fitness_2
    """
    if fitness_1 < fitness_2:
        return -1
    if fitness_1 > fitness_2:
        return 1
    return 0
