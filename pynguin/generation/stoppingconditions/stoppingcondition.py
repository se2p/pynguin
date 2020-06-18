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
"""Provides an interface for a stopping condition of the algorithm."""
from abc import ABCMeta, abstractmethod


class StoppingCondition(metaclass=ABCMeta):
    """Provides an interface for a stopping condition of the algorithm."""

    _current_value = 0

    @property
    def current_value(self) -> int:
        """Provide how much of the budget we have used.

        Returns:
            The current value of the budget
        """
        return self._current_value

    @current_value.setter
    def current_value(self, value: int) -> None:
        """Forces a specific amount of used budget.  Handle with care!

        Args:
            value: The new amount of used budget for this StoppingCondition
        """
        self._current_value = value

    @abstractmethod
    def limit(self) -> int:
        """Get upper limit of resources.

        Mainly used for `__repr__()` and `__str__()`

        Returns:
            The limit  # noqa: DAR202
        """

    @abstractmethod
    def is_fulfilled(self) -> bool:
        """Returns whether the condition is fulfilled, thus the algorithm should stop

        Returns:
            True if the condition is fulfilled, False otherwise  # noqa: DAR202
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset everything."""

    @abstractmethod
    def set_limit(self, limit: int) -> None:
        """Sets new upper limit of resources.

        Args:
            limit: The new upper limit
        """

    @abstractmethod
    def iterate(self) -> None:
        """Shall be called in each algorithm iteration.

        Does nothing if the stopping condition does not care for algorithm
        iterations, it must not raise an exception in such a case!
        """
