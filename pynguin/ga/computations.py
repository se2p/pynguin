#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides classes for computations on chromosomes, e.g., fitness and coverage."""
from __future__ import annotations

import abc
import dataclasses
import math
import statistics
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from pynguin.testcase.execution import ExecutionTrace

if TYPE_CHECKING:
    from pynguin.testcase.execution import ExecutionResult, KnownData, TestCaseExecutor


@dataclasses.dataclass(eq=False)
class ChromosomeComputation(abc.ABC):  # pylint:disable=too-few-public-methods
    """An abstract computation on chromosomes."""

    _executor: TestCaseExecutor
    """Executor that will be used by the computation to execute chromosomes."""


class TestCaseChromosomeComputation(
    ChromosomeComputation, metaclass=abc.ABCMeta
):  # pylint:disable=too-few-public-methods
    """A function that computes something on a test case chromosome."""

    def _run_test_case_chromosome(self, individual) -> ExecutionResult:
        """Runs a test suite and updates the execution results for
        all test cases that were changed.

        Args:
            individual: The individual to run

        Returns:
            A list of execution results
        """
        if individual.has_changed() or individual.get_last_execution_result() is None:
            individual.set_last_execution_result(
                self._executor.execute(individual.test_case)
            )
            individual.set_changed(False)
        result = individual.get_last_execution_result()
        assert result is not None
        return result


class TestSuiteChromosomeComputation(
    ChromosomeComputation, metaclass=abc.ABCMeta
):  # pylint:disable=too-few-public-methods
    """A function that computes something on a test suite chromosome."""

    def _run_test_suite_chromosome(self, individual) -> list[ExecutionResult]:
        """Runs a test suite and updates the execution results for
        all test cases that were changed.

        Args:
            individual: The individual to run

        Returns:
            A list of execution results
        """
        results: list[ExecutionResult] = []
        for test_case_chromosome in individual.test_case_chromosomes:
            if (
                test_case_chromosome.has_changed()
                or test_case_chromosome.get_last_execution_result() is None
            ):
                test_case_chromosome.set_last_execution_result(
                    self._executor.execute(test_case_chromosome.test_case)
                )
                test_case_chromosome.set_changed(False)
                # If we execute a suite which in turn executes it's test cases,
                # then we have to invalidate the values of the test cases, because
                # the test case is no longer aware that it was changed.
                test_case_chromosome.invalidate_cache()
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


class TestCaseFitnessFunction(
    TestCaseChromosomeComputation, FitnessFunction, metaclass=abc.ABCMeta
):
    """Base class for test case fitness functions."""

    def __init__(self, executor, code_object_id: int):
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

    def compute_fitness(self, individual) -> float:
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer = self._executor.tracer

        return compute_branch_distance_fitness(merged_trace, tracer.get_known_data())

    def compute_is_covered(self, individual) -> bool:
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer = self._executor.tracer

        return compute_branch_distance_fitness_is_covered(
            merged_trace, tracer.get_known_data()
        )

    def is_maximisation_function(self) -> bool:
        return False


class TestSuiteFitnessFunction(
    TestSuiteChromosomeComputation, FitnessFunction, metaclass=abc.ABCMeta
):
    """Base class for test case fitness functions."""


class BranchDistanceTestSuiteFitnessFunction(TestSuiteFitnessFunction):
    """A fitness function based on branch distances and entered code objects."""

    def __init__(self, executor):
        super().__init__(executor)
        self._excluded_code_objects: set[int] = set()
        self._excluded_true_predicates: set[int] = set()
        self._excluded_false_predicates: set[int] = set()

    def restrict(
        self, exclude_code: set[int], exclude_true: set[int], exclude_false: set[int]
    ) -> None:
        """Restrict this fitness function, i.e., which branches/code objects it
        considers

        Args:
            exclude_code: Ids of the code objects that should not be considered.
            exclude_true: Ids of predicates whose True branch should not be considered.
            exclude_false: Ids of predicates whose False branch should not be
                considered.
        """
        self._excluded_code_objects.update(exclude_code)
        self._excluded_true_predicates.update(exclude_true)
        self._excluded_false_predicates.update(exclude_false)

    def compute_fitness(self, individual) -> float:
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer

        return compute_branch_distance_fitness(
            merged_trace,
            tracer.get_known_data(),
            self._excluded_code_objects,
            self._excluded_true_predicates,
            self._excluded_false_predicates,
        )

    def compute_is_covered(self, individual) -> bool:
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer

        return compute_branch_distance_fitness_is_covered(
            merged_trace,
            tracer.get_known_data(),
            self._excluded_code_objects,
            self._excluded_true_predicates,
            self._excluded_false_predicates,
        )

    def is_maximisation_function(self) -> bool:
        return False


