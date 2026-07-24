#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Computation results caching and demand-driven calculations."""

from __future__ import annotations

import math
import statistics
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

    from pynguin.ga.computations import CoverageFunction, FitnessFunction

    T = TypeVar("T", CoverageFunction, FitnessFunction)
else:
    T = TypeVar("T")


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
                # whether the goal is covered without calling compute_is_covered,
                # simply by checking if the fitness value is close enough to zero.
                self._is_covered_cache[fitness_func] = math.isclose(new_value, 0.0)

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

    def set_fitness_values(self, fitness_values: dict[FitnessFunction, float]) -> None:
        """Sets the fitness values for the specific functions.

        Args:
            fitness_values: A dictionary of fitness values, keyed by fitness function.
        """
        for fitness_key, value in fitness_values.items():
            self._fitness_cache[fitness_key] = value

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

    def set_coverage_values(self, coverage_values: dict[CoverageFunction, float]) -> None:
        """Sets the coverage values for the specific functions.

        Args:
            coverage_values: A dictionary of coverage values, keyed by coverage function.
        """
        for coverage_key, value in coverage_values.items():
            self._coverage_cache[coverage_key] = value

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
