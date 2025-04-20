#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an atomic integer implementation."""

import threading


class AtomicInteger:
    """An atomic integer implementation.

    This class is thread-safe, it does not rely on the global interpreter lock.

    Adapted from https://stackoverflow.com/a/48433648
    """

    def __init__(self, value: int = 0) -> None:
        """Initializes the atomic integer.

        Args:
            value: The start value, defaults to zero.
        """
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