class LineTestSuiteFitnessFunction(TestSuiteFitnessFunction):
    """A fitness function based on lines covered and entered code objects."""

    def compute_fitness(self, individual) -> float:
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        existing_lines = self._executor.tracer.get_known_data().existing_lines
        return len(existing_lines) - len(merged_trace.covered_line_ids)

    def compute_is_covered(self, individual) -> bool:
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer

        return compute_line_coverage_fitness_is_covered(
            merged_trace,
            tracer.get_known_data(),
        )

    def is_maximisation_function(self) -> bool:
        return False


class CoverageFunction:  # pylint:disable=too-few-public-methods
    """Interface for a coverage function."""

    @abstractmethod
    def compute_coverage(self, individual) -> float:
        """Compute the coverage of the given individual.

        Args:
            individual: the chromosome to compute the coverage for.

        Returns:
            The computed coverage.
        """


# pylint: disable=too-few-public-methods
class TestSuiteCoverageFunction(
    TestSuiteChromosomeComputation, CoverageFunction, metaclass=abc.ABCMeta
):
    """Base class for all coverage functions that act on test suite level."""


class TestCaseCoverageFunction(
    TestCaseChromosomeComputation, CoverageFunction, metaclass=abc.ABCMeta
):  # pylint: disable=too-few-public-methods
    """Base class for all coverage functions that act on test case level."""


class TestSuiteBranchCoverageFunction(TestSuiteCoverageFunction):
    """Computes branch coverage on test suites."""

    def compute_coverage(self, individual) -> float:
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer
        return compute_branch_coverage(merged_trace, tracer.get_known_data())


class TestCaseBranchCoverageFunction(TestCaseCoverageFunction):
    """Computes branch coverage on test cases."""

    def compute_coverage(self, individual) -> float:
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer = self._executor.tracer
        return compute_branch_coverage(merged_trace, tracer.get_known_data())


class TestSuiteLineCoverageFunction(TestSuiteCoverageFunction):
    """Computes line coverage on test suites."""

    def compute_coverage(self, individual) -> float:
        results = self._run_test_suite_chromosome(individual)
        merged_trace = analyze_results(results)
        tracer = self._executor.tracer
        return compute_line_coverage(merged_trace, tracer.get_known_data())


class TestCaseLineCoverageFunction(TestCaseCoverageFunction):
    """Computes line coverage on test cases."""

    def compute_coverage(self, individual) -> float:
        result = self._run_test_case_chromosome(individual)
        merged_trace = analyze_results([result])
        tracer = self._executor.tracer
        return compute_line_coverage(merged_trace, tracer.get_known_data())


