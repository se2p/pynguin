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
"""Provides abstract factories for output variables"""
from __future__ import annotations

import time
from abc import ABCMeta, abstractmethod
from typing import Generic, List, Tuple, TypeVar

import pynguin.configuration as config
import pynguin.testsuite.testsuitechromosome as tsc
import pynguin.utils.statistics.statistics as stat  # pylint: disable=cyclic-import
import pynguin.utils.statistics.statisticsbackend as sb

T = TypeVar("T", int, float)  # pylint: disable=invalid-name


class ChromosomeOutputVariableFactory(Generic[T], metaclass=ABCMeta):
    """Factory to create an output variable when given a test suite chromosome"""

    def __init__(self, variable: stat.RuntimeVariable) -> None:
        self._variable = variable

    @abstractmethod
    def get_data(self, individual: tsc.TestSuiteChromosome) -> T:
        """Returns the data value from the individual.

        Args:
            individual: The individual to query

        Returns:
            The current value of the variable in the individual  # noqa: DAR202
        """

    def get_variable(self, individual: tsc.TestSuiteChromosome) -> sb.OutputVariable[T]:
        """Provides the output variable

        Args:
            individual: The individual

        Returns:
            The output variable for the individual
        """
        return sb.OutputVariable(
            name=self._variable.name, value=self.get_data(individual)
        )


class SequenceOutputVariableFactory(Generic[T], metaclass=ABCMeta):
    """Creates an output variable that represents a sequence of values"""

    def __init__(self, variable: stat.RuntimeVariable) -> None:
        self._variable = variable
        self._time_stamps: List[int] = []
        self._values: List[T] = []
        self._start_time: int = 0

    def set_start_time(self, start_time: int) -> None:
        """Sets the start time.

        Args:
            start_time: the start time
        """
        self._start_time = start_time

    @abstractmethod
    def get_value(self, individual: tsc.TestSuiteChromosome) -> T:
        """Returns the current value of the variable for the selected individual

        Args:
            individual: The individual to query

        Returns:
            The current value of the variable in the individual  # noqa: DAR202
        """

    def update(self, individual: tsc.TestSuiteChromosome) -> None:
        """Updates the values for an individual

        Args:
            individual: The individual
        """
        self._time_stamps.append(time.time_ns() - self._start_time)
        self._values.append(self.get_value(individual))

    def get_variable_names_indices(self) -> List[Tuple[int, str]]:
        """Provides a list of variable names

        Returns:
            A list of pairs consisting of variable names and their index.
        """
        return [
            (i + 1, f"{self._variable.name}_T{i + 1}")
            for i in range(self._calculate_number_of_intervals())
        ]

    def get_output_variables(self) -> List[sb.OutputVariable[T]]:
        """Provides the output variables

        Returns:
            A list of output variables
        """
        return [
            sb.OutputVariable(
                name=variable_name, value=self._get_time_line_value(variable_index)
            )
            for variable_index, variable_name in self.get_variable_names_indices()
        ]

    def _get_time_line_value(self, index: int) -> T:
        if not self._time_stamps:
            # No data, if this is even possible.
            return 0
        interval = config.INSTANCE.timeline_interval
        preferred_time = interval * index
        for i in range(len(self._time_stamps)):
            # find the first stamp that is following the time we would like to get
            # the value for
            stamp = self._time_stamps[i]
            if stamp < preferred_time:
                continue

            if i == 0:
                # it is the first element, just use it as value
                return self._values[i]

            if not config.INSTANCE.timeline_interpolation:
                # if we do not want to interpolate, return last observed value
                return self._values[i - 1]

            # interpolate the value, since we do not have the value for the exact
            # time we want
            time_delta = self._time_stamps[i] - self._time_stamps[i - 1]
            if time_delta > 0:
                value_delta = float(self._values[i]) - float(self._values[i - 1])
                ratio = value_delta / time_delta
                diff = preferred_time - self._time_stamps[i - 1]
                value = float(self._values[i - 1]) + (diff * ratio)
                return value  # type: ignore

        # no time stamp was higher, just use the last value seen
        return self._values[-1]

    @staticmethod
    def _calculate_number_of_intervals() -> int:
        interval = config.INSTANCE.timeline_interval
        total_time = config.INSTANCE.budget * 1_000_000_000
        number_of_intervals = total_time // interval
        return int(number_of_intervals)


class DirectSequenceOutputVariableFactory(SequenceOutputVariableFactory, Generic[T]):
    """Sequence output variable whose value can be set directly, instead of
    retrieving it from an individual"""

    def __init__(self, variable: stat.RuntimeVariable, start_value: T) -> None:
        super().__init__(variable)
        self._value = start_value  # type: ignore

    def get_value(self, individual) -> T:
        return self._value

    def set_value(self, value: T) -> None:
        """Sets the value directly.

        Args:
            value: the value to be set
        """
        self._value = value

    @staticmethod
    def get_float(
        variable: stat.RuntimeVariable,
    ) -> DirectSequenceOutputVariableFactory:
        """Creates a factory for a float variable.

        Args:
            variable: the runtime variable

        Returns:
            A factory for that variable
        """
        return DirectSequenceOutputVariableFactory(variable, 0.0)

    @staticmethod
    def get_integer(
        variable: stat.RuntimeVariable,
    ) -> DirectSequenceOutputVariableFactory:
        """Creates a factory for an integer variable.

        Args:
            variable: the runtime variable

        Returns:
            A factory for that variable
        """
        return DirectSequenceOutputVariableFactory(variable, 0)
