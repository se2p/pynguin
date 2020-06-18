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
"""Dictionary-like structure with information about timers.

Based on the implementation of https://github.com/realpython/codetiming
"""
import collections
import math
import statistics
from typing import Any, Callable, Dict, List


# pylint: disable=too-many-ancestors
class Timers(collections.UserDict):
    """Dictionary-like structure with information about timers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """A private dictionary keeping track of all timings.

        Args:
            args: A list of positional arguments
            kwargs: A dictionary of named arguments
        """
        super().__init__(*args, **kwargs)
        self._timings: Dict[str, List[float]] = collections.defaultdict(list)

    def add(self, name: str, value: float) -> None:
        """Add a timing value to the given timer.

        Args:
            name: The name of the timer
            value: The value that shall be added
        """
        self._timings[name].append(value)
        self.data.setdefault(name, 0)
        self.data[name] += value

    def clear(self) -> None:
        """Clear timers."""
        self.data.clear()
        self._timings.clear()

    def __setitem__(self, key: str, value: float) -> None:
        """Disallow setting of timer values.

        Args:
            key: the name of the property
            value: the value to be set

        Raises:
            TypeError: always as it is not allowed to set timer value
        """
        raise TypeError(
            f"{self.__class__.__name__!r} does not support item assignment. "
            "Use '.add()' to update values."
        )

    def apply(self, func: Callable[[List[float]], float], name: str) -> float:
        """Apply a function to the results of one named timer.

        Args:
            func: The function that should be applied
            name: The name of the timer

        Returns:
            The result of the function application

        Raises:
            KeyError: if the timer was not found
        """
        if name in self._timings:
            return func(self._timings[name])
        raise KeyError(name)

    def count(self, name: str) -> float:
        """Number of timings.

        Args:
            name: The name of the timer

        Returns:
            The number of timings
        """
        return self.apply(len, name=name)

    def total(self, name: str) -> float:
        """Total time for timers.

        Args:
            name: The name of the timer

        Returns:
            The total time for the timer
        """
        return self.apply(sum, name=name)

    def min(self, name: str) -> float:
        """Minimal value of timings.

        Args:
            name: The name of the timer

        Returns:
            The minimal value of the timings
        """
        return self.apply(lambda values: min(values or [0]), name=name)

    def max(self, name: str) -> float:
        """Maximal value of timings.

        Args:
            name: The name of the timer

        Returns:
            The maximal value of the timings
        """
        return self.apply(lambda values: max(values or [0]), name=name)

    def mean(self, name: str) -> float:
        """Mean value of timings.

        Args:
            name: The name of the timer

        Returns:
            The mean value of the timings
        """
        return self.apply(lambda values: statistics.mean(values or [0]), name=name)

    def median(self, name: str) -> float:
        """Median value of timings.

        Args:
            name: The name of the timer

        Returns:
            The median value of the timings
        """
        return self.apply(lambda values: statistics.median(values or [0]), name=name)

    def std_dev(self, name: str) -> float:
        """Standard deviation of timings.

        Args:
            name: The name of the timer

        Returns:
            The standard deviation of timings

        Raises:
            KeyError: if the timer was not found
        """
        if name in self._timings:
            value = self._timings[name]
            return statistics.stdev(value) if len(value) >= 2 else math.nan
        raise KeyError(name)
