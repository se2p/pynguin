#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides abstract factories for output variables."""

from __future__ import annotations

import time
import typing

from abc import ABC
from abc import abstractmethod
from typing import Generic
from typing import TypeVar
from typing import overload

import pynguin.configuration as config
import pynguin.utils.statistics.statisticsbackend as sb


if typing.TYPE_CHECKING:
    import pynguin.ga.chromosome as chrom
    import pynguin.utils.statistics.stats as stat

    from pynguin.utils.statistics.runtimevariable import RuntimeVariable

T = TypeVar("T", int, float)


class ChromosomeOutputVariableFactory(ABC, Generic[T]):
    """Factory to create an output variable when given a test suite chromosome."""

    def __init__(self, variable: RuntimeVariable) -> None:
        """Initializes the factory for a given RuntimeVariable.

        Args:
            variable: The runtime variable for that output variable
        """
        self._variable = variable

    @abstractmethod
    def get_data(self, individual: chrom.Chromosome) -> T:
        """Returns the data value from the individual.

        Args:
            individual: The individual to query

        Returns:
            The current value of the variable in the individual  # noqa: DAR202
        """

    def get_variable(self, individual: chrom.Chromosome) -> sb.OutputVariable[T]:
        """Provides the output variable.

        Args:
            individual: The individual

        Returns:
            The output variable for the individual
        """
        return sb.OutputVariable(name=self._variable.name, value=self.get_data(individual))


class SequenceOutputVariableFactory(ABC, Generic[T]):
    """Creates an output variable that represents a sequence of values."""

    def __init__(self, variable: stat.RuntimeVariable) -> None:  # noqa: D107
        self._variable = variable
        self._time_stamps: list[int] = []
        self._values: list[T] = []
        self._start_time: int = 0

    def set_start_time(self, start_time: int) -> None:
        """Sets the start time.

        Args:
            start_time: the start time
        """
        self._start_time = start_time

    @abstractmethod
    def get_value(self, individual: chrom.Chromosome) -> T:
        """Returns the current value of the variable for the selected individual.

        Args:
            individual: The individual to query

        Returns:
            The current value of the variable in the individual  # noqa: DAR202
        """

    def update(self, individual: chrom.Chromosome) -> None:
        """Updates the values for an individual.

        Args:
            individual: The individual
        """
        self._time_stamps.append(time.time_ns() - self._start_time)
        self._values.append(self.get_value(individual))

    @overload
    def update_value(self, value: int) -> None: ...

    @overload
    def update_value(self, value: float) -> None: ...

    def update_value(self, value) -> None:
        """Updates the value directly.

        Args:
            value: The value
        """
        self._time_stamps.append(time.time_ns() - self._start_time)
        self._values.append(value)

    def get_variable_names_indices(self) -> list[tuple[int, str]]:
        """Provides a list of variable names.

        Returns:
            A list of pairs consisting of variable names and their index.
        """
        return [
            (i + 1, f"{self._variable.name}_T{i + 1}")
            for i in range(self._calculate_number_of_intervals())
        ]

    def get_output_variables(self) -> list[sb.OutputVariable[T]]:
        """Provides the output variables.

        Returns:
            A list of output variables
        """
        return [
            sb.OutputVariable(name=variable_name, value=self._get_time_line_value(variable_index))
            for variable_index, variable_name in self.get_variable_names_indices()
        ]

    @property
    def area_under_curve(self) -> float:
        """Provides the area under the curve using trapezoid approximation."""
        assert config.configuration.stopping.maximum_search_time is not None
        time_stamps_values: list[tuple[float, float]] = list(
            zip(self._time_stamps, self._values, strict=True)
        )
        run_time = self._time_stamps[-1] / 1_000_000_000

        area = 0.0
        previous_value = 0.0
        previous_time_stamp = 0.0
        for time_stamp, value in time_stamps_values:
            time_delta = time_stamp - previous_time_stamp
            # Taking the abs should actually not be necessary, because time_delta should
            # always be >= 0, but to prevent issues with rounding, etc....
            current_area = abs((previous_value + value) / 2 * time_delta)
            area += current_area
            previous_time_stamp = time_stamp
            previous_value = value

        if run_time < config.configuration.stopping.maximum_search_time:
            area += (config.configuration.stopping.maximum_search_time - run_time) * self._values[
                -1
            ]

        return area / 1_000_000_000

    @property
    def normalised_area_under_curve(self) -> float:
        """Provides the normalised area under curve using trapezoid approximation."""
        assert config.configuration.stopping.maximum_search_time is not None
        run_time = self._time_stamps[-1] / 1_000_000_000
        if run_time >= config.configuration.stopping.maximum_search_time:
            normalised_area = self.area_under_curve / run_time
        else:
            last_value = self._values[-1]
            time_delta = config.configuration.stopping.maximum_search_time - run_time
            normalised_area = (
                self.area_under_curve + last_value * time_delta
            ) / config.configuration.stopping.maximum_search_time
        assert 0.0 <= normalised_area <= 1.0, f"Normalised AuC out of range ({normalised_area})!"
        return normalised_area

    @property
    def area_under_curve_output_variable(self) -> sb.OutputVariable[float]:
        """Provides the output variable for area under curve."""
        return sb.OutputVariable(name=f"{self._variable.name}_AUC", value=self.area_under_curve)

    @property
    def normalised_area_under_curve_output_variable(self) -> sb.OutputVariable[float]:
        """Provides the output variable for normalised area under curve."""
        return sb.OutputVariable(
            name=f"{self._variable.name}_nAUC", value=self.normalised_area_under_curve
        )

    def _get_time_line_value(self, index: int) -> T:
        if not self._time_stamps:
            # No data, if this is even possible.
            return 0
        interval = config.configuration.statistics_output.timeline_interval
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

            if not config.configuration.statistics_output.timeline_interpolation:
                # if we do not want to interpolate, return last observed value
                return self._values[i - 1]

            # interpolate the value, since we do not have the value for the exact
            # time we want
            time_delta = self._time_stamps[i] - self._time_stamps[i - 1]
            if time_delta > 0:
                value_delta = float(self._values[i]) - float(self._values[i - 1])
                ratio = value_delta / time_delta
                diff = preferred_time - self._time_stamps[i - 1]
                return float(self._values[i - 1]) + (  # type: ignore[return-value]
                    diff * ratio
                )

        # no time stamp was higher, just use the last value seen
        return self._values[-1]

    @staticmethod
    def _calculate_number_of_intervals() -> int:
        interval = config.configuration.statistics_output.timeline_interval
        assert config.configuration.stopping.maximum_search_time is not None
        total_time = config.configuration.stopping.maximum_search_time * 1_000_000_000
        number_of_intervals = total_time // interval
        return int(number_of_intervals)