class ComputationCache:
    """Caches computation results and computes values on demand."""

    def __init__(
        self,
        chromosome,
        fitness_functions: list[FitnessFunction] | None = None,
        coverage_functions: list[CoverageFunction] | None = None,
        fitness_cache: dict[FitnessFunction, float] | None = None,
        is_covered_cache: dict[FitnessFunction, bool] | None = None,
        coverage_cache: dict[CoverageFunction, float] | None = None,
    ):  # pylint:disable=too-many-arguments
        self._chromosome = chromosome
        self._fitness_functions = fitness_functions if fitness_functions else []
        self._coverage_functions = coverage_functions if coverage_functions else []
        self._fitness_cache: dict[FitnessFunction, float] = (
            fitness_cache if fitness_cache else {}
        )
        self._is_covered_cache: dict[FitnessFunction, bool] = (
            is_covered_cache if is_covered_cache else {}
        )
        self._coverage_cache: dict[CoverageFunction, float] = (
            coverage_cache if coverage_cache else {}
        )

    def clone(self, new_chromosome) -> ComputationCache:
        """Create a deep copy of this cache.

        Args:
            new_chromosome: The chromosome with which this cache is associated.

        Returns:
            A deep copy.
        """
        return ComputationCache(
            new_chromosome,
            list(self._fitness_functions),
            list(self._coverage_functions),
            dict(self._fitness_cache),
            dict(self._is_covered_cache),
            dict(self._coverage_cache),
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
        assert (
            not fitness_function.is_maximisation_function()
        ), "Currently only minimization is supported"
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
        if self._chromosome.has_changed():
            # If the chromosome has changed, we invalidate all values computed so far
            self.invalidate_cache()
            # Compute those values in which we are interested.
            comp(only)
            # Mark individual as no longer changed.
            self._chromosome.set_changed(False)
        elif len(cache) != len(funcs):
            # The individual has not changed, but not all values are cached.
            # So we might have to compute the missing ones.
            comp(only)

    def _compute_fitness(self, only: FitnessFunction | None = None):
        for fitness_func in self._fitness_functions if only is None else (only,):
            if fitness_func not in self._fitness_cache:
                new_value = fitness_func.compute_fitness(self._chromosome)
                assert (
                    not math.isnan(new_value)
                    and not math.isinf(new_value)
                    and new_value >= 0
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
                assert (
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
        """Provide a sum of the current fitness values

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
        """Provides the coverage value for a certain coverage function

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
    known_data: KnownData,
    exclude_code: set[int] | None = None,
    exclude_true: set[int] | None = None,
    exclude_false: set[int] | None = None,
) -> float:
    """Computes fitness based on covered branches and branch distances.

    Args:
        trace: The execution trace
        known_data: All known data
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
        known_data.branch_less_code_objects.difference(
            trace.executed_code_objects, exclude_code
        )
    )
    assert (
        code_objects_missing >= 0.0
    ), "Amount of non covered code objects cannot be negative"

    # Handle None for branches.
    exclude_true = set() if exclude_true is None else exclude_true
    exclude_false = set() if exclude_false is None else exclude_false

    # Check if all predicates are covered
    predicate_fitness: float = 0.0
    for predicate in known_data.existing_predicates:
        if predicate not in exclude_true:
            predicate_fitness += _predicate_fitness(
                predicate, trace.true_distances, trace
            )
        if predicate not in exclude_false:
            predicate_fitness += _predicate_fitness(
                predicate, trace.false_distances, trace
            )
    assert predicate_fitness >= 0.0, "Predicate fitness cannot be negative."
    total_fitness = code_objects_missing + predicate_fitness
    return total_fitness


def _predicate_fitness(
    predicate: int, branch_distances: dict[int, float], trace: ExecutionTrace
) -> float:
    if predicate in branch_distances and branch_distances[predicate] == 0.0:
        return 0.0
    if (
        predicate in trace.executed_predicates
        and trace.executed_predicates[predicate] >= 2
    ):
        return normalise(branch_distances[predicate])
    return 1.0


def compute_branch_distance_fitness_is_covered(
    trace: ExecutionTrace,
    known_data: KnownData,
    exclude_code: set[int] | None = None,
    exclude_true: set[int] | None = None,
    exclude_false: set[int] | None = None,
) -> bool:
    """Computes if all branches and code objects have been executed.

    Args:
        trace: The execution trace
        known_data: All known data
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
            known_data.branch_less_code_objects.difference(
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
    for predicate in known_data.existing_predicates:
        if (
            predicate not in exclude_true
            and (predicate, 0.0) not in trace.true_distances
        ):
            return False
        if (
            predicate not in exclude_false
            and (predicate, 0.0) not in trace.false_distances
        ):
            return False
    return True


def compute_line_coverage_fitness_is_covered(
    trace: ExecutionTrace, known_data: KnownData
) -> bool:
    """Computes if all lines and code objects have been executed.

    Args:
        trace: The execution trace
        known_data: All known data

    Returns:
        True, if all lines were covered, false otherwise
    """
    return len(trace.covered_line_ids) == len(known_data.existing_lines)


def compute_branch_coverage(trace: ExecutionTrace, known_data: KnownData) -> float:
    """Computes branch coverage on bytecode instructions which should equal
    decision coverage on source.

    Args:
        trace: The execution trace
        known_data: All known data

    Returns:
        The computed coverage value
    """

    covered = len(
        trace.executed_code_objects.intersection(known_data.branch_less_code_objects)
    )
    existing = len(known_data.branch_less_code_objects)

    # Every predicate creates two branches
    existing += len(known_data.existing_predicates) * 2

    # A branch is covered if it has a distance of 0.0
    # Must consider both branches created by a predicate, i.e. true and false.
    covered += len([v for v in trace.true_distances.values() if v == 0.0])
    covered += len([v for v in trace.false_distances.values() if v == 0.0])

    if existing == 0:
        # Nothing to cover => everything is covered.
        coverage = 1.0
    else:
        coverage = covered / existing
    assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
    return coverage


def compute_line_coverage(trace: ExecutionTrace, known_data: KnownData) -> float:
    """Computes line coverage on bytecode instructions.

    Args:
        trace: The execution trace
        known_data: All known data

    Returns:
        The computed coverage value
    """
    existing = len(known_data.existing_lines)

    if existing == 0:
        # Nothing to cover => everything is covered.
        coverage = 1.0
    else:
        covered = len(trace.covered_line_ids)
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
