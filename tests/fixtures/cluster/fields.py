#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""A fixture module exercising public field/property discovery."""


class Helper:
    """A helper type used as a non-primitive field type."""


class WithFields:
    """A class exposing public class attributes and a public property."""

    counter: int = 0
    helper: Helper = Helper()

    def __init__(self) -> None:
        """Initialise the instance value."""
        self._value = 1

    @property
    def value(self) -> int:
        """Return the current value.

        Returns:
            The stored value.
        """
        return self._value

    def _private(self) -> int:
        """Return a private helper value.

        Returns:
            A constant.
        """
        return 42
