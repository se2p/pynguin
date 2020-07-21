# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides tracking of statistics for various variables and types."""
from __future__ import annotations

import enum
import queue
from typing import Any, Dict, Generator, Optional, Tuple

import pynguin.ga.chromosome as chrom
import pynguin.utils.statistics.searchstatistics as ss  # pylint: disable=cyclic-import
import pynguin.utils.statistics.statisticsbackend as sb


@enum.unique
class RuntimeVariable(str, enum.Enum):
    """Defines all runtime variables we want to store in the result CSV files.

    A runtime variable is either an output of the generation (e.g., obtained coverage)
    or something that can only be determined once the CUT is analysed (e.g., number of
    branches).

    It is perfectly fine to add new runtime variables in this enum, in any position, but
    it is essential to provide a unique name and a description for each new variable,
    because this description will become the text in the result.
    """

    # The module name for which we currently generate tests
    TargetModule = "TargetModule"

    # An identifier for this configuration for benchmarking
    ConfigurationId = "ConfigurationId"

    # Total time spent by Pynguin to generate tests
    TotalTime = "TotalTime"

    # Number of iterations of the test-generation algorithm
    AlgorithmIterations = "AlgorithmIterations"

    # Execution results
    ExecutionResults = "ExecutionResults"

    # Number of MonkeyType executions
    MonkeyTypeExecutions = "MonkeyTypeExecutions"

    # Updated parameter types
    ParameterTypeUpdates = "ParameterTypeUpdates"

    # "Number of updated parameter types"
    ParameterTypeUpdatesSize = "ParameterTypeUpdatesSize"

    # Updated return types
    ReturnTypeUpdates = "ReturnTypeUpdates"

    # Number of updated return types
    ReturnTypeUpdatesSize = "ReturnTypeUpdatesSize"

    # Obtained coverage of the chosen testing criterion
    Coverage = "Coverage"

    # The random seed used during the search.
    # A random one was used if none was specified in the beginning
    RandomSeed = "RandomSeed"

    # Obtained coverage (of the chosen testing criterion) at different points in time
    CoverageTimeline = "CoverageTimeline"

    # Obtained size values at different points in time
    SizeTimeline = "SizeTimeline"

    # Obtained length values at different points in time
    LengthTimeline = "LengthTimeline"

    # Obtained fitness values at different points in time
    FitnessTimeline = "FitnessTimeline"

    # Total number of exceptions
    TotalExceptionsTimeline = "TotalExceptionsTimeline"

    # Coverage over time
    BranchCoverageTimeline = "BranchCoverageTimeline"

    # Total number of statements in the final test suite
    Length = "Length"

    # Total number of statements in the final passing test suite
    PassingLength = "PassingLength"

    # Total number of statements in the final failing test suite
    FailingLength = "FailingLength"

    # Number of tests in the resulting test suite
    Size = "Size"

    # Number of tests in the resulting failing test suite
    FailingSize = "FailingSize"

    # Number of tests in the resulting passing test suite
    PassingSize = "PassingSize"

    # Fitness value of the best individual
    Fitness = "Fitness"

    # Code Objects in the SUT
    CodeObjects = "CodeObjects"

    # Predicates in the bytecode of the SUT
    Predicates = "Predicates"

    # Accessible objects under test (e.g., methods and functions)
    AccessibleObjectsUnderTest = "AccessibleObjectsUnderTest"

    # Number of all generatable types, i.e., the types we can generate values for
    GeneratableTypes = "GeneratableTypes"

    def __repr__(self):
        return f"{self.name}"


class StatisticsTracker:
    """A singleton tracker for statistics."""

    _instance: Optional[StatisticsTracker] = None

    def __new__(cls) -> StatisticsTracker:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._variables: queue.Queue = queue.Queue()
            cls._search_statistics: ss.SearchStatistics = ss.SearchStatistics()
        return cls._instance

    def track_output_variable(self, runtime_variable: RuntimeVariable, value: Any):
        """Tracks a run-time variable for output.

        Args:
            runtime_variable: The run-time variable
            value: The value to track for the variable
        """
        self._variables.put((runtime_variable, value))

    @property
    def variables(self) -> queue.Queue:
        """Provides the queue of tracked variables.

        Returns:
            The queue of tracked variables
        """
        return self._variables

    @property
    def variables_generator(self) -> Generator[Tuple[RuntimeVariable, Any], None, None]:
        """Provides a generator.

        Yields:
            A generator for iteration
        """
        while not self._variables.empty():
            yield self._variables.get()

    @property
    def search_statistics(self) -> ss.SearchStatistics:
        """Provides the internal search statistics instance.

        Returns:
            The search statistics instance
        """
        return self._search_statistics

    def set_sequence_start_time(self, start_time: int) -> None:
        """This should only be called once, before any sequence data was generated.

        Args:
            start_time: the start time
        """
        self._search_statistics.set_sequence_output_variable_start_time(start_time)

    def current_individual(self, individual: chrom.Chromosome) -> None:
        """Called when a new individual is sent.

        The individual represents the best individual of the current generation.

        Args:
            individual: The best individual of the current generation
        """
        self._search_statistics.current_individual(individual)

    def set_output_variable(self, variable: sb.OutputVariable) -> None:
        """Sets an output variable to a value directly

        Args:
            variable: The variable to be set
        """
        self._search_statistics.set_output_variable(variable)

    def set_output_variable_for_runtime_variable(
        self, variable: RuntimeVariable, value: Any
    ) -> None:
        """Sets an output variable to a value directly

        Args:
            variable: The variable to be set
            value: the value to be set
        """
        self._search_statistics.set_output_variable_for_runtime_variable(
            variable, value
        )

    @property
    def output_variables(self) -> Dict[str, sb.OutputVariable]:
        """Provides the output variables.

        Returns:
            The output variables
        """
        return self._search_statistics.output_variables

    def write_statistics(self) -> bool:
        """Write result to disk using selected backend

        Returns:
            True if the writing was successful
        """
        return self._search_statistics.write_statistics()
