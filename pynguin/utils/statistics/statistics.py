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
class RuntimeVariable(enum.Enum):
    """Defines all runtime variables we want to store in the result CSV files.

    A runtime variable is either an output of the generation (e.g., obtained coverage)
    or something that can only be determined once the CUT is analysed (e.g., number of
    branches).

    It is perfectly fine to add new runtime variables in this enum, in any position, but
    it is essential to provide a unique name and a description for each new variable, because this
    description will become the text in the result.
    """

    TargetModule = (
        "TargetModule",
        "The module name for which we currently generate tests",
    )
    ConfigurationId = (
        "ConfigurationId",
        "An identifier for this configuration for benchmarking",
    )
    TotalTime = "TotalTime", "Total time spent by Pynguin to generate tests"
    AlgorithmIterations = (
        "AlgorithmIterations",
        "Number of iterations of the test-generation algorithm",
    )
    ExecutionResults = "ExecutionResults", "Execution results"
    MonkeyTypeExecutions = "MonkeyTypeExecutions", "Number of MonkeyType executions"
    ParameterTypeUpdates = "ParameterTypeUpdates", "Updated parameter types"
    ParameterTypeUpdatesSize = (
        "ParameterTypeUpdatesSize",
        "Number of updated parameter types",
    )
    ReturnTypeUpdates = "ReturnTypeUpdates", "Updated return types"
    ReturnTypeUpdatesSize = "ReturnTypeUpdatesSize", "Number of updated return types"
    Coverage = "Coverage", "Obtained coverage of the chosen testing criterion"
    RandomSeed = (
        "RandomSeed",
        "The random seed used during the search. "
        "A random one was used if none was specified in the beginning",
    )
    CoverageTimeline = (
        "CoverageTimeline",
        "Obtained coverage (of the chosen testing criterion) at different points in time",
    )
    SizeTimeline = "SizeTimeline", "Obtained size values at different points in time"
    LengthTimeline = (
        "LengthTimeline",
        "Obtained length values at different points in time",
    )
    FitnessTimeline = (
        "FitnessTimeline",
        "Obtained fitness values at different points in time",
    )
    TotalExceptionsTimeline = "TotalExceptionsTimeline", "Total number of exceptions"
    BranchCoverageTimeline = "BranchCoverageTimeline", "Coverage over time"
    Length = "Length", "Total number of statements in the final test suite"
    PassingLength = (
        "PassingLength",
        "Total number of statements in the final passing test suite",
    )
    FailingLength = (
        "FailingLength",
        "Total number of statements in the final failing test suite",
    )
    Size = "Size", "Number of tests in the resulting test suite"
    FailingSize = "FailingSize", "Number of tests in the resulting failing test suite"
    PassingSize = "PassingSize", "Number of tests in the resulting passing test suite"
    Fitness = "Fitness", "Fitness value of the best individual"
    CodeObjects = "CodeObjects", "Code Objects in the SUT"
    Predicates = "Predicates", "Predicates in the bytecode of the SUT"
    AccessibleObjectsUnderTest = (
        "AccessibleObjectsUnderTest",
        "Accessible objects under test (e.g., methods and functions)",
    )

    def __new__(cls, name: str, description: str) -> RuntimeVariable:
        obj = object.__new__(cls)
        obj._value_ = name
        obj.description = description
        return obj


class StatisticsTracker:
    """A singleton tracker for statistics."""

    _instance: Optional[StatisticsTracker] = None

    def __new__(cls) -> StatisticsTracker:
        if cls._instance is None:
            cls._instance = super(StatisticsTracker, cls).__new__(cls)
            cls._variables: queue.Queue = queue.Queue()
            cls._search_statistics: ss.SearchStatistics = ss.SearchStatistics()
        return cls._instance

    def track_output_variable(self, runtime_variable: RuntimeVariable, value: Any):
        """Tracks a run-time variable for output.

        :param runtime_variable: The run-time variable
        :param value: The value to track for the variable
        """
        self._variables.put((runtime_variable, value))

    @property
    def variables(self) -> queue.Queue:
        """Provides the queue of tracked variables"""
        return self._variables

    @property
    def variables_generator(self) -> Generator[Tuple[RuntimeVariable, Any], None, None]:
        """Provides a generator"""
        while not self._variables.empty():
            yield self._variables.get()

    @property
    def search_statistics(self) -> ss.SearchStatistics:
        """Provides the internal search statistics instance"""
        return self._search_statistics

    def set_sequence_start_time(self, start_time: int):
        """This should only be called once, before any sequence data was generated."""
        self._search_statistics.set_sequence_output_variable_start_time(start_time)

    def current_individual(self, individual: chrom.Chromosome) -> None:
        """Called when a new individual is sent.

        The individual represents the best individual of the current generation.

        :param individual: The best individual of the current generation
        """
        self._search_statistics.current_individual(individual)

    def set_output_variable(self, variable: sb.OutputVariable) -> None:
        """Sets an output variable to a value directly

        :param variable: The variable to be set
        """
        self._search_statistics.set_output_variable(variable)

    def set_output_variable_for_runtime_variable(
        self, variable: RuntimeVariable, value: Any
    ) -> None:
        """Sets an output variable to a value directly

        :param variable: The variable to be set
        :param value: the value to be set
        """
        self._search_statistics.set_output_variable_for_runtime_variable(
            variable, value
        )

    @property
    def output_variables(self) -> Dict[str, sb.OutputVariable]:
        """Provides the output variables"""
        return self._search_statistics.output_variables

    def write_statistics(self) -> bool:
        """Write result to disk using selected backend

        :return: True if the writing was successful
        """
        return self._search_statistics.write_statistics()
