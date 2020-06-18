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
"""
Provides an atomic integer implementation similar to the Java class
`AtomicInteger`.
"""
import threading


class AtomicInteger:
    """An atomic integer implementation.

    This class is thread-safe, it does not rely on the global interpreter lock.

    Adapted from https://stackoverflow.com/a/48433648
    """

    def __init__(self, value: int = 0) -> None:
        self._value = value
        self._lock = threading.Lock()

    def inc(self) -> int:
        """Increments the value of the integer by one and returns the new value.

        Returns:
            The new value of the atomic integer
        """
        with self._lock:
            self._value += 1
            return self._value

    def dec(self) -> int:
        """Decrements the value of the integer by one and returns the new value.

        Returns:
            The new value of the atomic integer
        """
        with self._lock:
            self._value -= 1
            return self._value

    @property
    def value(self) -> int:
        """Provides the current value of the atomic integer.

        Returns:
            The current value of the atomic integer
        """
        with self._lock:
            return self._value

    @value.setter
    def value(self, value: int) -> None:
        """Sets the current value of the atomic integer and returns it.

        Args:
            value: The new value for the atomic integer
        """
        with self._lock:
            self._value = value