class DirectSequenceOutputVariableFactory(SequenceOutputVariableFactory, Generic[T]):
    """Sequence output variable whose value can be set directly."""

    def __init__(self, variable: RuntimeVariable, start_value: T) -> None:  # noqa: D107
        super().__init__(variable)
        self._value = start_value  # type: ignore[var-annotated]

    def get_value(self, individual) -> T:  # noqa: D102
        return self._value

    def set_value(self, value: T) -> None:
        """Sets the value directly.

        Args:
            value: the value to be set
        """
        self._value = value

    @staticmethod
    def get_float(
        variable: RuntimeVariable,
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
        variable: RuntimeVariable,
    ) -> DirectSequenceOutputVariableFactory:
        """Creates a factory for an integer variable.

        Args:
            variable: the runtime variable

        Returns:
            A factory for that variable
        """
        return DirectSequenceOutputVariableFactory(variable, 0)


class TypeEvolutionSequenceOutputVariableFactory(DirectSequenceOutputVariableFactory, Generic[T]):
    """A sequence output variable for type-information evolution."""

    def __init__(self, variable: RuntimeVariable, start_value: T) -> None:  # noqa: D107
        super().__init__(variable, start_value)

    def get_value(self, individual: chrom.Chromosome) -> T:  # noqa: D102
        return self._values[-1]

    def update(self, individual: chrom.Chromosome) -> None:  # noqa: D102
        pass  # do nothing on purpose for this variable, use `update_value` instead

    def _get_time_line_value(self, index: int) -> T:
        if not self._time_stamps:
            # No data, if this is even possible.
            raise ValueError("Cannot get timeline if no time stamps exist.")
        interval = config.configuration.statistics_output.timeline_interval
        preferred_time = interval * index

        for i in range(len(self._time_stamps)):
            # find the first stamp that is following the time we would like to get the
            # value for
            stamp = self._time_stamps[i]
            if stamp < preferred_time:
                continue
            if i == 0:
                # it is the first element, just use it as value
                return self._values[i]
            # we cannot interpolate, thus return the last observed value
            return self._values[i - 1]
        # no time stamp was higher, just use the last value seen
        return self._values[-1]
